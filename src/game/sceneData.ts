// Hollywood & Highland scene GEOMETRY — building footprints and the shared spatial
// constants the renderer reads. NPC souls live in src/soul/.
//
// Phase 2: the world is now a full BLOCK, taller than the viewport, drawn edge to
// edge with no sky — a receding backdrop skyline above the boulevard and a
// residential band below it. The camera pans and zooms within WORLD_W × WORLD_H.

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
  // Phase 2: override the ground line a building sits on (for backdrop / residential
  // rows placed away from the main storefront baselines), and a depth-dim factor
  // (1 = front/full color, <1 = pushed back / darker).
  baseY?: number;
  dim?: number;
}

// The whole block. Bigger than any phone viewport → the camera pans/zooms within it.
export const WORLD_W = 1600;
export const WORLD_H = 1200;

// The boulevard sits in the lower-middle, leaving room for a backdrop skyline above.
export const ROAD_TOP = 720;
export const ROAD_BOTTOM = 820;
export const NORTH_SIDEWALK_TOP = 680;
export const SOUTH_SIDEWALK_TOP = ROAD_BOTTOM;
export const SOUTH_SIDEWALK_BOTTOM = 860;
export const NORTH_BASELINE = NORTH_SIDEWALK_TOP; // north storefronts grow upward from here
export const SOUTH_BASELINE = SOUTH_SIDEWALK_BOTTOM; // south storefronts grow downward from here
export const HIGHLAND_LEFT = 480;
export const HIGHLAND_RIGHT = 560;

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

// ---- procedural backdrop + residential rows (deterministic, no randomness) ----

interface RowOpts {
  baseY: number;
  side: "north" | "south";
  count: number;
  startX: number;
  minW: number;
  varW: number;
  minH: number;
  varH: number;
  dim: number;
  palette: string[];
  gapBase: number;
  gapVar: number;
}

function genRow(o: RowOpts): Building[] {
  const out: Building[] = [];
  let x = o.startX;
  for (let i = 0; i < o.count; i++) {
    const w = o.minW + ((i * 37 + o.baseY) % o.varW);
    const h = o.minH + ((i * 53 + 7) % o.varH);
    out.push({
      x,
      width: w,
      height: h,
      side: o.side,
      baseY: o.baseY,
      facadeColor: o.palette[(i + o.baseY) % o.palette.length],
      dim: o.dim,
    });
    x += w + o.gapBase + ((i * 23) % o.gapVar);
    if (x > WORLD_W + 40) break;
  }
  return out;
}

const BACKDROP_PALETTE = ["#39414e", "#454b56", "#4b4038", "#3f4a4a", "#4e463a", "#424a58"];
const RESI_PALETTE = ["#5a4a3a", "#6a5544", "#4e4436", "#63513f", "#574a3c", "#4a4032"];

// Two receding rows above the north storefronts (far + mid), then the storefronts.
export const BACKDROP_BUILDINGS: Building[] = [
  ...genRow({ baseY: 300, side: "north", count: 15, startX: -60, minW: 110, varW: 90, minH: 190, varH: 110, dim: 0.5, palette: BACKDROP_PALETTE, gapBase: 8, gapVar: 26 }),
  ...genRow({ baseY: 500, side: "north", count: 15, startX: -30, minW: 90, varW: 80, minH: 130, varH: 90, dim: 0.72, palette: BACKDROP_PALETTE, gapBase: 10, gapVar: 24 }),
];

// Residential band below the south storefronts.
export const RESIDENTIAL_BUILDINGS: Building[] = [
  ...genRow({ baseY: 1010, side: "south", count: 16, startX: -40, minW: 84, varW: 66, minH: 90, varH: 66, dim: 0.85, palette: RESI_PALETTE, gapBase: 14, gapVar: 28 }),
  ...genRow({ baseY: 1150, side: "south", count: 18, startX: -20, minW: 72, varW: 58, minH: 58, varH: 48, dim: 0.68, palette: RESI_PALETTE, gapBase: 16, gapVar: 26 }),
];
