"""Genera templates/official_it/: il template ufficiale con le etichette tradotte in italiano.

Le scritte inglesi sono testo vero nel PDF: vengono rimosse (senza riempimento, così lo sfondo e la
grafica restano intatti) e sostituite con il testo italiano nella stessa posizione. Le abilità vengono
riordinate in ordine alfabetico italiano e la fieldmap viene rigenerata di conseguenza.

Uso:  python tools/make_italian_template.py
"""
from __future__ import annotations

from pathlib import Path

import pymupdf
import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "templates" / "official"
DST_DIR = ROOT / "templates" / "official_it"
SRC_PDF = SRC_DIR / "DnD_5E_CharacterSheet_FormFillable.pdf"
FONT = next(f for f in ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "C:/Windows/Fonts/arial.ttf")
            if Path(f).exists())  # Liberation Sans e Arial hanno le stesse metriche
FONTNAME = "LibSans"
_FONT = pymupdf.Font(fontfile=FONT)

EN_ORDER = ["acrobatics", "animal_handling", "arcana", "athletics", "deception", "history", "insight", "intimidation",
            "investigation", "medicine", "nature", "perception", "performance", "persuasion", "religion", "sleight_of_hand",
            "stealth", "survival"]
IT_ORDER = ["acrobatics", "animal_handling", "arcana", "athletics", "stealth", "investigation", "deception", "intimidation",
            "performance", "insight", "medicine", "nature", "perception", "persuasion", "sleight_of_hand", "religion",
            "survival", "history"]
EN_LABELS = {"acrobatics": "Acrobatics (Dex)", "animal_handling": "Animal Handling (Wis)", "arcana": "Arcana (Int)",
             "athletics": "Athletics (Str)", "deception": "Deception (Cha)", "history": "History (Int)", "insight": "Insight (Wis)",
             "intimidation": "Intimidation (Cha)", "investigation": "Investigation (Int)", "medicine": "Medicine (Wis)",
             "nature": "Nature (Int)", "perception": "Perception (Wis)", "performance": "Performance (Cha)",
             "persuasion": "Persuasion (Cha)", "religion": "Religion (Int)", "sleight_of_hand": "Sleight of Hand (Dex)",
             "stealth": "Stealth (Dex)", "survival": "Survival (Wis)"}
ABBR = {"str": "For", "dex": "Des", "con": "Cos", "int": "Int", "wis": "Sag", "cha": "Car"}

# (testo inglese, testo italiano, opzioni): x = x0 per disambiguare, align = left|center|right, maxw = larghezza max,
# rotate = 90, size = dimensione fissa
LABELS = {
    0: [
        ("CLASS & LEVEL", "CLASSE & LIVELLO", {"align": "left"}), ("BACKGROUND", "BACKGROUND", {"align": "left"}),
        ("PLAYER NAME", "NOME GIOCATORE", {"align": "left"}), ("RACE", "RAZZA", {"align": "left"}),
        ("ALIGNMENT", "ALLINEAMENTO", {"align": "left"}), ("CHARACTER NAME", "NOME PERSONAGGIO", {"align": "left"}),
        ("EXPERIENCE POINTS", "PUNTI ESPERIENZA", {"align": "left"}), ("INSPIRATION", "ISPIRAZIONE", {}),
        ("STRENGTH", "FORZA", {}), ("DEXTERITY", "DESTREZZA", {"maxw": 42}), ("CONSTITUTION", "COSTITUZIONE", {"maxw": 42}),
        ("INTELLIGENCE", "INTELLIGENZA", {"maxw": 42}), ("WISDOM", "SAGGEZZA", {}), ("CHARISMA", "CARISMA", {}),
        ("ARMOR", "CLASSE", {"size": 5.2}), ("CLASS", "ARMATURA", {"x": 238, "size": 4.6}),
        ("PROFICIENCY BONUS", "BONUS DI COMPETENZA", {}), ("INITIATIVE", "INIZIATIVA", {}), ("SPEED", "VELOCITÀ", {}),
        ("PERSONALITY TRAITS", "TRATTI CARATTERIALI", {}),
        ("Hit Point Maximum", "Massimo dei Punti Ferita", {"align": "left", "maxw": 59}),
        ("Strength", "Forza", {"align": "left"}), ("Dexterity", "Destrezza", {"align": "left"}),
        ("Constitution", "Costituzione", {"align": "left"}), ("Intelligence", "Intelligenza", {"align": "left"}),
        ("Wisdom", "Saggezza", {"align": "left"}), ("Charisma", "Carisma", {"align": "left"}),
        ("CURRENT HIT POINTS", "PUNTI FERITA ATTUALI", {}), ("IDEALS", "IDEALI", {}), ("SAVING THROWS", "TIRI SALVEZZA", {}),
        ("TEMPORARY HIT POINTS", "PUNTI FERITA TEMPORANEI", {}), ("BONDS", "LEGAMI", {}), ("Total", "Totale", {"align": "left"}),
        ("SUCCESSES", "SUCCESSI", {"align": "right"}), ("FAILURES", "FALLIMENTI", {"align": "right"}),
        ("HIT DICE", "DADI VITA", {}), ("DEATH SAVES", "TS CONTRO MORTE", {}), ("FLAWS", "DIFETTI", {}),
        ("NAME", "NOME", {"align": "left"}), ("ATK BONUS", "BONUS ATT.", {"align": "left"}), ("DAMAGE/TYPE", "DANNI/TIPO", {"align": "left"}),
        ("SKILLS", "ABILITÀ", {}), ("ATTACKS & SPELLCASTING", "ATTACCHI & INCANTESIMI", {}),
        ("PASSIVE WISDOM (PERCEPTION)", "SAGGEZZA (PERCEZIONE) PASSIVA", {"maxw": 100}),
        ("CP", "MR", {}), ("SP", "MA", {}), ("EP", "ME", {}), ("GP", "MO", {}), ("PP", "MP", {}),
        ("OTHER PROFICIENCIES & LANGUAGES", "ALTRE COMPETENZE & LINGUAGGI", {}),
        ("EQUIPMENT", "EQUIPAGGIAMENTO", {}), ("FEATURES & TRAITS", "PRIVILEGI & TRATTI", {}),
    ],
    1: [
        ("AGE", "ETÀ", {"align": "left"}), ("HEIGHT", "ALTEZZA", {"align": "left"}), ("WEIGHT", "PESO", {"align": "left"}),
        ("CHARACTER NAME", "NOME PERSONAGGIO", {"align": "left"}), ("SKIN", "PELLE", {"align": "left"}),
        ("EYES", "OCCHI", {"align": "left"}), ("HAIR", "CAPELLI", {"align": "left"}),
        ("NAME", "NOME", {"align": "left"}), ("SYMBOL", "SIMBOLO", {}),
        ("CHARACTER APPEARANCE", "ASPETTO DEL PERSONAGGIO", {}), ("ALLIES & ORGANIZATIONS", "ALLEATI & ORGANIZZAZIONI", {}),
        ("ADDITIONAL FEATURES & TRAITS", "PRIVILEGI & TRATTI AGGIUNTIVI", {}),
        ("TREASURE", "TESORO", {}), ("CHARACTER BACKSTORY", "STORIA DEL PERSONAGGIO", {}),
    ],
    2: [
        ("SPELLCASTING", "CARATTERISTICA", {"x": 292, "maxw": 62}), ("ABILITY", "DA INCANTATORE", {"maxw": 62}),
        ("SPELL SAVE DC", "CD TIRO SALVEZZA", {"maxw": 62}),
        ("SPELL ATTACK", "BONUS ATTACCO", {"maxw": 62}), ("BONUS", "INCANTESIMI", {"maxw": 62}),
        ("SPELLCASTING", "CLASSE", {"x": 70, "align": "left"}), ("CLASS", "DA INCANTATORE", {"x": 70, "align": "left"}),
        ("CANTRIPS", "TRUCCHETTI", {}),
        ("SPELL", "LIVELLO", {"x": 31, "align": "left", "maxw": 18}), ("LEVEL", "INCANT.", {"x": 31, "align": "left", "maxw": 18}),
        ("SLOTS TOTAL", "SLOT TOTALI", {"align": "left"}), ("SLOTS EXPENDED", "SLOT USATI", {"align": "left"}),
        ("SPELL NAME", "NOME INCANTESIMO", {}), ("SPELLS KNOWN", "INCANTESIMI CONOSCIUTI", {"rotate": 90}),
    ],
}


def lines_of(page):
    groups = {}
    for w in page.get_text("words"):
        groups.setdefault((w[5], w[6]), []).append(w)
    out = []
    for ws in groups.values():
        ws.sort(key=lambda w: w[0])
        rect = pymupdf.Rect(min(w[0] for w in ws), min(w[1] for w in ws), max(w[2] for w in ws), max(w[3] for w in ws))
        out.append((" ".join(w[4] for w in ws), rect))
    return out


def find(lines, text, x=None):
    cands = [(t, r) for t, r in lines if t == text]
    if not cands:
        raise SystemExit(f"Etichetta non trovata: {text!r}")
    if x is not None:
        cands.sort(key=lambda tr: abs(tr[1].x0 - x))
    return cands[0][1]


def text_width(text, size):
    return _FONT.text_length(text, fontsize=size)


def place(page, rect, text, opts):
    align = opts.get("align", "center")
    size = opts.get("size") or min(rect.height * 0.92, 7.0)
    maxw = opts.get("maxw") or max(rect.width * 1.7, rect.width + 24)
    while text_width(text, size) > maxw and size > 3.5:
        size -= 0.25
    tw = text_width(text, size)
    if opts.get("rotate") == 90:
        cx, cy = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
        page.insert_text((cx + size * 0.35, cy + tw / 2), text, fontsize=size, fontname=FONTNAME, fontfile=FONT, rotate=90)
        return
    baseline = rect.y0 + (rect.height + size * 0.72) / 2
    x = rect.x0 if align == "left" else rect.x1 - tw if align == "right" else (rect.x0 + rect.x1) / 2 - tw / 2
    page.insert_text((x, baseline), text, fontsize=size, fontname=FONTNAME, fontfile=FONT)


def main():
    DST_DIR.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(SRC_PDF))
    skills_it = yaml.safe_load((ROOT / "dnd5e" / "rules" / "skills.yaml").read_text(encoding="utf-8"))["skills"]
    for pno, labels in LABELS.items():
        page = doc[pno]
        lines = lines_of(page)
        jobs = [(find(lines, en, opts.get("x")), it, opts) for en, it, opts in labels]
        if pno == 0:
            rows = [find(lines, EN_LABELS[key]) for key in EN_ORDER]
            for i, key in enumerate(IT_ORDER):
                info = skills_it[key]
                jobs.append((rows[i], f"{info['it']} ({ABBR[info['ability']]})", {"align": "left", "maxw": 66}))
        if pno == 2:
            for t, r in lines:  # lettere di "PREPARED" disposte ad arco
                if len(t) == 1 and t.isalpha() and r.x0 < 50:
                    jobs.append((r, None, {}))
        for rect, _, _ in jobs:
            page.add_redact_annot(rect, fill=False)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
        for rect, it, opts in jobs:
            if it:
                place(page, rect, it, opts)
        if pno == 2:
            place(page, pymupdf.Rect(24, 343, 46, 354), "PREP.", {"size": 4.2})
    out_pdf = DST_DIR / "DnD_5E_CharacterSheet_IT.pdf"
    doc.save(str(out_pdf), garbage=3, deflate=True)
    fm = yaml.safe_load((SRC_DIR / "fieldmap.yaml").read_text(encoding="utf-8"))
    fields = dict(fm["fields"])
    for i, en_key in enumerate(EN_ORDER):
        fields[f"skill_{IT_ORDER[i]}"] = fm["fields"][f"skill_{en_key}"]
        fields[f"skill_{IT_ORDER[i]}_prof"] = fm["fields"][f"skill_{en_key}_prof"]
    fm["fields"] = fields
    header = ("# Mappa dei campi del template ITALIANO, generata da tools/make_italian_template.py a partire da\n"
              "# templates/official/fieldmap.yaml: le righe delle abilità sono in ordine alfabetico italiano.\n")
    (DST_DIR / "fieldmap.yaml").write_text(header + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    print(f"scritto {out_pdf}")


if __name__ == "__main__":
    main()
