/* Forgia degli Eroi: crea un personaggio di D&D 5e (Manuale del Giocatore 2014) passo dopo passo.
 *
 * Nessun framework: lo stato vive in `S` (salvato nel browser), le regole arrivano da /api/rules,
 * cosa resta da scegliere da /api/requirements (con un calcolo locale di riserva) e la scheda
 * calcolata da /api/preview. Alla fine /api/build scrive il YAML e genera i PDF.
 */
'use strict';

/* ------------------------------------------------------------------ costanti */
const ABIL = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
const ABBR = { str: 'FOR', dex: 'DES', con: 'COS', int: 'INT', wis: 'SAG', cha: 'CAR' };
const ABNAME = { str: 'Forza', dex: 'Destrezza', con: 'Costituzione', int: 'Intelligenza', wis: 'Saggezza', cha: 'Carisma' };
const ABHINT = {
  str: 'muscoli: colpire forte, sollevare, saltare',
  dex: 'agilità: schivare, tirare con l\'arco, muoversi furtivi',
  con: 'resistenza: più punti ferita, non stancarsi',
  int: 'studio e memoria: magia dei maghi, ricordare',
  wis: 'intuito e attenzione: magia di druidi e chierici, notare le cose',
  cha: 'personalità: convincere, ingannare, magia di bardi e stregoni',
};
const ALIGN_ORDER = ['LG', 'NG', 'CG', 'LN', 'N', 'CN', 'LE', 'NE', 'CE'];
const ALIGN_HINT = {
  LG: 'Rispetta le regole e protegge chi è debole.',
  NG: 'Fa del bene, senza badare troppo alle regole.',
  CG: 'Segue il cuore e ama la libertà, ma è buono.',
  LN: 'Conta l\'ordine: la legge e la parola data.',
  N: 'Non si schiera: equilibrio prima di tutto.',
  CN: 'Fa quello che vuole, quando vuole.',
  LE: 'Usa le regole per prendersi ciò che vuole.',
  NE: 'Pensa solo a sé, senza scrupoli.',
  CE: 'Fa del male per il gusto di farlo.',
};
const TERRAINS = { arctic: 'Artico', coast: 'Costa', desert: 'Deserto', forest: 'Foresta', grassland: 'Prateria', mountain: 'Montagna', swamp: 'Palude', underdark: 'Underdark' };
const DRAGON_COLORS = { black: '#2d2f36', blue: '#2f6fd6', brass: '#cfa64a', bronze: '#a8692c', copper: '#c0703a', gold: '#e8b93c', green: '#3c9b4d', red: '#c8352a', silver: '#c9d3dc', white: '#f4f4f0' };
const MONEY = [['pp', 'mp', 'platino'], ['gp', 'mo', 'oro'], ['ep', 'me', 'electrum'], ['sp', 'ma', 'argento'], ['cp', 'mr', 'rame']];
const RACE_PITCH = {
  elf: 'Agili e longevi, con sensi acuti e un legame antico con la magia.',
  human: 'Versatili e ambiziosi: bravi un po\' in tutto.',
  dwarf: 'Robusti e testardi, resistono al veleno e conoscono la pietra.',
  halfling: 'Piccoli, svelti e fortunati: la sorte dà loro una mano.',
  half_elf: 'Metà umani e metà elfi: simpatici, versatili, mai fuori posto.',
  half_orc: 'Forti e tenaci: quando cadono, si rialzano.',
  tiefling: 'Sangue infernale: corna, coda e un po\' di magia del fuoco.',
  dragonborn: 'Discendenti dei draghi: soffiano fuoco, ghiaccio, fulmini o acido.',
  gnome: 'Piccoli inventori curiosi, con una mente difficile da ingannare.',
};
const CLASS_PITCH = {
  barbarian: 'Una furia selvaggia: colpisce fortissimo e resiste a tutto.',
  bard: 'Musica e parole magiche: incanta, aiuta gli amici e sa un po\' di tutto.',
  cleric: 'Al servizio di un dio: cura gli amici e scaccia il male.',
  druid: 'Custode della natura: magie della foresta e trasformazioni in animali.',
  fighter: 'Maestria con armi e armature: forte in ogni battaglia.',
  monk: 'Combatte a mani nude, con agilità e un\'energia interiore: il ki.',
  paladin: 'Un giuramento sacro, armatura pesante e magia di luce.',
  ranger: 'Esplorazione e caccia: arco, tracce e magia della natura.',
  rogue: 'Furtività e astuzia: colpi a sorpresa, serrature e trappole.',
  sorcerer: 'La magia ce l\'ha nel sangue: pochi incantesimi, ma potenti e flessibili.',
  warlock: 'Ha stretto un patto con un essere potente in cambio della magia.',
  wizard: 'Studia la magia sui libri: tantissimi incantesimi per ogni occasione.',
};
const CLASS_MAIN = { barbarian: ['str'], bard: ['cha'], cleric: ['wis'], druid: ['wis'], fighter: ['str', 'dex'], monk: ['dex', 'wis'], paladin: ['str', 'cha'], ranger: ['dex', 'wis'], rogue: ['dex'], sorcerer: ['cha'], warlock: ['cha'], wizard: ['int'] };
const CLASS_PRIORITY = {
  barbarian: ['str', 'con', 'dex', 'wis', 'cha', 'int'],
  bard: ['cha', 'dex', 'con', 'wis', 'int', 'str'],
  cleric: ['wis', 'con', 'str', 'dex', 'cha', 'int'],
  druid: ['wis', 'con', 'dex', 'int', 'cha', 'str'],
  fighter: ['str', 'con', 'dex', 'wis', 'cha', 'int'],
  monk: ['dex', 'wis', 'con', 'str', 'int', 'cha'],
  paladin: ['str', 'cha', 'con', 'wis', 'dex', 'int'],
  ranger: ['dex', 'wis', 'con', 'str', 'int', 'cha'],
  rogue: ['dex', 'con', 'int', 'wis', 'cha', 'str'],
  sorcerer: ['cha', 'con', 'dex', 'wis', 'int', 'str'],
  warlock: ['cha', 'con', 'dex', 'wis', 'int', 'str'],
  wizard: ['int', 'con', 'dex', 'wis', 'cha', 'str'],
};
const BUILDS = [
  { name: 'Bravo in tutto', hint: 'Nessun punto debole grave.', values: [15, 14, 13, 12, 10, 8] },
  { name: 'Forte nei punti chiave', hint: 'Le prime tre altissime, le altre basse.', values: [15, 15, 14, 10, 8, 8] },
];
const TOOL_SUGGESTIONS = [
  'Strumenti da fabbro', 'Strumenti da falegname', 'Strumenti da muratore', 'Strumenti da calligrafo', 'Strumenti da cartografo',
  'Strumenti da ciabattino', 'Strumenti da conciatore', 'Strumenti da gioielliere', 'Strumenti da intagliatore', 'Strumenti da inventore',
  'Strumenti da pittore', 'Strumenti da soffiatore di vetro', 'Strumenti da tessitore', 'Strumenti da vasaio', 'Scorte da alchimista',
  'Scorte da birraio', 'Utensili da cuoco', 'Borsa da erborista', 'Arnesi da scasso', 'Arnesi da falsario', 'Trucchi per il camuffamento',
  'Strumenti da navigatore', 'Set di dadi', 'Mazzo di carte da gioco', 'Scacchi dei draghi', 'Flauto', 'Flauto di Pan', 'Liuto', 'Lira',
  'Cornamusa', 'Corno', 'Tamburo', 'Viola', 'Salterio', 'Ciaramella',
];
const STORE_KEY = 'forgia-eroi-v1';

/* ------------------------------------------------------------------ emblemi (SVG inline) */
const EMBLEM_PATHS = {
  // razze
  elf: '<path d="M24 5c10 6 14 17 10 27-3 6-8 9-10 11-2-2-7-5-10-11C10 22 14 11 24 5z"/><path d="M24 10v33M24 20l-5-4M24 27l6-5M24 34l-6-4"/>',
  human: '<circle cx="24" cy="16" r="7"/><path d="M9 41c2-9 8-13 15-13s13 4 15 13"/><path d="M24 3v3M14 6l2 2M34 6l-2 2"/>',
  dwarf: '<path d="M12 19c0-8 5-13 12-13s12 5 12 13"/><path d="M10 19h28"/><path d="M14 19c0 13 4 21 10 24 6-3 10-11 10-24"/><path d="M19 27v8M24 27v12M29 27v8"/>',
  halfling: '<path d="M9 41V28a15 15 0 0 1 30 0v13z"/><path d="M19 14.5V41M29 14.5V41"/><circle cx="33" cy="31" r="1.6" fill="currentColor"/><path d="M4 41h40"/>',
  half_elf: '<path d="M24 5c10 6 14 17 10 27-3 6-8 9-10 11z"/><path d="M24 5v38"/><path d="M24 14c-7 0-11 6-11 13s4 12 11 13"/><path d="M24 22l5-4M24 29l5-4"/>',
  half_orc: '<path d="M10 19c0 13 6 22 14 22s14-9 14-22"/><path d="M16 27l2-11 3 10M32 27l-2-11-3 10"/><path d="M11 12l9 4M37 12l-9 4"/>',
  tiefling: '<path d="M17 21c-8-2-12-10-9-16 2 5 6 7 11 8"/><path d="M31 21c8-2 12-10 9-16-2 5-6 7-11 8"/><circle cx="24" cy="29" r="10"/><path d="M34 33c5 2 7 6 5 10l-3-2"/>',
  dragonborn: '<path d="M4 24c6-9 13-13 20-13s14 4 20 13c-6 9-13 13-20 13S10 33 4 24z"/><path d="M24 14.5c-3 5-3 14 0 19 3-5 3-14 0-19z" fill="currentColor"/>',
  gnome: '<circle cx="24" cy="24" r="9"/><circle cx="24" cy="24" r="3.5"/><path d="M24 6v7M24 35v7M6 24h7M35 24h7M11.3 11.3l5 5M31.7 31.7l5 5M11.3 36.7l5-5M31.7 16.3l5-5"/>',
  // classi
  fighter: '<path d="M9 9l22 22M39 9L17 31"/><path d="M26 35l9-9M13 26l9 9"/><path d="M33 37l4 4M15 37l-4 4"/>',
  barbarian: '<path d="M24 5v39"/><path d="M24 11c-8-4-15 0-17 8 2 8 9 12 17 7"/><path d="M24 11c8-4 15 0 17 8-2 8-9 12-17 7"/>',
  bard: '<path d="M14 9c-5 9-3 21 10 27 13-6 15-18 10-27"/><path d="M14 9c3 0 5 2 5 5M34 9c-3 0-5 2-5 5"/><path d="M18 18h12M21 18v13M24 18v15M27 18v13"/><path d="M19 41h10M24 36v5"/>',
  cleric: '<circle cx="24" cy="15" r="7"/><path d="M24 22v21M14 30h20"/><path d="M24 2.5v2.5M12.5 6.5l1.8 1.8M35.5 6.5l-1.8 1.8M9 15h2.5M36.5 15H39"/>',
  druid: '<path d="M31 5a17 17 0 1 0 12 28A15 15 0 0 1 31 5z"/><path d="M12 33c4-7 11-8 14-5-2 7-9 9-14 5z"/><path d="M12 33l7-4"/>',
  monk: '<circle cx="24" cy="24" r="18"/><path d="M24 6a9 9 0 0 1 0 18 9 9 0 0 0 0 18"/><circle cx="24" cy="15" r="2.2" fill="currentColor"/><circle cx="24" cy="33" r="2.2"/>',
  paladin: '<path d="M24 5l15 5v12c0 10-7 17-15 21C16 39 9 32 9 22V10z"/><path d="M24 13v21M17 21h14"/>',
  ranger: '<path d="M13 5c14 7 20 21 13 38"/><path d="M13 5l13 38" stroke-dasharray="2 3"/><path d="M5 31l35-19"/><path d="M40 12l-7 .5M40 12l-3 6"/><path d="M8 29l-3 5M11 27.5l-3 5"/>',
  rogue: '<path d="M4 19c6-4 14-4 20 1 6-5 14-5 20-1-1 9-6 13-11 13-4 0-7-3-9-6-2 3-5 6-9 6-5 0-10-4-11-13z"/><circle cx="14.5" cy="22.5" r="3"/><circle cx="33.5" cy="22.5" r="3"/>',
  sorcerer: '<path d="M24 4c3 8 12 12 12 24a12 12 0 0 1-24 0c0-6 3-9 5-12 0 4 2 6 4 6-2-8 1-13 3-18z"/><path d="M24 30c2 2 4 4 4 7a4 4 0 0 1-8 0c0-3 2-5 4-7z"/>',
  warlock: '<path d="M24 5l19 35H5z"/><path d="M13.5 30c3-4 6.5-6 10.5-6s7.5 2 10.5 6c-3 4-6.5 6-10.5 6s-7.5-2-10.5-6z"/><circle cx="24" cy="30" r="2.6" fill="currentColor"/>',
  wizard: '<path d="M16 44l13-29"/><circle cx="31.5" cy="10" r="6"/><path d="M31.5 4v-1M37.5 10h1M10 12l1.6 3.4 3.4 1.6-3.4 1.6L10 22l-1.6-3.4L5 17l3.4-1.6zM40 26l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"/>',
  // generici
  tunic: '<path d="M17 6l-9 5 3 8 4-2v24h18V17l4 2 3-8-9-5c-1.5 3-4 4.5-7 4.5S18.5 9 17 6z"/><path d="M15 30h18"/>',
  cuirass: '<path d="M15 6h18l6 7-4 5v19l-11 6-11-6V18l-4-5z"/><path d="M24 12v30M17 22c4 2 10 2 14 0"/>',
  d20: '<path d="M24 4l17 10v20L24 44 7 34V14z"/><path d="M24 4l-9 16h18zM15 20l9 24 9-24M7 14l8 6M41 14l-8 6M7 34l8-14M41 34l-8-14"/>',
  scroll: '<path d="M12 8h22a5 5 0 0 1 0 10H14"/><path d="M12 8a4 4 0 0 0-4 4v24a4 4 0 0 0 4 4h22a4 4 0 0 0 4-4V18"/><path d="M14 26h16M14 32h12"/>',
  lock: '<rect x="12" y="21" width="24" height="19" rx="3"/><path d="M17 21v-6a7 7 0 0 1 14 0v6"/><circle cx="24" cy="30" r="2.4" fill="currentColor"/>',
  check: '<path d="M10 25l9 9 19-20"/>',
  star: '<path d="M24 3l4.5 15.5L44 24l-15.5 4.5L24 44l-4.5-15.5L4 24l15.5-5.5z"/>',
};
function emblem(key, cls = 'emblem') {
  const p = EMBLEM_PATHS[key] || EMBLEM_PATHS.d20;
  return `<svg class="${cls}" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${p}</svg>`;
}

/* ------------------------------------------------------------------ utilità */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const clone = (o) => JSON.parse(JSON.stringify(o));
const modOf = (score) => Math.floor((score - 10) / 2);
const fmtMod = (n) => (n >= 0 ? '+' : '−') + Math.abs(n);
const plural = (n, one, many) => (n === 1 ? one : many);
const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const slug = (s) => norm(s).replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
/* Nome del file come lo calcola il programma (webcore.slugify): serve per ritratto e salvataggio. */
const RESERVED_STEMS = new Set(['con', 'prn', 'aux', 'nul', ...[1, 2, 3, 4, 5, 6, 7, 8, 9].flatMap((i) => [`com${i}`, `lpt${i}`])]);
function fileStem(name) {
  let t = String(name || '').normalize('NFKD').replace(/[^\x00-\x7f]/g, '').toLowerCase();
  t = t.trim().replace(/\s+/g, '_').replace(/[^a-z0-9_-]/g, '').replace(/_+/g, '_').replace(/^[_-]+|[_-]+$/g, '').slice(0, 48);
  return RESERVED_STEMS.has(t) ? `${t}_pg` : t;
}
const cap = (s) => { s = String(s || ''); return s.charAt(0).toUpperCase() + s.slice(1); };
const sum = (arr) => arr.reduce((a, b) => a + (Number(b) || 0), 0);
const asList = (v) => (v == null ? [] : Array.isArray(v) ? v : [v]);
const feet2m = (ft) => `${String(Math.round(ft * 0.3 * 10) / 10).replace('.', ',')} m`;
const ord = (n) => `${n}°`;
const numWord = (n) => (['zero', 'uno', 'due', 'tre', 'quattro', 'cinque', 'sei', 'sette', 'otto', 'nove', 'dieci'][n] ?? String(n));
/* Chiavi in ordine alfabetico italiano (abilità, linguaggi...): l'ordine delle regole è quello inglese. */
const sortIt = (keys, nameOf) => [...keys].sort((a, b) => String(nameOf(a)).localeCompare(String(nameOf(b)), 'it'));
/* Testo di una casella (strumenti): le caselle vuote salvate nel browser tornano come null, mai come "null". */
const cellText = (v) => (v == null ? '' : String(v).trim());

/* ------------------------------------------------------------------ stato */
function defaultChar() {
  return {
    name: '', player: '', gender: null, simple: false, template: 'official_it',
    race: null, subrace: null, draconic_ancestry: null,
    class: null, subclass: null, level: 1, xp: 0, background: null, alignment: null,
    abilities: { method: 'point_buy', base: { str: 8, dex: 8, con: 8, int: 8, wis: 8, cha: 8 }, racial_choice: [] },
    hp: { method: 'average' },
    skills: [], background_skills: null, racial_skills: [], extra_skills: [], expertise: [],
    racial_cantrips: [], cantrips: [], spells: [], spellbook: [], circle_terrain: null,
    fighting_style: null, fighting_styles: [], maneuvers: [], class_options: {},
    option_picks: {}, // sotto-scelte delle opzioni di classe: {'pact_boons|pact_of_the_tome': {cantrips: [...]}}
    companion: null, spell_mastery: [], signature_spells: [],
    languages_extra: [], tools: [], background_tools: null,
    armor: null, shield: false, weapons: [], equipment: [], money: { cp: 0, sp: 0, ep: 0, gp: 0, pp: 0 },
    include_background_equipment: true,
    personality: { traits: '', ideals: '', bonds: '', flaws: '' },
    appearance: { age: '', height: '', weight: '', eyes: '', skin: '', hair: '' },
    allies: '', treasure: '', backstory: '', portrait: null,
  };
}
function defaultState() {
  return {
    v: 1, char: defaultChar(), slots: {}, raceFeat: null,
    assign: { standard_array: {}, rolled: {} }, rolls: [null, null, null, null, null, null], rollDice: [],
    step: 0, visited: [0], stem: null, thumb: null, built: null,
    ui: { featOpen: {}, featQuery: {}, spellTab: null, spellQuery: '', bookMode: 'book', heroOpen: false },
  };
}
let S = defaultState();
let RULES = null;
let SERVER_REQ = null; // {key, data}
let PREVIEW = null; // risposta di /api/preview sul personaggio vero
let PREVIEW_PAD = null; // anteprima provvisoria con le scelte mancanti riempite
let CHARS = null; // personaggi salvati
let OFFLINE = false;
let BUILDING = false;
let lastStepRendered = -1;

function saveState() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(S)); } catch (e) { /* browser senza memoria: pazienza */ }
}
function loadState() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || data.v !== 1 || !data.char) return null;
    const base = defaultState();
    return { ...base, ...data, char: { ...defaultChar(), ...data.char }, ui: { ...base.ui, ...(data.ui || {}) } };
  } catch (e) { return null; }
}

/* ------------------------------------------------------------------ API */
async function api(path, opts = {}) {
  let res;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    const err = new Error('offline'); err.offline = true; throw err;
  }
  let data = null;
  try { data = await res.json(); } catch (e) { data = null; }
  if (!res.ok && !(data && (data.error || data.ok === false))) {
    const err = new Error((data && data.error) || `Il programma ha risposto con un errore (${res.status}).`);
    err.status = res.status; throw err;
  }
  return data;
}
const postJSON = (path, body) => api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

/* ------------------------------------------------------------------ regole: accesso */
const isF = () => S.char.gender === 'f';
const nm = (e, fallback = '') => (!e ? fallback : (isF() && e.name_f ? e.name_f : (e.name ?? fallback)));
const raceOf = (c = S.char) => (RULES && c.race ? RULES.races[c.race] || null : null);
function subOf(c = S.char) {
  const r = raceOf(c);
  if (!r || !c.subrace) return null;
  return (r.subraces || {})[c.subrace] || (r.variants || {})[c.subrace] || null;
}
const clsOf = (c = S.char) => (RULES && c.class ? RULES.classes[c.class] || null : null);
function subclassOf(c = S.char) {
  const k = clsOf(c);
  return k && c.subclass ? (k.subclasses || {})[c.subclass] || null : null;
}
function activeSubclass(c = S.char) {
  const k = clsOf(c);
  return k && (c.level || 1) >= (k.subclass_level || 99) ? subclassOf(c) : null;
}
const bgOf = (c = S.char) => (RULES && c.background ? RULES.backgrounds[c.background] || null : null);
const skillName = (k) => RULES?.skills?.skills?.[k]?.it || k;
const skillAbil = (k) => RULES?.skills?.skills?.[k]?.ability || 'str';
const langName = (k) => RULES?.skills?.languages?.[k] || k;
const spellOf = (k) => RULES?.spells?.spells?.[k] || null;
let SPELL_BY_NAME = null;
function spellByName(name) {
  if (!SPELL_BY_NAME) {
    SPELL_BY_NAME = {};
    for (const [k, sp] of Object.entries(RULES.spells.spells || {})) SPELL_BY_NAME[norm(sp.name)] = k;
  }
  return SPELL_BY_NAME[norm(name)] || null;
}
function raceTraits(c = S.char) {
  const r = raceOf(c);
  if (!r) return [];
  const s = subOf(c);
  let t = s && s.replaces_traits ? [] : [...(r.traits || [])];
  if (s) t = t.concat(s.traits || []);
  return t;
}
function raceBonus(c = S.char) {
  const r = raceOf(c);
  if (!r) return { fixed: {}, choice: null };
  const s = subOf(c);
  const fixed = s && s.replaces_base_bonus ? {} : { ...(r.ability_bonus || {}) };
  if (s) for (const [k, v] of Object.entries(s.ability_bonus || {})) fixed[k] = (fixed[k] || 0) + v;
  const choice = s && 'ability_choice' in s ? s.ability_choice : (r.ability_choice || null);
  return { fixed, choice };
}
function raceSpeed(c = S.char) {
  const r = raceOf(c); if (!r) return null;
  const s = subOf(c);
  return (s && s.speed) || r.speed || 30;
}
const raceFeatChoice = (c = S.char) => raceTraits(c).some((t) => t.feat_choice);
function levelFeatures(c = S.char) {
  const k = clsOf(c);
  if (!k) return [];
  const lvl = c.level || 1;
  const out = [];
  for (const [L, fs] of Object.entries(k.features || {})) if (+L <= lvl) for (const f of fs || []) out.push({ ...f, level: +L, source: nm(k) });
  const sc = activeSubclass(c);
  if (sc) for (const [L, fs] of Object.entries(sc.features || {})) if (+L <= lvl) for (const f of fs || []) out.push({ ...f, level: +L, source: nm(sc), sub: true });
  out.sort((a, b) => a.level - b.level);
  return out;
}
function classTable(c = S.char) {
  const k = clsOf(c);
  if (!k) return {};
  const sc = activeSubclass(c);
  const cols = { ...(k.table || {}), ...((sc && sc.table) || {}) };
  const lvl = c.level || 1;
  const out = {};
  for (const [col, arr] of Object.entries(cols)) if (Array.isArray(arr) && arr.length >= lvl) out[col] = arr[lvl - 1];
  return out;
}
function featPickOf(f) {
  if (!f || !f.key) return null;
  const feat = RULES.feats?.[f.key];
  const pick = { key: f.key };
  if (feat?.ability_choice && f.ability) pick.ability = f.ability;
  if (feat?.save_proficiency_choice && f.ability) pick.save = f.ability;
  if (feat?.weapon_proficiencies && !Array.isArray(feat.weapon_proficiencies) && f.weapons?.length) pick.weapons = [...f.weapons];
  if ((feat?.cantrip_choice?.lists || feat?.spell_choice) && f.list) pick.list = f.list;
  if (feat?.cantrip_choice && f.cantrips?.length) pick.cantrips = [...f.cantrips];
  if (feat?.spell_choice && f.spells?.length) {
    if ((feat.spell_choice.count || 1) === 1) pick.spell = f.spells[0]; else pick.spells = [...f.spells];
  }
  if (feat?.damage_type_choice && f.damage_type) pick.damage_type = f.damage_type;
  return Object.keys(pick).length === 1 ? f.key : pick;
}
/* Opzioni di classe (suppliche, patti, metamagia...): regola, prerequisiti e sotto-scelte, come engine.resolve_options. */
const optKey = (e) => (e && typeof e === 'object' ? e.key : e);
const listsOk = (sp, allowed) => allowed == null || allowed === 'any' || asList(allowed).some((l) => (sp.lists || []).includes(l));
function optionRule(listKey, itemKey, c = S.char) {
  const sc = activeSubclass(c);
  const k = clsOf(c);
  return sc?.option_lists?.[listKey]?.items?.[itemKey] || k?.option_lists?.[listKey]?.items?.[itemKey] || null;
}
function optionBlocked(it, c = S.char) {
  if (!it) return '';
  if (it.min_level && (c.level || 1) < Number(it.min_level)) return `dal ${ord(it.min_level)} livello`;
  if (it.requires_pact && !asList(c.class_options?.pact_boons).map(optKey).includes(it.requires_pact)) {
    const pact = optionRule('pact_boons', it.requires_pact, c);
    return `serve il ${pact ? nm(pact) : it.requires_pact}`;
  }
  if (it.requires_cantrip && !asList(c.cantrips).includes(it.requires_cantrip)) {
    return `serve il trucchetto ${spellOf(it.requires_cantrip)?.name || it.requires_cantrip}`;
  }
  return '';
}
function optionSubPools(it, c = S.char) {
  const out = {};
  if (!it || !RULES) return out;
  const all = Object.entries(RULES.spells?.spells || {});
  const cc = it.cantrip_choice;
  const sc = it.spell_choice;
  if (cc) out.cantrip = { count: Number(cc.count || 1), pool: all.filter(([, sp]) => sp.level === 0 && listsOk(sp, cc.lists)) };
  if (sc) {
    const maxLv = sc.ritual_only ? Math.max(Number(sc.level || 1), Math.floor(((c.level || 1) + 1) / 2)) : Number(sc.level || 1);
    out.spell = { count: Number(sc.count || 1), ritual: !!sc.ritual_only,
      pool: all.filter(([, sp]) => sp.level >= 1 && sp.level <= maxLv && listsOk(sp, sc.lists) && (!sc.ritual_only || sp.ritual)) };
  }
  for (const v of Object.values(out)) v.pool.sort((a, b) => a[1].name.localeCompare(b[1].name, 'it'));
  return out;
}
/* Compagno animale del Signore delle Bestie: bestie entro GS e taglia (come engine.resolve_companion). */
const SIZE_ORDER = ['minusc', 'picc', 'medi', 'grand', 'enorm', 'mastod'];
const sizeRank = (s) => { const t = String(s || '').toLowerCase(); const i = SIZE_ORDER.findIndex((p) => t.startsWith(p)); return i < 0 ? 2 : i; };
const crText = (cr) => ({ 0: '0', 0.125: '1/8', 0.25: '1/4', 0.5: '1/2' }[cr] ?? String(cr));
function companionOptions(spec) {
  if (!spec) return [];
  const maxCr = Number(spec.max_cr ?? 0.25);
  const maxSize = sizeRank(spec.max_size || 'Media');
  return Object.entries(RULES.beasts || {}).filter(([, b]) => Number(b.cr) <= maxCr && sizeRank(b.size) <= maxSize)
    .sort((a, b) => a[1].name.localeCompare(b[1].name, 'it'));
}
function asiLevelsOf(c = S.char) {
  const k = clsOf(c);
  return (k?.asi_levels || []).filter((l) => l <= (c.level || 1));
}

/* Il personaggio con ASI e talenti ricostruiti dalle scelte per livello (nessuna potatura). */
function baseChar() {
  const c = clone(S.char);
  c.abilities = { ...(c.abilities || {}), asi: [] };
  c.feats = [];
  if (raceFeatChoice(c) && S.raceFeat?.key) c.feats.push(featPickOf(S.raceFeat));
  for (const L of asiLevelsOf(c)) {
    const s = S.slots[L];
    if (!s) continue;
    if (s.type === 'feat') {
      if (s.feat?.key) c.feats.push(featPickOf(s.feat));
    } else {
      const asi = {};
      for (const a of s.asi || []) if (a) asi[a] = (asi[a] || 0) + 1;
      if (Object.keys(asi).length) c.abilities.asi.push(asi);
    }
  }
  return c;
}

function computeScores(c) {
  const base = c.abilities?.base || {};
  const { fixed, choice } = raceBonus(c);
  const out = {};
  for (const a of ABIL) out[a] = { base: base[a] ?? null, race: fixed[a] || 0, extra: 0 };
  if (choice) for (const a of asList(c.abilities?.racial_choice).slice(0, choice.count)) if (out[a]) out[a].race += choice.bonus;
  for (const asi of c.abilities?.asi || []) for (const [a, v] of Object.entries(asi)) if (out[a]) out[a].extra += v;
  for (const f of c.feats || []) {
    const pick = typeof f === 'string' ? { key: f } : f;
    const feat = RULES.feats?.[pick.key];
    if (!feat) continue;
    for (const [a, v] of Object.entries(feat.ability_bonus || {})) if (out[a]) out[a].extra += v;
    if (feat.ability_choice && pick.ability && out[pick.ability]) out[pick.ability].extra += feat.ability_choice.bonus || 1;
  }
  for (const a of ABIL) {
    const b = out[a].base ?? 10;
    out[a].total = b + out[a].race + out[a].extra;
    out[a].mod = modOf(out[a].total);
  }
  return out;
}

/* ------------------------------------------------------------------ requisiti (server + calcolo locale di riserva) */
function reqKeyOf(c) {
  return JSON.stringify([c.race, c.subrace, c.class, c.subclass, c.level, c.background, c.feats, c.abilities, c.circle_terrain]);
}
function localReq(c) {
  const r = {};
  const sk = RULES.skills || {};
  r.point_buy = sk.point_buy;
  r.standard_array = sk.standard_array;
  const race = raceOf(c);
  const traits = raceTraits(c);
  const bg = bgOf(c);
  if (race) {
    const { choice } = raceBonus(c);
    if (choice) r.racial_choice = { count: choice.count, bonus: choice.bonus, exclude: choice.exclude || [] };
    const rs = sum(traits.map((t) => t.skill_choice || 0));
    if (rs) r.racial_skills = { count: rs };
    const cc = traits.find((t) => t.cantrip_choice);
    if (cc) r.racial_cantrip = { count: 1, list: cc.cantrip_choice.list, ability: cc.cantrip_choice.ability };
    if (race.ancestry) r.draconic_ancestry = true;
  }
  const k = clsOf(c);
  const lvl = c.level || 1;
  const feats = (c.feats || []).map((f) => RULES.feats?.[typeof f === 'string' ? f : f.key]).filter(Boolean);
  const features = levelFeatures(c);
  let langs = 0;
  if (race) {
    const s = subOf(c);
    langs += s && s.replaces_traits ? 0 : (race.extra_languages || 0);
    langs += (s && s.extra_languages) || 0;
    langs += sum(traits.map((t) => t.extra_languages || 0));
  }
  if (bg) langs += Number(bg.languages || 0);
  langs += sum(features.map((f) => f.extra_languages || 0)) + sum(feats.map((f) => f.languages || 0));
  if (langs) r.languages = { count: langs };
  const toolSlots = [];
  const addSlots = (n, label, category = null) => { for (let i = 0; i < n; i++) toolSlots.push({ label, category: category || toolCategoryOf(label) }); };
  if (k) {
    for (const t of k.tools || []) addSlots(placeholderCount(t), t);
    if (k.tool_choice && typeof k.tool_choice === 'object') addSlots(Number(k.tool_choice.count || 1), k.tool_choice.label || 'Strumenti a scelta', k.tool_choice.category || null);
  }
  for (const t of traits) addSlots(Number(t.tool_choice || 0), `${nm(t)}: strumento a scelta`, t.tool_choice_category || null);
  for (const f of features) if (Number.isInteger(f.tool_choice)) addSlots(f.tool_choice, `${nm(f)}: strumento a scelta`, f.tool_choice_category || toolCategoryOf(f.short || f.text));
  if (toolSlots.length) r.tools = { count: toolSlots.length, slots: toolSlots };
  if (bg) r.background_skills = { count: (bg.skills || []).length };
  if (!k) return r;
  r.class_skills = { count: k.skill_choices?.count || 0, from: k.skill_choices?.from || [] };
  r.subclass = { required: lvl >= (k.subclass_level || 99), level: k.subclass_level, label: k.subclass_label, options: Object.keys(k.subclasses || {}) };
  const sc = activeSubclass(c);
  if (sc && sc.circle_spells) r.circle_terrain = true;
  if (sc && sc.companion) r.companion = { max_cr: sc.companion.max_cr ?? 0.25, max_size: sc.companion.max_size || 'Media', examples: sc.companion.examples || [] };
  const extra = sum(features.map((f) => f.bonus_proficiencies?.skill_choice?.count || 0)) + sum(feats.map((f) => f.skill_choice?.count || 0));
  if (extra) {
    const from = features.map((f) => f.bonus_proficiencies?.skill_choice?.from).find(Boolean);
    r.extra_skills = { count: extra, from: feats.some((f) => f.skill_choice) ? undefined : from };
  }
  const exp = sum(features.map((f) => f.expertise_count || 0));
  if (exp) r.expertise = { count: exp, from: features.map((f) => f.expertise_from).find(Boolean) };
  // stile di combattimento, manovre, opzioni di classe
  const styleFeats = features.filter((f) => f.fighting_style || /^Stile di Combattimento/.test(f.name || ''));
  if (styleFeats.length) {
    const opts = new Set();
    styleFeats.forEach((f) => (f.fighting_style_options || []).forEach((o) => opts.add(o)));
    r.fighting_style = { count: styleFeats.length, options: opts.size ? [...opts] : Object.keys(RULES.equipment.fighting_styles || {}) };
  }
  if (features.some((f) => /Superiorità in Combattimento/.test(f.name || ''))) {
    r.maneuvers = { count: 3 + 2 * (lvl >= 7) + 2 * (lvl >= 10) + 2 * (lvl >= 15) };
  }
  const tbl = classTable(c);
  const lists = { ...(k.option_lists || {}), ...((sc && sc.option_lists) || {}) };
  const co = {};
  for (const [key, opt] of Object.entries(lists)) {
    if (opt.level && lvl < opt.level) continue;
    const want = opt.count_table ? tbl[opt.count_table] : opt.count;
    if (!want) continue;
    co[key] = { label: opt.label || key, count: want, items: opt.items || {} };
  }
  if (Object.keys(co).length) r.class_options = co;
  r.asi_levels = asiLevelsOf(c);
  r.feats_allowed = true;
  // magia
  const caster = (sc && sc.spellcasting) || k.spellcasting;
  if (caster && caster.type) {
    const list = caster.list || c.class;
    const ck = RULES.spells.cantrips_known || {};
    let cantripCount = null;
    const known = ck[c.class] || (caster.type === 'third' ? ck.third : null);
    if (known) cantripCount = known[lvl - 1];
    for (const col of ['cantrips_known', 'cantrips']) if (Number.isInteger(tbl[col])) cantripCount = tbl[col];
    let bonus = 0;
    const clists = [list];
    for (const f of features) {
      bonus += Number(f.cantrip_bonus || 0);
      const ch = f.cantrip_choice;
      if (ch && typeof ch === 'object' && ch.list) { clists.push(ch.list); bonus += Number(ch.count || 1); }
    }
    if (cantripCount != null && cantripCount + bonus > 0) r.cantrips = { count: cantripCount + bonus, lists: clists };
    const row = RULES.spells.slots?.[caster.type]?.[String(lvl)];
    const slots = {};
    if (Array.isArray(row)) row.forEach((n, i) => { if (n) slots[i + 1] = n; });
    else if (row && typeof row === 'object') slots[row.level] = row.slots;
    const maxL = Math.max(0, ...Object.keys(slots).map(Number));
    if (maxL > 0) {
      const scores = computeScores(c);
      let mode = caster.spellbook ? 'spellbook' : (caster.prepared === 'ability_plus_level' ? 'prepared' : 'known');
      let count = null;
      if (caster.prepared === 'ability_plus_level') count = Math.max(1, scores[caster.ability].mod + (caster.type === 'full' ? lvl : Math.floor(lvl / 2)));
      else if (Number.isInteger(tbl.spells_known)) count = tbl.spells_known + sum(features.map((f) => f.bonus_spells_known || 0));
      const always = [];
      if (sc) {
        for (const [L, keys] of Object.entries(sc.always_prepared || {})) if (+L <= lvl) always.push(...keys);
        if (sc.circle_spells && c.circle_terrain && sc.circle_spells[c.circle_terrain]) {
          for (const [L, names] of Object.entries(sc.circle_spells[c.circle_terrain])) if (+L <= lvl) always.push(...names);
        }
      }
      const extraLists = [];
      if (sc && sc.expanded_spells) extraLists.push('__expanded__');
      r.spells = { mode, count, max_level: maxL, list, always_prepared: always, extra_lists: extraLists };
      if (sc && sc.expanded_spells) r.spells.expanded = Object.values(sc.expanded_spells).flat();
      if (caster.spellbook) r.spellbook = { count: 6 + 2 * (lvl - 1) };
      if (caster.spellbook && lvl >= 18) r.spell_mastery = { count: 2, levels: [1, 2] };
      if (caster.spellbook && lvl >= 20) r.signature_spells = { count: 2, level: 3 };
    }
  }
  return r;
}
function req() {
  const c = baseChar();
  const local = RULES ? localReq(c) : {};
  if (SERVER_REQ && SERVER_REQ.key === reqKeyOf(c) && SERVER_REQ.data) {
    const merged = { ...local, ...SERVER_REQ.data };
    // chiavi presenti in locale ma assenti sul server = non richieste dal server
    return merged;
  }
  return local;
}
const isCaster = (R = req()) => !!(R.cantrips || R.spells || R.spellbook);

/* ------------------------------------------------------------------ personaggio pulito per il server */
function proficientSet(c, R) {
  const set = {};
  const add = (s, src) => { if (s && !set[s]) set[s] = src; };
  for (const t of raceTraits(c)) for (const s of t.skills || []) add(s, 'razza');
  for (const s of asList(c.racial_skills).slice(0, R.racial_skills?.count || 0)) add(s, 'razza');
  for (const s of effectiveBgSkills(c)) add(s, 'background');
  for (const s of asList(c.skills)) add(s, 'classe');
  for (const f of levelFeatures(c)) for (const s of f.bonus_proficiencies?.skills || []) add(s, f.name);
  for (const [s, src] of optionSkills(c, R)) add(s, src);
  if (R.extra_skills) for (const s of extraPicks(c, R)) add(s, 'privilegio o talento');
  return set;
}
/* Le scelte che valgono davvero: senza doppioni e senza quelle uscite dall'elenco dopo un cambio di razza,
 * classe o sottoclasse. Una scelta nascosta ma contata riempirebbe il contatore senza poterla più togliere. */
function knownLangSet(c = S.char, R = req()) {
  return Array.isArray(R.languages?.known) ? new Set(R.languages.known) : knownLanguages(c);
}
function langPicks(c = S.char, R = req()) {
  const known = knownLangSet(c, R);
  return asList(c.languages_extra).filter((l, i, a) => l && !known.has(l) && l !== 'druidic' && l !== 'thieves_cant' && a.indexOf(l) === i);
}
function extraSkillPool(R = req()) {
  return R.extra_skills?.from?.length ? R.extra_skills.from : Object.keys(RULES.skills.skills);
}
function extraPicks(c = S.char, R = req()) {
  const pool = extraSkillPool(R);
  return asList(c.extra_skills).filter((s, i, a) => pool.includes(s) && a.indexOf(s) === i);
}
function expertisePool(c = S.char, R = req()) {
  const prof = proficientSet(c, R);
  return (R.expertise?.from?.length ? R.expertise.from : Object.keys(RULES.skills.skills)).filter((s) => prof[s]);
}
function expertisePicks(c = S.char, R = req()) {
  const pool = expertisePool(c, R);
  return asList(c.expertise).filter((s, i, a) => pool.includes(s) && a.indexOf(s) === i);
}
const toolPicks = (c = S.char) => asList(c.tools).map(cellText);
/* Abilità regalate da un'opzione di classe scelta (es. Influenza Ammaliante: Inganno e Persuasione). */
function optionSkills(c, R) {
  const out = [];
  for (const [key, list] of Object.entries(c.class_options || {})) {
    if (R && R.class_options && !R.class_options[key]) continue;
    for (const ik of asList(list).map(optKey)) {
      const it = optionRule(key, ik, c);
      for (const s of asList(it?.skills)) out.push([s, nm(it, ik)]);
    }
  }
  return out;
}
function effectiveBgSkills(c = S.char) {
  const bg = bgOf(c);
  if (!bg) return [];
  const own = bg.skills || [];
  const over = c.background_skills;
  return Array.isArray(over) && over.length === own.length ? over : own;
}

function compileChar() {
  const c = baseChar();
  const R = req();
  const out = {};
  const keep = (k, v) => {
    if (v == null || v === '' || (Array.isArray(v) && !v.length)) return;
    if (typeof v === 'object' && !Array.isArray(v) && !Object.keys(v).length) return;
    out[k] = v;
  };
  keep('name', (c.name || '').trim());
  keep('player', (c.player || '').trim());
  if (c.gender) out.gender = c.gender;
  out.simple = !!c.simple;
  out.template = c.template || 'official_it';
  keep('race', c.race);
  const race = raceOf(c);
  if (race && c.subrace && subOf(c)) out.subrace = c.subrace;
  if (race?.ancestry && c.draconic_ancestry && race.ancestry[c.draconic_ancestry]) out.draconic_ancestry = c.draconic_ancestry;
  keep('class', c.class);
  const k = clsOf(c);
  if (k && c.subclass && subclassOf(c) && (c.level || 1) >= (k.subclass_level || 99)) out.subclass = c.subclass;
  out.level = Math.min(20, Math.max(1, Number(c.level) || 1));
  if (c.xp != null && c.xp !== '') out.xp = Math.max(0, Number(c.xp) || 0);
  keep('background', c.background);
  keep('alignment', c.alignment);
  // caratteristiche
  const ab = { method: c.abilities.method || 'point_buy', base: {} };
  for (const a of ABIL) { const v = c.abilities.base?.[a]; if (v != null && v !== '') ab.base[a] = Number(v); }
  if (R.racial_choice) ab.racial_choice = asList(c.abilities.racial_choice).filter((a) => !(R.racial_choice.exclude || []).includes(a)).slice(0, R.racial_choice.count);
  if (c.abilities.asi?.length) ab.asi = c.abilities.asi;
  out.abilities = ab;
  if (c.feats?.length) out.feats = c.feats;
  out.hp = c.hp || { method: 'average' };
  // abilità
  const pool = R.class_skills?.from || [];
  let skills = asList(c.skills).filter((s) => !pool.length || pool.includes(s));
  if (R.class_skills?.count) skills = skills.slice(0, R.class_skills.count);
  keep('skills', skills);
  const bg = bgOf(c);
  if (bg && Array.isArray(c.background_skills) && c.background_skills.length === (bg.skills || []).length
      && c.background_skills.join() !== (bg.skills || []).join()) out.background_skills = c.background_skills;
  if (R.racial_skills?.count) keep('racial_skills', asList(c.racial_skills).slice(0, R.racial_skills.count));
  if (R.extra_skills?.count) keep('extra_skills', extraPicks(c, R).slice(0, R.extra_skills.count));
  const prof = proficientSet({ ...c, skills, extra_skills: out.extra_skills || [], racial_skills: out.racial_skills || [] }, R);
  if (R.expertise?.count) {
    const from = R.expertise.from?.length ? R.expertise.from : null;
    keep('expertise', asList(c.expertise).filter((s, i, a) => prof[s] && (!from || from.includes(s)) && a.indexOf(s) === i).slice(0, R.expertise.count));
  }
  // magia
  if (R.racial_cantrip) keep('racial_cantrips', asList(c.racial_cantrips).slice(0, 1));
  if (R.cantrips) keep('cantrips', asList(c.cantrips).filter((key) => spellOf(key)?.level === 0 && !racialCantrips(c).includes(key)));
  if (R.spells) {
    const max = R.spells.max_level || 9;
    const arc = asList(R.spells.arcanum_levels);
    let book = [];
    if (R.spells.mode === 'spellbook' || R.spellbook) {
      book = asList(c.spellbook).filter((key) => { const sp = spellOf(key); return sp && sp.level >= 1 && sp.level <= max; });
      keep('spellbook', book);
    }
    // gli incantesimi sempre preparati (dominio, giuramento, circolo) non si scelgono: non vanno in 'spells'
    const always = alwaysPreparedKeys(R);
    let spells = asList(c.spells).filter((key) => { const sp = spellOf(key); return sp && sp.level >= 1 && (sp.level <= max || arc.includes(sp.level)) && !always.has(key); });
    if (R.spells.mode === 'spellbook') spells = spells.filter((key) => book.includes(key));
    // Maestria (18°) e Incantesimi Personali (20°): il programma li accetta solo completi, quindi si mandano solo così
    const inBook = new Set(book);
    if (R.spell_mastery) {
      const m = asList(c.spell_mastery).filter((key) => inBook.has(key));
      const lv = m.map((key) => spellOf(key)?.level).sort();
      if (m.length === 2 && lv[0] === 1 && lv[1] === 2) out.spell_mastery = m;
    }
    if (R.signature_spells) {
      const sig = asList(c.signature_spells).filter((key) => inBook.has(key) && spellOf(key)?.level === 3);
      if (sig.length === 2) {
        out.signature_spells = sig;
        spells = spells.filter((key) => !sig.includes(key)); // sempre preparati: non vanno tra quelli preparati
      }
    }
    keep('spells', spells);
  }
  if (R.circle_terrain && c.circle_terrain) out.circle_terrain = c.circle_terrain;
  if (R.companion && c.companion && companionOptions(R.companion).some(([key]) => key === c.companion)) out.companion = c.companion;
  // privilegi
  if (R.fighting_style) {
    const styles = [c.fighting_style, ...asList(c.fighting_styles)].filter((s, i, a) => s && a.indexOf(s) === i && RULES.equipment.fighting_styles?.[s]);
    if (styles[0]) out.fighting_style = styles[0];
    if (styles.length > 1) out.fighting_styles = styles.slice(1, R.fighting_style.count || 9);
  }
  if (R.maneuvers) keep('maneuvers', asList(c.maneuvers).filter((m) => RULES.maneuvers?.[m]));
  if (R.class_options) {
    const co = {};
    for (const [key, list] of Object.entries(c.class_options || {})) {
      if (!R.class_options[key] || !asList(list).length) continue;
      // un'opzione con sotto-scelte (Patto del Tomo: 3 trucchetti) va come {key, cantrips, spells}
      co[key] = asList(list).map(optKey).map((ik) => {
        const it = optionRule(key, ik, c);
        const sub = c.option_picks?.[`${key}|${ik}`] || {};
        const entry = { key: ik };
        if (it?.cantrip_choice && asList(sub.cantrips).length) entry.cantrips = asList(sub.cantrips);
        if (it?.spell_choice && asList(sub.spells).length) entry.spells = asList(sub.spells);
        return Object.keys(entry).length > 1 ? entry : ik;
      });
    }
    keep('class_options', co);
  }
  // competenze
  // mai più di quanti ne concedono le regole (se cambiano razza, classe o livello quelli in più restano fuori)
  keep('languages_extra', langPicks(c, R).slice(0, R.languages?.count || 0));
  keep('tools', toolPicks(c).slice(0, R.tools?.count || 0).filter(Boolean));
  if (bg && Array.isArray(c.background_tools)) { // elenco completo: fissi + scelti (le caselle vuote restano fuori)
    const slots = bgToolSlots(c);
    const chosen = slots.filter((t) => t.open).map((t) => t.value.trim()).filter(Boolean);
    if (chosen.length) out.background_tools = [...slots.filter((t) => !t.open).map((t) => t.label), ...chosen];
  }
  // equipaggiamento
  if (c.armor && RULES.equipment.armor?.[c.armor]) out.armor = c.armor;
  if (c.shield) out.shield = typeof c.shield === 'string' ? c.shield : true;
  keep('weapons', asList(c.weapons));
  keep('equipment', asList(c.equipment).filter((e) => (typeof e === 'string' ? e.trim() : e && e.pack)));
  const money = {};
  for (const [key] of MONEY) { const v = Number(c.money?.[key] || 0); if (v) money[key] = v; }
  keep('money', money);
  out.include_background_equipment = c.include_background_equipment !== false;
  // storia
  const pers = {}; for (const [kk, v] of Object.entries(c.personality || {})) if (String(v || '').trim()) pers[kk] = v;
  keep('personality', pers);
  const app = {}; for (const [kk, v] of Object.entries(c.appearance || {})) if (String(v || '').trim()) app[kk] = v;
  keep('appearance', app);
  keep('allies', (c.allies || '').trim());
  keep('treasure', (c.treasure || '').trim());
  keep('backstory', (c.backstory || '').trim());
  keep('portrait', c.portrait);
  return out;
}

/* Riempie le scelte obbligatorie mancanti, solo per l'anteprima provvisoria. */
function padChar(src) {
  const c = clone(src);
  const R = req();
  const padded = { skills: new Set() };
  if (!c.name) c.name = 'Eroe';
  const race = raceOf(c);
  if (race) {
    const subs = Object.keys(race.subraces || {});
    if (subs.length && !c.subrace) c.subrace = subs[0];
    if (race.ancestry && !c.draconic_ancestry) c.draconic_ancestry = Object.keys(race.ancestry)[0];
  }
  if (!c.background) c.background = Object.keys(RULES.backgrounds)[0];
  const ab = c.abilities;
  if (ab.method === 'standard_array') {
    const left = [...(R.standard_array || [15, 14, 13, 12, 10, 8])];
    for (const a of ABIL) if (ab.base[a] != null) left.splice(left.indexOf(ab.base[a]), 1);
    for (const a of ABIL) if (ab.base[a] == null) ab.base[a] = left.shift() ?? 10;
  } else {
    for (const a of ABIL) if (ab.base[a] == null) ab.base[a] = ab.method === 'point_buy' ? 8 : 10;
  }
  if (ab.method === 'point_buy') { // punti spesi male: per l'anteprima conta solo il numero
    const pb = R.point_buy || RULES.skills.point_buy;
    const costs = ABIL.map((a) => pb.costs[String(ab.base[a])]);
    if (costs.some((x) => x == null) || sum(costs) > pb.budget) ab.method = 'manual';
  }
  if (R.racial_choice) {
    const picks = asList(ab.racial_choice);
    for (const a of ABIL) if (picks.length < R.racial_choice.count && !picks.includes(a) && !(R.racial_choice.exclude || []).includes(a)) picks.push(a);
    ab.racial_choice = picks;
  }
  const taken = new Set(Object.keys(proficientSet(c, R)));
  const allSkills = Object.keys(RULES.skills.skills);
  if (R.racial_skills?.count) {
    const picks = asList(c.racial_skills);
    for (const s of allSkills) if (picks.length < R.racial_skills.count && !taken.has(s)) { picks.push(s); taken.add(s); padded.skills.add(s); }
    c.racial_skills = picks;
  }
  if (R.class_skills?.count) {
    const picks = asList(c.skills);
    for (const s of R.class_skills.from || allSkills) if (picks.length < R.class_skills.count && !taken.has(s) && !picks.includes(s)) { picks.push(s); taken.add(s); padded.skills.add(s); }
    c.skills = picks;
  }
  if (R.racial_cantrip && !asList(c.racial_cantrips).length) {
    const first = Object.entries(RULES.spells.spells).find(([, sp]) => sp.level === 0 && (sp.lists || []).includes(R.racial_cantrip.list));
    if (first) c.racial_cantrips = [first[0]];
  }
  const k = clsOf(c);
  if (k && (c.level || 1) >= (k.subclass_level || 99) && !c.subclass) c.subclass = Object.keys(k.subclasses || {})[0];
  const sc = k && c.subclass ? k.subclasses[c.subclass] : null;
  if (sc && sc.circle_spells && !c.circle_terrain) c.circle_terrain = Object.keys(sc.circle_spells)[0];
  if (c.feats) {
    c.feats = c.feats.map((f) => {
      const pick = typeof f === 'string' ? { key: f } : { ...f };
      const feat = RULES.feats?.[pick.key];
      if (feat?.ability_choice && !pick.ability) pick.ability = (feat.ability_choice.from || ABIL)[0];
      if (feat?.save_proficiency_choice && !pick.save) pick.save = pick.ability;
      return pick;
    });
  }
  return { char: c, padded };
}

/* ------------------------------------------------------------------ anteprima */
function sheet() {
  if (PREVIEW && PREVIEW.ok && PREVIEW.sheet) return { s: PREVIEW.sheet, provisional: false };
  if (PREVIEW_PAD && PREVIEW_PAD.ok && PREVIEW_PAD.sheet) return { s: PREVIEW_PAD.sheet, provisional: true, padded: PREVIEW_PAD.padded };
  return { s: null, provisional: true };
}
function sheetScore(s, a) {
  const ab = s?.abilities || {};
  if (ab.scores && ab.scores[a] != null) return { total: ab.scores[a], mod: ab.mods?.[a] ?? modOf(ab.scores[a]) };
  if (ab[a] && typeof ab[a] === 'object') return { total: ab[a].score ?? ab[a].total, mod: ab[a].mod ?? modOf(ab[a].score ?? ab[a].total) };
  return null;
}
function placeholders() {
  const c = S.char;
  const vals = { livello: c.level || 1, o: isF() ? 'a' : 'o', un_amico: isF() ? "un'amica" : 'un amico', amici: isF() ? 'amiche' : 'amici' };
  for (const [col, v] of Object.entries(classTable(c))) vals[`t_${col}`] = v === 99 ? 'illimitati' : v;
  // stime locali, sostituite dai numeri del motore appena arriva l'anteprima
  const est = {};
  try {
    const sc = computeScores(baseChar());
    const pbc = RULES.skills.proficiency_bonus[(c.level || 1) - 1];
    est.cd_manovre = 8 + pbc + Math.max(sc.str.mod, sc.dex.mod);
    const caster = activeSubclass(c)?.spellcasting || clsOf(c)?.spellcasting;
    const ab = caster?.ability || raceTraits(c).find((t) => t.cantrip_choice)?.cantrip_choice.ability || raceTraits(c).find((t) => t.innate_ability)?.innate_ability;
    if (ab && sc[ab]) Object.assign(est, { cd: 8 + pbc + sc[ab].mod, att: fmtMod(pbc + sc[ab].mod), mod: fmtMod(sc[ab].mod) });
  } catch (e) { /* personaggio incompleto */ }
  const { s } = sheet();
  if (s) {
    Object.assign(vals, s.placeholders || {});
    const sp = s.spellcasting;
    if (sp && vals.cd == null && sp.save_dc != null) vals.cd = sp.save_dc;
    if (sp && vals.att == null && sp.attack_bonus != null) vals.att = fmtMod(sp.attack_bonus);
    if (sp && vals.mod == null && sp.mod != null) vals.mod = fmtMod(sp.mod);
    if (sp && vals.mod == null && sp.ability && s.abilities?.mods?.[sp.ability] != null) vals.mod = fmtMod(s.abilities.mods[sp.ability]);
    const pbv = s.proficiency_bonus;
    const mm = s.abilities?.mods;
    if (pbv != null && mm && vals.cd_manovre == null) vals.cd_manovre = 8 + pbv + Math.max(mm.str ?? 0, mm.dex ?? 0);
    if (s.breath && vals.soffio_cd == null) Object.assign(vals, { soffio_cd: s.breath.dc, soffio_danni: s.breath.dice, soffio_tipo: s.breath.type, soffio_area: s.breath.area, soffio_ts: s.breath.save_name });
  }
  for (const [k, v] of Object.entries(est)) if (vals[k] == null) vals[k] = v;
  return vals;
}
let PH = null;
function kidFmt(text, extra = null) {
  if (!text) return '';
  if (!PH) PH = placeholders();
  return String(text).replace(/\{(\w+)\}/g, (m, k) => {
    const v = extra && extra[k] != null ? extra[k] : PH[k];
    return v != null && v !== '' ? String(v) : '…';
  });
}
/* {dadi} nei testi dei trucchetti: i dadi crescono al 5°, 11° e 17° livello (come engine._scale_cantrip). */
function spellDice(sp) {
  const d = String(sp?.damage || '');
  if (!d) return null;
  if (sp.level !== 0 || sp.scaling === 'beams') return d;
  const m = d.match(/^(\d+)d(\d+)/);
  if (!m) return d;
  const lvl = S.char.level || 1;
  return `${Number(m[1]) * (1 + (lvl >= 5) + (lvl >= 11) + (lvl >= 17))}d${m[2]}`;
}
const spellFmt = (sp, text) => kidFmt(text, { dadi: spellDice(sp) });

let refreshTimer = null;
let refreshSeq = 0;
function scheduleRefresh(delay = 280) {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(refresh, delay);
}
async function refresh() {
  const seq = ++refreshSeq;
  const c = baseChar();
  const key = reqKeyOf(c);
  const compiled = compileChar();
  try {
    if (compiled.race || compiled.class) {
      const r = await postJSON('/api/requirements', { character: { ...compiled, name: compiled.name || 'Eroe' } });
      if (seq !== refreshSeq) return;
      // {requirements: {}, error} = errore del programma: si usa il calcolo locale
      const data = r && !r.error ? (r.requirements || r) : null;
      SERVER_REQ = data && !data.error && Object.keys(data).length ? { key, data } : null;
    } else SERVER_REQ = null;
  } catch (e) {
    if (e.offline) { setOffline(true); return; }
    SERVER_REQ = null;
  }
  setOffline(false);
  const full = compileChar(); // ricompilato con i requisiti del server
  try {
    let p = null;
    if (full.race && full.class && full.background) {
      p = await postJSON('/api/preview', { character: { ...full, name: full.name || 'Eroe' } });
      if (seq !== refreshSeq) return;
    }
    PREVIEW = p ? { ...p, key: JSON.stringify(full) } : null;
    PREVIEW_PAD = null;
    if ((!p || !p.ok) && full.race && full.class) {
      const { char: padded, padded: info } = padChar(full);
      const pp = await postJSON('/api/preview', { character: padded });
      if (seq !== refreshSeq) return;
      PREVIEW_PAD = pp && pp.ok ? { ...pp, padded: info } : null;
    }
  } catch (e) {
    if (e.offline) { setOffline(true); return; }
    PREVIEW = { ok: false, error: e.message, warnings: [], key: JSON.stringify(full) };
  }
  renderAll(false, { soft: true });
}
function setOffline(v) {
  if (OFFLINE === v) return;
  OFFLINE = v;
  const b = $('#offline-banner');
  if (b) b.hidden = !v;
  if (!v && S.built && S.built.offline) { S.built = null; saveState(); } // il programma è tornato: via il vecchio avviso
  if (RULES) renderAside();
}

/* ------------------------------------------------------------------ cosa manca */
function missingFor(id) {
  const c = baseChar();
  const R = req();
  const m = [];
  const need = (n, one, many, anchor) => { if (n > 0) m.push({ text: `Ti ${n === 1 ? 'manca' : 'mancano'} ${n} ${plural(n, one, many)}`, anchor }); };
  // scelti troppi (es. dopo aver abbassato il livello o cambiato razza): il PDF li avrebbe in più o li perderebbe
  const fit = (have, want, one, many, anchor) => {
    if (have < want) need(want - have, one, many, anchor);
    else if (have > want) m.push({ text: `${cap(many)}: ${have - want === 1 ? 'ce n\'è 1' : `ce ne sono ${have - want}`} di troppo, togline ${have - want}`, anchor });
  };
  if (id === 'start') {
    if (!(c.name || '').trim()) m.push({ text: 'Scrivi il nome del personaggio', anchor: 'f-name' });
    if (!c.gender) m.push({ text: 'Scegli femminile o maschile', anchor: 'f-gender' });
  } else if (id === 'race') {
    const race = raceOf(c);
    if (!race) m.push({ text: 'Scegli una razza', anchor: 'sec-races' });
    else {
      if (Object.keys(race.subraces || {}).length && !subOf(c)) m.push({ text: 'Scegli la sottorazza', anchor: 'sec-subrace' });
      if (race.ancestry && !c.draconic_ancestry) m.push({ text: 'Scegli il colore del drago', anchor: 'sec-ancestry' });
      if (R.racial_choice) fit(asList(c.abilities.racial_choice).length, R.racial_choice.count, 'caratteristica da aumentare', 'caratteristiche da aumentare', 'sec-racechoice');
      if (R.racial_skills) fit(asList(c.racial_skills).length, R.racial_skills.count, 'abilità della razza', 'abilità della razza', 'sec-raceskills');
      if (R.racial_cantrip) need(1 - Math.min(1, asList(c.racial_cantrips).length), 'trucchetto della razza', 'trucchetti della razza', 'sec-racecantrip');
      if (raceFeatChoice(c) && !S.raceFeat?.key) m.push({ text: 'Scegli il talento della razza', anchor: 'sec-racefeat' });
      if (raceFeatChoice(c) && S.raceFeat?.key) featMissing(S.raceFeat, 'Talento della razza', m, 'sec-racefeat');
    }
  } else if (id === 'class') {
    const k = clsOf(c);
    if (!k) m.push({ text: 'Scegli una classe', anchor: 'sec-classes' });
    else {
      if (R.subclass?.required && !subclassOf(c)) m.push({ text: `Scegli: ${R.subclass.label || 'la sottoclasse'}`, anchor: 'sec-subclass' });
      if (R.circle_terrain && !c.circle_terrain) m.push({ text: 'Scegli il terreno del circolo', anchor: 'sec-terrain' });
    }
  } else if (id === 'background') {
    if (!bgOf(c)) m.push({ text: 'Scegli un background', anchor: 'sec-backgrounds' });
    else {
      const dup = bgDuplicates(c);
      if (dup.length) m.push({ text: `${dup.map(skillName).join(' e ')} ${dup.length === 1 ? 'è già tua' : 'sono già tue'}: scegli un'altra abilità al suo posto`, anchor: 'sec-bgswap' });
      const open = bgToolSlots(c).filter((t) => t.open && !t.value);
      if (open.length) m.push({ text: `Specifica ${open.length === 1 ? 'lo strumento' : 'gli strumenti'} a scelta`, anchor: 'sec-bgtools' });
      const own = ownToolNames(c);
      for (const t of bgToolSlots(c).filter((x) => x.open && x.value && own.has(norm(x.value)))) {
        m.push({ text: `${t.value}: ce l'hai già, scegli un altro strumento del background`, anchor: 'sec-bgtools' });
      }
      for (const t of bgToolSlots(c).filter((x) => x.open && x.value)) {
        const why = toolCategoryProblem(t.value, t.category || toolCategoryOf(t.label));
        if (why) m.push({ text: why, anchor: 'sec-bgtools' });
      }
    }
  } else if (id === 'abilities') {
    const ab = c.abilities;
    if (ab.method === 'point_buy') {
      const pb = R.point_buy || RULES.skills.point_buy;
      const spent = sum(ABIL.map((a) => pb.costs[String(ab.base[a])] ?? 0));
      if (spent < pb.budget) m.push({ text: `Ti ${pb.budget - spent === 1 ? 'resta' : 'restano'} ${pb.budget - spent} ${plural(pb.budget - spent, 'punto', 'punti')} da spendere`, anchor: 'sec-method' });
      if (spent > pb.budget) m.push({ text: `Hai speso ${spent - pb.budget} ${plural(spent - pb.budget, 'punto', 'punti')} di troppo: abbassa qualche numero`, anchor: 'sec-method' });
      if (ABIL.some((a) => pb.costs[String(ab.base[a])] == null)) m.push({ text: 'Con i punti da spendere ogni numero va da 8 a 15', anchor: 'sec-method' });
    } else if (ABIL.some((a) => ab.base[a] == null || ab.base[a] === '')) {
      const n = ABIL.filter((a) => ab.base[a] == null || ab.base[a] === '').length;
      need(n, 'punteggio da assegnare', 'punteggi da assegnare', 'sec-method');
    }
    for (const L of R.asi_levels || []) {
      const s = S.slots[L];
      if (!s || (s.type === 'asi' && asList(s.asi).filter(Boolean).length < 2) || (s.type === 'feat' && !s.feat?.key)) m.push({ text: `Livello ${L}: scegli l'aumento o il talento`, anchor: `sec-asi-${L}` });
      else if (s.type === 'feat') featMissing(s.feat, `Livello ${L}`, m, `sec-asi-${L}`);
    }
  } else if (id === 'skills') {
    if (R.class_skills) {
      const taken = proficientSet({ ...c, skills: [] }, R);
      const valid = asList(c.skills).filter((s) => !taken[s]);
      fit(valid.length, R.class_skills.count, 'abilità di classe', 'abilità di classe', 'sec-classskills');
      const dup = asList(c.skills).filter((s) => taken[s]);
      if (dup.length) m.push({ text: `${dup.map(skillName).join(', ')}: ${dup.length === 1 ? 'l\'hai' : 'le hai'} già, scegline un'altra`, anchor: 'sec-classskills' });
    }
    if (R.extra_skills) fit(extraPicks(c, R).length, R.extra_skills.count, 'abilità extra', 'abilità extra', 'sec-extraskills');
    if (R.expertise) fit(expertisePicks(c, R).length, R.expertise.count, 'maestria', 'maestrie', 'sec-expertise');
    if (R.languages) fit(langPicks(c, R).length, R.languages.count, 'linguaggio', 'linguaggi', 'sec-languages');
    if (R.tools) {
      const filled = toolPicks(c).slice(0, R.tools.count).filter(Boolean).length;
      need(R.tools.count - filled, 'strumento', 'strumenti', 'sec-tools');
      // doppioni con gli strumenti di classe, razza o background (il programma lo segnala)
      const have = new Set([...ownToolNames(c), ...bgToolSlots(c).map((t) => norm(t.value)).filter(Boolean)]);
      toolPicks(c).slice(0, R.tools.count).forEach((v, i) => {
        const why = toolCategoryProblem(v, asList(R.tools.slots)[i]?.category);
        if (why) m.push({ text: why, anchor: 'sec-tools' });
      });
      const seen = new Set();
      for (const t of toolPicks(c).slice(0, R.tools.count).filter(Boolean)) {
        if (have.has(norm(t)) || seen.has(norm(t))) m.push({ text: `${t}: ce l'hai già, scegli un altro strumento`, anchor: 'sec-tools' });
        seen.add(norm(t));
      }
    }
  } else if (id === 'magic') {
    const racial = racialCantrips(c);
    const granted = grantedCantrips(R);
    if (R.cantrips) fit(asList(c.cantrips).filter((k) => !racial.includes(k) && !granted.includes(k)).length, R.cantrips.count, 'trucchetto', 'trucchetti', 'sec-spells');
    if (R.spellbook) {
      const max = R.spells?.max_level || 9;
      fit(asList(c.spellbook).filter((k) => (spellOf(k)?.level ?? 1) <= max).length, R.spellbook.count, 'incantesimo nel libro', 'incantesimi nel libro', 'sec-spells');
    }
    if (R.spells && R.spells.count) {
      const word = R.spells.mode === 'known' ? ['incantesimo conosciuto', 'incantesimi conosciuti'] : ['incantesimo preparato', 'incantesimi preparati'];
      fit(countedSpells(c, R).length, R.spells.count, word[0], word[1], 'sec-spells');
    }
    // magie fuori lista o fuori scuola: le regole ne permettono solo alcune (il programma le rifiuterebbe)
    const lim = spellLimits(c, R);
    if (R.cantrips && lim.offCantrips.length > lim.cantripMax) {
      const from = lim.extraC.map((e) => `${e.count} dalla lista del ${listName(e.list)}`).join(', ');
      m.push({ text: `Trucchetti: ${lim.offCantrips.length} vengono da un'altra lista, ${from ? `puoi prenderne solo ${from}` : `devono essere tutti della lista del ${listName(lim.main)}`}`, anchor: 'sec-spells' });
    }
    if (R.spells && lim.offList.length > lim.secrets) {
      m.push({ text: lim.secrets ? `Segreti Magici: puoi prendere solo ${lim.secrets} incantesimi di altre classi, ne hai ${lim.offList.length}` : `${lim.offList.map((k) => spellOf(k).name).join(', ')}: non ${lim.offList.length === 1 ? 'è' : 'sono'} della tua lista, ${lim.offList.length === 1 ? 'toglilo' : 'toglili'}`, anchor: 'sec-spells' });
    }
    if (R.spells && lim.allowed && lim.offSchool.length > lim.anySchool) {
      m.push({ text: `Incantesimi di un'altra scuola: ne puoi avere ${lim.anySchool}, ne hai ${lim.offSchool.length}`, anchor: 'sec-spells' });
    }
    for (const L of asList(R.spells?.arcanum_levels)) {
      if (!asList(c.spells).some((k) => spellOf(k)?.level === L)) m.push({ text: `Arcanum Mistico: scegli un incantesimo di ${ord(L)} livello`, anchor: 'sec-spells' });
    }
    const book = new Set(asList(c.spellbook));
    if (R.spell_mastery) {
      const lv = asList(c.spell_mastery).filter((k) => book.has(k)).map((k) => spellOf(k)?.level);
      if (!(lv.includes(1) && lv.includes(2))) m.push({ text: 'Maestria negli Incantesimi: scegli un incantesimo di 1° e uno di 2° livello', anchor: 'sec-mastery' });
    }
    if (R.signature_spells) {
      need(2 - asList(c.signature_spells).filter((k) => book.has(k) && spellOf(k)?.level === 3).length, 'incantesimo personale', 'incantesimi personali', 'sec-signature');
    }
  } else if (id === 'features') {
    if (R.fighting_style) fit([c.fighting_style, ...asList(c.fighting_styles)].filter(Boolean).length, R.fighting_style.count, 'stile di combattimento', 'stili di combattimento', 'sec-style');
    if (R.maneuvers) fit(asList(c.maneuvers).length, R.maneuvers.count, 'manovra', 'manovre', 'sec-maneuvers');
    for (const [key, opt] of Object.entries(R.class_options || {})) {
      const n = (opt.count || 0) - asList(c.class_options?.[key]).length;
      if (n > 0) m.push({ text: `${opt.label || key}: ${n === 1 ? 'manca' : 'mancano'} ${n} ${plural(n, 'scelta', 'scelte')}`, anchor: `sec-opt-${key}` });
      if (n < 0) m.push({ text: `${opt.label || key}: ${n === -1 ? 'c\'è 1 scelta' : `ci sono ${-n} scelte`} di troppo, togline ${-n}`, anchor: `sec-opt-${key}` });
      for (const ik of asList(c.class_options?.[key]).map(optKey)) {
        const it = optionRule(key, ik, c);
        if (!it) continue;
        const why = optionBlocked(it, c);
        if (why) m.push({ text: `${nm(it, ik)}: ${why}`, anchor: `sec-opt-${key}` });
        const sub = c.option_picks?.[`${key}|${ik}`] || {};
        for (const [kind, p] of Object.entries(optionSubPools(it, c))) {
          const left = p.count - asList(kind === 'cantrip' ? sub.cantrips : sub.spells).length;
          if (left > 0) {
            const what = kind === 'cantrip' ? plural(left, 'trucchetto', 'trucchetti') : plural(left, p.ritual ? 'rituale' : 'incantesimo', p.ritual ? 'rituali' : 'incantesimi');
            m.push({ text: `${nm(it, ik)}: ${left === 1 ? 'manca' : 'mancano'} ${left} ${what}`, anchor: `sec-opt-${key}` });
          }
        }
      }
    }
    if (R.companion && !c.companion) m.push({ text: 'Scegli il compagno animale', anchor: 'sec-companion' });
  } else if (id === 'story') {
    if (!c.alignment) m.push({ text: 'Scegli l\'allineamento', anchor: 'sec-alignment' });
  }
  // il programma ha rifiutato la scheda per qualcosa di questo passo che qui sopra non risulta (es. un talento
  // senza il prerequisito): lo si dice qui, non solo nel riepilogo, così il passo non sembra "tutto scelto"
  const p = PREVIEW;
  if (!m.length && p && !p.ok && p.error && p.key && p.key === CUR_KEY && id !== 'summary' && stepForError(p.error) === stepIndex(id)) {
    m.push({ text: humanize(p.error), anchor: anchorForError(id, p.error), engine: true });
  }
  return m;
}
/* Il riquadro del passo a cui porta un errore del programma (il talento sbagliato, se c'è). */
function anchorForError(id, msg) {
  const t = norm(msg);
  if (id === 'race' && /talento/.test(t)) return 'sec-racefeat';
  if (id === 'abilities') {
    const L = Object.keys(S.slots).find((lv) => S.slots[lv]?.type === 'feat' && RULES.feats?.[S.slots[lv].feat?.key] && t.includes(norm(RULES.feats[S.slots[lv].feat.key].name)));
    return L ? `sec-asi-${L}` : 'sec-method';
  }
  return { race: 'sec-races', class: 'sec-classes', background: 'sec-backgrounds', magic: 'sec-spells' }[id] || '';
}
/* Incantesimi che contano per il limite (l'Arcanum Mistico del warlock è a parte). */
function countedSpells(c, R) {
  const max = R.spells?.max_level || 9;
  const sig = R.signature_spells ? asList(c.signature_spells) : []; // Incantesimi Personali: sempre preparati, fuori dal conto
  const always = alwaysPreparedKeys(R); // dominio, giuramento, circolo: gratis, fuori dal conto
  const book = R.spells?.mode === 'spellbook' ? new Set(asList(c.spellbook)) : null;
  return asList(c.spells).filter((k, i, a) => (spellOf(k)?.level ?? 1) <= max && !sig.includes(k) && !always.has(k)
    && (!book || book.has(k)) && a.indexOf(k) === i);
}
/* Magie fuori dalla lista della classe o dalla sua scuola, con quante ne permettono le regole:
 * Segreti Magici del bardo, Accolito della Natura (1 trucchetto da druido), Cavaliere Mistico e Mistificatore Arcano. */
function cantripExtraLists(c = S.char) {
  return levelFeatures(c).filter((f) => f.cantrip_choice && typeof f.cantrip_choice === 'object' && f.cantrip_choice.list)
    .map((f) => ({ list: f.cantrip_choice.list, count: Number(f.cantrip_choice.count || 1), source: nm(f) }));
}
function spellLimits(c = S.char, R = req()) {
  const main = R.spells?.list || R.cantrips?.list || asList(R.cantrips?.lists)[0] || c.class;
  const racial = racialCantrips(c);
  const extraC = cantripExtraLists(c);
  const offCantrips = asList(c.cantrips).filter((k) => !racial.includes(k) && spellOf(k) && !(spellOf(k).lists || []).includes(main));
  const expanded = new Set(asList(R.spells?.expanded));
  const counted = R.spells ? countedSpells(c, R) : [];
  const offList = counted.filter((k) => spellOf(k) && !(spellOf(k).lists || []).includes(main) && !expanded.has(k));
  const sch = R.spells?.schools;
  const schoolKey = (s) => norm(SCHOOL_IT[s] || s);
  const allowed = sch && asList(sch.allowed).length ? asList(sch.allowed).map(schoolKey) : null;
  const arc = new Set(asList(R.spells?.arcanum_levels));
  const offSchool = allowed ? counted.filter((k) => spellOf(k) && !arc.has(spellOf(k).level) && !allowed.includes(schoolKey(spellOf(k).school))) : [];
  return {
    main, extraC, offCantrips, cantripMax: sum(extraC.map((e) => e.count)),
    offList, secrets: Number(R.spells?.magical_secrets || 0),
    offSchool, anySchool: Number(sch?.any_school_count || 0), allowed,
  };
}
const listName = (l) => RULES.classes[l]?.name || l; // "la lista del Druido": la lista è sempre al maschile
function featMissing(f, label, m, anchor) {
  const feat = RULES.feats?.[f.key];
  if (!feat) return;
  if (feat.ability_choice && !f.ability) m.push({ text: `${label}: scegli la caratteristica del talento`, anchor });
  const wp = feat.weapon_proficiencies;
  if (wp && !Array.isArray(wp) && wp.count && asList(f.weapons).length < wp.count) m.push({ text: `${label}: scegli ${wp.count} armi`, anchor });
  const cc = feat.cantrip_choice;
  const scc = feat.spell_choice;
  if ((cc?.lists || scc?.lists || (scc && cc)) && !f.list) m.push({ text: `${label}: scegli la lista di magie del talento`, anchor });
  else {
    if (cc && asList(f.cantrips).length < (cc.count || 1)) m.push({ text: `${label}: scegli ${cc.count || 1} ${plural(cc.count || 1, 'trucchetto', 'trucchetti')} del talento`, anchor });
    if (scc && asList(f.spells).length < (scc.count || 1)) m.push({ text: `${label}: scegli ${scc.count || 1} ${plural(scc.count || 1, 'incantesimo', 'incantesimi')} del talento`, anchor });
  }
  if (feat.damage_type_choice && !f.damage_type) m.push({ text: `${label}: scegli il tipo di danno`, anchor });
}
function bgDuplicates(c = S.char) {
  const R = req();
  const others = new Set();
  for (const t of raceTraits(c)) (t.skills || []).forEach((s) => others.add(s));
  asList(c.racial_skills).forEach((s) => others.add(s));
  asList(c.skills).filter((s) => (R.class_skills?.from || []).includes(s)).forEach((s) => others.add(s));
  optionSkills(c, R).forEach(([s]) => others.add(s));
  return effectiveBgSkills(c).filter((s) => others.has(s));
}
/* Strumenti del background, come engine.resolve_tools: prima i fissi, poi una casella per ogni scelta
 * ('tools' con "a scelta" e 'tool_choices'). Sul personaggio 'background_tools' è l'elenco completo. */
const NUMBER_WORDS = { un: 1, uno: 1, una: 1, due: 2, tre: 3, quattro: 4 };
function placeholderCount(text) {
  const s = String(text || '').toLowerCase();
  if (!s.includes('a scelta')) return 0;
  return NUMBER_WORDS[s.split(/\s+/)[0]] || 1;
}
/* Strumenti già dati da classe, privilegi e razza (nomi normalizzati), per trovare i doppioni del background. */
function ownToolNames(c = S.char) {
  const table = RULES?.equipment?.tools || {};
  const tn = (t) => norm(table[t]?.name || (t === 'thieves_tools' ? 'Arnesi da scasso' : t));
  const out = new Set();
  for (const t of clsOf(c)?.tools || []) if (!placeholderCount(t)) out.add(tn(t));
  for (const f of levelFeatures(c)) for (const t of f.bonus_proficiencies?.tools || []) out.add(tn(t));
  for (const tr of raceTraits(c)) for (const t of tr.tool_proficiencies || []) out.add(tn(t));
  return out;
}
function bgToolSlotDefs(bg, c = S.char) {
  const own = ownToolNames(c);
  const defs = [];
  for (const t of bg?.tools || []) {
    if (placeholderCount(t)) continue;
    // un doppione (es. Arnesi da scasso per un ladro criminale): le regole fanno sceglierne un altro al suo posto
    defs.push(own.has(norm(t)) ? { label: t, open: true, dup: true, category: null } : { label: t, open: false, category: null });
  }
  for (const t of bg?.tools || []) for (let i = 0; i < placeholderCount(t); i++) defs.push({ label: t, open: true, category: toolCategoryOf(t) });
  for (const ch of asList(bg?.tool_choices)) {
    for (let i = 0; i < Number(ch?.count || 1); i++) defs.push({ label: ch?.label || 'Strumento a scelta', open: true, category: ch?.category || null });
  }
  return defs;
}
/* Un elenco salvato (anche da file scritti a mano) rimesso nelle caselle: i fissi per nome, gli altri in ordine. */
function bgToolsToSlots(bg, list, c = S.char) {
  const defs = bgToolSlotDefs(bg, c);
  const rest = asList(list).map((v) => String(v ?? '')).filter((v) => !defs.some((d) => !d.open && norm(d.label) === norm(v)));
  return defs.map((d) => (d.open ? (rest.shift() ?? '') : d.label));
}
/* Nomi degli strumenti dalle regole (equipment.tools), filtrati per categoria: artisan, musical, gaming... */
function toolNames(category = null) {
  const table = RULES?.equipment?.tools;
  if (!table || typeof table !== 'object' || !Object.keys(table).length) return TOOL_SUGGESTIONS;
  const cats = category ? String(category).split('+') : null; // "artisan+musical": strumenti da artigiano o musicali
  const names = Object.values(table).filter((t) => !cats || (t && cats.includes(t.category))).map((t) => (typeof t === 'string' ? t : t?.name)).filter(Boolean);
  return names.length ? names : TOOL_SUGGESTIONS;
}
/* Uno strumento conosciuto ma del gruppo sbagliato (es. Scorte da alchimista dove serve uno strumento musicale).
 * I nomi scritti a mano che non sono nell'elenco vanno bene: il master sa cosa sono. */
const TOOL_CAT_IT = { artisan: 'uno strumento da artigiano', musical: 'uno strumento musicale', gaming: 'un gioco', other: 'uno strumento' };
function toolCategoryProblem(value, category) {
  if (!value || !category) return '';
  const tool = Object.values(RULES?.equipment?.tools || {}).find((t) => t && t.name && norm(t.name) === norm(value));
  const cats = String(category).split('+');
  if (!tool || !tool.category || cats.includes(tool.category)) return '';
  return `${value}: qui serve ${cats.map((x) => TOOL_CAT_IT[x] || x).join(' o ')}`;
}
/* Gruppo di strumenti dedotto dal testo quando le regole non lo dicono (come choices._tool_category). */
function toolCategoryOf(text) {
  const s = String(text || '').toLowerCase();
  return [['artisan', /artigian/], ['musical', /musical/], ['gaming', /gioc/]].filter(([, re]) => re.test(s)).map(([c]) => c).join('+') || null;
}
function toolSlotLabels(slots) { // "Tre strumenti musicali a scelta" ripetuto tre volte -> "... (1 di 3)"
  return slots.map((s, i) => {
    const same = slots.filter((x) => x.label === s.label);
    return same.length > 1 ? `${cap(s.label)} (${slots.slice(0, i + 1).filter((x) => x.label === s.label).length} di ${same.length})` : cap(s.label);
  });
}
function bgToolSlots(c = S.char) {
  const bg = bgOf(c);
  if (!bg) return [];
  const over = Array.isArray(c.background_tools) ? c.background_tools : null;
  return bgToolSlotDefs(bg, c).map((d, i) => {
    const value = d.open ? String((over && over[i]) ?? '') : d.label;
    return { ...d, value };
  });
}

/* ------------------------------------------------------------------ passi */
const STEPS = [
  { id: 'start', title: 'Inizio', lead: 'Dai un nome al tuo eroe e scrivi chi lo giocherà. Se vuoi, aggiungi anche un ritratto.' },
  { id: 'race', title: 'Razza', lead: 'Da quale popolo viene il tuo eroe? La razza cambia l\'aspetto, i sensi e qualche dono naturale.' },
  { id: 'class', title: 'Classe', lead: 'La classe è il mestiere dell\'avventuriero: come combatte, che magie usa, in cosa è bravo.' },
  { id: 'background', title: 'Background', lead: 'Che vita faceva prima di partire all\'avventura? Ogni background regala abilità, strumenti e un privilegio.' },
  { id: 'abilities', title: 'Caratteristiche', lead: 'Sei numeri dicono quanto il tuo eroe è forte, agile, resistente, sveglio, attento e simpatico. Più alto è, meglio è.' },
  { id: 'skills', title: 'Abilità e competenze', short: 'Abilità', lead: 'In cosa è allenato il tuo eroe? Il numero accanto a ogni abilità è quello che aggiungi al d20 quando la usi.' },
  { id: 'magic', title: 'Magie', lead: 'I trucchetti si usano quando vuoi; gli incantesimi consumano uno slot, che torna dopo un riposo lungo.', applicable: () => !!S.char.class && isCaster() },
  { id: 'features', title: 'Privilegi e opzioni', short: 'Privilegi', lead: 'Le mosse speciali della classe e quello che il tuo eroe impara salendo di livello.' },
  { id: 'equipment', title: 'Equipaggiamento', lead: 'Armatura, armi e zaino. La Classe Armatura (CA) dice quanto è difficile colpirti.' },
  { id: 'story', title: 'Personalità e storia', short: 'Storia', lead: 'Carattere, aspetto e passato: le cose che rendono il tuo eroe unico.' },
  { id: 'summary', title: 'Riepilogo e PDF', short: 'Scheda', lead: 'Controlla il tuo eroe e crea la scheda in PDF, pronta da stampare.' },
];
const stepIndex = (id) => STEPS.findIndex((s) => s.id === id);
const applicable = (i) => !STEPS[i].applicable || STEPS[i].applicable();
const prefersReducedMotion = () => !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

function goStep(i) {
  if (i < 0 || i >= STEPS.length) return;
  S.step = i;
  if (!S.visited.includes(i)) S.visited.push(i);
  S.ui.heroOpen = false;
  saveState();
  renderAll(true);
  if (!SERVER_REQ || SERVER_REQ.key !== reqKeyOf(baseChar())) scheduleRefresh(0);
  window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  const t = $('#step-title');
  if (t) t.focus({ preventScroll: true });
}
function moveStep(dir) {
  let i = S.step + dir;
  while (i >= 0 && i < STEPS.length && !applicable(i)) i += dir;
  if (i >= 0 && i < STEPS.length) goStep(i);
}

/* ------------------------------------------------------------------ mattoncini HTML */
function head(i, extra = '') {
  const st = STEPS[i];
  return `<header class="step-head"><p class="eyebrow">Passo ${i + 1} di ${STEPS.length}</p>
    <h2 id="step-title" tabindex="-1">${esc(st.title)}</h2><p class="lead">${esc(st.lead)}</p>${extra}</header>`;
}
function counter(n, max) {
  if (max == null) return `<span class="counter">${n} ${plural(n, 'scelta', 'scelte')}</span>`;
  const cls = n === max ? 'ok' : n > max ? 'over' : '';
  return `<span class="counter ${cls}">scelti <b>${n}</b> su ${max}</span>`;
}
function block(id, title, body, { hint = '', count = '', cls = '' } = {}) {
  return `<section class="block ${cls}" id="${id}" tabindex="-1">
    <div class="block-head"><h3>${title}</h3>${count}</div>${hint ? `<p class="hint">${hint}</p>` : ''}${body}</section>`;
}
function card({ act, value, on, em = '', title, meta = '', chips = [], body = '', extra = '', k, disabled = false, cls = '', label = '' }) {
  return `<button type="button" class="card ${cls}" data-act="${act}" data-value="${esc(value)}" data-k="${esc(k || `${act}-${value}`)}" aria-pressed="${on ? 'true' : 'false'}" ${disabled ? 'disabled' : ''} ${label ? `aria-label="${esc(label)}"` : ''}>
    <span class="card-check" aria-hidden="true">${emblem('check', 'i')}</span>
    ${em ? `<span class="card-emblem">${em}</span>` : ''}
    <span class="card-title">${esc(title)}</span>
    ${meta ? `<span class="card-meta">${esc(meta)}</span>` : ''}
    ${chips.length ? `<span class="card-chips">${chips.map((x) => `<span class="tag">${esc(x)}</span>`).join('')}</span>` : ''}
    ${body ? `<span class="card-body">${esc(body)}</span>` : ''}${extra}</button>`;
}
function chip({ act, value, on, label, sub = '', disabled = false, title = '', k, cls = '' }) {
  return `<button type="button" class="chip ${cls}" data-act="${act}" data-value="${esc(value)}" data-k="${esc(k || `${act}-${value}`)}" aria-pressed="${on ? 'true' : 'false'}" ${disabled ? 'disabled' : ''} ${title ? `title="${esc(title)}"` : ''}><span class="chip-dot" aria-hidden="true"></span><span class="chip-label">${esc(label)}</span>${sub !== '' ? `<span class="chip-sub">${esc(sub)}</span>` : ''}</button>`;
}
function field(label, bind, { type = 'text', placeholder = '', hint = '', id = '', area = false, rows = 3, value, attrs = '' } = {}) {
  const v = value !== undefined ? value : getPath(S.char, bind);
  const fid = id || `f-${bind.replace(/\W/g, '-')}`;
  const control = area
    ? `<textarea id="${fid}" data-bind="${bind}" rows="${rows}" placeholder="${esc(placeholder)}" ${attrs}>${esc(v ?? '')}</textarea>`
    : `<input id="${fid}" type="${type}" data-bind="${bind}" value="${esc(v ?? '')}" placeholder="${esc(placeholder)}" ${type === 'number' ? 'data-num inputmode="numeric"' : ''} autocomplete="off" ${attrs}>`;
  return `<div class="field"><label for="${fid}">${label}</label>${control}${hint ? `<p class="hint small">${hint}</p>` : ''}</div>`;
}
function getPath(o, path) { return path.split('.').reduce((a, k) => (a == null ? a : a[k]), o); }
function setPath(o, path, v) {
  const ks = path.split('.');
  let cur = o;
  for (let i = 0; i < ks.length - 1; i++) { if (cur[ks[i]] == null || typeof cur[ks[i]] !== 'object') cur[ks[i]] = {}; cur = cur[ks[i]]; }
  cur[ks[ks.length - 1]] = v;
}
const textOf = (f) => kidFmt(f.kid || f.short || f.text);
function bonusChips(bonus) {
  const e = Object.entries(bonus || {});
  if (e.length === 6 && e.every(([, v]) => v === e[0][1])) return [`+${e[0][1]} a tutte`];
  return e.map(([a, v]) => `${ABBR[a]} ${v >= 0 ? '+' : ''}${v}`);
}
function rangeText(r) {
  if (r == null || r === '') return '';
  if (typeof r === 'number') return `${String(r).replace('.', ',')} m`;
  return String(r);
}

/* ------------------------------------------------------------------ passo 1: inizio */
function renderStart() {
  const c = S.char;
  let h = head(0);
  const genderBtns = [['f', 'Femminile', 'Elfa, Druida, Maga…'], ['m', 'Maschile', 'Elfo, Druido, Mago…']].map(([v, l, sub]) =>
    `<button type="button" class="seg" data-act="gender" data-value="${v}" data-k="gender-${v}" aria-pressed="${c.gender === v}"><span>${l}</span><small>${sub}</small></button>`).join('');
  const thumb = S.thumb || (c.portrait ? `/portraits/${encodeURI(c.portrait)}` : '');
  const hasName = !!(c.name || '').trim();
  h += `<div class="start-grid">
    <section class="block" id="sec-who" tabindex="-1">
      <div class="block-head"><h3>Chi è il tuo eroe?</h3></div>
      ${field('Nome del personaggio', 'name', { placeholder: 'Es. Reyla', id: 'f-name', attrs: 'maxlength="40"' })}
      ${field('Chi lo gioca', 'player', { placeholder: 'Es. Arianna', attrs: 'maxlength="40"' })}
      <div class="field" id="f-gender" tabindex="-1"><span class="label">Femminile o maschile?</span><div class="segs">${genderBtns}</div>
        <p class="hint small">Serve per scrivere i nomi giusti sulla scheda.</p></div>
      <div class="field">
        <button type="button" class="switch" role="switch" aria-checked="${!!c.simple}" data-act="simple" data-k="simple">
          <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
          <span class="switch-text"><b>Versione semplice per bambini</b><small>Testi facili sulla scheda e una guida con una carta per ogni magia.</small></span>
        </button>
      </div>
    </section>
    <section class="block portrait-block" id="sec-portrait" tabindex="-1">
      <div class="block-head"><h3>Ritratto</h3></div>
      <label class="portrait-drop ${hasName ? '' : 'is-disabled'} ${thumb ? 'has-img' : ''}" for="portrait-file">
        ${thumb ? `<img src="${esc(thumb)}" alt="Ritratto di ${esc(c.name || 'eroe')}" onerror="this.parentNode.classList.remove('has-img');this.remove()">` : ''}
        <span class="portrait-empty">${emblem('d20', 'emblem big')}<span>${hasName ? 'Scegli un\'immagine' : 'Scrivi prima il nome'}</span></span>
      </label>
      <input type="file" id="portrait-file" accept="image/*" class="sr-only" data-change="portrait" ${hasName ? '' : 'disabled'}>
      <p class="hint small">Un disegno o una foto: finirà sulla seconda pagina della scheda.</p>
      ${c.portrait ? `<p class="ok-line">${emblem('check', 'i')} Ritratto salvato</p><button type="button" class="btn ghost small" data-act="portrait-remove">Togli il ritratto</button>` : ''}
    </section>
  </div>`;
  let list;
  if (CHARS == null) list = '<p class="hint">Cerco i personaggi salvati…</p>';
  else if (!CHARS.length) list = '<p class="hint">Non c\'è ancora nessun personaggio salvato: il primo sarà questo.</p>';
  else {
    list = `<div class="cards cards-sm">${CHARS.map((ch) => {
      const r = RULES.races[ch.race]; const k = RULES.classes[ch.class];
      const className = ch.class_name || (k ? k.name : '');
      const raceName = ch.race_name || (r ? r.name : '');
      const em = ch.portrait_url
        ? `<span class="card-portrait">${emblem(ch.class || 'd20')}<img src="${esc(ch.portrait_url)}" alt="" onerror="this.remove()"></span>`
        : emblem(ch.class || 'd20');
      return card({
        act: 'load-char', value: ch.stem, on: S.stem === ch.stem, em,
        title: ch.name || ch.stem, meta: [className ? `${className} ${ch.level || ''}`.trim() : '', raceName].filter(Boolean).join(' · '),
        body: ch.player ? `Gioca: ${ch.player}` : '', label: `Apri ${ch.name || ch.stem}`,
      });
    }).join('')}</div>`;
  }
  h += block('sec-saved', 'Oppure riprendi un personaggio salvato', list, { hint: 'Aprilo per cambiarlo, salire di livello o rifare il PDF.' });
  return h;
}

/* ------------------------------------------------------------------ passo 2: razza */
function renderRace() {
  const c = S.char;
  const R = req();
  let h = head(1);
  h += block('sec-races', 'Scegli la razza', `<div class="cards cards-lg">${Object.entries(RULES.races).map(([key, r]) => card({
    act: 'race', value: key, on: c.race === key, em: emblem(key), title: nm(r),
    meta: `${r.size || 'Medio'} · velocità ${feet2m(r.speed || 30)}`,
    chips: bonusChips(r.ability_bonus).concat(r.ability_choice ? [`+${r.ability_choice.bonus} a ${numWord(r.ability_choice.count)} a scelta`] : []),
    body: RACE_PITCH[key] || kidFmt((r.traits || []).find((t) => t.kid)?.kid || ''),
  })).join('')}</div>`);
  const race = raceOf(c);
  if (!race) return h;
  const subs = Object.entries(race.subraces || {});
  const vars = Object.entries(race.variants || {});
  if (subs.length || vars.length) {
    const items = subs.length ? subs : [['', { name: `${nm(race)} classic${isF() ? 'a' : 'o'}`, ability_bonus: race.ability_bonus, traits: [] }], ...vars];
    h += block('sec-subrace', subs.length ? 'Scegli la sottorazza' : 'Classico o variante?', `<div class="cards">${items.map(([key, s]) => card({
      act: 'subrace', value: key, on: (c.subrace || '') === key, em: emblem(c.race), title: nm(s),
      meta: s.speed ? `velocità ${feet2m(s.speed)}` : '',
      chips: bonusChips(s.ability_bonus).concat(s.ability_choice ? [`+${s.ability_choice.bonus} a ${numWord(s.ability_choice.count)} a scelta`] : []),
      body: key === '' ? 'Un punto in più a tutte le caratteristiche.' : (s.traits || []).map((t) => kidFmt(t.kid || t.short)).filter(Boolean).slice(0, 2).join(' '),
      k: `subrace-${key || 'base'}`,
    })).join('')}</div>`, { hint: subs.length ? 'Ogni popolo ha le sue famiglie, con doni diversi.' : 'La variante cambia i bonus e regala un talento.' });
  }
  if (race.ancestry) {
    h += block('sec-ancestry', 'Di che colore è il tuo drago?', `<div class="swatches">${Object.entries(race.ancestry).map(([key, a]) => `
      <button type="button" class="swatch" data-act="ancestry" data-value="${key}" data-k="anc-${key}" aria-pressed="${c.draconic_ancestry === key}">
        <span class="swatch-dot" style="--sw:${DRAGON_COLORS[key] || '#888'}" aria-hidden="true"></span>
        <span class="swatch-name">${esc(a.name)}</span>
        <span class="swatch-sub">${esc(cap(a.damage_type))} · ${esc(a.area)}</span>
        <span class="swatch-sub">TS su ${esc(ABNAME[a.save] || a.save)}</span>
      </button>`).join('')}</div>`, { hint: 'Il colore decide il tuo soffio e il danno a cui resisti.' });
  }
  const traits = raceTraits(c);
  h += block('sec-traits', `Cosa sa fare: ${esc(nm(subOf(c) || race))}`, `<ul class="traits">${traits.map((t) =>
    `<li><strong>${esc(nm(t))}</strong><span>${esc(kidFmt(t.kid || t.short || t.text))}</span></li>`).join('')}</ul>`, { cls: 'lore' });
  if (R.racial_choice) {
    const picks = asList(c.abilities.racial_choice);
    const excl = R.racial_choice.exclude || [];
    const fixedBonus = raceBonus(c).fixed;
    h += block('sec-racechoice', `Aumenta ${numWord(R.racial_choice.count)} caratteristiche di +${R.racial_choice.bonus}`,
      `<div class="chips">${ABIL.map((a) => chip({ act: 'racial-choice', value: a, on: picks.includes(a), label: ABNAME[a],
        sub: excl.includes(a) ? `ha già +${fixedBonus[a] || 0}` : ABBR[a], disabled: excl.includes(a) })).join('')}</div>`,
      { count: counter(picks.length, R.racial_choice.count), hint: `Scegli quelle che servono di più alla tua classe${excl.length ? ` (tranne ${excl.map((a) => ABNAME[a]).join(' e ')}: ha già il suo bonus)` : ''}.` });
  }
  if (R.racial_skills) {
    const fixed = new Set(traits.flatMap((t) => t.skills || []));
    const picks = asList(c.racial_skills);
    h += block('sec-raceskills', 'Abilità della razza', `<div class="chips">${sortIt(Object.keys(RULES.skills.skills), skillName).filter((s) => !fixed.has(s)).map((s) =>
      chip({ act: 'racial-skill', value: s, on: picks.includes(s), label: skillName(s), sub: ABBR[skillAbil(s)] })).join('')}</div>`,
    { count: counter(picks.length, R.racial_skills.count), hint: 'Abilità in cui il tuo popolo è allenato. Le altre le sceglierai con la classe.' });
  }
  if (R.racial_cantrip) {
    const pool = Object.entries(RULES.spells.spells).filter(([, sp]) => sp.level === 0 && (sp.lists || []).includes(R.racial_cantrip.list));
    const picks = asList(c.racial_cantrips);
    h += block('sec-racecantrip', 'Il trucchetto della razza', `<div class="spells">${pool.map(([key, sp]) => spellCard(key, sp, { act: 'racial-cantrip', on: picks.includes(key) })).join('')}</div>`,
      { count: counter(picks.length, 1), hint: `Un piccolo incantesimo che puoi usare quando vuoi. Usa ${ABNAME[R.racial_cantrip.ability] || 'Intelligenza'}.` });
  }
  if (raceFeatChoice(c)) {
    h += block('sec-racefeat', 'Il talento della razza', featPicker('race', S.raceFeat), { hint: 'Un talento è un dono speciale: leggi cosa fa e scegli quello che ti piace.' });
  }
  return h;
}

/* ------------------------------------------------------------------ passo 3: classe */
function classFirstKid(k) {
  const f1 = (k.features?.['1'] || []);
  const withKid = f1.find((f) => f.kid && !f.kid_hide) || f1.find((f) => f.kid);
  return withKid ? `${nm(withKid)}: ${withKid.kid}` : '';
}
function renderClass() {
  const c = S.char;
  const R = req();
  let h = head(2);
  h += block('sec-classes', 'Scegli la classe', `<div class="cards cards-lg">${Object.entries(RULES.classes).map(([key, k]) => card({
    act: 'class', value: key, on: c.class === key, em: emblem(key), title: nm(k),
    meta: `Dado vita d${k.hit_die} · punto forte: ${(CLASS_MAIN[key] || []).map((a) => ABNAME[a]).join(' e ') || '—'}`,
    chips: k.spellcasting ? ['Usa la magia'] : [],
    body: CLASS_PITCH[key] || kidFmt(classFirstKid(k)), cls: k.spellcasting ? 'is-magic' : '',
  })).join('')}</div>`);
  const k = clsOf(c);
  if (!k) return h;
  const lvl = c.level || 1;
  const thr = RULES.skills.xp_thresholds || [];
  h += block('sec-level', 'Livello', `<div class="level-row">
      <div class="level-dial" aria-hidden="true"><span class="level-num" id="level-num">${lvl}</span><span class="level-cap">livello</span></div>
      <div class="level-ctrl">
        <label class="label" for="f-level">Trascina per scegliere il livello</label>
        <input id="f-level" type="range" min="1" max="20" step="1" value="${lvl}" data-live="level" aria-valuetext="${lvl}° livello">
        <div class="level-ticks" aria-hidden="true"><span>1</span><span>5</span><span>10</span><span>15</span><span>20</span></div>
        ${field('Punti esperienza (PE)', 'xp', { type: 'number', id: 'f-xp', hint: `Per il ${ord(lvl)} livello servono almeno ${(thr[lvl - 1] ?? 0).toLocaleString('it-IT')} PE.`, attrs: 'min="0"' })}
      </div></div>`, { hint: 'Di solito si parte dal 1° livello: il master ti dice da quale livello cominciare.' });
  const subs = Object.entries(k.subclasses || {});
  const subLvl = k.subclass_level || 99;
  if (subs.length) {
    if (lvl >= subLvl) {
      h += block('sec-subclass', esc(k.subclass_label || 'Sottoclasse'), `<div class="cards">${subs.map(([key, sc]) => {
        const feats = Object.entries(sc.features || {}).filter(([L]) => +L <= lvl).flatMap(([, fs]) => fs || []);
        const txt = feats.filter((f) => !f.kid_hide).map((f) => kidFmt(f.kid || f.short)).filter(Boolean).slice(0, 2).join(' ');
        return card({ act: 'subclass', value: key, on: c.subclass === key, em: emblem(c.class), title: nm(sc),
          chips: feats.slice(0, 3).map((f) => nm(f)), body: txt, cls: 'card-sub' });
      }).join('')}</div>`, { hint: `Dal ${ord(subLvl)} livello la tua classe prende una strada speciale.` });
      const sc = activeSubclass(c);
      if (sc && sc.circle_spells) {
        h += block('sec-terrain', 'Il terreno del tuo circolo', `<div class="chips">${Object.keys(sc.circle_spells).map((t) =>
          chip({ act: 'terrain', value: t, on: c.circle_terrain === t, label: TERRAINS[t] || cap(t) })).join('')}</div>`,
        { hint: 'Il luogo a cui sei legato: ti regala incantesimi sempre pronti.' });
      }
    } else {
      h += `<p class="note">${emblem('star', 'i')} Al ${ord(subLvl)} livello sceglierai: <b>${esc(k.subclass_label || 'la sottoclasse')}</b>.</p>`;
    }
  }
  const feats = levelFeatures(c);
  h += block('sec-classfeat', `${esc(nm(k))} di ${ord(lvl)} livello: cosa sa fare`,
    `<ul class="traits">${feats.map((f) =>
      `<li><strong>${esc(nm(f))} <em class="lvl-tag">${ord(f.level)}</em></strong><span>${esc(textOf(f))}</span></li>`).join('')}</ul>`, { cls: 'lore' });
  return h;
}

/* ------------------------------------------------------------------ passo 4: background */
function renderBackground() {
  const c = S.char;
  let h = head(3);
  h += block('sec-backgrounds', 'Scegli il background', `<div class="cards">${Object.entries(RULES.backgrounds).map(([key, bg]) => card({
    act: 'background', value: key, on: c.background === key, em: emblem('scroll'), title: nm(bg),
    chips: (bg.skills || []).map(skillName).concat(bg.languages ? [`+${bg.languages} ${plural(bg.languages, 'linguaggio', 'linguaggi')}`] : []),
    body: bg.feature ? `${bg.feature.name}: ${kidFmt(bg.feature.kid || bg.feature.text)}` : '',
  })).join('')}</div>`);
  const bg = bgOf(c);
  if (!bg) return h;
  const eff = effectiveBgSkills(c);
  const dup = bgDuplicates(c);
  const R = req();
  const taken = proficientSet({ ...c, background_skills: null }, R);
  if (dup.length || (Array.isArray(c.background_skills) && c.background_skills.join() !== (bg.skills || []).join())) {
    h += block('sec-bgswap', 'Abilità doppie', (bg.skills || []).map((orig, i) => {
      const cur = eff[i];
      const others = Object.keys(RULES.skills.skills).filter((s) => !(taken[s] && taken[s] !== 'background') && !eff.some((e, j) => j !== i && e === s));
      if (!others.includes(cur)) others.unshift(cur);
      return `<div class="swap-row"><span class="swap-from">${esc(skillName(orig))}</span><span aria-hidden="true" class="swap-arrow">→</span>
        <label class="sr-only" for="bgswap-${i}">Al posto di ${esc(skillName(orig))}</label>
        <select id="bgswap-${i}" data-change="bgswap" data-index="${i}" data-k="bgswap-${i}">
          ${others.map((s) => `<option value="${s}" ${s === cur ? 'selected' : ''}>${esc(skillName(s))}${dup.includes(s) && s === cur ? ' (già tua: cambiala)' : ''}</option>`).join('')}
        </select></div>`;
    }).join(''), { hint: 'Se un\'abilità del background ce l\'hai già dalla razza o dalla classe, le regole ti fanno sceglierne un\'altra al suo posto.' });
  }
  const slots = bgToolSlots(c);
  if (slots.length) {
    const labels = toolSlotLabels(slots);
    h += block('sec-bgtools', 'Strumenti del background', slots.map((t, i) => (t.open
      ? `<div class="field"><label for="bgtool-${i}">${esc(t.dup ? `${t.label}: ce l'hai già, scegline un altro` : labels[i])}</label><input id="bgtool-${i}" list="tool-list-${t.category || 'all'}" data-input="bgtool" data-index="${i}" data-k="bgtool-${i}" value="${esc(t.value)}" placeholder="Scegli dall'elenco o scrivi quale" autocomplete="off"></div>`
      : `<p class="tool-fixed">${emblem('check', 'i')} ${esc(t.label)}</p>`)).join('') + toolDatalist(slots.map((t) => t.category)),
    { hint: 'Gli strumenti che il tuo eroe sa usare bene.' });
  }
  const f = bg.feature;
  h += block('sec-bgdetail', esc(nm(bg)), `<ul class="traits">
      ${f ? `<li><strong>${esc(f.name)}</strong><span>${esc(kidFmt(f.kid || f.text))}</span></li>` : ''}
      <li><strong>Abilità</strong><span>${eff.map(skillName).join(', ') || '—'}</span></li>
      ${bg.languages ? `<li><strong>Linguaggi</strong><span>${bg.languages} a scelta: li scegli al passo Abilità.</span></li>` : ''}
      ${(bg.equipment || []).length ? `<li><strong>Equipaggiamento</strong><span>${esc(bg.equipment.join(', '))}${bg.gold ? `, ${bg.gold} mo` : ''}</span></li>` : ''}
    </ul>`, { cls: 'lore' });
  return h;
}
function toolDatalist(categories = [null]) {
  return [...new Set(categories.map((x) => x || null))].map((cat) => `<datalist id="tool-list-${cat || 'all'}">${toolNames(cat).map((t) =>
    `<option value="${esc(t)}"></option>`).join('')}</datalist>`).join('');
}

/* ------------------------------------------------------------------ passo 5: caratteristiche */
const METHODS = [
  ['point_buy', 'Punti da spendere', '27 punti da distribuire'],
  ['standard_array', 'Valori fissi', '15, 14, 13, 12, 10, 8'],
  ['rolled', 'Tiro i dadi', '4d6, tieni i 3 più alti'],
  ['manual', 'Scrivo io', 'numeri dati dal master'],
];
let ROLLING = false;
function arrayPool(method) {
  if (method === 'standard_array') return (req().standard_array || RULES.skills.standard_array || [15, 14, 13, 12, 10, 8]);
  return S.rolls;
}
function syncAssignedBase(method) {
  const pool = arrayPool(method);
  const asg = S.assign[method] || {};
  for (const a of ABIL) {
    const idx = asg[a];
    const v = idx == null || idx === '' ? null : pool[idx];
    S.char.abilities.base[a] = v == null ? null : Number(v);
  }
}
function renderAbilities() {
  const c = S.char;
  const R = req();
  const ab = c.abilities;
  const method = ab.method || 'point_buy';
  const bc = baseChar();
  const scores = computeScores(bc);
  let h = head(4);
  const k = clsOf(c);
  if (k) {
    const prio = CLASS_PRIORITY[c.class] || ABIL;
    h += block('sec-builds', `Consigliati per ${isF() ? 'una' : 'un'} ${esc(nm(k))}`, `<div class="builds">${BUILDS.map((b, i) => {
      const vals = Object.fromEntries(prio.map((a, j) => [a, b.values[j]]));
      return `<button type="button" class="build" data-act="build-apply" data-value="${i}" data-k="build-${i}">
        <span class="build-name">${esc(b.name)}</span><span class="build-hint">${esc(b.hint)}</span>
        <span class="build-vals">${ABIL.map((a) => `<span class="${prio.slice(0, 2).includes(a) ? 'hi' : ''}"><small>${ABBR[a]}</small>${vals[a]}</span>`).join('')}</span>
        <span class="build-go">Usa questi numeri</span></button>`;
    }).join('')}</div>`, { hint: 'Il modo più veloce: un clic e i punti sono già distribuiti bene per la tua classe. Puoi sempre ritoccarli.' });
  }
  const tabs = `<div class="tabs" role="tablist" aria-label="Come scegli i numeri">${METHODS.map(([key, label, sub]) =>
    `<button type="button" role="tab" class="tab" aria-selected="${method === key}" data-act="method" data-value="${key}" data-k="method-${key}"><span>${label}</span><small>${sub}</small></button>`).join('')}</div>`;
  let extra = '';
  if (method === 'point_buy') {
    const pb = R.point_buy || RULES.skills.point_buy;
    const spent = sum(ABIL.map((a) => pb.costs[String(ab.base[a])] ?? 0));
    const left = pb.budget - spent;
    extra = `<div class="gems" role="img" aria-label="Punti spesi ${spent} su ${pb.budget}">
      ${Array.from({ length: pb.budget }, (_, i) => `<span class="gem ${i < spent ? 'on' : ''}"></span>`).join('')}</div>
      <p class="gems-text">${left > 0 ? `Ti ${left === 1 ? 'resta' : 'restano'} <b>${left}</b> ${plural(left, 'punto', 'punti')} da spendere.` : left === 0 ? 'Hai speso tutti i punti. Perfetto!' : `Hai speso <b>${-left}</b> punti di troppo.`}
      <span class="small">Ogni numero parte da 8; salire costa di più verso il 15.</span></p>`;
  } else if (method === 'standard_array') {
    extra = `<p class="hint">Dai a ogni caratteristica uno dei sei valori. Il più alto va su quella che serve alla tua classe.</p>
      ${k ? '<button type="button" class="btn ghost small" data-act="array-auto">Metti i valori al posto giusto per me</button>' : ''}`;
  } else if (method === 'rolled') {
    extra = `<div class="dice-tray ${ROLLING ? 'is-rolling' : ''}">
      <button type="button" class="btn gold" data-act="roll" data-k="roll">${emblem('d20', 'i')} Tira 4d6 sei volte</button>
      <div class="rolls">${S.rolls.map((v, i) => {
        const dice = S.rollDice[i] || [];
        const low = dice.length ? dice.indexOf(Math.min(...dice)) : -1;
        return `<div class="roll"><span class="dice">${dice.map((d, j) => `<span class="die ${j === low ? 'drop' : ''}">${d}</span>`).join('')}</span>
          <label class="sr-only" for="roll-${i}">Risultato ${i + 1}</label>
          <input id="roll-${i}" type="number" min="3" max="18" inputmode="numeric" data-input="roll" data-index="${i}" data-k="roll-${i}" value="${v ?? ''}" placeholder="—"></div>`;
      }).join('')}</div>
      <p class="hint small">Tira i dadi qui oppure scrivi i risultati dei tuoi dadi veri. Poi assegna ogni risultato a una caratteristica.</p></div>`;
  } else {
    extra = '<p class="hint">Scrivi i punteggi che ti ha dato il master, da 3 a 18, prima dei bonus della razza.</p>';
  }
  const rows = ABIL.map((a) => {
    const sc = scores[a];
    let ctrl;
    if (method === 'point_buy') {
      const pb = R.point_buy || RULES.skills.point_buy;
      const v = Number(ab.base[a] ?? 8);
      const spent = sum(ABIL.map((x) => pb.costs[String(ab.base[x])] ?? 0));
      const nextCost = (pb.costs[String(v + 1)] ?? 99) - (pb.costs[String(v)] ?? 0);
      ctrl = `<div class="stepper-ctl">
        <button type="button" class="round" data-act="pb" data-value="${a}:-1" data-k="pb-${a}-minus" aria-label="Diminuisci ${ABNAME[a]}" ${v <= 8 ? 'disabled' : ''}>−</button>
        <output class="base-val" aria-live="polite">${v}</output>
        <button type="button" class="round" data-act="pb" data-value="${a}:1" data-k="pb-${a}-plus" aria-label="Aumenta ${ABNAME[a]}" ${v >= 15 || spent + nextCost > pb.budget ? 'disabled' : ''}>+</button>
        <span class="cost">costo ${pb.costs[String(v)] ?? '?'}</span></div>`;
    } else if (method === 'standard_array' || method === 'rolled') {
      const pool = arrayPool(method);
      const asg = S.assign[method] || {};
      const usedBy = {};
      for (const x of ABIL) if (asg[x] != null && asg[x] !== '') usedBy[asg[x]] = x;
      ctrl = `<label class="sr-only" for="asg-${a}">Valore di ${ABNAME[a]}</label><select id="asg-${a}" class="asg" data-change="assign" data-ability="${a}" data-k="asg-${a}">
        <option value="">—</option>${pool.map((v, i) => (v == null ? '' : `<option value="${i}" ${String(asg[a]) === String(i) ? 'selected' : ''} ${usedBy[i] && usedBy[i] !== a ? 'disabled' : ''}>${v}${usedBy[i] && usedBy[i] !== a ? ` (${ABBR[usedBy[i]]})` : ''}</option>`)).join('')}</select>`;
    } else {
      ctrl = `<label class="sr-only" for="man-${a}">${ABNAME[a]}</label><input id="man-${a}" class="man" type="number" min="3" max="18" inputmode="numeric" data-bind="abilities.base.${a}" data-num value="${ab.base[a] ?? ''}">`;
    }
    const mod = sc.base == null ? null : sc.mod;
    return `<div class="ab-row">
      <div class="ab-name"><b>${ABNAME[a]}</b> <span class="abbr">${ABBR[a]}</span><small>${ABHINT[a]}</small></div>
      <div class="ab-ctrl">${ctrl}</div>
      <div class="ab-plus" title="Bonus della razza"><small class="ab-cap" aria-hidden="true">razza</small>${sc.race ? `<span class="plus race"><span class="sr-only">razza </span>+${sc.race}</span>` : '<span class="plus none">·</span>'}</div>
      <div class="ab-plus" title="Aumenti e talenti"><small class="ab-cap" aria-hidden="true">extra</small>${sc.extra ? `<span class="plus asi"><span class="sr-only">aumenti e talenti </span>+${sc.extra}</span>` : '<span class="plus none">·</span>'}</div>
      <div class="ab-total"><span class="total">${sc.base == null ? '—' : sc.total}</span><span class="mod ${mod == null ? '' : mod > 0 ? 'pos' : mod < 0 ? 'neg' : ''}">${mod == null ? '' : fmtMod(mod)}</span></div>
    </div>`;
  }).join('');
  h += block('sec-method', 'Come scegli i numeri', `${tabs}<div class="method-extra">${extra}</div>
    <div class="ab-table" role="group" aria-label="Caratteristiche">
      <div class="ab-row ab-headrow" aria-hidden="true"><span>Caratteristica</span><span>Base</span><span>Razza</span><span>Extra</span><span>Totale</span></div>
      ${rows}</div>
    <p class="hint small">Il numero piccolo accanto al totale è il <b>modificatore</b>: è quello che aggiungi ai tiri di dado.</p>`);
  // aumenti di caratteristica e talenti
  for (const L of R.asi_levels || []) {
    const s = S.slots[L] || { type: 'asi', asi: [] };
    const type = s.type || 'asi';
    let body = `<div class="segs">
      <button type="button" class="seg" data-act="slot-type" data-value="${L}:asi" data-k="slot-${L}-asi" aria-pressed="${type === 'asi'}"><span>Aumenta le caratteristiche</span><small>+2 a una, oppure +1 a due</small></button>
      ${R.feats_allowed !== false ? `<button type="button" class="seg" data-act="slot-type" data-value="${L}:feat" data-k="slot-${L}-feat" aria-pressed="${type === 'feat'}"><span>Scegli un talento</span><small>un dono speciale</small></button>` : ''}
    </div>`;
    if (type === 'asi') {
      body += `<div class="asi-picks">${[0, 1].map((i) => `<div class="field"><label for="asi-${L}-${i}">${i === 0 ? 'Primo punto (+1)' : 'Secondo punto (+1)'}</label>
        <select id="asi-${L}-${i}" data-change="slot-asi" data-level="${L}" data-index="${i}" data-k="asi-${L}-${i}"><option value="">—</option>
        ${ABIL.map((a) => `<option value="${a}" ${(s.asi || [])[i] === a ? 'selected' : ''}>${ABNAME[a]} (ora ${scores[a].total})</option>`).join('')}</select></div>`).join('')}</div>
        <p class="hint small">Puoi mettere tutti e due i punti sulla stessa caratteristica. Il massimo è 20.</p>`;
    } else {
      body += featPicker(`slot-${L}`, s.feat);
    }
    h += block(`sec-asi-${L}`, `${ord(L)} livello: aumento o talento`, body);
  }
  return h;
}

/* talenti */
function getFeatSlot(scope) {
  if (scope === 'race') return S.raceFeat;
  const L = scope.replace('slot-', '');
  return S.slots[L]?.feat || null;
}
function setFeatSlot(scope, val) {
  if (scope === 'race') { S.raceFeat = val; return; }
  const L = scope.replace('slot-', '');
  S.slots[L] = { ...(S.slots[L] || {}), type: 'feat', feat: val };
}
function featPicker(scope, cur) {
  const feats = RULES.feats || {};
  const open = !!S.ui.featOpen[scope] || !cur?.key;
  let h = '';
  if (cur?.key && feats[cur.key]) {
    const f = feats[cur.key];
    h += `<div class="feat-chosen"><div class="feat-chosen-text"><span class="eyebrow">Talento scelto</span><strong>${esc(f.name)}</strong><p>${esc(kidFmt(f.kid || f.short))}</p>`;
    if (f.ability_choice) {
      h += `<div class="field"><label for="featab-${scope}">Quale caratteristica aumenta di +${f.ability_choice.bonus || 1}?</label>
        <select id="featab-${scope}" data-change="feat-ability" data-scope="${scope}" data-k="featab-${scope}"><option value="">—</option>
        ${(f.ability_choice.from || ABIL).map((a) => `<option value="${a}" ${cur.ability === a ? 'selected' : ''}>${ABNAME[a]}</option>`).join('')}</select></div>`;
    }
    const wp = f.weapon_proficiencies;
    if (wp && !Array.isArray(wp) && wp.count) {
      const picks = asList(cur.weapons);
      const pool = Object.entries(RULES.equipment.weapons).filter(([, w]) => !wp.from || wp.from.includes(w.category));
      h += `<p class="label">Scegli ${wp.count} armi ${counter(picks.length, wp.count)}</p><div class="chips">${pool.map(([key, w]) =>
        chip({ act: 'feat-weapon', value: `${scope}|${key}`, on: picks.includes(key), label: w.name })).join('')}</div>`;
    }
    h += featSpellChoices(scope, f, cur);
    h += `</div><button type="button" class="btn ghost small" data-act="feat-open" data-value="${scope}" data-k="featopen-${scope}">${open ? 'Chiudi l\'elenco' : 'Cambia talento'}</button></div>`;
  }
  if (open) {
    const q = norm(S.ui.featQuery[scope] || '');
    const list = Object.entries(feats).filter(([, f]) => !q || norm(`${f.name} ${f.short} ${f.kid}`).includes(q));
    h += `<div class="feat-list"><div class="search"><label class="sr-only" for="featq-${scope}">Cerca un talento</label>
      <input id="featq-${scope}" type="search" placeholder="Cerca un talento…" data-input="feat-query" data-scope="${scope}" data-k="featq-${scope}" value="${esc(S.ui.featQuery[scope] || '')}" autocomplete="off"></div>
      <div class="feat-items">${list.map(([key, f]) => `<button type="button" class="feat-item" data-act="feat-pick" data-value="${scope}|${key}" data-k="feat-${scope}-${key}" aria-pressed="${cur?.key === key}">
        <span class="feat-name">${esc(f.name)}${f.prerequisite ? `<span class="tag warn">Serve: ${esc(f.prerequisite)}</span>` : ''}</span>
        <span class="feat-kid">${esc(kidFmt(f.kid || f.short))}</span></button>`).join('') || '<p class="hint">Nessun talento con queste parole.</p>'}</div></div>`;
  }
  return h;
}

function featSpellChoices(scope, f, cur) {
  let h = '';
  const cc = f.cantrip_choice;
  const scc = f.spell_choice;
  const lists = asList(cc?.lists || scc?.lists);
  if (lists.length) {
    h += `<div class="field"><label for="featlist-${scope}">Da quale lista prendi le magie?</label>
      <select id="featlist-${scope}" data-change="feat-list" data-scope="${scope}" data-k="featlist-${scope}"><option value="">—</option>
      ${lists.map((l) => `<option value="${l}" ${cur.list === l ? 'selected' : ''}>${esc(RULES.classes[l] ? nm(RULES.classes[l]) : l)}${cc?.ability_by_list?.[l] ? ` (usa ${ABNAME[cc.ability_by_list[l]]})` : ''}</option>`).join('')}</select></div>`;
  }
  const list = cur.list;
  if (cc && list) {
    const picks = asList(cur.cantrips);
    const pool = Object.entries(RULES.spells.spells).filter(([, sp]) => sp.level === 0 && (sp.lists || []).includes(list) && (!cc.attack_roll_required || sp.attack))
      .sort((a, b) => a[1].name.localeCompare(b[1].name, 'it'));
    h += `<p class="label">Trucchetti del talento ${counter(picks.length, cc.count || 1)}</p><div class="chips">${pool.map(([k, sp]) =>
      chip({ act: 'feat-cantrip', value: `${scope}|${k}`, on: picks.includes(k), label: sp.name, title: spellFmt(sp, sp.kid || sp.text) })).join('')}</div>`;
  }
  if (scc && list) {
    const picks = asList(cur.spells);
    const lvl = scc.level || 1;
    const pool = Object.entries(RULES.spells.spells).filter(([, sp]) => sp.level === lvl && (sp.lists || []).includes(list) && (!scc.ritual_only || sp.ritual))
      .sort((a, b) => a[1].name.localeCompare(b[1].name, 'it'));
    h += `<p class="label">${scc.ritual_only ? 'Rituali' : 'Incantesimi'} del talento ${counter(picks.length, scc.count || 1)}</p><div class="chips">${pool.map(([k, sp]) =>
      chip({ act: 'feat-spell', value: `${scope}|${k}`, on: picks.includes(k), label: sp.name, title: spellFmt(sp, sp.kid || sp.text) })).join('') || '<p class="hint">Nessun incantesimo adatto in questa lista.</p>'}</div>`;
  }
  if (f.damage_type_choice) {
    h += `<p class="label">Tipo di danno</p><div class="chips">${asList(f.damage_type_choice).map((d) =>
      chip({ act: 'feat-dmg', value: `${scope}|${d}`, on: cur.damage_type === d, label: cap(d) })).join('')}</div>`;
  }
  return h;
}

/* ------------------------------------------------------------------ passo 6: abilità */
function skillInfo() {
  const c = baseChar();
  const R = req();
  const prof = proficientSet(c, R);
  const exp = new Set(asList(c.expertise));
  const scores = computeScores(c);
  const pb = RULES.skills.proficiency_bonus[(c.level || 1) - 1];
  const { s, provisional } = sheet();
  const fresh = !provisional && PREVIEW && PREVIEW.key === CUR_KEY;
  const out = {};
  for (const [k, info] of Object.entries(RULES.skills.skills)) {
    const isProf = !!prof[k];
    let value;
    if (fresh && s?.skills?.[k]?.value != null) value = s.skills[k].value;
    else value = scores[info.ability].mod + (isProf ? pb * (exp.has(k) ? 2 : 1) : 0);
    out[k] = { value, prof: isProf, exp: exp.has(k), source: prof[k], name: info.it, ability: info.ability };
  }
  return out;
}
function knownLanguages(c = S.char) {
  const out = new Set();
  const race = raceOf(c);
  (race?.languages || []).forEach((l) => out.add(l));
  for (const f of levelFeatures(c)) (f.languages || []).forEach((l) => out.add(l));
  if (c.class === 'druid') out.add('druidic');
  if (c.class === 'rogue') out.add('thieves_cant');
  return out;
}
function renderSkills() {
  const c = baseChar();
  const R = req();
  const info = skillInfo();
  let h = head(5);
  if (!clsOf(c)) return `${h}<p class="note">${emblem('star', 'i')} Scegli prima la classe: ogni classe ha le sue abilità.</p>`;
  const others = proficientSet({ ...c, skills: [] }, R);
  if (R.class_skills) {
    const picks = asList(c.skills);
    const pool = sortIt(R.class_skills.from?.length ? R.class_skills.from : Object.keys(RULES.skills.skills), skillName);
    h += block('sec-classskills', 'Abilità della classe', `<div class="chips">${pool.map((s) => {
      const dup = !!others[s];
      const on = picks.includes(s);
      return chip({ act: 'skill-class', value: s, on, label: skillName(s), sub: dup && !on ? `già tua (${others[s]})` : fmtMod(info[s].value), disabled: dup && !on, cls: dup && on ? 'is-dup' : '' });
    }).join('')}</div>`, { count: counter(picks.filter((s) => !others[s]).length, R.class_skills.count), hint: 'Le abilità già date dalla razza o dal background non si possono scegliere due volte.' });
  }
  if (R.extra_skills) {
    const picks = extraPicks(c, R);
    const pool = sortIt(extraSkillPool(R), skillName);
    const prof = proficientSet({ ...c, extra_skills: [] }, R);
    const sources = asList(R.extra_skills.sources).map((x) => x && x.source).filter(Boolean);
    h += block('sec-extraskills', 'Abilità extra', `<div class="chips">${pool.map((s) => chip({ act: 'skill-extra', value: s, on: picks.includes(s), label: skillName(s), sub: prof[s] && !picks.includes(s) ? 'già tua' : fmtMod(info[s].value), disabled: !!prof[s] && !picks.includes(s) })).join('')}</div>`,
      { count: counter(picks.length, R.extra_skills.count), hint: sources.length ? `Abilità in più regalate da: ${esc(sources.join(', '))}.` : 'Un privilegio o un talento ti regala altre abilità.' });
  }
  if (R.expertise) {
    const picks = expertisePicks(c, R);
    const pool = sortIt(expertisePool(c, R), skillName);
    h += block('sec-expertise', 'Maestria', pool.length ? `<div class="chips">${pool.map((s) => chip({ act: 'skill-exp', value: s, on: picks.includes(s), label: skillName(s), sub: fmtMod(info[s].value) })).join('')}</div>`
      : '<p class="hint">Scegli prima le abilità: la maestria si mette su quelle che conosci già.</p>',
    { count: counter(picks.length, R.expertise.count), hint: 'Nelle abilità con maestria sei bravissimo: il tuo bonus di competenza conta doppio.' });
  }
  if (R.languages) {
    const known = knownLangSet(c, R);
    const picks = langPicks(c, R);
    const pool = sortIt(Object.keys(RULES.skills.languages).filter((l) => !known.has(l) && l !== 'druidic' && l !== 'thieves_cant'), langName);
    h += block('sec-languages', 'Linguaggi', `<p class="hint small">Parli già: ${[...known].map(langName).join(', ') || '—'}.</p><div class="chips">${pool
      .map((l) => chip({ act: 'lang', value: l, on: picks.includes(l), label: langName(l) })).join('')}</div>`,
    { count: counter(picks.length, R.languages.count), hint: 'Le lingue in più che il tuo eroe sa parlare, leggere e scrivere.' });
  }
  if (R.tools) {
    const tools = toolPicks(c);
    const slots = Array.from({ length: R.tools.count }, (_, i) => asList(R.tools.slots)[i] || { label: `Strumento ${i + 1}`, category: null });
    const labels = toolSlotLabels(slots);
    h += block('sec-tools', 'Strumenti', slots.map((sl, i) => `<div class="field"><label for="tool-${i}">${esc(labels[i])}</label>
      <input id="tool-${i}" list="tool-list-${sl.category || 'all'}" data-input="tool" data-index="${i}" data-k="tool-${i}" value="${esc(tools[i] || '')}" placeholder="Scegli dall'elenco o scrivi quale" autocomplete="off"></div>`).join('') + toolDatalist(slots.map((sl) => sl.category)),
    { count: counter(tools.slice(0, R.tools.count).filter(Boolean).length, R.tools.count), hint: 'Scrivi lo strumento oppure sceglilo dall\'elenco che compare.' });
  }
  const rows = Object.entries(info).sort((a, b) => a[1].name.localeCompare(b[1].name, 'it')).map(([k, s]) =>
    `<li class="${s.prof ? 'is-prof' : ''} ${s.exp ? 'is-exp' : ''}"><span class="pip" aria-hidden="true"></span><span class="sk-name">${esc(s.name)}</span>
     <span class="sk-ab">${ABBR[s.ability]}</span><span class="sk-src">${s.exp ? 'maestria' : s.prof ? esc(s.source || '') : ''}</span><span class="sk-val">${fmtMod(s.value)}</span>
     <span class="sr-only">${s.prof ? 'competente' : ''}</span></li>`).join('');
  h += block('sec-allskills', 'Tutte le abilità', `<ul class="skill-list">${rows}</ul>`, { hint: 'Il pallino pieno vuol dire che il tuo eroe è allenato in quell\'abilità.' });
  return h;
}

/* ------------------------------------------------------------------ passo 7: magie */
function spellCard(key, sp, { act, on = false, locked = false, kind = '', note = '', lockText = 'Sempre preparato' }) {
  const lvl = sp.level === 0 ? 'Trucchetto' : `${ord(sp.level)} livello`;
  const value = kind ? `${kind}|${key}` : key;
  const meta = [cap(sp.school), sp.cast, rangeText(sp.range), sp.duration].filter(Boolean).join(' · ');
  return `<article class="spell ${on ? 'is-on' : ''} ${locked ? 'is-locked' : ''}" ${locked ? '' : `data-act="${act}" data-value="${esc(value)}"`}>
    <header class="spell-head"><span class="spell-lvl">${lvl}</span>
      <span class="badges">${sp.conc ? '<abbr class="badge" title="Concentrazione: dura finché resti concentrato">C</abbr>' : ''}${sp.ritual ? '<abbr class="badge" title="Rituale: puoi lanciarlo in 10 minuti in più senza usare uno slot">R</abbr>' : ''}</span></header>
    <h4>${esc(sp.name)}</h4>
    <p class="spell-meta">${esc(meta)}</p>
    <p class="spell-kid">${esc(spellFmt(sp, sp.kid || sp.text))}</p>
    ${sp.tip ? `<p class="spell-tip">${esc(spellFmt(sp, sp.tip))}</p>` : ''}
    ${sp.text && sp.kid ? `<details><summary>Testo completo</summary><p>${esc(spellFmt(sp, sp.text))}</p></details>` : ''}
    ${note ? `<p class="spell-note">${esc(note)}</p>` : ''}
    ${locked ? `<p class="spell-lock">${emblem('lock', 'i')} ${esc(lockText)}</p>`
      : `<button type="button" class="pick" data-act="${act}" data-value="${esc(value)}" data-k="sp-${esc(value)}" aria-pressed="${on}">${on ? `${emblem('check', 'i')} Scelto` : 'Scegli'}</button>`}
  </article>`;
}
function spellPool(R, level) {
  const out = [];
  if (level === 'c') {
    const lists = R.cantrips?.lists || [R.spells?.list].filter(Boolean);
    for (const [k, sp] of Object.entries(RULES.spells.spells)) if (sp.level === 0 && (sp.lists || []).some((l) => lists.includes(l))) out.push([k, sp]);
  } else {
    const list = R.spells?.list;
    const extra = R.spells?.extra_lists || [];
    const expanded = new Set(R.spells?.expanded || []);
    for (const [k, sp] of Object.entries(RULES.spells.spells)) {
      if (sp.level !== level) continue;
      if ((sp.lists || []).includes(list) || (sp.lists || []).some((l) => extra.includes(l)) || expanded.has(k)) out.push([k, sp]);
    }
  }
  return out.sort((a, b) => a[1].name.localeCompare(b[1].name, 'it'));
}
function alwaysPrepared(R) {
  const all = [...asList(R.spells?.always_prepared), ...asList(R.spells?.circle_spells)];
  // livello degli incantesimi del circolo scritti per nome: dal livello da druido in cui arrivano
  const circleLevel = {};
  const sc = activeSubclass();
  const byTerrain = sc?.circle_spells?.[S.char.circle_terrain] || {};
  for (const [L, names] of Object.entries(byTerrain)) for (const n of asList(names)) circleLevel[n] = Math.ceil(Number(L) / 2);
  return all.filter((x, i) => all.indexOf(x) === i).map((x) => {
    const key = spellOf(x) ? x : spellByName(x);
    const sp = key ? spellOf(key) : null;
    return { key: key || x, sp: sp || { name: String(x), level: circleLevel[x] ?? null, school: '', text: 'Incantesimo del circolo, sempre preparato.' } };
  });
}
const alwaysPreparedKeys = (R = req()) => new Set(alwaysPrepared(R).map((x) => x.key));
/* Trucchetti che la razza dà già (fissi, es. Illusione Minore dello gnomo delle foreste, o scelti come l'elfo alto). */
function racialCantrips(c = S.char) {
  const out = raceTraits(c).flatMap((t) => asList(t.fixed_cantrips)).concat(asList(c.racial_cantrips));
  return out.filter((k, i) => k && out.indexOf(k) === i);
}
function dropRacialFromClassCantrips() {
  const racial = racialCantrips();
  S.char.cantrips = asList(S.char.cantrips).filter((k) => !racial.includes(k));
}
function grantedCantrips(R) {
  return [...asList(R.cantrips?.granted), ...asList(R.granted_cantrips)].filter((k, i, a) => spellOf(k) && a.indexOf(k) === i);
}
const SCHOOL_IT = { abjuration: 'abiurazione', conjuration: 'evocazione', divination: 'divinazione', enchantment: 'ammaliamento', evocation: 'invocazione', illusion: 'illusione', necromancy: 'necromanzia', transmutation: 'trasmutazione' };
function renderMagic() {
  const c = S.char;
  const R = req();
  let h = head(6);
  if (!clsOf(c)) return `${h}<p class="note">${emblem('star', 'i')} Scegli prima la classe.</p>`;
  if (!isCaster(R)) return `${h}<p class="note">${emblem('star', 'i')} ${esc(nm(clsOf(c)))} di ${ord(c.level)} livello non usa la magia: puoi saltare questo passo.</p>`;
  const book = !!R.spellbook;
  const mode = book ? (S.ui.bookMode || 'book') : 'list';
  const counters = [];
  // stessi conti del riquadro "cosa manca": senza i trucchetti della razza o regalati e senza le magie sopra il livello
  const ownCantrips = asList(c.cantrips).filter((k) => !racialCantrips(c).includes(k) && !grantedCantrips(R).includes(k));
  if (R.cantrips) counters.push(['Trucchetti', ownCantrips.length, R.cantrips.count]);
  if (book) counters.push(['Nel libro', asList(c.spellbook).filter((k) => (spellOf(k)?.level ?? 1) <= (R.spells?.max_level || 9)).length, R.spellbook.count]);
  if (R.spells && (R.spells.count || R.spells.max_level)) counters.push([R.spells.mode === 'known' ? 'Conosciuti' : 'Preparati', countedSpells(c, R).length, R.spells.count || null]);
  const { s } = sheet();
  const slots = s?.spellcasting?.slots || {};
  h += `<div class="magic-bar" id="sec-spells" tabindex="-1">
    <div class="counters">${counters.map(([l, n, m]) => `<span class="mcount ${m != null && n === m ? 'ok' : m != null && n > m ? 'over' : ''}"><small>${l}</small><b>${n}</b>${m != null ? `<span>/ ${m}</span>` : ''}</span>`).join('')}</div>
    ${Object.keys(slots).length ? `<p class="slots">Slot: ${Object.entries(slots).map(([L, n]) => `<span><b>${n}</b> di ${ord(L)}</span>`).join(' ')}</p>` : ''}
    ${s?.spellcasting?.save_dc ? `<p class="slots">CD dei tiri salvezza <b>${s.spellcasting.save_dc}</b> · attacco magico <b>${fmtMod(s.spellcasting.attack_bonus)}</b></p>` : ''}
  </div>`;
  if (book) {
    h += `<div class="segs book-segs">
      <button type="button" class="seg" data-act="book-mode" data-value="book" data-k="book-book" aria-pressed="${mode === 'book'}"><span>1. Il libro degli incantesimi</span><small>tutto quello che hai imparato</small></button>
      <button type="button" class="seg" data-act="book-mode" data-value="prep" data-k="book-prep" aria-pressed="${mode === 'prep'}"><span>2. Preparati oggi</span><small>scelti dal libro</small></button></div>
      <p class="hint">${mode === 'book' ? `Prima riempi il libro: ${R.spellbook.count} incantesimi in tutto. Poi scegli quali preparare.` : `Ogni giorno prepari ${R.spells?.count ?? 'alcuni'} incantesimi presi dal libro.`}</p>`;
  }
  const sch = R.spells?.schools;
  if (sch && asList(sch.allowed).length) {
    const names = asList(sch.allowed).map((x) => SCHOOL_IT[x] || x);
    h += `<p class="note">${emblem('scroll', 'i')} <span>I tuoi incantesimi vengono dalle scuole di <b>${esc(names.join(' e '))}</b>${sch.any_school_count ? `; ${sch.any_school_count === 1 ? 'uno può essere' : `${sch.any_school_count} possono essere`} di una scuola qualsiasi` : ''}.</span></p>`;
  }
  const maxL = R.spells?.max_level || 0;
  const arc = asList(R.spells?.arcanum_levels).filter((L) => L > maxL);
  const tabs = [];
  if (R.cantrips && mode !== 'prep') tabs.push('c');
  for (let L = 1; L <= maxL; L++) tabs.push(L);
  if (mode !== 'book') for (const L of arc) tabs.push(L);
  let tab = S.ui.spellTab;
  if (!tabs.includes(tab)) tab = tabs[0];
  if (arc.includes(tab)) h += `<p class="note">${emblem('star', 'i')} <span><b>Arcanum Mistico</b>: un solo incantesimo di ${ord(tab)} livello, che lanci una volta per riposo lungo senza usare slot.</span></p>`;
  if (tabs.length > 1) {
    h += `<div class="tabs tabs-sm" role="tablist" aria-label="Livello degli incantesimi">${tabs.map((t) => {
      let n = 0;
      if (t === 'c') n = asList(c.cantrips).length;
      else n = asList(mode === 'book' ? c.spellbook : c.spells).filter((k) => spellOf(k)?.level === t).length;
      return `<button type="button" role="tab" class="tab" aria-selected="${t === tab}" data-act="spell-tab" data-value="${t}" data-k="stab-${t}"><span>${t === 'c' ? 'Trucchetti' : `${ord(t)} livello`}</span>${n ? `<small>${n} ${plural(n, 'scelto', 'scelti')}</small>` : '<small>&nbsp;</small>'}</button>`;
    }).join('')}</div>`;
  }
  h += `<div class="search"><label class="sr-only" for="spell-q">Cerca un incantesimo</label>
    <input id="spell-q" type="search" placeholder="Cerca per nome o scuola…" data-input="spell-query" data-k="spell-q" value="${esc(S.ui.spellQuery || '')}" autocomplete="off"></div>`;
  const q = norm(S.ui.spellQuery || '');
  const match = ([, sp]) => !q || norm(`${sp.name} ${sp.school}`).includes(q);
  let cards = '';
  // prima le magie della propria lista (o scuola), poi quelle permesse solo in parte, sotto un titolo che dice quante
  const lim = spellLimits(c, R);
  const inMain = (sp) => (sp.lists || []).includes(lim.main);
  const divider = (title, n, max) => `<p class="spells-divider">${emblem('star', 'i')}<span>${esc(title)}</span>${counter(n, max)}</p>`;
  if (tab === 'c') {
    const picks = asList(c.cantrips);
    const granted = grantedCantrips(R);
    const racial = racialCantrips(c).filter((k) => spellOf(k) && !granted.includes(k)); // già noti dalla razza: non si scelgono due volte
    cards = granted.map((k) => spellCard(k, spellOf(k), { locked: true, lockText: 'Regalato dalla classe' })).join('');
    cards += racial.map((k) => spellCard(k, spellOf(k), { locked: true, lockText: 'Lo conosci già dalla razza' })).join('');
    const pool = spellPool(R, 'c').filter(match).filter(([k]) => !granted.includes(k) && !racial.includes(k));
    const one = ([k, sp], note = '') => spellCard(k, sp, { act: 'spell', kind: 'cantrip', on: picks.includes(k), note });
    cards += pool.filter(([, sp]) => inMain(sp)).map((x) => one(x)).join('');
    const other = pool.filter(([, sp]) => !inMain(sp));
    if (other.length) {
      const src = lim.extraC.map((e) => `${e.source}: dalla lista del ${listName(e.list)}`).join(' · ') || 'Da altre liste';
      cards += divider(src, lim.offCantrips.length, lim.cantripMax) + other.map((x) => {
        const from = lim.extraC.find((e) => (x[1].lists || []).includes(e.list));
        return one(x, from ? `Lista del ${listName(from.list)}` : '');
      }).join('');
    }
  } else if (tab != null) {
    const always = alwaysPrepared(R).filter((x) => x.sp.level === tab || (x.sp.level == null && tab === 1));
    if (always.length && mode !== 'book') cards += always.map((x) => spellCard(x.key, x.sp.level == null ? { ...x.sp, level: tab } : x.sp, { locked: true })).join('');
    if (mode === 'prep') {
      const picks = asList(c.spells);
      const inBook = asList(c.spellbook).filter((k) => spellOf(k)?.level === tab).map((k) => [k, spellOf(k)]).filter(match);
      const sig = R.signature_spells ? asList(c.signature_spells) : [];
      cards += inBook.length ? inBook.map(([k, sp]) => spellCard(k, sp, { act: 'spell', kind: 'spell', on: picks.includes(k), locked: sig.includes(k), lockText: 'Incantesimo personale: sempre preparato' })).join('')
        : `<p class="note">${emblem('scroll', 'i')} Nel libro non hai ancora incantesimi di ${ord(tab)} livello.</p>`;
    } else {
      const kind = mode === 'book' ? 'book' : 'spell';
      const picks = asList(mode === 'book' ? c.spellbook : c.spells);
      const alwaysKeys = alwaysPreparedKeys(R);
      const expanded = new Set(asList(R.spells?.expanded));
      const pool = spellPool(R, tab).filter(match).filter(([k]) => mode === 'book' || !alwaysKeys.has(k));
      const one = ([k, sp], note = '') => spellCard(k, sp, { act: 'spell', kind, on: picks.includes(k), note: note || (mode === 'book' && asList(c.spells).includes(k) ? 'Preparato' : '') });
      const schoolOk = (sp) => !lim.allowed || lim.allowed.includes(norm(SCHOOL_IT[sp.school] || sp.school));
      if (mode !== 'book' && lim.secrets) { // bardo: Segreti Magici da qualsiasi lista
        cards += pool.filter(([k, sp]) => inMain(sp) || expanded.has(k)).map((x) => one(x)).join('');
        const other = pool.filter(([k, sp]) => !inMain(sp) && !expanded.has(k));
        if (other.length) cards += divider('Segreti Magici: incantesimi di altre classi', lim.offList.length, lim.secrets) + other.map((x) => one(x, 'Segreto magico')).join('');
      } else if (mode !== 'book' && lim.allowed) { // Cavaliere Mistico e Mistificatore Arcano: due scuole, poche eccezioni
        cards += pool.filter(([, sp]) => schoolOk(sp)).map((x) => one(x)).join('');
        const other = pool.filter(([, sp]) => !schoolOk(sp));
        if (other.length) cards += divider('Di un\'altra scuola', lim.offSchool.length, lim.anySchool) + other.map((x) => one(x, 'Scuola libera')).join('');
      } else {
        cards += pool.map(([k, sp]) => one([k, sp], expanded.has(k) && !inMain(sp) ? 'Dal tuo patrono' : '')).join('');
      }
    }
  }
  h += `<div class="spells">${cards || '<p class="hint">Nessun incantesimo con queste parole.</p>'}</div>`;
  // mago di alto livello: Maestria negli Incantesimi (18°) e Incantesimi Personali (20°), scelti dal libro
  const inBook = (L) => asList(c.spellbook).filter((k) => spellOf(k)?.level === L);
  const noneYet = (L) => `<p class="hint">Prima metti nel libro un incantesimo di ${ord(L)} livello.</p>`;
  if (R.spell_mastery) {
    const picks = asList(c.spell_mastery);
    h += block('sec-mastery', 'Maestria negli Incantesimi', [1, 2].map((L) => `<p class="label">${ord(L)} livello</p><div class="chips">${inBook(L).map((k) =>
      chip({ act: 'mastery', value: k, on: picks.includes(k), label: spellOf(k).name, k: `mastery-${k}` })).join('') || noneYet(L)}</div>`).join(''),
    { hint: 'Un incantesimo di 1° e uno di 2° livello del tuo libro: li lanci al livello più basso quando vuoi, senza usare slot.' });
  }
  if (R.signature_spells) {
    const picks = asList(c.signature_spells);
    h += block('sec-signature', 'Incantesimi Personali', `<div class="chips">${inBook(3).map((k) =>
      chip({ act: 'signature', value: k, on: picks.includes(k), label: spellOf(k).name, k: `sig-${k}` })).join('') || noneYet(3)}</div>`,
    { count: counter(picks.length, 2), hint: 'Due incantesimi di 3° livello del libro: sempre preparati, e ognuno una volta per riposo senza slot.' });
  }
  return h;
}

/* ------------------------------------------------------------------ passo 8: privilegi e opzioni */
function optionItems(key, opt) {
  const k = clsOf();
  const sc = activeSubclass();
  const ruleItems = (sc?.option_lists?.[key] || k?.option_lists?.[key])?.items;
  if (Array.isArray(opt.items) && opt.items.length) {
    return opt.items.map((ik) => (typeof ik === 'string'
      ? [ik, ruleItems?.[ik] || { name: ik }]
      : [ik.key, { ...(ruleItems?.[ik.key] || {}), ...ik }]));
  }
  if (opt.items && typeof opt.items === 'object' && Object.keys(opt.items).length) return Object.entries(opt.items);
  return Object.entries(ruleItems || {});
}
function renderFeatures() {
  const c = S.char;
  const R = req();
  let h = head(7);
  const k = clsOf(c);
  if (!k) return `${h}<p class="note">${emblem('star', 'i')} Scegli prima la classe.</p>`;
  if (R.fighting_style) {
    const styles = RULES.equipment.fighting_styles || {};
    const opts = (R.fighting_style.options?.length ? R.fighting_style.options : Object.keys(styles))
      .map((o) => (typeof o === 'string' ? o : o?.key)).filter((o) => styles[o]);
    const picks = [c.fighting_style, ...asList(c.fighting_styles)].filter(Boolean);
    h += block('sec-style', 'Stile di combattimento', `<div class="cards">${opts.map((o) => card({ act: 'style', value: o, on: picks.includes(o), em: emblem('fighter'), title: styles[o].name, body: styles[o].text })).join('')}</div>`,
      { count: counter(picks.length, R.fighting_style.count), hint: 'Il tuo modo preferito di combattere: ti dà un piccolo vantaggio sempre attivo.' });
  }
  if (R.maneuvers) {
    const picks = asList(c.maneuvers);
    h += block('sec-maneuvers', 'Manovre', `<div class="cards">${Object.entries(RULES.maneuvers || {}).map(([key, m]) => card({ act: 'maneuver', value: key, on: picks.includes(key), title: m.name, body: kidFmt(m.kid || m.text) })).join('')}</div>`,
      { count: counter(picks.length, R.maneuvers.count), hint: 'Mosse speciali che usi spendendo un dado di superiorità.' });
  }
  for (const [key, opt] of Object.entries(R.class_options || {})) {
    const picks = asList(c.class_options?.[key]).map(optKey);
    let body = `<div class="cards">${optionItems(key, opt).map(([ik, it]) => {
      const on = picks.includes(ik);
      const why = optionBlocked(it, c); // prerequisito non soddisfatto: livello, patto o trucchetto
      const chips = it.cost != null ? [`${it.cost} ${plural(Number(it.cost), 'punto', 'punti')}`] : [];
      if (why) chips.push(cap(why));
      return card({
        act: 'option', value: `${key}|${ik}`, on, title: nm(it, ik), body: kidFmt(it.kid || it.short || it.text || ''),
        chips, k: `opt-${key}-${ik}`, disabled: !!why && !on, cls: why ? 'is-warn' : '',
      });
    }).join('')}</div>`;
    // sotto-scelte delle opzioni prese (Patto del Tomo: 3 trucchetti; Libro dei Segreti Antichi: 2 rituali)
    for (const ik of picks) {
      const it = optionRule(key, ik, c);
      const sub = c.option_picks?.[`${key}|${ik}`] || {};
      for (const [kind, p] of Object.entries(optionSubPools(it, c))) {
        const chosen = asList(kind === 'cantrip' ? sub.cantrips : sub.spells);
        const what = kind === 'cantrip' ? plural(p.count, 'trucchetto', 'trucchetti') : plural(p.count, p.ritual ? 'rituale' : 'incantesimo', p.ritual ? 'rituali' : 'incantesimi');
        body += `<div class="sub-choice"><p class="label">${esc(nm(it, ik))}: scegli ${p.count} ${what} ${counter(chosen.length, p.count)}</p>
          <div class="chips">${p.pool.map(([sk, sp]) => chip({ act: 'opt-sub', value: `${key}|${ik}|${kind}|${sk}`, on: chosen.includes(sk), label: sp.name,
            sub: sp.level ? ord(sp.level) : '', title: spellFmt(sp, sp.kid || sp.text) })).join('') || '<p class="hint">Nessun incantesimo adatto.</p>'}</div></div>`;
      }
    }
    h += block(`sec-opt-${key}`, esc(opt.label || key), body, { count: counter(picks.length, opt.count) });
  }
  if (R.companion) {
    const opts = companionOptions(R.companion);
    const ex = asList(R.companion.examples);
    h += block('sec-companion', 'Il tuo compagno animale', `<div class="cards cards-sm">${opts.map(([bk, b]) => card({
      act: 'companion', value: bk, on: c.companion === bk, em: emblem('ranger'), title: b.name,
      meta: `GS ${crText(b.cr)} · ${b.size || ''}`, chips: ex.includes(bk) ? ['consigliato'] : [], body: kidFmt(b.kid || b.traits || ''), k: `comp-${bk}`,
    })).join('')}</div>`, {
      count: counter(c.companion ? 1 : 0, 1),
      hint: `Una bestia di taglia ${String(R.companion.max_size || 'Media').toLowerCase()} o più piccola, con grado di sfida ${crText(R.companion.max_cr ?? 0.25)} o meno: viaggia e combatte con te.`,
    });
  }
  if (!R.fighting_style && !R.maneuvers && !Object.keys(R.class_options || {}).length && !R.companion) {
    h += `<p class="note">${emblem('check', 'i')} A questo livello non ci sono opzioni da scegliere: leggi qui sotto cosa sa fare il tuo eroe.</p>`;
  }
  // linea del tempo dei privilegi
  const lvl = c.level || 1;
  const all = [];
  for (const [L, fs] of Object.entries(k.features || {})) for (const f of fs || []) all.push({ ...f, level: +L, source: nm(k) });
  const sc = subclassOf(c);
  if (sc) for (const [L, fs] of Object.entries(sc.features || {})) for (const f of fs || []) all.push({ ...f, level: +L, source: nm(sc), sub: true });
  all.sort((a, b) => a.level - b.level);
  const byLevel = {};
  for (const f of all) (byLevel[f.level] = byLevel[f.level] || []).push(f);
  const now = Object.keys(byLevel).map(Number).filter((L) => L <= lvl);
  const later = Object.keys(byLevel).map(Number).filter((L) => L > lvl);
  h += block('sec-timeline', 'I privilegi livello per livello', `<ol class="timeline">${now.map((L) => `<li><span class="tl-lvl">${ord(L)}</span><div class="tl-items">${byLevel[L].map((f) =>
    `<div class="tl-item ${f.sub ? 'is-sub' : ''}"><strong>${esc(nm(f))}</strong>${f.sub ? `<span class="tag">${esc(f.source)}</span>` : ''}<p>${esc(textOf(f))}</p></div>`).join('')}</div></li>`).join('')}</ol>
    ${later.length ? `<details class="later"><summary>Cosa imparerai più avanti</summary><ol class="timeline dim">${later.map((L) => `<li><span class="tl-lvl">${ord(L)}</span><div class="tl-items"><p>${byLevel[L].map((f) => esc(nm(f))).join(' · ')}</p></div></li>`).join('')}</ol></details>` : ''}`, { cls: 'lore' });
  return h;
}

/* ------------------------------------------------------------------ passo 9: equipaggiamento */
function profCats(c = S.char) {
  const k = clsOf(c);
  const armor = new Set(k?.armor || []);
  const weapons = new Set(k?.weapons || []);
  for (const f of levelFeatures(c)) { (f.bonus_proficiencies?.armor || []).forEach((a) => armor.add(a)); (f.bonus_proficiencies?.weapons || []).forEach((w) => weapons.add(w)); }
  for (const t of raceTraits(c)) { (t.armor_proficiencies || []).forEach((a) => armor.add(a)); (t.weapon_proficiencies || []).forEach((w) => weapons.add(w)); }
  for (const f of baseChar().feats || []) {
    const pick = typeof f === 'string' ? { key: f } : f;
    const feat = RULES.feats?.[pick.key];
    (feat?.armor_proficiencies || []).forEach((a) => armor.add(a));
    if (Array.isArray(feat?.weapon_proficiencies)) feat.weapon_proficiencies.forEach((w) => weapons.add(w));
    asList(pick.weapons).forEach((w) => weapons.add(w));
  }
  return { armor, weapons };
}
function currentMods() {
  const sc = computeScores(baseChar());
  return Object.fromEntries(ABIL.map((a) => [a, sc[a].mod]));
}
function styleList(c = S.char) { return [c.fighting_style, ...asList(c.fighting_styles)].filter(Boolean); }
function acFor(armorKey, shield) {
  const c = S.char;
  const m = currentMods();
  const table = RULES.equipment.armor;
  let ac;
  if (armorKey && table[armorKey]) {
    const a = table[armorKey];
    ac = a.base + (a.dex === 'full' ? m.dex : a.dex === 'max2' ? Math.min(m.dex, 2) : 0);
    if (styleList(c).includes('defense')) ac += 1;
  } else {
    ac = 10 + m.dex;
    if (c.class === 'barbarian') ac += m.con;
    else if (c.class === 'monk' && !shield) ac += m.wis;
    else for (const f of levelFeatures(c)) if (f.unarmored_ac) ac = Math.max(ac, f.unarmored_ac.base + m[f.unarmored_ac.ability || 'dex']);
  }
  if (shield) ac += table.shield?.bonus || 2;
  return ac;
}
function weaponCalc(key) {
  const w = RULES.equipment.weapons[key];
  const m = currentMods();
  const pb = RULES.skills.proficiency_bonus[(S.char.level || 1) - 1];
  const props = w.properties || [];
  const ranged = w.type === 'ranged';
  const ab = props.includes('finesse') ? (m.dex >= m.str ? 'dex' : 'str') : ranged ? 'dex' : 'str';
  const { weapons } = profCats();
  const prof = weapons.has(w.category) || weapons.has(key);
  let atk = m[ab] + (prof ? pb : 0);
  const styles = styleList();
  if (ranged && styles.includes('archery')) atk += 2;
  let dm = m[ab];
  if (!ranged && styles.includes('dueling') && !props.includes('two_handed')) dm += 2;
  const dice = String(w.damage || '');
  const dmg = /^\d/.test(dice) && dice.includes('d') ? `${dice}${dm ? fmtMod(dm) : ''}` : dice;
  return { atk, dmg: `${dmg} ${w.damage_type || ''}`.trim(), prof };
}
const PROPS_IT = { finesse: 'accurata', light: 'leggera', heavy: 'pesante', two_handed: 'a due mani', versatile: 'versatile', thrown: 'da lancio', ammunition: 'munizioni', reach: 'portata', loading: 'ricarica', special: 'speciale' };
function renderEquipment() {
  const c = S.char;
  let h = head(8);
  if (!clsOf(c)) return `${h}<p class="note">${emblem('star', 'i')} Scegli prima la classe.</p>`;
  const { armor: aprof } = profCats();
  const table = RULES.equipment.armor;
  const { s } = sheet();
  const fresh = PREVIEW && PREVIEW.ok && PREVIEW.key === CUR_KEY;
  const acNow = fresh && s?.ac?.value != null ? s.ac.value : acFor(c.armor, !!c.shield);
  const catName = { light: 'leggera', medium: 'media', heavy: 'pesante' };
  const armorCards = [['', null], ...Object.entries(table).filter(([, a]) => a.category !== 'shield')].map(([key, a]) => {
    if (!a) return card({ act: 'armor', value: '', on: !c.armor, em: emblem('tunic'), title: 'Nessuna armatura', meta: `CA ${acFor(null, !!c.shield)}`, body: 'Più leggeri e silenziosi.', k: 'armor-none' });
    const prof = aprof.has(a.category);
    const chips = [cap(catName[a.category] || a.category)];
    if (a.stealth_disadvantage) chips.push('rumorosa');
    if (a.str_req) chips.push(`serve FOR ${a.str_req}`);
    if (a.metal && clsOf(c)?.no_metal_armor) chips.push('di metallo: i druidi non la indossano');
    if (!prof) chips.push('non sai usarla');
    return card({ act: 'armor', value: key, on: c.armor === key, em: emblem('cuirass'), title: a.name, meta: `CA ${acFor(key, !!c.shield)} · ${a.weight} kg · ${a.cost}`, chips, cls: !prof || (a.metal && clsOf(c)?.no_metal_armor) ? 'is-warn' : '' });
  }).join('');
  h += block('sec-armor', 'Armatura', `<div class="ac-big" aria-live="polite">${emblem('paladin', 'emblem')}<span class="ac-num">${acNow}</span><span class="ac-cap">Classe Armatura</span></div>
    <div class="cards cards-sm">${armorCards}</div>
    <button type="button" class="switch" role="switch" aria-checked="${!!c.shield}" data-act="shield" data-k="shield">
      <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
      <span class="switch-text"><b>Scudo (+2 CA)</b><small>${aprof.has('shields') ? 'Lo tieni in una mano.' : 'Attenzione: la tua classe non sa usare lo scudo.'}</small></span></button>`,
  { hint: 'Le armature che la tua classe non sa usare sono segnate: meglio evitarle.' });
  const picks = asList(c.weapons).map((w) => (typeof w === 'string' ? w : w.key));
  const groups = [['simple', 'melee', 'Armi semplici da mischia'], ['simple', 'ranged', 'Armi semplici a distanza'], ['martial', 'melee', 'Armi da guerra da mischia'], ['martial', 'ranged', 'Armi da guerra a distanza']];
  const freshW = fresh ? Object.fromEntries((s.weapons || []).map((w) => [w.key, w])) : {};
  const wl = groups.map(([cat, type, title]) => {
    const items = Object.entries(RULES.equipment.weapons).filter(([, w]) => w.category === cat && w.type === type);
    if (!items.length) return '';
    return `<h4 class="group-title">${title}</h4><div class="weapon-list">${items.map(([key, w]) => {
      const calc = weaponCalc(key);
      const pw = freshW[key];
      const atk = pw ? pw.attack_str : fmtMod(calc.atk);
      const dmg = pw ? pw.damage : calc.dmg;
      const props = (w.properties || []).map((p) => PROPS_IT[p] || p).concat(w.range ? [`gittata ${w.range} m`] : []);
      return `<button type="button" class="weapon ${picks.includes(key) ? '' : ''} ${calc.prof ? '' : 'no-prof'}" data-act="weapon" data-value="${key}" data-k="weapon-${key}" aria-pressed="${picks.includes(key)}">
        <span class="w-check" aria-hidden="true">${emblem('check', 'i')}</span><span class="w-name">${esc(w.name)}</span>
        <span class="w-atk" title="Tiro per colpire">${esc(atk)}</span><span class="w-dmg">${esc(dmg)}</span>
        <span class="w-props">${esc(props.join(', '))}${calc.prof ? '' : ' · senza competenza'}</span></button>`;
    }).join('')}</div>`;
  }).join('');
  h += block('sec-weapons', 'Armi', `<p class="hint small">Il primo numero è quanto aggiungi al d20 per colpire, poi i danni.</p>${wl}`, { count: `<span class="counter">${picks.length} ${plural(picks.length, 'scelta', 'scelte')}</span>` });
  // dotazioni
  const packs = RULES.equipment.packs || {};
  const eq = asList(c.equipment);
  const curPack = eq.find((e) => e && typeof e === 'object' && e.pack)?.pack || '';
  h += block('sec-pack', 'Zaino (dotazione)', `<div class="cards cards-sm">${[['', { name: 'Nessuna dotazione', items: [] }], ...Object.entries(packs)].map(([key, p]) =>
    card({ act: 'pack', value: key, on: curPack === key, title: p.name, body: (p.items || []).join(', ') || 'Scrivi tu cosa porti nello zaino.', k: `pack-${key || 'none'}` })).join('')}</div>`,
  { hint: 'Un pacchetto già pronto con le cose utili per viaggiare.' });
  const items = eq.map((e, i) => [e, i]).filter(([e]) => typeof e === 'string');
  const k = clsOf(c);
  const sugg = (k?.starting_equipment || []).map((x) => (x && x.choice ? x.choice.join(' oppure ') : typeof x === 'string' ? x : '')).filter(Boolean);
  h += block('sec-items', 'Altri oggetti', `<ul class="items">${items.map(([e, i]) => `<li><span>${esc(e)}</span><button type="button" class="btn ghost small" data-act="item-remove" data-value="${i}" data-k="item-rm-${i}" aria-label="Togli ${esc(e)}">Togli</button></li>`).join('') || '<li class="empty">Nessun oggetto in più, per ora.</li>'}</ul>
    <div class="add-row"><label class="sr-only" for="item-new">Nuovo oggetto</label><input id="item-new" data-k="item-new" placeholder="Es. Focus druidico (ramo di vischio)" autocomplete="off">
    <button type="button" class="btn ghost" data-act="item-add">Aggiungi</button></div>
    ${sugg.length ? `<details class="sugg"><summary>Cosa suggerisce il manuale per ${esc(nm(k))}</summary><ul>${sugg.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></details>` : ''}`);
  const bg = bgOf(c);
  if (bg) {
    h += block('sec-bgequip', `Equipaggiamento del background (${esc(nm(bg))})`, `<button type="button" class="switch" role="switch" aria-checked="${c.include_background_equipment !== false}" data-act="bg-equip" data-k="bg-equip">
      <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
      <span class="switch-text"><b>Aggiungilo alla scheda</b><small>${esc((bg.equipment || []).join(', ') || '—')}</small></span></button>`);
  }
  h += block('sec-money', 'Monete', `<div class="money">${MONEY.map(([key, abbr, label]) => `<div class="field coin coin-${key}"><label for="money-${key}"><b>${abbr}</b> ${label}</label>
      <input id="money-${key}" type="number" min="0" inputmode="numeric" data-bind="money.${key}" data-num value="${Number(c.money?.[key] || 0)}"></div>`).join('')}</div>
    ${bg?.gold ? `<button type="button" class="btn ghost small" data-act="bg-gold">Metti le ${bg.gold} monete d'oro del background</button>` : ''}`,
  { hint: '1 moneta d\'oro (mo) = 10 d\'argento (ma) = 100 di rame (mr).' });
  return h;
}

/* ------------------------------------------------------------------ passo 10: storia */
function renderStory() {
  const c = S.char;
  let h = head(9);
  const al = RULES.skills.alignments || {};
  h += block('sec-alignment', 'Allineamento', `<div class="align-grid" role="group" aria-label="Allineamento">${ALIGN_ORDER.map((k) =>
    `<button type="button" class="align" data-act="align" data-value="${k}" data-k="align-${k}" aria-pressed="${c.alignment === k}"><b>${esc(al[k] || k)}</b><small>${esc(ALIGN_HINT[k])}</small></button>`).join('')}</div>`,
  { hint: 'Il modo di pensare del tuo eroe: rispetta le regole o la libertà? È buono o egoista?' });
  h += block('sec-personality', 'Carattere', `<div class="grid-2">
    ${field('Tratti caratteriali', 'personality.traits', { area: true, placeholder: 'Es. Osservo molto e parlo poco.' })}
    ${field('Ideali', 'personality.ideals', { area: true, placeholder: 'Es. Libertà: nessuno mi dirà dove andare.' })}
    ${field('Legami', 'personality.bonds', { area: true, placeholder: 'Es. Devo ritrovare i miei genitori.' })}
    ${field('Difetti', 'personality.flaws', { area: true, placeholder: 'Es. Non mi fido di nessuno.' })}</div>`);
  h += block('sec-appearance', 'Aspetto', `<div class="grid-3">
    ${field('Età', 'appearance.age', { placeholder: 'Es. 21' })}
    ${field('Altezza', 'appearance.height', { placeholder: 'Es. 1,75 m' })}
    ${field('Peso', 'appearance.weight', { placeholder: 'Es. 60 kg' })}
    ${field('Occhi', 'appearance.eyes', { placeholder: 'Es. Verdi' })}
    ${field('Pelle', 'appearance.skin', { placeholder: 'Es. Chiara, con lentiggini' })}
    ${field('Capelli', 'appearance.hair', { placeholder: 'Es. Ramati e lunghi' })}</div>`);
  h += block('sec-story', 'Storia', `${field('Alleati e organizzazioni', 'allies', { area: true, rows: 3, placeholder: 'Amici, famiglia, gilde…' })}
    ${field('Tesoro', 'treasure', { area: true, rows: 2, placeholder: 'Oggetti preziosi o ricordi speciali' })}
    ${field('La storia del personaggio', 'backstory', { area: true, rows: 9, placeholder: 'Da dove viene? Cosa cerca? Perché è partito all\'avventura?' })}`);
  return h;
}

/* ------------------------------------------------------------------ passo 11: riepilogo */
/* Nomi dei campi del file del personaggio, come li capisce chi gioca. */
const FIELD_IT = {
  draconic_ancestry: 'il colore del drago', circle_terrain: 'il terreno del circolo', racial_cantrips: 'il trucchetto della razza',
  spell_mastery: 'Maestria negli Incantesimi', signature_spells: 'Incantesimi Personali', companion: 'il compagno animale',
};
/* Chiavi delle regole (inglesi) -> nomi italiani: razze, sottorazze, colori del drago, classi, terreni, incantesimi... */
function keyNames() {
  const d = {};
  const add = (k, v) => { if (k && v && !(k in d)) d[k] = v; };
  for (const [k, r] of Object.entries(RULES.races || {})) {
    add(k, nm(r));
    for (const [sk, s] of Object.entries({ ...(r.subraces || {}), ...(r.variants || {}) })) add(sk, nm(s));
    for (const [ak, a] of Object.entries(r.ancestry || {})) add(ak, a.name);
  }
  for (const [k, cl] of Object.entries(RULES.classes || {})) {
    add(k, nm(cl));
    for (const [sk, s] of Object.entries(cl.subclasses || {})) add(sk, nm(s));
  }
  for (const [k, t] of Object.entries(TERRAINS)) add(k, t);
  for (const [k, b] of Object.entries(RULES.backgrounds || {})) add(k, nm(b));
  for (const [k, s] of Object.entries(RULES.skills?.skills || {})) add(k, s.it);
  for (const [k, l] of Object.entries(RULES.skills?.languages || {})) add(k, l);
  for (const [k, sp] of Object.entries(RULES.spells?.spells || {})) add(k, sp.name);
  for (const [k, f] of Object.entries(RULES.feats || {})) add(k, f.name);
  for (const [k, mv] of Object.entries(RULES.maneuvers || {})) add(k, mv.name);
  for (const [k, b] of Object.entries(RULES.beasts || {})) add(k, b.name);
  for (const [k, w] of Object.entries(RULES.equipment?.weapons || {})) add(k, w.name);
  for (const [k, a] of Object.entries(RULES.equipment?.armor || {})) add(k, a.name);
  for (const [k, s] of Object.entries(RULES.equipment?.fighting_styles || {})) add(k, s.name);
  // niente chiavi delle caratteristiche ("con") né chiavi che sono anche parole italiane
  for (const w of ['ape', 'mobile', 'medicine', 'lance', 'nature', 'haste', 'net']) delete d[w];
  return d;
}
function humanize(msg) {
  // via i nomi tecnici dei campi; le chiavi delle regole diventano i nomi italiani
  const names = RULES ? keyNames() : {};
  return String(msg || '').replace(/ in '[^']*'/g, '').replace(/\s*\('[^']*'\)/g, '')
    .replace(/'([a-z_:\s]+)'/g, (m, k) => (FIELD_IT[k] ?? names[k] ?? ''))
    .replace(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)*\b/g, (w) => names[w] ?? w)
    .replace(/\(dat[eio]: (\d+)\)/g, '(ne hai scelte $1)')
    .replace(/ {2,}/g, ' ').replace(/ ([:.,])/g, '$1').trim();
}
function stepForError(msg) {
  const m = norm(msg);
  // il talento della razza (umano variante) si sceglie al passo Razza, gli altri a Caratteristiche
  const raceFeat = S.raceFeat?.key && RULES.feats?.[S.raceFeat.key];
  if (raceFeat && /talento/.test(m) && m.includes(norm(raceFeat.name))) return stepIndex('race');
  const map = [
    [/non e nella lista|non e un trucchetto|slot solo fino|fuori scuola|segreti magici/, 'magic'],
    [/competenza\/e in strumenti|linguaggi extra/, 'skills'],
    [/maestria negli incantesimi|incantesimi personali|spell_mastery|signature_spells/, 'magic'],
    [/compagno|companion|supplic|patto del|metamagia/, 'features'],
    [/racial|sottorazza|razza|draconic|tratto/, 'race'], [/circle_terrain/, 'class'], [/trucchett|incantesim|libro/, 'magic'],
    [/abilita|skills|maestria/, 'skills'], [/archetipo|subclass|livello deve|classe sconosciuta|richiede un|tradizione|dominio|giuramento|patrono|collegio|origine|cammino/, 'class'],
    [/background/, 'background'], [/point buy|array|caratteristic|punteggio|talento/, 'abilities'], [/stile|manovra|opzione|class_options/, 'features'],
    [/arma|armatura/, 'equipment'],
  ];
  for (const [re, id] of map) if (re.test(m)) return stepIndex(id);
  return -1;
}
function allMissing() {
  const out = [];
  STEPS.forEach((st, i) => { if (st.id !== 'summary' && applicable(i)) for (const x of missingFor(st.id)) out.push({ ...x, step: i }); });
  return out;
}
function renderSummary() {
  const c = S.char;
  let h = head(10);
  const p = PREVIEW;
  const fresh = p && p.key === CUR_KEY;
  const blocked = p && !p.ok;
  const miss = allMissing().filter((x) => !(blocked && x.engine)); // l'errore del programma è già nel riquadro rosso
  if (!c.race || !c.class || !c.background) {
    h += `<div class="alert">${emblem('star', 'i')}<div><b>Mancano ancora le scelte principali.</b><p>Per creare la scheda servono almeno razza, classe e background.</p></div></div>`;
  } else if (!p) {
    h += '<p class="note">Sto calcolando la scheda…</p>';
  } else if (blocked) {
    const si = stepForError(p.error);
    h += `<div class="alert alert-error" role="alert">${emblem('star', 'i')}<div><b>La scheda non si può ancora creare</b><p>${esc(humanize(p.error))}</p>
      ${si >= 0 ? `<button type="button" class="btn gold small" data-act="go" data-value="${si}">Vai al passo ${esc(STEPS[si].title)}</button>` : ''}</div></div>`;
  }
  if (miss.length) {
    h += block('sec-todo', 'Ancora da completare', `<ul class="todo-list">${miss.map((x) =>
      `<li><span>${esc(x.text)}</span><button type="button" class="btn ghost small" data-act="goto-anchor" data-value="${x.step}|${x.anchor || ''}">${esc(STEPS[x.step].short || STEPS[x.step].title)}</button></li>`).join('')}</ul>`,
    { hint: blocked ? '' : 'Puoi creare la scheda anche adesso: queste cose resteranno vuote o da sistemare.' });
  }
  const s = p && p.ok ? p.sheet : null;
  if (s) h += summarySheet(s);
  const warnings = (p && p.warnings) || [];
  if (warnings.length) {
    h += block('sec-warn', 'Da controllare', `<ul class="warn-list">${warnings.map((w) => `<li>${esc(humanize(w))}</li>`).join('')}</ul>`, { hint: 'Avvisi delle regole: la scheda si crea lo stesso.' });
  }
  const canBuild = canBuildNow();
  const b = S.built;
  const stale = b && b.ok && b.key !== CUR_KEY;
  h += `<div class="forge" id="sec-build" tabindex="-1">
    <button type="button" class="btn forge-btn" data-act="build" ${canBuild ? '' : 'disabled'}>${BUILDING ? '<span class="spinner" aria-hidden="true"></span> Sto scrivendo la scheda…' : `${emblem('scroll', 'i')} Genera la scheda PDF`}</button>
    ${!(c.name || '').trim() ? '<p class="hint">Scrivi il nome del personaggio al passo Inizio.</p>' : ''}
    ${!fresh && p ? '<p class="hint small">Aggiorno l\'anteprima…</p>' : ''}
  </div>`;
  if (b) {
    if (b.ok) {
      const stem = b.stem || slug(c.name) || 'scheda';
      h += `<section class="block result" id="sec-result" tabindex="-1">
        <div class="block-head"><h3>La scheda di ${esc(c.name || 'eroe')} è pronta</h3></div>
        ${stale ? '<p class="alert">Hai cambiato qualcosa dopo l\'ultimo PDF: premi di nuovo «Genera la scheda PDF» per aggiornarlo.</p>' : ''}
        <div class="downloads">
          <a class="btn gold" href="${esc(b.pdf_url)}" download="${esc(stem)}.pdf">Scarica la scheda</a>
          ${b.guide_url ? `<a class="btn ghost" href="${esc(b.guide_url)}" download="${esc(stem)}_guida.pdf">Scarica la guida</a>` : ''}
          <a class="btn ghost" href="${esc(b.pdf_url)}" target="_blank" rel="noopener">Apri per stampare</a>
          ${b.md_url ? `<a class="btn ghost small" href="${esc(b.md_url)}" target="_blank" rel="noopener">Riepilogo di testo</a>` : ''}
        </div>
        ${(b.warnings || []).length ? `<ul class="warn-list">${b.warnings.map((w) => `<li>${esc(humanize(w))}</li>`).join('')}</ul>` : ''}
        <iframe class="pdf" title="Anteprima della scheda PDF" src="${esc(b.pdf_url)}"></iframe>
      </section>`;
    } else {
      h += `<div class="alert alert-error" role="alert" id="sec-result" tabindex="-1">${emblem('star', 'i')}<div><b>Il PDF non è stato creato</b><p>${esc(humanize(b.error))}</p></div></div>`;
    }
  }
  return h;
}
function canBuildNow() {
  const c = S.char;
  return !!(c.race && c.class && c.background && PREVIEW && PREVIEW.ok && !BUILDING && (c.name || '').trim());
}
function summarySheet(s) {
  const c = S.char;
  const ab = ABIL.map((a) => {
    const sc = sheetScore(s, a) || { total: '—', mod: 0 };
    const sv = s.saves?.[a];
    return `<div class="medal"><span class="m-abbr">${ABBR[a]}</span><span class="m-score">${sc.total}</span><span class="m-mod">${fmtMod(sc.mod)}</span>
      ${sv ? `<span class="m-save ${sv.proficient ? 'prof' : ''}">TS ${fmtMod(sv.value)}</span>` : ''}</div>`;
  }).join('');
  const stats = [
    ['CA', s.ac?.value], ['Punti ferita', s.hp?.max], ['Iniziativa', s.initiative != null ? fmtMod(s.initiative) : null],
    ['Velocità', s.speed_m], ['Competenza', s.proficiency_bonus != null ? fmtMod(s.proficiency_bonus) : null], ['Percezione passiva', s.passive_perception],
  ].filter(([, v]) => v != null && v !== '');
  const attacks = (s.weapons || []).map((w) => `<li><b>${esc(w.name)}</b><span>${esc(w.attack_str)}</span><span>${esc(w.damage)}</span></li>`);
  const sp = s.spellcasting;
  for (const at of sp?.spell_attacks || []) attacks.push(`<li><b>${esc(at.name)}</b><span>${esc(at.attack_str)}</span><span>${esc(at.damage)}</span></li>`);
  let spells = '';
  if (sp) {
    const lines = [];
    if ((sp.cantrips || []).length) lines.push(`<li><b>Trucchetti</b><span>${sp.cantrips.map((x) => esc(x.name)).join(', ')}</span></li>`);
    for (const [L, list] of Object.entries(sp.spells_by_level || {}).sort((a, b) => a[0] - b[0])) {
      lines.push(`<li><b>${ord(L)} livello${sp.slots?.[L] ? ` · ${sp.slots[L]} slot` : ''}</b><span>${list.map((x) => `${esc(x.name)}${x.always_prepared ? ' ★' : ''}${x.prepared === false ? ' (nel libro)' : ''}`).join(', ')}</span></li>`);
    }
    spells = `<div class="sum-sec"><h4>Magia</h4><p class="sum-line">CD ${sp.save_dc ?? '—'} · attacco ${sp.attack_bonus != null ? fmtMod(sp.attack_bonus) : '—'}</p><ul class="sum-list">${lines.join('')}</ul></div>`;
  }
  const feats = (s.features || []).filter((f) => !(c.simple && f.kid_hide)).map((f) => `<li><b>${esc(f.name)}</b><span>${esc(kidFmt(c.simple ? (f.kid || f.short) : (f.short || f.kid)))}</span></li>`).join('');
  const k = clsOf(c);
  const race = raceOf(c);
  return `<article class="parchment sum" aria-label="Riepilogo della scheda">
    <header class="sum-head">
      ${portraitHTML('sum-portrait')}
      <div><h3 class="sum-name">${esc(c.name || 'Senza nome')}</h3>
      <p class="sum-sub">${esc([race ? nm(subOf(c) || race) : '', k ? `${nm(k)} ${c.level}` : '', activeSubclass(c) ? nm(activeSubclass(c)) : ''].filter(Boolean).join(' · '))}</p>
      <p class="sum-sub small">${esc([bgOf(c) ? nm(bgOf(c)) : '', RULES.skills.alignments?.[c.alignment] || '', c.player ? `gioca ${c.player}` : ''].filter(Boolean).join(' · '))}</p></div>
    </header>
    <div class="medals">${ab}</div>
    <dl class="sum-stats">${stats.map(([l, v]) => `<div><dt>${l}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>
    ${attacks.length ? `<div class="sum-sec"><h4>Attacchi</h4><ul class="sum-list atk">${attacks.join('')}</ul></div>` : ''}
    ${spells}
    ${s.breath ? `<div class="sum-sec"><h4>Soffio</h4><p class="sum-line">${esc(s.breath.area)}, ${esc(s.breath.dice)} ${esc(s.breath.type)}, TS ${esc(s.breath.save_name || '')} CD ${esc(s.breath.dc)}</p></div>` : ''}
    ${feats ? `<div class="sum-sec"><h4>Privilegi e tratti</h4><ul class="sum-list feats">${feats}</ul></div>` : ''}
  </article>`;
}

/* ------------------------------------------------------------------ cornice: costellazione, pergamena, barra in basso */
let CUR_KEY = '';
let DEFERRED = false;
const RENDER = {
  start: renderStart, race: renderRace, class: renderClass, background: renderBackground, abilities: renderAbilities,
  skills: renderSkills, magic: renderMagic, features: renderFeatures, equipment: renderEquipment, story: renderStory, summary: renderSummary,
};

function renderStepper() {
  const box = $('#stepper');
  if (!box) return;
  box.innerHTML = STEPS.map((st, i) => {
    const app = applicable(i);
    const visited = S.visited.includes(i);
    const miss = app && st.id !== 'summary' ? missingFor(st.id).length : 0;
    let state = 'is-new';
    if (!app) state = 'is-off';
    else if (visited) state = miss ? 'is-todo' : 'is-done';
    const lit = `${i > 0 && S.visited.includes(i - 1) ? 'lit' : ''} ${S.visited.includes(i) ? 'lit-out' : ''}`;
    let label = `Passo ${i + 1}: ${st.title}`;
    if (!app) label += ' (non serve)';
    else if (visited && miss) label += `, ${miss} ${plural(miss, 'cosa', 'cose')} da scegliere`;
    else if (visited) label += ', fatto';
    return `<li class="st ${state} ${i === S.step ? 'is-current' : ''} ${lit}"><button type="button" data-act="go" data-value="${i}" data-k="st-${i}" aria-label="${esc(label)}" ${i === S.step ? 'aria-current="step"' : ''}>
      <span class="st-star" aria-hidden="true">${emblem('star', 'i')}</span><span class="st-label">${esc(st.short || st.title)}</span></button></li>`;
  }).join('');
  const cur = box.querySelector('.is-current');
  if (cur && box.scrollWidth > box.clientWidth) {
    const left = cur.offsetLeft - box.clientWidth / 2 + cur.clientWidth / 2;
    box.scrollTo({ left, behavior: 'auto' });
  }
}
function portraitHTML(cls) {
  const c = S.char;
  const src = S.thumb || (c.portrait ? `/portraits/${encodeURI(c.portrait)}` : '');
  const fallback = emblem(c.class || c.race || 'd20', 'emblem');
  return `<div class="${cls}">${fallback}${src ? `<img src="${esc(src)}" alt="" onerror="this.remove()">` : ''}</div>`;
}
function renderAside() {
  const el = $('#hero-body');
  if (!el) return;
  const c = S.char;
  const scores = computeScores(baseChar());
  const { s, provisional } = sheet();
  const race = raceOf(c);
  const k = clsOf(c);
  const sc = activeSubclass(c);
  const bg = bgOf(c);
  const blank = '<span class="blank">da scegliere</span>';
  const line1 = [race ? esc(nm(subOf(c) || race)) : '', k ? `${esc(nm(k))} ${c.level || 1}` : ''].filter(Boolean).join(' · ');
  const line2 = [sc ? nm(sc) : '', bg ? nm(bg) : '', c.alignment ? RULES.skills.alignments?.[c.alignment] : ''].filter(Boolean).map(esc).join(' · ');
  const medals = ABIL.map((a) => {
    const v = scores[a];
    const has = v.base != null && v.base !== '';
    return `<div class="h-ab"><span>${ABBR[a]}</span><b>${has ? v.total : '–'}</b><i>${has ? fmtMod(v.mod) : ''}</i></div>`;
  }).join('');
  const stats = [
    ['CA', s?.ac?.value ?? '–'], ['PF', s?.hp?.max ?? '–'],
    ['Iniziativa', s?.initiative != null ? fmtMod(s.initiative) : '–'], ['Velocità', s?.speed_m || (race ? feet2m(raceSpeed(c)) : '–')],
  ];
  let magic = '';
  const sp = s?.spellcasting;
  if (sp) {
    const nC = (sp.cantrips || []).length;
    const nS = Object.values(sp.spells_by_level || {}).reduce((a, l) => a + l.length, 0);
    magic = `<p class="h-magic">${emblem('sorcerer', 'i')} ${nC} ${plural(nC, 'trucchetto', 'trucchetti')} · ${nS} ${plural(nS, 'incantesimo', 'incantesimi')} · CD ${sp.save_dc}</p>`;
  }
  const miss = allMissing().length;
  el.innerHTML = `
    ${portraitHTML('h-portrait')}
    <h2 class="h-name">${c.name ? esc(c.name) : '<span class="blank">Senza nome</span>'}</h2>
    <p class="h-line">${line1 || blank}</p>
    ${line2 ? `<p class="h-line small">${line2}</p>` : ''}
    <div class="h-abs">${medals}</div>
    <dl class="h-stats">${stats.map(([l, v]) => `<div><dt>${l}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>
    ${magic}
    <p class="h-note">${OFFLINE ? 'Il programma non risponde.' : !s ? (c.race && c.class ? 'Qualcosa va sistemato: guarda il passo Riepilogo.' : 'Scegli razza e classe per vedere i numeri.') : provisional ? 'Anteprima provvisoria: mancano ancora delle scelte.' : 'Numeri calcolati con le regole ufficiali.'}</p>
    ${miss ? `<p class="h-miss">${miss} ${plural(miss, 'cosa', 'cose')} ancora da scegliere</p>` : (s && !provisional ? '<p class="h-ok">Tutto pronto per il PDF</p>' : '')}`;
  const tg = $('#hero-toggle-count');
  if (tg) tg.textContent = miss ? String(miss) : '';
}
function renderFooter() {
  const box = $('#footer');
  if (!box) return;
  const i = S.step;
  const st = STEPS[i];
  const miss = st.id === 'summary' || !applicable(i) ? [] : missingFor(st.id);
  let next = i + 1;
  while (next < STEPS.length && !applicable(next)) next++;
  let prev = i - 1;
  while (prev >= 0 && !applicable(prev)) prev--;
  let todo = '';
  if (miss.length) {
    todo = `<button type="button" class="todo-btn" data-act="goto-anchor" data-value="${i}|${esc(miss[0].anchor || '')}" data-k="todo"><span class="todo-dot" aria-hidden="true"></span><span>${esc(miss[0].text)}${miss.length > 1 ? ` <small>e ${plural(miss.length - 1, 'un\'altra cosa', `altre ${miss.length - 1} cose`)}</small>` : ''}</span></button>`;
  } else if (st.id !== 'summary') {
    todo = `<span class="todo-ok">${emblem('check', 'i')} Tutto scelto</span>`;
  }
  box.innerHTML = `
    <button type="button" class="btn ghost nav-btn" data-act="prev" data-k="nav-prev" ${prev < 0 ? 'disabled' : ''}><span aria-hidden="true">←</span><span class="hide-sm">Indietro</span><span class="sr-only">Passo precedente</span></button>
    <div class="todo" aria-live="polite">${todo}</div>
    ${next < STEPS.length
    ? `<button type="button" class="btn gold nav-btn" data-act="next" data-k="nav-next"><span>Avanti<span class="hide-sm">: ${esc(STEPS[next].short || STEPS[next].title)}</span></span> <span aria-hidden="true">→</span></button>`
    : `<button type="button" class="btn gold nav-btn" data-act="build" data-k="nav-build" ${canBuildNow() ? '' : 'disabled'}>${BUILDING ? '<span class="spinner" aria-hidden="true"></span> Un momento…' : `${emblem('scroll', 'i')} <span>Genera il PDF</span>`}</button>`}`;
}
function captureFocus() {
  const a = document.activeElement;
  if (!a || a === document.body) return null;
  const key = a.dataset?.k || a.dataset?.bind || a.id;
  if (!key) return null;
  let sel = null;
  try { if (typeof a.selectionStart === 'number') sel = [a.selectionStart, a.selectionEnd]; } catch (e) { sel = null; }
  return { key, sel };
}
function restoreFocus(f) {
  if (!f) return;
  const q = CSS.escape(f.key);
  const el = document.querySelector(`[data-k="${q}"]`) || document.querySelector(`[data-bind="${q}"]`) || document.getElementById(f.key);
  if (!el || el === document.activeElement) return;
  el.focus({ preventScroll: true });
  if (f.sel && typeof el.setSelectionRange === 'function') { try { el.setSelectionRange(f.sel[0], f.sel[1]); } catch (e) { /* tipo senza selezione */ } }
}
function typingInStep() {
  const a = document.activeElement;
  const step = $('#step');
  return !!(a && step && step.contains(a) && (a.tagName === 'TEXTAREA' || (a.tagName === 'INPUT' && /^(text|search|number|)$/.test(a.type))));
}
function renderAll(stepChanged = false, { soft = false } = {}) {
  if (!RULES) return;
  PH = null;
  CUR_KEY = JSON.stringify(compileChar());
  document.body.dataset.step = STEPS[S.step].id;
  document.body.classList.toggle('hero-open', !!S.ui.heroOpen);
  $('#hero-toggle')?.setAttribute('aria-expanded', String(!!S.ui.heroOpen));
  if (soft && !stepChanged && typingInStep()) {
    DEFERRED = true;
    renderStepper(); renderAside(); renderFooter();
    return;
  }
  DEFERRED = false;
  const focus = stepChanged ? null : captureFocus();
  const y = window.scrollY;
  renderStepper();
  const panel = $('#step');
  panel.innerHTML = RENDER[STEPS[S.step].id]();
  if (stepChanged && lastStepRendered !== S.step && !prefersReducedMotion()) {
    panel.classList.remove('enter');
    void panel.offsetWidth;
    panel.classList.add('enter');
  }
  lastStepRendered = S.step;
  renderAside();
  renderFooter();
  if (!stepChanged) {
    if (Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
    restoreFocus(focus);
  }
}
function lightRender() {
  CUR_KEY = JSON.stringify(compileChar());
  renderStepper(); renderAside(); renderFooter();
}

/* ------------------------------------------------------------------ avvisi e finestre */
function toast(msg) {
  const box = $('#toasts');
  if (!box) return;
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => t.classList.add('out'), 3400);
  setTimeout(() => t.remove(), 3900);
}
function confirmBox(title, text, ok = 'Sì', cancel = 'Annulla') {
  return new Promise((resolve) => {
    const d = $('#dlg');
    if (!d || typeof d.showModal !== 'function') { resolve(window.confirm(`${title}\n\n${text}`)); return; }
    d.innerHTML = `<form method="dialog" class="dlg"><h2>${esc(title)}</h2><p>${esc(text)}</p>
      <div class="dlg-btns"><button value="cancel" class="btn ghost">${esc(cancel)}</button><button value="ok" class="btn gold" autofocus>${esc(ok)}</button></div></form>`;
    d.addEventListener('close', () => resolve(d.returnValue === 'ok'), { once: true });
    d.returnValue = '';
    d.showModal();
  });
}

/* ------------------------------------------------------------------ azioni */
function change(fn, { refresh = true } = {}) {
  fn();
  saveState();
  renderAll();
  if (refresh) scheduleRefresh();
}
function toggleLimited(arr, v, max, what, fem = false) {
  const a = asList(arr).slice();
  const i = a.indexOf(v);
  if (i >= 0) { a.splice(i, 1); return a; }
  if (max != null && max > 0 && a.length >= max) {
    if (max === 1) return [v];
    toast(`Hai già scelto ${max} ${what}: ${fem ? 'togline una' : 'togline uno'} per cambiare.`);
    return null;
  }
  a.push(v);
  return a;
}
const hasWork = () => !!((S.char.name || '').trim() || S.char.race || S.char.class);
function rollDie() {
  const buf = new Uint32Array(1);
  (window.crypto || window.msCrypto).getRandomValues(buf);
  return (buf[0] % 6) + 1;
}

const ACTIONS = {
  go: (v) => goStep(Number(v)),
  prev: () => moveStep(-1),
  next: () => moveStep(1),
  'goto-anchor': (v) => {
    const [st, anchor] = String(v).split('|');
    const i = Number(st);
    const scroll = () => {
      const el = anchor && document.getElementById(anchor);
      if (!el) return;
      el.scrollIntoView({ block: 'center', behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
      el.focus({ preventScroll: true });
      el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
    };
    if (i !== S.step) { goStep(i); setTimeout(scroll, 80); } else scroll();
  },
  reset: async () => {
    if (hasWork() && !(await confirmBox('Ricominciare da capo?', 'Il personaggio che stai creando verrà cancellato da questa pagina. I PDF e i personaggi già salvati restano.', 'Ricomincia'))) return;
    S = defaultState();
    try { localStorage.removeItem(STORE_KEY); } catch (e) { /* niente */ }
    SERVER_REQ = null; PREVIEW = null; PREVIEW_PAD = null;
    goStep(0);
    scheduleRefresh(0);
  },
  retry: () => { scheduleRefresh(0); loadChars(); },
  'hero-toggle': () => {
    S.ui.heroOpen = !S.ui.heroOpen;
    document.body.classList.toggle('hero-open', S.ui.heroOpen);
    $('#hero-toggle')?.setAttribute('aria-expanded', String(S.ui.heroOpen));
    if (S.ui.heroOpen) $('#hero-close')?.focus(); else $('#hero-toggle')?.focus();
  },
  gender: (v) => change(() => { S.char.gender = v; }),
  simple: () => change(() => { S.char.simple = !S.char.simple; }),
  'portrait-remove': () => change(() => { S.char.portrait = null; S.thumb = null; }),
  'load-char': (v) => loadCharacter(v),
  race: (v) => change(() => {
    if (S.char.race === v) return;
    // gli strumenti a scelta sono in fila (classe, razza, privilegi): cambiando razza le caselle si spostano
    Object.assign(S.char, { race: v, subrace: null, draconic_ancestry: null, racial_skills: [], racial_cantrips: [], tools: [] });
    dropRacialFromClassCantrips();
    S.char.abilities.racial_choice = [];
    S.raceFeat = null;
  }),
  subrace: (v) => change(() => {
    if ((S.char.subrace || '') === v) return;
    S.char.subrace = v || null;
    S.char.abilities.racial_choice = []; S.char.racial_skills = []; S.char.racial_cantrips = []; S.raceFeat = null;
    dropRacialFromClassCantrips();
  }),
  ancestry: (v) => change(() => { S.char.draconic_ancestry = v; }),
  'racial-choice': (v) => {
    const R = req();
    const next = toggleLimited(S.char.abilities.racial_choice, v, R.racial_choice?.count, 'caratteristiche', true);
    if (next) change(() => { S.char.abilities.racial_choice = next; });
  },
  'racial-skill': (v) => {
    const next = toggleLimited(S.char.racial_skills, v, req().racial_skills?.count, 'abilità', true);
    if (next) change(() => { S.char.racial_skills = next; });
  },
  'racial-cantrip': (v) => change(() => { S.char.racial_cantrips = asList(S.char.racial_cantrips).includes(v) ? [] : [v]; dropRacialFromClassCantrips(); }),
  class: (v) => change(() => {
    if (S.char.class === v) return;
    Object.assign(S.char, {
      class: v, subclass: null, skills: [], cantrips: [], spells: [], spellbook: [], class_options: {}, fighting_style: null,
      fighting_styles: [], maneuvers: [], expertise: [], extra_skills: [], circle_terrain: null,
      option_picks: {}, companion: null, spell_mastery: [], signature_spells: [], tools: [],
    });
    S.slots = {};
    S.ui.spellTab = null;
  }),
  subclass: (v) => change(() => {
    if (S.char.subclass === v) return;
    S.char.subclass = v; S.char.circle_terrain = null; S.char.companion = null;
  }),
  terrain: (v) => change(() => { S.char.circle_terrain = v; }),
  background: (v) => change(() => {
    if (S.char.background === v) return;
    S.char.background = v; S.char.background_skills = null; S.char.background_tools = null;
  }),
  method: (v) => change(() => {
    const ab = S.char.abilities;
    if (ab.method === v) return;
    ab.method = v;
    if (v === 'point_buy') {
      const pb = req().point_buy || RULES.skills.point_buy;
      const costs = ABIL.map((a) => pb.costs[String(ab.base[a])]);
      if (costs.some((x) => x == null) || sum(costs) > pb.budget) ABIL.forEach((a) => { ab.base[a] = 8; });
    } else if (v === 'standard_array' || v === 'rolled') {
      syncAssignedBase(v);
    } else {
      ABIL.forEach((a) => { if (ab.base[a] == null) ab.base[a] = 10; });
    }
  }),
  pb: (v) => {
    const [a, d] = v.split(':');
    const ab = S.char.abilities;
    const pb = req().point_buy || RULES.skills.point_buy;
    const cur = Number(ab.base[a] ?? 8);
    const nv = cur + Number(d);
    if (nv < 8 || nv > 15) return;
    const spent = sum(ABIL.map((x) => pb.costs[String(x === a ? nv : ab.base[x])] ?? 0));
    if (spent > pb.budget) { toast('Non hai abbastanza punti: abbassa un\'altra caratteristica.'); return; }
    change(() => { ab.base[a] = nv; });
  },
  'build-apply': (v) => change(() => {
    const b = BUILDS[Number(v)];
    const prio = CLASS_PRIORITY[S.char.class] || ABIL;
    const ab = S.char.abilities;
    ab.method = 'point_buy';
    prio.forEach((a, j) => { ab.base[a] = b.values[j]; });
    toast(`Numeri «${b.name}» pronti: li vedi qui sotto.`);
  }),
  'array-auto': () => change(() => {
    const arr = arrayPool('standard_array');
    const order = arr.map((v, i) => [v, i]).sort((x, y) => y[0] - x[0]).map(([, i]) => i);
    const prio = CLASS_PRIORITY[S.char.class] || ABIL;
    S.assign.standard_array = Object.fromEntries(prio.map((a, j) => [a, order[j]]));
    syncAssignedBase('standard_array');
  }),
  roll: () => {
    ROLLING = true;
    for (let i = 0; i < 6; i++) {
      const dice = [rollDie(), rollDie(), rollDie(), rollDie()];
      S.rollDice[i] = dice;
      S.rolls[i] = sum(dice) - Math.min(...dice);
    }
    change(() => { if (S.char.abilities.method === 'rolled') syncAssignedBase('rolled'); });
    setTimeout(() => { ROLLING = false; if (STEPS[S.step].id === 'abilities') renderAll(); }, 700);
  },
  'slot-type': (v) => change(() => {
    const [L, type] = v.split(':');
    S.slots[L] = { ...(S.slots[L] || { asi: [] }), type };
  }),
  'feat-open': (scope) => change(() => { S.ui.featOpen[scope] = !S.ui.featOpen[scope]; }, { refresh: false }),
  'feat-pick': (v) => change(() => {
    const [scope, key] = v.split('|');
    const cur = getFeatSlot(scope);
    if (!cur || cur.key !== key) setFeatSlot(scope, { key });
    S.ui.featOpen[scope] = false;
    S.ui.featQuery[scope] = '';
  }),
  'feat-weapon': (v) => {
    const [scope, key] = v.split('|');
    const f = getFeatSlot(scope);
    const wp = RULES.feats?.[f?.key]?.weapon_proficiencies;
    const next = toggleLimited(f?.weapons, key, wp?.count, 'armi', true);
    if (next) change(() => setFeatSlot(scope, { ...f, weapons: next }));
  },
  'feat-cantrip': (v) => {
    const [scope, key] = v.split('|');
    const f = getFeatSlot(scope);
    const next = toggleLimited(f?.cantrips, key, RULES.feats?.[f?.key]?.cantrip_choice?.count || 1, 'trucchetti');
    if (next) change(() => setFeatSlot(scope, { ...f, cantrips: next }));
  },
  'feat-spell': (v) => {
    const [scope, key] = v.split('|');
    const f = getFeatSlot(scope);
    const next = toggleLimited(f?.spells, key, RULES.feats?.[f?.key]?.spell_choice?.count || 1, 'incantesimi');
    if (next) change(() => setFeatSlot(scope, { ...f, spells: next }));
  },
  'feat-dmg': (v) => {
    const [scope, d] = v.split('|');
    const f = getFeatSlot(scope);
    change(() => setFeatSlot(scope, { ...f, damage_type: f?.damage_type === d ? null : d }));
  },
  'skill-class': (v) => {
    const R = req();
    const others = proficientSet({ ...baseChar(), skills: [] }, R);
    const valid = asList(S.char.skills).filter((s) => !others[s]);
    if (!asList(S.char.skills).includes(v) && valid.length >= (R.class_skills?.count || 99)) {
      if ((R.class_skills?.count || 0) === 1) { change(() => { S.char.skills = [v]; }); return; }
      toast(`Hai già scelto ${R.class_skills.count} abilità: togline una per cambiare.`);
      return;
    }
    change(() => {
      const a = asList(S.char.skills).slice();
      const i = a.indexOf(v);
      if (i >= 0) a.splice(i, 1); else a.push(v);
      S.char.skills = a;
    });
  },
  // si parte dalle scelte valide: quelle uscite dall'elenco (cambio di razza o sottoclasse) non occupano posto
  'skill-extra': (v) => { const R = req(); const next = toggleLimited(extraPicks(baseChar(), R), v, R.extra_skills?.count, 'abilità', true); if (next) change(() => { S.char.extra_skills = next; }); },
  'skill-exp': (v) => { const R = req(); const next = toggleLimited(expertisePicks(baseChar(), R), v, R.expertise?.count, 'maestrie', true); if (next) change(() => { S.char.expertise = next; }); },
  lang: (v) => { const R = req(); const next = toggleLimited(langPicks(baseChar(), R), v, R.languages?.count, 'linguaggi'); if (next) change(() => { S.char.languages_extra = next; }); },
  spell: (v) => {
    const [kind, key] = v.split('|');
    const R = req();
    const lim = spellLimits(baseChar(), R);
    const sp0 = spellOf(key);
    if (kind === 'cantrip') {
      const own = asList(S.char.cantrips).filter((k) => !racialCantrips().includes(k) && !grantedCantrips(R).includes(k));
      if (!own.includes(key) && sp0 && !(sp0.lists || []).includes(lim.main) && lim.offCantrips.length >= lim.cantripMax) {
        const from = lim.extraC.map((e) => `${e.count} dalla lista del ${listName(e.list)}`).join(', ');
        toast(from ? `Da un'altra lista puoi prendere solo ${from}: togli quello scelto per cambiarlo.` : 'Questo trucchetto non è della tua lista.');
        return;
      }
      const next = toggleLimited(own, key, R.cantrips?.count, 'trucchetti');
      if (next) change(() => { S.char.cantrips = next; });
    } else if (kind === 'book') {
      const max = R.spells?.max_level || 9; // quelli sopra il livello attuale non si vedono: non devono occupare posto
      const next = toggleLimited(asList(S.char.spellbook).filter((k) => (spellOf(k)?.level ?? 1) <= max), key, R.spellbook?.count, 'incantesimi nel libro');
      if (next) change(() => { S.char.spellbook = next; S.char.spells = asList(S.char.spells).filter((k) => next.includes(k)); });
    } else {
      const sp = spellOf(key);
      const cur = asList(S.char.spells);
      if (sp && sp.level > (R.spells?.max_level || 9)) { // Arcanum Mistico: uno per livello, fuori dal conteggio
        change(() => {
          const others = cur.filter((k) => spellOf(k)?.level !== sp.level);
          S.char.spells = cur.includes(key) ? others : [...others, key];
        });
        return;
      }
      if (!cur.includes(key) && R.spells?.count && countedSpells(S.char, R).length >= R.spells.count) {
        toast(`Hai già scelto ${R.spells.count} ${R.spells.mode === 'known' ? 'incantesimi' : 'incantesimi da preparare'}: togline uno per cambiare.`);
        return;
      }
      if (!cur.includes(key) && sp) {
        const offList = !(sp.lists || []).includes(lim.main) && !asList(R.spells?.expanded).includes(key) && !alwaysPreparedKeys(R).has(key);
        if (offList && lim.secrets && lim.offList.length >= lim.secrets) {
          toast(`Segreti Magici: puoi prendere solo ${lim.secrets} incantesimi di altre classi. Togline uno per cambiare.`);
          return;
        }
        if (lim.allowed && !lim.allowed.includes(norm(SCHOOL_IT[sp.school] || sp.school)) && lim.offSchool.length >= lim.anySchool) {
          toast(`Di un'altra scuola puoi averne solo ${lim.anySchool}: togline uno per cambiare.`);
          return;
        }
      }
      change(() => { S.char.spells = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key]; });
    }
  },
  'spell-tab': (v) => change(() => { S.ui.spellTab = v === 'c' ? 'c' : Number(v); }, { refresh: false }),
  'book-mode': (v) => change(() => { S.ui.bookMode = v; S.ui.spellTab = null; }, { refresh: false }),
  style: (v) => {
    const R = req();
    const count = R.fighting_style?.count || 1;
    const cur = [S.char.fighting_style, ...asList(S.char.fighting_styles)].filter(Boolean);
    const next = count === 1 ? (cur[0] === v ? [] : [v]) : toggleLimited(cur, v, count, 'stili');
    if (next) change(() => { S.char.fighting_style = next[0] || null; S.char.fighting_styles = next.slice(1); });
  },
  maneuver: (v) => { const next = toggleLimited(S.char.maneuvers, v, req().maneuvers?.count, 'manovre', true); if (next) change(() => { S.char.maneuvers = next; }); },
  option: (v) => {
    const [key, item] = v.split('|');
    const opt = req().class_options?.[key];
    const next = toggleLimited(asList(S.char.class_options?.[key]).map(optKey), item, opt?.count, 'opzioni', true);
    if (next) change(() => { S.char.class_options = { ...(S.char.class_options || {}), [key]: next }; });
  },
  'opt-sub': (v) => {
    const [key, ik, kind, sk] = v.split('|');
    const p = optionSubPools(optionRule(key, ik))[kind];
    if (!p) return;
    const id = `${key}|${ik}`;
    const field = kind === 'cantrip' ? 'cantrips' : 'spells';
    const cur = S.char.option_picks?.[id] || {};
    const next = toggleLimited(cur[field], sk, p.count, kind === 'cantrip' ? 'trucchetti' : 'incantesimi');
    if (next) change(() => { S.char.option_picks = { ...(S.char.option_picks || {}), [id]: { ...cur, [field]: next } }; });
  },
  companion: (v) => change(() => { S.char.companion = S.char.companion === v ? null : v; }),
  mastery: (v) => change(() => { // uno di 1° e uno di 2°: scegliere un altro dello stesso livello lo sostituisce
    const cur = asList(S.char.spell_mastery);
    const L = spellOf(v)?.level;
    S.char.spell_mastery = cur.includes(v) ? cur.filter((k) => k !== v) : [...cur.filter((k) => spellOf(k)?.level !== L), v];
  }),
  signature: (v) => {
    const next = toggleLimited(S.char.signature_spells, v, 2, 'incantesimi personali');
    if (next) change(() => { S.char.signature_spells = next; S.char.spells = asList(S.char.spells).filter((k) => !next.includes(k)); });
  },
  armor: (v) => change(() => { S.char.armor = v || null; }),
  shield: () => change(() => { S.char.shield = !S.char.shield; }),
  weapon: (v) => change(() => {
    const list = asList(S.char.weapons).slice();
    const i = list.findIndex((w) => (typeof w === 'string' ? w : w.key) === v);
    if (i >= 0) list.splice(i, 1); else list.push(v);
    S.char.weapons = list;
  }),
  pack: (v) => change(() => {
    const eq = asList(S.char.equipment).filter((e) => !(e && typeof e === 'object' && e.pack));
    S.char.equipment = v ? [{ pack: v }, ...eq] : eq;
  }),
  'item-remove': (v) => change(() => { const eq = asList(S.char.equipment).slice(); eq.splice(Number(v), 1); S.char.equipment = eq; }),
  'item-add': () => {
    const inp = $('#item-new');
    const text = (inp?.value || '').trim();
    if (!text) { inp?.focus(); return; }
    change(() => { S.char.equipment = [...asList(S.char.equipment), text]; });
    const again = $('#item-new');
    if (again) { again.value = ''; again.focus(); }
  },
  'bg-equip': () => change(() => { S.char.include_background_equipment = S.char.include_background_equipment === false; }),
  'bg-gold': () => change(() => { S.char.money = { ...(S.char.money || {}), gp: Number(bgOf()?.gold || 0) }; }),
  align: (v) => change(() => { S.char.alignment = v; }),
  build: () => buildPdf(),
};

/* ------------------------------------------------------------------ ritratto, caricamento, PDF */
function makeThumb(file, max = 360) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = reject;
    reader.onload = () => {
      const img = new Image();
      img.onerror = reject;
      img.onload = () => {
        const scale = Math.min(1, max / Math.max(img.width, img.height));
        const cv = document.createElement('canvas');
        cv.width = Math.round(img.width * scale);
        cv.height = Math.round(img.height * scale);
        cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height);
        resolve(cv.toDataURL('image/jpeg', 0.82));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}
async function onPortrait(file) {
  if (!file) return;
  if (!(S.char.name || '').trim()) { toast('Scrivi prima il nome del personaggio.'); return; }
  if (!/^image\//.test(file.type)) { toast('Questo file non è un\'immagine: scegli una foto o un disegno.'); return; }
  const oldThumb = S.thumb;
  try { S.thumb = await makeThumb(file); } catch (e) { S.thumb = null; }
  saveState(); renderAll();
  const fd = new FormData();
  // stessa cartella in cui il programma salverà il personaggio (characters/<nome>/portrait.jpg);
  // il nome serve al programma per non toccare mai il ritratto di un altro personaggio protetto
  fd.append('stem', fileStem(S.char.name) || 'personaggio');
  fd.append('name', S.char.name.trim());
  fd.append('file', file);
  try {
    const r = await api('/api/portrait', { method: 'POST', body: fd });
    if (!r || !r.portrait) throw new Error((r && r.error) || 'il programma non ha salvato l\'immagine');
    S.char.portrait = r.portrait;
    toast('Ritratto salvato.');
  } catch (e) {
    S.thumb = oldThumb; // l'immagine non è stata salvata: non mostrarla come se lo fosse
    toast(e.offline ? 'Il programma non risponde: il ritratto non è stato salvato.' : `Ritratto non salvato: ${e.message}`);
  }
  saveState(); renderAll(); scheduleRefresh();
}
async function loadChars() {
  try {
    const r = await api('/api/characters');
    CHARS = Array.isArray(r) ? r : (r && r.characters) || [];
  } catch (e) { CHARS = []; }
  if (STEPS[S.step].id === 'start') renderAll(false, { soft: true });
}
function importChar(ch, stem) {
  const st = defaultState();
  const base = defaultChar();
  const c = { ...base, ...clone(ch) };
  c.abilities = { ...base.abilities, ...(ch.abilities || {}) };
  c.abilities.base = { ...base.abilities.base, ...((ch.abilities || {}).base || {}) };
  c.abilities.racial_choice = asList(c.abilities.racial_choice);
  c.money = { ...base.money, ...(ch.money || {}) };
  c.personality = { ...base.personality, ...(ch.personality || {}) };
  c.appearance = { ...base.appearance, ...(ch.appearance || {}) };
  c.class_options = {};
  c.option_picks = {};
  for (const [key, list] of Object.entries(ch.class_options || {})) { // {key, cantrips, spells} -> chiave + sotto-scelte
    c.class_options[key] = asList(list).map((e) => {
      if (e && typeof e === 'object') { c.option_picks[`${key}|${e.key}`] = { cantrips: asList(e.cantrips), spells: asList(e.spells) }; return e.key; }
      return e;
    });
  }
  for (const key of ['skills', 'racial_skills', 'extra_skills', 'expertise', 'racial_cantrips', 'cantrips', 'spells', 'spellbook', 'maneuvers', 'languages_extra', 'tools', 'weapons', 'equipment', 'fighting_styles', 'spell_mastery', 'signature_spells']) c[key] = asList(c[key]);
  if (c.background_skills != null) c.background_skills = asList(c.background_skills);
  if (c.background_tools != null) {
    const bgRule = RULES.backgrounds?.[c.background];
    c.background_tools = bgRule ? bgToolsToSlots(bgRule, c.background_tools, c) : asList(c.background_tools);
  }
  if (c.xp == null) c.xp = RULES.skills.xp_thresholds?.[(c.level || 1) - 1] ?? 0;
  const asis = asList(ch.abilities?.asi);
  const feats = asList(ch.feats).map((f) => (typeof f === 'string' ? { key: f }
    : { ...f, ability: f.ability || f.save, spells: f.spells ? asList(f.spells) : (f.spell ? [f.spell] : undefined) }));
  delete c.feats;
  delete c.abilities.asi;
  st.char = c;
  S = st;
  if (raceFeatChoice(c) && feats.length) S.raceFeat = feats.shift();
  for (const L of asiLevelsOf(c)) {
    if (asis.length) {
      const a = asis.shift();
      const picks = [];
      for (const [k, v] of Object.entries(a)) for (let i = 0; i < v; i++) picks.push(k);
      S.slots[L] = { type: 'asi', asi: picks.slice(0, 2) };
    } else if (feats.length) S.slots[L] = { type: 'feat', feat: feats.shift() };
  }
  const m = c.abilities.method;
  if (m === 'standard_array') {
    const arr = [...(RULES.skills.standard_array || [])];
    const used = new Set();
    S.assign.standard_array = Object.fromEntries(ABIL.map((a) => {
      const idx = arr.findIndex((v, i) => v === c.abilities.base[a] && !used.has(i));
      if (idx >= 0) used.add(idx);
      return [a, idx >= 0 ? idx : null];
    }));
  } else if (m === 'rolled') {
    S.rolls = ABIL.map((a) => c.abilities.base[a] ?? null);
    S.assign.rolled = Object.fromEntries(ABIL.map((a, i) => [a, i]));
  }
  S.stem = stem;
  S.visited = STEPS.map((_, i) => i);
}
async function loadCharacter(stem) {
  if (hasWork() && S.stem !== stem && !(await confirmBox('Aprire un altro personaggio?', 'Il personaggio che stai creando verrà sostituito in questa pagina. Se non hai ancora generato il PDF, le modifiche andranno perse.', 'Apri'))) return;
  try {
    const data = await api(`/api/characters/${encodeURIComponent(stem)}`);
    const ch = (data && (data.character || data)) || null;
    if (!ch || !ch.name) throw new Error('personaggio non trovato');
    importChar(ch, stem);
    SERVER_REQ = null; PREVIEW = null; PREVIEW_PAD = null;
    saveState();
    toast(`${ch.name} è pronto: cambia quello che vuoi.`);
    renderAll(true);
    scheduleRefresh(0);
  } catch (e) {
    toast(e.offline ? 'Il programma non risponde.' : `Non riesco ad aprire il personaggio: ${e.message}`);
  }
}
async function buildPdf() {
  if (BUILDING) return;
  // il programma salva in characters/<nome>.yaml: un personaggio nuovo con il nome di uno già salvato lo sostituirebbe
  const target = fileStem(S.char.name);
  const clash = target && S.stem !== target && (CHARS || []).find((ch) => ch.stem === target);
  if (clash) {
    const who = `${clash.name || target}${clash.player ? ` (gioca ${clash.player})` : ''}`;
    const ok = await confirmBox('Esiste già un personaggio con questo nome',
      `C'è già un personaggio salvato chiamato ${who}. Se continui, verrà sostituito da questo. Per tenerli tutti e due, annulla e cambia il nome al passo Inizio.`,
      'Sostituiscilo', 'Annulla');
    if (!ok) { toast('Niente è stato sovrascritto: cambia il nome al passo Inizio.'); return; }
  }
  BUILDING = true;
  renderAll();
  const character = compileChar();
  const key = JSON.stringify(character);
  try {
    const r = await postJSON('/api/build', { character });
    if (r && r.ok) {
      S.built = { ...r, key, at: Date.now() };
      if (r.stem) S.stem = r.stem;
      toast('La scheda è pronta!');
      loadChars();
    } else {
      S.built = { ok: false, error: (r && r.error) || 'Il programma non ha creato il PDF.' };
    }
  } catch (e) {
    S.built = { ok: false, offline: !!e.offline, error: e.offline ? 'Il programma non risponde: riaprilo con il doppio clic su «Crea personaggio» e riprova.' : e.message };
  }
  BUILDING = false;
  saveState();
  renderAll();
  const res = $('#sec-result');
  if (res) { res.scrollIntoView({ block: 'start', behavior: prefersReducedMotion() ? 'auto' : 'smooth' }); res.focus({ preventScroll: true }); }
}

/* ------------------------------------------------------------------ eventi */
document.addEventListener('click', (ev) => {
  const el = ev.target.closest('[data-act]');
  if (!el || el.disabled || el.getAttribute('aria-disabled') === 'true') return;
  const inner = ev.target.closest('details, summary, a, input, select, textarea, label');
  if (inner && inner !== el && el.contains(inner)) return;
  const fn = ACTIONS[el.dataset.act];
  if (fn) { ev.preventDefault(); fn(el.dataset.value, el, ev); }
});
document.addEventListener('input', (ev) => {
  const el = ev.target;
  if (el.dataset.live === 'level') {
    const lvl = Math.min(20, Math.max(1, Number(el.value) || 1));
    S.char.level = lvl;
    S.char.xp = RULES.skills.xp_thresholds?.[lvl - 1] ?? 0;
    const n = $('#level-num'); if (n) n.textContent = lvl;
    const x = $('#f-xp'); if (x) x.value = S.char.xp;
    el.setAttribute('aria-valuetext', `${lvl}° livello`);
    return;
  }
  if (el.dataset.bind) {
    let v = el.value;
    if (el.hasAttribute('data-num')) v = v === '' ? (el.dataset.bind.startsWith('abilities.base') ? null : 0) : Number(v);
    setPath(S.char, el.dataset.bind, v);
    saveState();
    scheduleRefresh(450);
    if (el.dataset.bind === 'name') {
      const has = !!String(v).trim();
      const inp = $('#portrait-file'); if (inp) inp.disabled = !has;
      const drop = $('.portrait-drop'); if (drop) drop.classList.toggle('is-disabled', !has);
      const t = $('.portrait-empty > span'); if (t) t.textContent = has ? 'Scegli un\'immagine' : 'Scrivi prima il nome';
    }
    if (el.closest('.ab-table')) renderAll(); else lightRender();
    return;
  }
  const kind = el.dataset.input;
  if (kind === 'bgtool') {
    const arr = bgToolSlots().map((t) => t.value);
    arr[Number(el.dataset.index)] = el.value;
    S.char.background_tools = arr;
    saveState(); scheduleRefresh(450); lightRender();
  } else if (kind === 'tool') {
    const t = toolPicks(); // niente buchi: una casella vuota è '' (non null, che diventerebbe "null")
    const i = Number(el.dataset.index);
    while (t.length <= i) t.push('');
    t[i] = el.value;
    S.char.tools = t;
    saveState(); scheduleRefresh(450); lightRender();
  } else if (kind === 'feat-query') {
    S.ui.featQuery[el.dataset.scope] = el.value; renderAll();
  } else if (kind === 'spell-query') {
    S.ui.spellQuery = el.value; renderAll();
  } else if (kind === 'roll') {
    const i = Number(el.dataset.index);
    S.rolls[i] = el.value === '' ? null : Number(el.value);
    S.rollDice[i] = [];
    if (S.char.abilities.method === 'rolled') syncAssignedBase('rolled');
    saveState(); scheduleRefresh(450); renderAll();
  }
});
document.addEventListener('change', (ev) => {
  const el = ev.target;
  if (el.dataset.live === 'level') { saveState(); renderAll(); scheduleRefresh(); return; }
  const kind = el.dataset.change;
  if (kind === 'portrait') { onPortrait(el.files && el.files[0]); el.value = ''; }
  else if (kind === 'bgswap') {
    change(() => {
      const bg = bgOf();
      const arr = effectiveBgSkills().slice();
      arr[Number(el.dataset.index)] = el.value;
      S.char.background_skills = arr.join() === (bg.skills || []).join() ? null : arr;
    });
  } else if (kind === 'assign') {
    change(() => {
      const m = S.char.abilities.method;
      S.assign[m] = { ...(S.assign[m] || {}), [el.dataset.ability]: el.value === '' ? null : Number(el.value) };
      syncAssignedBase(m);
    });
  } else if (kind === 'slot-asi') {
    const L = el.dataset.level;
    change(() => {
      const s = S.slots[L] || { type: 'asi', asi: [] };
      const asi = asList(s.asi).slice();
      asi[Number(el.dataset.index)] = el.value || null;
      S.slots[L] = { ...s, type: 'asi', asi };
    });
    if (el.value && computeScores(baseChar())[el.value].total > 20) toast(`${ABNAME[el.value]} supera 20: il massimo normale è 20.`);
  } else if (kind === 'feat-list') {
    change(() => { const f = getFeatSlot(el.dataset.scope); setFeatSlot(el.dataset.scope, { ...f, list: el.value || null, cantrips: [], spells: [] }); });
  } else if (kind === 'feat-ability') {
    change(() => { const f = getFeatSlot(el.dataset.scope); setFeatSlot(el.dataset.scope, { ...f, ability: el.value || null }); });
  }
});
document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter' && ev.target.id === 'item-new') { ev.preventDefault(); ACTIONS['item-add'](); }
  if (ev.key === 'Escape' && S.ui.heroOpen) ACTIONS['hero-toggle']();
});
document.addEventListener('focusout', () => {
  if (!DEFERRED) return;
  setTimeout(() => { if (DEFERRED && !typingInStep()) renderAll(); }, 0);
});

/* ------------------------------------------------------------------ avvio */
function showFatal() {
  document.body.classList.remove('is-loading');
  const text = window.DND_BROWSER_MODE
    ? 'Non sono riuscito a caricare il libro delle regole. Controlla la connessione a internet e ricarica la pagina.'
    : 'Questa pagina funziona solo mentre il programma è acceso. Chiudi questa finestra e riaprila con il doppio clic su «Crea personaggio».';
  $('#app').innerHTML = `<div class="fatal">${emblem('d20', 'emblem big')}
    <h2>Il programma non risponde</h2><p>${esc(text)}</p>
    <button type="button" class="btn gold" onclick="location.reload()">Riprova</button></div>`;
}
async function init() {
  const saved = loadState();
  if (saved) S = saved;
  try {
    const r = await api('/api/rules');
    RULES = (r && r.rules) || r;
    if (!RULES || !RULES.races || !RULES.classes) throw new Error('regole mancanti');
  } catch (e) {
    showFatal();
    return;
  }
  for (const key of ['backgrounds', 'feats', 'maneuvers']) RULES[key] = RULES[key] || {};
  RULES.equipment = RULES.equipment || { weapons: {}, armor: {}, packs: {}, fighting_styles: {} };
  RULES.spells = RULES.spells || { spells: {}, slots: {}, cantrips_known: {} };
  if (S.step < 0 || S.step >= STEPS.length) S.step = 0;
  document.body.classList.remove('is-loading');
  renderAll(true);
  scheduleRefresh(0);
  loadChars();
}
init();
