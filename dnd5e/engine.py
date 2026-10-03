"""Motore di regole: trasforma il YAML di un personaggio in una scheda calcolata.

L'output di `build_sheet` è un dizionario con tutti i valori derivati (modificatori,
tiri salvezza, abilità, CA, PF, attacchi, privilegi...) pronto per il renderer PDF
o per un riepilogo testuale. Le regole sono lette dai file YAML in `dnd5e/rules/`.
"""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

RULES_DIR = Path(__file__).parent / "rules"
ABILITIES = ["str", "dex", "con", "int", "wis", "cha"]

ARMOR_CATEGORY_NAMES = {
    "light": "armature leggere",
    "medium": "armature medie",
    "heavy": "armature pesanti",
    "shields": "scudi",
}
WEAPON_CATEGORY_NAMES = {"simple": "armi semplici", "martial": "armi da guerra"}


class RulesError(ValueError):
    """Errore nei dati del personaggio rispetto alle regole."""


def load_rules() -> dict:
    rules = {}
    for path in sorted(RULES_DIR.glob("*.yaml")):
        rules[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return rules


def load_character(path: str | Path) -> dict:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["_dir"] = path.parent
    data["_stem"] = path.stem
    return data


def ability_mod(score: int) -> int:
    return (score - 10) // 2


def fmt_mod(value: int) -> str:
    return f"+{value}" if value >= 0 else str(value)


def _merge_bonus(target: dict, bonus: dict | None) -> None:
    for key, value in (bonus or {}).items():
        target[key] = target.get(key, 0) + value


# ---------------------------------------------------------------------------
# Razza
# ---------------------------------------------------------------------------
def resolve_race(char: dict, rules: dict) -> dict:
    races = rules["races"]
    race_key = char["race"]
    if race_key not in races:
        raise RulesError(f"Razza sconosciuta: {race_key}")
    race = copy.deepcopy(races[race_key])
    result = {
        "name": race["name"],
        "name_en": race.get("name_en", race["name"]),
        "size": race.get("size", "Medio"),
        "speed": race.get("speed", 30),
        "ability_bonus": dict(race.get("ability_bonus", {})),
        "ability_choice": race.get("ability_choice"),
        "languages": list(race.get("languages", [])),
        "extra_languages": race.get("extra_languages", 0),
        "traits": list(race.get("traits", [])),
        "age": race.get("age", ""),
    }
    sub_key = char.get("subrace")
    pools = {}
    pools.update(race.get("subraces", {}) or {})
    pools.update(race.get("variants", {}) or {})
    if sub_key:
        if sub_key not in pools:
            raise RulesError(f"Sottorazza sconosciuta per {race_key}: {sub_key}")
        sub = pools[sub_key]
        result["name"] = sub.get("name", result["name"])
        result["name_en"] = sub.get("name_en", result["name_en"])
        if "ability_bonus" in sub:
            if sub.get("replaces_base_bonus"):
                result["ability_bonus"] = {}
            _merge_bonus(result["ability_bonus"], sub["ability_bonus"])
        if "ability_choice" in sub:
            result["ability_choice"] = sub["ability_choice"]
        if "speed" in sub:
            result["speed"] = sub["speed"]
        result["traits"] += sub.get("traits", [])
        result["extra_languages"] += sub.get("extra_languages", 0)
    elif pools:
        raise RulesError(
            f"La razza {race_key} richiede una sottorazza tra: {', '.join(pools)}"
        )
    # tratti con effetti meccanici
    for trait in result["traits"]:
        result["extra_languages"] += trait.get("extra_languages", 0)
    return result


# ---------------------------------------------------------------------------
# Punteggi di caratteristica
# ---------------------------------------------------------------------------
def resolve_abilities(char: dict, race: dict, rules: dict, warnings: list) -> dict:
    spec = char.get("abilities", {})
    method = spec.get("method", "manual")
    base = {k: int(spec.get("base", {}).get(k, 10)) for k in ABILITIES}
    skills_rules = rules["skills"]
    if method == "point_buy":
        costs = skills_rules["point_buy"]["costs"]
        total = 0
        for k, v in base.items():
            if v not in costs:
                raise RulesError(f"Point buy: {k.upper()} = {v} non è tra 8 e 15")
            total += costs[v]
        budget = skills_rules["point_buy"]["budget"]
        if total != budget:
            warnings.append(f"Point buy: spesi {total} punti su {budget}")
    elif method == "standard_array":
        if sorted(base.values()) != sorted(skills_rules["standard_array"]):
            raise RulesError("Array standard: i punteggi base devono essere 15, 14, 13, 12, 10, 8")
    elif method in ("manual", "rolled"):
        for k, v in base.items():
            if not 3 <= v <= 18:
                warnings.append(f"Punteggio base {k.upper()} = {v} fuori dal range 3-18")
    else:
        raise RulesError(f"Metodo per le caratteristiche sconosciuto: {method}")

    scores = dict(base)
    _merge_bonus(scores, race["ability_bonus"])
    choice = race.get("ability_choice")
    if choice:
        picks = spec.get("racial_choice", [])
        if len(picks) != choice["count"]:
            raise RulesError(
                f"La razza richiede {choice['count']} caratteristiche in 'abilities.racial_choice'"
            )
        for k in picks:
            if k in choice.get("exclude", []):
                raise RulesError(f"La razza non permette il bonus a scelta su {k.upper()}")
            scores[k] += choice["bonus"]
    for asi in spec.get("asi", []) or []:
        _merge_bonus(scores, asi)
    for k, v in scores.items():
        if v > 20:
            warnings.append(f"{k.upper()} = {v}: il massimo normale è 20")
    return {
        "method": method,
        "base": base,
        "scores": scores,
        "mods": {k: ability_mod(v) for k, v in scores.items()},
    }


# ---------------------------------------------------------------------------
# Classe
# ---------------------------------------------------------------------------
def resolve_class(char: dict, rules: dict) -> dict:
    classes = rules["classes"]
    key = char["class"]
    if key not in classes:
        raise RulesError(f"Classe sconosciuta: {key}")
    cls = copy.deepcopy(classes[key])
    level = int(char.get("level", 1))
    if not 1 <= level <= 20:
        raise RulesError("Il livello deve essere tra 1 e 20")
    features = []
    for lvl in sorted(cls.get("features", {})):
        if lvl <= level:
            for f in cls["features"][lvl]:
                features.append({**f, "level": lvl, "source": cls["name"]})
    subclass = None
    sub_key = char.get("subclass")
    sub_level = cls.get("subclass_level", 99)
    if level >= sub_level:
        if not sub_key:
            raise RulesError(
                f"Al livello {level} serve un {cls.get('subclass_label', 'archetipo')} ('subclass')"
            )
        subs = cls.get("subclasses", {})
        if sub_key not in subs:
            raise RulesError(f"{cls.get('subclass_label', 'Archetipo')} sconosciuto: {sub_key}")
        subclass = subs[sub_key]
        for lvl in sorted(subclass.get("features", {})):
            if lvl <= level:
                for f in subclass["features"][lvl]:
                    features.append({**f, "level": lvl, "source": subclass["name"]})
    return {
        "key": key,
        "name": cls["name"],
        "name_en": cls.get("name_en", cls["name"]),
        "level": level,
        "hit_die": cls["hit_die"],
        "saves": cls["saves"],
        "armor": cls.get("armor", []),
        "weapons": cls.get("weapons", []),
        "tools": cls.get("tools", []),
        "skill_choices": cls.get("skill_choices", {"count": 0, "from": []}),
        "spellcasting": cls.get("spellcasting"),
        "subclass_label": cls.get("subclass_label"),
        "subclass": subclass,
        "subclass_key": sub_key,
        "features": features,
    }


# ---------------------------------------------------------------------------
# Competenze e abilità
# ---------------------------------------------------------------------------
def resolve_skills(char: dict, race: dict, cls: dict, background: dict, rules: dict, warnings: list) -> dict:
    proficient = {}
    choices = list(char.get("skills", []) or [])
    pool = cls["skill_choices"]
    if len(choices) != pool["count"]:
        raise RulesError(
            f"La classe {cls['name']} richiede {pool['count']} abilità in 'skills' (date: {len(choices)})"
        )
    for s in choices:
        if s not in rules["skills"]["skills"]:
            raise RulesError(f"Abilità sconosciuta: {s}")
        if pool["from"] and s not in pool["from"]:
            raise RulesError(f"{s} non è tra le abilità di classe di {cls['name']}")
        proficient[s] = f"classe ({cls['name']})"
    for s in background["skills"]:
        if s in proficient:
            warnings.append(f"Abilità {s} duplicata tra classe e background: scegline un'altra")
        proficient.setdefault(s, f"background ({background['name']})")
    for trait in race["traits"]:
        for s in trait.get("skills", []):
            if s in proficient:
                warnings.append(f"Abilità {s} già data da {proficient[s]}: la razza la dà di nuovo")
            proficient.setdefault(s, f"razza ({trait['name']})")
    for s in char.get("extra_skills", []) or []:
        proficient.setdefault(s, "altro")
    expertise = set(char.get("expertise", []) or [])
    for s in expertise:
        if s not in proficient:
            raise RulesError(f"Maestria in {s} ma nessuna competenza")
    return {"proficient": proficient, "expertise": expertise}


def resolve_background(char: dict, rules: dict) -> dict:
    key = char.get("background")
    if isinstance(key, dict):  # background personalizzato definito nel file
        bg = copy.deepcopy(key)
        bg.setdefault("skills", [])
        bg.setdefault("tools", [])
        bg.setdefault("languages", 0)
        bg.setdefault("equipment", [])
        bg.setdefault("gold", 0)
        return bg
    if key not in rules["backgrounds"]:
        raise RulesError(f"Background sconosciuto: {key}")
    return copy.deepcopy(rules["backgrounds"][key])


# ---------------------------------------------------------------------------
# Equipaggiamento, CA, attacchi
# ---------------------------------------------------------------------------
def _weapon_proficient(wkey: str, weapon: dict, cls: dict, race: dict) -> bool:
    if weapon.get("category") in cls["weapons"] or wkey in cls["weapons"]:
        return True
    for trait in race["traits"]:
        if wkey in trait.get("weapon_proficiencies", []):
            return True
    return False


def resolve_weapons(char: dict, abilities: dict, cls: dict, race: dict, prof: int, styles: list, rules: dict) -> list:
    table = rules["equipment"]["weapons"]
    mods = abilities["mods"]
    out = []
    for entry in char.get("weapons", []) or []:
        if isinstance(entry, str):
            entry = {"key": entry}
        wkey = entry.get("key")
        weapon = copy.deepcopy(table.get(wkey, {})) if wkey else {}
        if wkey and not weapon:
            raise RulesError(f"Arma sconosciuta: {wkey}")
        weapon.update({k: v for k, v in entry.items() if k != "key"})
        props = weapon.get("properties", [])
        ranged = weapon.get("type") == "ranged"
        if "finesse" in props:
            ability = "dex" if mods["dex"] >= mods["str"] else "str"
        elif ranged and "thrown" not in props:
            ability = "dex"
        else:
            ability = "str"
        ability = weapon.get("ability", ability)
        amod = mods[ability]
        proficient = weapon.get("proficient")
        if proficient is None:
            proficient = _weapon_proficient(wkey, weapon, cls, race) if wkey else True
        atk = amod + (prof if proficient else 0) + int(weapon.get("magic_bonus", 0))
        dmg_bonus = amod + int(weapon.get("magic_bonus", 0))
        notes = []
        if ranged and "archery" in styles:
            atk += 2
            notes.append("Tiro +2")
        if (not ranged and "dueling" in styles and "two_handed" not in props):
            dmg_bonus += 2
            notes.append("Duello +2 danni se usata in una mano")
        dice = weapon.get("damage", "")
        dmg = f"{dice}{fmt_mod(dmg_bonus)}" if dice and dice[0].isdigit() else dice
        if weapon.get("versatile"):
            dmg += f" ({weapon['versatile']}{fmt_mod(dmg_bonus)} a 2 mani)"
        dmg_type = weapon.get("damage_type", "")
        extra = []
        if weapon.get("range"):
            extra.append(f"gittata {weapon['range']} m")
        prop_names = {
            "finesse": "accurata", "light": "leggera", "heavy": "pesante", "two_handed": "a due mani",
            "versatile": "versatile", "thrown": "da lancio", "ammunition": "munizioni", "reach": "portata",
            "loading": "ricarica", "special": "speciale",
        }
        extra += [prop_names.get(p, p) for p in props if p != "versatile"]
        out.append({
            "key": wkey,
            "name": weapon.get("name", wkey),
            "attack": atk,
            "attack_str": fmt_mod(atk),
            "damage": f"{dmg} {dmg_type}".strip(),
            "ability": ability,
            "proficient": proficient,
            "properties": extra,
            "notes": notes,
        })
    return out


def resolve_ac(char: dict, abilities: dict, cls: dict, styles: list, rules: dict, warnings: list) -> dict:
    armor_table = rules["equipment"]["armor"]
    dex = abilities["mods"]["dex"]
    armor_key = char.get("armor")
    parts = []
    if armor_key:
        if armor_key not in armor_table:
            raise RulesError(f"Armatura sconosciuta: {armor_key}")
        armor = armor_table[armor_key]
        ac = armor["base"]
        parts.append(f"{armor['name']} {armor['base']}")
        if armor["dex"] == "full":
            ac += dex
            parts.append(f"DES {fmt_mod(dex)}")
        elif armor["dex"] == "max2":
            ac += min(dex, 2)
            parts.append(f"DES {fmt_mod(min(dex, 2))} (max +2)")
        if armor["category"] not in cls["armor"]:
            warnings.append(f"Nessuna competenza in {ARMOR_CATEGORY_NAMES[armor['category']]}: svantaggio e niente incantesimi")
        if armor.get("str_req") and abilities["scores"]["str"] < armor["str_req"]:
            warnings.append(f"{armor['name']} richiede FOR {armor['str_req']}: velocità -3 m")
        if "defense" in styles:
            ac += 1
            parts.append("Difesa +1")
        armor_name = armor["name"]
        stealth_dis = armor.get("stealth_disadvantage", False)
    else:
        ac = 10 + dex
        parts.append(f"10 + DES {fmt_mod(dex)}")
        if cls["key"] == "barbarian":
            ac += abilities["mods"]["con"]
            parts.append(f"COS {fmt_mod(abilities['mods']['con'])}")
        elif cls["key"] == "monk":
            ac += abilities["mods"]["wis"]
            parts.append(f"SAG {fmt_mod(abilities['mods']['wis'])}")
        armor_name = "Nessuna armatura"
        stealth_dis = False
    if char.get("shield"):
        ac += armor_table["shield"]["bonus"]
        parts.append("Scudo +2")
    ac += int(char.get("ac_bonus", 0))
    return {"value": ac, "armor": armor_name, "shield": bool(char.get("shield")), "breakdown": ", ".join(parts), "stealth_disadvantage": stealth_dis}


def resolve_hp(char: dict, abilities: dict, cls: dict, race: dict, warnings: list) -> dict:
    spec = char.get("hp", {}) or {}
    method = spec.get("method", "average")
    level = cls["level"]
    con = abilities["mods"]["con"]
    die = cls["hit_die"]
    per_level_bonus = sum(t.get("hp_per_level", 0) for t in race["traits"])
    if method == "manual":
        total = int(spec["value"])
        detail = "valore inserito manualmente"
    else:
        first = die + con + per_level_bonus
        if method == "average":
            gains = [die // 2 + 1 + con + per_level_bonus] * (level - 1)
            detail = f"{die} + COS al 1° livello, poi {die // 2 + 1} + COS per livello"
        elif method == "rolled":
            rolls = list(spec.get("rolled", []))
            if len(rolls) != level - 1:
                raise RulesError(f"hp.rolled deve contenere {level - 1} tiri (uno per livello dal 2°)")
            gains = [int(r) + con + per_level_bonus for r in rolls]
            detail = f"{die} + COS al 1° livello, poi tiri {rolls} + COS"
        else:
            raise RulesError(f"Metodo PF sconosciuto: {method}")
        total = first + sum(max(1, g) for g in gains)
    return {"max": total, "hit_dice": f"{level}d{die}", "detail": detail}


# ---------------------------------------------------------------------------
# Scheda completa
# ---------------------------------------------------------------------------
def build_sheet(char: dict, rules: dict | None = None) -> dict:
    rules = rules or load_rules()
    warnings: list[str] = []
    skills_rules = rules["skills"]

    race = resolve_race(char, rules)
    cls = resolve_class(char, rules)
    background = resolve_background(char, rules)
    abilities = resolve_abilities(char, race, rules, warnings)
    level = cls["level"]
    prof = skills_rules["proficiency_bonus"][level - 1]
    xp = char.get("xp")
    if xp is None:
        xp = skills_rules["xp_thresholds"][level - 1]
    elif xp < skills_rules["xp_thresholds"][level - 1]:
        warnings.append(f"{xp} PE non bastano per il livello {level}")

    skills = resolve_skills(char, race, cls, background, rules, warnings)
    styles = list(char.get("fighting_styles", []) or [])
    if char.get("fighting_style"):
        styles.insert(0, char["fighting_style"])
    for s in styles:
        if s not in rules["equipment"]["fighting_styles"]:
            raise RulesError(f"Stile di combattimento sconosciuto: {s}")

    mods = abilities["mods"]
    saves = {}
    for a in ABILITIES:
        is_prof = a in cls["saves"]
        saves[a] = {"value": mods[a] + (prof if is_prof else 0), "proficient": is_prof}

    skill_values = {}
    for key, info in skills_rules["skills"].items():
        is_prof = key in skills["proficient"]
        bonus = mods[info["ability"]]
        if is_prof:
            bonus += prof * (2 if key in skills["expertise"] else 1)
        skill_values[key] = {
            "value": bonus, "proficient": is_prof, "expertise": key in skills["expertise"],
            "name": info["it"], "ability": info["ability"], "source": skills["proficient"].get(key),
        }
    passive_perception = 10 + skill_values["perception"]["value"]

    ac = resolve_ac(char, abilities, cls, styles, rules, warnings)
    hp = resolve_hp(char, abilities, cls, race, warnings)
    weapons = resolve_weapons(char, abilities, cls, race, prof, styles, rules)

    # --- privilegi e tratti ---
    features = []
    for t in race["traits"]:
        features.append({"name": t["name"], "short": t.get("short", ""), "text": t.get("text", ""), "source": race["name"]})
    for f in cls["features"]:
        features.append({"name": f["name"], "short": f.get("short", ""), "text": f.get("text", ""), "source": f["source"], "level": f["level"]})
    style_descriptions = []
    for s in styles:
        st = rules["equipment"]["fighting_styles"][s]
        style_descriptions.append({"name": f"Stile di Combattimento: {st['name']}", "short": st["text"], "text": st["text"], "source": cls["name"]})
    maneuvers = []
    for m in char.get("maneuvers", []) or []:
        if m not in rules["maneuvers"]:
            raise RulesError(f"Manovra sconosciuta: {m}")
        maneuvers.append(rules["maneuvers"][m])
    bg_feature = {"name": f"{background['feature']['name']} (background)", "short": background["feature"]["text"], "text": background["feature"]["text"], "source": background["name"]} if background.get("feature") else None

    # --- competenze e linguaggi ---
    armor_prof = [ARMOR_CATEGORY_NAMES[a] for a in cls["armor"] if a in ARMOR_CATEGORY_NAMES]
    for t in race["traits"]:
        armor_prof += [ARMOR_CATEGORY_NAMES[a] for a in t.get("armor_proficiencies", [])]
    weapon_prof = [WEAPON_CATEGORY_NAMES.get(w, rules["equipment"]["weapons"].get(w, {}).get("name", w).lower()) for w in cls["weapons"]]
    for t in race["traits"]:
        for w in t.get("weapon_proficiencies", []):
            name = rules["equipment"]["weapons"][w]["name"].lower()
            if name not in weapon_prof and "armi da guerra" not in weapon_prof:
                weapon_prof.append(name)
    bg_tools = char.get("background_tools")
    if bg_tools is None:
        bg_tools = background.get("tools", [])
    tools = list(cls["tools"]) + list(bg_tools) + list(char.get("tools", []) or [])
    for t in race["traits"]:
        tools += t.get("tool_proficiencies", [])
    lang_names = skills_rules["languages"]
    languages = [lang_names.get(l, l) for l in race["languages"]]
    extra_langs = list(char.get("languages_extra", []) or [])
    allowed_extra = race["extra_languages"] + int(background.get("languages", 0))
    if len(extra_langs) > allowed_extra:
        warnings.append(f"Linguaggi extra: scelti {len(extra_langs)}, consentiti {allowed_extra}")
    elif len(extra_langs) < allowed_extra:
        warnings.append(f"Linguaggi extra: puoi sceglierne ancora {allowed_extra - len(extra_langs)}")
    languages += [lang_names.get(l, l) for l in extra_langs]

    # --- equipaggiamento ---
    equipment = []
    for item in char.get("equipment", []) or []:
        if isinstance(item, dict) and "pack" in item:
            pack = rules["equipment"]["packs"][item["pack"]]
            equipment.append(f"{pack['name']}: {', '.join(pack['items'])}")
        else:
            equipment.append(str(item))
    if char.get("include_background_equipment", True):
        equipment += background.get("equipment", [])
    money = {k: char.get("money", {}).get(k, 0) for k in ("cp", "sp", "ep", "gp", "pp")}

    # --- incantesimi / trucchetti ---
    cantrips = []
    spell_ability = None
    for t in race["traits"]:
        if t.get("cantrip_choice"):
            spell_ability = t["cantrip_choice"]["ability"]
    if cls.get("spellcasting"):
        spell_ability = cls["spellcasting"]["ability"]
    if cls.get("subclass") and cls["subclass"].get("spellcasting"):
        spell_ability = cls["subclass"]["spellcasting"]["ability"]
    for c in char.get("cantrips", []) or []:
        table = rules["equipment"]["wizard_cantrips"]
        cantrips.append(table[c] if c in table else {"name": c, "text": ""})
    spellcasting = None
    if spell_ability and (cantrips or char.get("spells")):
        spellcasting = {
            "ability": spell_ability,
            "ability_name": skills_rules["abilities"][spell_ability]["it"],
            "save_dc": 8 + prof + mods[spell_ability],
            "attack_bonus": prof + mods[spell_ability],
        }

    alignment = char.get("alignment", "")
    alignment = skills_rules["alignments"].get(alignment, alignment)

    portrait = None
    if char.get("portrait"):
        portrait = Path(char["_dir"]) / char["portrait"]
        if not portrait.exists():
            warnings.append(f"Ritratto non trovato: {portrait}")
            portrait = None

    return {
        "name": char.get("name", ""),
        "player": char.get("player", ""),
        "race": race,
        "class": cls,
        "class_level": f"{cls['name']} {level}",
        "subclass_name": cls["subclass"]["name"] if cls["subclass"] else None,
        "level": level,
        "xp": xp,
        "background": background,
        "alignment": alignment,
        "abilities": abilities,
        "proficiency_bonus": prof,
        "saves": saves,
        "skills": skill_values,
        "passive_perception": passive_perception,
        "ac": ac,
        "initiative": mods["dex"] + int(char.get("initiative_bonus", 0)),
        "speed": race["speed"],
        "speed_m": f"{race['speed'] * 0.3:g} m",
        "hp": hp,
        "weapons": weapons,
        "features": features,
        "fighting_styles": style_descriptions,
        "maneuvers": maneuvers,
        "background_feature": bg_feature,
        "proficiencies": {"armor": armor_prof, "weapons": weapon_prof, "tools": tools},
        "languages": languages,
        "equipment": equipment,
        "money": money,
        "cantrips": cantrips,
        "spellcasting": spellcasting,
        "personality": char.get("personality", {}) or {},
        "appearance": char.get("appearance", {}) or {},
        "backstory": char.get("backstory", "") or "",
        "allies": char.get("allies", "") or "",
        "treasure": char.get("treasure", "") or "",
        "extra_features": char.get("extra_features", "") or "",
        "attacks_notes": char.get("attacks_notes", "") or "",
        "portrait": str(portrait) if portrait else None,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Riepilogo testuale (Markdown)
# ---------------------------------------------------------------------------
def sheet_markdown(sheet: dict) -> str:
    a = sheet["abilities"]
    lines = [f"# {sheet['name']}", ""]
    lines.append(f"**{sheet['race']['name']} {sheet['class_level']}**"
                 + (f" ({sheet['subclass_name']})" if sheet["subclass_name"] else "")
                 + f" · {sheet['background']['name']} · {sheet['alignment']} · {sheet['xp']} PE")
    lines += ["", "| Caratteristica | Punteggio | Mod. | TS |", "|---|---|---|---|"]
    names = {"str": "Forza", "dex": "Destrezza", "con": "Costituzione", "int": "Intelligenza", "wis": "Saggezza", "cha": "Carisma"}
    for k in ABILITIES:
        s = sheet["saves"][k]
        lines.append(f"| {names[k]} | {a['scores'][k]} | {fmt_mod(a['mods'][k])} | {fmt_mod(s['value'])}{' ●' if s['proficient'] else ''} |")
    lines += ["", f"- Bonus di competenza: {fmt_mod(sheet['proficiency_bonus'])}",
              f"- CA: {sheet['ac']['value']} ({sheet['ac']['breakdown']})",
              f"- Iniziativa: {fmt_mod(sheet['initiative'])} · Velocità: {sheet['speed_m']}",
              f"- PF massimi: {sheet['hp']['max']} ({sheet['hp']['detail']}) · Dadi vita: {sheet['hp']['hit_dice']}",
              f"- Percezione passiva: {sheet['passive_perception']}", ""]
    lines += ["## Abilità", ""]
    for k, s in sorted(sheet["skills"].items(), key=lambda kv: kv[1]["name"]):
        mark = " ● " + (s["source"] or "") if s["proficient"] else ""
        lines.append(f"- {s['name']} ({s['ability'].upper()}): {fmt_mod(s['value'])}{mark}")
    lines += ["", "## Attacchi", ""]
    for w in sheet["weapons"]:
        lines.append(f"- {w['name']}: {w['attack_str']} per colpire, {w['damage']}" + (f" ({', '.join(w['properties'])})" if w["properties"] else ""))
    lines += ["", "## Privilegi e tratti", ""]
    for f in sheet["features"] + sheet["fighting_styles"] + ([sheet["background_feature"]] if sheet["background_feature"] else []):
        lines.append(f"- **{f['name']}** ({f['source']}): {f['short']}")
    for m in sheet["maneuvers"]:
        lines.append(f"- **Manovra: {m['name']}**: {m['text']}")
    for c in sheet["cantrips"]:
        lines.append(f"- **Trucchetto: {c['name']}**: {c.get('text', '')}")
    p = sheet["proficiencies"]
    lines += ["", "## Competenze e linguaggi", "",
              f"- Armature: {', '.join(p['armor']) or '—'}",
              f"- Armi: {', '.join(p['weapons']) or '—'}",
              f"- Strumenti: {', '.join(p['tools']) or '—'}",
              f"- Linguaggi: {', '.join(sheet['languages'])}", "", "## Equipaggiamento", ""]
    lines += [f"- {e}" for e in sheet["equipment"]]
    money = ", ".join(f"{v} {k}" for k, v in sheet["money"].items() if v)
    lines.append(f"- Monete: {money or '—'}")
    if sheet["warnings"]:
        lines += ["", "## Avvisi", ""] + [f"- {w}" for w in sheet["warnings"]]
    return "\n".join(lines) + "\n"
