# Regole delle classi: come sono fatti i file

Una classe per file (la chiave in cima è la chiave della classe); il motore li unisce in `rules['classes']`.
Ci sono tutte le 12 classi del Manuale del Giocatore (PHB 2014), con i privilegi dal 1° al 20° livello e le sottoclassi
del manuale. Testi riassunti con parole nostre; distanze in metri (1,5 m = 5 piedi). Ogni file comincia con un commento
che spiega i campi macchina usati solo lì.

## Radice della classe

- `name`, `name_f` (femminile), `name_en`, `hit_die`, `saves`, `armor`, `weapons` (categorie o chiavi di arma),
  `skill_choices` {count, from}, `starting_equipment`, `subclass_level`, `subclass_label`, `asi_levels`, `features`,
  `subclasses`, `option_lists`, `table`, `spellcasting`.
- `tools`: solo gli strumenti fissi, con i nomi di `equipment.yaml > tools`.
- `tool_choice: {count, label}`: strumenti a scelta della classe (bardo: 3 strumenti musicali; monaco: uno strumento
  da artigiano o musicale). Quelli scelti vanno in `tools` del personaggio. In un privilegio, `tool_choice: N` (numero)
  vuol dire N strumenti a scelta (Studioso di Guerra).
- `always_prepared_tag`: etichetta degli incantesimi sempre preparati sulla scheda e nella guida (dominio, circolo,
  giuramento...).
- `martial_arts: {die_column, weapons, simple_melee, exclude_properties, requires_unarmored}`: Arti Marziali del monaco
  (colonna di `table` con il dado, armi da monaco in più, armi semplici da mischia senza le proprietà escluse, e se
  servono senza armatura né scudo).
- `table`: colonne per livello, liste di 20 valori (indice 0 = 1° livello). Ogni colonna si usa nei testi come
  `{t_<colonna>}`. Può stare anche nella sottoclasse: il Maestro di Battaglia ha `maneuvers_known`,
  `superiority_dice` e `superiority_die` (d8, d10 dal 10°, d12 dal 18°).

## Privilegi (`features`: livello -> lista di voci)

Testi: `name`, `name_f`, `short` (riga per la scheda), `text` (descrizione completa), `kid` (versione semplice, in
seconda persona, con i numeri veri).

- `kid_hide: true`: voce nascosta nella versione semplice.
- `sheet_hide`: voce nascosta sulla scheda completa. Se manca vale come `kid_hide`; `sheet_hide: false` = nascosta ai
  bambini ma visibile sulla scheda completa.
- `replaces`: nome (o lista di nomi, al maschile) dei privilegi precedenti che questa voce sostituisce (Attacco Extra,
  Indomito, Superiorità Migliorata...).
- `half_proficiency_checks`: `true` = metà del bonus di competenza (per difetto) alle prove senza competenza
  (Factotum); `{abilities: [str, dex, con], round: up}` = solo per quelle caratteristiche, per eccesso (Atleta
  Straordinario). Vale anche per l'iniziativa.
- `fighting_style: true` + `fighting_style_options: [...]` (chiavi di `equipment.yaml > fighting_styles`): il
  privilegio dà uno stile di combattimento; ogni privilegio così ne chiede uno diverso (nel personaggio:
  `fighting_style` / `fighting_styles`).
- `cantrip_damage_bonus: {ability, lists | spells}`: somma il modificatore ai danni dei trucchetti di classe delle
  liste indicate (`lists`) o dei trucchetti indicati (`spells`): Incantesimi Potenziati, Evocazione Potenziata...
- `expertise_count` / `expertise_from`: Maestria (quante abilità ed eventualmente da quali). `expertise_tools: [chiavi
  di equipment.yaml > tools]`: strumenti in cui si può prendere Maestria al posto di un'abilità (ladro:
  `thieves_tools`).
- `spellbook_add: <chiave>`: incantesimo aggiunto gratis al libro, fuori dal conto 6 + 2 per livello.
- `combat_wild_shape: true`: Forma Selvatica da Combattimento (testi semplici e cura con gli slot).
- Altri campi (`grants_cantrip`, `cantrip_choice`, `bonus_proficiencies`, `save_proficiencies`, `speed_bonus`,
  `speed_bonus_table`, `unarmored_ac`, `uses_table`, `damage_bonus_table`, `ability_bonus`/`ability_max`,
  `initiative_advantage`, `ritual_only_spells`, `arcanum_level`, `ki_spells`...): vedi il commento in cima al file
  che li usa.

## Sottoclassi (`subclasses`)

- `name`, `name_f`, `name_en`, `features` (stesso schema), `table`, `option_lists`, `spellcasting` (terzi incantatori),
  `save_dc: {ability, placeholder}` (come calcolare `{cd}`).
- `always_prepared: {livello: [chiavi]}`: incantesimi sempre preparati (dominio, giuramento), fuori dal limite.
- `circle_spells: {terreno: {livello: [chiavi]}}` + `terrain_labels: {terreno: nome italiano}`: Circolo della Terra;
  il personaggio sceglie con `circle_terrain` (arctic, coast, desert, forest, grassland, mountain, swamp, underdark).
- `expanded_spells: {livello: [chiavi]}`: lista ampliata del patrono (warlock).
- `wild_shape: {livello: {cr, fly, swim, uses, elementals}}`: Forma Selvatica. `cr: "level/3"` = livello da druido
  diviso 3; `uses: null` = illimitati; `elementals: true` = anche gli elementali di `beasts.yaml` (`elemental: true`,
  costano 2 usi).

## Liste di opzioni (`option_lists`)

`{label, level, count | count_table, items}`: `level` = livello da cui si sceglie; `count_table` = colonna di `table`
con quante opzioni si hanno. Il personaggio sceglie in `class_options: {lista: [chiavi o {key, ...}]}`.
Campi di ogni opzione (`items`): `name`, `name_f`, `short`, `text`, `kid`, `kid_hide`, `sheet_hide`, `replaces`;
`prerequisite` (testo); controlli `min_level`, `requires_pact`, `requires_cantrip`; costi `cost` / `ki_cost`;
incantesimi dati dall'opzione `spell`, `spell_uses`, `spell_choice`, `cantrip_choice`; `skills`;
`cantrip_damage_bonus`; `damage_type`, `range_override`.

## Segnaposto nei testi (`short`, `text`, `kid`)

- `{livello}` livello di classe; `{cd}` `{att}` `{mod}` CD, attacco e modificatore da incantatore (o del ki, o della
  sottoclasse con `save_dc`); `{t_<colonna>}` valore di `table` al livello attuale.
- `{forma_ore}` durata e `{forma_gs}` GS massimo della Forma Selvatica.
- `{cd_manovre}` CD delle manovre (8 + competenza + mod. FOR o DES, il migliore) e `{t_superiority_die}` dado di
  superiorità (anche per chi ha il talento Adepto Marziale).
- `{soffio_cd}` `{soffio_danni}` `{soffio_tipo}` `{soffio_area}` `{soffio_ts}`: arma a soffio del dragonide.
- `{dadi}`: dadi di danno di un trucchetto al livello attuale (testi di `spells.yaml`).
- Genere, per i testi `kid` in seconda persona: `{o}` = o/a per aggettivi e participi riferiti a chi gioca
  ("attent{o}", "te stess{o}", "l{o} tocchi"); `{un_amico}` = un amico / un'amica; `{amici}` = amici / amiche (senza
  articolo). Al femminile il testo resta quello scritto per le bambine; dove servirebbe un articolo si usa una parola
  neutra ("il gruppo", "chi è con te").

Un segnaposto che il motore non conosce resta scritto com'è e il motore lo segnala come avviso.
