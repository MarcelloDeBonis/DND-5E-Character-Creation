"""Interfaccia a riga di comando.

    python -m dnd5e build characters/reyla.yaml            # genera output/reyla.pdf e output/reyla.md
    python -m dnd5e build characters/reyla.yaml -o x.pdf   # percorso di uscita personalizzato
    python -m dnd5e summary characters/reyla.yaml          # stampa il riepilogo senza generare il PDF
    python -m dnd5e list races|classes|backgrounds|weapons|armor|maneuvers|cantrips
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import RulesError, build_sheet, load_character, load_rules, sheet_markdown
from .sheet import SheetRenderer

ROOT = Path(__file__).resolve().parent.parent


def cmd_build(args):
    rules = load_rules()
    char = load_character(args.character)
    sheet = build_sheet(char, rules)
    out = Path(args.output) if args.output else ROOT / "output" / f"{char['_stem']}.pdf"
    renderer = SheetRenderer(args.template or char.get("template", "official"))
    renderer.render(sheet, out, appendix=not args.no_appendix)
    md = out.with_suffix(".md")
    md.write_text(sheet_markdown(sheet), encoding="utf-8")
    print(f"PDF: {out}\nRiepilogo: {md}")
    if sheet.get("simple") or args.guide:
        from .guide import build_guide
        g = build_guide(sheet, rules, out.with_name(out.stem + "_guida.pdf"))
        print(f"Guida: {g}")
    for w in sheet["warnings"]:
        print(f"AVVISO: {w}")


def cmd_summary(args):
    rules = load_rules()
    sheet = build_sheet(load_character(args.character), rules)
    sys.stdout.write(sheet_markdown(sheet))


def cmd_list(args):
    rules = load_rules()
    tables = {
        "races": rules["races"], "classes": rules["classes"], "backgrounds": rules["backgrounds"],
        "weapons": rules["equipment"]["weapons"], "armor": rules["equipment"]["armor"],
        "maneuvers": rules["maneuvers"], "cantrips": rules["equipment"]["wizard_cantrips"],
        "fighting_styles": rules["equipment"]["fighting_styles"], "packs": rules["equipment"]["packs"],
    }
    table = tables[args.what]
    for key, val in table.items():
        name = val.get("name", "") if isinstance(val, dict) else ""
        extra = ""
        if args.what == "races" and isinstance(val, dict):
            subs = list((val.get("subraces") or {}).keys()) + list((val.get("variants") or {}).keys())
            extra = f"  sottorazze: {', '.join(subs)}" if subs else ""
        if args.what == "classes" and isinstance(val, dict):
            extra = f"  archetipi: {', '.join((val.get('subclasses') or {}).keys()) or '—'}"
        print(f"{key:20s} {name}{extra}")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # console Windows: evita errori con ●, ° ecc.
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="dnd5e", description="Generatore di schede D&D 5e")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="genera il PDF della scheda")
    b.add_argument("character")
    b.add_argument("-o", "--output")
    b.add_argument("-t", "--template", default=None, help="official | official_it (default: campo template del personaggio)")
    b.add_argument("--no-appendix", action="store_true", help="non aggiungere la pagina di appendice")
    b.add_argument("--guide", action="store_true", help="genera anche la guida semplice <nome>_guida.pdf (automatica con simple: true)")
    b.set_defaults(func=cmd_build)
    s = sub.add_parser("summary", help="stampa il riepilogo calcolato")
    s.add_argument("character")
    s.set_defaults(func=cmd_summary)
    l = sub.add_parser("list", help="elenca le opzioni disponibili")
    l.add_argument("what", choices=["races", "classes", "backgrounds", "weapons", "armor", "maneuvers", "cantrips", "fighting_styles", "packs"])
    l.set_defaults(func=cmd_list)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except RulesError as exc:
        print(f"ERRORE REGOLE: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
