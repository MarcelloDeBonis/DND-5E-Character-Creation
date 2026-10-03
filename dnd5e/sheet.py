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

from .engine import ABBR_IT, ABILITIES, fmt_cr, fmt_mod, spell_label_tags

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

WIN = "C:/Windows/Fonts/"
LIB = "/usr/share/fonts/truetype/liberation/"
# Liberation (Linux) oppure gli equivalenti metrici di Windows; in mancanza, i font standard PDF
FONT_CANDIDATES = {
    "Serif": ([LIB + "LiberationSerif-Regular.ttf", WIN + "times.ttf"], "Times-Roman"),
    "Serif-Bold": ([LIB + "LiberationSerif-Bold.ttf", WIN + "timesbd.ttf"], "Times-Bold"),
    "Serif-Italic": ([LIB + "LiberationSerif-Italic.ttf", WIN + "timesi.ttf"], "Times-Italic"),
    "Serif-BoldItalic": ([LIB + "LiberationSerif-BoldItalic.ttf", WIN + "timesbi.ttf"], "Times-BoldItalic"),
    "Sans": ([LIB + "LiberationSans-Regular.ttf", WIN + "arial.ttf"], "Helvetica"),
    "Sans-Bold": ([LIB + "LiberationSans-Bold.ttf", WIN + "arialbd.ttf"], "Helvetica-Bold"),
    "Sans-Italic": ([LIB + "LiberationSans-Italic.ttf", WIN + "ariali.ttf"], "Helvetica-Oblique"),
    "Sans-BoldItalic": ([LIB + "LiberationSans-BoldItalic.ttf", WIN + "arialbi.ttf"], "Helvetica-BoldOblique"),
}
FONTS: dict[str, str] = {}
# carattere minimo del riquadro PRIVILEGI della scheda completa: quello che non ci sta va a pagina 2
FEATURES_MIN_SIZE = 6.5


def _register_fonts() -> None:
    if FONTS:
        return
    for alias, (paths, fallback) in FONT_CANDIDATES.items():
        path = next((p for p in paths if Path(p).exists()), None)
        if path:
            pdfmetrics.registerFont(TTFont(alias, path))
            FONTS[alias] = alias
        else:
            FONTS[alias] = fallback
    for fam in ("Serif", "Sans"):
        pdfmetrics.registerFontFamily(
            FONTS[fam], normal=FONTS[fam], bold=FONTS[fam + "-Bold"],
            italic=FONTS[fam + "-Italic"], boldItalic=FONTS[fam + "-BoldItalic"],
        )


# Campi numerici o brevi da centrare
CENTERED = {
    "inspiration", "prof_bonus", "ac", "initiative", "speed", "passive_perception",
    "cp", "sp", "ep", "gp", "pp", "hp_max", "hd_total", "hd",
    "spellcasting_ability", "spell_save_dc", "spell_attack_bonus",
}
BIG = {"ac", "initiative", "speed", "prof_bonus", "inspiration", "passive_perception"}


def _range_str(rng) -> str:
    rng = str(rng or "")
    return rng + (" m" if rng[:1].isdigit() else "")


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
        self._overflow: list = []

    # ------------------------------------------------------------------ primitives
    def _rect(self, name: str):
        f = self.fields[name]
        return f["page"], f["rect"]

    def text(self, c, name, value, size=10, font="Sans", min_size=5, align=None, dy=0):
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
        if pdfmetrics.stringWidth(value, fname, size) > w:  # non entra nemmeno al minimo: si taglia con i puntini
            while len(value) > 1 and pdfmetrics.stringWidth(value + "…", fname, size) > w:
                value = value[:-1]
            value = value.rstrip() + "…"
        c.setFont(fname, size)
        baseline = y1 + (h - size * 0.7) / 2 + dy
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

    def box(self, c, name, paragraphs, size=8.5, min_size=5, font="Serif", leading=1.2, align="left", overflow=False):
        """Testo multi-paragrafo che si restringe per entrare nel riquadro.

        `paragraphs` è una lista di stringhe (markup minimo <b>/<i> consentito) oppure una stringa
        con righe separate da newline. Con `overflow=True` il carattere non scende sotto `min_size`:
        i paragrafi che non ci stanno vengono restituiti, per scriverli in un altro riquadro.
        """
        if not paragraphs:
            return []
        page, (x1, y1, x2, y2) = self._rect(name)
        if page != self._page:
            return []
        if isinstance(paragraphs, str):
            paragraphs = [p for p in paragraphs.split("\n")]
        w, h = x2 - x1 - 6, y2 - y1 - 6

        def make(sz):
            style = ParagraphStyle(
                name, fontName=FONTS[font], fontSize=sz, leading=sz * leading,
                spaceAfter=sz * 0.35, alignment={"left": 0, "center": 1, "justify": 4}[align],
            )
            return [Paragraph(p if p.strip() else "&nbsp;", style) for p in paragraphs], style

        frame = Frame(x1 + 3, y1 + 3, w, h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
        if not overflow:
            flow, _ = make(size)
            frame.addFromList([KeepInFrame(w, h, flow, mode="shrink")], c)
            return []
        sz = size
        while True:
            flow, style = make(sz)
            total = sum(f.wrap(w, h)[1] + style.spaceAfter for f in flow) - style.spaceAfter
            if total <= h or sz <= min_size:
                break
            sz = max(min_size, sz - 0.25)
        n = len(flow)
        frame.addFromList(flow, c)  # toglie dalla lista i paragrafi disegnati
        return list(paragraphs[n - len(flow):]) if flow else []

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
        if s["ac"].get("stealth_disadvantage") and "skill_stealth" in self.fields:
            self._stealth_note(c)
        self.text(c, "passive_perception", str(s["passive_perception"]), size=12, font="Sans-Bold")
        self.text(c, "ac", str(s["ac"]["value"]), size=15, font="Sans-Bold", dy=4)
        self.text(c, "initiative", fmt_mod(s["initiative"]) + (" V" if s.get("initiative_advantage") else ""), size=16, font="Sans-Bold")
        self.text(c, "speed", s["speed_m"], size=12, font="Sans-Bold")
        self.text(c, "hp_max", str(s["hp"]["max"]), size=10, font="Sans-Bold")
        self.text(c, "hd_total", s["hp"]["hit_dice"], size=8)
        self.text(c, "hd", f"1d{s['class']['hit_die']}", size=11)
        for i, w in enumerate(s["weapons"][:3], start=1):
            self.text(c, f"weapon_{i}_name", w["name"], size=8.5)
            self.text(c, f"weapon_{i}_atk", w["attack_str"], size=9, align="center")
            self.text(c, f"weapon_{i}_dmg", w["damage"], size=7.5)
        if s.get("simple"):
            self.box(c, "attacks_spellcasting", simple_attacks(s), size=8)
        else:
            self._attacks_full(c, s)
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
        # privilegi (versione breve, o semplice per i più giovani)
        extras = s["fighting_styles"] + ([s["background_feature"]] if s["background_feature"] else [])
        if s.get("simple"):
            feats = []
            for f in s["features"] + extras:
                if f.get("kid_hide"):
                    continue
                feats.append(f"<b>{esc(f['name'].replace(' (background)', ''))}.</b> {esc(f.get('kid') or f['short'])}")
            self.box(c, "features_traits", feats, size=8.5)
            self._overflow = []
        else:
            feats = [f"<b>{esc(name)}.</b> {esc(short)}" for name, short in page_features(s["features"])]
            feats += [f"<b>{esc(f['name'])}.</b> {esc(f['short'])}" for f in extras]
            self._overflow = self.box(c, "features_traits", feats, size=7.5, min_size=FEATURES_MIN_SIZE, overflow=True)
        # competenze e linguaggi
        pr = s["proficiencies"]
        prof_lines = [
            f"<b>Armature:</b> {esc(', '.join(pr['armor']) or 'nessuna')}",
            f"<b>Armi:</b> {esc(', '.join(pr['weapons']) or 'nessuna')}",
            f"<b>Strumenti:</b> {esc(', '.join(pr['tools']) or 'nessuno')}",
            f"<b>Linguaggi:</b> {esc(', '.join(s['languages']))}",
        ]
        self.box(c, "proficiencies_languages", prof_lines, size=8)

    def _stealth_note(self, c):
        """'sv.' accanto a Furtività quando l'armatura dà svantaggio."""
        page, (x1, y1, x2, y2) = self._rect("skill_stealth")
        if page != self._page:
            return
        c.setFont(FONTS["Sans-Bold"], 5.5)
        c.drawString(x2 + 50, y1 + 2.2, "sv.")

    def _attacks_full(self, c, s):
        # riquadro attacchi: armi oltre la terza, dettagli, incantesimi, manovre, soffio, ki, compagno
        atk = []
        for w in s["weapons"][3:]:
            atk.append(f"<b>{esc(w['name'])}</b> {esc(w['attack_str'])}, {esc(w['damage'])}")
        for w in s["weapons"]:
            det = ", ".join(w["properties"] + w["notes"])
            if det:
                atk.append(f"<i>{esc(w['name'])}</i>: {esc(det)}")
        mi = s.get("maneuver_info")
        if s["maneuvers"]:
            head = f"<b>Manovre</b> (CD {mi['dc']}, {mi['dice']}{esc(mi['die'])}): " if mi else "<b>Manovre</b> (dadi di superiorità): "
            atk.append(head + esc(", ".join(m["name"] for m in s["maneuvers"])))
        b = s.get("breath")
        if b:
            atk.append(f"<b>Arma a soffio</b> ({esc(b['type'])}): {esc(b['area'])}, TS {esc(b['save_name'])} CD {b['dc']}, "
                       f"{esc(b['dice'])} (metà se supera), 1 volta per riposo breve o lungo")
        ki = s.get("ki")
        if ki:
            atk.append(f"<b>Ki</b>: {ki['points']} punti, CD {ki['dc']}" + (f"; colpo senz'armi {esc(ki['attack_str'])}, {esc(ki['damage'])}" if ki.get("attack_str") else ""))
        sp = s["spellcasting"]
        if sp:
            for at in sp["spell_attacks"]:
                how = at["attack_str"] if at.get("attack_str") else at.get("save_str", "")
                atk.append(f"<b>{esc(at['name'])}</b> {esc(how)}, {esc(at['damage'])}" + (f" (gittata {esc(_range_str(at['range']))})" if at.get("range") else ""))
            atk.append(f"<b>Incantesimi:</b> {esc(sp['ability_name'])}, CD {sp['save_dc']}, attacco {esc(fmt_mod(sp['attack_bonus']))}"
                       + (", slot " + ", ".join(f"{n}×{lvl}°" for lvl, n in sp["slots"].items()) if sp["slots"] else "") + ". Vedi pagina 3.")
        comp = s.get("companion")
        if comp:
            atk.append(f"<b>Compagno: {esc(comp['name'])}</b> CA {comp['ac']}, PF {comp['hp']}; {esc(comp['attacks_text'])}")
        ws = s["wild_shape"]
        if ws:
            top = [b["name"] for b in ws["forms"] if b["cr"] == ws.get("top_cr", ws["max_cr"]) and not b.get("elemental")][:6]
            atk.append(f"<b>Forma Selvatica</b> (GS max {esc(ws['max_cr_str'])}, {ws['uses']} usi, {ws['duration_hours']} h): "
                       + esc(", ".join(top)) + "... (tabella completa in appendice)")
        if s["attacks_notes"]:
            atk += [esc(x) for x in s["attacks_notes"].split("\n")]
        self.box(c, "attacks_spellcasting", atk, size=7.5)

    def _draw_page_1(self, c, s):
        ap = s["appearance"]
        self.text(c, "character_name_2", s["name"], size=14, font="Serif-Bold")
        for k in ("age", "height", "weight", "eyes", "skin", "hair"):
            self.text(c, k, ap.get(k, ""), size=9)
        self.image(c, "portrait", s["portrait"])
        self.box(c, "allies", esc(s["allies"]), size=8.5)
        self.box(c, "backstory", esc(s["backstory"]), size=8.5, align="justify")
        self.box(c, "treasure", esc(s["treasure"]), size=8.5)
        if s.get("simple"):
            self.box(c, "additional_features", how_to_play(s), size=8.5)
            return
        feats = []
        moved = {p.split("</b>")[0] for p in self._overflow}
        if self._overflow:
            feats.append("<i>Privilegi e tratti (segue da pagina 1):</i>")
            feats += self._overflow
        for f in s["fighting_styles"] + ([s["background_feature"]] if s["background_feature"] else []):
            if f"<b>{esc(f['name'])}." in moved:  # già scritto qui sopra, arrivato da pagina 1
                continue
            feats.append(f"<b>{esc(f['name'])}.</b> {esc(f['text'])}")
        mi = s.get("maneuver_info")
        for m in s["maneuvers"]:
            feats.append(f"<b>Manovra: {esc(m['name'])}.</b> {esc(m['text'])}")
        if mi and s["maneuvers"]:
            feats.append(f"<i>Manovre: CD {mi['dc']} (8 + competenza + FOR o DES), {mi['dice']} dadi di superiorità {esc(mi['die'])}.</i>")
        for cn in s["cantrips"]:
            feats.append(f"<b>Trucchetto: {esc(cn['name'])}</b> ({esc(cn['source'])}). {esc(cn.get('text', ''))}")
        for sp in s.get("extra_spells") or []:
            feats.append(f"<b>{esc(sp['name'])}</b> ({esc(sp['source'])}, {esc(sp.get('tag', ''))}). {esc(sp.get('text', ''))}")
        comp = s.get("companion")
        if comp:
            feats.append(f"<b>Compagno animale: {esc(comp['name'])}.</b> CA {comp['ac']}, PF {comp['hp']}, velocità {esc(_speed_str(comp['speed']))}; "
                         f"{esc(comp['attacks_text'])}. {esc(comp.get('traits', ''))} (TS e abilità +{comp['saves_skills_bonus']}.)")
        ws = s["wild_shape"]
        if ws:
            feats.append(f"<b>Forma Selvatica.</b> GS massimo {esc(ws['max_cr_str'])}, volo {'sì' if ws['fly'] else 'no'}, nuoto {'sì' if ws['swim'] else 'no'}; "
                         f"{ws['uses']} usi per riposo breve o lungo, durata {ws['duration_hours']} ora/e. Forme: " + esc(", ".join(b["name"] for b in ws["forms"])) + ".")
        if s["extra_features"]:
            feats += [esc(x) for x in s["extra_features"].split("\n")]
        feats.append("<i>Le descrizioni complete di tratti, privilegi, incantesimi e forme animali sono nelle pagine di appendice.</i>")
        self.box(c, "additional_features", feats, size=8)

    def _draw_page_2(self, c, s):
        sp = s["spellcasting"]
        if not sp:
            return
        title = sp.get("title") or (s["class"]["name"] if sp["class_caster"] else s["race"]["name"])
        self.text(c, "spellcasting_class", title, size=12, font="Serif-Bold")
        self.text(c, "spellcasting_ability", sp["ability_name"], size=9)
        self.text(c, "spell_save_dc", str(sp["save_dc"]), size=14, font="Sans-Bold")
        self.text(c, "spell_attack_bonus", fmt_mod(sp["attack_bonus"]), size=14, font="Sans-Bold")
        cantrips = sp["cantrips"]
        n_rows = len([k for k in self.fields if k.startswith("cantrip_") and k[8:].isdigit()]) or 8
        for i, cn in enumerate(cantrips[:n_rows], start=1):
            if i == n_rows and len(cantrips) > n_rows:
                self.text(c, f"cantrip_{i}", ", ".join(x["name"] for x in cantrips[i - 1:]), size=7, min_size=4)
                s["warnings"].append(f"Pagina 3: i trucchetti non stanno nelle righe: gli ultimi {len(cantrips) - i + 1} sono sulla stessa riga")
                break
            label = cn["name"] + ("" if cn["source"] == s["class"]["name"] else f" ({cn['source']})")
            if cn.get("other_ability"):
                label += f" {ABBR_IT.get(cn['ability'], cn['ability'].upper())}: CD {cn['save_dc']}, att. {fmt_mod(cn['attack_bonus'])}"
            self.text(c, f"cantrip_{i}", label, size=8.5)
        for lvl in range(1, 10):
            n = sp["slots"].get(lvl)
            if n:
                self.text(c, f"slots_total_{lvl}", str(n), size=12, font="Sans-Bold")
            spells = sp["spells_by_level"].get(lvl, [])
            rows = len([k for k in self.fields if k.startswith(f"spell_{lvl}_") and k[len(f"spell_{lvl}_"):].isdigit()])
            for i, spell in enumerate(spells, start=1):
                field = f"spell_{lvl}_{i}"
                if field not in self.fields:
                    break
                if i == rows and len(spells) > rows:  # non ci stanno: gli ultimi sulla stessa riga, più piccoli
                    rest = spells[i - 1:]
                    self.text(c, field, ", ".join(x["name"] + spell_label_tags(x, sp) for x in rest), size=6.5, min_size=4)
                    s["warnings"].append(f"Pagina 3: gli incantesimi di {lvl}° livello non stanno nelle righe: gli ultimi {len(rest)} sono sulla stessa riga")
                    break
                label = spell["name"] + spell_label_tags(spell, sp)
                if spell.get("other_ability"):
                    label += f" {ABBR_IT.get(spell['ability'], spell['ability'])} CD {spell['save_dc']}"
                self.text(c, field, label, size=8)
                if (f"{field}_prep" in self.fields and (sp["prepares"] or spell.get("always_prepared")) and spell.get("prepared", True)
                        and not spell.get("extra")):
                    self.check(c, f"{field}_prep", True)

    # ------------------------------------------------------------------ appendix
    def appendix_pdf(self, s: dict) -> bytes:
        """Pagina/e extra con le descrizioni complete di tratti, privilegi, manovre e trucchetti."""
        from reportlab.lib import colors
        from reportlab.platypus import BaseDocTemplate, NextPageTemplate, PageBreak, PageTemplate, Table, TableStyle
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
        one = PageTemplate(id="one", frames=[Frame(margin, 40, W - 2 * margin, H - 110, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=header)
        doc.addPageTemplates([PageTemplate(id="two", frames=frames, onPage=header), one])
        h_style = ParagraphStyle("h", fontName=FONTS["Serif-Bold"], fontSize=11, leading=13, spaceBefore=8, spaceAfter=3)
        b_style = ParagraphStyle("b", fontName=FONTS["Serif"], fontSize=8.5, leading=10.5, spaceAfter=4, alignment=4)
        cell = ParagraphStyle("cell", fontName=FONTS["Serif"], fontSize=6.4, leading=7.4)
        cellb = ParagraphStyle("cellb", fontName=FONTS["Serif-Bold"], fontSize=6.4, leading=7.4)
        story = []

        def section(heading, items):
            if not items:
                return
            story.append(Paragraph(esc(heading), h_style))
            for name, text in items:
                story.append(Paragraph(f"<b>{esc(name)}.</b> {esc(text)}", b_style))

        def label(f):
            if f.get("level"):
                return f"{f['name']} ({f['level']}° livello, {f['source']})"
            return f"{f['name']} ({f['source']})"

        feats_all = s["features"]
        race_items = [(f["name"], f.get("text") or f.get("short", "")) for f in feats_all if f.get("kind") == "race"]
        class_items = [(label(f), f.get("text") or f.get("short", "")) for f in feats_all if f.get("kind") in ("class", "asi", None)]
        section(f"Tratti razziali: {s['race']['name']}", race_items)
        section(f"Privilegi di classe: {s['class_level']}" + (f", {s['subclass_name']}" if s["subclass_name"] else ""), class_items)
        groups: dict[str, list] = {}
        for f in feats_all:
            if f.get("kind") == "option":
                groups.setdefault(f["source"], []).append((f["name"], f.get("text") or f.get("short", "")))
        for heading, items in groups.items():
            section(heading, items)
        section("Talenti", [(f["name"], f.get("text") or f.get("short", "")) for f in feats_all if f.get("kind") == "feat"])
        section("Stile di combattimento", [(f["name"].split(": ", 1)[-1], f["text"]) for f in s["fighting_styles"]])
        mi = s.get("maneuver_info")
        section("Manovre" + (f" (CD {mi['dc']}, {mi['dice']} dadi di superiorità {mi['die']})" if mi else ""),
                [(m["name"], m["text"]) for m in s["maneuvers"]])
        if s["background_feature"]:
            section(f"Privilegio del background: {s['background']['name']}", [(s["background_feature"]["name"].replace(" (background)", ""), s["background_feature"]["text"])])
        sp = s["spellcasting"]
        if sp:
            head = f"Incantesimi ({sp['ability_name']}, CD {sp['save_dc']}, attacco {fmt_mod(sp['attack_bonus'])}"
            if sp["slots"]:
                head += "; slot: " + ", ".join(f"{n} di {lvl}°" for lvl, n in sp["slots"].items())
            head += ")"
            items = [(f"{c['name']} (trucchetto, {c['source']}" + (f", {ABBR_IT.get(c['ability'], c['ability'])}: CD {c['save_dc']}, attacco {fmt_mod(c['attack_bonus'])}" if c.get("other_ability") else "") + ")", c.get("text", "")) for c in sp["cantrips"]]
            for lvl in sorted(sp["spells_by_level"]):
                for spell in sp["spells_by_level"][lvl]:
                    tags = [f"{lvl}° livello"]
                    if spell.get("conc"):
                        tags.append("concentrazione")
                    if spell.get("ritual") and (sp.get("ritual") or spell.get("tag") == "solo rituale"):
                        tags.append("rituale")
                    if spell.get("range"):
                        tags.append(f"gittata {_range_str(spell['range'])}")
                    if spell.get("always_prepared"):
                        tags.append(f"sempre preparato, {spell['source']}")
                    elif spell.get("extra"):
                        tags.append(f"{spell.get('tag', '')}, {spell['source']}")
                    if spell.get("mastery"):
                        tags.append("senza slot (Maestria negli Incantesimi)")
                    if spell.get("other_ability"):
                        tags.append(f"{ABBR_IT.get(spell['ability'], spell['ability'])}: CD {spell['save_dc']}, attacco {fmt_mod(spell['attack_bonus'])}")
                    items.append((f"{spell['name']} ({', '.join(tags)})", spell.get("text", "")))
            section(head, items)
        if s.get("extra_spells"):
            section("Incantesimi dai privilegi", [(f"{x['name']} ({x.get('level')}° livello, {x.get('tag', '')}, {x['source']})", x.get("text", ""))
                                                  for x in s["extra_spells"]])
        comp = s.get("companion")
        if comp:
            section(f"Compagno animale: {comp['name']}", [
                ("Statistiche", f"Taglia {comp['size']}, GS {fmt_cr(comp['cr'])}; CA {comp['ac']}, PF {comp['hp']}, velocità {_speed_str(comp['speed'])}. "
                                f"Già calcolati con il tuo bonus di competenza (+{comp['prof']}) a CA, attacchi, danni, TS e abilità."),
                ("Attacchi", comp["attacks_text"]),
            ] + ([("Tratti", comp["traits"])] if comp.get("traits") else []))
        if s["extra_features"]:
            section("Altro", [("Note", s["extra_features"])])
        surge = s.get("surge_table")
        if surge:
            story += [NextPageTemplate("one"), PageBreak()]
            story.append(Paragraph("Tabella degli Impulsi di Magia Selvaggia (d100)", h_style))
            rows = [[Paragraph("d100", cellb), Paragraph("Effetto", cellb)]]
            for r in surge:
                rows.append([Paragraph(esc(r.get("roll", f"{r.get('min')}-{r.get('max')}")), cell), Paragraph(esc(r.get("text", "")), cell)])
            tw = W - 2 * margin
            table = Table(rows, colWidths=[tw * 0.08, tw * 0.92], repeatRows=1)
            table.setStyle(_grid_style(colors))
            story.append(table)
        ws = s["wild_shape"]
        if ws:
            if not surge:
                story += [NextPageTemplate("one"), PageBreak()]
            story.append(Paragraph(esc(f"Forma Selvatica: forme disponibili al livello {s['level']} (GS massimo {ws['max_cr_str']}, volo {'sì' if ws['fly'] else 'no'}, nuoto {'sì' if ws['swim'] else 'no'})"), h_style))
            story.append(Paragraph(esc(f"{ws['uses']} usi per riposo breve o lungo; durata {ws['duration_hours']} ora/e. In forma di bestia usi le statistiche della bestia (CA, PF, velocità, attacchi, sensi), mantieni INT, SAG, CAR, allineamento e competenze nei TS e nelle abilità (usando il bonus migliore)."), b_style))
            rows = [[Paragraph(h, cellb) for h in ["Bestia", "GS", "Taglia", "CA", "PF", "Velocità", "Attacchi", "Tratti"]]]
            for b in ws["forms"]:
                rows.append([Paragraph(esc(b["name"] + (" (elementale: 2 usi)" if b.get("elemental") else "")), cellb), Paragraph(fmt_cr(b["cr"]), cell), Paragraph(esc(b["size"]), cell), Paragraph(str(b["ac"]), cell), Paragraph(str(b["hp"]), cell),
                             Paragraph(esc(_speed_str(b["speed"])), cell), Paragraph(esc(b["attacks"]), cell), Paragraph(esc(b.get("traits", "")), cell)])
            tw = W - 2 * margin
            table = Table(rows, colWidths=[tw * 0.14, tw * 0.05, tw * 0.08, tw * 0.05, tw * 0.05, tw * 0.13, tw * 0.28, tw * 0.22], repeatRows=1)
            table.setStyle(_grid_style(colors))
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
        if appendix and not sheet.get("simple"):
            for page in PdfReader(io.BytesIO(self.appendix_pdf(sheet))).pages:
                writer.add_page(page)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "wb") as fh:
            writer.write(fh)
        return output


def _grid_style(colors):
    from reportlab.platypus import TableStyle
    return TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ])


def _speed_str(speed: dict) -> str:
    names = {"climb": "scalata", "burrow": "scavo", "fly": "volo", "swim": "nuoto"}
    return ", ".join(f"{v:g} m" if k == "walk" else f"{names.get(k, k)} {v:g} m" for k, v in (speed or {}).items() if v)


def esc(text) -> str:
    return escape(str(text or ""))


def page_features(features: list) -> list:
    """Privilegi per il riquadro di pagina 1 della scheda completa: senza le voci di sola contabilità
    (`sheet_hide`, che di base vale come `kid_hide`) e con i nomi ripetuti uniti: 'Nome (4°, 8°, 12°)'."""
    groups: dict[str, dict] = {}
    for f in features:
        if f.get("sheet_hide"):
            continue
        g = groups.setdefault(f["name"], {"short": f.get("short", ""), "levels": []})
        if f.get("level"):
            g["levels"].append(f["level"])
    out = []
    for name, g in groups.items():
        if len(g["levels"]) > 1:
            name = f"{name} ({', '.join(f'{lv}°' for lv in g['levels'])})"
        out.append((name, g["short"]))
    return out


def simple_attacks(s: dict) -> list:
    """Riquadro attacchi in parole semplici: ogni riga dice cosa tirare."""
    out = []
    for w in s["weapons"][3:]:
        out.append(f"<b>{esc(w['name'])}</b>: tira d20{esc(w['attack_str'])}, danni {esc(w['damage'])}"
                   + (f" (a due mani {esc(w['versatile_damage'])})" if w.get("versatile_damage") else ""))
    for w in s["weapons"][:3]:
        if w.get("versatile_damage"):
            out.append(f"<b>{esc(w['name'])}</b> impugnata a due mani: danni {esc(w['versatile_damage'])}")
    sp = s["spellcasting"]
    if sp:
        for at in sp["spell_attacks"]:
            rng = str(at.get("range", "") or "")
            if at.get("attack_str"):
                how = f"tira d20{esc(at['attack_str'])}"
            else:
                how = f"il nemico tira {esc(at.get('save_ability', ''))} contro <b>{at.get('save_dc')}</b>"
            out.append(f"<b>{esc(at['name'])}</b> (magia): {how}, danni {esc(at['damage'])}"
                       + (f", fino a {esc(rng)} m" if rng[:1].isdigit() else ""))
    ki = s.get("ki")
    if ki:
        out.append(f"<b>Ki</b>: {ki['points']} punti, CD <b>{ki['dc']}</b>"
                   + (f", pugno d20{esc(ki['attack_str'])}, danni {esc(ki['damage'].replace(' contundente', ''))}" if ki.get("attack_str") else ""))
    mi = s.get("maneuver_info")
    if s["maneuvers"] and mi:
        out.append(f"<b>Manovre</b> ({mi['dice']} dadi {esc(mi['die'])}, il nemico resiste contro <b>{mi['dc']}</b>): "
                   + esc(", ".join(m["name"] for m in s["maneuvers"])) + ". Spiegate nella guida.")
    b = s.get("breath")
    if b:
        out.append(f"<b>Soffio di {esc(b['type'])}</b> (1 volta, poi riposo): {esc(b['area'])}. I nemici tirano {esc(b['save_name'])} "
                   f"contro <b>{b['dc']}</b>: se sbagliano {esc(b['dice'])} danni, se riescono la metà.")
    if s.get("mage_armor_ac"):
        out.append(f"<b>Armatura Magica</b>: lanciala al mattino e la tua CA diventa <b>{s['mage_armor_ac']}</b> per 8 ore.")
    comp = s.get("companion")
    if comp:
        out.append(f"<b>{esc(comp['name'])}</b> (il tuo compagno): CA {comp['ac']}, PF {comp['hp']}. "
                   + "; ".join(f"{esc(a.get('name', ''))}: tira d20{esc(a['hit'])}, danni {esc(a['damage'])}" for a in comp["attacks"]) + ".")
    if sp:
        out.append(f"<b>Magie</b>: i nemici resistono contro <b>{sp['save_dc']}</b>; i tuoi attacchi magici sono d20{esc(fmt_mod(sp['attack_bonus']))}. "
                   "Elenco a pagina 3, spiegazioni nella guida.")
    if s.get("extra_spells"):
        out.append("<b>Magie rituali</b>: " + esc(", ".join(x["name"] for x in s["extra_spells"]))
                   + ": le lanci solo come rituale (10 minuti in più, nessuno slot).")
    ws = s["wild_shape"]
    if ws:
        times = "quante volte vuoi" if ws.get("unlimited") else f"{ws['uses']} volte, poi devi riposare"
        out.append(f"<b>Forma Selvatica</b>: diventi un animale {times}. Gli animali sono nella guida.")
    if s["attacks_notes"]:
        out += [esc(x) for x in s["attacks_notes"].split("\n")]
    return out


def wild_shape_line(s: dict) -> str:
    """Promemoria della Forma Selvatica (scheda semplice e guida)."""
    ws = s["wild_shape"]
    o = "a" if s.get("female") else "o"
    hours = ws["duration_hours"]
    action = "Con un'azione bonus" if ws.get("combat") else "Con un'azione"
    times = "Quante volte vuoi" if ws.get("unlimited") else f"{ws['uses']} volte, poi riposo"
    line = (f"<b>Forma Selvatica.</b> {action} diventi un animale che hai già visto (sono nella guida). {times}. "
            f"Dura fino a {hours} {'ora' if hours == 1 else 'ore'}. Usi PF, CA e attacchi dell'animale; quando i suoi PF finiscono torni te stess{o} "
            "con i tuoi PF.")
    heal = "con un'azione bonus puoi spendere uno slot per curarti 1d8 PF per livello dello slot."
    if ws.get("level", s.get("level", 1)) >= 18:  # Incantesimi Bestiali: da animale si lanciano le magie
        line += " Da animale puoi anche lanciare le tue magie" + (f"; e {heal}" if ws.get("combat") else ".")
    elif ws.get("combat"):
        line += f" Da animale non lanci magie, ma {heal}"
    else:
        line += " Da animale non lanci magie."
    return line


def how_to_play(s: dict) -> list:
    """Promemoria delle regole base, così la scheda basta per giocare."""
    o = "a" if s.get("female") else "o"
    sp = s["spellcasting"]
    if sp and sp["slots"]:
        rest = "recuperi tutte le magie."
    elif s["class"]["key"] == "barbarian":
        rest = "recuperi gli usi di Ira e degli altri poteri."
    else:
        rest = "recuperi gli usi dei tuoi poteri."
    lines = [
        "<b>COME SI GIOCA</b>",
        f"<b>Il tuo turno.</b> 1) Muoviti fino a {s['speed_m']}. 2) Fai UNA azione: attaccare, lanciare una magia, aiutare un amico, "
        "nasconderti, scappare... 3) Se hai qualcosa che si fa con un'<i>azione bonus</i>, puoi farlo in più.",
        "<b>Colpire.</b> Tira il d20 e aggiungi il numero dell'attacco. Se arrivi alla CA del nemico (o più), lo colpisci e tiri i dadi dei danni.",
        "<b>Prove.</b> Quando il Master chiede una prova (es. Furtività), tira il d20 e aggiungi il numero accanto all'abilità.",
        "<b>Tiro salvezza.</b> Per resistere a una trappola o a una magia tira il d20 e aggiungi il numero del tiro salvezza giusto.",
        "<b>Vantaggio / svantaggio.</b> Tiri 2 d20: con il vantaggio tieni il più alto, con lo svantaggio il più basso.",
        f"<b>Punti Ferita.</b> Ne hai {s['hp']['max']}. Quando ti colpiscono scendono. A 0 cadi a terra svenut{o}: a ogni tuo turno tira un d20, "
        f"con 10 o più è un successo. 3 successi: sei salv{o}. 3 fallimenti: muori. Un amico può curarti prima.",
        f"<b>Riposo.</b> Breve (1 ora): puoi tirare i Dadi Vita per recuperare PF. Lungo (8 ore di sonno): torni al massimo dei PF e {rest}",
    ]
    if sp and sp["slots"]:
        slots = ", ".join(f"{n} di {lvl}° livello" for lvl, n in sp["slots"].items())
        free = "I trucchetti sono gratis: li usi quando vuoi. " if sp["cantrips"] else ""
        lines.append(f"<b>Magie.</b> {free}Le altre magie consumano uno <i>slot</i>: ne hai {slots}. "
                     "Annerisci un cerchietto a pagina 3 quando lo usi; tornano tutti dopo un riposo "
                     + ("breve o lungo." if sp.get("pact") else "lungo."))
        lines.append("<b>Concentrazione (C).</b> Puoi tenere attiva una sola magia con la C alla volta. Se ti fanno male tira d20 + il tuo "
                     "tiro salvezza su Costituzione: con 10 o più la magia continua.")
        if sp.get("spellbook"):
            lines.append("<b>Libro degli incantesimi.</b> Dentro ci sono tutte le tue magie. Ogni mattina scegli quali tenere pronte "
                         "(quelle con il pallino a pagina 3). Le magie con (R) puoi lanciarle come rituale: 10 minuti in più e nessuno slot.")
        elif sp["prepares"]:
            lines.append(f"<b>Magie preparate.</b> Dopo ogni riposo lungo puoi cambiare le {sp['prepared_max'] or ''} magie preparate "
                         "scegliendole dalla guida.")
        else:
            lines.append("<b>Magie conosciute.</b> Le magie di pagina 3 le sai sempre. Quando sali di livello ne impari di nuove (sono nella guida) "
                         "e puoi cambiarne una.")
    if s["wild_shape"]:
        lines.append(wild_shape_line(s))
    return lines
