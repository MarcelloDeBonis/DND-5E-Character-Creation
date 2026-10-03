"""Pagina web per creare i personaggi passo per passo (python -m dnd5e web).

Un piccolo server Flask, solo su 127.0.0.1. La logica sta in `dnd5e/webcore.py` (la stessa che usa il sito
pubblicato tramite Pyodide); qui ci sono solo le rotte HTTP e l'avvio:

    GET  /                        la pagina (dnd5e/web/static/index.html), file statici sotto /static/
    GET  /api/rules               tutte le regole in JSON
    POST /api/requirements        {character} -> {requirements}: le scelte che mancano (dnd5e/choices.py)
    POST /api/preview             {character} -> {ok, error, warnings, markdown, sheet}
    POST /api/portrait            multipart {stem, file[, name]} -> salva characters/<stem>/portrait.jpg
    POST /api/build               {character[, stem]} -> characters/<stem>.yaml + output/<stem>.pdf (+ guida)
    GET  /output/<file>           i PDF e i riepiloghi generati
    GET  /portraits/<stem>/<img>  i ritratti dei personaggi
    GET  /api/characters          i personaggi salvati in characters/*.yaml
    GET  /api/characters/<stem>   un personaggio, per modificarlo
"""
from __future__ import annotations

import json
import logging
import socket
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from . import webcore as core
from .webcore import (RULES, character_from_body, choose_stem, jsonable, normalize_character,  # noqa: F401
                      safe_stem, slugify)

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
DEFAULT_PORT = 8765
log = logging.getLogger("dnd5e.web")

PLACEHOLDER_PAGE = """<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Creatore di personaggi</title></head>
<body style="font-family:sans-serif;background:#1b1420;color:#f3e9d2;padding:40px">
<h1>Creatore di personaggi D&amp;D 5e</h1><p>Il server funziona, ma manca la pagina
<code>dnd5e/web/static/index.html</code>.</p></body></html>"""


def _versioned(url):
    """Aggiunge ?v=... agli indirizzi dei PDF: il browser mostra sempre quello appena rigenerato."""
    return f"{url}?v={int(time.time())}" if url else url


def create_app() -> Flask:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.json.sort_keys = False
    app.json.ensure_ascii = False

    def body():
        return character_from_body(request.get_json(silent=True) or {})

    @app.after_request
    def no_cache(resp):
        if request.path.startswith(("/api/", "/output/", "/portraits/")) or request.path == "/":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(413)
    def too_big(_):
        return jsonify(ok=False, error="Il file è troppo grande (massimo 30 MB)."), 413

    @app.get("/")
    def index():
        if (STATIC_DIR / "index.html").is_file():
            return send_from_directory(STATIC_DIR, "index.html")
        return Response(PLACEHOLDER_PAGE, mimetype="text/html")

    @app.get("/api/ping")
    def ping():
        return jsonify(app="dnd5e", ok=True, mode="server")

    @app.get("/api/rules")
    def api_rules():
        try:
            return Response(RULES.as_json(), mimetype="application/json")
        except Exception as exc:
            log.error("Regole non leggibili:\n%s", traceback.format_exc())
            return jsonify(ok=False, error=f"Non riesco a leggere le regole: {exc}"), 500

    @app.post("/api/requirements")
    def api_requirements():
        return jsonify(core.requirements_for(body()[0]))

    @app.post("/api/preview")
    def api_preview():
        return jsonify(core.preview(body()[0]))

    @app.post("/api/build")
    def api_build():
        out = core.build(*body())
        if out.get("ok"):
            for key in ("pdf_url", "md_url", "guide_url"):
                out[key] = _versioned(out.get(key))
        return jsonify(out)

    @app.post("/api/portrait")
    def api_portrait():
        file = request.files.get("file")
        if file is None or not file.filename:
            return jsonify(ok=False, error="Nessuna immagine ricevuta."), 400
        out, status = core.save_portrait(file.read(), request.form.get("stem"), request.form.get("name", ""))
        if out.get("ok"):
            out["url"] = _versioned(out["url"])
        return jsonify(out), status

    @app.get("/portraits/<path:rel>")
    def portraits(rel):
        path = core.portrait_path(rel)
        if not path:
            abort(404)
        return send_from_directory(path.parent, path.name)

    @app.get("/output/<path:filename>")
    def output_file(filename):
        path = core.output_path(filename)
        if not path:
            abort(404)
        if path.suffix.lower() == ".md":
            return Response(path.read_text(encoding="utf-8"), content_type="text/plain; charset=utf-8")
        return send_from_directory(path.parent, path.name, mimetype="application/pdf")

    @app.get("/api/characters")
    def api_characters():
        return jsonify(core.list_characters())

    @app.get("/api/characters/<stem>")
    def api_character(stem):
        out, status = core.get_character(stem)
        return jsonify(out), status

    return app


app = create_app()


# ---------------------------------------------------------------------------
# Avvio (python -m dnd5e web)
# ---------------------------------------------------------------------------
def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _already_ours(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as resp:
            return json.loads(resp.read().decode("utf-8")).get("app") == "dnd5e"
    except Exception:
        return False


def serve(port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    from werkzeug.serving import make_server

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    if not _port_free(port):
        if _already_ours(port):  # doppio clic una seconda volta: riapro solo la pagina
            url = f"http://127.0.0.1:{port}/"
            print(f"Il creatore di personaggi è già aperto: {url}", flush=True)
            if open_browser:
                webbrowser.open(url)
            return
        port = next((p for p in range(port + 1, port + 50) if _port_free(p)), 0)
        if not port:
            raise SystemExit("Nessuna porta libera per aprire la pagina: chiudi qualche programma e riprova.")
    RULES.get()  # carica subito le regole: un errore nei file si vede adesso, non nella pagina
    server = make_server("127.0.0.1", port, app, threaded=True)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 60)
    print("  Creatore di personaggi D&D 5e")
    print(f"  La pagina è aperta qui: {url}")
    print("  Lascia aperta questa finestra mentre usi la pagina.")
    print("  Per chiudere tutto: chiudi questa finestra (o premi Ctrl+C).")
    print("=" * 60, flush=True)
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Creatore di personaggi chiuso.")
    finally:
        server.server_close()
