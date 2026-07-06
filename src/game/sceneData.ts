// Hollywood & Highland scene GEOMETRY — building footprints, street layout, and the
// shared spatial constants the renderer reads. NPC souls live in src/soul/.
//
// Phase 2b: the world is a walkable SQUARE. Hollywood Blvd runs E–W through the vertical
// middle; Highland Ave runs N–S through it — a "+" of walkable street corridors.
//
// The 14 fictionalized landmarks are placed at their REAL Hollywood & Highland positions
// (correct side of the boulevard + east/west of Highland) and spaced by their actual
// rendered widths so nothing overlaps:
//   NORTH, west of Highland: Madame Rousseau's (Tussauds), Jade Pagoda (Chinese)
//   NORTH, at/east of Highland: Overture (Ovation), Vantage (Dolby), Thunderclap
//     (Hard Rock), Crescendo (Loews), Meridian (W, far east)
//   SOUTH, west of Highland: Sovereign (Roosevelt)
//   SOUTH, east of Highland: Wonderland (El Capitan), Glamour (Hollywood Museum),
//     Blackwood's (Ripley's), Apex (Guinness), Marchetti & Vane (Musso), Reel Page
//     (Larry Edmunds)
// Each slot carries a `ch` height and a `sprite` hook; the renderer sizes the facade to
// ch × 84 units and composites public/buildings/<sprite>.png in place.

export interface Building {
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
  baseY?: number;
  dim?: number;
  ch?: number;
  sprite?: string;
}

// The whole block. Bigger than any phone viewport → the camera pans/zooms within it.
export const WORLD_W = 5100;
export const WORLD_H = 2200;

// ---- Hollywood Blvd (horizontal, main street through the vertical middle) ----
export const ROAD_TOP = 1060;
export const ROAD_BOTTOM = 1180;
export const NORTH_SIDEWALK_TOP = 1000; // north blvd sidewalk: [1000, ROAD_TOP]
export const SOUTH_SIDEWALK_TOP = ROAD_BOTTOM;
export const SOUTH_SIDEWALK_BOTTOM = 1240; // south blvd sidewalk: [ROAD_BOTTOM, 1240]
export const NORTH_BASELINE = NORTH_SIDEWALK_TOP; // north storefronts grow upward from here
export const SOUTH_BASELINE = SOUTH_SIDEWALK_BOTTOM; // south storefronts grow downward from here

// ---- Highland Ave (vertical cross street, full height) ----
export const HIGHLAND_SIDEWALK_LEFT = 1367;
export const HIGHLAND_LEFT = 1427; // road band
export const HIGHLAND_RIGHT = 1567;
export const HIGHLAND_SIDEWALK_RIGHT = 1627;

// ---- walkability: walk anywhere in the street "+" corridor, not into a quadrant ----
export function canWalk(x: number, y: number): boolean {
  if (x < 20 || x > WORLD_W - 20 || y < 20 || y > WORLD_H - 20) return false;
  const onBlvd = y >= NORTH_SIDEWALK_TOP && y <= SOUTH_SIDEWALK_BOTTOM;
  const onHighland = x >= HIGHLAND_SIDEWALK_LEFT && x <= HIGHLAND_SIDEWALK_RIGHT;
  return onBlvd || onHighland;
}

// Frontage sidewalk lines the cast stands/patrols on.
export const NORTH_FRONTAGE_Y = NORTH_SIDEWALK_TOP + 28; // 1028
export const SOUTH_FRONTAGE_Y = ROAD_BOTTOM + 28; // 1208

// ---- the 14 landmarks at their real geographic slots (west → east) ----
// x/width are the on-screen footprint (width = ch·84 · image aspect), so adjacent
// facades sit side-by-side with a gap and never overlap.
export const NORTH_BUILDINGS: Building[] = [
  { x: 120, width: 386, height: 420, ch: 5, side: "north", facadeColor: "#8a7a6a", roofColor: "#5f5346", label: "MADAME ROUSSEAU'S", marquee: "WAX MUSEUM", marqueeColor: "#c9962c", sprite: "madame-rousseau" },
  { x: 596, width: 681, height: 588, ch: 7, side: "north", facadeColor: "#7a2320", roofColor: "#1f5c47", label: "JADE PAGODA", marquee: "THEATRE", marqueeColor: "#c9a34a", sprite: "jade-pagoda" },
  { x: 1717, width: 1010, height: 504, ch: 6, side: "north", facadeColor: "#5b5546", roofColor: "#3f3a30", label: "OVERTURE HOLLYWOOD", marquee: "SHOPS · DINE", marqueeColor: "#c9962c", sprite: "overture-hollywood" },
  { x: 2817, width: 493, height: 504, ch: 6, side: "north", facadeColor: "#4a5560", roofColor: "#333b44", label: "VANTAGE", marquee: "THEATRE", marqueeColor: "#c9a34a", sprite: "vantage-theatre" },
  { x: 3400, width: 434, height: 378, ch: 4.5, side: "north", facadeColor: "#7a3b2e", roofColor: "#4a2019", label: "THUNDERCLAP", marquee: "ROCK CAFE", marqueeColor: "#e0b23a", sprite: "thunderclap-cafe" },
  { x: 3924, width: 580, height: 924, ch: 11, side: "north", facadeColor: "#c8b48a", roofColor: "#9a8258", label: "CRESCENDO", marquee: "HOTEL", marqueeColor: "#d8b25a", sprite: "crescendo-hotel" },
  { x: 4594, width: 255, height: 840, ch: 10, side: "north", facadeColor: "#2f3540", roofColor: "#20242c", label: "MERIDIAN", marquee: "HOTEL", marqueeColor: "#d8a24a", sprite: "meridian-hotel" },
];

export const SOUTH_BUILDINGS: Building[] = [
  { x: 120, width: 428, height: 588, ch: 7, side: "south", facadeColor: "#c9b78a", roofColor: "#9a8258", label: "SOVEREIGN", marquee: "HOTEL", marqueeColor: "#d8b25a", sprite: "sovereign-hotel" },
  { x: 1717, width: 454, height: 546, ch: 6.5, side: "south", facadeColor: "#b89b52", roofColor: "#8a6a2c", label: "WONDERLAND", marquee: "THEATRE", marqueeColor: "#e0b23a", sprite: "wonderland-theatre" },
  { x: 2261, width: 374, height: 420, ch: 5, side: "south", facadeColor: "#c79aa0", roofColor: "#9a6f76", label: "GLAMOUR ARCHIVE", marquee: "MUSEUM", marqueeColor: "#d8b25a", sprite: "glamour-archive" },
  { x: 2725, width: 504, height: 420, ch: 5, side: "south", facadeColor: "#3a3346", roofColor: "#241f2c", label: "BLACKWOOD'S", marquee: "ODDITORIUM", marqueeColor: "#b06fd8", sprite: "blackwood-odditorium" },
  { x: 3319, width: 281, height: 420, ch: 5, side: "south", facadeColor: "#3f4a6a", roofColor: "#2a3348", label: "APEX WORLD RECORDS", marquee: "MUSEUM", marqueeColor: "#e0b23a", sprite: "apex-records" },
  { x: 3690, width: 248, height: 336, ch: 4, side: "south", facadeColor: "#233a30", roofColor: "#16261f", label: "MARCHETTI & VANE", marquee: "GRILL · 1919", marqueeColor: "#d8b25a", sprite: "marchetti-vane-grill" },
  { x: 4028, width: 234, height: 294, ch: 3.5, side: "south", facadeColor: "#5a6a3a", roofColor: "#3f4a28", label: "THE REEL PAGE", marquee: "BOOKS", marqueeColor: "#e0b23a", sprite: "reel-page-bookshop" },
];

// ---- ordinary storefronts / apartments (sliced from the filler sheets) ----
// A residential back-street row below the boulevard, plus shops dropped into the two big
// boulevard lots (SW between Sovereign and Highland, SE east of Reel Page). Same Building
// shape → renders through drawBuilding/drawBuildingSprite like the landmarks.
export const FILLER_BUILDINGS: Building[] = [
  // residential back-street row below the boulevard
  { x: 40, width: 342, height: 269, ch: 3.2, side: "south", sprite: "apt-palm-court", baseY: 1860 },
  { x: 442, width: 351, height: 269, ch: 3.2, side: "south", sprite: "apt-sunset-arms", baseY: 1860 },
  { x: 853, width: 784, height: 143, ch: 1.7, side: "south", sprite: "parking-a", baseY: 1860 },
  { x: 1697, width: 326, height: 269, ch: 3.2, side: "south", sprite: "apt-el-camino", baseY: 1860 },
  { x: 2083, width: 412, height: 269, ch: 3.2, side: "south", sprite: "apt-corner-slice", baseY: 1860 },
  { x: 2555, width: 413, height: 269, ch: 3.2, side: "south", sprite: "apt-vine-terrace", baseY: 1860 },
  { x: 3028, width: 784, height: 143, ch: 1.7, side: "south", sprite: "parking-b", baseY: 1860 },
  { x: 3872, width: 392, height: 269, ch: 3.2, side: "south", sprite: "apt-el-camino-2", baseY: 1860 },
  { x: 4324, width: 342, height: 269, ch: 3.2, side: "south", sprite: "apt-palm-court", baseY: 1860 },
  { x: 4726, width: 351, height: 269, ch: 3.2, side: "south", sprite: "apt-sunset-arms", baseY: 1860 },
  // SW boulevard lot (between Sovereign and Highland)
  { x: 600, width: 324, height: 218, ch: 2.6, side: "south", sprite: "shop-slice" },
  { x: 984, width: 334, height: 218, ch: 2.6, side: "south", sprite: "shop-cage" },
  // SE boulevard lot (east of Reel Page)
  { x: 4320, width: 334, height: 218, ch: 2.6, side: "south", sprite: "shop-cage" },
  { x: 4714, width: 324, height: 218, ch: 2.6, side: "south", sprite: "shop-slice" },
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

// Receding skyline high above the north frontage.
export const BACKDROP_BUILDINGS: Building[] = [
  ...genRow({ baseY: 300, side: "north", count: 46, startX: -60, minW: 120, varW: 100, minH: 200, varH: 120, dim: 0.5, palette: BACKDROP_PALETTE, gapBase: 10, gapVar: 30 }),
  ...genRow({ baseY: 520, side: "north", count: 46, startX: -30, minW: 100, varW: 90, minH: 150, varH: 100, dim: 0.72, palette: BACKDROP_PALETTE, gapBase: 12, gapVar: 26 }),
];

// Residential band: the sliced apartment sprites in FILLER_BUILDINGS are the real
// residential row now, so the procedural blocks are retired (they only peeked around the
// keyed apartments as boxy halos). One very dim, distant row is kept far behind for depth.
export const RESIDENTIAL_BUILDINGS: Building[] = [
  ...genRow({ baseY: 2140, side: "south", count: 52, startX: -20, minW: 84, varW: 60, minH: 60, varH: 48, dim: 0.5, palette: RESI_PALETTE, gapBase: 18, gapVar: 28 }),
];
