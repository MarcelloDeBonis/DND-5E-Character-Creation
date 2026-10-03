"""Guida per giocatori giovani: un PDF separato dalla scheda, in parole semplici.

Contiene il promemoria delle regole, una carta per ogni potere, una per ogni magia (quelle sulla
scheda e tutte le altre che il personaggio può scegliere) e, per i druidi, una carta per ogni
animale della Forma Selvatica. I testi semplici stanno nei file di regole (campi `kid`, `tip`,
`kid_attacks`, `kid_traits`).
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

from .engine import _scale_cantrip, fmt_cr, fmt_mod, gender_values, kid_fmt
from .sheet import FONTS, _register_fonts, esc, how_to_play, wild_shape_line

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
SAVE_NAMES = {"str": "Forza", "dex": "Destrezza", "con": "Costituzione", "int": "Intelligenza", "wis": "Saggezza", "cha": "Carisma"}


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


def spell_card(sp, values, st, theme, mark="", ritual_ok=True):
    dark, light, _ = theme
    lvl = "Trucchetto" if sp.get("level") == 0 else f"{sp.get('level')}° livello"
    head = f"{esc(sp['name'])}  <font size=8 color='#555555'>{lvl}</font>"
    if mark:
        head += f"  <font size=8 color='{dark}'><b>{esc(mark)}</b></font>"
    chips = [f"<b>Tempo:</b> {esc(sp.get('cast', '—'))}", f"<b>Distanza:</b> {esc(_range(sp.get('range')))}",
             f"<b>Durata:</b> {esc(sp.get('duration', '—'))}"]
    if sp.get("conc"):
        chips.append("<b>C</b> = concentrazione")
    if sp.get("ritual") and ritual_ok:
        chips.append("<b>R</b> = rituale")
    rows = [Paragraph(head, st.card_h), Paragraph(" · ".join(chips), st.chips),
            Paragraph(esc(kid_fmt(sp.get("kid") or sp.get("text", ""), values)), st.card)]
    if sp.get("tip"):
        rows.append(Paragraph("Quando usarla: " + esc(kid_fmt(sp["tip"], values)), st.tip))
    return _card(rows, st, light, dark, highlight=bool(mark))


def beast_card(b, st, theme, values=None):
    dark, light, _ = theme
    values = values or {}
    spd = ", ".join(f"{v:g} m" if k == "walk" else f"{SPEED_NAMES.get(k, k)} {v:g} m" for k, v in b["speed"].items() if v)
    rows = [Paragraph(f"{esc(b['name'])}  <font size=8 color='#555555'>{esc(b['size'])}, GS {fmt_cr(b['cr'])}</font>", st.card_h),
            Paragraph(f"<b>PF {b['hp']}</b> · <b>CA {b['ac']}</b> · <b>Velocità</b> {esc(spd)}"
                      + (" · <b>Elementale:</b> costa 2 usi di Forma Selvatica" if b.get("elemental") else ""), st.chips)]
    if b.get("kid"):
        rows.append(Paragraph(esc(kid_fmt(b["kid"], values)), st.card))
    attacks = b.get("kid_attacks")
    if attacks:
        for a in attacks:
            line = f"<b>{esc(a.get('name', ''))}</b>: tira d20{esc(a.get('hit', ''))}; se colpisci {esc(a.get('damage', ''))} danni {esc(a.get('type', ''))}."
            if a.get("extra"):
                line += " " + esc(kid_fmt(a["extra"], values))
            rows.append(Paragraph(line, st.card))
        if b.get("multi"):
            rows.append(Paragraph(esc(kid_fmt(b["multi"], values)), st.tip))
    else:
        rows.append(Paragraph("<b>Attacchi:</b> " + esc(b.get("attacks", "")), st.card))
    for t in b.get("kid_traits") or ([b["traits"]] if b.get("traits") else []):
        rows.append(Paragraph("• " + esc(kid_fmt(t, values)), st.chips))
    return _card(rows, st, light, dark)


def _values(sp_like, caster, sheet=None):
    ab = sp_like.get("attack_bonus", caster["attack_bonus"])
    dc = sp_like.get("save_dc", caster["save_dc"])
    mod = sp_like.get("mod", caster["mod"]) if "attack_bonus" not in sp_like else ab - (caster["attack_bonus"] - caster["mod"])
    out = {"att": fmt_mod(ab), "cd": dc, "mod": fmt_mod(mod)}
    if sheet is not None:
        out.update(gender_values(sheet.get("female")))
        if sp_like.get("level") == 0 and sp_like.get("damage"):
            out["dadi"] = sp_like.get("damage_scaled") or (sp_like["damage"] if sp_like.get("scaling") == "beams"
                                                           else _scale_cantrip(sp_like["damage"], sheet["level"]))
    return out


def _power_cards(sheet, st, theme):
    """Una carta per ogni privilegio, opzione o talento che ha un testo semplice."""
    dark, light, _ = theme
    cards = []
    entries = sheet["features"] + sheet["fighting_styles"] + ([sheet["background_feature"]] if sheet["background_feature"] else [])
    seen = set()
    for f in entries:
        kid = f.get("kid")
        if f.get("kid_hide") or not kid or f["name"] in seen:
            continue
        seen.add(f["name"])
        src = f.get("source", "")
        head = f"{esc(f['name'].replace(' (background)', ''))}  <font size=8 color='#555555'>{esc(src)}</font>"
        cards.append(_card([Paragraph(head, st.card_h), Paragraph(esc(kid), st.card)], st, light, dark))
    return cards


def build_guide(sheet: dict, rules: dict, output: str | Path) -> Path:
    theme = THEMES.get(sheet["class"]["key"], DEFAULT_THEME)
    dark, light, paper = theme
    st = Styles(dark)
    W, H = A4
    margin, gutter = 36, 16
    colw = (W - 2 * margin - gutter) / 2
    title = f"Guida di {sheet['name']}"
    gv = gender_values(sheet.get("female"))

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

    # --- poteri (privilegi, opzioni, talenti)
    powers = _power_cards(sheet, st, theme)
    if powers:
        story += _bar("I tuoi poteri", st, dark)
        story += powers

    # --- manovre
    mi = sheet.get("maneuver_info")
    if sheet.get("maneuvers") and mi:
        story += _bar("Le tue manovre", st, dark)
        story.append(Paragraph(f"Hai <b>{mi['dice']} dadi di superiorità</b> ({esc(mi['die'])}): ogni manovra ne usa uno e li riprendi tutti "
                               f"dopo un riposo breve o lungo. Quando il nemico deve resistere, tira contro <b>{mi['dc']}</b>.", st.body))
        for m in sheet["maneuvers"]:
            rows = [Paragraph(esc(m["name"]), st.card_h)]
            if m.get("save"):
                rows.append(Paragraph(f"<b>Il nemico resiste con:</b> {SAVE_NAMES.get(m['save'], m['save'])} contro {mi['dc']}", st.chips))
            rows.append(Paragraph(esc(m.get("kid") or m.get("text", "")), st.card))
            story.append(_card(rows, st, light, dark))

    # --- compagno animale
    comp = sheet.get("companion")
    if comp:
        story += _bar("Il tuo compagno animale", st, dark)
        if comp.get("card_kid"):
            story.append(Paragraph(esc(kid_fmt(comp["card_kid"], {**sheet.get("placeholders", {}), **gv})), st.body))
        beast = {"name": comp["name"], "size": comp["size"], "cr": comp["cr"], "hp": comp["hp"], "ac": comp["ac"], "speed": comp["speed"],
                 "kid": comp.get("kid"), "kid_attacks": comp["attacks"], "kid_traits": comp.get("kid_traits"), "traits": comp.get("traits"),
                 "attacks": comp.get("attacks_text")}
        story.append(beast_card(beast, st, theme, gv))

    # --- soffio del drago
    b = sheet.get("breath")
    if b:
        story += _bar("Il tuo soffio di drago", st, dark)
        story.append(_card([Paragraph(f"Soffio di {esc(b['type'])}", st.card_h),
                            Paragraph(f"<b>Tempo:</b> 1 azione · <b>Area:</b> {esc(b['area'])} · <b>Usi:</b> 1, poi riposo breve o lungo", st.chips),
                            Paragraph(esc(f"Soffi {b['type']} davanti a te ({b['area']}). Ogni creatura lì dentro tira un d20 per resistere "
                                          f"(tiro salvezza su {b['save_name']} contro {b['dc']}): se sbaglia prende {b['dice']} danni da {b['type']}, "
                                          f"se riesce prende la metà. Attent{gv['o']} a non prendere gli amici!"), st.card),
                            Paragraph(f"Inoltre il {esc(b['type'])} ti fa meno male: prendi solo metà dei danni da {esc(b['type'])}.", st.tip)],
                           st, light, dark, highlight=True))

    # --- magie
    sp = sheet["spellcasting"]
    if sp:
        table = rules["spells"]["spells"]
        ritual_ok = bool(sp.get("ritual"))
        chosen = {c["key"] for c in sp["cantrips"]}
        story += _bar("Le tue magie", st, dark)
        intro = (f"Quando una magia chiede un tiro salvezza, il nemico tira contro <b>{sp['save_dc']}</b>. "
                 f"Quando una magia chiede un attacco, tira <b>d20{fmt_mod(sp['attack_bonus'])}</b>.")
        story.append(Paragraph(intro, st.body))
        if sp["cantrips"]:
            story.append(Paragraph("<b>Trucchetti</b> (gratis, li usi quando vuoi)", st.body))
        for cn in sp["cantrips"]:
            story.append(spell_card(cn, _values(cn, sp, sheet), st, theme, mark="sulla tua scheda", ritual_ok=ritual_ok))
        by_level = sp["spells_by_level"]
        for lvl in sorted(by_level):
            label = "nel tuo libro" if sp.get("spellbook") else "preparata" if sp["prepares"] else "la conosci"
            if sp["slots"]:
                story.append(Paragraph(f"<b>Magie di {lvl}° livello</b> (usano uno slot di {lvl}° livello o più alto)", st.body))
            else:
                story.append(Paragraph(f"<b>Magie di {lvl}° livello</b>", st.body))
            for spell in by_level[lvl]:
                mark = ("preparata" if spell.get("prepared", True) else "nel libro") if sp.get("spellbook") else label
                if spell.get("always_prepared"):
                    mark = "sempre preparata" + (f" ({spell['tag']})" if spell.get("tag") else "")
                elif spell.get("extra"):
                    mark = spell.get("tag") or "privilegio"
                story.append(spell_card(spell, _values(spell, sp, sheet), st, theme, mark=mark,
                                        ritual_ok=ritual_ok or spell.get("tag") == "solo rituale"))

        # altre scelte possibili
        taken = chosen | {s.get("key") for lvl in by_level for s in by_level[lvl]}
        list_key = sp.get("list")
        if list_key:
            nxt = sp.get("next_cantrip_level")
            if sp.get("spellbook"):
                head = "Altre magie che puoi copiare nel libro"
                note = ("Se trovi un rotolo o un libro con una di queste magie puoi copiarla nel tuo libro (2 ore e 50 mo per livello). "
                        "Ogni volta che sali di livello ne aggiungi 2 gratis." + (f" I trucchetti nuovi arrivano al {nxt}° livello." if nxt else ""))
            elif sp["prepares"]:
                head = "Tutte le altre magie che puoi scegliere"
                note = f"Dopo ogni riposo lungo puoi cambiare le magie preparate: ne tieni pronte {sp['prepared_max']}, scelte da questo elenco."
                if sp["cantrips"]:
                    note += " I trucchetti invece restano gli stessi" + (f": ne impari uno nuovo al {nxt}° livello." if nxt else ".")
            else:
                head = "Le magie che potrai imparare"
                note = ("Tu conosci poche magie, ma le usi sempre. Quando sali di livello impari quelle nuove da questo elenco "
                        "e puoi cambiarne una che conosci con un'altra." + (f" Il prossimo trucchetto nuovo arriva al {nxt}° livello." if nxt else ""))
            schools = sp.get("schools")
            expanded = set(sp.get("expanded") or [])
            others = [{"key": k, **v} for k, v in table.items()
                      if (list_key in v.get("lists", []) or k in expanded) and v.get("level") is not None and v["level"] <= sp["max_level"]
                      and k not in taken and not (schools and v["level"] > 0 and v.get("school") not in schools and k not in expanded)]
            if not sp["cantrips"] and not sheet["class"]["table"].get("cantrips_known"):
                others = [o for o in others if o["level"] > 0]
            if others:
                story += _bar(head, st, dark)
                story.append(Paragraph(note, st.body))
                if schools:
                    story.append(Paragraph(f"Le tue magie sono di {' e '.join(schools)}. "
                                           + (f"Fino a {sp['any_school_free']} possono essere di un'altra scuola: quelle le trovi nel Manuale."
                                              if sp.get("any_school_free") else ""), st.body))
                for lvl in sorted({o["level"] for o in others}):
                    story.append(Paragraph(f"<b>{'Trucchetti' if lvl == 0 else f'{lvl}° livello'}</b>", st.body))
                    for o in sorted((o for o in others if o["level"] == lvl), key=lambda o: o["name"]):
                        story.append(spell_card(o, _values(o if lvl == 0 else {}, sp, sheet), st, theme, ritual_ok=ritual_ok))
        # trucchetto razziale a scelta (es. Elfa Alta)
        for t in sheet["race"]["traits"]:
            ch = t.get("cantrip_choice")
            if not ch:
                continue
            ab = ch["ability"]
            mods = sheet["abilities"]["mods"]
            vals = {"att": fmt_mod(sheet["proficiency_bonus"] + mods[ab]), "cd": 8 + sheet["proficiency_bonus"] + mods[ab], "mod": fmt_mod(mods[ab]), **gv}
            opts = [{"key": k, **v} for k, v in table.items() if v.get("level") == 0 and ch["list"] in v.get("lists", []) and k not in taken]
            if opts:
                ab_name = rules["skills"]["abilities"].get(ab, {}).get("it", ab)
                story += _bar(f"Il trucchetto da {sheet['race']['name'].split(' (')[0].lower()}: altre scelte", st, dark)
                art = "l'" if ab_name[:1] in "AEIOU" else "il " if ab_name == "Carisma" else "la "
                story.append(Paragraph(f"Questo trucchetto usa {art}{ab_name}: "
                                       f"attacco d20{vals['att']}, i nemici resistono contro {vals['cd']}.", st.body))
                for o in sorted(opts, key=lambda o: o["name"]):
                    ov = dict(vals)
                    if o.get("damage"):
                        ov["dadi"] = _scale_cantrip(o["damage"], sheet["level"])
                    story.append(spell_card(o, ov, st, theme, ritual_ok=ritual_ok))

    # --- magie rituali di chi non ha la pagina degli incantesimi (Guerriero Totemico)
    if sheet.get("extra_spells"):
        story += _bar("Le tue magie rituali", st, dark)
        story.append(Paragraph("Le lanci solo come rituale: ci metti 10 minuti in più e non serve nessuno slot.", st.body))
        for x in sheet["extra_spells"]:
            story.append(spell_card(x, {**gv}, st, theme, mark=x.get("tag", ""), ritual_ok=True))

    # --- Magia Selvaggia
    surge = sheet.get("surge_table")
    if surge:
        story += _bar("Magia Selvaggia: la tabella", st, dark)
        story.append(Paragraph("Quando il Master te lo chiede, tira un d100 (due d10: decine e unità) e guarda qui cosa succede.", st.body))
        rows = [[Paragraph("<b>d100</b>", st.chips), Paragraph("<b>Cosa succede</b>", st.chips)]]
        for r in surge:
            rows.append([Paragraph(esc(r.get("roll", "")), st.chips), Paragraph(esc(kid_fmt(r.get("kid") or r.get("text", ""), gv)), st.chips)])
        t = Table(rows, colWidths=[colw * 0.16, colw * 0.84], repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#999999")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(light)),
                               ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
        story.append(t)

    # --- forme animali
    ws = sheet["wild_shape"]
    if ws:
        story += _bar("I tuoi animali (Forma Selvatica)", st, dark)
        story.append(Paragraph(wild_shape_line(sheet), st.body))
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
                story.append(beast_card(beast, st, theme, gv))

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)
    return output
