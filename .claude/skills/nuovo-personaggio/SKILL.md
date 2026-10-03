---
name: nuovo-personaggio
description: Crea (o modifica) un personaggio di D&D 5e secondo le regole ufficiali del Manuale del Giocatore 2014 e genera il PDF della scheda dal template ufficiale con etichette italiane, più la guida semplice. Usala ogni volta che l'utente chiede una scheda, un personaggio, un PG, un cambio di livello o di incantesimi in questo progetto.
---

# Procedura: dal personaggio richiesto al PDF

Tutto ciò che legge l'utente va in italiano. Va veloce: le domande si fanno in un blocco solo, e ogni PDF si consegna appena è pronto.

## 0. Prepara

```bash
git pull origin claude/jolly-rubin-vupjy9
pip install -r requirements.txt
```

Leggi `RIPRENDI-DA-QUI.md`: dice a che punto sono i dati di regole e chi sono i personaggi.

## 1. Raccogli quello che l'utente ha già dato

Nome, giocatore o giocatrice (con l'età, se è un bambino), razza, classe, livello e storia. Le immagini mandate in chat si trovano nella cartella **Download**: prendi la più recente e ritagliala con Pillow in `characters/<nome>/portrait.jpg`. Dalla storia ricava background, allineamento, tratti, ideali, legami, difetti e aspetto.

## 2. Fai le domande sulle scelte che mancano

Usa AskUserQuestion: massimo 4 domande per blocco e 4 opzioni per domanda. La prima opzione è quella "(Consigliato)" e l'anteprima mostra i dettagli. Una scelta di poco conto si decide da soli e si dice in una riga. Cosa chiedere, in base al personaggio:

- razza e sottorazza; per il dragonide il colore del drago (`draconic_ancestry`);
- classe e sottoclasse, se il livello la prevede (`subclass_level` in `dnd5e/rules/classes.yaml`);
- background, che si deduce dalla storia (`dnd5e/rules/backgrounds.yaml`);
- caratteristiche: proponi 2-3 build già calcolate col point buy (27 punti, valori da 8 a 15 prima dei bonus razziali);
- abilità di classe, che non devono doppiare quelle di razza e background;
- trucchetti, incantesimi preparati o conosciuti e, per il mago, il libro (`spellbook`, 6 + 2 per livello);
- opzioni di classe (`option_lists` nella classe: suppliche, metamagia, nemico prescelto...) da mettere in `class_options`;
- dal 4° livello in su: aumento delle caratteristiche (`abilities.asi`) o talento (`dnd5e/rules/feats.yaml`);
- linguaggi extra e strumenti;
- versione semplice (`simple: true`) se gioca un bambino, e `gender: f` per i nomi al femminile.

Per vedere le opzioni: `python -m dnd5e list races|classes|backgrounds|weapons|armor|cantrips|fighting_styles|packs`.

## 3. Scrivi il personaggio

Copia `characters/kate.yaml` (incantatrice), `characters/reyla.yaml` (druida) o `characters/examples/reyla_guerriera.yaml` (guerriera) in `characters/<nome>.yaml`. Cambia solo le **scelte**: tutto il resto lo calcola il motore. Scrivi una riga di commento per ogni scelta.

## 4. Genera e correggi

```bash
python -m dnd5e build characters/<nome>.yaml
```

Escono `output/<nome>.pdf`, `output/<nome>.md` e, con `simple: true`, `output/<nome>_guida.pdf`.
- `ERRORE REGOLE`: c'è una scelta non permessa. Correggila o chiedi.
- `AVVISO`: c'è qualcosa da completare (linguaggi, numero di incantesimi...). Risolvilo.
- Se manca una regola (sottoclasse, incantesimo, talento, bestia), aggiungila nel YAML giusto di `dnd5e/rules/` con lo stesso schema delle voci vicine: campi `name`, `name_f`, `short`, `text`, `kid`, `tip`. Il codice non si tocca.

## 5. Controlla il PDF a occhio

Trasforma le pagine in immagini (pymupdf, `page.get_pixmap(dpi=110)`) e guardale. Controlla che i testi stiano nei riquadri, che i valori e il ritratto siano giusti e che i pallini degli incantesimi preparati siano corretti.

## 6. Consegna

- `git add` di `characters/`, `output/` e delle regole cambiate, poi commit e **push subito** sul branch `claude/jolly-rubin-vupjy9`;
- aggiorna `RIPRENDI-DA-QUI.md` (tabella dei personaggi e scelte fatte);
- manda i PDF con SendUserFile e una didascalia in italiano;
- riassumi in poche righe le scelte fatte da soli, che l'utente può cambiare.

## Per cambiare un personaggio esistente

Modifica il suo YAML: livello (con `xp`), nuovi incantesimi, ASI o talento, nuove opzioni di classe. Poi ripeti i passi 4-6. Al passaggio di livello chiedi solo le scelte nuove di quel livello.
