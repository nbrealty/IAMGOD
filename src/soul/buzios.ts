// Jogo de búzios — a RESPECTFUL game simulation of Candomblé cowrie-shell divination, as read by
// Yara (Águas Douradas). This is fiction inspired by the tradition, NOT a real oracle: in life a
// reading is done only by an initiated ialorixá/babalorixá. Here it's the mechanic by which the
// amnesiac-god player, through Yara, reads their own soul and begins to remember their power.
//
// Mechanic (merindilogun, simplified): 16 cowrie shells are cast; the number that land "open"
// (mouth up), 1–16, selects an ODÙ — a sign governed by an orixá. A second reading marks the sign
// IRE (blessing) or OSOGBO (obstacle). The odù is WEIGHTED by the player-soul's real state, so the
// reading genuinely judges where their choices have led them, then speaks of what is coming.
//
// Consequence: each reading raises AXÉ (spiritual strength = the soul's initiationLevel track, which
// glows the aura + opens the Crown) and opens a specific CHAKRA (by boosting the need that drives
// it); opening a chakra unlocks the divine POWER seated there — powers only Yara can help awaken.

import type { Soul, ChakraName, NeedKey } from "./types.ts";
import { chakraState, clamp } from "./derive.ts";

// The seven chakra-seated powers the god reawakens through Yara's readings. (Names/flavour now;
// their actual gameplay effects are wired as the quest tree grows.)
export interface Power {
  chakra: ChakraName;
  id: string;
  name: string;
  blurb: string;
}
export const CHAKRA_POWERS: Record<ChakraName, Power> = {
  Root: { chakra: "Root", id: "firmament", name: "Firmament", blurb: "The ground itself steadies under you — the god remembers how to simply BE, unshaken." },
  Sacral: { chakra: "Sacral", id: "sweet-waters", name: "Sweet Waters", blurb: "Oxum's river moves in you — desire, art, and creation flow where you turn your gaze." },
  "Solar Plexus": { chakra: "Solar Plexus", id: "thundercrown", name: "Thundercrown", blurb: "Xangô's fire — your will lands like a verdict; others feel the weight of your certainty." },
  Heart: { chakra: "Heart", id: "mercy", name: "Mercy", blurb: "You can mend what is broken between souls — bonds heal in your presence." },
  Throat: { chakra: "Throat", id: "the-word", name: "The Word", blurb: "You speak and the world leans to listen — the divine voice that once named things." },
  "Third Eye": { chakra: "Third Eye", id: "second-sight", name: "Second Sight", blurb: "You read the fate on a soul at a glance — what they carry, and where it pulls them." },
  Crown: { chakra: "Crown", id: "remembrance", name: "Remembrance", blurb: "The veil thins. You begin to remember what you are, and the sky answers to the name." },
};

// The need that principally DRIVES each chakra's openness (see engine.chakraTargets). A reading
// boosts this to durably open the chakra (the aura/chakra follow next tick).
const CHAKRA_NEED: Record<ChakraName, NeedKey> = {
  Root: "survival",
  Sacral: "belonging",
  "Solar Plexus": "esteem",
  Heart: "belonging",
  Throat: "esteem",
  "Third Eye": "actualization",
  Crown: "actualization",
};

export interface Odu {
  n: number; // number of open shells (1–16) that yields this sign
  name: string;
  orixa: string;
  chakra: ChakraName; // the domain it moves
  theme: string; // one-word/short domain of life
  ire: string; // the blessing/future when the sign falls IRE
  osogbo: string; // the warning/future when it falls OSOGBO
}

// The 16 primary odù (Oju Odu). Spellings/attributions vary by house; these use common ones and
// map each to a chakra domain for the game. (Odù 5 Oxé & 6 Obara carry Oxum — Yara's orixá.)
export const ODUS: Odu[] = [
  { n: 1, name: "Okaran", orixa: "Exu", chakra: "Root", theme: "the crossroads", ire: "a door you thought shut is only latched — push, and the road opens.", osogbo: "a small neglect is about to trip you; settle what you've been avoiding before it settles you." },
  { n: 2, name: "Eji Oko", orixa: "Ibeji & Ogun", chakra: "Sacral", theme: "the pair", ire: "someone is coming to walk beside you — say yes when they arrive.", osogbo: "you are carrying two roads at once; one of them is quietly costing you the other." },
  { n: 3, name: "Ogunda", orixa: "Ogun", chakra: "Solar Plexus", theme: "the blade", ire: "you have the strength to cut the knot that's bound you — do it clean, and soon.", osogbo: "anger is a tool you've been holding by the blade; it's cutting the wrong hand." },
  { n: 4, name: "Irosun", orixa: "Yemanjá & the ancestors", chakra: "Root", theme: "the deep water", ire: "what your line began, you're meant to finish — the old blessing is still owed to you.", osogbo: "you're standing on ground you never made peace with; the past is asking to be faced." },
  { n: 5, name: "Oxé", orixa: "Oxum", chakra: "Sacral", theme: "sweet water", ire: "love and abundance are turning toward you like a river — receive them without apology.", osogbo: "you've been pouring from an empty vessel; Oxum says fill yourself before you give again." },
  { n: 6, name: "Obara", orixa: "Xangô & Oxum", chakra: "Heart", theme: "the scale", ire: "a fairness long delayed is about to land in your favour — hold your dignity and wait.", osogbo: "a debt of the heart is unbalanced; someone is owed the truth, and it may be you." },
  { n: 7, name: "Odi", orixa: "Obaluaiê & Yemanjá", chakra: "Root", theme: "the foundation", ire: "the shaky ground under you is quietly setting firm — build now, it will hold.", osogbo: "the body and the home are asking for care you keep postponing; tend the base." },
  { n: 8, name: "Eji Onile", orixa: "Oxalá", chakra: "Crown", theme: "the throne", ire: "you are being lifted to lead — the calm you've earned is about to be needed by others.", osogbo: "pride is standing where humility should; the seat is real, but not yet yours to take." },
  { n: 9, name: "Osa", orixa: "Iansã", chakra: "Throat", theme: "the wind", ire: "a wind of change is at your back — speak the thing you've been holding, it will carry.", osogbo: "a storm you keep silent is building pressure; say it before it says itself." },
  { n: 10, name: "Ofun", orixa: "Oxalá", chakra: "Crown", theme: "creation", ire: "you're at the white dawn of something — begin gently, in peace, and it will be blessed.", osogbo: "you're rushing a birth; Oxalá counsels stillness — nothing pure comes from hurry." },
  { n: 11, name: "Owonrin", orixa: "the restless orixás", chakra: "Sacral", theme: "the turning", ire: "everything is in motion for you now — ride the change instead of bracing against it.", osogbo: "you're changing everything but the one thing that matters; the turning is a distraction." },
  { n: 12, name: "Ejila Xeborá", orixa: "Xangô", chakra: "Solar Plexus", theme: "the verdict", ire: "justice remembers you — the authority you've been denied is coming to your hand.", osogbo: "you're judging a matter you haven't understood; Xangô warns against a hasty verdict." },
  { n: 13, name: "Ika", orixa: "Nanã & Obaluaiê", chakra: "Root", theme: "the ending", ire: "an old thing is ending so a truer one can begin — let it close, and bless it as it goes.", osogbo: "you're feeding something already dead; Nanã asks you to bury it and grieve it properly." },
  { n: 14, name: "Oturupon", orixa: "Nanã & Omolu", chakra: "Heart", theme: "endurance", ire: "the long, patient work is nearly through — what you've endured is about to mean something.", osogbo: "you're carrying more than is yours; set down what you didn't agree to hold." },
  { n: 15, name: "Ofun Kanran", orixa: "Oxalá", chakra: "Crown", theme: "the reckoning", ire: "a heavy account is being cleared in your favour — the weight you've carried is lifting.", osogbo: "an old debt of spirit is due; face it now, gently, and it will not compound." },
  { n: 16, name: "Irete", orixa: "the completed word", chakra: "Third Eye", theme: "the seal", ire: "a cycle completes in blessing — you see, now, what you couldn't before. Trust the sight.", osogbo: "you're closing a door you were meant to walk through; look again before you seal it." },
];

export interface Reading {
  odu: Odu;
  openCount: number; // shells that fell open (1–16)
  ire: boolean; // true = blessing, false = osogbo (obstacle)
  present: string; // the "judgement" — what their soul-state (their choices) shows now
  future: string; // what is coming (the odù's ire/osogbo line)
  axeGain: number; // spiritual strength gained
  chakra: ChakraName; // the domain this reading moves
}

export interface ReadingOutcome {
  reading: Reading;
  axeAfter: number; // 0–100 progress within the tier
  tieredUp: boolean; // initiationLevel rose
  newInitiation: number;
  unlockedPower: Power | null; // a chakra-power awakened by this reading (else null)
}

// A tiny deterministic PRNG so a reading is reproducible from a seed (no Math.random — matches the
// project's no-Date/no-random rule; the seed is passed in from the caller, e.g. clock minutes + id).
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Read the soul's chakras: the most-open (a strength) and most-blocked (what their choices have
// starved). Used to make the "present" judgement feel personal, and to bias which odù falls.
function readChakras(s: Soul): { weakest: ChakraName; strongest: ChakraName } {
  const order = Object.keys(s.chakras) as ChakraName[];
  let weakest = order[0], strongest = order[0];
  for (const c of order) {
    if (s.chakras[c] < s.chakras[weakest]) weakest = c;
    if (s.chakras[c] > s.chakras[strongest]) strongest = c;
  }
  return { weakest, strongest };
}

const CHAKRA_STRENGTH_LINE: Record<ChakraName, string> = {
  Root: "your footing is sure — you know how to survive",
  Sacral: "your heart for pleasure and making is alive",
  "Solar Plexus": "your will is bright — you move when you decide to",
  Heart: "you love openly, and it shows",
  Throat: "you speak your truth cleanly",
  "Third Eye": "you already sense more than you admit",
  Crown: "something in you reaches for the sky, and touches it",
};
const CHAKRA_LACK_LINE: Record<ChakraName, string> = {
  Root: "but you've let your own ground go untended — safety, rest, the body",
  Sacral: "but joy and connection have gone thin in you",
  "Solar Plexus": "but you doubt your own weight — you wait to be told",
  Heart: "but you've closed the heart to keep from being hurt",
  Throat: "but there's a truth you keep swallowing",
  "Third Eye": "but you look away from what you see",
  Crown: "but you've forgotten there's anything above the roof",
};

// Cast the shells for a soul. `seed` makes it reproducible. The odù is drawn from a distribution
// pulled toward the soul's WEAKEST chakra (the reading names what their choices have neglected),
// with real randomness on top; ire/osogbo is biased by overall spiritual balance.
export function castReading(soul: Soul, seed: number): Reading {
  const rng = mulberry32(seed);
  const { weakest, strongest } = readChakras(soul);

  // 16 shells, each "open" with a base 0.5 plus a small favour for a more spiritually-open soul.
  const avgOpen = (Object.values(soul.chakras).reduce((a, c) => a + c, 0) / 7) / 100; // 0..1
  const pOpen = 0.42 + avgOpen * 0.16; // 0.42..0.58
  let openCount = 0;
  for (let i = 0; i < 16; i++) if (rng() < pOpen) openCount++;
  if (openCount < 1) openCount = 1;

  // Bias the SIGN toward one that governs the soul's weakest chakra 40% of the time (the oracle
  // "speaks to" what's been neglected), else take the odù the shell-count landed on.
  let odu = ODUS[openCount - 1];
  if (rng() < 0.4) {
    const matches = ODUS.filter((o) => o.chakra === weakest);
    if (matches.length) odu = matches[Math.floor(rng() * matches.length)];
  }

  // Ire vs osogbo: a balanced, tended soul tilts toward blessing; a neglected one toward warning.
  const ire = rng() < 0.4 + avgOpen * 0.35;

  const present =
    `The shells show me you as you are: ${CHAKRA_STRENGTH_LINE[strongest]}, ` +
    `${CHAKRA_LACK_LINE[weakest]}. This is the shape your own choices have drawn.`;
  const future = `${odu.name} falls, and ${odu.orixa} speaks: ` + (ire ? odu.ire : odu.osogbo);
  const axeGain = ire ? 22 : 11;

  return { odu, openCount, ire, present, future, axeGain, chakra: odu.chakra };
}

// Apply a reading's consequence to the soul: raise AXÉ (initiationLevel progress), durably open the
// odù's chakra by boosting its driving need, and awaken that chakra's power if it opens. Mutates the
// soul (the engine owns the soul; these are the deeper drivers, so chakra/aura follow on the tick).
export function applyReading(soul: Soul, reading: Reading): ReadingOutcome {
  // AXÉ: fill the tier progress; overflow raises the initiation level (max 7) → brighter aura + Crown.
  let axe = (soul.axe ?? 0) + reading.axeGain;
  let tieredUp = false;
  while (axe >= 100 && soul.initiationLevel < 7) {
    axe -= 100;
    soul.initiationLevel += 1;
    tieredUp = true;
  }
  if (soul.initiationLevel >= 7) axe = Math.min(axe, 100);
  soul.axe = axe;

  // Open the chakra: boost its driving need (durable) AND nudge the current openness for instant feel.
  const need = CHAKRA_NEED[reading.chakra];
  soul.needs[need] = clamp(soul.needs[need] + (reading.ire ? 10 : 6));
  soul.chakras[reading.chakra] = clamp(soul.chakras[reading.chakra] + (reading.ire ? 14 : 8));

  // Awaken the seated power if this reading opened the chakra and it isn't already known.
  let unlockedPower: Power | null = null;
  const powers = (soul.powers ??= []);
  const power = CHAKRA_POWERS[reading.chakra];
  if (chakraState(soul.chakras[reading.chakra]) === "open" && !powers.includes(power.id)) {
    powers.push(power.id);
    unlockedPower = power;
  }

  return { reading, axeAfter: soul.axe, tieredUp, newInitiation: soul.initiationLevel, unlockedPower };
}
