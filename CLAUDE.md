# CLAUDE.md

Leggi per primo `RIPRENDI-DA-QUI.md` (cos'è il progetto, come si genera una scheda, a che punto siamo). Per creare o cambiare un personaggio segui la skill `.claude/skills/nuovo-personaggio/SKILL.md`.

- Questa repository serve a creare in PDF le schede D&D 5e (regole PHB 2014) per i giocatori, a partire dal template ufficiale con etichette italiane.
- Per ogni personaggio nuovo: fai a chi gioca le domande sulle scelte (caratteristiche, abilità, background, incantesimi, ritratto) prima di generare, poi `python -m dnd5e build characters/<nome>.yaml`.
- Le giocatrici attuali hanno 10 anni: usa `simple: true` e `gender: f`. Servono testi brevi e facili e la guida separata.
- Le regole stanno nei YAML di `dnd5e/rules/`. Un'opzione nuova si aggiunge lì, senza toccare il motore.
- Dopo ogni modifica: rigenera i PDF, fai commit e push sul branch `claude/jolly-rubin-vupjy9` e aggiorna `RIPRENDI-DA-QUI.md`.
