// The structured Soul model — the real three-layer state a simulation can tick,
// replacing the display-string SoulProfile stubs from Phase 0.
//
// Psychology (needs, traits, ACE, resilience, Kohlberg), sociology (belonging,
// archetype), and spirit (chakra openness, soul age, initiation) all live here as
// numbers the engine mutates over time. Display strings are DERIVED from these, not
// stored (see derive.ts).

export type ChakraState = "blocked" | "imbalanced" | "open";

export const CHAKRA_ORDER = [
  "Root",
  "Sacral",
  "Solar Plexus",
  "Heart",
  "Throat",
  "Third Eye",
  "Crown",
] as const;

export type ChakraName = (typeof CHAKRA_ORDER)[number];

// Plutchik primaries (compact — the doctrine's 34k compounds can layer on later).
export type PrimaryEmotion =
  | "joy"
  | "trust"
  | "fear"
  | "surprise"
  | "sadness"
  | "disgust"
  | "anger"
  | "anticipation"
  | "neutral";

// Maslow-derived needs, 0–100. They decay over time and are replenished by
// activities the utility AI selects.
export interface Needs {
  survival: number; // food, rest, physical safety of the body (Maslow 1)
  safety: number; // stability, security, freedom from fear (Maslow 2)
  belonging: number; // connection, love, community (Maslow 3)
  esteem: number; // recognition, competence, dignity (Maslow 4)
  actualization: number; // purpose, growth, meaning (Maslow 5)
}

export type NeedKey = keyof Needs;
export const NEED_KEYS: NeedKey[] = [
  "survival",
  "safety",
  "belonging",
  "esteem",
  "actualization",
];

// The 5 maladaptive trait elevations, 0–100. Slow-moving; shape how a soul reacts.
export interface Traits {
  negativeAffectivity: number;
  detachment: number;
  antagonism: number;
  disinhibition: number;
  psychoticism: number;
}

export type SoulAge = "Young" | "Mature" | "Old";

export interface EmotionState {
  primary: PrimaryEmotion;
  intensity: number; // 0–100
}

export interface Soul {
  // identity
  id: string;
  name: string;
  occupation: string;
  archetype: string;
  age: number;
  narrative: string;
  // Cluster-level social affiliation (a street set, a scene, a crew). Per the locked
  // homophily decision, faction is a GROUP signal that drives faction-coded clothing —
  // NOT an individual trait. The same colors sit on a true believer, a scared initiate,
  // and someone quietly getting out; the soul's own numbers carry the real difference.
  faction?: string;

  // psychology
  needs: Needs;
  traits: Traits;
  aceScore: number; // 0–10+
  resilience: number; // 0–100
  kohlberg: number; // 1–6 moral reasoning stage
  emotion: EmotionState;

  // spirit
  soulAge: SoulAge;
  initiationLevel: number; // 0–7
  // Chakra OPENNESS as a continuous 0–100 value; the blocked/imbalanced/open enum
  // is derived from it (see derive.ts → chakraState). Continuous state lets the
  // interference rules nudge chakras smoothly.
  chakras: Record<ChakraName, number>;

  // the god-only dramatic irony: what they THINK they want vs. what their soul
  // actually incarnated to do. Often divergent — closing that gap is the deep game.
  consciousAspiration: string;
  soulPurpose: string;

  // current utility-selected activity (id from engine.ts ACTIVITIES)
  activity: string;

  // per-soul activity affinities — flavor multipliers so a performer performs and a
  // tourist gazes without hard-coding archetype into the scorer.
  affinities: Record<string, number>;

  // per-need decay overrides (per sim-minute); falls back to engine defaults.
  decay?: Partial<Needs>;

  // The natural plateau for each need WITHOUT divine intervention — the highest a
  // need realistically sits given this soul's circumstance and psychology. Activities
  // replenish toward the ceiling with diminishing returns, so souls settle into a
  // band that reflects who they are; they don't all drift to 100. The player-god's
  // blessings are what push a soul *past* its ceiling. Computed by the engine from
  // starting needs + traits if not authored.
  ceilings?: Needs;

  // spatial / patrol data the renderer uses (movement stays simple in Phase 1)
  row: "north" | "south";
  xMin: number;
  xMax: number;
  baseSpeed: number;
  // Phase 2b: the square opened up N/S. `patrolY` pins a soul to an explicit frontage
  // line (a sidewalk y) instead of the row-derived boulevard sidewalk — lets the cast
  // spread across the new frontages (e.g. standing on a Highland Ave sidewalk) rather
  // than only the two boulevard sidewalks. Falls back to the row logic when unset.
  patrolY?: number;
}
