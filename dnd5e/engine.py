"""Motore di regole: trasforma il YAML di un personaggio in una scheda calcolata.

L'output di `build_sheet` è un dizionario con tutti i valori derivati (modificatori,
tiri salvezza, abilità, CA, PF, attacchi, privilegi, incantesimi, Forma Selvatica...)
pronto per il renderer PDF o per un riepilogo testuale. Le regole sono lette dai
file YAML in `dnd5e/rules/`.
"""
from __future__ import annotations

import copy
import math
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
# nomi degli strumenti citati per chiave (se equipment.yaml non ha ancora la tabella `tools`)
DEFAULT_TOOL_NAMES = {"thieves_tools": "Arnesi da scasso"}
# etichetta degli incantesimi sempre preparati, se la classe non ha `always_prepared_tag`
DEFAULT_PREPARED_TAG = {"cleric": "dominio", "paladin": "giuramento", "druid": "circolo"}
# come si usano gli incantesimi dati da un'opzione di classe (`spell_uses`)
SPELL_USES_TAGS = {"at_will": "a volontà", "long_rest_slot": "1 per riposo lungo, con uno slot", "ritual": "solo rituale"}
# Arti Marziali del monaco, se monk.yaml non ha ancora il blocco `martial_arts`
DEFAULT_MARTIAL_ARTS = {"die_column": "martial_arts", "weapons": ["shortsword"], "simple_melee": True,
                        "exclude_properties": ["two_handed", "heavy"], "requires_unarmored": True}
SIZE_ORDER = ["minusc", "picc", "medi", "grand", "enorm", "mastod"]
NUMBER_WORDS = {"un": 1, "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4}
PLACEHOLDER_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")


class RulesError(ValueError):
    """Errore nei dati del personaggio rispetto alle regole."""


def load_rules() -> dict:
    rules = {}
    for path in sorted(RULES_DIR.glob("*.yaml")):
        rules[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    # cartelle con un file per voce (es. rules/classes/wizard.yaml): unite in rules["classes"]
    for folder in sorted(p for p in RULES_DIR.iterdir() if p.is_dir()):
        merged = rules.setdefault(folder.name, {})
        for path in sorted(folder.glob("*.yaml")):
            merged.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
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


def fmt_bonus(value: int) -> str:
    """Come fmt_mod, ma un modificatore pari a zero non si scrive (1d8, non 1d8+0)."""
    return "" if not value else fmt_mod(value)


def fmt_cr(cr) -> str:
    return {0: "0", 0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}.get(cr, str(int(cr)) if float(cr).is_integer() else str(cr))


def _dice_with_mod(dice: str, mod: int) -> str:
    dice = str(dice or "")
    return f"{dice}{fmt_bonus(mod)}" if dice[:1].isdigit() else dice


def _die_max(dice) -> int:
    m = re.match(r"(\d+)d(\d+)", str(dice or ""))
    return int(m.group(1)) * int(m.group(2)) if m else 0


def _add_to_damage(damage: str, bonus: int) -> str:
    """'1d6+2' + 4 -> '1d6+6'; '1' + 4 -> '5'; altri testi restano uguali."""
    s = str(damage or "").strip()
    m = re.fullmatch(r"(\d+d\d+)\s*([+-]\s*\d+)?", s)
    if m:
        base = int(m.group(2).replace(" ", "")) if m.group(2) else 0
        return f"{m.group(1)}{fmt_bonus(base + bonus)}"
    if re.fullmatch(r"\d+", s):
        return str(int(s) + bonus)
    return s


def _merge_bonus(target: dict, bonus: dict | None) -> None:
    for key, value in (bonus or {}).items():
        if key in ABILITIES:
            target[key] = target.get(key, 0) + value


def _as_list(value) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _pick_key(entry) -> str:
    return entry.get("key") if isinstance(entry, dict) else entry


def _check_duplicates(picks: list, label: str) -> None:
    seen = set()
    for p in picks:
        k = _pick_key(p)
        if k in seen:
            raise RulesError(f"{label}: '{k}' è scritto due volte")
        seen.add(k)


def is_female(char: dict) -> bool:
    return str(char.get("gender", "")).lower() in ("f", "femmina", "donna", "female")


def gender_values(female: bool) -> dict:
    """Segnaposto di genere per i testi semplici: brav{o}, {un_amico}, {amici}."""
    return {"o": "a" if female else "o", "un_amico": "un'amica" if female else "un amico",
            "amici": "amiche" if female else "amici"}


def _nm(entry: dict, female: bool, default: str = "") -> str:
    """Nome italiano di una voce di regole, al femminile se richiesto e disponibile (`name_f`)."""
    if female and entry.get("name_f"):
        return entry["name_f"]
    return entry.get("name", default)


def _size_rank(size: str) -> int:
    s = str(size or "").lower()
    return next((i for i, p in enumerate(SIZE_ORDER) if s.startswith(p)), 2)


def tool_names(rules: dict) -> dict:
    names = dict(DEFAULT_TOOL_NAMES)
    for k, v in ((rules.get("equipment") or {}).get("tools") or {}).items():
        names[k] = v.get("name", k) if isinstance(v, dict) else str(v)
    return names


def iter_feats(char: dict, rules: dict):
    """Talenti scelti: `feats: [alert, {key: resilient, ability: con}, ...]` -> (chiave, regola, scelta)."""
    table = rules.get("feats") or {}
    out = []
    seen = set()
    for entry in _as_list(char.get("feats")):
        pick = entry if isinstance(entry, dict) else {"key": entry}
        key = pick.get("key")
        if key not in table:
            raise RulesError(f"Talento sconosciuto: {key} (vedi dnd5e/rules/feats.yaml)")
        if key in seen and not table[key].get("repeatable"):
            raise RulesError(f"Il talento {table[key]['name']} si può prendere una volta sola")
        seen.add(key)
        out.append((key, table[key], pick))
    return out


def feat_label(feat: dict, pick: dict, rules: dict | None = None) -> str:
    """Nome del talento con la scelta fatta: 'Resiliente (SAG)', 'Iniziato alla Magia (chierico)'."""
    extra = []
    if pick.get("ability") in ABBR_IT:
        extra.append(ABBR_IT[pick["ability"]])
    elif pick.get("save") in ABBR_IT:
        extra.append(ABBR_IT[pick["save"]])
    if pick.get("list"):
        cls = ((rules or {}).get("classes") or {}).get(pick["list"]) or {}
        extra.append(str(cls.get("name", pick["list"])).lower())
    if pick.get("damage_type"):
        extra.append(str(pick["damage_type"]))
    return feat["name"] + (f" ({', '.join(extra)})" if extra else "")


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def kid_fmt(text: str, values: dict) -> str:
    """Sostituisce i segnaposto ({cd}, {att}, {mod}, {soffio_cd}...) lasciando intatti quelli sconosciuti."""
    try:
        return str(text or "").format_map(_SafeDict(values))
    except (ValueError, IndexError, AttributeError, KeyError):
        return str(text or "")


def unresolved_placeholders(*texts) -> list:
    out = []
    for t in texts:
        out += [m for m in PLACEHOLDER_RE.findall(str(t or "")) if m not in out]
    return out


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
    # nomi dei tratti al femminile (Minacciosa, Fortunata, Coraggiosa...)
    result["traits"] = [{**t, "base_name": t.get("name", ""), "name": _nm(t, female)} for t in result["traits"]]
    for trait in result["traits"]:
        result["extra_languages"] += trait.get("extra_languages", 0)
    result["ancestry"] = None
    if race.get("ancestry"):
        anc_key = char.get("draconic_ancestry")
        if anc_key not in race["ancestry"]:
            raise RulesError(f"La razza {result['name']} richiede 'draconic_ancestry' tra: {', '.join(race['ancestry'])}")
        anc = race["ancestry"][anc_key]
        result["ancestry"] = {"key": anc_key, **anc}
        result["name"] += f" ({anc.get('label') or 'drago ' + anc['name'].lower()})"
    return result


# ---------------------------------------------------------------------------
# Punteggi di caratteristica
# ---------------------------------------------------------------------------
def _class_casts(cls: dict | None, rules: dict) -> bool:
    """Vero se la classe, al suo livello, lancia già incantesimi (slot o trucchetti)."""
    caster = (cls or {}).get("spellcasting")
    if not caster:
        return False
    row = (rules["spells"].get("slots") or {}).get(caster.get("type"), {}).get(cls["level"], [])
    if isinstance(row, dict) or any(row or []):
        return True
    return any(isinstance(cls["table"].get(c), int) and cls["table"][c] > 0 for c in ("cantrips_known", "cantrips"))


def resolve_abilities(char: dict, race: dict, rules: dict, warnings: list, cls: dict | None = None) -> dict:
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
    asi_list = spec.get("asi", []) or []
    for asi in asi_list:
        if not isinstance(asi, dict):
            raise RulesError(f"abilities.asi: ogni aumento è del tipo {{dex: 2}} o {{str: 1, con: 1}} (dato: {asi})")
        vals = {k: v for k, v in asi.items() if k != "level"}
        for k, v in vals.items():
            if k not in ABILITIES:
                raise RulesError(f"abilities.asi: caratteristica sconosciuta {k}")
            if not isinstance(v, int) or v < 1 or v > 2:
                raise RulesError(f"abilities.asi: {ABBR_IT[k]} +{v} non è permesso (un aumento è +2 a una caratteristica o +1 a due)")
        if sum(vals.values()) != 2:
            raise RulesError(f"abilities.asi: ogni aumento vale 2 punti in tutto (+2 a una o +1 a due), non {asi}")
        _merge_bonus(scores, vals)
    # talenti: prerequisiti controllati sui punteggi prima del bonus del talento stesso
    feats = iter_feats(char, rules)
    armor_profs = set((cls or {}).get("armor") or [])
    for t in race["traits"]:
        armor_profs.update(t.get("armor_proficiencies", []))
    caster = _class_casts(cls, rules) or any(t.get("fixed_cantrips") or t.get("cantrip_choice") or t.get("innate_spells")
                                             for t in race["traits"])
    for key, feat, pick in feats:
        name = feat["name"]
        need = feat.get("prereq_ability") or {}
        low = [f"{ABBR_IT[k]} {v}" for k, v in need.items() if scores.get(k, 0) < v]
        if low:
            raise RulesError(f"Il talento {name} richiede {', '.join(low)} o più")
        need_any = feat.get("prereq_ability_any") or {}
        if need_any and not any(scores.get(k, 0) >= v for k, v in need_any.items()):
            raise RulesError(f"Il talento {name} richiede " + " o ".join(f"{ABBR_IT[k]} {v}" for k, v in need_any.items()) + " o più")
        if cls is not None and feat.get("prereq_armor") and feat["prereq_armor"] not in armor_profs:
            raise RulesError(f"Il talento {name} richiede la competenza nelle {ARMOR_CATEGORY_NAMES.get(feat['prereq_armor'], feat['prereq_armor'])}")
        if cls is not None and feat.get("prereq_spellcaster") and not caster:
            raise RulesError(f"Il talento {name} richiede di saper lanciare almeno un incantesimo")
        armor_profs.update(feat.get("armor_proficiencies", []))
        if feat.get("cantrip_choice") or feat.get("spell_choice"):
            caster = True
        _merge_bonus(scores, feat.get("ability_bonus"))
        ch = feat.get("ability_choice")
        if ch:
            ab = pick.get("ability")
            if ab not in ch.get("from", ABILITIES):
                raise RulesError(f"Il talento {feat['name']} richiede 'ability' tra: {', '.join(ch.get('from', ABILITIES))}")
            scores[ab] += int(ch.get("bonus", 1))
    caps = {k: 20 for k in ABILITIES}
    if cls is not None:
        # aumenti dati dai privilegi (Campione Primordiale: +4 FOR e COS, massimo 24)
        for f in cls["features"]:
            _merge_bonus(scores, f.get("ability_bonus"))
            for k, v in (f.get("ability_max") or {}).items():
                caps[k] = max(caps.get(k, 20), int(v))
        # quanti aumenti/talenti spettano al livello attuale
        asi_levels = cls.get("asi_levels") or []
        allowed = len([lv for lv in asi_levels if lv <= cls["level"]]) + sum(int(t.get("feat_choice", 0)) for t in race["traits"])
        if asi_levels and len(asi_list) + len(feats) != allowed:
            warnings.append(f"Aumenti di caratteristica e talenti: scelti {len(asi_list) + len(feats)}, al livello {cls['level']} "
                            f"ne spettano {allowed} ('abilities.asi' e 'feats')")
    for k, v in scores.items():
        if v > caps.get(k, 20):
            warnings.append(f"{k.upper()} = {v}: il massimo normale è {caps.get(k, 20)}")
    return {
        "method": method,
        "base": base,
        "scores": scores,
        "mods": {k: ability_mod(v) for k, v in scores.items()},
    }


# ---------------------------------------------------------------------------
# Classe
# ---------------------------------------------------------------------------
def _apply_replaces(features: list) -> list:
    """Toglie i privilegi superati: una voce con `replaces` sostituisce quelle (precedenti) con quel nome."""
    drop = set()
    for i, f in enumerate(features):
        names = set(_as_list(f.get("replaces")))
        if not names:
            continue
        for j, g in enumerate(features):
            if j != i and j not in drop and g.get("base_name", g.get("name")) in names and (g.get("level") or 0) <= (f.get("level") or 0):
                drop.add(j)
    return [f for i, f in enumerate(features) if i not in drop]


def resolve_class(char: dict, rules: dict, warnings: list | None = None) -> dict:
    warnings = warnings if warnings is not None else []
    classes = rules["classes"]
    key = char["class"]
    if key not in classes:
        raise RulesError(f"Classe sconosciuta: {key}")
    cls = copy.deepcopy(classes[key])
    level = int(char.get("level", 1))
    if not 1 <= level <= 20:
        raise RulesError("Il livello deve essere tra 1 e 20")
    female = is_female(char)
    features = []
    for lvl in sorted(cls.get("features", {})):
        if lvl <= level:
            for f in cls["features"][lvl]:
                features.append({**f, "name": _nm(f, female), "base_name": f.get("name", ""), "level": lvl,
                                 "source": _nm(cls, female), "origin": "class"})
    subclass = None
    sub_key = char.get("subclass")
    sub_level = cls.get("subclass_level", 99)
    subs = cls.get("subclasses", {}) or {}
    label = cls.get("subclass_label", "archetipo")
    if sub_key and sub_key not in subs:
        raise RulesError(f"{label} sconosciuto: {sub_key} (possibili: {', '.join(subs) or 'nessuno'})")
    if level >= sub_level:
        if not sub_key:
            raise RulesError(f"Al livello {level} serve la scelta: {label} ('subclass')")
        subclass = subs[sub_key]
        for lvl in sorted(subclass.get("features", {})):
            if lvl <= level:
                for f in subclass["features"][lvl]:
                    features.append({**f, "name": _nm(f, female), "base_name": f.get("name", ""), "level": lvl,
                                     "source": _nm(subclass, female), "origin": "subclass"})
    elif sub_key:
        warnings.append(f"{label}: si sceglie al {sub_level}° livello: per ora non conta")
        sub_key = None
    features = _apply_replaces(features)
    spellcasting = cls.get("spellcasting")
    if subclass and subclass.get("spellcasting"):
        spellcasting = subclass["spellcasting"]
    # numeri della tabella di classe al livello attuale (Attacco Furtivo, punti ki, incantesimi conosciuti...)
    columns = dict(cls.get("table") or {})
    columns.update((subclass or {}).get("table") or {})
    table = {k: v[level - 1] for k, v in columns.items() if isinstance(v, list) and len(v) >= level}
    option_lists = dict(cls.get("option_lists") or {})
    option_lists.update((subclass or {}).get("option_lists") or {})
    armor, weapons, tools = list(cls.get("armor", [])), list(cls.get("weapons", [])), list(cls.get("tools", []))
    for f in features:
        bp = f.get("bonus_proficiencies") or {}
        armor += [a for a in bp.get("armor", []) if a not in armor]
        weapons += [w for w in bp.get("weapons", []) if w not in weapons]
        tools += [t for t in bp.get("tools", []) if t not in tools]
    cls["armor"], cls["weapons"], cls["tools"] = armor, weapons, tools
    martial = cls.get("martial_arts")
    if martial is None and "martial_arts" in columns:
        martial = DEFAULT_MARTIAL_ARTS
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
        "tool_choice": cls.get("tool_choice") if isinstance(cls.get("tool_choice"), dict) else None,
        "skill_choices": cls.get("skill_choices", {"count": 0, "from": []}),
        "spellcasting": spellcasting,
        "subclass_label": cls.get("subclass_label"),
        "subclass_level": sub_level,
        "subclass": subclass,
        "subclass_name": _nm(subclass, female) if subclass else None,
        "table": table,
        "table_full": columns,
        "option_lists": option_lists,
        "ki_save": cls.get("ki_save"),
        "subclass_key": sub_key if subclass else None,
        "features": features,
        "wild_shape": (subclass or {}).get("wild_shape") or cls.get("wild_shape"),
        "asi_levels": list(cls.get("asi_levels") or []),
        "martial_arts": martial,
        "always_prepared_tag": cls.get("always_prepared_tag") or DEFAULT_PREPARED_TAG.get(key, "sottoclasse"),
    }


# ---------------------------------------------------------------------------
# Opzioni di classe (suppliche, metamagia, nemico prescelto, discipline...)
# ---------------------------------------------------------------------------
def resolve_options(char: dict, cls: dict, warnings: list) -> list:
    """Opzioni scelte in `class_options`, controllate: lista aperta, quante, prerequisiti."""
    level = cls["level"]
    female = is_female(char)
    picked = char.get("class_options") or {}
    for k in picked:
        if k not in cls["option_lists"]:
            raise RulesError(f"class_options: '{k}' non esiste per questa classe o sottoclasse ({', '.join(cls['option_lists']) or 'nessuna'})")
    pact_keys = {_pick_key(p) for p in _as_list(picked.get("pact_boons"))}
    cantrip_keys = {_pick_key(c) for c in _as_list(char.get("cantrips"))}
    out = []
    for list_key, opt in cls["option_lists"].items():
        chosen = _as_list(picked.get(list_key))
        label = opt.get("label", list_key)
        if opt.get("level") and level < opt["level"]:
            if chosen:
                warnings.append(f"{label} si sceglie al {opt['level']}° livello: per ora non conta")
            continue
        want = cls["table"].get(opt.get("count_table")) if opt.get("count_table") else opt.get("count")
        if isinstance(want, int) and want == 0:
            if chosen:
                warnings.append(f"{label}: al livello {level} non ne hai ancora: per ora non contano")
            continue
        if isinstance(want, int) and len(chosen) != want:
            warnings.append(f"{label}: scelte {len(chosen)}, al livello {level} ne servono {want} ('class_options: {list_key}')")
        _check_duplicates(chosen, label)
        for entry in chosen:
            pick = entry if isinstance(entry, dict) else {"key": entry}
            k = pick.get("key")
            item = (opt.get("items") or {}).get(k)
            if not item:
                raise RulesError(f"Opzione sconosciuta in {list_key}: {k}")
            name = _nm(item, female, k)
            if item.get("min_level") and level < int(item["min_level"]):
                raise RulesError(f"{label}: {name} richiede il {item['min_level']}° livello")
            if item.get("requires_pact") and item["requires_pact"] not in pact_keys:
                pact = ((cls["option_lists"].get("pact_boons") or {}).get("items") or {}).get(item["requires_pact"], {})
                raise RulesError(f"{label}: {name} richiede il {pact.get('name', item['requires_pact'])}")
            if item.get("requires_cantrip") and item["requires_cantrip"] not in cantrip_keys:
                raise RulesError(f"{label}: {name} richiede il trucchetto '{item['requires_cantrip']}' in 'cantrips'")
            out.append({"list": list_key, "label": label, "level": opt.get("level"), "key": k, "item": item,
                        "pick": pick, "name": name})
    return out


# ---------------------------------------------------------------------------
# Background, strumenti, competenze e abilità
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
    bg["tool_picks"] = None if char.get("background_tools") is None else _as_list(char["background_tools"])
    return bg


def _placeholder_count(text) -> int:
    """'Tre strumenti musicali a scelta' -> 3; un testo senza 'a scelta' -> 0."""
    s = str(text or "").lower()
    if "a scelta" not in s:
        return 0
    return NUMBER_WORDS.get(s.split()[0], 1) if s.split() else 1


def resolve_tools(char: dict, race: dict, cls: dict, background: dict, rules: dict, warnings: list) -> list:
    """Competenze negli strumenti: fisse + scelte. Le etichette 'a scelta' restano solo se mancano le scelte."""
    names = tool_names(rules)

    def tname(t):
        return names.get(t, t) if isinstance(t, str) else str(t)

    # scelte da 'tools' del personaggio: classe, razza, privilegi
    choices = []  # (quante, etichetta)
    cls_fixed = []
    for t in cls["tools"]:
        n = _placeholder_count(t)
        if n:
            choices.append((n, t))
        else:
            cls_fixed.append(tname(t))
    if cls.get("tool_choice"):
        choices.append((int(cls["tool_choice"].get("count", 1)), cls["tool_choice"].get("label", "Strumenti a scelta")))
    race_fixed = []
    for t in race["traits"]:
        race_fixed += [tname(x) for x in t.get("tool_proficiencies", [])]
        if int(t.get("tool_choice", 0) or 0):
            choices.append((int(t["tool_choice"]), f"{t['name']}: strumento a scelta"))
    for f in cls["features"]:
        tc = f.get("tool_choice")
        if isinstance(tc, int) and tc:
            choices.append((tc, f"{f['name']}: strumento a scelta"))
    picks = [tname(t) for t in _as_list(char.get("tools"))]
    expected = sum(n for n, _ in choices)
    missing_labels = []
    left = len(picks)
    for n, label in choices:
        if left >= n:
            left -= n
        else:
            missing_labels.append(label)
            left = 0
    if expected and len(picks) < expected:
        warnings.append(f"Hai {expected} competenza/e in strumenti a scelta: indicale in 'tools' (date: {len(picks)})")
    # background: fissi + scelte in 'background_tools'
    bg_fixed, bg_choices = [], []
    for t in background.get("tools", []):
        n = _placeholder_count(t)
        if n:
            bg_choices.append((n, t))
        else:
            bg_fixed.append(tname(t))
    for c in background.get("tool_choices") or []:
        bg_choices.append((int(c.get("count", 1)), c.get("label", "Strumento a scelta")))
    bg_picks = background.get("tool_picks")
    if bg_picks is None:
        bg_tools = bg_fixed + [label for _, label in bg_choices]
        if bg_choices:
            warnings.append(f"Background {background['name']}: scegli " + ", ".join(label.lower() for _, label in bg_choices)
                            + " e scrivi tutti gli strumenti del background in 'background_tools'")
    else:
        # 'background_tools' è l'elenco completo degli strumenti del background (così si può sostituire un doppione)
        bg_tools = [tname(t) for t in bg_picks]
        need = len(bg_fixed) + sum(n for n, _ in bg_choices)
        if len(bg_tools) < need:
            bg_tools += [label for _, label in bg_choices]
            warnings.append(f"Background {background['name']}: in 'background_tools' servono {need} strumenti (dati: {len(bg_picks)})"
                            + (" (" + ", ".join(label.lower() for _, label in bg_choices) + ")" if bg_choices else ""))
    tools = cls_fixed + missing_labels + bg_tools + picks + race_fixed
    out, seen = [], {}
    for t in tools:
        k = str(t).strip().lower()
        if k in seen:
            if "a scelta" not in k:
                warnings.append(f"Competenza in {t} data due volte: per le regole puoi sceglierne un'altra al suo posto")
            continue
        seen[k] = t
        out.append(t)
    return out


def resolve_skills(char: dict, race: dict, cls: dict, background: dict, rules: dict, warnings: list,
                   options: list | None = None, tools: list | None = None) -> dict:
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
    _check_duplicates(racial_picks, "racial_skills")
    if len(racial_picks) != racial_choice_count:
        raise RulesError(
            f"La razza concede {racial_choice_count} abilità a scelta: indicale in 'racial_skills' (date: {len(racial_picks)})"
        )
    for s in racial_picks:
        add(s, f"razza ({race['name']})")
    for o in options or []:  # opzioni di classe che danno abilità (Influenza Ammaliante)
        for s in o["item"].get("skills", []) or []:
            add(s, o["name"])
    expected_extra = 0
    extra_pools = []  # insiemi di abilità ammesse (None = qualsiasi)
    tools_allowed = False
    for f in cls["features"]:
        bp = f.get("bonus_proficiencies") or {}
        for s in bp.get("skills", []):
            add(s, f["name"])
        if bp.get("skill_choice"):
            expected_extra += int(bp["skill_choice"].get("count", 0))
            extra_pools.append(set(bp["skill_choice"].get("from") or []) or None)
    for _, feat, _ in iter_feats(char, rules):
        if feat.get("skill_choice"):
            expected_extra += int(feat["skill_choice"].get("count", 0))
            extra_pools.append(set(feat["skill_choice"].get("from") or []) or None)
            tools_allowed = tools_allowed or bool(feat["skill_choice"].get("tools_allowed"))
    extra = _as_list(char.get("extra_skills"))
    _check_duplicates(extra, "extra_skills")
    if len(extra) != expected_extra:
        warnings.append(f"Hai {expected_extra} abilità in più da privilegi o talenti: indicale in 'extra_skills' (date: {len(extra)})")
    extra_tools = []
    allowed_any = any(p is None for p in extra_pools)
    allowed = set().union(*[p for p in extra_pools if p]) if extra_pools else set()
    for s in extra:
        if s not in all_skills and tools_allowed:
            extra_tools.append(s)  # Abile: uno strumento al posto di un'abilità
            continue
        if extra_pools and not allowed_any and s not in allowed:
            raise RulesError(f"extra_skills: {s} non è tra le abilità che i privilegi o talenti permettono ({', '.join(sorted(allowed))})")
        add(s, "privilegio o talento")
    # maestria: abilità con competenza, oppure strumenti permessi (Arnesi da scasso del ladro)
    names = tool_names(rules)
    exp_picks = _as_list(char.get("expertise"))
    _check_duplicates(exp_picks, "expertise")
    expertise, expertise_tools = set(), []
    tool_keys_ok = {t for f in cls["features"] for t in _as_list(f.get("expertise_tools"))}
    have_tools = {str(t).strip().lower() for t in (tools or [])}
    for s in exp_picks:
        if s in all_skills:
            if s not in proficient:
                raise RulesError(f"Maestria in {s} ma nessuna competenza")
            expertise.add(s)
        elif s in tool_keys_ok:
            tname = names.get(s, s)
            if tname.strip().lower() not in have_tools:
                raise RulesError(f"Maestria in {tname} ma nessuna competenza in questo strumento")
            expertise_tools.append(tname)
        else:
            raise RulesError(f"Maestria in {s}: non è un'abilità né uno strumento permesso")
    restricted = [(int(f.get("expertise_count", 0)), set(f["expertise_from"])) for f in cls["features"] if f.get("expertise_from")]
    free = sum(int(f.get("expertise_count", 0)) for f in cls["features"] if not f.get("expertise_from"))
    if restricted:
        pool_from = set().union(*[p for _, p in restricted])
        outside = [s for s in exp_picks if s not in pool_from]
        if len(outside) > free:
            raise RulesError(f"Maestria: {', '.join(outside)} non è tra le abilità permesse ({', '.join(sorted(pool_from))})")
    exp_count = sum(int(f.get("expertise_count", 0)) for f in cls["features"])
    if exp_count and len(exp_picks) != exp_count:
        warnings.append(f"Maestria: scelte {len(exp_picks)} abilità in 'expertise', al livello attuale ne hai {exp_count}")
    return {"proficient": proficient, "expertise": expertise, "expertise_tools": expertise_tools, "extra_tools": extra_tools}


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


def _monk_weapon(wkey: str, weapon: dict, martial: dict) -> bool:
    if wkey in (martial.get("weapons") or []):
        return True
    props = weapon.get("properties", [])
    return bool(martial.get("simple_melee") and weapon.get("category") == "simple" and weapon.get("type") == "melee"
                and not any(p in props for p in martial.get("exclude_properties", [])))


def martial_arts_die(cls: dict, char: dict) -> str | None:
    """Dado delle Arti Marziali, se il monaco può usarle ora (senza armatura e senza scudo)."""
    martial = cls.get("martial_arts")
    if not martial:
        return None
    if martial.get("requires_unarmored", True) and (char.get("armor") or char.get("shield")):
        return None
    return cls["table"].get(martial.get("die_column", "martial_arts"))


def resolve_weapons(char: dict, abilities: dict, cls: dict, race: dict, prof: int, styles: list, rules: dict,
                    feats: list | None = None) -> list:
    table = rules["equipment"]["weapons"]
    mods = abilities["mods"]
    martial = cls.get("martial_arts")
    ma_die = martial_arts_die(cls, char)
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
        monk = bool(ma_die and wkey and _monk_weapon(wkey, weapon, martial))
        if "finesse" in props or monk:
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
        vdice = weapon.get("versatile")
        if monk:  # Arti Marziali: si usa il dado del monaco se è più grande
            if _die_max(ma_die) > _die_max(dice):
                dice = ma_die
            if vdice and _die_max(ma_die) > _die_max(vdice):
                vdice = ma_die
            notes.append("Arti Marziali")
        dmg = _dice_with_mod(dice, one_hand_bonus)
        dmg_type = weapon.get("damage_type", "")
        versatile_damage = _dice_with_mod(vdice, base_dmg_bonus) if vdice else None
        if versatile_damage:
            notes.insert(0, f"a 2 mani {versatile_damage}")
        if "two_weapon_fighting" in styles and "light" in props and not ranged:
            notes.append("seconda arma: con Combattere con Due Armi aggiungi il modificatore ai danni")
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
            "versatile_damage": versatile_damage,
            "ability": ability,
            "proficient": proficient,
            "properties": extra,
            "notes": notes,
        })
    # colpo senz'armi: per i monaci (Arti Marziali) e per chi ha Rissatore da Taverna
    brawler = next((feat for _, feat, _ in (feats or []) if feat.get("unarmed_damage")), None)
    if martial or brawler:
        die, ability = None, "str"
        if ma_die:
            die = ma_die
            ability = "dex" if mods["dex"] >= mods["str"] else "str"
        if brawler and _die_max(brawler["unarmed_damage"]) > _die_max(die):
            die = brawler["unarmed_damage"]
            if not ma_die:
                ability = "str"
        amod = mods[ability]
        dmg = _dice_with_mod(die, amod) if die else str(max(1, 1 + amod))
        out.append({"key": "unarmed_strike", "name": "Colpo senz'armi", "attack": amod + prof, "attack_str": fmt_mod(amod + prof),
                     "damage": f"{dmg} contundente", "versatile_damage": None, "ability": ability, "proficient": True,
                     "properties": [], "notes": ["Arti Marziali"] if ma_die else []})
    return out


def resolve_ac(char: dict, abilities: dict, cls: dict, race: dict, styles: list, rules: dict, warnings: list,
               feats: list | None = None) -> dict:
    armor_table = rules["equipment"]["armor"]
    dex = abilities["mods"]["dex"]
    armor_key = char.get("armor")
    armor_profs = set(cls["armor"])
    for t in race["traits"]:
        armor_profs.update(t.get("armor_proficiencies", []))
    feat_rules = [feat for _, feat, _ in (feats or [])]
    parts = []
    shield = char.get("shield")
    if armor_key:
        if armor_key not in armor_table:
            raise RulesError(f"Armatura sconosciuta: {armor_key}")
        armor = armor_table[armor_key]
        ac = armor["base"]
        parts.append(f"{armor['name']} {armor['base']}")
        stealth_dis = armor.get("stealth_disadvantage", False)
        if armor["dex"] == "full":
            ac += dex
            parts.append(f"DES {fmt_mod(dex)}")
        elif armor["dex"] == "max2":
            cap = max([2] + [int(f.get("medium_armor_dex_cap", 0)) for f in feat_rules])  # Maestro delle Armature Medie
            ac += min(dex, cap)
            parts.append(f"DES {fmt_mod(min(dex, cap))} (max +{cap})")
            if armor["category"] == "medium" and any(f.get("medium_armor_no_stealth_penalty") for f in feat_rules):
                stealth_dis = False
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
    else:
        ac = 10 + dex
        parts.append(f"10 + DES {fmt_mod(dex)}")
        if cls["key"] == "barbarian":
            ac += abilities["mods"]["con"]
            parts.append(f"COS {fmt_mod(abilities['mods']['con'])}")
        elif cls["key"] == "monk" and not shield:
            ac += abilities["mods"]["wis"]
            parts.append(f"SAG {fmt_mod(abilities['mods']['wis'])}")
        else:
            for f in cls["features"]:
                ua = f.get("unarmored_ac")
                if ua and ua["base"] + abilities["mods"][ua.get("ability", "dex")] > ac:
                    ac = ua["base"] + abilities["mods"][ua.get("ability", "dex")]
                    parts = [f"{ua['base']} + {ABBR_IT[ua.get('ability', 'dex')]} {fmt_mod(abilities['mods'][ua.get('ability', 'dex')])} ({f['name']})"]
        armor_name = "Nessuna armatura"
        stealth_dis = False
    if shield:
        ac += armor_table["shield"]["bonus"]
        shield_name = shield if isinstance(shield, str) else armor_table["shield"]["name"]
        parts.append(f"{shield_name} +2")
        if "shields" not in armor_profs:
            warnings.append("Nessuna competenza negli scudi: svantaggio a prove, TS e attacchi su FOR/DES e niente incantesimi")
    ac += int(char.get("ac_bonus", 0))
    category = armor_table[armor_key]["category"] if armor_key else None
    return {"value": ac, "armor": armor_name, "shield": bool(shield), "breakdown": ", ".join(parts),
            "stealth_disadvantage": stealth_dis, "category": category}


def resolve_hp(char: dict, abilities: dict, cls: dict, race: dict, warnings: list, rules: dict | None = None) -> dict:
    spec = char.get("hp", {}) or {}
    method = spec.get("method", "average")
    level = cls["level"]
    con = abilities["mods"]["con"]
    die = cls["hit_die"]
    sources = []  # (punti per livello, da dove)
    for t in race["traits"]:
        if t.get("hp_per_level"):
            sources.append((int(t["hp_per_level"]), t["name"]))
    for f in cls["features"]:
        if f.get("hp_per_level"):
            sources.append((int(f["hp_per_level"]), f["name"]))
    for _, feat, _ in iter_feats(char, rules or {}):
        if feat.get("hp_per_level"):
            sources.append((int(feat["hp_per_level"]), feat["name"]))
    per_level_bonus = sum(n for n, _ in sources)
    bonus_text = (f", + {per_level_bonus} PF per livello ({', '.join(name for _, name in sources)})" if per_level_bonus else "")
    if method == "manual":
        total = int(spec["value"])
        detail = "valore inserito manualmente"
    else:
        first = die + con + per_level_bonus
        if method == "average":
            gains = [die // 2 + 1 + con + per_level_bonus] * (level - 1)
            detail = f"{die} + COS al 1° livello, poi {die // 2 + 1} + COS per livello" + bonus_text
        elif method == "rolled":
            rolls = [int(r) for r in _as_list(spec.get("rolled"))]
            if len(rolls) != level - 1:
                raise RulesError(f"hp.rolled deve contenere {level - 1} tiri (uno per livello dal 2°)")
            for r in rolls:
                if not 1 <= r <= die:
                    raise RulesError(f"hp.rolled: {r} non è un risultato possibile di 1d{die}")
            gains = [r + con + per_level_bonus for r in rolls]
            detail = f"{die} + COS al 1° livello, poi tiri {rolls} + COS" + bonus_text
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


def _beams(level: int) -> int:
    return 1 + (level >= 5) + (level >= 11) + (level >= 17)


def _fallback_spell_level(lvl: int, caster_type: str | None) -> int:
    """Livello dell'incantesimo di sottoclasse ottenuto al livello di classe `lvl` (se manca nei dati)."""
    if caster_type == "half":
        return max(1, (lvl + 3) // 4)
    return max(1, (lvl + 1) // 2)


def resolve_spellcasting(char: dict, cls: dict, race: dict, abilities: dict, prof: int, rules: dict, warnings: list,
                         options: list | None = None, feats: list | None = None) -> dict | None:
    spells_rules = rules["spells"]
    table = spells_rules["spells"]
    mods = abilities["mods"]
    level = cls["level"]
    names = rules["skills"]["abilities"]
    options = options or []
    feats = feats if feats is not None else iter_feats(char, rules)
    by_name = {v.get("name"): k for k, v in table.items()}

    def lookup(key, source, origin="class"):
        if key not in table and key in by_name:  # dati vecchi: nome italiano al posto della chiave
            key = by_name[key]
        if key in table:
            return {"key": key, **copy.deepcopy(table[key]), "source": source, "origin": origin}
        return {"key": key, "name": str(key), "level": None, "lists": [], "text": "", "source": source, "origin": origin}

    def lists_ok(sp, allowed):
        return allowed in (None, "any") or bool(set(_as_list(allowed)) & set(sp.get("lists") or []))

    # --- razza: trucchetti fissi o a scelta, incantesimi innati per livello
    cantrips = []
    other_spells = []  # incantesimi fuori dalla classe: innati, talenti, opzioni, ki, rituali
    innate_ability = None
    for t in race["traits"]:
        for key in t.get("fixed_cantrips", []):
            cantrips.append({**lookup(key, t["name"], "race"), "ability": t.get("innate_ability")})
        if t.get("innate_ability"):
            innate_ability = t["innate_ability"]
        if t.get("cantrip_choice"):
            innate_ability = t["cantrip_choice"]["ability"]
            picks = _as_list(char.get("racial_cantrips"))
            if len(picks) != 1:
                raise RulesError(f"Il tratto {t['name']} richiede un trucchetto in 'racial_cantrips'")
            for key in picks:
                sp = lookup(key, race["name"], "race")
                if sp["level"] is None or t["cantrip_choice"]["list"] not in sp["lists"] or sp["level"] != 0:
                    raise RulesError(f"{key} non è un trucchetto della lista {t['cantrip_choice']['list']}")
                cantrips.append({**sp, "ability": t["cantrip_choice"]["ability"]})
        uses = t.get("innate_uses") or "1/riposo lungo"
        for lvl in sorted(t.get("innate_spells") or {}, key=int):
            if int(lvl) > level:
                continue
            for e in _as_list(t["innate_spells"][lvl]):
                key = _pick_key(e)
                cast = e.get("cast_level") if isinstance(e, dict) else None
                sp = lookup(key, t["name"], "race")
                sp["ability"] = t.get("innate_ability") or innate_ability
                sp["tag"] = "innata, " + (f"{cast}° livello, " if cast and cast != sp.get("level") else "") + uses
                sp["cast_level"] = cast
                sp["extra"] = True
                other_spells.append(sp)
    racial_cantrips = list(cantrips)
    racial_keys = {c["key"] for c in racial_cantrips}

    # --- classe
    caster = cls.get("spellcasting")
    slot_row = []
    if caster:
        slot_row = spells_rules["slots"][caster["type"]].get(level, []) if caster["type"] in spells_rules["slots"] else []
        if caster["type"] in ("half", "third") and not slot_row and not _class_casts(cls, rules):
            if char.get("cantrips") or char.get("spells"):
                warnings.append(f"{cls['name']} di livello {level}: non lancia ancora incantesimi, 'cantrips' e 'spells' per ora non contano")
            caster = None
    class_cantrips = []
    extra_cantrips = []  # da talenti e opzioni, fuori dal conteggio
    prepared = []
    slots = {}
    prepared_max = None
    circle_spells = []
    book = []
    spell_ability = innate_ability
    title = race["name"] if innate_ability else None
    sub = cls.get("subclass") or {}
    schools = None
    any_school_free = 0
    secret_cantrips = 0
    if caster:
        spell_ability = caster["ability"]
        title = cls["name"]
        list_key = caster.get("list", cls["key"])
        known_table = spells_rules["cantrips_known"].get(cls["key"]) or spells_rules["cantrips_known"].get(caster["type"])
        bonus = sum(int(f.get("cantrip_bonus", 0)) for f in cls["features"])
        expected = (known_table[level - 1] if known_table else None)
        for col in ("cantrips_known", "cantrips"):
            if isinstance(cls["table"].get(col), int):
                expected = cls["table"][col]
        # trucchetti da altre liste dati da un privilegio (es. Accolito della Natura: 1 trucchetto da druido)
        other_lists = {}
        for f in cls["features"]:
            ch = f.get("cantrip_choice")
            if isinstance(ch, dict) and ch.get("list"):
                other_lists[ch["list"]] = {"left": int(ch.get("count", 1)), "ability": ch.get("ability", spell_ability)}
                bonus += int(ch.get("count", 1))
        secrets_left = sum(int(f.get("magical_secrets", 0)) for f in cls["features"])  # Segreti Magici del bardo
        spell_picks = _as_list(char.get("spells"))
        _check_duplicates(spell_picks, "spells")
        picks = _as_list(char.get("cantrips"))
        _check_duplicates(picks, "cantrips")
        # un trucchetto scritto in 'spells' (es. Segreti Magici) si tratta come trucchetto, mai come incantesimo di 1°
        moved = [k for k in spell_picks if (table.get(k) or {}).get("level") == 0]
        spell_picks = [k for k in spell_picks if k not in moved]
        # trucchetti gratuiti dati da un privilegio (Illusione Minore Migliorata, Mano Magica del Mistificatore)
        granted = []
        for f in cls["features"]:
            key = f.get("grants_cantrip")
            if not key:
                continue
            if key in picks or key in moved or key in racial_keys:
                bonus += 1  # lo conosci già: al suo posto impari un altro trucchetto
            else:
                granted.append({**lookup(key, f["source"]), "ability": spell_ability})
        counted = 0
        for key in picks + moved:
            sp = lookup(key, cls["name"])
            ability = spell_ability
            if key in racial_keys:
                warnings.append(f"{sp['name']}: lo conosci già dalla razza: scegli un altro trucchetto in 'cantrips'")
            if sp["level"] is None:
                warnings.append(f"Trucchetto {key} non presente nei dati: aggiungilo a dnd5e/rules/spells.yaml")
                counted += 1
            elif sp["level"] != 0:
                raise RulesError(f"{sp['name']} non è un trucchetto")
            elif list_key not in sp["lists"]:
                extra = next((l for l in sp["lists"] if other_lists.get(l, {}).get("left", 0) > 0), None)
                if extra:
                    other_lists[extra]["left"] -= 1
                    ability = other_lists[extra]["ability"]
                    counted += 1
                elif secrets_left > 0:
                    secrets_left -= 1
                    secret_cantrips += 1
                    sp["source"] = "Segreti Magici"
                    sp["secret"] = True
                else:
                    raise RulesError(f"{sp['name']} non è un trucchetto della lista del {cls['name']}")
            else:
                counted += 1
                if key in moved:
                    warnings.append(f"{sp['name']} è un trucchetto: scrivilo in 'cantrips', non in 'spells'")
            class_cantrips.append({**sp, "ability": ability})
        class_cantrips += granted
        if expected is not None and counted != expected + bonus:
            warnings.append(f"Trucchetti di classe: scelti {counted}, al livello {level} ne conosci {expected + bonus}")
        if isinstance(slot_row, dict):  # magia del patto (warlock): tutti gli slot dello stesso livello
            slots = {slot_row["level"]: slot_row["slots"]}
        else:
            slots = {i + 1: n for i, n in enumerate(slot_row) if n}
        max_level = max(slots) if slots else 0
        # incantesimi sempre preparati della sottoclasse (dominio, giuramento, circolo della terra)
        tag = cls.get("always_prepared_tag") or "sottoclasse"
        seen_keys = set()

        def add_always(key, lvl, source):
            sp = lookup(key, source)
            if sp["level"] is None:
                warnings.append(f"Incantesimo {key} non presente nei dati: aggiungilo a dnd5e/rules/spells.yaml")
                sp["level"] = _fallback_spell_level(lvl, caster.get("type"))
            if sp["key"] in seen_keys:
                return
            seen_keys.add(sp["key"])
            sp["always_prepared"] = True
            sp["tag"] = tag
            circle_spells.append(sp)

        for lvl in sorted(sub.get("always_prepared") or {}):
            if lvl <= level:
                for key in sub["always_prepared"][lvl]:
                    add_always(key, lvl, _nm(sub, False))
        if sub.get("circle_spells"):
            terrain = char.get("circle_terrain")
            if terrain not in sub["circle_spells"]:
                raise RulesError(f"Il {sub['name']} richiede 'circle_terrain' tra: {', '.join(sub['circle_spells'])}")
            label = (sub.get("terrain_labels") or {}).get(terrain, terrain)
            for lvl in sorted(sub["circle_spells"][terrain]):
                if lvl <= level:
                    for key in sub["circle_spells"][terrain][lvl]:
                        add_always(key, lvl, f"{sub['name']} ({label})")
        # incantesimi fuori lista permessi: lista ampliata del patrono; quelli della sottoclasse danno solo un avviso
        expanded = {k for lvl, keys in (sub.get("expanded_spells") or {}).items() for k in keys}
        always_keys = {c["key"] for c in circle_spells}
        arcanum_left = {int(f["arcanum_level"]) for f in cls["features"] if f.get("arcanum_level")}  # Arcanum Mistico del warlock
        if caster.get("spellbook"):
            book_keys = _as_list(char.get("spellbook"))
            _check_duplicates(book_keys, "spellbook")
            free_keys = [f["spellbook_add"] for f in cls["features"] if f.get("spellbook_add")]
            counted_book = [k for k in book_keys if k not in free_keys]
            book_keys += [k for k in free_keys if k not in book_keys]
            expected_book = 6 + 2 * (level - 1)
            if len(counted_book) < expected_book:
                warnings.append(f"Libro degli incantesimi: {len(counted_book)} incantesimi, al livello {level} ne hai {expected_book} (senza contare quelli copiati)")
            for key in spell_picks:
                if key not in book_keys:
                    raise RulesError(f"{key} è preparato ma non è nel libro degli incantesimi ('spellbook')")
            for key in book_keys:
                sp = lookup(key, cls["name"])
                if sp["level"] is None:
                    warnings.append(f"Incantesimo {key} non presente nei dati: aggiungilo a dnd5e/rules/spells.yaml")
                elif list_key not in sp["lists"] and key not in free_keys:
                    raise RulesError(f"{sp['name']} non è nella lista del {cls['name']}")
                elif sp["level"] > max_level:
                    raise RulesError(f"{sp['name']} è di {sp['level']}° livello ma hai slot solo fino al {max_level}°")
                elif sp["level"] == 0:
                    raise RulesError(f"{sp['name']} è un trucchetto: non va nel libro ('spellbook')")
                sp["prepared"] = key in spell_picks
                book.append(sp)
        for key in spell_picks:
            sp = lookup(key, cls["name"])
            if sp["level"] is None:
                warnings.append(f"Incantesimo {key} non presente nei dati: aggiungilo a dnd5e/rules/spells.yaml")
            else:
                if list_key not in sp["lists"] and key not in expanded and key not in always_keys:
                    if secrets_left <= 0:
                        raise RulesError(f"{sp['name']} non è nella lista del {cls['name']}")
                    secrets_left -= 1
                    sp["source"] = "Segreti Magici"
                if sp["level"] > max_level:
                    if sp["level"] not in arcanum_left:
                        raise RulesError(f"{sp['name']} è di {sp['level']}° livello ma hai slot solo fino al {max_level}°")
                    arcanum_left.discard(sp["level"])
                    sp["arcanum"] = True
            prepared.append(sp)
        # scuole permesse (Mistificatore Arcano, Cavaliere Mistico)
        if caster.get("schools"):
            schools = list(caster["schools"])
            any_school_free = len([lv for lv in caster.get("any_school_levels") or [] if lv <= level])
            off = [sp for sp in prepared if sp.get("level") and sp.get("school") not in schools and not sp.get("arcanum")]
            if len(off) > any_school_free:
                raise RulesError(f"{cls['subclass_name'] or cls['name']}: impari incantesimi di {' e '.join(schools)}; "
                                 f"fuori scuola ne puoi avere solo {any_school_free} al livello {level}, invece sono "
                                 + ", ".join(sp["name"] for sp in off))
        # Maestria negli Incantesimi (18°) e Incantesimi Personali (20°) del mago
        mastery = _as_list(char.get("spell_mastery"))
        signature = _as_list(char.get("signature_spells"))
        book_by_key = {sp["key"]: sp for sp in book}
        if mastery:
            if not caster.get("spellbook") or level < 18:
                raise RulesError("'spell_mastery' (Maestria negli Incantesimi) è del mago dal 18° livello")
            lv = sorted((book_by_key.get(k) or {}).get("level") or 0 for k in mastery)
            if len(mastery) != 2 or lv != [1, 2] or any(k not in book_by_key for k in mastery):
                raise RulesError("'spell_mastery': un incantesimo di 1° e uno di 2° livello del libro")
            for sp in book + prepared:
                if sp["key"] in mastery:
                    sp["mastery"] = True
        if signature:
            if not caster.get("spellbook") or level < 20:
                raise RulesError("'signature_spells' (Incantesimi Personali) è del mago al 20° livello")
            if len(signature) != 2 or len(set(signature)) != 2 or any((book_by_key.get(k) or {}).get("level") != 3 for k in signature):
                raise RulesError("'signature_spells': due incantesimi di 3° livello del libro")
            for sp in book:
                if sp["key"] in signature:
                    sp["signature"] = True
                    sp["always_prepared"] = True
                    sp["tag"] = "personale"
                    if sp.get("prepared"):
                        warnings.append(f"{sp['name']} è un Incantesimo Personale (sempre preparato): toglilo da 'spells' e scegline un altro")
            prepared = [sp for sp in prepared if sp["key"] not in signature]
        if caster.get("prepared") == "ability_plus_level" and slots:
            prepared_max = max(1, mods[spell_ability] + (level if caster["type"] == "full" else level // 2))
            if len(prepared) != prepared_max:
                warnings.append(f"Incantesimi preparati: {len(prepared)} su {prepared_max} possibili")
        elif caster.get("prepared") == "known" and isinstance(cls["table"].get("spells_known"), int):
            known = cls["table"]["spells_known"] + sum(int(f.get("bonus_spells_known", 0)) for f in cls["features"])
            n_known = len([sp for sp in prepared if not sp.get("arcanum")]) + secret_cantrips
            if n_known != known:
                warnings.append(f"Incantesimi conosciuti: {n_known} su {known} al livello {level}")
        for sp in prepared:
            if sp.get("key") in always_keys:
                if sub.get("circle_spells"):
                    warnings.append(f"{sp['name']} è già un incantesimo del circolo (sempre preparato): scegline un altro in 'spells'")
                else:
                    warnings.append(f"{sp['name']} è già sempre preparato grazie alla sottoclasse: scegline un altro in 'spells'")
    else:
        for key in _as_list(char.get("cantrips")) + _as_list(char.get("spells")):
            if key and not cls.get("spellcasting"):
                warnings.append(f"{cls['name']}: questa classe non lancia incantesimi, '{key}' in 'cantrips'/'spells' non conta")
                break
        # trucchetti dati da un privilegio a chi non è incantatore (es. Arti dell'Ombra): caratteristica propria
        for f in cls["features"]:
            key = f.get("grants_cantrip")
            if key and key not in racial_keys:
                ab = f.get("cantrip_ability", "wis")
                class_cantrips.append({**lookup(key, f["source"]), "ability": ab})
                if not spell_ability:
                    spell_ability, title = ab, f["source"]

    # --- talenti che danno trucchetti o incantesimi (Iniziato alla Magia, Cecchino Magico, Celebrante Rituale)
    for fkey, feat, pick in feats:
        cc, sc = feat.get("cantrip_choice"), feat.get("spell_choice")
        if not (cc or sc):
            continue
        fname = feat["name"]
        allowed = (cc or sc).get("lists")
        by_list = (cc or sc).get("ability_by_list") or {}
        lst = pick.get("list")
        c_picks = _as_list(pick.get("cantrips"))
        s_picks = _as_list(pick.get("spells")) + _as_list(pick.get("spell"))
        _check_duplicates(c_picks + s_picks, f"Talento {feat['name']}")
        if not lst:
            first = next((k for k in c_picks + s_picks if k in table), None)
            lst = next((l for l in (table.get(first) or {}).get("lists", []) if lists_ok({"lists": [l]}, allowed)), None)
        if not lst:
            raise RulesError(f"Il talento {feat['name']} richiede 'list' (la classe da cui prendi le magie) e le scelte")
        if isinstance(allowed, list) and lst not in allowed:
            raise RulesError(f"Il talento {feat['name']}: 'list' deve essere tra {', '.join(allowed)}")
        ability = by_list.get(lst) or (cc or sc).get("ability") or spell_ability or "int"
        if cc:
            if len(c_picks) != int(cc.get("count", 1)):
                warnings.append(f"Talento {feat['name']}: scegli {cc.get('count', 1)} trucchetti in 'cantrips' (dati: {len(c_picks)})")
            for key in c_picks:
                sp = lookup(key, fname, "feat")
                if sp["level"] != 0 or lst not in sp["lists"]:
                    raise RulesError(f"Talento {feat['name']}: {sp['name']} non è un trucchetto della lista scelta ({lst})")
                if cc.get("attack_roll_required") and not sp.get("attack"):
                    raise RulesError(f"Talento {feat['name']}: {sp['name']} non richiede un tiro per colpire")
                extra_cantrips.append({**sp, "ability": ability})
        if sc:
            want = int(sc.get("count", 1))
            if len(s_picks) < want or (not sc.get("ritual_book") and len(s_picks) != want):
                warnings.append(f"Talento {feat['name']}: scegli {want} incantesimi in 'spells' (dati: {len(s_picks)})")
            max_lv = int(sc.get("level", 1))
            if sc.get("ritual_book"):
                max_lv = max(max_lv, (level + 1) // 2)
            for key in s_picks:
                sp = lookup(key, fname, "feat")
                if sp["level"] is None or sp["level"] < 1 or sp["level"] > max_lv or lst not in sp["lists"]:
                    raise RulesError(f"Talento {feat['name']}: {sp['name']} deve essere della lista scelta ({lst}) e di livello {max_lv} o meno")
                if sc.get("ritual_only") and not sp.get("ritual"):
                    raise RulesError(f"Talento {feat['name']}: {sp['name']} non è un rituale")
                sp["ability"] = ability
                sp["tag"] = "solo rituale" if sc.get("ritual_only") else "1/riposo lungo senza slot"
                sp["extra"] = True
                other_spells.append(sp)
        if not spell_ability:
            spell_ability, title = ability, feat["name"]

    # --- opzioni di classe con incantesimi (suppliche, discipline, patto del tomo...)
    ki_ab = (cls.get("ki_save") or {}).get("ability", "wis")
    at_will_mage_armor = False
    for o in options:
        item, pick = o["item"], o["pick"]
        if item.get("spell"):
            sp = lookup(item["spell"], o["name"], "option")
            uses = item.get("spell_uses")
            if item.get("ki_cost") and not uses:
                sp["tag"] = f"ki {item['ki_cost']}"
                sp["ability"] = ki_ab
                sp["ki"] = True
            else:
                sp["tag"] = SPELL_USES_TAGS.get(uses, "privilegio")
            sp["extra"] = True
            if sp["level"] == 0:
                extra_cantrips.append(sp)
            else:
                other_spells.append(sp)
            if uses == "at_will" and sp["key"] == "mage_armor":
                at_will_mage_armor = True
        cc, sc = item.get("cantrip_choice"), item.get("spell_choice")
        c_picks, s_picks = _as_list(pick.get("cantrips")), _as_list(pick.get("spells"))
        _check_duplicates(c_picks + s_picks, o["name"])
        if cc:
            if len(c_picks) != int(cc.get("count", 1)):
                warnings.append(f"{o['name']}: scegli {cc.get('count', 1)} trucchetti (class_options: {{key: {o['key']}, cantrips: [...]}}; dati: {len(c_picks)})")
            for key in c_picks:
                sp = lookup(key, o["name"], "option")
                if sp["level"] != 0 or not lists_ok(sp, cc.get("lists")):
                    raise RulesError(f"{o['name']}: {sp['name']} non è un trucchetto permesso")
                extra_cantrips.append({**sp, "ability": cc.get("ability") or spell_ability})
        if sc:
            want = int(sc.get("count", 1))
            if len(s_picks) < want:
                warnings.append(f"{o['name']}: scegli {want} incantesimi (class_options: {{key: {o['key']}, spells: [...]}}; dati: {len(s_picks)})")
            max_lv = max(int(sc.get("level", 1)), (level + 1) // 2) if sc.get("ritual_only") else int(sc.get("level", 1))
            for key in s_picks:
                sp = lookup(key, o["name"], "option")
                if sp["level"] is None or sp["level"] < 1 or sp["level"] > max_lv or not lists_ok(sp, sc.get("lists")):
                    raise RulesError(f"{o['name']}: {sp['name']} non è permesso (livello massimo {max_lv})")
                if sc.get("ritual_only") and not sp.get("ritual"):
                    raise RulesError(f"{o['name']}: {sp['name']} non è un rituale")
                sp["tag"] = "solo rituale" if sc.get("ritual_only") else "privilegio"
                sp["extra"] = True
                other_spells.append(sp)

    # --- privilegi: incantesimi con il ki e rituali (Arti dell'Ombra, Corpo Vuoto, Cercatore di Spiriti)
    for f in cls["features"]:
        for e in _as_list(f.get("ki_spells")):  # chiave, oppure {key, ki_cost} se costa diverso dal privilegio
            cost = (e.get("ki_cost") if isinstance(e, dict) else None) or f.get("ki_cost")
            sp = lookup(_pick_key(e), f["source"])
            sp.update(ability=ki_ab, tag=f"ki {cost}" if cost else "ki", ki=True, extra=True)
            other_spells.append(sp)
        for key in _as_list(f.get("ritual_only_spells")):
            sp = lookup(key, f["source"])
            sp.update(tag="solo rituale", extra=True)
            other_spells.append(sp)
    if not spell_ability and any(sp.get("ki") for sp in other_spells):
        spell_ability, title = ki_ab, cls["subclass_name"] or cls["name"]

    all_cantrips = racial_cantrips + class_cantrips + extra_cantrips
    if not (all_cantrips or prepared or circle_spells or other_spells or book):
        return None
    if not spell_ability:  # solo rituali senza caratteristica (Guerriero Totemico): niente pagina 3
        return {"ability": None, "other_spells": other_spells}

    # ogni trucchetto/incantesimo porta la propria caratteristica (razziale, di classe, del ki...)
    for sp in all_cantrips + prepared + book + circle_spells + other_spells:
        ab = sp.get("ability") or spell_ability
        sp["ability"] = ab
        sp["attack_bonus"] = prof + mods[ab]
        sp["save_dc"] = 8 + prof + mods[ab]
        sp["other_ability"] = ab != spell_ability
    # i dadi dei trucchetti crescono con il livello: {dadi} nei testi
    for sp in all_cantrips:
        if sp.get("damage"):
            scaled = sp["damage"] if sp.get("scaling") == "beams" else _scale_cantrip(sp["damage"], level)
            sp["damage_scaled"] = scaled
            for fld in ("text", "kid", "tip"):
                if sp.get(fld):
                    sp[fld] = kid_fmt(sp[fld], {"dadi": scaled})

    # --- righe di attacco con gli incantesimi
    bonus_rules = [f["cantrip_damage_bonus"] for f in cls["features"] if f.get("cantrip_damage_bonus")]
    bonus_rules += [o["item"]["cantrip_damage_bonus"] for o in options if o["item"].get("cantrip_damage_bonus")]

    def cantrip_bonus(sp):
        total = 0
        for r in bonus_rules:
            if (sp["key"] in _as_list(r.get("spells"))
                    or (r.get("lists") and set(r["lists"]) & set(sp.get("lists") or []) and sp.get("origin") == "class")):
                total += mods[r.get("ability", spell_ability)]
        return total

    spell_attacks = []
    seen_rows = set()
    for sp in all_cantrips + prepared + circle_spells + [s for s in book if s.get("signature")] + other_spells:
        if not sp.get("damage") or sp["key"] in seen_rows or sp.get("level") is None:
            continue
        is_cantrip = sp["level"] == 0
        if not sp.get("attack") and not (is_cantrip and sp.get("save")):
            continue
        seen_rows.add(sp["key"])
        dice = sp["damage"]
        if is_cantrip and sp.get("scaling") != "beams":
            dice = _scale_cantrip(dice, level)
        mod = mods[sp["ability"]] if sp.get("damage_mod") else 0
        if is_cantrip:
            mod += cantrip_bonus(sp)
        dmg = f"{_dice_with_mod(dice, mod)} {sp.get('damage_type', '')}".strip()
        if sp.get("scaling") == "beams" and _beams(level) > 1:
            dmg += f" x {_beams(level)} raggi (un tiro per raggio)"
        elif sp.get("rays"):
            dmg += f" x {sp['rays']} raggi"
        row = {"name": sp["name"], "key": sp["key"], "damage": dmg, "range": sp.get("range"),
               "attack_str": None, "save_str": None, "save_ability": None, "save_dc": None}
        if sp.get("attack"):
            row["attack_str"] = fmt_mod(sp["attack_bonus"])
        else:
            row.update(save_str=f"TS {ABBR_IT.get(sp['save'], sp['save'])} CD {sp['save_dc']}", save_ability=ABBR_IT.get(sp["save"], sp["save"]),
                       save_dc=sp["save_dc"])
        spell_attacks.append(row)

    by_level: dict[int, list] = {}
    seen_lvl = set()
    for sp in (book or prepared) + circle_spells + other_spells:
        lvl = sp["level"] if sp.get("level") is not None else 1
        mark = (sp["key"], sp.get("tag") if sp.get("extra") else None)
        if lvl == 0 or mark in seen_lvl:
            continue
        seen_lvl.add(mark)
        by_level.setdefault(lvl, []).append(sp)
    # prossimo livello in cui si impara un trucchetto nuovo (per la guida)
    col = None
    if caster:
        full = cls.get("table_full") or {}
        col = full.get("cantrips_known") or full.get("cantrips") or spells_rules["cantrips_known"].get(cls["key"])
    next_cantrip = None
    if isinstance(col, list) and len(col) >= level:
        next_cantrip = next((i + 1 for i in range(level, len(col)) if isinstance(col[i], int) and col[i] > col[level - 1]), None)
    attack_bonus = prof + mods[spell_ability]
    return {
        "ability": spell_ability,
        "ability_name": names[spell_ability]["it"],
        "title": title or cls["name"],
        "save_dc": 8 + attack_bonus,
        "attack_bonus": attack_bonus,
        "cantrips": all_cantrips,
        "spells_by_level": by_level,
        "slots": slots,
        "prepared_max": prepared_max,
        "prepares": bool(caster and (caster.get("prepared") == "ability_plus_level" or caster.get("spellbook"))),
        "ritual": bool(caster and caster.get("ritual")),
        "focus": caster.get("focus") if caster else None,
        "spell_attacks": spell_attacks,
        "class_caster": bool(caster),
        "list": (caster or {}).get("list", cls["key"]) if caster else None,
        "spellbook": bool(book),
        "prepared": prepared,
        "max_level": max(slots) if slots else 0,
        "mod": mods[spell_ability],
        "pact": bool(caster and caster.get("type") == "pact"),
        "schools": schools,
        "any_school_free": any_school_free,
        "expanded": sorted({k for keys in (sub.get("expanded_spells") or {}).values() for k in keys}) if caster else [],
        "other_spells": other_spells,
        "at_will_mage_armor": at_will_mage_armor,
        "next_cantrip_level": next_cantrip,
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
        if b.get("elemental"):
            if row.get("elementals"):
                forms.append({"key": key, **b})
            continue
        if b["cr"] > max_cr:
            continue
        if not row.get("fly") and b["speed"].get("fly"):
            continue
        if not row.get("swim") and b["speed"].get("swim"):
            continue
        forms.append({"key": key, **b})
    forms.sort(key=lambda b: (-b["cr"], b["name"]))
    uses = row.get("uses", 2)
    combat = any(f.get("combat_wild_shape") for f in cls["features"]) or (
        not any("combat_wild_shape" in f for f in cls["features"]) and cls.get("subclass_key") == "moon")
    beasts_only = [b for b in forms if not b.get("elemental")]
    return {"max_cr": max_cr, "max_cr_str": fmt_cr(max_cr), "fly": row.get("fly", False), "swim": row.get("swim", False),
            "uses": "illimitati" if uses is None else uses, "unlimited": uses is None, "duration_hours": max(1, level // 2),
            "forms": forms, "combat": combat, "elementals": bool(row.get("elementals")),
            "top_cr": max((b["cr"] for b in beasts_only), default=0), "level": level}


# ---------------------------------------------------------------------------
# Compagno animale (Signore delle Bestie)
# ---------------------------------------------------------------------------
def resolve_companion(char: dict, cls: dict, prof: int, rules: dict) -> dict | None:
    key = char.get("companion")
    if not key:
        return None
    spec = (cls.get("subclass") or {}).get("companion")
    if not spec:
        raise RulesError("'companion' è il compagno animale del Signore delle Bestie: questa classe/sottoclasse non ce l'ha")
    beasts = rules["beasts"]
    if key not in beasts:
        raise RulesError(f"Compagno animale sconosciuto: {key} (vedi dnd5e/rules/beasts.yaml)")
    b = beasts[key]
    if b["cr"] > float(spec.get("max_cr", 0.25)):
        raise RulesError(f"{b['name']} ha GS {fmt_cr(b['cr'])}: il compagno deve avere GS {fmt_cr(spec.get('max_cr', 0.25))} o meno")
    if _size_rank(b.get("size")) > _size_rank(spec.get("max_size", "Media")):
        raise RulesError(f"{b['name']} è di taglia {b['size']}: il compagno deve essere {spec.get('max_size', 'Media')} o più piccolo")
    add = set(spec.get("add_proficiency") or ["ac", "attack", "damage", "saves", "skills"])
    level = cls["level"]
    attacks = []
    for a in b.get("kid_attacks") or []:
        hit = a.get("hit", "")
        try:
            hit = fmt_mod(int(str(hit).replace("+", "")) + (prof if "attack" in add else 0))
        except ValueError:
            pass
        dmg = _add_to_damage(a.get("damage", ""), prof if "damage" in add else 0) if a.get("damage") not in ("-", "—", None) else a.get("damage")
        attacks.append({**a, "hit": hit, "damage": dmg})
    text = "; ".join(f"{a.get('name', '')} {a['hit']}, {a['damage']} {a.get('type', '')}".strip() for a in attacks) or b.get("attacks", "")
    return {"key": key, "name": b["name"], "size": b.get("size"), "cr": b["cr"], "speed": b.get("speed", {}),
            "ac": b["ac"] + (prof if "ac" in add else 0), "hp": max(int(b["hp"]), int(spec.get("hp_per_ranger_level", 4)) * level),
            "attacks": attacks, "attacks_text": text, "traits": b.get("traits", ""), "kid": b.get("kid", ""),
            "kid_traits": b.get("kid_traits") or [], "prof": prof, "card_kid": spec.get("kid", ""),
            "saves_skills_bonus": prof if ("saves" in add or "skills" in add) else 0}


# ---------------------------------------------------------------------------
# Scheda completa
# ---------------------------------------------------------------------------
def build_sheet(char: dict, rules: dict | None = None) -> dict:
    rules = rules or load_rules()
    warnings: list[str] = []
    skills_rules = rules["skills"]
    female = is_female(char)

    race = resolve_race(char, rules)
    cls = resolve_class(char, rules, warnings)
    background = resolve_background(char, rules)
    feats = iter_feats(char, rules)
    abilities = resolve_abilities(char, race, rules, warnings, cls)
    for _, feat, pick in feats:  # armature dei talenti
        cls["armor"] += [a for a in feat.get("armor_proficiencies", []) if a not in cls["armor"]]
    level = cls["level"]
    prof = skills_rules["proficiency_bonus"][level - 1]
    xp = char.get("xp")
    if xp is None:
        xp = skills_rules["xp_thresholds"][level - 1]
    elif xp < skills_rules["xp_thresholds"][level - 1]:
        warnings.append(f"{xp} PE non bastano per il livello {level}")

    options = resolve_options(char, cls, warnings)
    tools = resolve_tools(char, race, cls, background, rules, warnings)
    skills = resolve_skills(char, race, cls, background, rules, warnings, options, tools)
    tools += [t for t in skills["extra_tools"] if t not in tools]
    if skills["expertise_tools"]:
        tools = [f"{t} (Maestria)" if t in skills["expertise_tools"] else t for t in tools]

    # --- stili di combattimento
    styles = _as_list(char.get("fighting_styles"))
    if char.get("fighting_style"):
        styles.insert(0, char["fighting_style"])
    style_table = rules["equipment"]["fighting_styles"]
    style_feats = [f for f in cls["features"] if f.get("fighting_style")]
    allowed_styles = set()
    for f in style_feats:
        allowed_styles.update(f.get("fighting_style_options") or style_table.keys())
    _check_duplicates(styles, "Stili di combattimento")
    for s in styles:
        if s not in style_table:
            raise RulesError(f"Stile di combattimento sconosciuto: {s}")
        if not style_feats:
            raise RulesError(f"Stile di combattimento {style_table[s]['name']}: {cls['name']} di livello {level}, nessun privilegio dà uno stile")
        if s not in allowed_styles:
            raise RulesError(f"Lo stile {style_table[s]['name']} non è permesso a questa classe ({', '.join(style_table[k]['name'] for k in sorted(allowed_styles))})")
    if style_feats and len(styles) != len(style_feats):
        warnings.append(f"Stili di combattimento: scelti {len(styles)}, al livello {level} ne hai {len(style_feats)} ('fighting_style' e 'fighting_styles')")

    mods = abilities["mods"]
    for _, feat, pick in feats:  # armi dei talenti
        wp = feat.get("weapon_proficiencies")
        cls["weapons"] += [w for w in (wp if isinstance(wp, list) else _as_list(pick.get("weapons"))) if w not in cls["weapons"]]
    save_profs = set(cls["saves"])
    for f in cls["features"]:
        save_profs.update(f.get("save_proficiencies") or [])
    for _, feat, pick in feats:
        if feat.get("save_proficiency_choice"):
            save_profs.add(pick.get("save") or pick.get("ability"))
    saves = {}
    for a in ABILITIES:
        is_prof = a in save_profs
        saves[a] = {"value": mods[a] + (prof if is_prof else 0), "proficient": is_prof}

    # mezza competenza: Factotum (true, per difetto) o Atleta Straordinario (solo FOR/DES/COS, per eccesso)
    half_rules = [f["half_proficiency_checks"] for f in cls["features"] if f.get("half_proficiency_checks")]

    def half(ab):
        best = 0
        for r in half_rules:
            if r is True:
                best = max(best, prof // 2)
            elif isinstance(r, dict) and ab in r.get("abilities", ABILITIES):
                best = max(best, math.ceil(prof / 2) if r.get("round") == "up" else prof // 2)
        return best

    skill_values = {}
    for key, info in skills_rules["skills"].items():
        is_prof = key in skills["proficient"]
        bonus = mods[info["ability"]]
        if is_prof:
            bonus += prof * (2 if key in skills["expertise"] else 1)
        else:
            bonus += half(info["ability"])
        skill_values[key] = {
            "value": bonus, "proficient": is_prof, "expertise": key in skills["expertise"],
            "name": info["it"], "ability": info["ability"], "source": skills["proficient"].get(key),
        }
    passive_perception = 10 + skill_values["perception"]["value"] + sum(int(feat.get("passive_bonus", 0)) for _, feat, _ in feats)

    ac = resolve_ac(char, abilities, cls, race, styles, rules, warnings, feats)
    hp = resolve_hp(char, abilities, cls, race, warnings, rules)
    weapons = resolve_weapons(char, abilities, cls, race, prof, styles, rules, feats)
    spellcasting = resolve_spellcasting(char, cls, race, abilities, prof, rules, warnings, options, feats)
    extra_spells = []
    if spellcasting and spellcasting.get("ability") is None:  # solo rituali, senza pagina 3
        extra_spells = spellcasting["other_spells"]
        spellcasting = None
    wild_shape = resolve_wild_shape(cls, rules)
    companion = resolve_companion(char, cls, prof, rules)

    # --- arma a soffio (dragonide) ---
    breath = None
    anc = race.get("ancestry")
    if anc:
        dice = "2d6" if level < 6 else "3d6" if level < 11 else "4d6" if level < 16 else "5d6"
        breath = {"dc": 8 + mods["con"] + prof, "dice": dice, "type": anc["damage_type"], "area": anc["area"],
                  "save": anc["save"], "save_name": skills_rules["abilities"][anc["save"]]["it"]}

    # --- velocità e iniziativa con privilegi e talenti ---
    heavy = ac.get("category") == "heavy"
    unarmored = not char.get("armor") and not char.get("shield")
    speed_ft = race["speed"]
    for f in cls["features"]:
        if f.get("requires_no_heavy_armor") and heavy:
            continue
        if f.get("requires_unarmored") and not unarmored:
            continue
        speed_ft += float(f.get("speed_bonus", 0)) / 0.3
        col = f.get("speed_bonus_table")
        if col and isinstance(cls["table"].get(col), (int, float)):
            speed_ft += cls["table"][col]
    speed_ft += sum(float(feat.get("speed_bonus", 0)) / 0.3 for _, feat, _ in feats)
    initiative = mods["dex"] + int(char.get("initiative_bonus", 0)) + sum(int(feat.get("initiative_bonus", 0)) for _, feat, _ in feats)
    initiative += half("dex")
    initiative_advantage = any(f.get("initiative_advantage") for f in cls["features"])

    # --- manovre (Maestro di Battaglia, Adepto Marziale) ---
    maneuver_keys = _as_list(char.get("maneuvers"))
    _check_duplicates(maneuver_keys, "maneuvers")
    is_bm = "maneuvers_known" in cls["table"]
    adept = [feat for _, feat, _ in feats if feat.get("maneuver_choice")]
    maneuver_info = None
    if maneuver_keys and not (is_bm or adept):
        raise RulesError("Le manovre servono al Maestro di Battaglia (dal 3° livello) o a chi ha il talento Adepto Marziale")
    if is_bm or adept:
        want = int(cls["table"].get("maneuvers_known") or 0) + sum(int(f["maneuver_choice"].get("count", 2)) for f in adept)
        if len(maneuver_keys) != want:
            warnings.append(f"Manovre: scelte {len(maneuver_keys)}, al livello {level} ne conosci {want} ('maneuvers')")
        n_dice = int(cls["table"].get("superiority_dice") or 0) + sum(int((f.get("superiority_dice") or {}).get("count", 1)) for f in adept)
        die = cls["table"].get("superiority_die") or next(((f.get("superiority_dice") or {}).get("die", "d6") for f in adept), "d6")
        maneuver_info = {"dc": 8 + prof + max(mods["str"], mods["dex"]), "dice": n_dice, "die": die}

    # --- segnaposto per i testi semplici ---
    hours = wild_shape["duration_hours"] if wild_shape else 0
    placeholders = {"livello": level, "forma_ore": f"{hours} {'ora' if hours == 1 else 'ore'}" if hours else ""}
    placeholders.update(gender_values(female))
    if spellcasting:
        placeholders.update(cd=spellcasting["save_dc"], att=fmt_mod(spellcasting["attack_bonus"]), mod=fmt_mod(spellcasting["mod"]))
    for col, val in cls["table"].items():
        placeholders[f"t_{col}"] = "illimitati" if val == 99 else val
    ki = None
    if cls.get("ki_save") and not (spellcasting and spellcasting["class_caster"]):
        ab = cls["ki_save"].get("ability", "wis")
        placeholders.update(cd=8 + prof + mods[ab], mod=fmt_mod(mods[ab]))
        unarmed = next((w for w in weapons if w["key"] == "unarmed_strike"), None)
        ki = {"points": cls["table"].get("ki", 0), "dc": 8 + prof + mods[ab], "ability": ab,
              "attack_str": unarmed["attack_str"] if unarmed else None,
              "damage": unarmed["damage"] if unarmed else None}
    sdc = (cls.get("subclass") or {}).get("save_dc")
    if sdc:
        placeholders[sdc.get("placeholder", "cd")] = 8 + prof + mods[sdc.get("ability", "cha")]
    if maneuver_info:
        placeholders["cd_manovre"] = maneuver_info["dc"]
        placeholders.setdefault("t_superiority_die", maneuver_info["die"])
        placeholders.setdefault("t_superiority_dice", maneuver_info["dice"])
    if wild_shape:
        placeholders["forma_gs"] = wild_shape["max_cr_str"]
    if breath:
        placeholders.update(soffio_cd=breath["dc"], soffio_danni=breath["dice"], soffio_tipo=breath["type"],
                            soffio_area=breath["area"], soffio_ts=breath["save_name"])

    # --- privilegi e tratti ---
    features = []

    def add_feature(entry: dict, where: str):
        out = {**entry}
        for fld in ("short", "text", "kid"):
            out[fld] = kid_fmt(entry.get(fld, ""), placeholders)
        out.setdefault("kid_hide", False)
        if out.get("sheet_hide") is None:
            out["sheet_hide"] = out["kid_hide"]
        for ph in unresolved_placeholders(out["short"], out["text"], out["kid"]):
            warnings.append(f"Segnaposto non risolto {{{ph}}} in {where}")
        features.append(out)

    for t in race["traits"]:
        add_feature({"name": t["name"], "short": t.get("short", ""), "text": t.get("text", ""), "kid": t.get("kid", ""),
                     "source": race["name"], "level": None, "kind": "race", "kid_hide": t.get("kid_hide", False),
                     "sheet_hide": t.get("sheet_hide")}, t["name"])
    for f in cls["features"]:
        add_feature({"name": f["name"], "short": f.get("short", ""), "text": f.get("text", ""), "kid": f.get("kid", ""),
                     "source": f["source"], "level": f["level"], "kind": "class", "base_name": f.get("base_name"),
                     "kid_hide": f.get("kid_hide", False), "sheet_hide": f.get("sheet_hide")}, f["name"])
    # riepilogo degli aumenti di caratteristica scelti (al posto delle righe ripetute)
    asi_parts = []
    for e in (char.get("abilities", {}) or {}).get("asi", []) or []:
        vals = [f"{ABBR_IT[k]} +{v}" for k, v in e.items() if k in ABILITIES]
        asi_parts.append(" e ".join(vals) + (f" ({e['level']}°)" if e.get("level") else ""))
    if asi_parts:
        add_feature({"name": "Aumenti di caratteristica", "short": "; ".join(asi_parts) + ".", "text": "; ".join(asi_parts) + ".",
                     "kid": "", "source": cls["name"], "level": None, "kind": "asi", "kid_hide": True, "sheet_hide": False},
                    "Aumenti di caratteristica")
    # opzioni di classe scelte (suppliche, metamagia, nemico prescelto, discipline...)
    opt_features = []
    for o in options:
        item = o["item"]
        opt_features.append({"name": o["name"], "short": item.get("short", ""), "text": item.get("text", ""), "kid": item.get("kid", ""),
                             "source": o["label"], "level": o["level"], "kind": "option", "base_name": item.get("name"),
                             "replaces": item.get("replaces"), "kid_hide": item.get("kid_hide", False), "sheet_hide": item.get("sheet_hide")})
    for f in opt_features:
        gone = set(_as_list(f.get("replaces")))
        if gone:  # un'opzione può sostituire un privilegio o un'opzione precedente
            features = [g for g in features if g.get("kind") not in ("class", "option") or g.get("base_name", g["name"]) not in gone]
        add_feature(f, f["name"])
    for key, feat, pick in feats:
        add_feature({"name": feat_label(feat, pick, rules), "short": feat.get("short", ""), "text": feat.get("text", ""),
                     "kid": feat.get("kid", ""), "source": "Talento", "level": None, "kind": "feat",
                     "kid_hide": False, "sheet_hide": False}, feat["name"])
    style_descriptions = []
    for s in styles:
        st = style_table[s]
        style_descriptions.append({"name": f"Stile di Combattimento: {st['name']}", "short": st["text"], "text": st["text"],
                                   "source": cls["name"], "kid": kid_fmt(st.get("kid", ""), placeholders)})
    maneuvers = []
    for m in maneuver_keys:
        if m not in rules["maneuvers"]:
            raise RulesError(f"Manovra sconosciuta: {m}")
        mm = dict(rules["maneuvers"][m])
        mm["key"] = m
        mm["kid"] = kid_fmt(mm.get("kid", ""), placeholders)
        maneuvers.append(mm)
    bg_feature = None
    if background.get("feature"):
        bg_text = kid_fmt(background["feature"]["text"], placeholders)
        bg_feature = {"name": f"{background['feature']['name']} (background)", "short": bg_text, "text": bg_text,
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
    lang_names = skills_rules["languages"]
    languages = [lang_names.get(l, l) for l in race["languages"]]
    extra_langs = _as_list(char.get("languages_extra"))
    allowed_extra = race["extra_languages"] + int(background.get("languages", 0))
    allowed_extra += sum(int(f.get("extra_languages", 0)) for f in cls["features"]) + sum(int(feat.get("languages", 0)) for _, feat, _ in feats)
    for f in cls["features"]:
        languages += [lang_names.get(l, l) for l in f.get("languages", []) if lang_names.get(l, l) not in languages]
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

    mage_armor = bool(spellcasting and (spellcasting.get("at_will_mage_armor")
                                        or any(s.get("key") == "mage_armor" for s in spellcasting["prepared"])))
    surge = (cls.get("subclass") or {}).get("surge_table")
    return {
        "name": char.get("name", ""),
        "player": char.get("player", ""),
        "race": race,
        "class": cls,
        "class_level": f"{cls['name']} {level}",
        "subclass_name": cls["subclass_name"],
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
        "initiative": initiative,
        "initiative_advantage": initiative_advantage,
        "speed": speed_ft,
        "speed_m": f"{round(speed_ft * 0.3, 1):g} m".replace(".", ","),
        "hp": hp,
        "weapons": weapons,
        "features": features,
        "fighting_styles": style_descriptions,
        "maneuvers": maneuvers,
        "maneuver_info": maneuver_info,
        "ki": ki,
        "background_feature": bg_feature,
        "proficiencies": {"armor": armor_prof, "weapons": weapon_prof, "tools": tools},
        "languages": languages,
        "equipment": equipment,
        "money": money,
        "spellcasting": spellcasting,
        "cantrips": spellcasting["cantrips"] if spellcasting else [],
        "extra_spells": extra_spells,
        "wild_shape": wild_shape,
        "companion": companion,
        "surge_table": surge,
        "personality": char.get("personality", {}) or {},
        "appearance": char.get("appearance", {}) or {},
        "backstory": char.get("backstory", "") or "",
        "allies": char.get("allies", "") or "",
        "treasure": char.get("treasure", "") or "",
        "extra_features": char.get("extra_features", "") or "",
        "attacks_notes": char.get("attacks_notes", "") or "",
        "portrait": str(portrait) if portrait else None,
        "breath": breath,
        "mage_armor_ac": (13 + mods["dex"]) if (not char.get("armor") and mage_armor) else None,
        "placeholders": placeholders,
        "female": female,
        "simple": bool(char.get("simple")),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Riepilogo testuale (Markdown)
# ---------------------------------------------------------------------------
def spell_label_tags(s: dict, sp: dict) -> str:
    """Etichette dopo il nome di un incantesimo: (C), (R), [dominio], [ki 2], (senza slot)..."""
    out = " (C)" if s.get("conc") else ""
    if s.get("ritual") and (sp.get("ritual") or s.get("tag") == "solo rituale"):
        out += " (R)"
    if s.get("tag"):
        out += f" [{s['tag']}]"
    if s.get("mastery"):
        out += " (senza slot)"
    return out


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
              f"- Iniziativa: {fmt_mod(sheet['initiative'])}" + (" (vantaggio)" if sheet.get("initiative_advantage") else "")
              + f" · Velocità: {sheet['speed_m']}",
              f"- PF massimi: {sheet['hp']['max']} ({sheet['hp']['detail']}) · Dadi vita: {sheet['hp']['hit_dice']}",
              f"- Percezione passiva: {sheet['passive_perception']}"]
    if sheet.get("mage_armor_ac"):
        lines.append(f"- CA con Armatura Magica: {sheet['mage_armor_ac']}")
    b = sheet.get("breath")
    if b:
        lines.append(f"- Arma a soffio: {b['area']}, TS {b['save_name']} CD {b['dc']}, {b['dice']} {b['type']} (metà se supera), 1 volta per riposo breve o lungo")
    ki = sheet.get("ki")
    if ki:
        lines.append(f"- Ki: {ki['points']} punti, CD {ki['dc']}" + (f", colpo senz'armi {ki['attack_str']}, {ki['damage']}" if ki.get("attack_str") else ""))
    mi = sheet.get("maneuver_info")
    if mi:
        lines.append(f"- Manovre: CD {mi['dc']}, {mi['dice']} dadi di superiorità ({mi['die']})")
    lines.append("")
    lines += ["## Abilità", ""]
    for k, s in sorted(sheet["skills"].items(), key=lambda kv: kv[1]["name"]):
        mark = " ● " + (s["source"] or "") if s["proficient"] else ""
        if k == "stealth" and sheet["ac"].get("stealth_disadvantage"):
            mark += " (svantaggio per l'armatura)"
        lines.append(f"- {s['name']} ({ABBR_IT[s['ability']]}): {fmt_mod(s['value'])}{mark}")
    lines += ["", "## Attacchi", ""]
    for w in sheet["weapons"]:
        lines.append(f"- {w['name']}: {w['attack_str']} per colpire, {w['damage']}" + (f" ({', '.join(w['properties'] + w['notes'])})" if w["properties"] or w["notes"] else ""))
    sp = sheet["spellcasting"]
    if sp:
        for at in sp["spell_attacks"]:
            how = f"{at['attack_str']} per colpire" if at.get("attack_str") else at.get("save_str", "")
            rng = (f", gittata {at['range']}" + (" m" if str(at['range'])[:1].isdigit() else "")) if at.get("range") else ""
            lines.append(f"- {at['name']} (incantesimo): {how}, {at['damage']}{rng}")
    comp = sheet.get("companion")
    if comp:
        lines.append(f"- Compagno animale, {comp['name']}: CA {comp['ac']}, PF {comp['hp']}; {comp['attacks_text']}")
    if sp:
        lines += ["", "## Incantesimi", "",
                  f"- Caratteristica: {sp['ability_name']} · CD tiro salvezza {sp['save_dc']} · attacco con incantesimo {fmt_mod(sp['attack_bonus'])}"]
        if sp["slots"]:
            lines.append("- Slot: " + ", ".join(f"{n} di {lvl}°" for lvl, n in sp["slots"].items()))
        if sp["prepared_max"]:
            lines.append(f"- Incantesimi preparabili: {sp['prepared_max']}")
        if sp["cantrips"]:
            lines.append("- Trucchetti: " + ", ".join(f"{c['name']} ({c['source']}" + (f", {ABBR_IT[c['ability']]}: CD {c['save_dc']}, attacco {fmt_mod(c['attack_bonus'])}" if c.get("other_ability") else "") + ")" for c in sp["cantrips"]))
        for lvl in sorted(sp["spells_by_level"]):
            lines.append(f"- {lvl}° livello: " + ", ".join(s["name"] + spell_label_tags(s, sp)
                                                       + (f" ({ABBR_IT[s['ability']]}: CD {s['save_dc']})" if s.get("other_ability") else "")
                                                       + (" [nel libro, non preparato]" if s.get("prepared") is False and not s.get("always_prepared") else "")
                                                       for s in sp["spells_by_level"][lvl]))
    if sheet.get("extra_spells"):
        lines += ["", "## Incantesimi da privilegi", ""]
        lines.append("- " + ", ".join(f"{s['name']} ({s.get('level')}° livello) [{s.get('tag', '')}]" for s in sheet["extra_spells"]))
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
