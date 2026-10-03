# D&D 5e Character Creation

Generatore di schede personaggio per Dungeons & Dragons 5a edizione (regole del Manuale del Giocatore 2014), con output sul PDF ufficiale della scheda Wizards of the Coast.

## Come funziona

1. Ogni personaggio è un file YAML in `characters/` (vedi `characters/reyla.yaml`, commentato riga per riga). Si indicano solo le **scelte** (razza, classe, punteggi base, abilità, stile, armi...).
2. Il motore (`dnd5e/engine.py`) applica le regole lette da `dnd5e/rules/*.yaml`: bonus razziali, modificatori, bonus di competenza, tiri salvezza, abilità, CA, punti ferita, attacchi, privilegi per livello, linguaggi, equipaggiamento.
3. Il renderer (`dnd5e/sheet.py`) scrive i valori sul template ufficiale usando le coordinate in `templates/official/fieldmap.yaml`, inserisce il ritratto a pagina 2, compila la pagina incantesimi (trucchetti, slot, incantesimi preparati) quando serve e aggiunge pagine di appendice con le descrizioni complete di tratti, privilegi, incantesimi e la tabella delle forme animali per la Forma Selvatica.

```bash
pip install -r requirements.txt
python -m dnd5e build characters/reyla.yaml        # -> output/reyla.pdf + output/reyla.md (riepilogo)
python -m dnd5e summary characters/reyla.yaml      # solo il riepilogo testuale
python -m dnd5e list races                         # opzioni disponibili: races, classes, backgrounds,
                                                   #   weapons, armor, maneuvers, cantrips, fighting_styles, packs
```

Il motore segnala errori di regole (abilità non di classe, point buy sbagliato, archetipo mancante...) e avvisi (linguaggi non scelti, armatura senza competenza...).

## Struttura

```
dnd5e/
  rules/
    skills.yaml        caratteristiche, abilità, bonus di competenza, PE, point buy, linguaggi, allineamenti
    races.yaml         razze e sottorazze del PHB con i tratti (testo breve + completo)
    classes/           un file per classe (12 classi del PHB complete dal 1° al 20° livello con tutte le sottoclassi)
    feats.yaml         i 42 talenti del PHB
    backgrounds.yaml   i 13 background del PHB
    equipment.yaml     armi, armature, dotazioni, stili di combattimento
    maneuvers.yaml     manovre del Maestro di Battaglia
    spells.yaml        slot per livello (incantatori completi, mezzi, un terzo), trucchetti conosciuti,
                       incantesimi (lista completa del druido fino al 3° livello + trucchetti comuni)
    beasts.yaml        bestie per la Forma Selvatica (GS fino a 1) con statistiche
  engine.py            calcolo della scheda
  sheet.py             rendering PDF
  cli.py               riga di comando
templates/official/    PDF ufficiale WotC (distribuito gratuitamente per uso personale) + mappa dei campi
characters/            un YAML per personaggio, ritratto in characters/<nome>/; characters/examples/ contiene varianti di prova
output/                PDF e riepiloghi generati
```

## Aggiungere un personaggio

Copia `characters/reyla.yaml`, cambia le scelte e lancia `build`. Per opzioni non ancora presenti nei file di regole (una nuova sottoclasse, un talento, un oggetto magico) si aggiunge la voce nel YAML corrispondente in `dnd5e/rules/`: il motore e il renderer non vanno toccati.

Campi liberi utili nel YAML del personaggio: `extra_skills`, `expertise`, `tools`, `background_tools`, `ac_bonus`, `initiative_bonus`, `attacks_notes`, `extra_features`, `allies`, `treasure`, armi personalizzate come `{key: longsword, name: "Spada del Nonno", magic_bonus: 1}`.

## Personaggi

- **Reyla** (giocatrice Arianna) — Elfa Alta, Druida (Circolo della Luna) di 3° livello, Forestiera. `characters/reyla.yaml` → `output/reyla.pdf` + `output/reyla_guida.pdf`.
- **Kate** (giocatrice Rebecca) — Dragonide (drago rosso), Maga (Scuola di Ammaliamento) di 3° livello, Artigiana di Gilda. `characters/kate.yaml` → `output/kate.pdf` + `output/kate_guida.pdf`.

## Versione per bambini e guida

Con `simple: true` nel personaggio la scheda usa testi facili (campi `kid` nei file di regole), mette sulla pagina 2 un riquadro "Come si gioca" e non aggiunge l'appendice. Il comando `build` genera anche `<nome>_guida.pdf`: regole base, una carta per ogni magia (quelle del personaggio evidenziate, poi tutte le altre che può scegliere) e una carta per ogni animale della Forma Selvatica. Con `gender: f` razza, classe e background sono al femminile (`name_f`). `python -m dnd5e build x.yaml --guide` genera la guida anche senza `simple`.
- `characters/examples/reyla_guerriera.yaml` — la stessa Reyla come Guerriera (Maestro di Battaglia), usata come esempio e test della classe.

Chiavi utili per gli incantatori: `cantrips` (trucchetti di classe), `spells` (incantesimi preparati o conosciuti), `spellbook` (libro del mago: `spells` deve esserne un sottoinsieme), `racial_cantrips` (trucchetto razziale, es. Elfo Alto), `circle_terrain` (Circolo della Terra). Dragonide: `draconic_ancestry` (red, black, green...).
