/* Ponte per la versione pubblicata sul sito (hosting senza Python).
 *
 * La pagina del creatore parla con un "server" tramite fetch('/api/...'). Sul PC quel server è Flask
 * (python -m dnd5e web); sul sito invece questo file intercetta le stesse chiamate e le esegue con il
 * motore Python vero, caricato nel browser con Pyodide. Regole, calcoli e PDF sono identici.
 *
 * I personaggi e i ritratti restano nel browser di chi li crea (localStorage): niente dati sul server.
 */
(function () {
  "use strict";

  var PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.29.3/full/";
  var HERE = new URL(".", document.currentScript ? document.currentScript.src : location.href).href;
  var KEY_CHARS = "dnd5e.sito.personaggi";
  var KEY_PORTRAIT = "dnd5e.sito.ritratto.";
  var origFetch = window.fetch.bind(window);
  var outputs = {};          // "/output/<file>" -> blob URL generati in questa sessione
  var ready = null;

  // ------------------------------------------------------------------ copertina di caricamento
  var cover = null;
  function showCover(text) {
    if (!document.body) { document.addEventListener("DOMContentLoaded", function () { showCover(text); }); return; }
    if (!cover) {
      cover = document.createElement("div");
      cover.id = "py-cover";
      cover.setAttribute("role", "status");
      cover.style.cssText = "position:fixed;inset:0;z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;" +
        "gap:18px;background:radial-gradient(ellipse at center,#2a1b10 0%,#0d0907 75%);color:#f3dfa8;font:600 18px/1.4 Georgia,serif;text-align:center;padding:24px";
      cover.innerHTML = '<div style="width:64px;height:64px;border:3px solid rgba(243,223,168,.25);border-top-color:#e8b04a;border-radius:50%;animation:pyspin 1s linear infinite"></div>' +
        '<div id="py-cover-text"></div><div style="font:400 13px/1.4 system-ui,sans-serif;color:#c9b38a;max-width:420px">La prima volta serve circa mezzo minuto: il libro delle regole viene caricato nel tuo browser. Le volte dopo è molto più veloce.</div>' +
        "<style>@keyframes pyspin{to{transform:rotate(360deg)}}</style>";
      document.body.appendChild(cover);
    }
    cover.style.display = "flex";
    cover.querySelector("#py-cover-text").textContent = text;
  }
  function hideCover() { if (cover) cover.style.display = "none"; }
  function failCover(err) {
    showCover("Non sono riuscito a preparare il creatore.");
    var t = cover.querySelector("#py-cover-text");
    t.innerHTML = "Non sono riuscito a preparare il creatore.<br><small style='font:400 13px system-ui'>" +
      String(err && err.message || err).replace(/</g, "&lt;") + "<br>Controlla la connessione e ricarica la pagina.</small>";
  }

  function loadScript(src) {
    return new Promise(function (ok, ko) {
      var s = document.createElement("script");
      s.src = src; s.onload = ok; s.onerror = function () { ko(new Error("impossibile caricare " + src)); };
      document.head.appendChild(s);
    });
  }

  // ------------------------------------------------------------------ avvio di Python
  async function boot() {
    showCover("Apro il grimorio…");
    await loadScript(PYODIDE + "pyodide.js");
    var py = await window.loadPyodide({ indexURL: PYODIDE });
    showCover("Preparo gli ingredienti magici…");
    await py.loadPackage(["pyyaml", "pillow", "charset-normalizer", "micropip"]);
    var manifest = await (await origFetch(HERE + "py/manifest.json", { cache: "no-cache" })).json();
    var micropip = py.pyimport("micropip");
    await micropip.install(manifest.wheels.map(function (w) { return HERE + "py/" + w; }), { deps: false });
    showCover("Carico le regole del Manuale…");
    var zip = await (await origFetch(HERE + "py/" + manifest.app + "?v=" + manifest.version)).arrayBuffer();
    py.unpackArchive(zip, "zip", { extractDir: "/app" });
    py.runPython("import sys\nsys.path.insert(0, '/app')\nimport dnd5e.webcore as W\nW.init('/app')");
    hideCover();
    return py;
  }
  function start() {
    if (!ready) ready = boot().catch(function (e) { failCover(e); throw e; });
    return ready;
  }

  // ------------------------------------------------------------------ archivio nel browser
  function loadChars() { try { return JSON.parse(localStorage.getItem(KEY_CHARS) || "{}"); } catch (e) { return {}; } }
  function saveChars(all) { try { localStorage.setItem(KEY_CHARS, JSON.stringify(all)); } catch (e) { /* spazio pieno: pazienza */ } }

  function json(data, status) {
    return new Response(JSON.stringify(data), { status: status || 200, headers: { "Content-Type": "application/json" } });
  }

  function writePortrait(py, stem, dataUrl) {
    if (!dataUrl) return;
    var bin = atob(dataUrl.split(",")[1]);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    py.FS.mkdirTree("/app/characters/" + stem);
    py.FS.writeFile("/app/characters/" + stem + "/portrait.jpg", bytes);
  }

  // riduce l'immagine a max 700 px e la salva come JPEG (sta comodamente nel localStorage)
  function shrink(file) {
    return new Promise(function (ok, ko) {
      var img = new Image();
      img.onload = function () {
        var s = Math.min(1, 700 / Math.max(img.width, img.height));
        var c = document.createElement("canvas");
        c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        ok(c.toDataURL("image/jpeg", 0.88));
        URL.revokeObjectURL(img.src);
      };
      img.onerror = function () { ko(new Error("immagine non leggibile")); };
      img.src = URL.createObjectURL(file);
    });
  }

  function call(py, method, path, body) {
    var api = py.globals.get("W") || py.pyimport("dnd5e.webcore");
    var out = api.api(method, path, body || "");
    return JSON.parse(out);
  }

  function blobFromFS(py, fsPath, type) {
    var data = py.FS.readFile(fsPath);
    return URL.createObjectURL(new Blob([data], { type: type }));
  }

  // ------------------------------------------------------------------ le chiamate della pagina
  async function handle(method, route, init) {
    var py = await start();
    var body = init && init.body;

    if (route === "ping") return json({ ok: true, mode: "browser" });

    if (route === "characters" && method === "GET") {
      var all = loadChars();
      return json(Object.keys(all).sort().map(function (stem) {
        var c = all[stem] || {};
        var pic = c.portrait ? localStorage.getItem(KEY_PORTRAIT + c.portrait.split("/")[0]) : null;
        return { stem: stem, name: c.name || stem, player: c.player || "", race: c.race || "", "class": c["class"] || "", level: c.level || 1,
                 portrait: c.portrait || null, portrait_url: pic };
      }));
    }
    var m = route.match(/^characters\/([a-z0-9_\-]+)$/);
    if (m) {
      var ch = loadChars()[m[1]];
      return ch ? json(ch) : json({ ok: false, error: "Personaggio non trovato" }, 404);
    }

    if (route === "portrait" && method === "POST") {
      var stem = (body.get("stem") || "personaggio").toString().toLowerCase().replace(/[^a-z0-9_\-]/g, "_");
      var file = body.get("file");
      var dataUrl = await shrink(file);
      try { localStorage.setItem(KEY_PORTRAIT + stem, dataUrl); } catch (e) { /* troppo grande */ }
      writePortrait(py, stem, dataUrl);
      return json({ ok: true, portrait: stem + "/portrait.jpg", url: dataUrl });
    }

    if (route === "build" && method === "POST") {
      var payload = JSON.parse(body);
      var char = payload.character || payload;
      var guess = (char.portrait || "").split("/")[0];
      if (guess) writePortrait(py, guess, localStorage.getItem(KEY_PORTRAIT + guess));
      var res = call(py, "POST", "build", JSON.stringify(payload));
      if (res.ok) {
        ["pdf_url", "guide_url", "md_url"].forEach(function (k) {
          if (!res[k]) return;
          var file = res[k].split("/").pop();
          var type = file.endsWith(".pdf") ? "application/pdf" : "text/markdown";
          var url = blobFromFS(py, "/app/output/" + file, type);
          outputs["/output/" + file] = url;
          res[k] = url;
        });
        var all = loadChars();
        all[res.stem] = char;
        saveChars(all);
      }
      return json(res, res.ok ? 200 : 400);
    }

    var text = typeof body === "string" ? body : "";
    return json(call(py, method, route, text));
  }

  window.fetch = function (input, init) {
    var url = new URL(typeof input === "string" ? input : input.url, location.href);
    var method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
    var api = url.pathname.match(/\/api\/(.+)$/);
    if (api) {
      return handle(method, api[1].replace(/\/$/, ""), init).catch(function (e) {
        return json({ ok: false, error: String(e && e.message || e) }, 500);
      });
    }
    var out = url.pathname.match(/\/output\/([^\/]+)$/);
    if (out && outputs["/output/" + out[1]]) return origFetch(outputs["/output/" + out[1]]);
    return origFetch(input, init);
  };

  window.DND_BROWSER_MODE = true;
  window.dndOutputUrl = function (path) { return outputs[path] || path; };
  start();
})();
