# Riprendi da qui

Generatore di schede personaggio D&D 5e (Manuale del Giocatore 2014) sul PDF ufficiale con etichette italiane.
A cosa serve: con questo repository Claude crea in PDF le schede dei personaggi, seguendo le regole ufficiali.
Ogni personaggio è un file YAML in `characters/`.

## Come si lavora

```bash
git pull origin claude/jolly-rubin-vupjy9
pip install -r requirements.txt
python -m dnd5e build characters/reyla.yaml      # -> output/reyla.pdf, output/reyla.md, output/reyla_guida.pdf
python -m dnd5e build characters/kate.yaml
python tools/make_italian_template.py             # solo se cambiano le etichette del template italiano
```

- `simple: true` nel personaggio = **versione per bambini**. Ha testi facili (campi `kid` nelle regole), il riquadro "Come si gioca" sulla scheda e nessuna appendice. Genera anche la guida `<nome>_guida.pdf`, con una carta per ogni magia e per ogni animale.
- `gender: f` = nomi al femminile (campi `name_f` nelle regole): Elfa Alta, Druida, Maga, Forestiera...
- Il maga/mago usa `spellbook` (il libro) e `spells` (gli incantesimi preparati, che devono stare nel libro).
- Il dragonide usa `draconic_ancestry` (black, blue, brass, bronze, copper, gold, green, red, silver, white).
- Per un personaggio nuovo: copia un YAML, fai a chi gioca le domande sulle scelte (caratteristiche, abilità, incantesimi...), lancia `build`.

Nessun segreto e nessun file fuori da git: tutto quello che serve sta nel repository.

## Personaggi

| Personaggio | Giocatrice | Cosa | File |
|---|---|---|---|
| Reyla | Arianna (10 anni) | Elfa Alta, Druida 3, Circolo della Luna, Forestiera | `characters/reyla.yaml` |
| Kate | Rebecca (10 anni) | Dragonide (drago rosso), Maga 3, Scuola di Ammaliamento, Artigiana di Gilda | `characters/kate.yaml` |

Scelte di Arianna (3/10/2026): trucchetti Produrre Fiamma e Guida, trucchetto da elfa Illusione Minore. Incantesimi preparati: Cura Ferite, Parola Guaritrice, Intralciare, Bacche Benefiche, Bagliore Lunare (nel manuale italiano; prima era scritto "Raggio di Luna"). Abilità: Natura e Sopravvivenza.
Scelte per Rebecca (3/10/2026): background Artigiana di Gilda, drago rosso, Scuola di Ammaliamento. Trucchetti Dardo di Fuoco, Mano Magica, Prestidigitazione. Nel libro: Armatura Magica, Dardo Incantato, Scudo, Sonno, Immagine Silenziosa, Camuffare Se Stesso, Passo Velato, Immagine Speculare, Invisibilità, Suggestione. Preparati: Armatura Magica, Dardo Incantato, Scudo, Sonno, Immagine Speculare. Caratteristiche consigliate (point buy): FOR 10, DES 14, COS 14, INT 15, SAG 10, CAR 11. Abilità: Arcano e Indagare. Ritratto preso da Download.

## A che punto siamo

- [x] Motore, renderer, CLI, template italiano con le etichette che stanno nei riquadri.
- [x] Regole: Guerriero, Druido e Mago completi dal 1° al 20° livello. Le altre classi hanno solo i dati base.
- [x] Incantesimi: tutta la lista del druido fino al 3° livello e del mago fino al 2°, con i testi per bambini.
- [x] Bestie della Forma Selvatica con i testi per bambini e le statistiche verificate.
- [x] Versione semplice, nomi al femminile, guida separata, riepilogo `.md` in italiano.
- [ ] Le altre classi complete, quando servono (un file per classe in `dnd5e/rules/classes/`).
- [ ] Incantesimi di 3° livello e oltre per il mago, quando un personaggio arriva al 5° livello.
- [ ] Nomi italiani incerti di alcuni incantesimi da mago (es. Trucco della Corda, Aura Magica di Nystul): da controllare sul manuale.
