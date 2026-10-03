"""Le funzioni del creatore di personaggi web, senza Flask.

Le usa il server locale (`dnd5e/web.py`, python -m dnd5e web) e, sul sito pubblicato, il ponte Pyodide
(`web_static/pyodide-bridge.js`), che chiama `init(root)` e poi `api(metodo, percorso, corpo)` al posto del server.
Tutto passa dal motore (`engine.build_sheet`, `sheet.SheetRenderer`, `guide.build_guide`): qui non ci sono regole.

    api("GET",  "rules")                    -> tutte le regole (JSON)
    api("POST", "requirements", {character}) -> {requirements}            (dnd5e/choices.py)
    api("POST", "preview", {character})     -> {ok, error, warnings, markdown, sheet}
    api("POST", "build", {character, stem?}) -> {ok, stem, yaml, pdf_url, guide_url, md_url, warnings}
    api("GET",  "characters")               -> [{stem, name, player, race, class, level, ...}]
    api("GET",  "characters/<stem>")        -> il personaggio
"""
from __future__ import annotations

import copy
import io
import json
import logging
import math
import re
import threading
import traceback
import unicodedata
from pathlib import Path

import yaml

from .choices import requirements as compute_requirements
from .engine import RULES_DIR, RulesError, build_sheet, load_rules, sheet_markdown

ROOT = Path(__file__).resolve().parent.parent
CHARACTERS_DIR = ROOT / "characters"
OUTPUT_DIR = ROOT / "output"
DEFAULT_TEMPLATE = "official_it"

# personaggi che non si sovrascrivono mai, se non dallo stesso personaggio (stesso nome)
PROTECTED_STEMS = {"kate", "reyla"}
WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
STEM_RE = re.compile(r"^[a-z0-9_][a-z0-9_-]{0,63}$")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
PORTRAIT_MAX = 1200

# ordine delle chiavi nel YAML salvato (come i personaggi scritti a mano)
KEY_ORDER = [
    "name", "template", "player", "gender", "simple", "race", "subrace", "draconic_ancestry",
    "class", "subclass", "level", "xp", "background", "alignment", "abilities", "feats", "hp",
    "skills", "background_skills", "racial_skills", "extra_skills", "expertise", "background_tools", "tools",
    "languages_extra", "racial_cantrips", "cantrips", "spellbook", "spells", "circle_terrain",
    "fighting_style", "fighting_styles", "maneuvers", "class_options", "armor", "shield", "weapons",
    "equipment", "include_background_equipment", "money", "personality", "appearance", "portrait",
    "allies", "treasure", "backstory",
]

log = logging.getLogger("dnd5e.web")
_build_lock = threading.Lock()


def init(root) -> None:
    """Cambia la cartella di lavoro (characters/ e output/): nel browser è '/app'."""
    global ROOT, CHARACTERS_DIR, OUTPUT_DIR
    ROOT = Path(root)
    CHARACTERS_DIR = ROOT / "characters"
    OUTPUT_DIR = ROOT / "output"
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Regole (ricaricate solo se i file YAML cambiano)
# ---------------------------------------------------------------------------
class _RulesCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.signature = None
        self.rules = None
        self.json_text = None

    @staticmethod
    def _signature():
        return tuple((p.relative_to(RULES_DIR).as_posix(), p.stat().st_mtime_ns, p.stat().st_size)
                     for p in sorted(RULES_DIR.rglob("*.yaml")))

    def get(self) -> dict:
        with self.lock:
            sig = self._signature()
            if sig != self.signature or self.rules is None:
                try:
                    self.rules = load_rules()
                    self.json_text = None
                    self.signature = sig
                except Exception:  # file di regole a metà di una modifica: tengo la versione precedente
                    if self.rules is None:
                        raise
                    log.warning("Regole non ricaricate (file in modifica?):\n%s", traceback.format_exc())
            return self.rules

    def fresh(self) -> dict:
        """Una copia delle regole per una singola scheda (il motore non deve poter cambiare quelle condivise)."""
        return copy.deepcopy(self.get())

    def as_json(self) -> str:
        rules = self.get()
        with self.lock:
            if self.json_text is None:
                self.json_text = json.dumps(jsonable(rules), ensure_ascii=False)
            return self.json_text


RULES = _RulesCache()


# ---------------------------------------------------------------------------
# Conversioni e nomi dei file
# ---------------------------------------------------------------------------
def jsonable(obj):
    """Converte in tipi JSON: chiavi in stringa, Path in percorso, set in lista ordinata."""
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        try:
            return [jsonable(v) for v in sorted(obj)]
        except TypeError:
            return [jsonable(v) for v in obj]
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def slugify(text: str) -> str:
    """Nome del file dal nome del personaggio: minuscole senza accenti, spazi -> _."""
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"[^a-z0-9_-]", "", text)
    text = re.sub(r"_+", "_", text).strip("_-")[:48]
    if text in WINDOWS_RESERVED:
        text += "_pg"
    return text


def safe_stem(stem) -> str | None:
    """La stem se è un nome di file sicuro (niente percorsi), altrimenti None."""
    stem = str(stem or "").strip().lower()
    if not STEM_RE.match(stem) or stem in WINDOWS_RESERVED:
        return None
    return stem


def choose_stem(name: str, requested=None) -> str:
    """Nome del file del personaggio: dal nome (o la stem richiesta), senza mai sovrascrivere Kate o Reyla
    se il personaggio non è proprio lei."""
    stem = safe_stem(requested) or slugify(name) or "personaggio"
    if stem in PROTECTED_STEMS and slugify(name) != stem:
        own = slugify(name)  # il nome è di un altro personaggio: uso il suo (anche Kate o Reyla, se è lei)
        stem = own or alt_stem(stem)
    return stem


def alt_stem(stem: str) -> str:
    n = 2
    while (CHARACTERS_DIR / f"{stem}_{n}.yaml").exists():
        n += 1
    return f"{stem}_{n}"


def _coerce_int(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\s*-?\d+\s*", value):
        return int(value)
    return value


def _clean(value):
    """Toglie i valori vuoti (None, "", [], {}) lasciando False e 0, che hanno un significato."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if str(k).startswith("_"):
                continue
            v = _clean(v)
            if v is None or v == "" or v == [] or v == {}:
                continue
            out[k] = v
        return out
    if isinstance(value, list):
        return [x for x in (_clean(v) for v in value) if not (x is None or x == "" or x == {})]
    if isinstance(value, str):
        return value.replace("\r\n", "\n").strip()
    return value


def portrait_path(rel) -> Path | None:
    """Percorso del ritratto dentro characters/, oppure None se non è sicuro o non esiste."""
    if not isinstance(rel, str) or not rel.strip():
        return None
    try:
        path = (CHARACTERS_DIR / rel.strip()).resolve()
        path.relative_to(CHARACTERS_DIR.resolve())
    except (ValueError, OSError):
        return None
    if path.suffix.lower() not in IMAGE_SUFFIXES or not path.is_file():
        return None
    return path


def normalize_character(char) -> dict:
    """Pulisce il personaggio arrivato dalla pagina: valori vuoti, numeri scritti come testo, ritratto sicuro."""
    if not isinstance(char, dict):
        return {}
    char = _clean(char)
    for key in ("level", "xp"):
        if key in char:
            char[key] = _coerce_int(char[key])
    ab = char.get("abilities")
    if isinstance(ab, dict):
        if isinstance(ab.get("base"), dict):
            ab["base"] = {k: _coerce_int(v) for k, v in ab["base"].items()}
        if isinstance(ab.get("asi"), list):
            ab["asi"] = [{k: _coerce_int(v) for k, v in a.items()} if isinstance(a, dict) else a for a in ab["asi"]]
    if isinstance(char.get("money"), dict):
        char["money"] = {k: _coerce_int(v) for k, v in char["money"].items()}
    hp = char.get("hp")
    if isinstance(hp, dict):
        if isinstance(hp.get("rolled"), list):
            hp["rolled"] = [_coerce_int(v) for v in hp["rolled"]]
        if "value" in hp:
            hp["value"] = _coerce_int(hp["value"])
    if "portrait" in char and not portrait_path(char["portrait"]):
        char.pop("portrait")
    return char


def character_from_body(data) -> tuple[dict, str | None]:
    """Dal corpo della richiesta ({character, stem?} oppure il personaggio da solo) al personaggio pulito."""
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data or "{}")
        except ValueError:
            data = {}
    if not isinstance(data, dict):
        return {}, None
    char = data.get("character", data)
    stem = data.get("stem") if "character" in data else None
    return normalize_character(char), stem


def _missing(char: dict, need_name: bool) -> list:
    labels = [("race", "la razza"), ("class", "la classe"), ("background", "il background")]
    if need_name:
        labels.insert(0, ("name", "il nome"))
    return [label for key, label in labels if not char.get(key)]


def _with_paths(char: dict, stem: str) -> dict:
    data = dict(char)
    data["_dir"] = CHARACTERS_DIR
    data["_stem"] = stem
    return data


def sheet_summary(sheet: dict) -> dict:
    """La parte della scheda che serve alla pagina (senza i testi lunghi)."""
    sp = sheet.get("spellcasting")
    spell = None
    if sp:
        def small(s):
            return {k: s.get(k) for k in ("key", "name", "level", "source", "prepared", "always_prepared", "conc",
                                          "ritual", "arcanum", "ability", "save_dc", "attack_bonus", "school")
                    if s.get(k) is not None}
        spell = {
            "ability": sp["ability"], "ability_name": sp["ability_name"],
            "save_dc": sp["save_dc"], "attack_bonus": sp["attack_bonus"],
            "slots": sp["slots"], "prepared_max": sp["prepared_max"], "max_level": sp["max_level"],
            "cantrips": [small(c) for c in sp["cantrips"]],
            "spells_by_level": {lvl: [small(s) for s in lst] for lvl, lst in sp["spells_by_level"].items()},
            "spell_attacks": sp["spell_attacks"],
        }
    ws = sheet.get("wild_shape")
    wild = None
    if ws:
        wild = {k: ws.get(k) for k in ("max_cr_str", "fly", "swim", "uses", "duration_hours")}
        wild["forms"] = [{"key": b.get("key"), "name": b.get("name"), "cr": b.get("cr")} for b in ws.get("forms", [])]
    portrait = None
    if sheet.get("portrait"):
        try:
            portrait = Path(sheet["portrait"]).resolve().relative_to(CHARACTERS_DIR.resolve()).as_posix()
        except ValueError:
            portrait = None
    race, cls, bg = sheet["race"], sheet["class"], sheet["background"]
    return jsonable({
        "name": sheet["name"], "player": sheet["player"], "level": sheet["level"], "xp": sheet["xp"],
        "race": {"key": race["key"], "name": race["name"], "size": race.get("size"), "speed": race.get("speed")},
        "class": {"key": cls["key"], "name": cls["name"], "level": cls["level"], "hit_die": cls.get("hit_die")},
        "class_level": sheet["class_level"], "subclass_name": sheet["subclass_name"],
        "background": {"name": bg.get("name")}, "alignment": sheet["alignment"],
        "abilities": sheet["abilities"], "saves": sheet["saves"], "skills": sheet["skills"],
        "ac": sheet["ac"], "hp": sheet["hp"], "initiative": sheet["initiative"], "speed_m": sheet["speed_m"],
        "proficiency_bonus": sheet["proficiency_bonus"], "passive_perception": sheet["passive_perception"],
        "spellcasting": spell, "weapons": sheet["weapons"],
        "features": [{k: f.get(k) for k in ("name", "short", "kid", "source", "level", "kid_hide")} for f in sheet["features"]],
        "fighting_styles": [{"name": f.get("name"), "short": f.get("short")} for f in sheet.get("fighting_styles", [])],
        "maneuvers": [{"name": m.get("name"), "text": m.get("text")} for m in sheet.get("maneuvers", [])],
        "background_feature": sheet.get("background_feature"), "proficiencies": sheet.get("proficiencies"),
        "languages": sheet.get("languages"), "equipment": sheet.get("equipment"), "money": sheet.get("money"),
        "breath": sheet.get("breath"), "wild_shape": wild, "mage_armor_ac": sheet.get("mage_armor_ac"),
        "portrait": portrait, "portrait_url": f"/portraits/{portrait}" if portrait else None,
        "simple": sheet.get("simple"), "female": sheet.get("female"),
        # i numeri del motore per i testi semplici ({cd}, {forma_ore}, {cd_manovre}...): la pagina li usa nei riquadri
        "placeholders": sheet.get("placeholders") or {}, "maneuver_info": sheet.get("maneuver_info"),
    })


# ---------------------------------------------------------------------------
# YAML del personaggio
# ---------------------------------------------------------------------------
class _Dumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def _short(v) -> bool:
    return isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) <= 30 and "\n" not in v)


def _dict_presenter(dumper, data):
    # in una riga solo i dizionari piccoli di valori brevi, es. base: {str: 8, dex: 14, ...}
    flow = len(data) <= 8 and all(_short(v) for v in data.values())
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=flow)


def _list_presenter(dumper, data):
    # in una riga le liste di chiavi (spells: [a, b, c]); una voce per riga le frasi (equipaggiamento)
    flow = all(isinstance(v, (int, float)) or (isinstance(v, str) and " " not in v) for v in data)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


_Dumper.add_representer(str, _str_presenter)
_Dumper.add_representer(dict, _dict_presenter)
_Dumper.add_representer(list, _list_presenter)


def character_yaml(char: dict, stem: str) -> str:
    ordered = {k: char[k] for k in KEY_ORDER if k in char}
    ordered.update({k: v for k, v in char.items() if k not in ordered})
    header = (f"# {char.get('name', stem)} — creato con la pagina web (doppio clic su 'Crea personaggio.bat')\n"
              f"# Genera la scheda anche da riga di comando:  python -m dnd5e build characters/{stem}.yaml\n\n")
    body = yaml.dump(ordered, Dumper=_Dumper, allow_unicode=True, sort_keys=False, default_flow_style=False, width=110)
    return header + body


# ---------------------------------------------------------------------------
# Le operazioni della pagina
# ---------------------------------------------------------------------------
def requirements_for(char: dict) -> dict:
    try:
        return {"requirements": jsonable(compute_requirements(char, RULES.get()))}
    except Exception as exc:
        log.error("Errore in requirements:\n%s", traceback.format_exc())
        return {"requirements": {}, "error": f"Errore interno: {exc}"}


def preview(char: dict) -> dict:
    empty = {"warnings": [], "markdown": "", "sheet": None}
    missing = _missing(char, need_name=False)
    if missing:
        return {"ok": False, "error": "Manca ancora " + ", ".join(missing) + ".", **empty}
    try:
        sheet = build_sheet(_with_paths(char, "anteprima"), RULES.fresh())
        return {"ok": True, "error": None, "warnings": list(sheet["warnings"]), "markdown": sheet_markdown(sheet),
                "sheet": sheet_summary(sheet)}
    except RulesError as exc:
        return {"ok": False, "error": str(exc), **empty}
    except Exception as exc:
        log.error("Errore in preview:\n%s", traceback.format_exc())
        return {"ok": False, "error": f"Errore interno: {type(exc).__name__}: {exc}", **empty}


def build(char: dict, requested_stem=None) -> dict:
    """Salva characters/<stem>.yaml e genera output/<stem>.pdf, .md e (se simple) _guida.pdf."""
    missing = _missing(char, need_name=True)
    if missing:
        return {"ok": False, "error": "Manca ancora " + ", ".join(missing) + "."}
    char = dict(char)
    char.setdefault("template", DEFAULT_TEMPLATE)
    stem = choose_stem(char["name"], requested_stem)
    rules = RULES.fresh()
    guide = None
    try:
        with _build_lock:
            sheet = build_sheet(_with_paths(char, stem), rules)
            from .sheet import SheetRenderer

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            pdf = OUTPUT_DIR / f"{stem}.pdf"
            SheetRenderer(char.get("template", DEFAULT_TEMPLATE)).render(sheet, pdf, appendix=True)
            pdf.with_suffix(".md").write_text(sheet_markdown(sheet), encoding="utf-8")
            if sheet.get("simple"):
                from .guide import build_guide

                guide = build_guide(sheet, rules, OUTPUT_DIR / f"{stem}_guida.pdf")
            CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
            (CHARACTERS_DIR / f"{stem}.yaml").write_text(character_yaml(char, stem), encoding="utf-8")
    except RulesError as exc:
        return {"ok": False, "error": str(exc)}
    except PermissionError as exc:
        return {"ok": False, "error": "Non riesco a scrivere il file: forse è aperto in un altro programma. "
                                      f"Chiudi il PDF e riprova ({Path(str(exc.filename or '')).name})."}
    except Exception as exc:
        log.error("Errore in build:\n%s", traceback.format_exc())
        return {"ok": False, "error": f"Errore interno: {type(exc).__name__}: {exc}"}
    return {"ok": True, "stem": stem, "yaml": f"characters/{stem}.yaml",
            "pdf_url": f"/output/{stem}.pdf", "md_url": f"/output/{stem}.md",
            "guide_url": f"/output/{stem}_guida.pdf" if guide else None,
            "warnings": list(sheet["warnings"])}


def save_portrait(data: bytes, stem=None, name: str = "") -> tuple[dict, int]:
    """Salva characters/<stem>/portrait.jpg (JPEG, lato massimo 1200 px). Restituisce (risposta, codice HTTP)."""
    from PIL import Image, ImageOps

    stem = safe_stem(stem) or slugify(name)
    if not stem:
        return {"ok": False, "error": "Scrivi prima il nome del personaggio."}, 400
    if stem in PROTECTED_STEMS and slugify(name) != stem:
        stem = alt_stem(stem)  # mai sostituire il ritratto di Kate o Reyla per sbaglio
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        img.thumbnail((PORTRAIT_MAX, PORTRAIT_MAX), Image.LANCZOS)
    except Exception as exc:
        return {"ok": False, "error": f"Questa non sembra un'immagine valida ({exc})."}, 400
    folder = CHARACTERS_DIR / stem
    folder.mkdir(parents=True, exist_ok=True)
    img.save(folder / "portrait.jpg", "JPEG", quality=90)
    rel = f"{stem}/portrait.jpg"
    return {"ok": True, "portrait": rel, "url": f"/portraits/{rel}", "width": img.width, "height": img.height}, 200


def list_characters() -> list:
    rules = RULES.get()
    out = []
    for path in sorted(CHARACTERS_DIR.glob("*.yaml")):
        stem = path.stem
        try:
            char = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(char, dict):
            continue
        female = str(char.get("gender", "")).lower() in ("f", "femmina", "donna", "female")
        race = (rules.get("races") or {}).get(char.get("race")) or {}
        cls = (rules.get("classes") or {}).get(char.get("class")) or {}
        portrait = char.get("portrait") if portrait_path(char.get("portrait")) else None
        out.append(jsonable({
            "stem": stem, "name": char.get("name", stem), "player": char.get("player", ""),
            "race": char.get("race"), "class": char.get("class"), "level": char.get("level", 1),
            "subclass": char.get("subclass"),
            "race_name": (race.get("name_f") if female and race.get("name_f") else race.get("name")) or char.get("race"),
            "class_name": (cls.get("name_f") if female and cls.get("name_f") else cls.get("name")) or char.get("class"),
            "portrait": portrait, "portrait_url": f"/portraits/{portrait}" if portrait else None,
            "pdf_url": f"/output/{stem}.pdf" if (OUTPUT_DIR / f"{stem}.pdf").is_file() else None,
            "guide_url": f"/output/{stem}_guida.pdf" if (OUTPUT_DIR / f"{stem}_guida.pdf").is_file() else None,
        }))
    return out


def get_character(stem) -> tuple[dict, int]:
    stem = safe_stem(stem)
    path = CHARACTERS_DIR / f"{stem}.yaml" if stem else None
    if not path or not path.is_file():
        return {"ok": False, "error": "Personaggio non trovato."}, 404
    try:
        char = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {"ok": False, "error": f"Il file del personaggio non è leggibile: {exc}"}, 500
    return jsonable(char), 200


def output_path(filename: str) -> Path | None:
    """Un file generato dentro output/ (solo .pdf e .md, niente sottocartelle), se esiste."""
    if not filename or "/" in filename or "\\" in filename or Path(filename).suffix.lower() not in (".pdf", ".md"):
        return None
    path = OUTPUT_DIR / filename
    return path if path.is_file() else None


# ---------------------------------------------------------------------------
# Un solo punto d'ingresso per il ponte Pyodide
# ---------------------------------------------------------------------------
def api(method: str, path: str, body="") -> str:
    """Risponde a una chiamata della pagina come farebbe il server: restituisce il JSON come testo."""
    method = (method or "GET").upper()
    route = str(path or "").strip("/")
    if route.startswith("api/"):
        route = route[4:]
    try:
        if route == "rules" and method == "GET":
            return RULES.as_json()
        if route == "ping":
            out = {"app": "dnd5e", "ok": True}
        elif route == "requirements" and method == "POST":
            out = requirements_for(character_from_body(body)[0])
        elif route == "preview" and method == "POST":
            out = preview(character_from_body(body)[0])
        elif route == "build" and method == "POST":
            out = build(*character_from_body(body))
        elif route == "characters" and method == "GET":
            out = list_characters()
        elif route.startswith("characters/") and method == "GET":
            out = get_character(route.split("/", 1)[1])[0]
        else:
            out = {"ok": False, "error": f"Richiesta sconosciuta: {method} {route}"}
    except Exception as exc:
        log.error("Errore in %s %s:\n%s", method, route, traceback.format_exc())
        out = {"ok": False, "error": f"Errore interno: {type(exc).__name__}: {exc}"}
    return json.dumps(jsonable(out), ensure_ascii=False)
