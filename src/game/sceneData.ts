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
  ch?: number; // building height in character-heights (1 CH = 84 units)
  sprite?: string; // public/buildings/<sprite>.png facade art
  aspect?: number; // nominal w/h of the art (fallback until the image loads; live aspect wins)
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
// Every building sits its FEET on a ground line and grows UP (bottom-aligned, like any
// real street) — so a row's entrances align on one line and only the rooflines vary.
export const NORTH_BASELINE = NORTH_SIDEWALK_TOP; // far row: feet at the north sidewalk (1000)
// Near row: feet on a ground line in the foreground, below the south sidewalk. Set so the
// tallest near facade's roof reaches up to the sidewalk and shorter ones leave a plaza.
export const SOUTH_BASELINE = 1786; // near-row FEET line (bottom-aligned)

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

// ============================================================================
// REAL-ESTATE LAYOUT — buildings are authored as ordered LOTS on a frontage, and
// their on-screen x/width are computed at draw time by layoutFrontage(). Nothing is
// hand-placed: a frontage is a strip of buildable land between two cross-streets, and
// its buildings are PACKED shoulder-to-shoulder (a thin, even slightly negative seam) so
// the row reads as one continuous condensed wall — never scattered with dead lots between
// them. The leftover land is pushed to the OUTER edge (align "toward"), hugging the row
// against the Highland intersection so the block's heart is dense and the empty space
// falls off-screen. Each building's rendered width = ch·84·aspect where aspect is the live
// image ratio (or the nominal `aspect` fallback). Regenerate any facade at a new shape and
// the whole street re-packs itself tidy — zero manual coordinate math.
// ============================================================================

export interface Frontage {
  key: string;
  x0: number; // west edge of buildable land
  x1: number; // east edge of buildable land
  side: "north" | "south";
  baseY?: number; // overrides the side's default baseline (used by the back-street row)
  // Buildings always pack shoulder-to-shoulder; align only decides where the LEFTOVER
  // land goes. "toward" hugs the row against the Highland intersection (dense heart, empty
  // land pushed off-screen to the outer edge); "center" splits it; "left" pins to x0.
  align?: "toward" | "center" | "left";
  gap: number; // seam between neighbours — small (or negative) so facades read as one wall
  buildings: Building[]; // ordered west→east; x + width are assigned by layoutFrontage
}

// Rendered width of a building for a given art aspect (w/h).
export function buildingWidth(b: Building, aspect: number): number {
  return (b.ch ?? (b.height ?? 90) / 84) * 84 * aspect;
}

// Assign each building's x (left edge) + width (footprint) so the row fills its frontage.
// aspectOf resolves the live image ratio; falls back to the building's nominal `aspect`.
export function layoutFrontage(f: Frontage, aspectOf: (b: Building) => number): void {
  const n = f.buildings.length;
  if (n === 0) return;
  const ws = f.buildings.map((b) => buildingWidth(b, aspectOf(b)));
  const total = ws.reduce((a, c) => a + c, 0);
  const span = f.x1 - f.x0;
  const align = f.align ?? "center";

  // Buildings sit shoulder-to-shoulder separated only by `gap` (a thin/negative seam) so
  // the row reads as one continuous wall. If the run is too wide for the strip, the seam
  // shrinks until it fits rather than overflowing.
  let gap = f.gap;
  const usedAt = (g: number) => total + g * (n - 1);
  if (usedAt(gap) > span && n > 1) gap = (span - total) / (n - 1);
  const usedFinal = usedAt(gap);

  // Where the leftover land goes. "toward" hugs the Highland intersection: east strips
  // (x0 just east of Highland) pin to x0; west strips (x1 just west of Highland) pin the
  // row's right edge to x1. We detect the side by which bound sits nearer Highland center.
  let x: number;
  if (align === "toward") {
    const highlandCenter = (HIGHLAND_SIDEWALK_LEFT + HIGHLAND_SIDEWALK_RIGHT) / 2;
    const westStrip = Math.abs(f.x1 - highlandCenter) < Math.abs(f.x0 - highlandCenter);
    x = westStrip ? f.x1 - usedFinal : f.x0;
  } else if (align === "left") {
    x = f.x0;
  } else {
    x = f.x0 + (span - usedFinal) / 2;
  }

  for (let i = 0; i < n; i++) {
    f.buildings[i].width = ws[i];
    f.buildings[i].x = x;
    x += ws[i] + gap;
  }
}

// Buildable-land bounds: the block is split by the Highland Ave corridor into a WEST
// segment and a much larger EAST segment (matching the real intersection).
const LOT_MARGIN = 60;
const WEST_X0 = LOT_MARGIN;
const WEST_X1 = HIGHLAND_SIDEWALK_LEFT - 30; // 1337
const EAST_X0 = HIGHLAND_SIDEWALK_RIGHT + 30; // 1657
const EAST_X1 = WORLD_W - LOT_MARGIN; // 5040

// A landmark lot: art + fictional signage + character-height scale + nominal aspect.
function lot(sprite: string, ch: number, aspect: number, label: string, marquee: string, marqueeColor: string, side: "north" | "south"): Building {
  return { x: 0, ch, aspect, side, sprite, label, marquee, marqueeColor };
}
// A plain filler lot (shop / apartment / parking): art + scale + aspect only.
function fill(sprite: string, ch: number, aspect: number, side: "north" | "south", baseY?: number): Building {
  return { x: 0, ch, aspect, side, sprite, baseY };
}

// ---- North side of Hollywood Blvd (the hero row, facades grow UP toward the sky) ----
export const NORTH_FRONTAGES: Frontage[] = [
  {
    key: "n-west", x0: WEST_X0, x1: WEST_X1, side: "north", align: "toward", gap: -18,
    buildings: [
      lot("madame-rousseau", 5, 0.918, "MADAME ROUSSEAU'S", "WAX MUSEUM", "#c9962c", "north"),
      lot("jade-pagoda", 7, 1.159, "JADE PAGODA", "THEATRE", "#c9a34a", "north"),
    ],
  },
  {
    key: "n-east", x0: EAST_X0, x1: EAST_X1, side: "north", align: "toward", gap: -18,
    buildings: [
      lot("overture-hollywood", 6, 2.004, "OVERTURE HOLLYWOOD", "SHOPS · DINE", "#c9962c", "north"),
      lot("vantage-theatre", 6, 0.979, "VANTAGE", "THEATRE", "#c9a34a", "north"),
      lot("thunderclap-cafe", 4.5, 1.148, "THUNDERCLAP", "ROCK CAFE", "#e0b23a", "north"),
      lot("crescendo-hotel", 11, 0.628, "CRESCENDO", "HOTEL", "#d8b25a", "north"),
      lot("meridian-hotel", 10, 0.304, "MERIDIAN", "HOTEL", "#d8a24a", "north"),
    ],
  },
];

// ---- South side of Hollywood Blvd (near row, facades grow DOWN toward the camera) ----
export const SOUTH_FRONTAGES: Frontage[] = [
  {
    key: "s-west", x0: WEST_X0, x1: WEST_X1, side: "south", align: "toward", gap: -18,
    buildings: [
      lot("sovereign-hotel", 7, 0.728, "SOVEREIGN", "HOTEL", "#d8b25a", "south"),
      fill("shop-slice", 2.6, 1.72, "south"),
      fill("shop-cage", 2.6, 1.631, "south"),
    ],
  },
  {
    key: "s-east", x0: EAST_X0, x1: EAST_X1, side: "south", align: "toward", gap: -18,
    buildings: [
      lot("wonderland-theatre", 6.5, 0.832, "WONDERLAND", "THEATRE", "#e0b23a", "south"),
      lot("glamour-archive", 5, 0.891, "GLAMOUR ARCHIVE", "MUSEUM", "#d8b25a", "south"),
      lot("blackwood-odditorium", 5, 1.2, "BLACKWOOD'S", "ODDITORIUM", "#b06fd8", "south"),
      lot("apex-records", 5, 0.668, "APEX WORLD RECORDS", "MUSEUM", "#e0b23a", "south"),
      lot("marchetti-vane-grill", 4, 0.737, "MARCHETTI & VANE", "GRILL · 1919", "#d8b25a", "south"),
      lot("reel-page-bookshop", 3.5, 0.797, "THE REEL PAGE", "BOOKS", "#e0b23a", "south"),
      fill("shop-cage", 2.6, 1.631, "south"),
      fill("shop-slice", 2.6, 1.72, "south"),
    ],
  },
];

// ---- Residential back-street below the boulevard (apartments + parking, sliced art) ----
// Feet on a ground line behind (below) the near row, so the apartments bottom-align too.
const BACK_Y = 2140;
export const RES_FRONTAGES: Frontage[] = [
  {
    key: "res-west", x0: WEST_X0, x1: WEST_X1, side: "south", baseY: BACK_Y, align: "toward", gap: -10,
    buildings: [
      fill("apt-palm-court", 3.2, 1.733, "south", BACK_Y),
      fill("apt-sunset-arms", 3.2, 1.872, "south", BACK_Y),
      fill("parking-a", 1.7, 5.741, "south", BACK_Y),
    ],
  },
  {
    key: "res-east", x0: EAST_X0, x1: EAST_X1, side: "south", baseY: BACK_Y, align: "toward", gap: -10,
    buildings: [
      fill("apt-el-camino", 3.2, 1.603, "south", BACK_Y),
      fill("apt-corner-slice", 3.2, 1.4, "south", BACK_Y),
      fill("apt-vine-terrace", 3.2, 1.445, "south", BACK_Y),
      fill("parking-b", 1.7, 5.041, "south", BACK_Y),
      fill("apt-el-camino-2", 3.2, 1.359, "south", BACK_Y),
      fill("apt-palm-court", 3.2, 1.733, "south", BACK_Y),
      fill("apt-sunset-arms", 3.2, 1.872, "south", BACK_Y),
    ],
  },
];

// All frontages, in back-to-front paint order (north hero row is drawn behind the
// street; south near row + residential back-street in front). The renderer lays each
// out then draws it, so a swapped facade re-justifies its whole row automatically.
export const ALL_FRONTAGES: Frontage[] = [...NORTH_FRONTAGES, ...SOUTH_FRONTAGES, ...RES_FRONTAGES];

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
  ...genRow({ baseY: 2000, side: "south", count: 52, startX: -20, minW: 84, varW: 60, minH: 60, varH: 48, dim: 0.5, palette: RESI_PALETTE, gapBase: 18, gapVar: 28 }),
];
