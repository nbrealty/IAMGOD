// Hollywood & Highland scene data — the NPC roster, building footprints, and the
// shared constants the renderer and interaction layer both read from.
//
// This is hand-authored stub data for the Day 1 / Phase 0 slice. In Phase 1 the
// NPC souls become procedurally generated and driven by a utility-AI tick loop;
// the shape below is the seam that engine will plug into.

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

export interface SoulProfile {
  id: string;
  name: string;
  occupation: string;
  archetype: string;
  age: number;
  maslow: string;
  emotion: string;
  aura: string;
  narrative: string;
  chakras: Record<ChakraName, ChakraState>;
  row: "north" | "south";
  xMin: number;
  xMax: number;
  speed: number;
}

export interface Building {
  special?: "tcl";
  x: number;
  width?: number;
  height?: number;
  side?: "north" | "south";
  facadeColor?: string;
  roofColor?: string;
  label?: string;
  marquee?: string;
  marqueeColor?: string;
  depth?: number;
  skew?: number;
}

// Virtual canvas size — the renderer draws to this coordinate space and scales.
export const SCENE_W = 1600;
export const SCENE_H = 900;

export const ROAD_TOP = 420;
export const ROAD_BOTTOM = 520;
export const NORTH_SIDEWALK_TOP = 380;
export const SOUTH_SIDEWALK_TOP = ROAD_BOTTOM;
export const SOUTH_SIDEWALK_BOTTOM = 560;
export const NORTH_BASELINE = NORTH_SIDEWALK_TOP;
export const SOUTH_BASELINE = SOUTH_SIDEWALK_BOTTOM;
export const HIGHLAND_LEFT = 480;
export const HIGHLAND_RIGHT = 560;

function chakraSet(pattern: ChakraState[]): Record<ChakraName, ChakraState> {
  const out = {} as Record<ChakraName, ChakraState>;
  CHAKRA_ORDER.forEach((name, i) => {
    out[name] = pattern[i];
  });
  return out;
}

export const NPCS: SoulProfile[] = [
  {
    id: "danny",
    name: "Danny Rios",
    occupation: 'Costumed Character Performer ("Robo-Hero")',
    archetype: "Costumed Street Performer",
    age: 34,
    maslow: "Level 1 — Physiological (fighting for basic survival)",
    emotion: "Grim determination behind a painted-on smile",
    aura: "#d98a3a",
    narrative:
      "Three failed auditions this year. The suit pays the rent the way the craft never did. He tells himself it's temporary, the way he has for six years.",
    chakras: chakraSet([
      "blocked",
      "imbalanced",
      "blocked",
      "imbalanced",
      "blocked",
      "imbalanced",
      "blocked",
    ]),
    row: "north",
    xMin: 100,
    xMax: 320,
    speed: 26,
  },
  {
    id: "trish",
    name: "Trish Anderson",
    occupation: "Tourist, Dayton, Ohio",
    archetype: "Tourist",
    age: 29,
    maslow: "Level 3 — Belonging (craving connection, on the trip of a lifetime)",
    emotion: "Wide-eyed wonder, edging toward a peak experience",
    aura: "#eaf3ff",
    narrative:
      "She has wanted to stand on this sidewalk since she was eleven. For a few seconds outside the Chinese Theatre, her whole chest went quiet.",
    chakras: chakraSet([
      "open",
      "open",
      "imbalanced",
      "open",
      "imbalanced",
      "imbalanced",
      "imbalanced",
    ]),
    row: "north",
    xMin: 640,
    xMax: 1050,
    speed: 18,
  },
  {
    id: "frank",
    name: "Frank Castellano",
    occupation: "Freelance Photographer",
    archetype: "Paparazzi",
    age: 47,
    maslow: "Level 4 — Esteem (chasing recognition through someone else's fame)",
    emotion: "Predatory anticipation",
    aura: "#c94d2c",
    narrative:
      "He hasn't sold a real cover shot in eight months. He's stopped calling it stalking, even in his own head.",
    chakras: chakraSet([
      "imbalanced",
      "blocked",
      "imbalanced",
      "blocked",
      "imbalanced",
      "open",
      "blocked",
    ]),
    row: "south",
    xMin: 250,
    xMax: 560,
    speed: 22,
  },
  {
    id: "vivian",
    name: "Vivian Laurent",
    occupation: "Former Screen Actress (credits: 1990s)",
    archetype: "Faded Star",
    age: 61,
    maslow: "Level 2 — Safety (stable, but consumed by fear of being forgotten)",
    emotion: "Grief wearing a practiced smile",
    aura: "#8a8a8a",
    narrative:
      "People still recognize her, less every year. She still walks this block every afternoon, in case someone does.",
    chakras: chakraSet([
      "open",
      "imbalanced",
      "imbalanced",
      "blocked",
      "imbalanced",
      "imbalanced",
      "blocked",
    ]),
    row: "north",
    xMin: 1080,
    xMax: 1500,
    speed: 14,
  },
  {
    id: "bailey",
    name: "Bailey Okafor",
    occupation: "Server, Auditioning Nights",
    archetype: "Industry Aspirant",
    age: 24,
    maslow: "Level 4 — Esteem (esteem-starved, performing confidence she doesn't feel)",
    emotion: "Anxious optimism",
    aura: "#d9762e",
    narrative:
      "Her agent hasn't called back in nine days. She rehearses the callback she hasn't gotten yet, out loud, on her walk to work.",
    chakras: chakraSet([
      "open",
      "open",
      "imbalanced",
      "open",
      "blocked",
      "imbalanced",
      "imbalanced",
    ]),
    row: "south",
    xMin: 650,
    xMax: 980,
    speed: 24,
  },
  {
    id: "marcus",
    name: "Marcus Webb",
    occupation: "Rideshare Driver",
    archetype: "Local Commuter",
    age: 39,
    maslow: "Level 2 — Safety",
    emotion: "Tired, steady",
    aura: "#a9c7e8",
    narrative:
      "Just passing through this block on the way to the next fare. Nothing dramatic today.",
    chakras: chakraSet([
      "open",
      "open",
      "open",
      "imbalanced",
      "open",
      "open",
      "imbalanced",
    ]),
    row: "south",
    xMin: 60,
    xMax: 240,
    speed: 30,
  },
  {
    id: "priya",
    name: "Priya Chandra",
    occupation: "Souvenir Shop Clerk",
    archetype: "Local Worker",
    age: 21,
    maslow: "Level 3 — Belonging",
    emotion: "Bored contentment",
    aura: "#b7d8c2",
    narrative:
      "Another shift, another thousand tourists asking where the stars are. She still likes the job, mostly.",
    chakras: chakraSet([
      "open",
      "open",
      "open",
      "open",
      "imbalanced",
      "open",
      "imbalanced",
    ]),
    row: "north",
    xMin: 360,
    xMax: 560,
    speed: 16,
  },
  {
    id: "hank",
    name: "Hank Torres",
    occupation: "Walking Tour Guide",
    archetype: "Local Worker",
    age: 52,
    maslow: "Level 4 — Esteem",
    emotion: "Performing enthusiasm on autopilot",
    aura: "#e0c96a",
    narrative:
      "Twelve tours a week, same jokes, same facts. He still means it when he points out the stars, mostly.",
    chakras: chakraSet([
      "open",
      "open",
      "imbalanced",
      "open",
      "open",
      "imbalanced",
      "imbalanced",
    ]),
    row: "north",
    xMin: 1120,
    xMax: 1480,
    speed: 20,
  },
];

export const NORTH_BUILDINGS: Building[] = [
  { special: "tcl", x: 60 },
  { x: 350, width: 100, height: 74, side: "north", facadeColor: "#8a6a44", label: "SOUVENIRS" },
  {
    x: 600,
    width: 250,
    height: 150,
    side: "north",
    facadeColor: "#5b6b7a",
    label: "OVATION HOLLYWOOD",
    marquee: "DOLBY THEATRE",
    marqueeColor: "#c9962c",
  },
  { x: 900, width: 90, height: 80, side: "north", facadeColor: "#7a5b6a", label: "CANDY CO." },
  {
    x: 1030,
    width: 210,
    height: 140,
    side: "north",
    facadeColor: "#7a3b2e",
    label: "EL CAPITAN",
    marquee: "NOW PLAYING",
    marqueeColor: "#2e8f6b",
  },
  {
    x: 1290,
    width: 240,
    height: 110,
    side: "north",
    facadeColor: "#3c3c46",
    label: "MADAME TUSSAUDS",
    marquee: "WAX MUSEUM",
    marqueeColor: "#c9962c",
  },
];

export const SOUTH_BUILDINGS: Building[] = [
  { x: 60, width: 130, height: 90, side: "south", facadeColor: "#6a5a44", label: "T-SHIRTS" },
  { x: 220, width: 120, height: 80, side: "south", facadeColor: "#4a5a6a", label: "PIZZA" },
  { x: 600, width: 170, height: 100, side: "south", facadeColor: "#5c4a63", label: "TOUR TICKETS" },
  { x: 810, width: 130, height: 82, side: "south", facadeColor: "#6a4a4a", label: "GIFT SHOP" },
  { x: 1000, width: 150, height: 92, side: "south", facadeColor: "#4a6a52", label: "CAFE" },
  { x: 1220, width: 250, height: 100, side: "south", facadeColor: "#5a5040", label: "PARKING STRUCTURE" },
];
