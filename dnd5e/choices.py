"""Scelte ancora da fare: cosa deve scegliere un personaggio per la sua razza, classe, livello e background.

`requirements(char, rules)` legge gli stessi dati di regole del motore (`dnd5e/rules/*.yaml`) e restituisce
un dizionario con il numero di scelte richieste e le opzioni possibili, per esempio:

    {"class_skills": {"count": 2, "from": [...]},
     "cantrips": {"count": 3, "lists": ["wizard"]},
     "spells": {"mode": "prepared", "count": 5, "max_level": 2, "list": "wizard", ...},
     "spellbook": {"count": 10}, ...}

Serve alla pagina web per guidare la creazione passo per passo. Funziona anche con un personaggio
incompleto (senza razza o senza classe): le parti che mancano restano semplicemente vuote, non
solleva mai eccezioni per dati parziali. Le chiavi con zero scelte non compaiono.
"""
from __future__ import annotations

from .engine import ABILITIES, ability_mod, is_female

# Numero di manovre del Maestro di Battaglia (PHB p. 73): 3 al 3° livello, +2 al 7°, 10° e 15°.
# Si usa solo se i dati della sottoclasse non hanno una colonna `maneuvers_known`.
BATTLE_MASTER_MANEUVERS = {3: 3, 7: 5, 10: 7, 15: 9}

# Incantesimi conosciuti dal PHB, usati solo se la classe nei dati non ha la colonna `spells_known`.
FALLBACK_SPELLS_KNOWN = {
    "third": [0, 0, 3, 4, 4, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 11, 11, 12, 13],
    "warlock": [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15],
}

SPELL_LISTS = ["bard", "cleric", "druid", "paladin", "ranger", "sorcerer", "warlock", "wizard"]

# taglie dalla più piccola (come engine.SIZE_ORDER): per il compagno animale del Signore delle Bestie
SIZE_ORDER = ["minusc", "picc", "medi", "grand", "enorm", "mastod"]


def _size_rank(size) -> int:
    s = str(size or "").lower()
    return next((i for i, p in enumerate(SIZE_ORDER) if s.startswith(p)), 2)


# "Tre strumenti musicali a scelta" -> 3 (come engine._placeholder_count)
NUMBER_WORDS = {"un": 1, "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4}


def _placeholder_count(text) -> int:
    s = str(text or "").lower()
    if "a scelta" not in s:
        return 0
    words = s.split()
    return NUMBER_WORDS.get(words[0], 1) if words else 1


def _tool_category(text) -> str | None:
    """Gruppo di strumenti (equipment.yaml > tools) da proporre, dedotto dal testo quando le regole non lo dicono:
    "Tre strumenti musicali a scelta" -> musical; "strumenti da artigiano o uno strumento musicale" -> artisan+musical."""
    s = str(text or "").lower()
    cats = [c for c, words in (("artisan", ("artigian",)), ("musical", ("musical",)), ("gaming", ("gioco", "giochi")))
            if any(w in s for w in words)]
    return "+".join(cats) or None


def _tool_slots(count: int, label: str, category=None) -> list:
    category = category or _tool_category(label)
    return [{"label": label, "category": category} for _ in range(max(0, count))]


# ---------------------------------------------------------------------------
# piccoli aiuti tolleranti
# ---------------------------------------------------------------------------
def _as_list(value) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _key(value):
    """Chiave di regole valida (stringa non vuota) o None."""
    return value if isinstance(value, str) and value else None


def _name(entry, female: bool, default: str = "") -> str:
    if not isinstance(entry, dict):
        return default
    if female and entry.get("name_f"):
        return entry["name_f"]
    return entry.get("name", default)


def _option(key, entry, female: bool) -> dict:
    out = {"key": key, "name": _name(entry, female, str(key))}
    if isinstance(entry, dict):
        for field in ("short", "kid"):
            if entry.get(field):
                out[field] = entry[field]
    return out


def _at_level(column, level: int):
    if isinstance(column, list) and len(column) >= level:
        return column[level - 1]
    return None


# ---------------------------------------------------------------------------
# razza
# ---------------------------------------------------------------------------
def _race_info(char: dict, rules: dict, female: bool) -> dict | None:
    races = rules.get("races") or {}
    race_key = _key(char.get("race"))
    race = races.get(race_key) if race_key else None
    if not isinstance(race, dict):
        return None
    subraces = race.get("subraces") or {}
    variants = race.get("variants") or {}
    pools = {**subraces, **variants}
    info = {
        "key": race_key,
        "ability_bonus": dict(race.get("ability_bonus") or {}),
        "ability_choice": race.get("ability_choice"),
        "languages": list(race.get("languages") or []),
        "extra_languages": _int(race.get("extra_languages")),
        "traits": list(race.get("traits") or []),
        "subrace_required": bool(subraces),
        "subrace_options": [_option(k, v, female) for k, v in pools.items()],
        "subrace_ok": False,
        "ancestry": race.get("ancestry") or {},
    }
    sub_key = _key(char.get("subrace"))
    sub = pools.get(sub_key) if sub_key else None
    if isinstance(sub, dict):
        info["subrace_ok"] = True
        if sub.get("replaces_base_bonus"):
            info["ability_bonus"] = {}
        for k, v in (sub.get("ability_bonus") or {}).items():
            info["ability_bonus"][k] = info["ability_bonus"].get(k, 0) + _int(v)
        if "ability_choice" in sub:
            info["ability_choice"] = sub["ability_choice"]
        if sub.get("replaces_traits"):
            info["traits"] = []
            info["extra_languages"] = 0
        info["traits"] += list(sub.get("traits") or [])
        info["extra_languages"] += _int(sub.get("extra_languages"))
    for trait in info["traits"]:
        if isinstance(trait, dict):
            info["extra_languages"] += _int(trait.get("extra_languages"))
    info["traits"] = [t for t in info["traits"] if isinstance(t, dict)]
    return info


# ---------------------------------------------------------------------------
# classe
# ---------------------------------------------------------------------------
def _class_info(char: dict, rules: dict, level: int, female: bool) -> dict | None:
    classes = rules.get("classes") or {}
    key = _key(char.get("class"))
    cls = classes.get(key) if key else None
    if not isinstance(cls, dict):
        return None
    features = []
    for lvl, flist in sorted((cls.get("features") or {}).items(), key=lambda kv: _int(kv[0])):
        if _int(lvl) <= level:
            features += [{**f, "_level": _int(lvl)} for f in _as_list(flist) if isinstance(f, dict)]
    subs = cls.get("subclasses") or {}
    sub_level = _int(cls.get("subclass_level"), 99)
    sub_key = _key(char.get("subclass"))
    subclass = subs.get(sub_key) if (sub_key and level >= sub_level) else None
    if not isinstance(subclass, dict):
        subclass = None
    if subclass:
        for lvl, flist in sorted((subclass.get("features") or {}).items(), key=lambda kv: _int(kv[0])):
            if _int(lvl) <= level:
                features += [{**f, "_level": _int(lvl)} for f in _as_list(flist) if isinstance(f, dict)]
    columns = dict(cls.get("table") or {})
    columns.update((subclass or {}).get("table") or {})
    table = {k: _at_level(v, level) for k, v in columns.items() if _at_level(v, level) is not None}
    option_lists = dict(cls.get("option_lists") or {})
    option_lists.update((subclass or {}).get("option_lists") or {})
    spellcasting = cls.get("spellcasting")
    if subclass and subclass.get("spellcasting"):
        spellcasting = subclass["spellcasting"]
    return {
        "key": key,
        "data": cls,
        "features": features,
        "subclass": subclass,
        "subclass_key": sub_key if subclass else None,
        "subclass_level": sub_level,
        "subclasses": subs,
        "table": table,
        "option_lists": option_lists,
        "spellcasting": spellcasting if isinstance(spellcasting, dict) else None,
    }


# ---------------------------------------------------------------------------
# background
# ---------------------------------------------------------------------------
def _background_info(char: dict, rules: dict) -> dict | None:
    bg = char.get("background")
    if isinstance(bg, dict):  # background personalizzato scritto nel personaggio
        return bg
    key = _key(bg)
    data = (rules.get("backgrounds") or {}).get(key) if key else None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# talenti scelti (solo quelli validi)
# ---------------------------------------------------------------------------
def _feats(char: dict, rules: dict) -> list:
    table = rules.get("feats") or {}
    out = []
    for entry in _as_list(char.get("feats")):
        pick = entry if isinstance(entry, dict) else {"key": entry}
        feat = table.get(pick.get("key")) if isinstance(pick.get("key"), str) else None
        if isinstance(feat, dict):
            out.append((pick["key"], feat, pick))
    return out


# ---------------------------------------------------------------------------
# punteggi (per il numero di incantesimi preparati)
# ---------------------------------------------------------------------------
def _scores(char: dict, race: dict | None, feats: list) -> dict:
    spec = char.get("abilities") if isinstance(char.get("abilities"), dict) else {}
    base = spec.get("base") if isinstance(spec.get("base"), dict) else {}
    scores = {k: _int(base.get(k), 10) for k in ABILITIES}
    if race:
        for k, v in race["ability_bonus"].items():
            if k in scores:
                scores[k] += _int(v)
        choice = race.get("ability_choice") or {}
        for k in set(_as_list(spec.get("racial_choice"))):
            if k in scores and k not in (choice.get("exclude") or []):
                scores[k] += _int(choice.get("bonus"), 1)
    for asi in _as_list(spec.get("asi")):
        if isinstance(asi, dict):
            for k, v in asi.items():
                if k in scores:
                    scores[k] += _int(v)
    for _, feat, pick in feats:
        for k, v in (feat.get("ability_bonus") or {}).items():
            if k in scores:
                scores[k] += _int(v)
        ch = feat.get("ability_choice")
        if ch and pick.get("ability") in scores:
            scores[pick["ability"]] += _int(ch.get("bonus"), 1)
    return scores


# ---------------------------------------------------------------------------
# incantesimi
# ---------------------------------------------------------------------------
def _slots(rules: dict, caster_type: str, level: int) -> dict:
    table = ((rules.get("spells") or {}).get("slots") or {}).get(caster_type) or {}
    row = table.get(level) if isinstance(table, dict) else None
    if isinstance(row, dict):  # magia del patto
        return {_int(row.get("level")): _int(row.get("slots"))} if row.get("slots") else {}
    return {i + 1: n for i, n in enumerate(row or []) if n}


def _spell_requirements(char, rules, cls, scores, level, female, req) -> None:
    caster = cls["spellcasting"]
    if not caster:
        granted = [f["grants_cantrip"] for f in cls["features"] if f.get("grants_cantrip")]
        if granted:
            req["granted_cantrips"] = granted
        return
    spells_rules = rules.get("spells") or {}
    caster_type = caster.get("type", "full")
    list_key = caster.get("list", cls["key"])
    ability = caster.get("ability")
    slots = _slots(rules, caster_type, level)
    max_level = max(slots) if slots else 0
    features = cls["features"]
    sub = cls["subclass"] or {}

    # --- trucchetti ---
    known = spells_rules.get("cantrips_known") or {}
    known_table = known.get(cls["key"]) or known.get(caster_type)
    expected = _at_level(known_table, level)
    for col in ("cantrips_known", "cantrips"):
        if isinstance(cls["table"].get(col), int):
            expected = cls["table"][col]
    bonus = sum(_int(f.get("cantrip_bonus")) for f in features)
    extra = []
    for f in features:
        ch = f.get("cantrip_choice")
        if isinstance(ch, dict) and ch.get("list"):
            n = _int(ch.get("count"), 1)
            bonus += n
            extra.append({"list": ch["list"], "count": n, "ability": ch.get("ability", ability), "source": f.get("name")})
    granted = [f["grants_cantrip"] for f in features if f.get("grants_cantrip")]
    if expected is not None and (expected + bonus) > 0:
        req["cantrips"] = {
            "count": expected + bonus,
            "lists": [list_key] + [e["list"] for e in extra if e["list"] != list_key],
            "list": list_key,
            "ability": ability,
        }
        if extra:
            req["cantrips"]["extra"] = extra
        if granted:
            req["cantrips"]["granted"] = granted
    elif granted:
        req["granted_cantrips"] = granted

    # --- incantesimi preparati / conosciuti / libro ---
    mod = ability_mod(scores.get(ability, 10)) if ability in scores else 0
    prepared = caster.get("prepared")
    spell = {"list": list_key, "max_level": max_level, "ability": ability,
             "slots": {str(k): v for k, v in slots.items()}}
    if caster.get("spellbook"):
        spell["mode"] = "spellbook"
        req["spellbook"] = {"count": 6 + 2 * (level - 1), "max_level": max_level, "list": list_key}
        # Maestria negli Incantesimi (18°): uno di 1° e uno di 2° dal libro; Incantesimi Personali (20°): due di 3°
        if level >= 18:
            req["spell_mastery"] = {"count": 2, "levels": [1, 2]}
        if level >= 20:
            req["signature_spells"] = {"count": 2, "level": 3}
    elif prepared == "ability_plus_level":
        spell["mode"] = "prepared"
    else:
        spell["mode"] = "known"
    if spell["mode"] in ("spellbook", "prepared"):
        count = max(1, mod + (level if caster_type == "full" else level // 2)) if slots else 0
        spell["formula"] = f"modificatore ({mod:+d}) + {'livello' if caster_type == 'full' else 'metà del livello'}"
    else:
        col = cls["table"].get("spells_known")
        if not isinstance(col, int):
            col = _at_level(FALLBACK_SPELLS_KNOWN.get(cls["key"]) or FALLBACK_SPELLS_KNOWN.get(caster_type), level)
        count = (col + sum(_int(f.get("bonus_spells_known")) for f in features)) if isinstance(col, int) else None
        if not slots:
            count = 0
    spell["count"] = count
    always = []
    for lvl in sorted((sub.get("always_prepared") or {}), key=_int):
        if _int(lvl) <= level:
            always += [k for k in _as_list(sub["always_prepared"][lvl]) if k not in always]
    spell["always_prepared"] = always
    if sub.get("circle_spells"):
        terrain = char.get("circle_terrain")
        names = []
        for lvl, lst in sorted(((sub["circle_spells"].get(terrain) or {}) if isinstance(terrain, str) else {}).items(), key=lambda kv: _int(kv[0])):
            if _int(lvl) <= level:
                names += _as_list(lst)
        if names:
            spell["circle_spells"] = names
    expanded = []
    spell_table = spells_rules.get("spells") or {}
    for lvl, keys in sorted((sub.get("expanded_spells") or {}).items(), key=lambda kv: _int(kv[0])):
        for k in _as_list(keys):  # solo quelli che può già lanciare
            sp_level = (spell_table.get(k) or {}).get("level")
            if k not in expanded and (not isinstance(sp_level, int) or sp_level <= max_level):
                expanded.append(k)
    # Arcanum Mistico del warlock: 1 incantesimo per ognuno di questi livelli, da mettere anch'esso in `spells`
    arcanum = sorted({_int(f["arcanum_level"]) for f in features if f.get("arcanum_level")})
    if arcanum:
        spell["arcanum_levels"] = arcanum
    secrets = sum(_int(f.get("magical_secrets")) for f in features)
    extra_lists = []
    if expanded:
        spell["expanded"] = expanded
    if secrets:
        spell["magical_secrets"] = secrets
        extra_lists = [l for l in SPELL_LISTS if l != list_key]
    if extra_lists:
        spell["extra_lists"] = extra_lists
    if caster.get("schools"):
        any_school = [l for l in _as_list(caster.get("any_school_levels")) if _int(l) <= level]
        spell["schools"] = {"allowed": list(caster["schools"]), "any_school_count": len(any_school)}
    if count or max_level:
        req["spells"] = spell


# ---------------------------------------------------------------------------
# funzione principale
# ---------------------------------------------------------------------------
def requirements(char: dict, rules: dict) -> dict:
    """Le scelte richieste al personaggio (vedi il docstring del modulo). Non solleva eccezioni per dati parziali."""
    char = char if isinstance(char, dict) else {}
    rules = rules or {}
    female = is_female(char)
    level = min(20, max(1, _int(char.get("level"), 1)))
    skills_rules = rules.get("skills") or {}
    all_skills = list((skills_rules.get("skills") or {}).keys())
    req: dict = {"level": level}
    prof_table = skills_rules.get("proficiency_bonus") or []
    if len(prof_table) >= level:
        req["proficiency_bonus"] = prof_table[level - 1]

    race = _race_info(char, rules, female)
    cls = _class_info(char, rules, level, female)
    bg = _background_info(char, rules)
    feats = _feats(char, rules)
    scores = _scores(char, race, feats)
    fixed_skills: dict[str, str] = {}

    # ---------------- razza ----------------
    if race:
        if race["subrace_options"]:
            req["subrace"] = {"required": race["subrace_required"], "options": race["subrace_options"]}
        choice = race.get("ability_choice")
        if isinstance(choice, dict) and _int(choice.get("count")):
            req["racial_choice"] = {"count": _int(choice["count"]), "bonus": _int(choice.get("bonus"), 1),
                                    "exclude": list(choice.get("exclude") or [])}
        racial_skill_count = 0
        racial_tool_slots = []
        feat_choice = 0
        fixed_cantrips = []
        for t in race["traits"]:
            for s in _as_list(t.get("skills")):
                fixed_skills.setdefault(s, "razza")
            racial_skill_count += _int(t.get("skill_choice"))
            racial_tool_slots += _tool_slots(_int(t.get("tool_choice")), f"{t.get('name', 'Razza')}: strumento a scelta",
                                             t.get("tool_choice_category"))
            feat_choice += _int(t.get("feat_choice"))
            fixed_cantrips += _as_list(t.get("fixed_cantrips"))
            ch = t.get("cantrip_choice")
            if isinstance(ch, dict):
                req["racial_cantrip"] = {"count": 1, "list": ch.get("list"), "ability": ch.get("ability"),
                                         "source": t.get("name")}
        if racial_skill_count:
            req["racial_skills"] = {"count": racial_skill_count, "from": all_skills}
        if fixed_cantrips:
            req["racial_cantrips_fixed"] = fixed_cantrips
        if feat_choice:
            req["feat_choice"] = {"count": feat_choice}
        req["_racial_tools"] = racial_tool_slots
        if race["ancestry"]:
            req["draconic_ancestry_options"] = [
                {"key": k, "name": v.get("name", k), "damage_type": v.get("damage_type"), "area": v.get("area"), "save": v.get("save")}
                for k, v in race["ancestry"].items() if isinstance(v, dict)]
    req["draconic_ancestry"] = bool(race and race["ancestry"])

    # ---------------- background ----------------
    bg_skills = _as_list((bg or {}).get("skills"))
    if bg is not None:
        if bg_skills:
            req["background_skills"] = {"count": len(bg_skills), "default": bg_skills, "from": all_skills}
        chosen_bg = _as_list(char.get("background_skills")) if char.get("background_skills") else bg_skills
        for s in chosen_bg:
            fixed_skills.setdefault(s, "background")
        # 'background_tools' sul personaggio = elenco completo: fissi + scelti (come engine.resolve_tools)
        bg_tools = _as_list(bg.get("tools"))
        fixed = [t for t in bg_tools if not _placeholder_count(t)]
        slots = []
        for t in bg_tools:
            slots += _tool_slots(_placeholder_count(t), t)
        for ch in _as_list(bg.get("tool_choices")):
            if isinstance(ch, dict):
                slots += _tool_slots(_int(ch.get("count"), 1), ch.get("label", "Strumento a scelta"), ch.get("category"))
        if bg_tools or slots:
            req["background_tools"] = {"default": fixed, "fixed": fixed, "choices": slots,
                                       "to_choose": [s["label"] for s in slots], "count": len(fixed) + len(slots)}

    # ---------------- classe ----------------
    extra_skill_sources = []
    expertise_count = 0
    expertise_from = None
    class_tool_slots = []
    feature_tool_slots = []
    if cls:
        data = cls["data"]
        pool = data.get("skill_choices") or {}
        if _int(pool.get("count")):
            req["class_skills"] = {"count": _int(pool["count"]), "from": list(pool.get("from") or all_skills)}
        subs = cls["subclasses"]
        if subs or data.get("subclass_level"):
            req["subclass"] = {
                "required": level >= cls["subclass_level"],
                "level": cls["subclass_level"],
                "label": data.get("subclass_label") or "Sottoclasse",
                "options": [_option(k, v, female) for k, v in subs.items()],
            }
        sub = cls["subclass"] or {}
        if sub.get("circle_spells"):
            req["circle_terrain_options"] = list(sub["circle_spells"].keys())
            if sub.get("choice_label"):
                req["circle_terrain_label"] = sub["choice_label"]
        req["circle_terrain"] = bool(sub.get("circle_spells"))
        comp = sub.get("companion")
        if isinstance(comp, dict):  # Signore delle Bestie: una bestia di GS e taglia limitati
            try:
                max_cr = float(comp.get("max_cr", 0.25))
            except (TypeError, ValueError):
                max_cr = 0.25
            max_size = comp.get("max_size", "Media")
            beasts = rules.get("beasts") or {}
            opts = []
            for k, b in beasts.items():
                if not isinstance(b, dict):
                    continue
                try:
                    cr = float(b.get("cr", 99))
                except (TypeError, ValueError):
                    continue
                if cr <= max_cr and _size_rank(b.get("size")) <= _size_rank(max_size):
                    opts.append({"key": k, "name": b.get("name", k), "cr": b.get("cr"), "size": b.get("size")})
            req["companion"] = {"max_cr": max_cr, "max_size": max_size, "examples": _as_list(comp.get("examples")), "options": opts}
        features = cls["features"]
        style_count = 0
        style_options: list = []
        for f in features:
            bp = f.get("bonus_proficiencies") or {}
            for s in _as_list(bp.get("skills")):
                fixed_skills.setdefault(s, "privilegio")
            sc = bp.get("skill_choice")
            if isinstance(sc, dict) and _int(sc.get("count")):
                extra_skill_sources.append({"source": f.get("name"), "count": _int(sc["count"]), "from": list(sc.get("from") or [])})
            expertise_count += _int(f.get("expertise_count"))
            if f.get("expertise_from"):
                expertise_from = list(f["expertise_from"])
            if isinstance(f.get("tool_choice"), int):  # es. Studioso di Guerra: uno strumento da artigiano
                feature_tool_slots += _tool_slots(_int(f.get("tool_choice")), f"{f.get('name', 'Privilegio')}: strumento a scelta",
                                                  f.get("tool_choice_category") or _tool_category(f.get("short") or f.get("text")))
            if f.get("fighting_style") or str(f.get("name", "")).startswith("Stile di Combattimento"):
                style_count += 1
                opts = f.get("fighting_style_options") or list((rules.get("equipment") or {}).get("fighting_styles") or {})
                style_options += [o for o in opts if o not in style_options]
        if style_count:
            styles = (rules.get("equipment") or {}).get("fighting_styles") or {}
            req["fighting_style"] = {
                "count": style_count,
                "options": [_option(k, styles.get(k, {}), female) for k in style_options],
                "keys": ["fighting_style"] + (["fighting_styles"] if style_count > 1 else []),
            }
        # manovre del Maestro di Battaglia (o colonna maneuvers_known nei dati)
        maneuvers = cls["table"].get("maneuvers_known")
        if not isinstance(maneuvers, int) and cls["subclass_key"] == "battle_master":
            maneuvers = max([n for lvl, n in BATTLE_MASTER_MANEUVERS.items() if lvl <= level] or [0])
        maneuvers = _int(maneuvers) + sum(_int((feat.get("maneuver_choice") or {}).get("count")) for _, feat, _ in feats)
        if maneuvers:
            req["maneuvers"] = {"count": maneuvers, "options": [_option(k, v, female) for k, v in (rules.get("maneuvers") or {}).items()]}
        # opzioni di classe (suppliche, metamagia, nemico prescelto, totem...)
        options = {}
        for list_key, opt in cls["option_lists"].items():
            if not isinstance(opt, dict) or (opt.get("level") and level < _int(opt["level"])):
                continue
            want = cls["table"].get(opt.get("count_table")) if opt.get("count_table") else opt.get("count")
            if isinstance(want, int) and want > 0:
                options[list_key] = {"label": opt.get("label", list_key), "count": want,
                                     "items": [_option(k, v, female) for k, v in (opt.get("items") or {}).items()]}
        if options:
            req["class_options"] = options
        _spell_requirements(char, rules, cls, scores, level, female, req)
        asi = [l for l in _as_list(data.get("asi_levels")) if _int(l) <= level]
        req["asi_levels"] = asi
        req["hp"] = {"hit_die": data.get("hit_die"), "rolls": level - 1}
        class_tools = [t for t in _as_list(data.get("tools")) if _placeholder_count(t)]
        for t in class_tools:
            class_tool_slots += _tool_slots(_placeholder_count(t), t)
        tc = data.get("tool_choice")
        if isinstance(tc, dict):
            class_tool_slots += _tool_slots(_int(tc.get("count"), 1), tc.get("label", "Strumenti a scelta"), tc.get("category"))
        if class_tools:
            req["class_tools_to_choose"] = class_tools
    else:
        req["asi_levels"] = []
        req["circle_terrain"] = False
    req["feats_allowed"] = bool(req["asi_levels"]) or bool(req.get("feat_choice"))

    # ---------------- talenti ----------------
    for _, feat, _ in feats:
        sc = feat.get("skill_choice")
        if isinstance(sc, dict) and _int(sc.get("count")):
            extra_skill_sources.append({"source": feat.get("name"), "count": _int(sc["count"]), "from": list(sc.get("from") or [])})

    if extra_skill_sources:
        pool_from = []
        if all(s["from"] for s in extra_skill_sources):
            for s in extra_skill_sources:
                pool_from += [k for k in s["from"] if k not in pool_from]
        req["extra_skills"] = {"count": sum(s["count"] for s in extra_skill_sources),
                               "from": pool_from or all_skills, "sources": extra_skill_sources}
    if expertise_count:
        req["expertise"] = {"count": expertise_count}
        if expertise_from:
            req["expertise"]["from"] = expertise_from
    if fixed_skills:
        req["fixed_skills"] = fixed_skills

    # ---------------- linguaggi e strumenti ----------------
    langs = 0
    known_langs = []
    if race:
        langs += race["extra_languages"]
        known_langs += race["languages"]
    if bg is not None:
        langs += _int(bg.get("languages"))
    if cls:
        langs += sum(_int(f.get("extra_languages")) for f in cls["features"])
        for f in cls["features"]:
            known_langs += [l for l in _as_list(f.get("languages")) if l not in known_langs]
        if cls["key"] == "druid":
            known_langs.append("druidic")
        if cls["key"] == "rogue":
            known_langs.append("thieves_cant")
    langs += sum(_int(feat.get("languages")) for _, feat, _ in feats)
    if langs:
        all_langs = list((skills_rules.get("languages") or {}).keys())
        req["languages"] = {"count": langs, "known": known_langs,
                            "from": [l for l in all_langs if l not in known_langs and l not in ("druidic", "thieves_cant")]}
    # stesso ordine del motore: classe, razza, privilegi; tutti vanno in 'tools'
    tool_slots = class_tool_slots + req.pop("_racial_tools", []) + feature_tool_slots
    if tool_slots:
        req["tools"] = {"count": len(tool_slots), "slots": tool_slots}

    # ---------------- caratteristiche ----------------
    pb = skills_rules.get("point_buy") or {}
    req["point_buy"] = {"budget": pb.get("budget", 27), "costs": {str(k): v for k, v in (pb.get("costs") or {}).items()}}
    req["standard_array"] = list(skills_rules.get("standard_array") or [15, 14, 13, 12, 10, 8])
    req["scores"] = scores
    return req
