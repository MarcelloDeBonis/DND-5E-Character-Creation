"""Renderer: disegna la scheda calcolata sopra il template PDF ufficiale.

Il template e la mappa dei campi (coordinate) stanno in `templates/<nome>/`.
Il testo viene disegnato con reportlab su un overlay trasparente, poi fuso con
le pagine del template; i campi modulo originali vengono rimossi (PDF statico).
"""
from __future__ import annotations

import io
from pathlib import Path
from xml.sax.saxutils import escape

import yaml
from pypdf import PdfReader, PdfWriter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, KeepInFrame, Paragraph

from .engine import ABILITIES, fmt_cr, fmt_mod

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

FONT_CANDIDATES = {
    "Serif": ("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", "Times-Roman"),
    "Serif-Bold": ("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf", "Times-Bold"),
    "Serif-Italic": ("/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf", "Times-Italic"),
    "Serif-BoldItalic": ("/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf", "Times-BoldItalic"),
    "Sans": ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "Helvetica"),
    "Sans-Bold": ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "Helvetica-Bold"),
}
FONTS: dict[str, str] = {}


def _register_fonts() -> None:
    if FONTS:
        return
    for alias, (path, fallback) in FONT_CANDIDATES.items():
        if Path(path).exists():
            pdfmetrics.registerFont(TTFont(alias, path))
            FONTS[alias] = alias
        else:
            FONTS[alias] = fallback
    pdfmetrics.registerFontFamily(
        FONTS["Serif"], normal=FONTS["Serif"], bold=FONTS["Serif-Bold"],
        italic=FONTS["Serif-Italic"], boldItalic=FONTS["Serif-BoldItalic"],
    )


# Campi numerici o brevi da centrare
CENTERED = {
    "inspiration", "prof_bonus", "ac", "initiative", "speed", "passive_perception",
    "cp", "sp", "ep", "gp", "pp", "hp_max", "hd_total", "hd",
    "spellcasting_ability", "spell_save_dc", "spell_attack_bonus",
}
BIG = {"ac", "initiative", "speed", "prof_bonus", "inspiration", "passive_perception"}


class SheetRenderer:
    def __init__(self, template: str = "official"):
        _register_fonts()
        self.dir = TEMPLATES_DIR / template
        meta = yaml.safe_load((self.dir / "fieldmap.yaml").read_text(encoding="utf-8"))
        self.page_size = tuple(meta["page_size"])
        self.fields = meta["fields"]
        pdfs = sorted(self.dir.glob("*.pdf"))
        if not pdfs:
            raise FileNotFoundError(f"Nessun PDF template in {self.dir}")
        self.template_pdf = pdfs[0]

    # ------------------------------------------------------------------ primitives
    def _rect(self, name: str):
        f = self.fields[name]
        return f["page"], f["rect"]

    def text(self, c, name, value, size=10, font="Sans", min_size=5, align=None):
        if value is None or value == "":
            return
        page, (x1, y1, x2, y2) = self._rect(name)
        if page != self._page:
            return
        value = str(value)
        w, h = x2 - x1 - 3, y2 - y1
        size = min(size, h * 0.85)
        fname = FONTS[font]
        while pdfmetrics.stringWidth(value, fname, size) > w and size > min_size:
            size -= 0.5
        c.setFont(fname, size)
        baseline = y1 + (h - size * 0.7) / 2
        if align is None:
            align = "center" if name in CENTERED or name.endswith(("_score", "_mod")) or name.startswith(("save_", "skill_")) else "left"
        if align == "center":
            c.drawCentredString((x1 + x2) / 2, baseline, value)
        else:
            c.drawString(x1 + 2, baseline, value)

    def check(self, c, name, on=True):
        if not on:
            return
        page, (x1, y1, x2, y2) = self._rect(name)
        if page != self._page:
            return
        r = min(x2 - x1, y2 - y1) * 0.36
        c.setFillGray(0.1)
        c.circle((x1 + x2) / 2, (y1 + y2) / 2, r, stroke=0, fill=1)
        c.setFillGray(0)

    def box(self, c, name, paragraphs, size=8.5, min_size=5, font="Serif", leading=1.2, align="left"):
        """Testo multi-paragrafo che si restringe per entrare nel riquadro.

        `paragraphs` è una lista di stringhe (markup minimo <b>/<i> consentito) oppure una stringa
        con righe separate da newline.
        """
        if not paragraphs:
            return
        page, (x1, y1, x2, y2) = self._rect(name)
        if page != self._page:
            return
        if isinstance(paragraphs, str):
            paragraphs = [p for p in paragraphs.split("\n")]
        w, h = x2 - x1 - 6, y2 - y1 - 6
        style = ParagraphStyle(
            name, fontName=FONTS[font], fontSize=size, leading=size * leading,
            spaceAfter=size * 0.35, alignment={"left": 0, "center": 1, "justify": 4}[align],
        )
        flow = [Paragraph(p if p.strip() else "&nbsp;", style) for p in paragraphs]
        kif = KeepInFrame(w, h, flow, mode="shrink")
        frame = Frame(x1 + 3, y1 + 3, w, h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
        frame.addFromList([kif], c)

    def image(self, c, name, path):
        if not path or not Path(path).exists():
            return
        page, (x1, y1, x2, y2) = self._rect(name)
        if page != self._page:
            return
        img = ImageReader(str(path))
        iw, ih = img.getSize()
        w, h = x2 - x1 - 4, y2 - y1 - 4
        scale = min(w / iw, h / ih)
        dw, dh = iw * scale, ih * scale
        c.drawImage(img, x1 + 2 + (w - dw) / 2, y1 + 2 + (h - dh) / 2, dw, dh, mask="auto")

    # ------------------------------------------------------------------ page content
    def draw_page(self, c, sheet: dict, page: int):
        self._page = page
        getattr(self, f"_draw_page_{page}")(c, sheet)

    def _draw_page_0(self, c, s):
        a = s["abilities"]
        self.text(c, "character_name", s["name"], size=14, font="Serif-Bold")
        self.text(c, "class_level", s["class_level"] + (f" ({s['subclass_name']})" if s["subclass_name"] else ""), size=9)
        self.text(c, "background", s["background"]["name"], size=9)
        self.text(c, "player_name", s["player"], size=9)
        self.text(c, "race", s["race"]["name"], size=9)
        self.text(c, "alignment", s["alignment"], size=9)
        self.text(c, "xp", str(s["xp"]), size=9)
        for k in ABILITIES:
            self.text(c, f"{k}_score", str(a["scores"][k]), size=20, font="Sans-Bold")
            self.text(c, f"{k}_mod", fmt_mod(a["mods"][k]), size=10)
            self.text(c, f"save_{k}", fmt_mod(s["saves"][k]["value"]), size=8)
            self.check(c, f"save_{k}_prof", s["saves"][k]["proficient"])
        self.text(c, "prof_bonus", fmt_mod(s["proficiency_bonus"]), size=12, font="Sans-Bold")
        for k, sk in s["skills"].items():
            self.text(c, f"skill_{k}", fmt_mod(sk["value"]), size=8)
            self.check(c, f"skill_{k}_prof", sk["proficient"])
        self.text(c, "passive_perception", str(s["passive_perception"]), size=12, font="Sans-Bold")
        self.text(c, "ac", str(s["ac"]["value"]), size=16, font="Sans-Bold")
        self.text(c, "initiative", fmt_mod(s["initiative"]), size=16, font="Sans-Bold")
        self.text(c, "speed", s["speed_m"], size=12, font="Sans-Bold")
        self.text(c, "hp_max", str(s["hp"]["max"]), size=10, font="Sans-Bold")
        self.text(c, "hd_total", s["hp"]["hit_dice"], size=8)
        self.text(c, "hd", f"1d{s['class']['hit_die']}", size=11)
        for i, w in enumerate(s["weapons"][:3], start=1):
            self.text(c, f"weapon_{i}_name", w["name"], size=8.5)
            self.text(c, f"weapon_{i}_atk", w["attack_str"], size=9, align="center")
            self.text(c, f"weapon_{i}_dmg", w["damage"], size=7.5)
        # riquadro attacchi: armi oltre la terza, dettagli, trucchetti e manovre
        atk = []
        for w in s["weapons"][3:]:
            atk.append(f"<b>{esc(w['name'])}</b> {esc(w['attack_str'])}, {esc(w['damage'])}")
        for w in s["weapons"]:
            det = ", ".join(w["properties"] + w["notes"])
            if det:
                atk.append(f"<i>{esc(w['name'])}</i>: {esc(det)}")
        if s["maneuvers"]:
            atk.append("<b>Manovre</b> (dadi di superiorità): " + esc(", ".join(m["name"] for m in s["maneuvers"])))
        sp = s["spellcasting"]
        if sp:
            for at in sp["spell_attacks"]:
                atk.append(f"<b>{esc(at['name'])}</b> {esc(at['attack_str'])}, {esc(at['damage'])}" + (f" (gittata {esc(at['range'])} m)" if at.get("range") else ""))
            atk.append(f"<b>Incantesimi:</b> {esc(sp['ability_name'])}, CD {sp['save_dc']}, attacco {esc(fmt_mod(sp['attack_bonus']))}"
                       + (", slot " + ", ".join(f"{n}×{lvl}°" for lvl, n in sp["slots"].items()) if sp["slots"] else "") + ". Vedi pagina 3.")
        ws = s["wild_shape"]
        if ws:
            top = [b["name"] for b in ws["forms"] if b["cr"] == ws["max_cr"]][:6]
            atk.append(f"<b>Forma Selvatica</b> (GS max {esc(ws['max_cr_str'])}, {ws['uses']} usi, {ws['duration_hours']} h): "
                       + esc(", ".join(top)) + "... (tabella completa in appendice)")
        if s["attacks_notes"]:
            atk += [esc(x) for x in s["attacks_notes"].split("\n")]
        self.box(c, "attacks_spellcasting", atk, size=7.5)
        # equipaggiamento
        eq = [esc(e) for e in s["equipment"]]
        self.box(c, "equipment", eq, size=7.5)
        for k in ("cp", "sp", "ep", "gp", "pp"):
            if s["money"].get(k):
                self.text(c, k, str(s["money"][k]), size=10)
        # personalità
        p = s["personality"]
        self.box(c, "personality_traits", esc(p.get("traits", "")), size=8)
        self.box(c, "ideals", esc(p.get("ideals", "")), size=8)
        self.box(c, "bonds", esc(p.get("bonds", "")), size=8)
        self.box(c, "flaws", esc(p.get("flaws", "")), size=8)
        # privilegi (versione breve)
        feats = []
        for f in s["features"] + s["fighting_styles"] + ([s["background_feature"]] if s["background_feature"] else []):
            feats.append(f"<b>{esc(f['name'])}.</b> {esc(f['short'])}")
        self.box(c, "features_traits", feats, size=7.5)
        # competenze e linguaggi
        pr = s["proficiencies"]
        prof_lines = [
            f"<b>Armature:</b> {esc(', '.join(pr['armor']) or 'nessuna')}",
            f"<b>Armi:</b> {esc(', '.join(pr['weapons']) or 'nessuna')}",
            f"<b>Strumenti:</b> {esc(', '.join(pr['tools']) or 'nessuno')}",
            f"<b>Linguaggi:</b> {esc(', '.join(s['languages']))}",
        ]
        self.box(c, "proficiencies_languages", prof_lines, size=8)

    def _draw_page_1(self, c, s):
        ap = s["appearance"]
        self.text(c, "character_name_2", s["name"], size=14, font="Serif-Bold")
        for k in ("age", "height", "weight", "eyes", "skin", "hair"):
            self.text(c, k, ap.get(k, ""), size=9)
        self.image(c, "portrait", s["portrait"])
        self.box(c, "allies", esc(s["allies"]), size=8.5)
        self.box(c, "backstory", esc(s["backstory"]), size=8.5, align="justify")
        feats = []
        for f in s["fighting_styles"] + ([s["background_feature"]] if s["background_feature"] else []):
            feats.append(f"<b>{esc(f['name'])}.</b> {esc(f['text'])}")
        for m in s["maneuvers"]:
            feats.append(f"<b>Manovra: {esc(m['name'])}.</b> {esc(m['text'])}")
        for cn in s["cantrips"]:
            feats.append(f"<b>Trucchetto: {esc(cn['name'])}</b> ({esc(cn['source'])}). {esc(cn.get('text', ''))}")
        ws = s["wild_shape"]
        if ws:
            feats.append(f"<b>Forma Selvatica.</b> GS massimo {esc(ws['max_cr_str'])}, volo {'sì' if ws['fly'] else 'no'}, nuoto {'sì' if ws['swim'] else 'no'}; "
                         f"{ws['uses']} usi per riposo breve o lungo, durata {ws['duration_hours']} ora/e. Forme: " + esc(", ".join(b["name"] for b in ws["forms"])) + ".")
        if s["extra_features"]:
            feats += [esc(x) for x in s["extra_features"].split("\n")]
        feats.append("<i>Le descrizioni complete di tratti, privilegi, incantesimi e forme animali sono nelle pagine di appendice.</i>")
        self.box(c, "additional_features", feats, size=8)
        self.box(c, "treasure", esc(s["treasure"]), size=8.5)

    def _draw_page_2(self, c, s):
        sp = s["spellcasting"]
        if not sp:
            return
        title = s["class"]["name"] if sp["class_caster"] else s["race"]["name"]
        self.text(c, "spellcasting_class", title, size=12, font="Serif-Bold")
        self.text(c, "spellcasting_ability", sp["ability_name"], size=9)
        self.text(c, "spell_save_dc", str(sp["save_dc"]), size=14, font="Sans-Bold")
        self.text(c, "spell_attack_bonus", fmt_mod(sp["attack_bonus"]), size=14, font="Sans-Bold")
        for i, cn in enumerate(sp["cantrips"][:8], start=1):
            self.text(c, f"cantrip_{i}", cn["name"] + ("" if cn["source"] == s["class"]["name"] else f" ({cn['source']})"), size=8.5)
        for lvl in range(1, 10):
            n = sp["slots"].get(lvl)
            if n:
                self.text(c, f"slots_total_{lvl}", str(n), size=12, font="Sans-Bold")
            spells = sp["spells_by_level"].get(lvl, [])
            for i, spell in enumerate(spells, start=1):
                if f"spell_{lvl}_{i}" not in self.fields:
                    break
                label = spell["name"] + (" (C)" if spell.get("conc") else "") + (" (R)" if spell.get("ritual") else "")
                if spell.get("always_prepared"):
                    label += " [circolo]"
                self.text(c, f"spell_{lvl}_{i}", label, size=8)
                if f"spell_{lvl}_{i}_prep" in self.fields and (sp["prepares"] or spell.get("always_prepared")):
                    self.check(c, f"spell_{lvl}_{i}_prep", True)

    # ------------------------------------------------------------------ appendix
    def appendix_pdf(self, s: dict) -> bytes:
        """Pagina/e extra con le descrizioni complete di tratti, privilegi, manovre e trucchetti."""
        from reportlab.platypus import BaseDocTemplate, PageTemplate, Spacer
        buf = io.BytesIO()
        W, H = self.page_size
        margin, gutter = 40, 14
        colw = (W - 2 * margin - gutter) / 2
        frames = [Frame(margin, 40, colw, H - 110, id="c1", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
                  Frame(margin + colw + gutter, 40, colw, H - 110, id="c2", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]
        title = f"{s['name']} — {s['race']['name']} {s['class_level']}"

        def header(c, doc):
            c.saveState()
            c.setFont(FONTS["Serif-Bold"], 15)
            c.drawString(margin, H - 50, title)
            c.setFont(FONTS["Sans"], 8)
            c.drawString(margin, H - 62, "Appendice: descrizioni complete di tratti razziali, privilegi di classe, manovre, incantesimi e forme animali")
            c.setLineWidth(0.8)
            c.line(margin, H - 68, W - margin, H - 68)
            c.setFont(FONTS["Sans"], 7)
            c.drawRightString(W - margin, 25, f"Pagina {doc.page}")
            c.restoreState()

        doc = BaseDocTemplate(buf, pagesize=self.page_size, title=f"Scheda personaggio - {s['name']} (appendice)")
        doc.addPageTemplates([PageTemplate(id="two", frames=frames, onPage=header)])
        h_style = ParagraphStyle("h", fontName=FONTS["Serif-Bold"], fontSize=11, leading=13, spaceBefore=8, spaceAfter=3)
        b_style = ParagraphStyle("b", fontName=FONTS["Serif"], fontSize=8.5, leading=10.5, spaceAfter=4, alignment=4)
        story = []

        def section(heading, items):
            if not items:
                return
            story.append(Paragraph(esc(heading), h_style))
            for name, text in items:
                story.append(Paragraph(f"<b>{esc(name)}.</b> {esc(text)}", b_style))

        race_items = [(f["name"], f["text"] or f["short"]) for f in s["features"] if f["source"] == s["race"]["name"]]
        class_items = [(f"{f['name']} ({f['level']}° livello, {f['source']})", f["text"] or f["short"]) for f in s["features"] if f["source"] != s["race"]["name"]]
        section(f"Tratti razziali: {s['race']['name']}", race_items)
        section(f"Privilegi di classe: {s['class_level']}" + (f", {s['subclass_name']}" if s["subclass_name"] else ""), class_items)
        section("Stile di combattimento", [(f["name"].split(": ", 1)[-1], f["text"]) for f in s["fighting_styles"]])
        section("Manovre", [(m["name"], m["text"]) for m in s["maneuvers"]])
        if s["background_feature"]:
            section(f"Privilegio del background: {s['background']['name']}", [(s["background_feature"]["name"].replace(" (background)", ""), s["background_feature"]["text"])])
        sp = s["spellcasting"]
        if sp:
            head = f"Incantesimi ({sp['ability_name']}, CD {sp['save_dc']}, attacco {fmt_mod(sp['attack_bonus'])}"
            if sp["slots"]:
                head += "; slot: " + ", ".join(f"{n} di {lvl}°" for lvl, n in sp["slots"].items())
            head += ")"
            items = [(f"{c['name']} (trucchetto, {c['source']})", c.get("text", "")) for c in sp["cantrips"]]
            for lvl in sorted(sp["spells_by_level"]):
                for spell in sp["spells_by_level"][lvl]:
                    tags = [f"{lvl}° livello"]
                    if spell.get("conc"):
                        tags.append("concentrazione")
                    if spell.get("ritual"):
                        tags.append("rituale")
                    if spell.get("range"):
                        tags.append(f"gittata {spell['range']}" + (" m" if str(spell["range"])[0].isdigit() else ""))
                    if spell.get("always_prepared"):
                        tags.append(f"sempre preparato, {spell['source']}")
                    items.append((f"{spell['name']} ({', '.join(tags)})", spell.get("text", "")))
            section(head, items)
        if s["extra_features"]:
            section("Altro", [("Note", s["extra_features"])])
        ws = s["wild_shape"]
        if ws:
            from reportlab.platypus import FrameBreak, NextPageTemplate, PageBreak, Table, TableStyle
            from reportlab.lib import colors
            one = PageTemplate(id="one", frames=[Frame(margin, 40, W - 2 * margin, H - 110, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=header)
            doc.addPageTemplates([one])
            story += [NextPageTemplate("one"), PageBreak()]
            story.append(Paragraph(esc(f"Forma Selvatica: forme disponibili al livello {s['level']} (GS massimo {ws['max_cr_str']}, volo {'sì' if ws['fly'] else 'no'}, nuoto {'sì' if ws['swim'] else 'no'})"), h_style))
            story.append(Paragraph(esc(f"{ws['uses']} usi per riposo breve o lungo; durata {ws['duration_hours']} ora/e. In forma di bestia usi le statistiche della bestia (CA, PF, velocità, attacchi, sensi), mantieni INT, SAG, CAR, allineamento e competenze nei TS e nelle abilità (usando il bonus migliore)."), b_style))
            cell = ParagraphStyle("cell", fontName=FONTS["Serif"], fontSize=6.4, leading=7.4)
            cellb = ParagraphStyle("cellb", fontName=FONTS["Serif-Bold"], fontSize=6.4, leading=7.4)
            rows = [[Paragraph(h, cellb) for h in ["Bestia", "GS", "Taglia", "CA", "PF", "Velocità", "Attacchi", "Tratti"]]]
            for b in ws["forms"]:
                spd = ", ".join(f"{v:g} m" if k == "walk" else f"{ {'climb': 'scalata', 'burrow': 'scavo', 'fly': 'volo', 'swim': 'nuoto'}.get(k, k)} {v:g} m" for k, v in b["speed"].items())
                rows.append([Paragraph(esc(b["name"]), cellb), Paragraph(fmt_cr(b["cr"]), cell), Paragraph(esc(b["size"]), cell), Paragraph(str(b["ac"]), cell), Paragraph(str(b["hp"]), cell),
                             Paragraph(esc(spd), cell), Paragraph(esc(b["attacks"]), cell), Paragraph(esc(b.get("traits", "")), cell)])
            tw = W - 2 * margin
            table = Table(rows, colWidths=[tw * 0.14, tw * 0.05, tw * 0.08, tw * 0.05, tw * 0.05, tw * 0.13, tw * 0.28, tw * 0.22], repeatRows=1)
            table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]))
            story.append(table)
        doc.build(story)
        return buf.getvalue()

    # ------------------------------------------------------------------ output
    def render(self, sheet: dict, output: str | Path, appendix: bool = True) -> Path:
        reader = PdfReader(str(self.template_pdf))
        pages = [0, 1]
        if sheet.get("spellcasting"):
            pages.append(2)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=self.page_size)
        c.setTitle(f"Scheda personaggio - {sheet['name']}")
        for p in pages:
            self.draw_page(c, sheet, p)
            c.showPage()
        c.save()
        buf.seek(0)
        overlay = PdfReader(buf)
        writer = PdfWriter()
        for i, p in enumerate(pages):
            page = reader.pages[p]
            if "/Annots" in page:
                del page["/Annots"]
            page.merge_page(overlay.pages[i])
            writer.add_page(page)
        if appendix:
            for page in PdfReader(io.BytesIO(self.appendix_pdf(sheet))).pages:
                writer.add_page(page)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "wb") as fh:
            writer.write(fh)
        return output


def esc(text) -> str:
    return escape(str(text or ""))
