"""Collaudo veloce della pagina web (backend): chiama ogni endpoint con Kate e Reyla.

    python tools/test_web.py

Usa il test_client di Flask (nessun server vero) e chiama anche webcore.api(), la strada usata dal sito
pubblicato con Pyodide. I file di prova (_test_kate, _test_reyla, _test_core, _test_ritratto, _test_talento) vengono creati
e poi cancellati. Esce con codice 1 se qualcosa non va.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from dnd5e import web, webcore  # noqa: E402
from dnd5e.choices import requirements  # noqa: E402
from dnd5e.engine import load_rules  # noqa: E402

FAILS: list[str] = []


def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)
    return cond


def load(stem):
    return yaml.safe_load((ROOT / "characters" / f"{stem}.yaml").read_text(encoding="utf-8"))


def cleanup(stems):
    for stem in stems:
        for p in [ROOT / "characters" / f"{stem}.yaml", ROOT / "output" / f"{stem}.pdf",
                  ROOT / "output" / f"{stem}.md", ROOT / "output" / f"{stem}_guida.pdf"]:
            if p.exists():
                p.unlink()
        folder = ROOT / "characters" / stem
        if folder.is_dir():
            shutil.rmtree(folder)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    client = web.app.test_client()
    test_stems = ["_test_kate", "_test_reyla", "_test_core", "_test_ritratto", "_test_talento"]
    cleanup(test_stems)
    kate, reyla = load("kate"), load("reyla")
    kate_yaml_before = (ROOT / "characters" / "kate.yaml").read_bytes()
    try:
        print("GET /")
        r = client.get("/")
        check(r.status_code == 200 and b"<html" in r.data.lower(), "la pagina risponde")

        print("GET /api/rules")
        r = client.get("/api/rules")
        rules = r.get_json()
        check(r.status_code == 200 and {"races", "classes", "spells", "backgrounds"} <= set(rules), "regole in JSON")
        check("1" in rules["spells"]["slots"]["full"], "chiavi numeriche convertite in stringhe")

        print("POST /api/requirements")
        rk = client.post("/api/requirements", json={"character": kate}).get_json()["requirements"]
        check(rk.get("cantrips", {}).get("count") == 3, f"Kate: 3 trucchetti (avuto {rk.get('cantrips')})")
        check(rk.get("spellbook", {}).get("count") == 10, f"Kate: 10 incantesimi nel libro (avuto {rk.get('spellbook')})")
        check(rk.get("spells", {}).get("mode") == "spellbook" and rk["spells"].get("count") == 5,
              f"Kate: 5 preparati dal libro (avuto {rk.get('spells', {}).get('count')})")
        check(rk.get("spells", {}).get("max_level") == 2, "Kate: incantesimi fino al 2° livello")
        check(rk.get("class_skills", {}).get("count") == 2, "Kate: 2 abilità di classe")
        check(rk.get("background_skills", {}).get("count") == 2, "Kate: 2 abilità di background")
        check(rk.get("languages", {}).get("count") == 1, "Kate: 1 linguaggio extra")
        check(rk.get("draconic_ancestry") is True, "Kate: sceglie il colore del drago")
        check(rk.get("subclass", {}).get("required") is True and rk["subclass"]["level"] == 2, "Kate: tradizione arcana dal 2° livello")
        check(rk.get("asi_levels") == [] and rk.get("feats_allowed") is False, "Kate: niente aumenti al 3° livello")
        check(rk.get("point_buy", {}).get("budget") == 27, "point buy da 27 punti")
        check(len(kate["cantrips"]) == rk["cantrips"]["count"] and len(kate["spellbook"]) == rk["spellbook"]["count"]
              and len(kate["spells"]) == rk["spells"]["count"], "Kate: le sue scelte tornano con i conteggi")

        rr = client.post("/api/requirements", json={"character": reyla}).get_json()["requirements"]
        check(rr.get("cantrips", {}).get("count") == 2, f"Reyla: 2 trucchetti (avuto {rr.get('cantrips')})")
        check(rr.get("spells", {}).get("mode") == "prepared" and rr["spells"].get("count") == 5,
              f"Reyla: 5 preparati (avuto {rr.get('spells', {}).get('count')})")
        check(rr.get("racial_cantrip", {}).get("count") == 1 and rr["racial_cantrip"].get("list") == "wizard",
              "Reyla: 1 trucchetto da elfa alta (lista del mago)")
        check(rr.get("languages", {}).get("count") == 2, "Reyla: 2 linguaggi extra")
        check("spellbook" not in rr, "Reyla: nessun libro degli incantesimi")
        check(rr.get("subrace", {}).get("required") is True, "Reyla: la sottorazza è obbligatoria")

        # personaggi incompleti: mai un errore
        partials = [{}, {"name": "X"}, {"race": "elf"}, {"class": "wizard"}, {"race": "nonesiste", "class": "nonesiste"},
                    {"race": "dragonborn", "class": "fighter", "level": "abc"}, {"class": "cleric", "level": 99},
                    {"class": "warlock", "level": 3, "subclass": "nonesiste"}, {"abilities": "rotto", "feats": [None, 3]}]
        ok = True
        for p in partials:
            resp = client.post("/api/requirements", json={"character": p})
            data = resp.get_json() or {}
            ok &= resp.status_code == 200 and "requirements" in data and "error" not in data
        check(ok, "requirements non va mai in errore con personaggi incompleti")

        # tutte le razze, sottorazze, classi, sottoclassi e livelli
        all_rules = load_rules()
        crashes = []
        for race_key, race in all_rules["races"].items():
            subs = [None] + list((race.get("subraces") or {}).keys()) + list((race.get("variants") or {}).keys())
            for sub in subs:
                for cls_key, cls in all_rules["classes"].items():
                    for sc in [None] + list((cls.get("subclasses") or {}).keys()):
                        for lvl in (1, 3, 5, 11, 20):
                            ch = {"race": race_key, "subrace": sub, "class": cls_key, "subclass": sc, "level": lvl,
                                  "background": "sage"}
                            try:
                                requirements(ch, all_rules)
                            except Exception as exc:  # pragma: no cover
                                crashes.append(f"{ch}: {exc}")
        check(not crashes, f"requirements su tutte le combinazioni razza/classe/livello ({len(crashes)} errori)")
        for c in crashes[:5]:
            print("        ", c)

        # qualche classe con conteggi noti dal Manuale del Giocatore
        def req(ch):
            return requirements({"background": "sage", **ch}, all_rules)
        bm = req({"race": "human", "class": "fighter", "subclass": "battle_master", "level": 7})
        check(bm.get("maneuvers", {}).get("count") == 5 and bm.get("fighting_style", {}).get("count") == 1,
              "Guerriero Maestro di Battaglia 7: 5 manovre, 1 stile")
        champ = req({"race": "human", "class": "fighter", "subclass": "champion", "level": 10})
        check(champ.get("fighting_style", {}).get("count") == 2, "Campione 10: 2 stili di combattimento")
        rogue = req({"race": "human", "class": "rogue", "level": 1})
        check(rogue.get("expertise", {}).get("count") == 2 and rogue["class_skills"]["count"] == 4, "Ladro 1: 4 abilità, 2 maestrie")
        half = req({"race": "half_elf", "class": "bard", "level": 3})
        check(half.get("racial_choice", {}).get("count") == 2 and half.get("racial_skills", {}).get("count") == 2
              and half.get("expertise", {}).get("count") == 2, "Mezzelfo bardo 3: 2 caratteristiche, 2 abilità, 2 maestrie")
        sorc = req({"race": "human", "class": "sorcerer", "subclass": "wild_magic", "level": 3})
        check(sorc.get("class_options", {}).get("metamagic", {}).get("count") == 2 and sorc["spells"]["count"] == 4,
              "Stregone 3: 2 metamagie, 4 incantesimi conosciuti")
        vh = req({"race": "human", "subrace": "variant_human", "class": "wizard", "level": 1})
        check(vh.get("feat_choice", {}).get("count") == 1 and vh.get("feats_allowed") is True, "Umano variante: 1 talento")
        cleric = req({"race": "human", "class": "cleric", "subclass": "life", "level": 1,
                      "abilities": {"method": "point_buy", "base": {"wis": 15}}})
        check(cleric["spells"]["count"] == 4 and "bless" in cleric["spells"]["always_prepared"],
              "Chierico della Vita 1 con SAG 16: 4 preparati + Benedizione sempre preparato")
        land = req({"race": "human", "class": "druid", "subclass": "land", "level": 2})
        check(land.get("circle_terrain") is True and land["cantrips"]["count"] == 3, "Druido della Terra 2: terreno e 3 trucchetti")
        bard = req({"race": "dwarf", "subrace": "hill_dwarf", "class": "bard", "level": 1, "background": "outlander"})
        check(bard.get("tools", {}).get("count") == 4 and len(bard["tools"].get("slots", [])) == 4,
              f"Bardo nano: 3 strumenti di classe + 1 del nano, una casella per ognuno (avuto {bard.get('tools', {}).get('count')})")
        bgt = req({"race": "human", "class": "fighter", "level": 1, "background": "soldier"}).get("background_tools", {})
        check(len(bgt.get("choices", [])) == 1 and bgt.get("count") == len(bgt.get("fixed", [])) + 1,
              "Soldato: strumenti fissi + 1 gioco a scelta in 'background_tools'")
        bm = req({"race": "human", "class": "ranger", "subclass": "beast_master", "level": 3})
        check(any(o["key"] == "wolf" for o in bm.get("companion", {}).get("options", [])), "Signore delle Bestie: si sceglie il compagno (lupo)")
        w18 = req({"race": "human", "class": "wizard", "subclass": "evocation", "level": 18})
        w20 = req({"race": "human", "class": "wizard", "subclass": "evocation", "level": 20})
        check(w18.get("spell_mastery") and not w18.get("signature_spells") and w20.get("signature_spells"),
              "Mago 18: Maestria negli Incantesimi; 20: Incantesimi Personali")

        print("POST /api/preview")
        for name, ch in (("Kate", kate), ("Reyla", reyla)):
            data = client.post("/api/preview", json={"character": ch}).get_json()
            check(data["ok"] is True and data["error"] is None, f"{name}: anteprima ok")
            check(data["warnings"] == [], f"{name}: nessun avviso ({data['warnings']})")
            s = data.get("sheet") or {}
            check(bool(data["markdown"]) and s.get("spellcasting") and s.get("ac") and s.get("hp"), f"{name}: scheda calcolata")
        data = client.post("/api/preview", json={"character": kate}).get_json()["sheet"]
        check(data["hp"]["max"] > 0 and data["spellcasting"]["save_dc"] == 12 and data["breath"]["dc"] == 12,
              "Kate: PF, CD incantesimi 12 e soffio CD 12")
        check(data["portrait"] == "kate/portrait.jpg", "Kate: ritratto trovato")
        check(isinstance(data.get("placeholders"), dict) and data["placeholders"].get("cd") == 12,
              "anteprima: i numeri per i testi semplici ({cd}...) arrivano alla pagina")
        bad = client.post("/api/preview", json={"character": {**kate, "cantrips": ["cure_wounds", "fire_bolt", "mage_hand"]}}).get_json()
        check(bad["ok"] is False and bad["error"], f"scelta illegale -> errore regole ({bad['error']})")
        miss = client.post("/api/preview", json={"character": {"name": "Solo nome"}}).get_json()
        check(miss["ok"] is False and "razza" in miss["error"], "personaggio senza razza -> messaggio chiaro")
        weird = client.post("/api/preview", json={"character": {**reyla, "level": "3", "xp": "900", "background_skills": [],
                                                                    "abilities": {**reyla["abilities"], "base": {k: str(v) for k, v in reyla["abilities"]["base"].items()}}}}).get_json()
        check(weird["ok"] is True, "numeri scritti come testo e liste vuote vengono accettati")

        print("POST /api/portrait")
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGBA", (2000, 1500), (200, 30, 30, 255)).save(buf, "PNG")
        buf.seek(0)
        r = client.post("/api/portrait", data={"stem": "_test_ritratto", "file": (buf, "ritratto.png")},
                        content_type="multipart/form-data")
        pj = r.get_json()
        saved = ROOT / "characters" / "_test_ritratto" / "portrait.jpg"
        check(r.status_code == 200 and pj["portrait"] == "_test_ritratto/portrait.jpg" and saved.is_file(), "ritratto salvato")
        with Image.open(saved) as im:
            check(max(im.size) == 1200 and im.format == "JPEG", f"ritratto ridotto a 1200 px ({im.size})")
        with client.get("/portraits/_test_ritratto/portrait.jpg") as r:
            check(r.status_code == 200 and r.mimetype == "image/jpeg", "ritratto visibile dalla pagina")
        buf2 = io.BytesIO(b"non sono un'immagine")
        r = client.post("/api/portrait", data={"stem": "_test_ritratto", "file": (buf2, "x.png")}, content_type="multipart/form-data")
        check(r.status_code == 400, "file che non è un'immagine -> errore")
        buf3 = io.BytesIO()
        Image.new("RGB", (10, 10)).save(buf3, "JPEG")
        buf3.seek(0)
        r = client.post("/api/portrait", data={"stem": "../../evil", "name": "", "file": (buf3, "x.jpg")}, content_type="multipart/form-data")
        check(r.status_code == 400 and not (ROOT.parent / "evil").exists(), "stem con percorso rifiutata")

        print("POST /api/build")
        for stem, ch in (("_test_kate", kate), ("_test_reyla", reyla)):
            data = client.post("/api/build", json={"character": ch, "stem": stem}).get_json()
            check(data.get("ok") is True and data.get("stem") == stem, f"{stem}: build ok ({data.get('error')})")
            pdf, guide, md = (ROOT / "output" / f"{stem}.pdf", ROOT / "output" / f"{stem}_guida.pdf", ROOT / "output" / f"{stem}.md")
            check(pdf.is_file() and pdf.stat().st_size > 50_000 and pdf.read_bytes()[:5] == b"%PDF-", f"{stem}: PDF scheda")
            check(guide.is_file() and guide.read_bytes()[:5] == b"%PDF-" and data.get("guide_url"), f"{stem}: PDF guida (simple)")
            check(md.is_file() and data.get("md_url"), f"{stem}: riepilogo .md")
            saved = yaml.safe_load((ROOT / "characters" / f"{stem}.yaml").read_text(encoding="utf-8"))
            same = {k: saved.get(k) for k in ("name", "race", "class", "level", "spells", "cantrips", "backstory")} == \
                   {k: ch.get(k) for k in ("name", "race", "class", "level", "spells", "cantrips")} | {"backstory": ch["backstory"].strip()}
            check(same, f"{stem}: YAML salvato uguale al personaggio")
            with client.get(data["pdf_url"]) as r:
                check(r.status_code == 200 and r.mimetype == "application/pdf" and r.data[:5] == b"%PDF-"
                      and "attachment" not in r.headers.get("Content-Disposition", ""), f"{stem}: PDF servito inline")
            with client.get(data["md_url"]) as r:
                check(r.status_code == 200 and data["md_url"] and "Incantesimi" in r.get_data(as_text=True), f"{stem}: riepilogo servito")
        # versione completa (con appendice) e un talento: il talento non ha un livello e l'appendice non deve rompersi
        full = {**kate, "simple": False, "feats": ["alert"]}
        data = client.post("/api/build", json={"character": full, "stem": "_test_talento"}).get_json()
        check(data.get("ok") is True and (ROOT / "output" / "_test_talento.pdf").is_file() and not data.get("guide_url"),
              f"versione completa con un talento: PDF con appendice ({data.get('error')})")
        check((ROOT / "characters" / "kate.yaml").read_bytes() == kate_yaml_before, "kate.yaml non è stato toccato")
        check(webcore.choose_stem("Pippo", "kate") == "pippo" and webcore.choose_stem("Kate") == "kate"
              and webcore.choose_stem("Kate!", "reyla") == "kate" and webcore.choose_stem("Àlì Bàbà") == "ali_baba"
              and webcore.choose_stem("Con") != "con", "nomi dei file: Kate e Reyla protette, accenti e nomi riservati")
        bad = client.post("/api/build", json={"character": {**kate, "spells": ["fireball"]}, "stem": "_test_kate"}).get_json()
        check(bad["ok"] is False and bad["error"], f"build con scelta illegale -> errore ({bad['error']})")

        print("GET /output, /api/characters")
        check(client.get("/output/../README.md").status_code == 404, "niente file fuori da output/")
        check(client.get("/output/nonesiste.pdf").status_code == 404, "PDF inesistente -> 404")
        lst = client.get("/api/characters").get_json()
        stems = {c["stem"]: c for c in lst}
        check({"kate", "reyla"} <= set(stems) and not any("examples" in s for s in stems), "elenco personaggi (senza examples)")
        check(stems["kate"]["name"] == "Kate" and stems["kate"]["level"] == 3 and stems["kate"]["class"] == "wizard"
              and stems["kate"]["race"] == "dragonborn" and stems["kate"]["player"] == "Rebecca", "Kate nell'elenco")
        one = client.get("/api/characters/reyla").get_json()
        check(one.get("name") == "Reyla" and one.get("subrace") == "high_elf", "carica Reyla per modificarla")
        check(client.get("/api/characters/..%2Fkate").status_code == 404 and client.get("/api/characters/nonesiste").status_code == 404,
              "personaggio inesistente o percorso strano -> 404")

        print("webcore.api (sito con Pyodide)")
        probe = subprocess.run([sys.executable, "-c", "import sys, dnd5e.webcore; print('flask' in sys.modules)"],
                               cwd=ROOT, capture_output=True, text=True)
        check(probe.stdout.strip() == "False", "webcore non usa Flask (gira anche nel browser)")
        check(json.loads(webcore.api("GET", "rules")).get("races"), "api: regole")
        req = json.loads(webcore.api("POST", "requirements", json.dumps({"character": reyla})))["requirements"]
        check(req.get("racial_cantrip", {}).get("count") == 1 and req["spells"]["count"] == 5, "api: requirements di Reyla")
        prev = json.loads(webcore.api("POST", "preview", json.dumps({"character": kate})))
        check(prev.get("ok") is True and prev["sheet"]["spellcasting"]["save_dc"] == 12, "api: anteprima di Kate")
        res = json.loads(webcore.api("POST", "build", json.dumps({"character": kate, "stem": "_test_core"})))
        check(res.get("ok") is True and res["pdf_url"] == "/output/_test_core.pdf" and res["guide_url"] == "/output/_test_core_guida.pdf"
              and (ROOT / "output" / "_test_core.pdf").is_file(), "api: build con indirizzi semplici (senza ?v=)")
        lst = json.loads(webcore.api("GET", "characters"))
        check(any(c["stem"] == "kate" for c in lst), "api: elenco personaggi")
        check(json.loads(webcore.api("GET", "characters/kate")).get("name") == "Kate", "api: carica Kate")
        check(json.loads(webcore.api("GET", "characters/..%2Fkate")).get("ok") is False, "api: percorso strano rifiutato")
        check(json.loads(webcore.api("DELETE", "boh")).get("ok") is False, "api: richiesta sconosciuta -> errore, non eccezione")
        check(json.loads(webcore.api("POST", "preview", "non è json")).get("ok") is False, "api: corpo non valido -> errore")
    finally:
        cleanup(test_stems)
    left = [p.name for p in list((ROOT / "characters").glob("_test_*")) + list((ROOT / "output").glob("_test_*"))]
    check(not left, f"file di prova cancellati ({left})")
    print()
    if FAILS:
        print(f"{len(FAILS)} controlli NON riusciti.")
        sys.exit(1)
    print("Tutti i controlli sono riusciti.")


if __name__ == "__main__":
    main()
