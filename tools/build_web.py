"""Prepara la cartella da pubblicare sul sito (hosting senza Python): dist/creatore-personaggi/.

    python tools/build_web.py            # crea dist/creatore-personaggi
    python tools/build_web.py --serve    # e la apre su http://127.0.0.1:8790 per provarla

Dentro ci sono la pagina del creatore (dnd5e/web/static), il ponte Pyodide (web_static/pyodide-bridge.js)
e in py/ il motore, le regole, il template PDF e le librerie Python pure (reportlab, pypdf) che il browser
carica con Pyodide. La cartella si carica così com'è con FileZilla, in modalità binaria per .zip e .whl.
Destinazione attuale: /domains/games.fantasyrolldice.it/public_html/games_internal/creatore-personaggi
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "dnd5e" / "web" / "static"
BRIDGE = ROOT / "web_static" / "pyodide-bridge.js"
DIST = ROOT / "dist" / "creatore-personaggi"
WHEELS_CACHE = ROOT / "dist" / "_wheels"
WHEELS = ["reportlab", "pypdf"]  # pure Python; PyYAML, Pillow e charset-normalizer arrivano da Pyodide
SKIP_PY = {"web.py", "cli.py", "__main__.py"}  # Flask e riga di comando non servono nel browser


def wheels() -> list[Path]:
    WHEELS_CACHE.mkdir(parents=True, exist_ok=True)
    found = []
    for name in WHEELS:
        hits = sorted(WHEELS_CACHE.glob(f"{name}-*-py3-none-any.whl"))
        if not hits:
            subprocess.run([sys.executable, "-m", "pip", "download", name, "--no-deps", "--only-binary=:all:",
                            "--platform", "any", "--python-version", "3.13", "--implementation", "py",
                            "-d", str(WHEELS_CACHE), "-q"], check=True)
            hits = sorted(WHEELS_CACHE.glob(f"{name}-*-py3-none-any.whl"))
        found.append(hits[-1])
    return found


def app_zip(dest: Path) -> str:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted((ROOT / "dnd5e").glob("*.py")):
            if p.name not in SKIP_PY:
                z.write(p, f"dnd5e/{p.name}")
        rules = ROOT / "dnd5e" / "rules"
        for p in sorted(rules.rglob("*.yaml")):
            z.write(p, f"dnd5e/rules/{p.relative_to(rules).as_posix()}")
        for tpl in ("official_it", "official"):
            for p in sorted((ROOT / "templates" / tpl).iterdir()):
                if p.suffix in (".pdf", ".yaml"):
                    z.write(p, f"templates/{tpl}/{p.name}")
    return hashlib.sha1(dest.read_bytes()).hexdigest()[:10]


def page(html: str) -> str:
    # percorsi relativi (la pagina vive in una sottocartella del sito) e ponte caricato prima dell'app
    html = re.sub(r'(href|src)="/static/', r'\1="./', html)
    tag = '<script src="./pyodide-bridge.js"></script>\n'
    i = html.find("<script")
    return html[:i] + tag + html[i:] if i != -1 else html.replace("</head>", tag + "</head>")


def build() -> Path:
    if not (STATIC / "index.html").exists():
        sys.exit("Manca dnd5e/web/static/index.html")
    if not (ROOT / "dnd5e" / "webcore.py").exists():
        sys.exit("Manca dnd5e/webcore.py (le funzioni del server usate anche nel browser)")
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(STATIC, DIST)
    (DIST / "index.html").write_text(page((STATIC / "index.html").read_text(encoding="utf-8")), encoding="utf-8")
    for js in DIST.rglob("*.js"):  # anche il JS può citare /static/
        txt = js.read_text(encoding="utf-8")
        js.write_text(txt.replace('"/static/', '"./').replace("'/static/", "'./"), encoding="utf-8")
    shutil.copy2(BRIDGE, DIST / "pyodide-bridge.js")
    py = DIST / "py"
    py.mkdir()
    names = []
    for w in wheels():
        shutil.copy2(w, py / w.name)
        names.append(w.name)
    version = app_zip(py / "app.zip")
    (py / "manifest.json").write_text(json.dumps({"app": "app.zip", "version": version, "wheels": names}, indent=1), encoding="utf-8")
    (DIST / ".htaccess").write_text(
        "AddDefaultCharset UTF-8\n"
        "AddType application/zip .zip\n"
        "AddType application/octet-stream .whl\n"
        "AddType application/javascript .js\n"
        "<IfModule mod_headers.c>\n  <FilesMatch \"\\.(zip|whl)$\">\n    Header set Cache-Control \"max-age=86400\"\n  </FilesMatch>\n</IfModule>\n",
        encoding="utf-8")
    size = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(f"Pronta: {DIST}  ({size / 1e6:.1f} MB, versione {version})")
    return DIST


if __name__ == "__main__":
    out = build()
    if "--serve" in sys.argv:
        import functools
        import http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
        print("Prova: http://127.0.0.1:8790/")
        http.server.ThreadingHTTPServer(("127.0.0.1", 8790), handler).serve_forever()
