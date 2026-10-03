# Checklist di consegna

Comandi per ripartire in locale:

```bash
git pull origin claude/jolly-rubin-vupjy9
pip install -r requirements.txt
python -m dnd5e build characters/reyla.yaml
```

## Completato

- [x] Motore di calcolo `dnd5e/engine.py`, renderer `dnd5e/sheet.py`, CLI `dnd5e/cli.py`.
- [x] Regole PHB 2014 in `dnd5e/rules/*.yaml`. Guerriero e Druido completi; altre classi parziali.
- [x] Template ufficiale inglese in `templates/official/` con le coordinate dei campi.
- [x] Template italiano in `templates/official_it/`, generato da `tools/make_italian_template.py` (richiede PyMuPDF).
- [x] Reyla: Elfa Alta, Druida, Circolo della Luna, livello 3, Forestiero, giocatrice Arianna, template italiano.
- [x] Versione guerriera di esempio in `characters/examples/`.
- [x] Prime due verifiche contro il Manuale applicate.

## Da fare

- [ ] Arianna deve scegliere 2 trucchetti, 5 incantesimi e il trucchetto da elfa. Ora in `characters/reyla.yaml` ci sono valori provvisori.
- [ ] Modalità semplice per una bambina di 10 anni: testi brevi e facili su privilegi e tratti, togliere ciò che è superfluo, niente appendice nella scheda.
- [ ] Secondo PDF "guida": come si gioca un turno, ogni incantesimo scegliibile spiegato in parole semplici (tempo di lancio, distanza, durata, dadi), ogni animale della Forma Selvatica con PF, CA, velocità, attacchi spiegati.
- [ ] Nomi al femminile se il personaggio è donna: Elfa Alta, Druida, Forestiera.
- [ ] Tutto in italiano anche nel riepilogo `.md` e nelle note: abbreviazioni Des/Sag/Int, monete mo/ma/mr.
- [ ] Ultime correzioni dalla terza verifica:
  - `beasts.yaml`: giant_toad e giant_frog, "afferrato e trattenuto" con CD 13 e CD 11.
  - `beasts.yaml`: giant_wolf_spider e giant_spider, "metà se supera; paralizzato se scende a 0 PF".
  - `classes.yaml`: aggiungere `prepared: ability_plus_level` a paladin, wizard e cleric.
  - `spells.yaml`: aggiungere la tabella `slots.pact` del warlock.
- [ ] Completare le altre classi e le sottoclassi mancanti quando servono.
