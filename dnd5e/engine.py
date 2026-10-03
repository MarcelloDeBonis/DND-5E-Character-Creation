"""Motore di regole: trasforma il YAML di un personaggio in una scheda calcolata.

L'output di `build_sheet` è un dizionario con tutti i valori derivati (modificatori,
tiri salvezza, abilità, CA, PF, attacchi, privilegi, incantesimi, Forma Selvatica...)
pronto per il renderer PDF o per un riepilogo testuale. Le regole sono lette dai
file YAML in `dnd5e/rules/`.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

import yaml

RULES_DIR = Path(__file__).parent / "rules"
ABILITIES = ["str", "dex", "con", "int", "wis", "cha"]
ABBR_IT = {"str": "FOR", "dex": "DES", "con": "COS", "int": "INT", "wis": "SAG", "cha": "CAR"}
MONEY_IT = {"cp": "mr", "sp": "ma", "ep": "me", "gp": "mo", "pp": "mp"}

ARMOR_CATEGORY_NAMES = {
    "light": "armature leggere",
    "medium": "armature medie",
    "heavy": "armature pesanti",
    "shields": "scudi",
}
WEAPON_CATEGORY_NAMES = {"simple": "armi semplici", "martial": "armi da guerra"}
PROPERTY_NAMES = {
    "finesse": "accurata", "light": "leggera", "heavy": "pesante", "two_handed": "a due mani",
    "versatile": "versatile", "thrown": "da lancio", "ammunition": "munizioni", "reach": "portata",
    "loading": "ricarica", "special": "speciale",
}


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


def fmt_cr(cr) -> str:
    return {0: "0", 0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}.get(cr, str(int(cr)) if float(cr).is_integer() else str(cr))


def _merge_bonus(target: dict, bonus: dict | None) -> None:
    for key, value in (bonus or {}).items():
        target[key] = target.get(key, 0) + value


def _as_list(value) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def is_female(char: dict) -> bool:
    return str(char.get("gender", "")).lower() in ("f", "femmina", "donna", "female")


def _nm(entry: dict, female: bool, default: str = "") -> str:
    """Nome italiano di una voce di regole, al femminile se richiesto e disponibile (`name_f`)."""
    if female and entry.get("name_f"):
        return entry["name_f"]
    return entry.get("name", default)


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def kid_fmt(text: str, values: dict) -> str:
    """Sostituisce i segnaposto ({cd}, {att}, {mod}, {soffio_cd}...) lasciando intatti quelli sconosciuti."""
    try:
        return str(text or "").format_map(_SafeDict(values))
    except (ValueError, IndexError):
        return str(text or "")


# ---------------------------------------------------------------------------
# Razza
# ---------------------------------------------------------------------------
def resolve_race(char: dict, rules: dict) -> dict:
    races = rules["races"]
    race_key = char["race"]
    if race_key not in races:
        raise RulesError(f"Razza sconosciuta: {race_key}")
    race = copy.deepcopy(races[race_key])
    female = is_female(char)
    result = {
        "key": race_key,
        "name": _nm(race, female),
        "name_en": race.get("name_en", race["name"]),
        "size": race.get("size", "Medio"),
        "speed": race.get("speed", 30),
        "ability_bonus": dict(race.get("ability_bonus", {})),
        "ability_choice": race.get("ability_choice"),
        "languages": list(race.get("languages", [])),
        "extra_languages": race.get("extra_languages", 0),
        "traits": list(race.get("traits", [])),
        "age": race.get("age", ""),
        "heavy_armor_no_speed_penalty": race.get("heavy_armor_no_speed_penalty", False),
    }
    sub_key = char.get("subrace")
    subraces = race.get("subraces", {}) or {}
    variants = race.get("variants", {}) or {}
    pools = {**subraces, **variants}
    if sub_key:
        if sub_key not in pools:
            raise RulesError(f"Sottorazza o variante sconosciuta per {race_key}: {sub_key}")
        sub = pools[sub_key]
        result["name"] = _nm(sub, female, result["name"])
        result["name_en"] = sub.get("name_en", result["name_en"])
        if sub.get("replaces_base_bonus"):
            result["ability_bonus"] = {}
        _merge_bonus(result["ability_bonus"], sub.get("ability_bonus", {}))
        if "ability_choice" in sub:
            result["ability_choice"] = sub["ability_choice"]
        if "speed" in sub:
            result["speed"] = sub["speed"]
        if sub.get("replaces_traits"):
            result["traits"] = []
            result["extra_languages"] = 0
        result["traits"] += sub.get("traits", [])
        result["extra_languages"] += sub.get("extra_languages", 0)
    elif subraces:  # le sottorazze sono obbligatorie, le varianti (umano variante) no
        raise RulesError(f"La razza {race_key} richiede una sottorazza tra: {', '.join(subraces)}")
    for trait in result["traits"]:
        result["extra_languages"] += trait.get("extra_languages", 0)
    result["ancestry"] = None
    if race.get("ancestry"):
        anc_key = char.get("draconic_ancestry")
        if anc_key not in race["ancestry"]:
            raise RulesError(f"La razza {result['name']} richiede 'draconic_ancestry' tra: {', '.join(race['ancestry'])}")
        anc = race["ancestry"][anc_key]
        result["ancestry"] = {"key": anc_key, **anc}
        result["name"] += f" (drago {anc['name'].lower()})"
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
        if total > budget:
            raise RulesError(f"Point buy: spesi {total} punti, il massimo è {budget}")
        if total < budget:
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
        picks = _as_list(spec.get("racial_choice"))
        if len(picks) != choice["count"] or len(set(picks)) != choice["count"]:
            raise RulesError(
                f"La razza richiede {choice['count']} caratteristiche diverse in 'abilities.racial_choice'"
            )
        for k in picks:
            if k not in ABILITIES:
                raise RulesError(f"Caratteristica sconosciuta in racial_choice: {k}")
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
    spellcasting = cls.get("spellcasting")
    if subclass and subclass.get("spellcasting"):
        spellcasting = subclass["spellcasting"]
    return {
        "key": key,
        "name": _nm(cls, is_female(char)),
        "name_en": cls.get("name_en", cls["name"]),
        "level": level,
        "hit_die": cls["hit_die"],
        "saves": cls["saves"],
        "armor": cls.get("armor", []),
        "no_metal_armor": cls.get("no_metal_armor", False),
        "weapons": cls.get("weapons", []),
        "tools": cls.get("tools", []),
        "skill_choices": cls.get("skill_choices", {"count": 0, "from": []}),
        "spellcasting": spellcasting,
        "subclass_label": cls.get("subclass_label"),
        "subclass": subclass,
        "subclass_key": sub_key,
        "features": features,
        "wild_shape": (subclass or {}).get("wild_shape") or cls.get("wild_shape"),
    }


# ---------------------------------------------------------------------------
# Background, competenze e abilità
# ---------------------------------------------------------------------------
def resolve_background(char: dict, rules: dict) -> dict:
    key = char.get("background")
    if isinstance(key, dict):  # background personalizzato definito nel file
        bg = copy.deepcopy(key)
    else:
        if key not in rules["backgrounds"]:
            raise RulesError(f"Background sconosciuto: {key}")
        bg = copy.deepcopy(rules["backgrounds"][key])
    bg["name"] = _nm(bg, is_female(char), str(key))
    bg.setdefault("skills", [])
    bg.setdefault("tools", [])
    bg.setdefault("languages", 0)
    bg.setdefault("equipment", [])
    bg.setdefault("gold", 0)
    if char.get("background_skills") is not None:
        picks = _as_list(char["background_skills"])
        if len(picks) != len(bg["skills"]):
            raise RulesError(f"background_skills deve contenere {len(bg['skills'])} abilità")
        bg["skills"] = picks
    if char.get("background_tools") is not None:
        bg["tools"] = _as_list(char["background_tools"])
    return bg


def resolve_skills(char: dict, race: dict, cls: dict, background: dict, rules: dict, warnings: list) -> dict:
    all_skills = rules["skills"]["skills"]
    proficient = {}

    def add(skill, source):
        if skill not in all_skills:
            raise RulesError(f"Abilità sconosciuta: {skill}")
        if skill in proficient:
            warnings.append(
                f"Abilità {all_skills[skill]['it']} data due volte ({proficient[skill]} e {source}): "
                "per le regole puoi sostituirne una con un'altra abilità a scelta"
            )
            return
        proficient[skill] = source

    choices = _as_list(char.get("skills"))
    pool = cls["skill_choices"]
    if len(choices) != pool["count"] or len(set(choices)) != len(choices):
        raise RulesError(
            f"La classe {cls['name']} richiede {pool['count']} abilità diverse in 'skills' (date: {len(choices)})"
        )
    for s in choices:
        if pool["from"] and s not in pool["from"]:
            raise RulesError(f"{s} non è tra le abilità di classe di {cls['name']}")
        add(s, f"classe ({cls['name']})")
    for s in background["skills"]:
        add(s, f"background ({background['name']})")
    racial_choice_count = 0
    for trait in race["traits"]:
        for s in trait.get("skills", []):
            add(s, f"razza ({trait['name']})")
        racial_choice_count += int(trait.get("skill_choice", 0))
    racial_picks = _as_list(char.get("racial_skills"))
    if len(racial_picks) != racial_choice_count:
        raise RulesError(
            f"La razza concede {racial_choice_count} abilità a scelta: indicale in 'racial_skills' (date: {len(racial_picks)})"
        )
    for s in racial_picks:
        add(s, f"razza ({race['name']})")
    for s in _as_list(char.get("extra_skills")):
        add(s, "altro")
    expertise = set(_as_list(char.get("expertise")))
    for s in expertise:
        if s not in proficient:
            raise RulesError(f"Maestria in {s} ma nessuna competenza")
    return {"proficient": proficient, "expertise": expertise}


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
    for entry in _as_list(char.get("weapons")):
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
        elif ranged:
            ability = "dex"
        else:
            ability = "str"
        ability = weapon.get("ability", ability)
        amod = mods[ability]
        proficient = weapon.get("proficient")
        if proficient is None:
            proficient = _weapon_proficient(wkey, weapon, cls, race) if wkey else True
        magic = int(weapon.get("magic_bonus", 0))
        atk = amod + (prof if proficient else 0) + magic
        base_dmg_bonus = amod + magic
        one_hand_bonus = base_dmg_bonus
        notes = []
        if ranged and "archery" in styles:
            atk += 2
            notes.append("Tiro +2")
        if not ranged and "dueling" in styles and "two_handed" not in props:
            one_hand_bonus += 2
            notes.append("Duello +2 danni se usata in una mano senza altre armi")
        dice = weapon.get("damage", "")
        dmg = f"{dice}{fmt_mod(one_hand_bonus)}" if dice and dice[0].isdigit() else dice
        if weapon.get("versatile"):
            dmg += f" ({weapon['versatile']}{fmt_mod(base_dmg_bonus)} a 2 mani)"
        dmg_type = weapon.get("damage_type", "")
        extra = []
        if weapon.get("range"):
            extra.append(f"gittata {weapon['range']} m")
        extra += [PROPERTY_NAMES.get(p, p) for p in props if p != "versatile"]
        if not proficient:
            notes.append("senza competenza")
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


def resolve_ac(char: dict, abilities: dict, cls: dict, race: dict, styles: list, rules: dict, warnings: list) -> dict:
    armor_table = rules["equipment"]["armor"]
    dex = abilities["mods"]["dex"]
    armor_key = char.get("armor")
    armor_profs = set(cls["armor"])
    for t in race["traits"]:
        armor_profs.update(t.get("armor_proficiencies", []))
    parts = []
    shield = char.get("shield")
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
        if armor["category"] not in armor_profs:
            warnings.append(f"Nessuna competenza in {ARMOR_CATEGORY_NAMES[armor['category']]}: svantaggio a prove, TS e attacchi su FOR/DES e niente incantesimi")
        if armor.get("str_req") and abilities["scores"]["str"] < armor["str_req"] and not race.get("heavy_armor_no_speed_penalty"):
            warnings.append(f"{armor['name']} richiede FOR {armor['str_req']}: velocità -3 m")
        if cls.get("no_metal_armor") and armor.get("metal"):
            warnings.append(f"{armor['name']} è di metallo: un druido non la indossa")
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
        elif cls["key"] == "monk" and not shield:
            ac += abilities["mods"]["wis"]
            parts.append(f"SAG {fmt_mod(abilities['mods']['wis'])}")
        armor_name = "Nessuna armatura"
        stealth_dis = False
    if shield:
        ac += armor_table["shield"]["bonus"]
        shield_name = shield if isinstance(shield, str) else armor_table["shield"]["name"]
        parts.append(f"{shield_name} +2")
        if "shields" not in armor_profs:
            warnings.append("Nessuna competenza negli scudi: svantaggio a prove, TS e attacchi su FOR/DES e niente incantesimi")
    ac += int(char.get("ac_bonus", 0))
    return {"value": ac, "armor": armor_name, "shield": bool(shield), "breakdown": ", ".join(parts), "stealth_disadvantage": stealth_dis}


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
            rolls = [int(r) for r in _as_list(spec.get("rolled"))]
            if len(rolls) != level - 1:
                raise RulesError(f"hp.rolled deve contenere {level - 1} tiri (uno per livello dal 2°)")
            for r in rolls:
                if not 1 <= r <= die:
                    raise RulesError(f"hp.rolled: {r} non è un risultato possibile di 1d{die}")
            gains = [r + con + per_level_bonus for r in rolls]
            detail = f"{die} + COS al 1° livello, poi tiri {rolls} + COS"
        else:
            raise RulesError(f"Metodo PF sconosciuto: {method}")
        total = first + sum(max(1, g) for g in gains)
    return {"max": total, "hit_dice": f"{level}d{die}", "detail": detail}


# ---------------------------------------------------------------------------
# Incantesimi
# ---------------------------------------------------------------------------
def _scale_cantrip(dice: str, level: int) -> str:
    m = re.match(r"(\d+)d(\d+)", dice or "")
    if not m:
        return dice
    n = int(m.group(1)) * (1 + (level >= 5) + (level >= 11) + (level >= 17))
    return f"{n}d{m.group(2)}"


def resolve_spellcasting(char: dict, cls: dict, race: dict, abilities: dict, prof: int, rules: dict, warnings: list) -> dict | None:
    spells_rules = rules["spells"]
    table = spells_rules["spells"]
    mods = abilities["mods"]
    level = cls["level"]
    names = rules["skills"]["abilities"]

    def lookup(key, source):
        if key in table:
            return {"key": key, **copy.deepcopy(table[key]), "source": source}
        return {"key": key, "name": str(key), "level": None, "lists": [], "text": "", "source": source}

    cantrips = []
    innate_ability = None
    for t in race["traits"]:
        for key in t.get("fixed_cantrips", []):
            cantrips.append({**lookup(key, t["name"]), "ability": t.get("innate_ability")})
        if t.get("innate_ability"):
            innate_ability = t["innate_ability"]
        if t.get("cantrip_choice"):
            innate_ability = t["cantrip_choice"]["ability"]
            picks = _as_list(char.get("racial_cantrips"))
            if len(picks) != 1:
                raise RulesError(f"Il tratto {t['name']} richiede un trucchetto in 'racial_cantrips'")
            for key in picks:
                sp = lookup(key, race["name"])
                if sp["level"] is None or t["cantrip_choice"]["list"] not in sp["lists"] or sp["level"] != 0:
                    raise RulesError(f"{key} non è un trucchetto della lista {t['cantrip_choice']['list']}")
                cantrips.append({**sp, "ability": innate_ability})
    racial_cantrips = list(cantrips)

    caster = cls.get("spellcasting")
    class_cantrips = []
    prepared = []
    slots = {}
    prepared_max = None
    circle_spells = []
    spell_ability = innate_ability
    if caster:
        spell_ability = caster["ability"]
        list_key = caster.get("list", cls["key"])
        known_table = spells_rules["cantrips_known"].get(cls["key"]) or spells_rules["cantrips_known"].get(caster["type"])
        bonus = sum(int(f.get("cantrip_bonus", 0)) for f in cls["features"])
        expected = (known_table[level - 1] if known_table else None)
        picks = _as_list(char.get("cantrips"))
        for key in picks:
            sp = lookup(key, cls["name"])
            if sp["level"] is None:
                warnings.append(f"Trucchetto {key} non presente nei dati: aggiungilo a dnd5e/rules/spells.yaml")
            elif sp["level"] != 0 or list_key not in sp["lists"]:
                raise RulesError(f"{sp['name']} non è un trucchetto della lista del {cls['name']}")
            class_cantrips.append({**sp, "ability": spell_ability})
        if expected is not None and len(picks) != expected + bonus:
            warnings.append(f"Trucchetti di classe: scelti {len(picks)}, al livello {level} ne conosci {expected + bonus}")
        # trucchetti gratuiti dati da un privilegio (es. Illusione Minore Migliorata), fuori dal conteggio
        for f in cls["features"]:
            key = f.get("grants_cantrip")
            if key and key not in picks and key not in [c["key"] for c in cantrips]:
                class_cantrips.append({**lookup(key, f["name"]), "ability": spell_ability})
        slot_row = spells_rules["slots"][caster["type"]].get(level, []) if caster["type"] in spells_rules["slots"] else []
        slots = {i + 1: n for i, n in enumerate(slot_row) if n}
        max_level = max(slots) if slots else 0
        book = []
        if caster.get("spellbook"):
            book_keys = _as_list(char.get("spellbook"))
            expected_book = 6 + 2 * (level - 1)
            if len(book_keys) != expected_book:
                warnings.append(f"Libro degli incantesimi: {len(book_keys)} incantesimi, al livello {level} ne hai {expected_book} (senza contare quelli copiati)")
            for key in _as_list(char.get("spells")):
                if key not in book_keys:
                    raise RulesError(f"{key} è preparato ma non è nel libro degli incantesimi ('spellbook')")
            for key in book_keys:
                sp = lookup(key, cls["name"])
                if sp["level"] is None:
                    warnings.append(f"Incantesimo {key} non presente nei dati: aggiungilo a dnd5e/rules/spells.yaml")
                elif list_key not in sp["lists"]:
                    raise RulesError(f"{sp['name']} non è nella lista del {cls['name']}")
                elif sp["level"] > max_level:
                    raise RulesError(f"{sp['name']} è di {sp['level']}° livello ma hai slot solo fino al {max_level}°")
                sp["prepared"] = key in _as_list(char.get("spells"))
                book.append(sp)
        for key in _as_list(char.get("spells")):
            sp = lookup(key, cls["name"])
            if sp["level"] is None:
                warnings.append(f"Incantesimo {key} non presente nei dati: aggiungilo a dnd5e/rules/spells.yaml")
            else:
                if list_key not in sp["lists"]:
                    raise RulesError(f"{sp['name']} non è nella lista del {cls['name']}")
                if sp["level"] > max_level:
                    raise RulesError(f"{sp['name']} è di {sp['level']}° livello ma hai slot solo fino al {max_level}°")
            prepared.append(sp)
        if caster.get("prepared") == "ability_plus_level":
            prepared_max = max(1, mods[spell_ability] + (level if caster["type"] == "full" else level // 2))
            if len(prepared) != prepared_max:
                warnings.append(f"Incantesimi preparati: {len(prepared)} su {prepared_max} possibili")
        sub = cls.get("subclass") or {}
        if sub.get("circle_spells"):
            terrain = char.get("circle_terrain")
            if terrain not in sub["circle_spells"]:
                raise RulesError(f"Il {sub['name']} richiede 'circle_terrain' tra: {', '.join(sub['circle_spells'])}")
            for lvl in sorted(sub["circle_spells"][terrain]):
                if lvl <= level:
                    circle_spells += [{"name": n, "level": (lvl + 1) // 2, "text": "", "source": f"{sub['name']} ({terrain})", "always_prepared": True} for n in sub["circle_spells"][terrain][lvl]]
            circle_names = {c["name"] for c in circle_spells}
            for sp in prepared:
                if sp["name"] in circle_names:
                    warnings.append(f"{sp['name']} è già un incantesimo del circolo (sempre preparato): scegline un altro in 'spells'")
    if not spell_ability:
        return None
    all_cantrips = racial_cantrips + class_cantrips
    if not (all_cantrips or prepared or circle_spells):
        return None
    attack_bonus = prof + mods[spell_ability]
    # ogni trucchetto/incantesimo porta la propria caratteristica (razziale o di classe)
    for sp in all_cantrips + prepared + book:
        ab = sp.get("ability") or spell_ability
        sp["ability"] = ab
        sp["attack_bonus"] = prof + mods[ab]
        sp["save_dc"] = 8 + prof + mods[ab]
        sp["other_ability"] = ab != spell_ability
    spell_attacks = []
    for sp in all_cantrips + prepared:
        if sp.get("attack") and sp.get("damage"):
            dmg = _scale_cantrip(sp["damage"], level) if sp["level"] == 0 else sp["damage"]
            spell_attacks.append({"name": sp["name"], "attack_str": fmt_mod(sp["attack_bonus"]), "damage": f"{dmg} {sp.get('damage_type', '')}".strip(), "range": sp.get("range")})
    by_level: dict[int, list] = {}
    for sp in (book or prepared) + circle_spells:
        by_level.setdefault(sp["level"] or 1, []).append(sp)
    return {
        "ability": spell_ability,
        "ability_name": names[spell_ability]["it"],
        "save_dc": 8 + attack_bonus,
        "attack_bonus": attack_bonus,
        "cantrips": all_cantrips,
        "spells_by_level": by_level,
        "slots": slots,
        "prepared_max": prepared_max,
        "prepares": bool(caster and caster.get("prepared")),
        "ritual": bool(caster and caster.get("ritual")),
        "focus": caster.get("focus") if caster else None,
        "spell_attacks": spell_attacks,
        "class_caster": bool(caster),
        "list": (caster or {}).get("list", cls["key"]) if caster else None,
        "spellbook": bool(book),
        "prepared": prepared,
        "max_level": max(slots) if slots else 0,
        "mod": mods[spell_ability],
    }


# ---------------------------------------------------------------------------
# Forma Selvatica
# ---------------------------------------------------------------------------
def resolve_wild_shape(cls: dict, rules: dict) -> dict | None:
    table = cls.get("wild_shape")
    if not table:
        return None
    level = cls["level"]
    applicable = [lvl for lvl in table if lvl <= level]
    if not applicable:
        return None
    row = table[max(applicable)]
    max_cr = row["cr"]
    if isinstance(max_cr, str):  # es. "level/3"
        max_cr = level // 3
    forms = []
    for key, b in rules["beasts"].items():
        if b["cr"] > max_cr:
            continue
        if not row.get("fly") and b["speed"].get("fly"):
            continue
        if not row.get("swim") and b["speed"].get("swim"):
            continue
        forms.append({"key": key, **b})
    forms.sort(key=lambda b: (-b["cr"], b["name"]))
    uses = row.get("uses", 2)
    return {"max_cr": max_cr, "max_cr_str": fmt_cr(max_cr), "fly": row.get("fly", False), "swim": row.get("swim", False),
            "uses": "illimitati" if uses is None else uses, "duration_hours": max(1, level // 2), "forms": forms}


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
    styles = _as_list(char.get("fighting_styles"))
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

    ac = resolve_ac(char, abilities, cls, race, styles, rules, warnings)
    hp = resolve_hp(char, abilities, cls, race, warnings)
    weapons = resolve_weapons(char, abilities, cls, race, prof, styles, rules)
    spellcasting = resolve_spellcasting(char, cls, race, abilities, prof, rules, warnings)
    wild_shape = resolve_wild_shape(cls, rules)

    # --- arma a soffio (dragonide) ---
    breath = None
    anc = race.get("ancestry")
    if anc:
        dice = "2d6" if level < 6 else "3d6" if level < 11 else "4d6" if level < 16 else "5d6"
        breath = {"dc": 8 + mods["con"] + prof, "dice": dice, "type": anc["damage_type"], "area": anc["area"],
                  "save": anc["save"], "save_name": skills_rules["abilities"][anc["save"]]["it"]}

    # --- segnaposto per i testi semplici ---
    placeholders = {"livello": level, "forma_ore": wild_shape["duration_hours"] if wild_shape else ""}
    if spellcasting:
        placeholders.update(cd=spellcasting["save_dc"], att=fmt_mod(spellcasting["attack_bonus"]), mod=fmt_mod(spellcasting["mod"]))
    if breath:
        placeholders.update(soffio_cd=breath["dc"], soffio_danni=breath["dice"], soffio_tipo=breath["type"],
                            soffio_area=breath["area"], soffio_ts=breath["save_name"])

    # --- privilegi e tratti ---
    features = []
    for t in race["traits"]:
        features.append({"name": t["name"], "short": t.get("short", ""), "text": t.get("text", ""), "source": race["name"],
                         "kid": kid_fmt(t.get("kid", ""), placeholders), "kid_hide": t.get("kid_hide", False)})
    for f in cls["features"]:
        features.append({"name": f["name"], "short": f.get("short", ""), "text": f.get("text", ""), "source": f["source"], "level": f["level"],
                         "kid": kid_fmt(f.get("kid", ""), placeholders), "kid_hide": f.get("kid_hide", False)})
    style_descriptions = []
    for s in styles:
        st = rules["equipment"]["fighting_styles"][s]
        style_descriptions.append({"name": f"Stile di Combattimento: {st['name']}", "short": st["text"], "text": st["text"], "source": cls["name"]})
    maneuvers = []
    for m in _as_list(char.get("maneuvers")):
        if m not in rules["maneuvers"]:
            raise RulesError(f"Manovra sconosciuta: {m}")
        maneuvers.append(rules["maneuvers"][m])
    bg_feature = None
    if background.get("feature"):
        bg_feature = {"name": f"{background['feature']['name']} (background)", "short": background["feature"]["text"], "text": background["feature"]["text"],
                      "source": background["name"], "kid": kid_fmt(background["feature"].get("kid", ""), placeholders), "kid_hide": False}

    # --- competenze e linguaggi ---
    armor_prof = [ARMOR_CATEGORY_NAMES[a] for a in cls["armor"] if a in ARMOR_CATEGORY_NAMES]
    if cls.get("no_metal_armor") and armor_prof:
        armor_prof[-1] += " (non di metallo)"
    for t in race["traits"]:
        armor_prof += [ARMOR_CATEGORY_NAMES[a] for a in t.get("armor_proficiencies", []) if ARMOR_CATEGORY_NAMES[a] not in armor_prof]
    weapon_prof = [WEAPON_CATEGORY_NAMES.get(w, rules["equipment"]["weapons"].get(w, {}).get("name", w).lower()) for w in cls["weapons"]]
    for t in race["traits"]:
        for w in t.get("weapon_proficiencies", []):
            name = rules["equipment"]["weapons"][w]["name"].lower()
            if name not in weapon_prof and "armi da guerra" not in weapon_prof:
                weapon_prof.append(name)
    tools = list(cls["tools"]) + list(background["tools"]) + _as_list(char.get("tools"))
    tool_choices = sum(int(t.get("tool_choice", 0)) for t in race["traits"]) + sum(int(f.get("tool_choice", 0)) for f in cls["features"])
    for t in race["traits"]:
        tools += t.get("tool_proficiencies", [])
    if tool_choices and len(_as_list(char.get("tools"))) < tool_choices:
        warnings.append(f"Hai {tool_choices} competenza/e in strumenti a scelta non indicate in 'tools'")
    lang_names = skills_rules["languages"]
    languages = [lang_names.get(l, l) for l in race["languages"]]
    extra_langs = _as_list(char.get("languages_extra"))
    allowed_extra = race["extra_languages"] + int(background.get("languages", 0))
    if len(extra_langs) > allowed_extra:
        warnings.append(f"Linguaggi extra: scelti {len(extra_langs)}, consentiti {allowed_extra}")
    elif len(extra_langs) < allowed_extra:
        warnings.append(f"Linguaggi extra: puoi sceglierne ancora {allowed_extra - len(extra_langs)}")
    languages += [lang_names.get(l, l) for l in extra_langs]
    if cls["key"] == "druid":
        languages.append(lang_names["druidic"])
    if cls["key"] == "rogue":
        languages.append(lang_names["thieves_cant"])

    # --- equipaggiamento ---
    equipment = []
    for item in _as_list(char.get("equipment")):
        if isinstance(item, dict) and "pack" in item:
            pack = rules["equipment"]["packs"][item["pack"]]
            equipment.append(f"{pack['name']}: {', '.join(pack['items'])}")
        else:
            equipment.append(str(item))
    if char.get("include_background_equipment", True):
        equipment += background.get("equipment", [])
    money = {k: (char.get("money") or {}).get(k, 0) for k in ("cp", "sp", "ep", "gp", "pp")}

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
        "spellcasting": spellcasting,
        "cantrips": spellcasting["cantrips"] if spellcasting else [],
        "wild_shape": wild_shape,
        "personality": char.get("personality", {}) or {},
        "appearance": char.get("appearance", {}) or {},
        "backstory": char.get("backstory", "") or "",
        "allies": char.get("allies", "") or "",
        "treasure": char.get("treasure", "") or "",
        "extra_features": char.get("extra_features", "") or "",
        "attacks_notes": char.get("attacks_notes", "") or "",
        "portrait": str(portrait) if portrait else None,
        "breath": breath,
        "mage_armor_ac": (13 + mods["dex"]) if (not char.get("armor") and spellcasting
                                                and any(s.get("key") == "mage_armor" for s in spellcasting["prepared"])) else None,
        "placeholders": placeholders,
        "female": is_female(char),
        "simple": bool(char.get("simple")),
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
              f"- Percezione passiva: {sheet['passive_perception']}"]
    if sheet.get("mage_armor_ac"):
        lines.append(f"- CA con Armatura Magica: {sheet['mage_armor_ac']}")
    b = sheet.get("breath")
    if b:
        lines.append(f"- Arma a soffio: {b['area']}, TS {b['save_name']} CD {b['dc']}, {b['dice']} {b['type']} (metà se supera), 1 volta per riposo breve o lungo")
    lines.append("")
    lines += ["## Abilità", ""]
    for k, s in sorted(sheet["skills"].items(), key=lambda kv: kv[1]["name"]):
        mark = " ● " + (s["source"] or "") if s["proficient"] else ""
        lines.append(f"- {s['name']} ({ABBR_IT[s['ability']]}): {fmt_mod(s['value'])}{mark}")
    lines += ["", "## Attacchi", ""]
    for w in sheet["weapons"]:
        lines.append(f"- {w['name']}: {w['attack_str']} per colpire, {w['damage']}" + (f" ({', '.join(w['properties'] + w['notes'])})" if w["properties"] or w["notes"] else ""))
    sp = sheet["spellcasting"]
    if sp:
        for at in sp["spell_attacks"]:
            lines.append(f"- {at['name']} (incantesimo): {at['attack_str']} per colpire, {at['damage']}, gittata {at['range']} m")
        lines += ["", "## Incantesimi", "",
                  f"- Caratteristica: {sp['ability_name']} · CD tiro salvezza {sp['save_dc']} · attacco con incantesimo {fmt_mod(sp['attack_bonus'])}"]
        if sp["slots"]:
            lines.append("- Slot: " + ", ".join(f"{n} di {lvl}°" for lvl, n in sp["slots"].items()))
        if sp["prepared_max"]:
            lines.append(f"- Incantesimi preparabili: {sp['prepared_max']}")
        lines.append("- Trucchetti: " + ", ".join(f"{c['name']} ({c['source']}" + (f", {ABBR_IT[c['ability']]}: CD {c['save_dc']}, attacco {fmt_mod(c['attack_bonus'])}" if c.get("other_ability") else "") + ")" for c in sp["cantrips"]))
        for lvl in sorted(sp["spells_by_level"]):
            lines.append(f"- {lvl}° livello: " + ", ".join(s["name"] + (" (C)" if s.get("conc") else "") + (" (R)" if s.get("ritual") else "")
                                                       + (" [nel libro, non preparato]" if s.get("prepared") is False else "") for s in sp["spells_by_level"][lvl]))
    ws = sheet["wild_shape"]
    if ws:
        lines += ["", "## Forma Selvatica", "",
                  f"- GS massimo {ws['max_cr_str']}, volo {'sì' if ws['fly'] else 'no'}, nuoto {'sì' if ws['swim'] else 'no'}; {ws['uses']} usi per riposo; durata {ws['duration_hours']} ora/e",
                  "- Forme disponibili: " + ", ".join(f"{b['name']} (GS {fmt_cr(b['cr'])})" for b in ws["forms"])]
    lines += ["", "## Privilegi e tratti", ""]
    for f in sheet["features"] + sheet["fighting_styles"] + ([sheet["background_feature"]] if sheet["background_feature"] else []):
        lines.append(f"- **{f['name']}** ({f['source']}): {f['short']}")
    for m in sheet["maneuvers"]:
        lines.append(f"- **Manovra: {m['name']}**: {m['text']}")
    p = sheet["proficiencies"]
    lines += ["", "## Competenze e linguaggi", "",
              f"- Armature: {', '.join(p['armor']) or '—'}",
              f"- Armi: {', '.join(p['weapons']) or '—'}",
              f"- Strumenti: {', '.join(p['tools']) or '—'}",
              f"- Linguaggi: {', '.join(sheet['languages'])}", "", "## Equipaggiamento", ""]
    lines += [f"- {e}" for e in sheet["equipment"]]
    money = ", ".join(f"{v} {MONEY_IT[k]}" for k, v in sheet["money"].items() if v)
    lines.append(f"- Monete: {money or '—'}")
    if sheet["warnings"]:
        lines += ["", "## Avvisi", ""] + [f"- {w}" for w in sheet["warnings"]]
    return "\n".join(lines) + "\n"
