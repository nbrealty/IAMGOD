// Hollywood & Highland scene GEOMETRY — building footprints, street layout, and the
// shared spatial constants the renderer reads. NPC souls live in src/soul/.
//
// Phase 2b: the world is now a walkable SQUARE. Hollywood Blvd runs E–W through the
// vertical middle; Highland Ave runs N–S through it. Together they form a "+" of
// walkable street corridors (road + flanking sidewalks). The 14 fictionalized
// landmarks fill the four quadrant CORNERS of that cross; the player can now walk both
// axes and turn the corner at the intersection — not just left/right. Every building
// has a fixed slot (with a `ch` height and a `sprite` hook) so real facade art drops
// straight into a known position in the next chunk.

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
  // Phase 2b: the character-height scale (1 CH = one standing character = 84 units) this
  // facade was drawn to, and the drop-in facade art. `sprite` names public/buildings/<stem>.png;
  // when present and loaded the renderer composites it in place of the code-drawn block,
  // else the placeholder shows. Left unset until the art chunk keys + places the files.
  ch?: number;
  sprite?: string;
}

// The whole block. Bigger than any phone viewport → the camera pans/zooms within it.
export const WORLD_W = 3400;
export const WORLD_H = 2000;

// ---- Hollywood Blvd (horizontal, main street through the vertical middle) ----
export const ROAD_TOP = 940;
export const ROAD_BOTTOM = 1060;
export const NORTH_SIDEWALK_TOP = 880; // north blvd sidewalk: [880, ROAD_TOP]
export const SOUTH_SIDEWALK_TOP = ROAD_BOTTOM;
export const SOUTH_SIDEWALK_BOTTOM = 1120; // south blvd sidewalk: [ROAD_BOTTOM, 1120]
export const NORTH_BASELINE = NORTH_SIDEWALK_TOP; // north storefronts grow upward from here
export const SOUTH_BASELINE = SOUTH_SIDEWALK_BOTTOM; // south storefronts grow downward from here

// ---- Highland Ave (vertical cross street, full height) ----
export const HIGHLAND_LEFT = 1440; // road band
export const HIGHLAND_RIGHT = 1560;
export const HIGHLAND_SIDEWALK_LEFT = 1380; // sidewalks flank the road
export const HIGHLAND_SIDEWALK_RIGHT = 1620;

// ---- walkability: the player/NPCs may move anywhere in the street "+" corridor
// (either the boulevard band, any x — or the Highland band, any y), but not into the
// building quadrants. At the intersection both bands overlap, so you turn the corner.
export function canWalk(x: number, y: number): boolean {
  if (x < 20 || x > WORLD_W - 20 || y < 20 || y > WORLD_H - 20) return false;
  const onBlvd = y >= NORTH_SIDEWALK_TOP && y <= SOUTH_SIDEWALK_BOTTOM;
  const onHighland = x >= HIGHLAND_SIDEWALK_LEFT && x <= HIGHLAND_SIDEWALK_RIGHT;
  return onBlvd || onHighland;
}

// Frontage sidewalk lines the cast stands/patrols on.
export const NORTH_FRONTAGE_Y = NORTH_SIDEWALK_TOP + 28; // ~908
export const SOUTH_FRONTAGE_Y = ROAD_BOTTOM + 28; // ~1088

// ---- the 14 fictionalized landmarks, one fixed slot each ----
// North frontage: base at NORTH_BASELINE, grows UP, facade faces the boulevard (down to
// camera). West of Highland, then the two intersection towers, then east of Highland.
export const NORTH_BUILDINGS: Building[] = [
  {
    x: 40, width: 520, height: 560, ch: 7, side: "north",
    facadeColor: "#7a2320", roofColor: "#1f5c47",
    label: "JADE PAGODA", marquee: "THEATRE", marqueeColor: "#c9a34a", sprite: "jade-pagoda",
  },
  {
    x: 600, width: 460, height: 520, ch: 6.5, side: "north",
    facadeColor: "#b89b52", roofColor: "#8a6a2c",
    label: "WONDERLAND", marquee: "THEATRE", marqueeColor: "#e0b23a", sprite: "wonderland-theatre",
  },
  {
    x: 1100, width: 220, height: 800, ch: 10, side: "north",
    facadeColor: "#2f3540", roofColor: "#20242c",
    label: "MERIDIAN", marquee: "HOTEL", marqueeColor: "#d8a24a", sprite: "meridian-hotel",
  },
  {
    x: 1660, width: 240, height: 800, ch: 11, side: "north",
    facadeColor: "#c8b48a", roofColor: "#9a8258",
    label: "CRESCENDO", marquee: "HOTEL", marqueeColor: "#d8b25a", sprite: "crescendo-hotel",
  },
  {
    x: 1940, width: 600, height: 500, ch: 6, side: "north",
    facadeColor: "#5b5546", roofColor: "#3f3a30",
    label: "OVERTURE HOLLYWOOD", marquee: "SHOPS · DINE", marqueeColor: "#c9962c", sprite: "overture-hollywood",
  },
  {
    x: 2580, width: 440, height: 500, ch: 6, side: "north",
    facadeColor: "#4a5560", roofColor: "#333b44",
    label: "VANTAGE", marquee: "THEATRE", marqueeColor: "#c9a34a", sprite: "vantage-theatre",
  },
  {
    x: 3060, width: 300, height: 420, ch: 5, side: "north",
    facadeColor: "#c79aa0", roofColor: "#9a6f76",
    label: "GLAMOUR ARCHIVE", marquee: "MUSEUM", marqueeColor: "#d8b25a", sprite: "glamour-archive",
  },
];

// South frontage: base at SOUTH_BASELINE, grows DOWN, facade faces the boulevard (up).
export const SOUTH_BUILDINGS: Building[] = [
  {
    x: 40, width: 520, height: 560, ch: 7, side: "south",
    facadeColor: "#c9b78a", roofColor: "#9a8258",
    label: "SOVEREIGN", marquee: "HOTEL", marqueeColor: "#d8b25a", sprite: "sovereign-hotel",
  },
  {
    x: 600, width: 300, height: 336, ch: 4, side: "south",
    facadeColor: "#233a30", roofColor: "#16261f",
    label: "MARCHETTI & VANE", marquee: "GRILL · 1919", marqueeColor: "#d8b25a", sprite: "marchetti-vane-grill",
  },
  {
    x: 940, width: 300, height: 300, ch: 3.5, side: "south",
    facadeColor: "#5a6a3a", roofColor: "#3f4a28",
    label: "THE REEL PAGE", marquee: "BOOKS", marqueeColor: "#e0b23a", sprite: "reel-page-bookshop",
  },
  {
    x: 1660, width: 440, height: 378, ch: 4.5, side: "south",
    facadeColor: "#7a3b2e", roofColor: "#4a2019",
    label: "THUNDERCLAP", marquee: "ROCK CAFE", marqueeColor: "#e0b23a", sprite: "thunderclap-cafe",
  },
  {
    x: 2140, width: 440, height: 420, ch: 5, side: "south",
    facadeColor: "#3a3346", roofColor: "#241f2c",
    label: "BLACKWOOD'S", marquee: "ODDITORIUM", marqueeColor: "#b06fd8", sprite: "blackwood-odditorium",
  },
  {
    x: 2620, width: 360, height: 420, ch: 5, side: "south",
    facadeColor: "#3f4a6a", roofColor: "#2a3348",
    label: "APEX WORLD RECORDS", marquee: "MUSEUM", marqueeColor: "#e0b23a", sprite: "apex-records",
  },
  {
    x: 3020, width: 340, height: 420, ch: 5, side: "south",
    facadeColor: "#8a7a6a", roofColor: "#5f5346",
    label: "MADAME ROUSSEAU'S", marquee: "WAX MUSEUM", marqueeColor: "#c9962c", sprite: "madame-rousseau",
  },
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
    // leave the Highland Ave corridor clear
    if (!(x + w > HIGHLAND_SIDEWALK_LEFT - 10 && x < HIGHLAND_SIDEWALK_RIGHT + 10)) {
      out.push({
        x,
        width: w,
        height: h,
        side: o.side,
        baseY: o.baseY,
        facadeColor: o.palette[(i + o.baseY) % o.palette.length],
        dim: o.dim,
      });
    }
    x += w + o.gapBase + ((i * 23) % o.gapVar);
    if (x > WORLD_W + 40) break;
  }
  return out;
}

const BACKDROP_PALETTE = ["#39414e", "#454b56", "#4b4038", "#3f4a4a", "#4e463a", "#424a58"];
const RESI_PALETTE = ["#5a4a3a", "#6a5544", "#4e4436", "#63513f", "#574a3c", "#4a4032"];

// Receding skyline high above the north frontage (fills the gaps between the tall
// landmark rooftops with distant, dimmer blocks).
export const BACKDROP_BUILDINGS: Building[] = [
  ...genRow({ baseY: 300, side: "north", count: 30, startX: -60, minW: 120, varW: 100, minH: 200, varH: 120, dim: 0.5, palette: BACKDROP_PALETTE, gapBase: 10, gapVar: 30 }),
  ...genRow({ baseY: 480, side: "north", count: 30, startX: -30, minW: 100, varW: 90, minH: 150, varH: 100, dim: 0.72, palette: BACKDROP_PALETTE, gapBase: 12, gapVar: 26 }),
];

// Residential band below the south frontage.
export const RESIDENTIAL_BUILDINGS: Building[] = [
  ...genRow({ baseY: 1780, side: "south", count: 30, startX: -40, minW: 100, varW: 70, minH: 100, varH: 70, dim: 0.85, palette: RESI_PALETTE, gapBase: 16, gapVar: 30 }),
  ...genRow({ baseY: 1920, side: "south", count: 34, startX: -20, minW: 84, varW: 60, minH: 64, varH: 52, dim: 0.68, palette: RESI_PALETTE, gapBase: 18, gapVar: 28 }),
];
