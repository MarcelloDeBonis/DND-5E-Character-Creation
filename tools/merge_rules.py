"""Unisce file di regole scritti a parte (es. da un lavoro in parallelo) nei YAML di dnd5e/rules/.

    python tools/merge_rules.py class_bard.yaml spells_L4.yaml feats.yaml ...

- un file con una sola chiave che è una classe (ha `hit_die`) sostituisce quella classe in classes.yaml;
- un file di incantesimi (voci con `level` e `school`) aggiunge in coda a spells.yaml le chiavi nuove;
- un file di talenti (voci con `prerequisite`) diventa / aggiorna dnd5e/rules/feats.yaml.
Ogni file viene controllato con yaml.safe_load prima e dopo l'unione.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

RULES = Path(__file__).resolve().parent.parent / "dnd5e" / "rules"


def merge_class(src: Path, data: dict) -> str:
    key = next(iter(data))
    target = RULES / "classes.yaml"
    text = target.read_text(encoding="utf-8")
    block = src.read_text(encoding="utf-8").rstrip() + "\n\n"
    m = re.search(rf"^{re.escape(key)}:\s*$", text, flags=re.M)
    if m:
        nxt = re.search(r"^[a-z_]+:\s*$", text[m.end():], flags=re.M)
        end = m.end() + nxt.start() if nxt else len(text)
        text = text[:m.start()] + block + text[end:]
    else:
        text = text.rstrip() + "\n\n" + block
    yaml.safe_load(text)
    target.write_text(text, encoding="utf-8")
    return f"classe {key} sostituita"


def merge_spells(src: Path, data: dict) -> str:
    target = RULES / "spells.yaml"
    text = target.read_text(encoding="utf-8")
    marker = f"\n\n  # ---- da {src.name} ----\n"
    if marker in text:  # file già unito: sostituisco il suo blocco con la versione nuova (es. dopo una verifica)
        start = text.index(marker)
        nxt = text.find("\n\n  # ---- da ", start + len(marker))
        text = text[:start] + (text[nxt:] if nxt != -1 else "\n")
    existing = yaml.safe_load(text)["spells"]
    new = {k: v for k, v in data.items() if k not in existing}
    if not new:
        return "nessun incantesimo nuovo"
    dump = yaml.safe_dump(new, allow_unicode=True, sort_keys=False, width=200)
    block = "\n".join(("  " + line) if line else line for line in dump.splitlines())
    text = text.rstrip() + f"\n\n  # ---- da {src.name} ----\n" + block + "\n"
    yaml.safe_load(text)
    target.write_text(text, encoding="utf-8")
    return f"{len(new)} incantesimi aggiunti ({len(data) - len(new)} già presenti)"


def merge_feats(src: Path, data: dict) -> str:
    target = RULES / "feats.yaml"
    old = yaml.safe_load(target.read_text(encoding="utf-8")) if target.exists() else {}
    old = old or {}
    old.update(data)
    header = ("# Talenti del Manuale del Giocatore (PHB 2014). Il personaggio li sceglie con\n"
              "# feats: [alert, {key: resilient, ability: con}, ...]; campi di calcolo: ability_bonus, ability_choice,\n"
              "# initiative_bonus, speed_bonus (m), hp_per_level, passive_bonus, armor_proficiencies, weapon_proficiencies,\n"
              "# skill_choice, languages, save_proficiency_choice.\n")
    target.write_text(header + yaml.safe_dump(old, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    return f"{len(data)} talenti in feats.yaml"


def main(paths):
    for p in map(Path, paths):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        first = next(iter(data.values()), {})
        if len(data) == 1 and isinstance(first, dict) and "hit_die" in first:
            msg = merge_class(p, data)
        elif isinstance(first, dict) and "school" in first:
            msg = merge_spells(p, data)
        elif isinstance(first, dict) and "prerequisite" in first:
            msg = merge_feats(p, data)
        else:
            msg = "tipo di file non riconosciuto, saltato"
        print(f"{p.name}: {msg}")


if __name__ == "__main__":
    main(sys.argv[1:])
