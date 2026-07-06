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
  // How the facade meets its ground line at baseY. true = feet ON the line, grows UP
  // (far/north row + the residential houses). false = street-front (top) ON the line,
  // hangs DOWN into the foreground (near/south row — the mirror). Defaults by side.
  growUp?: boolean;
}

// The whole DISTRICT — the real Hollywood Blvd Commercial & Entertainment District,
// 6200–7000 (Sycamore → Gower), tiled as a grid of blocks. Far wider than any phone
// viewport → the camera pans/zooms within it.
export const WORLD_W = 17200;
export const WORLD_H = 2200;

// ---- Hollywood Blvd (the horizontal spine through the vertical middle) ----
export const ROAD_TOP = 1060;
export const ROAD_BOTTOM = 1240; // 180u of asphalt
export const NORTH_SIDEWALK_TOP = 1000; // north blvd sidewalk: [1000, ROAD_TOP]
// The near (south) sidewalk is the FOREGROUND walkway the near row's bases sit on, below
// the near buildings so they grow UP from it toward the road but stop at the asphalt.
export const SOUTH_SIDEWALK_TOP = 1790;
export const SOUTH_SIDEWALK_BOTTOM = 1850;
export const NORTH_BASELINE = NORTH_SIDEWALK_TOP; // far row: base ON the north sidewalk (1000)
export const SOUTH_BASELINE = SOUTH_SIDEWALK_TOP; // near row: base ON the foreground sidewalk (1790)

// ---- Cross streets (vertical N–S), west → east, at their real district order ----
export interface CrossStreet { name: string; x: number; }
export const CS_ROAD_HALF = 90; // half the asphalt width of a cross street
export const CS_WALK = 60; // sidewalk flanking each side of a cross street
export const CS_HALF = CS_ROAD_HALF + CS_WALK; // 150: centre → outer sidewalk edge
// Real cross-street order W→E (addresses decrease eastward: 7000 → 6100). Positions are
// roughly proportional to the real spacing; the Highland→McCadden block is widened to hold
// the big Ovation complex. No streets that aren't actually in the district.
export const CROSS_STREETS: CrossStreet[] = [
  { name: "LA BREA", x: 700 },
  { name: "ORANGE", x: 2200 },
  { name: "HIGHLAND", x: 3700 },
  { name: "McCADDEN", x: 6850 },
  { name: "LAS PALMAS", x: 8050 },
  { name: "CHEROKEE", x: 9150 },
  { name: "WILCOX", x: 10150 },
  { name: "CAHUENGA", x: 11150 },
  { name: "IVAR", x: 12150 },
  { name: "VINE", x: 13350 },
  { name: "ARGYLE", x: 14550 },
  { name: "EL CENTRO", x: 15550 },
  { name: "GOWER", x: 16550 },
];

// ---- walkability: the Blvd (north sidewalk+road band and the foreground south walk, full
// width) joined by every cross-street corridor (full height). A block's buildings sit in
// the gaps between; the player walks the Blvd and turns down any cross street. ----
export function canWalk(x: number, y: number): boolean {
  if (x < 20 || x > WORLD_W - 20 || y < 20 || y > WORLD_H - 20) return false;
  const onNorthBand = y >= NORTH_SIDEWALK_TOP && y <= ROAD_BOTTOM;
  const onSouthWalk = y >= SOUTH_SIDEWALK_TOP && y <= SOUTH_SIDEWALK_BOTTOM;
  if (onNorthBand || onSouthWalk) return true;
  for (const cs of CROSS_STREETS) {
    if (x >= cs.x - CS_HALF && x <= cs.x + CS_HALF) return true;
  }
  return false;
}

// Frontage sidewalk lines the cast stands/patrols on.
export const NORTH_FRONTAGE_Y = NORTH_SIDEWALK_TOP + 28; // 1028
export const SOUTH_FRONTAGE_Y = SOUTH_SIDEWALK_TOP + 28; // 1818 — foreground walk at the near bases

// ============================================================================
// REAL-ESTATE LAYOUT — a frontage is one block face (the buildable land between two cross
// streets, one side of the Blvd). Its buildings are an ordered west→east list; layoutFrontage
// assigns each x + width so the row centres in the face with a gap between neighbours.
// Rendered width = ch·84·aspect, so swapping a facade re-flows its block automatically.
// ============================================================================

export interface Frontage {
  key: string;
  x0: number; // west edge of the block face
  x1: number; // east edge of the block face
  side: "north" | "south";
  baseY?: number; // overrides the side's default baseline (the back-street row)
  align?: "center" | "left"; // where the leftover land goes
  gap: number; // seam between neighbours
  buildings: Building[]; // ordered west→east; x + width assigned by layoutFrontage
}

// Rendered width of a building for a given art aspect (w/h).
export function buildingWidth(b: Building, aspect: number): number {
  return (b.ch ?? (b.height ?? 90) / 84) * 84 * aspect;
}

// Assign each building's x (left edge) + width so the row fills its block face.
export function layoutFrontage(f: Frontage, aspectOf: (b: Building) => number): void {
  const n = f.buildings.length;
  if (n === 0) return;
  const ws = f.buildings.map((b) => buildingWidth(b, aspectOf(b)));
  const total = ws.reduce((a, c) => a + c, 0);
  const span = f.x1 - f.x0;
  let gap = f.gap;
  const usedAt = (g: number) => total + g * (n - 1);
  if (usedAt(gap) > span && n > 1) gap = (span - total) / (n - 1); // too wide → shrink seam
  const usedFinal = usedAt(gap);
  let x = f.align === "left" ? f.x0 : f.x0 + (span - usedFinal) / 2;
  for (let i = 0; i < n; i++) {
    f.buildings[i].width = ws[i];
    f.buildings[i].x = x;
    x += ws[i] + gap;
  }
}

// A landmark lot: art + fictional signage + character-height scale + nominal aspect.
function lot(sprite: string, ch: number, aspect: number, label: string, marquee: string, marqueeColor: string, side: "north" | "south"): Building {
  return { x: 0, ch, aspect, side, sprite, label, marquee, marqueeColor };
}
// A plain filler lot (shop / apartment / parking): art + scale + aspect only.
function fill(sprite: string, ch: number, aspect: number, side: "north" | "south", baseY?: number, growUp?: boolean): Building {
  return { x: 0, ch, aspect, side, sprite, baseY, growUp };
}

// ---- the 14 keyed landmark facades, keyed by sprite stem (ch / aspect / signage) ----
type LmSpec = { ch: number; aspect: number; label: string; marquee: string; mc: string };
const LANDMARKS: Record<string, LmSpec> = {
  "sovereign-hotel": { ch: 7, aspect: 0.728, label: "SOVEREIGN", marquee: "HOTEL", mc: "#d8b25a" },
  "madame-rousseau": { ch: 5, aspect: 0.918, label: "MADAME ROUSSEAU'S", marquee: "WAX MUSEUM", mc: "#c9962c" },
  "jade-pagoda": { ch: 7, aspect: 1.159, label: "JADE PAGODA", marquee: "THEATRE", mc: "#c9a34a" },
  "overture-hollywood": { ch: 6, aspect: 2.004, label: "OVERTURE HOLLYWOOD", marquee: "SHOPS · DINE", mc: "#c9962c" },
  "vantage-theatre": { ch: 6, aspect: 0.979, label: "VANTAGE", marquee: "THEATRE", mc: "#c9a34a" },
  "wonderland-theatre": { ch: 6.5, aspect: 0.832, label: "WONDERLAND", marquee: "THEATRE", mc: "#e0b23a" },
  "glamour-archive": { ch: 5, aspect: 0.891, label: "GLAMOUR ARCHIVE", marquee: "MUSEUM", mc: "#d8b25a" },
  "thunderclap-cafe": { ch: 4.5, aspect: 1.148, label: "THUNDERCLAP", marquee: "ROCK CAFE", mc: "#e0b23a" },
  "blackwood-odditorium": { ch: 5, aspect: 1.2, label: "BLACKWOOD'S", marquee: "ODDITORIUM", mc: "#b06fd8" },
  "apex-records": { ch: 5, aspect: 0.668, label: "APEX WORLD RECORDS", marquee: "MUSEUM", mc: "#e0b23a" },
  "marchetti-vane-grill": { ch: 4, aspect: 0.737, label: "MARCHETTI & VANE", marquee: "GRILL · 1919", mc: "#d8b25a" },
  "reel-page-bookshop": { ch: 3.5, aspect: 0.797, label: "THE REEL PAGE", marquee: "BOOKS", mc: "#e0b23a" },
  "crescendo-hotel": { ch: 11, aspect: 0.628, label: "CRESCENDO", marquee: "HOTEL", mc: "#d8b25a" },
  "meridian-hotel": { ch: 10, aspect: 0.304, label: "MERIDIAN", marquee: "HOTEL", mc: "#d8a24a" },
};

// storefront fillers cycled through to pad each Blvd block face — the named fake
// businesses break up the repetition; the two generic slices add width variety.
const SHOP_FILL: [string, number, number][] = [
  ["shop-salon", 3.8, 0.867],
  ["shop-slice", 2.6, 1.72],
  ["shop-boutique", 3.8, 0.803],
  ["shop-cameras", 3.8, 0.797],
  ["shop-cage", 2.6, 1.631],
  ["shop-tacos", 3.8, 0.815],
  ["shop-records", 3.8, 0.885],
  ["shop-tattoo", 3.8, 0.814],
];
// a mid-rise apartment tower — only used on north faces (grows up from the north sidewalk
// with headroom; on the south row it would poke into the road).
const TOWER_FILL: [string, number, number] = ["apt-tower", 9, 0.361];
// residential back-street mix (short houses + apartments; no tower — it would overlap the
// near row's ground line).
const APT_FILL: [string, number, number][] = [
  ["house-casa", 2.9, 1.631],
  ["apt-el-camino", 3.2, 1.603],
  ["apt-corner-slice", 3.2, 1.4],
  ["apt-vine-terrace", 3.2, 1.445],
  ["house-casa", 2.9, 1.631],
  ["apt-el-camino-2", 3.2, 1.359],
  ["apt-palm-court", 3.2, 1.733],
  ["apt-sunset-arms", 3.2, 1.872],
];

// ---- which landmarks sit on which block (index = gap between CROSS_STREETS[i], [i+1]) ----
// Positions verified against real Hollywood Blvd addresses (odd = which side varies; sides
// are the documented ones). Empty faces fill with storefronts.
const PLACEMENT: { n?: string[]; s?: string[] }[] = [
  // 0  La Brea→Orange (7000–6900): Roosevelt 7000 S · Chinese 6925 + Tussauds 6933 N
  { n: ["madame-rousseau", "jade-pagoda"], s: ["sovereign-hotel"] },
  // 1  Orange→Highland (6900–6800): El Capitan 6838 N · Hollywood Museum (Max Factor) S
  { n: ["wonderland-theatre"], s: ["glamour-archive"] },
  // 2  Highland→McCadden (6800–6770): Ovation complex 6801 N (Dolby/Loews/Hard Rock) ·
  //    Ripley's 6780 + Guinness 6764 S
  { n: ["overture-hollywood", "vantage-theatre", "crescendo-hotel", "thunderclap-cafe"], s: ["blackwood-odditorium", "apex-records"] },
  {}, // 3  McCadden→Las Palmas (6770–6720): Egyptian 6712 S (no asset yet) → storefronts
  { s: ["marchetti-vane-grill"] }, // 4  Las Palmas→Cherokee (6720–6660): Musso & Frank 6667 S
  { s: ["reel-page-bookshop"] }, //   5  Cherokee→Wilcox (6660–6600): Larry Edmunds 6644 S
  {}, // 6  Wilcox→Cahuenga (6600–6500)
  {}, // 7  Cahuenga→Ivar (6500–6420)
  {}, // 8  Ivar→Vine (6420–6300)
  { n: ["meridian-hotel"] }, // 9  Vine→Argyle (6300–6250): W Hollywood 6250 N (Pantages 6233, no asset)
  {}, // 10 Argyle→El Centro (6250–6200)
  {}, // 11 El Centro→Gower (6200–6100)
];

const BLOCK_COUNT = CROSS_STREETS.length - 1;
const blockX0 = (i: number) => CROSS_STREETS[i].x + CS_HALF + 24;
const blockX1 = (i: number) => CROSS_STREETS[i + 1].x - CS_HALF - 24;

// Build one block face: place its landmarks (if any), then pad with storefronts until the
// face is roughly full, so the block reads as a continuous street with no dead lots.
function buildFace(i: number, side: "north" | "south", lmKeys: string[]): Frontage {
  const x0 = blockX0(i), x1 = blockX1(i);
  const target = x1 - x0;
  const gap = 34;
  const out: Building[] = [];
  let used = -gap;
  const push = (b: Building, w: number) => { out.push(b); used += w + gap; };
  for (const k of lmKeys) {
    const s = LANDMARKS[k];
    push(lot(k, s.ch, s.aspect, s.label, s.marquee, s.mc, side), s.ch * 84 * s.aspect);
  }
  const fills = side === "north" ? [...SHOP_FILL, TOWER_FILL] : SHOP_FILL;
  let fi = i; // vary the starting filler per block
  while (used < target - 260) {
    const [sp, ch, asp] = fills[fi % fills.length];
    fi++;
    push(fill(sp, ch, asp, side), ch * 84 * asp);
  }
  return { key: `b${i}-${side}`, x0, x1, side, align: "center", gap, buildings: out };
}

export const NORTH_FRONTAGES: Frontage[] = Array.from({ length: BLOCK_COUNT }, (_, i) =>
  buildFace(i, "north", PLACEMENT[i]?.n ?? []),
);
export const SOUTH_FRONTAGES: Frontage[] = Array.from({ length: BLOCK_COUNT }, (_, i) =>
  buildFace(i, "south", PLACEMENT[i]?.s ?? []),
);

// ---- Residential back-street below the boulevard (apartments, one face per block) ----
const BACK_Y = 2140;
function buildResFace(i: number): Frontage {
  const x0 = blockX0(i), x1 = blockX1(i);
  const target = x1 - x0;
  const gap = 24;
  const out: Building[] = [];
  let used = -gap;
  let fi = i;
  while (used < target - 260) {
    const [sp, ch, asp] = APT_FILL[fi % APT_FILL.length];
    fi++;
    out.push(fill(sp, ch, asp, "south", BACK_Y, true));
    used += ch * 84 * asp + gap;
  }
  return { key: `res${i}`, x0, x1, side: "south", baseY: BACK_Y, align: "center", gap, buildings: out };
}
export const RES_FRONTAGES: Frontage[] = Array.from({ length: BLOCK_COUNT }, (_, i) => buildResFace(i));

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
  growUp?: boolean;
}

function genRow(o: RowOpts): Building[] {
  const out: Building[] = [];
  let x = o.startX;
  for (let i = 0; i < o.count; i++) {
    const w = o.minW + ((i * 37 + o.baseY) % o.varW);
    const h = o.minH + ((i * 53 + 7) % o.varH);
    // Never let a code-drawn block land on a cross-street corridor (no houses on the road).
    const onStreet = CROSS_STREETS.some((cs) => x + w > cs.x - CS_HALF && x < cs.x + CS_HALF);
    if (!onStreet) {
      out.push({
        x,
        width: w,
        height: h,
        side: o.side,
        baseY: o.baseY,
        facadeColor: o.palette[(i + o.baseY) % o.palette.length],
        dim: o.dim,
        growUp: o.growUp,
      });
    }
    x += w + o.gapBase + ((i * 23) % o.gapVar);
    if (x > WORLD_W + 40) break;
  }
  return out;
}

const BACKDROP_PALETTE = ["#39414e", "#454b56", "#4b4038", "#3f4a4a", "#4e463a", "#424a58"];
const RESI_PALETTE = ["#5a4a3a", "#6a5544", "#4e4436", "#63513f", "#574a3c", "#4a4032"];

// Receding skyline high above the north frontage (spans the full district width).
export const BACKDROP_BUILDINGS: Building[] = [
  ...genRow({ baseY: 300, side: "north", count: 160, startX: -60, minW: 120, varW: 100, minH: 200, varH: 120, dim: 0.5, palette: BACKDROP_PALETTE, gapBase: 10, gapVar: 30 }),
  ...genRow({ baseY: 520, side: "north", count: 175, startX: -30, minW: 100, varW: 90, minH: 150, varH: 100, dim: 0.72, palette: BACKDROP_PALETTE, gapBase: 12, gapVar: 26 }),
];

// One very dim, distant row far behind the residential back-street for depth.
export const RESIDENTIAL_BUILDINGS: Building[] = [
  ...genRow({ baseY: 2000, side: "south", count: 185, startX: -20, minW: 84, varW: 60, minH: 60, varH: 48, dim: 0.5, palette: RESI_PALETTE, gapBase: 18, gapVar: 28, growUp: true }),
];
