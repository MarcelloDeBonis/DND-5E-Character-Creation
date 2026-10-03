"""Guida per giocatori giovani: un PDF separato dalla scheda, in parole semplici.

Contiene il promemoria delle regole, una carta per ogni magia (quelle sulla scheda e tutte le altre
che il personaggio può scegliere) e, per i druidi, una carta per ogni animale della Forma Selvatica.
I testi semplici stanno nei file di regole (campi `kid`, `tip`, `kid_attacks`, `kid_traits`).
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

from .engine import fmt_cr, fmt_mod, kid_fmt
from .sheet import FONTS, _register_fonts, esc, how_to_play

THEMES = {
    "druid": ("#2f6b3a", "#e7f2e4", "#f6faf4"),
    "wizard": ("#8a1c2b", "#f6e3e3", "#fcf6f4"),
}
DEFAULT_THEME = ("#3b4a7a", "#e5e9f5", "#f7f8fc")
ROLE_NAMES = {
    "combattere": "Per combattere", "esplorare": "Per esplorare e spiare", "viaggiare": "Per viaggiare",
    "nuotare": "Per nuotare", "volare": "Per volare",
}
SPEED_NAMES = {"climb": "scalata", "burrow": "scavo", "fly": "volo", "swim": "nuoto"}


class Styles:
    def __init__(self, dark):
        _register_fonts()
        sans, bold, ital = FONTS["Sans"], FONTS["Sans-Bold"], FONTS["Sans-Italic"]
        self.title = ParagraphStyle("t", fontName=FONTS["Serif-Bold"], fontSize=24, leading=28, textColor=colors.HexColor(dark))
        self.sub = ParagraphStyle("s", fontName=sans, fontSize=11, leading=14, spaceAfter=8)
        self.h = ParagraphStyle("h", fontName=bold, fontSize=13, leading=16, textColor=colors.white)
        self.body = ParagraphStyle("b", fontName=sans, fontSize=9.5, leading=12.5, spaceAfter=4)
        self.card_h = ParagraphStyle("ch", fontName=bold, fontSize=11, leading=13, textColor=colors.HexColor(dark))
        self.chips = ParagraphStyle("cc", fontName=sans, fontSize=7.8, leading=10, textColor=colors.HexColor("#444444"))
        self.card = ParagraphStyle("cb", fontName=sans, fontSize=9.3, leading=12)
        self.tip = ParagraphStyle("ct", fontName=ital, fontSize=8.5, leading=11, textColor=colors.HexColor("#333333"))


def _bar(text, st, dark):
    t = Table([[Paragraph(esc(text), st.h)]], colWidths=["100%"])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(dark)),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
    return [Spacer(1, 6), t, Spacer(1, 5)]


def _card(rows, st, light, border, highlight=False):
    t = Table([[r] for r in rows], colWidths=["100%"])
    style = [("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(light if highlight else "#ffffff")),
             ("BOX", (0, 0), (-1, -1), 1.2 if highlight else 0.6, colors.HexColor(border)),
             ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
             ("TOPPADDING", (0, 0), (-1, 0), 5), ("BOTTOMPADDING", (0, -1), (-1, -1), 6)]
    t.setStyle(TableStyle(style))
    return KeepTogether([t, Spacer(1, 6)])


def _range(r):
    r = str(r or "")
    return f"{r} m" if r[:1].isdigit() else r


def spell_card(sp, values, st, theme, mark=""):
    dark, light, _ = theme
    lvl = "Trucchetto" if sp.get("level") == 0 else f"{sp.get('level')}° livello"
    head = f"{esc(sp['name'])}  <font size=8 color='#555555'>{lvl}</font>"
    if mark:
        head += f"  <font size=8 color='{dark}'><b>{esc(mark)}</b></font>"
    chips = [f"<b>Tempo:</b> {esc(sp.get('cast', '—'))}", f"<b>Distanza:</b> {esc(_range(sp.get('range')))}",
             f"<b>Durata:</b> {esc(sp.get('duration', '—'))}"]
    if sp.get("conc"):
        chips.append("<b>C</b> = concentrazione")
    if sp.get("ritual"):
        chips.append("<b>R</b> = rituale")
    rows = [Paragraph(head, st.card_h), Paragraph(" · ".join(chips), st.chips),
            Paragraph(esc(kid_fmt(sp.get("kid") or sp.get("text", ""), values)), st.card)]
    if sp.get("tip"):
        rows.append(Paragraph("Quando usarla: " + esc(kid_fmt(sp["tip"], values)), st.tip))
    return _card(rows, st, light, dark, highlight=bool(mark))


def beast_card(b, st, theme):
    dark, light, _ = theme
    spd = ", ".join(f"{v:g} m" if k == "walk" else f"{SPEED_NAMES.get(k, k)} {v:g} m" for k, v in b["speed"].items() if v)
    rows = [Paragraph(f"{esc(b['name'])}  <font size=8 color='#555555'>{esc(b['size'])}, GS {fmt_cr(b['cr'])}</font>", st.card_h),
            Paragraph(f"<b>PF {b['hp']}</b> · <b>CA {b['ac']}</b> · <b>Velocità</b> {esc(spd)}", st.chips)]
    if b.get("kid"):
        rows.append(Paragraph(esc(b["kid"]), st.card))
    attacks = b.get("kid_attacks")
    if attacks:
        for a in attacks:
            line = f"<b>{esc(a.get('name', ''))}</b>: tira d20{esc(a.get('hit', ''))}; se colpisci {esc(a.get('damage', ''))} danni {esc(a.get('type', ''))}."
            if a.get("extra"):
                line += " " + esc(a["extra"])
            rows.append(Paragraph(line, st.card))
        if b.get("multi"):
            rows.append(Paragraph(esc(b["multi"]), st.tip))
    else:
        rows.append(Paragraph("<b>Attacchi:</b> " + esc(b.get("attacks", "")), st.card))
    for t in b.get("kid_traits") or ([b["traits"]] if b.get("traits") else []):
        rows.append(Paragraph("• " + esc(t), st.chips))
    return _card(rows, st, light, dark)


def _values(sp_like, caster):
    ab = sp_like.get("attack_bonus", caster["attack_bonus"])
    dc = sp_like.get("save_dc", caster["save_dc"])
    mod = sp_like.get("mod", caster["mod"]) if "attack_bonus" not in sp_like else ab - (caster["attack_bonus"] - caster["mod"])
    return {"att": fmt_mod(ab), "cd": dc, "mod": fmt_mod(mod)}


def build_guide(sheet: dict, rules: dict, output: str | Path) -> Path:
    theme = THEMES.get(sheet["class"]["key"], DEFAULT_THEME)
    dark, light, paper = theme
    st = Styles(dark)
    W, H = A4
    margin, gutter = 36, 16
    colw = (W - 2 * margin - gutter) / 2
    title = f"Guida di {sheet['name']}"

    def deco(c, doc):
        c.saveState()
        c.setFillColor(colors.HexColor(paper))
        c.rect(0, 0, W, H, stroke=0, fill=1)
        c.setFillColor(colors.HexColor(dark))
        c.rect(0, H - 14, W, 14, stroke=0, fill=1)
        c.setFont(FONTS["Sans"], 8)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawString(margin, 18, f"{title} · per {sheet['player']}" if sheet.get("player") else title)
        c.drawRightString(W - margin, 18, f"pagina {doc.page}")
        c.restoreState()

    frames = [Frame(margin, 34, colw, H - 34 - 30, id="c1", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
              Frame(margin + colw + gutter, 34, colw, H - 34 - 30, id="c2", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]
    doc = BaseDocTemplate(str(output), pagesize=A4, title=title, author="dnd5e")
    doc.addPageTemplates([PageTemplate(id="two", frames=frames, onPage=deco)])
    story = [Paragraph(esc(title), st.title),
             Paragraph(esc(f"{sheet['race']['name']} · {sheet['class_level']}" + (f" ({sheet['subclass_name']})" if sheet["subclass_name"] else "")
                           + (f" · giocatrice: {sheet['player']}" if sheet.get("player") and sheet.get("female") else
                              f" · giocatore: {sheet['player']}" if sheet.get("player") else "")), st.sub)]

    # --- regole base
    story += _bar("Come si gioca", st, dark)
    for line in how_to_play(sheet)[1:]:
        story.append(Paragraph(line, st.body))

    # --- soffio del drago
    b = sheet.get("breath")
    if b:
        story += _bar("Il tuo soffio di drago", st, dark)
        story.append(_card([Paragraph(f"Soffio di {esc(b['type'])}", st.card_h),
                            Paragraph(f"<b>Tempo:</b> 1 azione · <b>Area:</b> {esc(b['area'])} · <b>Usi:</b> 1, poi riposo breve o lungo", st.chips),
                            Paragraph(esc(f"Soffi {b['type']} davanti a te ({b['area']}). Ogni creatura lì dentro tira un d20 per resistere "
                                          f"(tiro salvezza su {b['save_name']} contro {b['dc']}): se sbaglia prende {b['dice']} danni da {b['type']}, "
                                          "se riesce prende la metà. Attenta a non prendere gli amici!"), st.card),
                            Paragraph(f"Inoltre il {esc(b['type'])} ti fa meno male: prendi solo metà dei danni da {esc(b['type'])}.", st.tip)],
                           st, light, dark, highlight=True))

    # --- magie
    sp = sheet["spellcasting"]
    if sp:
        table = rules["spells"]["spells"]
        chosen = {c["key"] for c in sp["cantrips"]}
        story += _bar("Le tue magie", st, dark)
        intro = (f"Quando una magia chiede un tiro salvezza, il nemico tira contro <b>{sp['save_dc']}</b>. "
                 f"Quando una magia chiede un attacco, tira <b>d20{fmt_mod(sp['attack_bonus'])}</b>.")
        story.append(Paragraph(intro, st.body))
        story.append(Paragraph("<b>Trucchetti</b> (gratis, li usi quando vuoi)", st.body))
        for cn in sp["cantrips"]:
            story.append(spell_card(cn, _values(cn, sp), st, theme, mark="sulla tua scheda"))
        by_level = sp["spells_by_level"]
        for lvl in sorted(by_level):
            label = "nel tuo libro" if sp.get("spellbook") else "preparata"
            story.append(Paragraph(f"<b>Magie di {lvl}° livello</b> (usano uno slot di {lvl}° livello o più alto)", st.body))
            for spell in by_level[lvl]:
                mark = ("preparata" if spell.get("prepared", True) else "nel libro") if sp.get("spellbook") else label
                if spell.get("always_prepared"):
                    mark = "sempre preparata"
                story.append(spell_card(spell, _values(spell, sp), st, theme, mark=mark))

        # altre scelte possibili
        taken = chosen | {s.get("key") for lvl in by_level for s in by_level[lvl]}
        list_key = sp.get("list")
        if list_key:
            if sp.get("spellbook"):
                head = "Altre magie che puoi copiare nel libro"
                note = ("Se trovi un rotolo o un libro con una di queste magie puoi copiarla nel tuo libro (2 ore e 50 mo per livello). "
                        "Ogni volta che sali di livello ne aggiungi 2 gratis. I trucchetti nuovi arrivano al 4° livello.")
            else:
                head = "Tutte le altre magie che puoi scegliere"
                note = (f"Dopo ogni riposo lungo puoi cambiare le magie preparate: ne tieni pronte {sp['prepared_max']}, scelte da questo elenco. "
                        "I trucchetti invece restano gli stessi: ne impari uno nuovo al 4° livello.")
            others = [{"key": k, **v} for k, v in table.items()
                      if list_key in v.get("lists", []) and v.get("level") is not None and v["level"] <= sp["max_level"] and k not in taken]
            if others:
                story += _bar(head, st, dark)
                story.append(Paragraph(note, st.body))
                for lvl in sorted({o["level"] for o in others}):
                    story.append(Paragraph(f"<b>{'Trucchetti' if lvl == 0 else f'{lvl}° livello'}</b>", st.body))
                    for o in sorted((o for o in others if o["level"] == lvl), key=lambda o: o["name"]):
                        story.append(spell_card(o, _values({}, sp), st, theme))
        # trucchetto razziale a scelta (es. Elfa Alta)
        for t in sheet["race"]["traits"]:
            ch = t.get("cantrip_choice")
            if not ch:
                continue
            ab = ch["ability"]
            mods = sheet["abilities"]["mods"]
            vals = {"att": fmt_mod(sheet["proficiency_bonus"] + mods[ab]), "cd": 8 + sheet["proficiency_bonus"] + mods[ab], "mod": fmt_mod(mods[ab])}
            opts = [{"key": k, **v} for k, v in table.items() if v.get("level") == 0 and ch["list"] in v.get("lists", []) and k not in taken]
            if opts:
                story += _bar(f"Il trucchetto da {sheet['race']['name'].split(' (')[0].lower()}: altre scelte", st, dark)
                story.append(Paragraph(f"Questo trucchetto usa l'Intelligenza: attacco d20{vals['att']}, i nemici resistono contro {vals['cd']}.", st.body))
                for o in sorted(opts, key=lambda o: o["name"]):
                    story.append(spell_card(o, vals, st, theme))

    # --- forme animali
    ws = sheet["wild_shape"]
    if ws:
        story += _bar("I tuoi animali (Forma Selvatica)", st, dark)
        story.append(Paragraph(how_to_play(sheet)[-1], st.body))
        story.append(Paragraph(f"Puoi diventare solo animali che hai già visto, fino a GS {ws['max_cr_str']}"
                               + ("" if ws["swim"] else ", senza nuoto") + ("" if ws["fly"] else " e senza volo") + ". "
                               "I numeri qui sotto sono già quelli dell'animale: usali al posto dei tuoi.", st.body))
        groups: dict[str, list] = {}
        for beast in ws["forms"]:
            groups.setdefault(beast.get("role", "combattere"), []).append(beast)
        for role in ["combattere", "esplorare", "viaggiare", "nuotare", "volare"] + [r for r in groups if r not in ROLE_NAMES]:
            if role not in groups:
                continue
            story.append(Paragraph(f"<b>{esc(ROLE_NAMES.get(role, role.capitalize()))}</b>", st.body))
            for beast in sorted(groups[role], key=lambda x: (-x["cr"], x["name"])):
                story.append(beast_card(beast, st, theme))

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)
    return output
