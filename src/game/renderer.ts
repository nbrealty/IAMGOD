// The Hollywood & Highland renderer. Draws the dimetric city block to a canvas and
// runs the walk-cycle animation. Phase 2: a full pannable/zoomable block (camera
// transform, DPR-aware, fills the viewport) with a receding backdrop skyline and a
// residential band — no sky. NPCs draw a real chibi "spirit" sprite from
// /spirits/<id>.png when present, else a code-drawn fallback figure.

import {
  WORLD_W,
  WORLD_H,
  ROAD_TOP,
  ROAD_BOTTOM,
  NORTH_SIDEWALK_TOP,
  SOUTH_SIDEWALK_TOP,
  SOUTH_SIDEWALK_BOTTOM,
  NORTH_BASELINE,
  SOUTH_BASELINE,
  CROSS_STREETS,
  CS_ROAD_HALF,
  CS_HALF,
  NORTH_FRONTAGE_Y,
  SOUTH_FRONTAGE_Y,
  canWalk,
  NORTH_FRONTAGES,
  SOUTH_FRONTAGES,
  RES_FRONTAGES,
  ALL_FRONTAGES,
  layoutFrontage,
  BACKDROP_BUILDINGS,
  OVERTURE,
  type Building,
} from "./sceneData";
import type { Soul } from "../soul/types";
import { auraColor } from "../soul/appearance";
import { SoulEngine } from "../soul/engine";
import { type Camera, clampCamera, minZoomFor, screenToWorld, zoomAbout } from "./camera";

interface NpcRuntime {
  soul: Soul;
  x: number;
  y: number;
  dir: number;
  moving: boolean;
}

interface CarRuntime {
  x: number;
  y: number;
  dir: number;
  speed: number;
  type: string;
}

// Ambient background pedestrians (public/npc/ped_NNN.png) — autonomous crowd filler that walks
// the sidewalks. Not playable, not tappable; pure atmosphere behind the named cast.
interface AmbientPed {
  x: number;
  y: number;
  dir: number;
  speed: number;
  sprite: number; // index into the ped pool
  bob: number; // phase offset so they don't bob in sync
}
const AMBIENT_PED_COUNT = 54;
// The pedestrian pool holds both front- and back-view art. Ambient peds walk the sidewalks
// horizontally (mirrored L/R), so they must use only FRONT-facing sprites — otherwise a
// back-view slot renders as someone always walking away. Hand-classified from the pool montage
// (face/skin cluster high-center = front; hair-dominated head, no face = back); the remaining
// indices are back views (reserved for future toward/away wanderers).
const PED_FRONT = [
  0, 2, 5, 6, 9, 10, 15, 16, 19, 21, 23, 24, 26, 28, 31, 34, 37, 38, 42, 43,
];

// Every character (ambient ped + named soul) is normalized to one visible body height so the
// crowd reads as a consistent scale, regardless of how much empty frame the source art carries.
// We measure each sprite's non-transparent bounds once (spriteBounds) and scale so the content —
// head-top to sole — spans CHAR_BODY_H, then anchor the content bottom (feet) at y + FEET_DROP.
const CHAR_BODY_H = 78;
const FEET_DROP = 10;
// Overworld characters draw at most ~CHAR_BODY_H/contentFrac × maxZoom(3) × maxDPR(3) ≈ 830 device
// px tall. Source spirit PNGs are ~1400px, so the per-frame hi-quality downscale reads ~3× the
// pixels it needs. Cache a one-time 1024px-tall downscale for the OVERWORLD draw (comfortably above
// 830 → always a downscale, never soft). ROOMS use the full-res source (charScale blows the sprite
// up large), so the in-shop NPC stays pixel-sharp. Sprites already ≤1024 (peds, small art) are used
// as-is.
const OVERWORLD_MAX_H = 1024;
// Pixel dims of an image OR a canvas (canvas has no naturalWidth).
function srcW(x: CanvasImageSource): number { return (x as HTMLImageElement).naturalWidth || (x as HTMLCanvasElement).width; }
function srcH(x: CanvasImageSource): number { return (x as HTMLImageElement).naturalHeight || (x as HTMLCanvasElement).height; }

// One entry in the unified depth pass: an upright actor keyed by its foot-Y (baseline), with a
// closure that draws it. Sorted ascending → far (small y) drawn first, near (large y) on top.
interface Actor {
  y: number;
  draw: () => void;
}

// Overture Court "room" — a Gaia-style scene swap. Walk deep enough up the sparse walk-in court
// and the game crossfades into this single painted backdrop plate (overture-court-interior.png),
// a closer, richer view of the storefronts you browse. Room-local coordinates ARE the plate's
// pixel space (0..w, 0..h); the avatar is a normal foot-Y billboard walking the painted floor.
// An enterable AREA (scene-swap room). Its VIEW is declared per-area — the city is top-down and
// sky-less; special areas like the court room are head-on and CAN show a time-reactive sky/skyline.
// Adding a future rooftop / interior is then DATA (a new AREAS entry), not new render code. Room-local
// coordinates ARE the backdrop plate's pixel space (0..w, 0..h); the avatar walks the painted floor
// as a normal foot-Y billboard.
type ViewMode = "topdown" | "headon";
interface AreaView {
  id: string;
  view: ViewMode; // 'headon' = elevated plate that may show sky; 'topdown' = city (no sky)
  backdrop: string; // interior plate key (loaded from /${dir ?? 'overture'}/<backdrop>.<png|jpg>)
  dir?: string; // asset subfolder under public/ (default 'overture'); e.g. 'aguas' for the botanica
  jpg?: boolean; // load the plate as .jpg instead of .png (opaque interior plates compress far smaller)
  exitTo?: string | null; // where the walk-out exit goes: null/undefined = overworld, or a room id
  exitDown?: boolean; // walk-down off the front floor edge exits (default true). Set false where the
                      // natural exit is a doorway on a side (e.g. the back room's beaded curtain), so
                      // walking down doesn't drop you out somewhere the plate has no door.
  exitCurtainX?: number; // if set, reaching this x (a doorway on the right, e.g. the bead curtain)
                         // triggers the exitTo transition — the intuitive "walk back out the door" exit.
  entryZoom?: number; // cover-zoom multiplier for the initial framing (default 1.05); >1 frames closer
  charScale?: number; // multiplier on CHAR_BODY_H for people in this room (default 1). Rooms are
                      // small painted interiors, so a person must be MUCH bigger than the overworld
                      // body height to read at the furniture's scale (≈0.8×door / ≈2×chair-back).
  occupants?: { stem: string; x: number; y: number; scale?: number; faceLeft?: boolean }[]; // static room NPCs (billboards)
  // A foreground plate (transparent above it) drawn IN FRONT of occupants but behind the player —
  // e.g. the shop counter, so a keeper (occupant) reads as standing BEHIND it while the player
  // stands in front. Loaded from the same dir as the backdrop.
  foreground?: string;
  // A beaded-curtain doorway on the right: as the player nears it the plate swaps to the open art,
  // and stepping into it scene-swaps to `toArea` (the back consultation room).
  curtain?: { openX: number; openBackdrop: string; enterX: number; toArea: string };
  w: number; h: number; // plate pixel size = room-local world
  floorTop: number; floorBot: number; // walkable band (painted floor), near→far
  halfTop: number; halfBot: number; // floor half-width at back / front (a parallel trapezoid lane)
  cx: number;
  entryX: number; entryY: number; // where you arrive on entering
  scaleBack: number; // avatar depth scale at the back vs 1.0 front (mild, parallel-safe)
  skyPad?: number; // head-on: transparent SKY headroom (world px) above the plate, so the sun/moon
                   // have a band to arc through that sits BELOW the top HUD instead of behind it.
  floorTile?: string; // optional shared ground tile key
  sky?: { skyline: string; windows: string; rooflineY: number }; // head-on areas only; procedural sky + these
}
const AREAS: Record<string, AreaView> = {
  "overture-court": {
    id: "overture-court",
    view: "headon",
    backdrop: "overture-court-interior", // transparent-sky plate (1517×1037), floor baked in
    // world = skyPad sky headroom on top + the 1037-tall plate below it (h = 520 + 1037)
    w: 1517, h: 1557, skyPad: 520,
    floorTop: 1180, floorBot: 1530, // plaza floor band (plate coords + skyPad)
    halfTop: 520, halfBot: 650,
    cx: 758, entryX: 758, entryY: 1460,
    scaleBack: 0.72,
    sky: { skyline: "skyline-silhouette", windows: "skyline-windows", rooflineY: 880 },
  },
  // Yara's botanica — the FRONT room (retail). A cozy interior plate (1536×1024, opaque) shown
  // through the same clamped cover-zoom camera as the city, so it pans and never shows an edge.
  // The avatar walks a shallow floor lane in front of the counter; walking off the front edge
  // exits to the boulevard. Geometry tuned by eye against the plate.
  "aguas-front": {
    id: "aguas-front",
    view: "topdown", // interior: no sky / no celestial arc
    backdrop: "aguas-front",
    dir: "aguas", jpg: true,
    w: 1536, h: 1024,
    floorTop: 830, floorBot: 1005, // shallow walkable lane along the bottom, in front of the counter
    halfTop: 470, halfBot: 610,
    cx: 768, entryX: 780, entryY: 962,
    // COUNTER RULE: a person's WAIST must sit on the counter line. The floor is ~y960 and the
    // counter top ~y600, so an adult (waist ≈ half height) needs ~8× the overworld body height.
    scaleBack: 0.94, entryZoom: 1.0, charScale: 10.0,
    exitTo: null, // walk off the front edge → back out to the boulevard
    foreground: "aguas-front-counter", // the counter, drawn IN FRONT of Yara so she stands behind it
    occupants: [{ stem: "yara", x: 660, y: 912, scale: 1.0 }], // Yara BEHIND the counter — waist on the counter line, legs hidden
    // beaded curtain on the right → the back consultation room
    curtain: { openX: 1000, openBackdrop: "aguas-front-open", enterX: 1150, toArea: "aguas-back" },
  },
  // Yara's botanica — the BACK room (consultation). Open wooden floor foreground; the búzios
  // table + Oxum altar + Exu corner are baked into the plate. Walking off the front edge steps
  // back through the beaded curtain into the front botanica.
  "aguas-back": {
    id: "aguas-back",
    view: "topdown",
    backdrop: "aguas-back",
    dir: "aguas", jpg: true,
    w: 1536, h: 1024,
    floorTop: 560, floorBot: 980, // the open floor in front of the reading table
    halfTop: 360, halfBot: 640,
    cx: 768, entryX: 980, entryY: 860, // arrive just inside the curtain doorway (right), facing in
    scaleBack: 0.82, charScale: 5.5, // people sized to the chairs/table (~2× chair-back height)
    occupants: [{ stem: "yara_seated", x: 620, y: 640, scale: 1.0 }], // Yara seated at her reading table
    exitTo: "aguas-front", // back through the beaded curtain → the front botanica
    // The doorway is the beaded curtain on the RIGHT, NOT the south edge — so exit at the curtain x
    // (walk right into it) and disable the walk-down exit, which would drop you out at a wall.
    exitDown: false, exitCurtainX: 1160,
  },
};
const ROOM_FADE = 0.42; // seconds for a full fade-through-black scene swap
const COURT_ENTER_Y = OVERTURE.courtBackY + 200; // walk north of this line in the court → load room

// Vehicle sprites (public/vehicles/<type>.png), drawn feet(wheels)-anchored to a road lane.
// Art faces LEFT; a car travelling right (dir +1) is mirrored. `h` is the draw height in world
// units (width follows the loaded image aspect).
const VEHICLES: Record<string, number> = {
  sedan: 52,
  police: 52,
  convertible: 50,
  limo: 58,
  van: 64,
  bus: 60,
  tourbus: 60,
};
const VEHICLE_TYPES = Object.keys(VEHICLES);

// Street props (public/props/<name>.png), stood foot-anchored on a sidewalk. Value = draw
// height in world units (width follows the image aspect).
const PROP_H: Record<string, number> = {
  palm: 150,
  bench: 34,
  planter: 30,
  trashcan: 40,
  hydrant: 46,
  fountain: 62,
  "bike-rack": 30,
  newsstand: 116,
  "bus-shelter": 82,
  valet: 108,
  "traffic-signal": 120,
  stanchion: 46, // Overture court: velvet-rope stanchion (roped)
  "stanchion-post": 46, // rope-less post
  "urn-topiary": 66, // ornamental topiary urn
};
// Deterministic scatter along the sidewalks (palms weighted for that Hollywood look), with an
// occasional larger set-piece; traffic signals are placed separately at the intersections.
const PROP_SCATTER = ["palm", "bench", "palm", "planter", "hydrant", "palm", "trashcan", "planter", "bench", "palm"];
const PROP_SETPIECES = ["newsstand", "bus-shelter", "valet", "fountain", "bike-rack"];
const PROP_STEP = 152; // world-units between prop slots

const NORTH_SIDEWALK_BOTTOM = ROAD_TOP;
const TAP_THRESHOLD = 7; // css px of movement below which a pointer-up counts as a tap

// Boulevard street-lamp geometry (shared by the lamp prop pass and the night light pass).
const LAMP_STEP = 156; // world-units between posts along each sidewalk
const LAMP_POLE_H = 118; // post height up-screen from its foot on the sidewalk
const LAMP_ARM = 13; // half-spacing of the twin globes on the cross-arm

// Sprite art convention: a walking character faces RIGHT by default and is mirrored to face
// left. A couple of the provided sprites were drawn facing LEFT instead, so their mirror is
// inverted here — otherwise they'd turn the wrong way relative to travel.
const SPRITE_FACES_LEFT = new Set(["elizabeth", "nathaniel"]);

// ---- Ground tile textures (public/tiles) ----------------------------------------------
// Seamless daylight-lit textures repeated across each surface. TILE_WORLD is how many world
// units one copy of the image spans (so terrazzo squares / asphalt aggregate read at a real
// size regardless of source resolution). GROUND_FALLBACK is the flat tone used when the
// image hasn't loaded yet or when zoomed too far out to bother tiling.
const TILE_WORLD: Record<string, number> = {
  "asphalt.jpg": 200,
  "sidewalk.jpg": 120, // art carries a 4×4 brass grid → ~30u terrazzo squares
  "grass.jpg": 230,
  "soil.jpg": 140,
  "plaza.jpg": 210,
  "backlot.jpg": 420, // the paved ground behind the buildings — large so its mirror-tile barely repeats
};
const GROUND_FALLBACK: Record<string, string> = {
  "asphalt.jpg": "#33322f",
  "sidewalk.jpg": "#6b665d",
  "grass.jpg": "#3b4a2e",
  "soil.jpg": "#38301f",
  "plaza.jpg": "#b6a877",
  "backlot.jpg": "#2a2724",
};
// Below this zoom the whole district is in frame; skip pattern tiling and just flat-fill.
const TILE_ZOOM_GATE = 0.24;
// Below this zoom, characters are small enough that the smoky walk FX + leg-blur read as noise but
// still cost ~9 blits/drawImages per mover per frame — so skip them (contact + cast shadow stay).
const FX_ZOOM = 0.5;
// One smooth low-frequency mottle tile spans this many world units (large = broad, organic
// variation that never reads as a repeating stamp).
const NOISE_WORLD = 420;

// Road curb (sep-road-curb.png) — the strip cropped to just the concrete lip + its contact shadow,
// so it paints only the curb, never fill over the world sidewalk/asphalt. RCH = the band's world
// height; RCF = the fraction of the band where the sidewalk↔road boundary sits.
const RCH = 10;
const RCF = 0.625;
// Grass curb (sep-grass-curb.png) — sep-grass with the sidewalk terrazzo cropped off the top (so it
// can't bleed a mismatched patch onto the world sidewalk) but the curb + grass kept (the grass bleeds
// softly onto the world grass, a wanted effect). GCH = band world height; GCF = the seam fraction.
const GCH = 28;
const GCF = 0.654;
// Corner cut: how far short of the elbow each straight curb stops so the rounded corner asset fills
// the junction without the straights' square vertex poking past the arc. ≈ the corner's arc radius.
const RCUT = 30; // road corner arc radius ≈ 27u (+ margin)
const GCUT = 44; // grass corner arc radius ≈ 40u (+ margin)

// Player-controlled character tuning. Movement is now bounded by the street "+" corridor
// (see canWalk in sceneData) rather than a fixed y-band, so the player can walk the full
// boulevard AND up/down Highland Ave and turn the corner at the intersection.
const PLAYER_SPEED = 130; // world units / sec, independent of the sim time-speed

function clamp255(v: number): number {
  return Math.max(0, Math.min(255, v));
}

function shade(hex: string, amt: number): string {
  const num = parseInt(hex.replace("#", ""), 16);
  const r = clamp255((num >> 16) + amt);
  const g = clamp255(((num >> 8) & 0xff) + amt);
  const b = clamp255((num & 0xff) + amt);
  return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
}

function hexAlpha(hex: string, alpha: number): string {
  const num = parseInt(hex.replace("#", ""), 16);
  const r = (num >> 16) & 0xff;
  const g = (num >> 8) & 0xff;
  const b = num & 0xff;
  return `rgba(${r},${g},${b},${alpha})`;
}

// ---- day/night lighting ----
interface RGBA { r: number; g: number; b: number; a: number }

function lerp(a: number, b: number, f: number): number {
  return a + (b - a) * f;
}
function smoothstep(e0: number, e1: number, x: number): number {
  const t = Math.max(0, Math.min(1, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
}
// Deterministic 0..1 hash of an integer cell (x,y) — the ground layer's stand-in for
// randomness (mirrors the integer-mod hashing genRow uses; never Math.random).
function groundHash(x: number, y: number): number {
  let h = (Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

// Ambient overlay colour+alpha by minute-of-day (0–1439). The scene is tinted TOWARD this
// colour: a saturated *magical* blue at night (not grey), amber at sunrise, and a rich
// magenta-over-orange at dusk, near-neutral at midday. Hues keyed to sunset/sunrise/night
// palettes (see lighting research). Alpha is the darkness lever; keep midday tiny.
const AMBIENT_KEYS: { m: number; c: RGBA }[] = [
  { m: 0, c: { r: 14, g: 20, b: 56, a: 0.66 } }, // deep magical night
  { m: 300, c: { r: 18, g: 24, b: 60, a: 0.63 } }, // 05:00 pre-dawn
  { m: 366, c: { r: 96, g: 72, b: 104, a: 0.44 } }, // 06:06 dawn — cool cobalt→violet
  { m: 420, c: { r: 255, g: 190, b: 124, a: 0.19 } }, // 07:00 sunrise amber
  { m: 600, c: { r: 255, g: 238, b: 216, a: 0.06 } }, // 10:00 warm morning
  { m: 780, c: { r: 255, g: 247, b: 230, a: 0.03 } }, // 13:00 midday, near-neutral
  { m: 1050, c: { r: 255, g: 214, b: 150, a: 0.11 } }, // 17:30 afternoon warmth
  { m: 1140, c: { r: 255, g: 138, b: 66, a: 0.22 } }, // 19:00 hot golden dusk
  { m: 1200, c: { r: 132, g: 62, b: 116, a: 0.4 } }, // 20:00 magenta dusk
  { m: 1245, c: { r: 58, g: 42, b: 98, a: 0.5 } }, // 20:45 violet→night
  { m: 1305, c: { r: 22, g: 26, b: 70, a: 0.6 } }, // 21:45 blue night
  { m: 1440, c: { r: 14, g: 20, b: 56, a: 0.66 } }, // wrap
];
function ambientAt(minutes: number): RGBA {
  const m = ((minutes % 1440) + 1440) % 1440;
  let a = AMBIENT_KEYS[0];
  let b = AMBIENT_KEYS[AMBIENT_KEYS.length - 1];
  for (let i = 0; i < AMBIENT_KEYS.length - 1; i++) {
    if (m >= AMBIENT_KEYS[i].m && m <= AMBIENT_KEYS[i + 1].m) {
      a = AMBIENT_KEYS[i];
      b = AMBIENT_KEYS[i + 1];
      break;
    }
  }
  const f = b.m === a.m ? 0 : (m - a.m) / (b.m - a.m);
  return {
    r: lerp(a.c.r, b.c.r, f),
    g: lerp(a.c.g, b.c.g, f),
    b: lerp(a.c.b, b.c.b, f),
    a: lerp(a.c.a, b.c.a, f),
  };
}
// 0 by day → 1 at night (drives the multiply switch + every night light's alpha). Lights
// ramp on at dusk (18:30→20:00) and off at dawn (05:00→06:30).
function nightAt(minutes: number): number {
  const m = ((minutes % 1440) + 1440) % 1440;
  if (m < 300) return 1; // 00:00–05:00 full night
  if (m < 390) return 1 - smoothstep(300, 390, m); // dawn
  if (m < 1110) return 0; // day
  if (m < 1200) return smoothstep(1110, 1200, m); // dusk
  return 1; // 20:00–24:00 full night
}
// 0..1 golden-hour scalar, a smooth bump peaking at sunrise (~06:40) and sunset (~19:00).
// Drives the warm horizon glow that makes dawn/dusk feel directional and wonderful.
function goldenAt(minutes: number): number {
  const m = ((minutes % 1440) + 1440) % 1440;
  const bump = (a: number, peak: number, c: number) => smoothstep(a, peak, m) - smoothstep(peak, c, m);
  return Math.max(bump(330, 400, 500), bump(1050, 1140, 1230));
}

// Time-of-day SUN → the cast-shadow transform for a ground-standing object. Models the sun arcing
// from the east horizon at sunrise, overhead at solar noon, to the west horizon at sunset:
//  - direction: the shadow points OPPOSITE the sun horizontally (morning sun east → shadow west),
//    sweeping across the ground through the day (skewX, ± as the sun crosses the sky);
//  - length: grows as the sun lowers (shadow ≈ height / tan(altitude)) — short at noon, long at
//    golden hour (lenY = forward flatten per unit of object height);
//  - strength: a touch softer when long, and fades to 0 through dusk into night (moonlight is
//    negligible; after dark the signage/lamp lights do the work instead).
// The shadow COLOR is a cool blue-black (baked into the silhouette) — sunlit faces read warm while
// shadows read cool (skylight, not sun), which is what makes a scene look lit by a real sun.
function sunShadowAt(minutes: number): { alpha: number; skewX: number; lenY: number } {
  const m = ((minutes % 1440) + 1440) % 1440;
  const SUNRISE = 360, SUNSET = 1140; // 06:00 → 19:00
  const day = 1 - nightAt(minutes); // fade the cast shadow out through dusk/dawn into night
  if (day <= 0.02 || m <= SUNRISE || m >= SUNSET) return { alpha: 0, skewX: 0, lenY: 0 };
  const frac = (m - SUNRISE) / (SUNSET - SUNRISE); // 0 at sunrise → 1 at sunset
  const altitude = Math.sin(Math.PI * frac); // 0 at the horizon, 1 at solar noon
  const horiz = Math.cos(Math.PI * frac); // +1 east (morning) → 0 noon → -1 west (evening)
  const low = 1 - altitude; // 0 overhead, 1 at the horizon
  return {
    skewX: -horiz * (0.12 + low * 0.9), // ± up to ~1.0 near golden hour; ~0 at noon (straight down)
    lenY: 0.12 + low * 0.42, // forward flatten per unit height: short at noon, long at dusk/dawn
    alpha: (0.44 - low * 0.14) * day, // slightly softer when long; fades into night
  };
}

// Procedural SKY gradient for HEAD-ON areas (the court room, future rooftops): zenith (top) →
// horizon (bottom), keyed to minute-of-day. Zero assets — reflects time automatically. The city's
// top-down view never draws this (it has no sky). Mirrors ambientAt's keyframe lerp.
type RGB = { r: number; g: number; b: number };
const SKY_KEYS: { m: number; top: RGB; hor: RGB }[] = [
  { m: 0, top: { r: 10, g: 16, b: 48 }, hor: { r: 26, g: 36, b: 64 } }, // deep night
  { m: 300, top: { r: 22, g: 32, b: 74 }, hor: { r: 52, g: 58, b: 102 } }, // pre-dawn
  { m: 366, top: { r: 74, g: 85, b: 144 }, hor: { r: 200, g: 160, b: 180 } }, // dawn
  { m: 420, top: { r: 127, g: 176, b: 224 }, hor: { r: 255, g: 202, b: 160 } }, // sunrise
  { m: 600, top: { r: 121, g: 184, b: 234 }, hor: { r: 207, g: 230, b: 245 } }, // morning
  { m: 780, top: { r: 111, g: 176, b: 240 }, hor: { r: 191, g: 224, b: 245 } }, // midday
  { m: 1050, top: { r: 122, g: 176, b: 224 }, hor: { r: 255, g: 214, b: 160 } }, // afternoon
  { m: 1140, top: { r: 106, g: 90, b: 160 }, hor: { r: 255, g: 138, b: 68 } }, // hot dusk
  { m: 1200, top: { r: 58, g: 44, b: 114 }, hor: { r: 132, g: 62, b: 116 } }, // magenta dusk
  { m: 1245, top: { r: 42, g: 44, b: 96 }, hor: { r: 88, g: 50, b: 106 } }, // violet
  { m: 1305, top: { r: 16, g: 20, b: 58 }, hor: { r: 34, g: 38, b: 74 } }, // blue night
  { m: 1440, top: { r: 10, g: 16, b: 48 }, hor: { r: 26, g: 36, b: 64 } }, // wrap
];
function skyAt(minutes: number): { top: RGB; hor: RGB } {
  const m = ((minutes % 1440) + 1440) % 1440;
  let a = SKY_KEYS[0];
  let b = SKY_KEYS[SKY_KEYS.length - 1];
  for (let i = 0; i < SKY_KEYS.length - 1; i++) {
    if (m >= SKY_KEYS[i].m && m <= SKY_KEYS[i + 1].m) {
      a = SKY_KEYS[i];
      b = SKY_KEYS[i + 1];
      break;
    }
  }
  const f = b.m === a.m ? 0 : (m - a.m) / (b.m - a.m);
  const mix = (x: RGB, y: RGB): RGB => ({ r: lerp(x.r, y.r, f), g: lerp(x.g, y.g, f), b: lerp(x.b, y.b, f) });
  return { top: mix(a.top, b.top), hor: mix(a.hor, b.hor) };
}
const rgbCss = (c: RGB) => `rgb(${Math.round(c.r)},${Math.round(c.g)},${Math.round(c.b)})`;

export class HollywoodRenderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private raf = 0;
  private lastTime: number | null = null;
  private npcs: NpcRuntime[];
  private cars: CarRuntime[];
  private peds: AmbientPed[] = [];
  private engine: SoulEngine;

  private cam: Camera = { x: 0, y: 0, zoom: 0.1 };
  private cssW = 0;
  private cssH = 0;
  private dpr = 1;
  private centered = false;

  // player control
  private controlledId: string | null = null;
  // scene-swap state: `room` = active room id (null = overworld); `trans` = a running fade;
  // `roomReturn` = the world position to restore the player to on exit.
  private room: string | null = null;
  private trans: { to: string | null; t: number; swapped: boolean } | null = null;
  private roomReturn: { x: number; y: number } | null = null;
  private camReturn: { x: number; y: number; zoom: number } | null = null;
  // Active outfit per soul: soulId → sprite stem (see outfits.ts). Absent → wears its default
  // (stem = soul id). Swapping an entry changes which sprite (front + `_back`) drawNPC loads.
  private outfits = new Map<string, string>();
  private held = new Set<string>();
  private facingLeft = false;
  private facingUp = false; // moving away from camera → show the back sprite
  // tap-to-walk destination (world coords overworld / room-local in a room); null = not walking to a
  // point. Set by tapping the ground; cleared on arrival, on manual D-pad/key input, or when blocked.
  private moveTarget: { x: number; y: number } | null = null;
  private startFramed = false; // one-time: drop the player in front of the enterable shop on first frame
  private transGuard = 0; // seconds after a scene swap during which enter/exit triggers are ignored
                          // (so holding a direction can't instantly bounce you back through a doorway)

  private sprites = new Map<string, HTMLImageElement | null>();
  private tiles = new Map<string, HTMLImageElement | null>();
  private patterns = new Map<string, CanvasPattern>();
  private patternMatrix = new Map<string, DOMMatrix>(); // cached fillTiled scale per tile name
  // Cached screen-space post-grade gradients (geometry-only, full alpha; time strength applied via
  // globalAlpha). Rebuilt only when the backing-store size changes, not every frame.
  private postGrad: { w: number; h: number; warm: CanvasGradient; vig: CanvasGradient } | null = null;
  // Baked cool-dark silhouettes (alpha-shaped, edge-softened) per sprite src, for the directional
  // time-of-day cast shadow. Built once on first use.
  private silCache = new Map<string, HTMLCanvasElement>();
  // Frontage layout (building x/width) only changes when a facade sprite decodes (its true aspect
  // becomes known). Re-run layoutFrontage only when this is set, not every frame. Starts true so the
  // first frame lays out with nominal aspects; each building sprite's onload re-flags it.
  private layoutDirty = true;
  private prefetchedAreas = new Set<string>(); // AREAS whose plates we've already kicked off loading
  private enterables: Building[] | null = null; // cached flat list of enterable storefronts
  // Cached non-transparent vertical bounds per character sprite ({ t, b } as fractions of natural
  // height), so we normalize every actor to one body height. Measured once, lazily, on first draw.
  private boundsCache = new Map<string, { t: number; b: number }>();
  private measureCanvas?: HTMLCanvasElement;
  private skylineBuf?: HTMLCanvasElement; // offscreen for tinting the skyline silhouette in isolation
  private tapHandler: ((cssX: number, cssY: number) => void) | null = null;
  private onRoomChange: ((room: string | null) => void) | null = null;

  // input state
  private pointers = new Map<number, { x: number; y: number }>();
  private downPos: { x: number; y: number } | null = null;
  private moved = false;
  private pinchDist = 0;
  private cleanupInput: (() => void) | null = null;

  constructor(canvas: HTMLCanvasElement, engine: SoulEngine) {
    this.canvas = canvas;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas context unavailable");
    this.ctx = ctx;
    this.engine = engine;

    this.npcs = engine.souls.map((soul) => ({
      soul,
      x: soul.xMin + Math.random() * (soul.xMax - soul.xMin),
      dir: Math.random() > 0.5 ? 1 : -1,
      y: soul.patrolY ?? (soul.row === "north" ? NORTH_FRONTAGE_Y : SOUTH_FRONTAGE_Y),
      moving: false,
    }));

    // Traffic: two lanes down the boulevard, cars spread across the world so several are on
    // screen at any pan. Upper lane travels right, lower lane left; types/speeds vary.
    const upperY = ROAD_TOP + 48;
    const lowerY = ROAD_BOTTOM - 42;
    this.cars = [];
    const N = 16;
    for (let i = 0; i < N; i++) {
      const upper = i % 2 === 0;
      this.cars.push({
        x: (WORLD_W / N) * i + (i % 3) * 140,
        y: upper ? upperY : lowerY,
        dir: upper ? 1 : -1,
        speed: 62 + (i % 5) * 12,
        type: VEHICLE_TYPES[i % VEHICLE_TYPES.length],
      });
    }

    // Ambient crowd: pedestrians spread along both boulevard sidewalks, at varied depth within
    // each walk band so the street reads as busy rather than a single conga line.
    this.peds = [];
    for (let i = 0; i < AMBIENT_PED_COUNT; i++) {
      const north = i % 2 === 0;
      const bandTop = north ? NORTH_SIDEWALK_TOP + 8 : SOUTH_SIDEWALK_TOP + 6;
      const bandH = north ? NORTH_SIDEWALK_BOTTOM - NORTH_SIDEWALK_TOP - 20 : SOUTH_SIDEWALK_BOTTOM - SOUTH_SIDEWALK_TOP - 14;
      this.peds.push({
        x: 120 + Math.random() * (WORLD_W - 240),
        y: bandTop + Math.random() * bandH,
        dir: Math.random() > 0.5 ? 1 : -1,
        speed: 18 + Math.random() * 26,
        sprite: PED_FRONT[Math.floor(Math.random() * PED_FRONT.length)],
        bob: Math.random() * 1000,
      });
    }
  }

  // ---- lifecycle ----

  start() {
    const step = (t: number) => {
      if (this.lastTime === null) this.lastTime = t;
      const dt = Math.min(0.05, (t - this.lastTime) / 1000);
      this.lastTime = t;

      this.engine.advance(dt);

      const moveScale = Math.min(this.engine.speed, 3);
      for (const s of this.npcs) {
        if (s.soul.id === this.controlledId) continue; // driven by input below
        // Autonomous souls stroll their xMin→xMax patrol at a natural walking pace so the street
        // reads as alive, and `moving` is derived from the ACTUAL per-frame displacement so the
        // walk FX (pendulum leg-blur + smoke) fires exactly when a soul translates.
        // (The old code drifted "stationary"-activity souls at 0.2× while forcing moving=false, so
        // they GLIDED along the sidewalk with NO FX — the reported "not firing on auto walk" bug.
        // The blur swing is time-based, so a real walking pace is needed or a slow drift moonwalks.)
        const dx = s.dir * s.soul.baseSpeed * moveScale * dt;
        s.x += dx;
        if (s.x > s.soul.xMax) {
          s.x = s.soul.xMax;
          s.dir = -1;
        }
        if (s.x < s.soul.xMin) {
          s.x = s.soul.xMin;
          s.dir = 1;
        }
        s.moving = Math.abs(dx) > 0; // walk FX fires exactly when the soul actually walks
      }

      // ambient crowd — walk the sidewalks, turn around at the world edges
      for (const ped of this.peds) {
        ped.x += ped.dir * ped.speed * dt * moveScale;
        if (ped.x > WORLD_W - 100) ped.dir = -1;
        else if (ped.x < 100) ped.dir = 1;
      }

      // advance any running scene-swap fade (fade-through-black; swap at the midpoint)
      if (this.trans) {
        this.trans.t += dt / ROOM_FADE;
        if (!this.trans.swapped && this.trans.t >= 0.5) {
          this.doRoomSwap();
          this.trans.swapped = true;
        }
        if (this.trans.t >= 1) this.trans = null;
      }

      // player-controlled character: WASD / arrows / on-screen D-pad. Real-time speed
      // (not scaled by sim time-speed). Frozen mid-transition. In a room, movement is bounded
      // to the painted floor and there's no follow-camera (the plate fills the frame).
      if (this.controlledId && !this.trans) {
        const pc = this.npcs.find((n) => n.soul.id === this.controlledId);
        if (pc && this.room) this.updateRoomPlayer(pc, dt);
        else if (pc) this.updateWorldPlayer(pc, dt);
      }
      for (const car of this.cars) {
        car.x += car.dir * car.speed * dt * moveScale;
        if (car.x > WORLD_W + 60) car.x = -60;
        if (car.x < -60) car.x = WORLD_W + 60;
      }

      this.render(t);
      this.raf = requestAnimationFrame(step);
    };
    this.raf = requestAnimationFrame(step);
  }

  stop() {
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = 0;
    this.cleanupInput?.();
    this.cleanupInput = null;
  }

  // ---- movement (overworld vs room) + scene-swap transitions ----

  // Overworld player step: move against the walkable "+" corridor + court pocket, face travel,
  // ease the camera to follow. Auto-loads the Overture Court room once you walk deep enough up.
  private updateWorldPlayer(pc: NpcRuntime, dt: number): void {
    if (this.transGuard > 0) this.transGuard -= dt;
    let vx = (this.held.has("right") ? 1 : 0) - (this.held.has("left") ? 1 : 0);
    let vy = (this.held.has("down") ? 1 : 0) - (this.held.has("up") ? 1 : 0);
    if (vx || vy) this.moveTarget = null; // manual input cancels tap-to-walk
    else { const a = this.aimAtTarget(pc); if (a) { vx = a.x; vy = a.y; } }
    pc.moving = vx !== 0 || vy !== 0;
    if (vx || vy) {
      const m = Math.hypot(vx, vy) || 1;
      const dx = (vx / m) * PLAYER_SPEED * dt;
      const dy = (vy / m) * PLAYER_SPEED * dt;
      const ox = pc.x, oy = pc.y;
      // Move axis-independently against the street "+" corridor: try the full step, else slide
      // along the wall on whichever axis stays walkable — so you hug the sidewalk and can turn.
      if (canWalk(pc.x + dx, pc.y + dy)) {
        pc.x += dx;
        pc.y += dy;
      } else {
        if (canWalk(pc.x + dx, pc.y)) pc.x += dx;
        if (canWalk(pc.x, pc.y + dy)) pc.y += dy;
      }
      if (vx < 0) this.facingLeft = true;
      else if (vx > 0) this.facingLeft = false;
      if (vy !== 0 && Math.abs(vy) >= Math.abs(vx)) this.facingUp = vy < 0;
      else if (vx !== 0) this.facingUp = false;
      pc.dir = vx < 0 ? -1 : 1;
      // walking to a tapped point but wall-blocked (barely moved) → give up the target
      if (this.moveTarget && Math.hypot(pc.x - ox, pc.y - oy) < 0.25) this.moveTarget = null;
      // deep in the court, on the axis → crossfade into the Overture Court room
      if (this.transGuard <= 0 && pc.y < COURT_ENTER_Y && Math.abs(pc.x - OVERTURE.cx) < OVERTURE.courtWalkHalf) {
        this.startTransition("overture-court");
      }
      // enterable storefront: walk fully UP to a shop's door (top of the north sidewalk, within the
      // door's x-span on the right of the facade) → crossfade into its interior room.
      if (this.transGuard <= 0 && !this.trans && this.facingUp && pc.y < NORTH_BASELINE + 24) {
        for (const f of ALL_FRONTAGES) {
          for (const b of f.buildings) {
            if (!b.enter || (b.side ?? "north") !== "north") continue;
            const bx = b.x ?? 0, bw = b.width ?? 0;
            if (pc.x >= bx + bw * 0.3 && pc.x <= bx + bw) { this.startTransition(b.enter); break; }
          }
          if (this.trans) break;
        }
      }
    }
    // Prefetch nearby shop / court interiors as the player approaches (moving OR idle), so the enter
    // crossfade never stalls on a multi-MB plate decode. Each area is fetched at most once.
    if (!this.trans) {
      if (!this.enterables) {
        this.enterables = [];
        for (const f of ALL_FRONTAGES) for (const b of f.buildings) if (b.enter) this.enterables.push(b);
      }
      for (const b of this.enterables) {
        const bcx = (b.x ?? 0) + (b.width ?? 0) / 2;
        if (Math.abs(pc.x - bcx) < 1100 && Math.abs(pc.y - NORTH_BASELINE) < 1200) this.prefetchArea(b.enter!);
      }
      if (Math.abs(pc.x - OVERTURE.cx) < 1200) this.prefetchArea("overture-court");
    }
    this.followCam(pc.x, pc.y);
  }

  // The active area descriptor (null when in the overworld).
  private activeArea(): AreaView | null {
    return this.room ? AREAS[this.room] ?? null : null;
  }

  // Active camera-bounds dimensions: the room's backdrop plate when inside one, else the world.
  // The camera clamp + min-zoom use these, so a room pans/zooms exactly like the city and NEVER
  // shows past the plate edges (min-zoom = cover; position clamped to the plate).
  private worldDims(): [number, number] {
    const R = this.activeArea();
    return R ? [R.w, R.h] : [WORLD_W, WORLD_H];
  }

  // Room player step: move within the painted floor trapezoid (room-local coords). Walking down
  // off the front edge exits back to the court.
  private updateRoomPlayer(pc: NpcRuntime, dt: number): void {
    const R = this.activeArea();
    if (!R) return;
    if (this.transGuard > 0) this.transGuard -= dt;
    let vx = (this.held.has("right") ? 1 : 0) - (this.held.has("left") ? 1 : 0);
    let vy = (this.held.has("down") ? 1 : 0) - (this.held.has("up") ? 1 : 0);
    if (vx || vy) this.moveTarget = null; // manual input cancels tap-to-walk
    else { const a = this.aimAtTarget(pc); if (a) { vx = a.x; vy = a.y; } }
    pc.moving = vx !== 0 || vy !== 0;
    if (vx || vy) {
      const m = Math.hypot(vx, vy) || 1;
      // Rooms scale people way up (charScale), so overworld speed feels like a crawl — scale the
      // walk speed with the character so it covers the small plate at a natural pace.
      const speed = PLAYER_SPEED * Math.max(1, (R.charScale ?? 1) * 0.6);
      const dx = (vx / m) * speed * dt;
      const dy = (vy / m) * speed * dt;
      const ox = pc.x, oy = pc.y;
      if (this.roomCanWalk(R, pc.x + dx, pc.y + dy)) {
        pc.x += dx;
        pc.y += dy;
      } else {
        if (this.roomCanWalk(R, pc.x + dx, pc.y)) pc.x += dx;
        if (this.roomCanWalk(R, pc.x, pc.y + dy)) pc.y += dy;
      }
      if (vx < 0) this.facingLeft = true;
      else if (vx > 0) this.facingLeft = false;
      if (vy !== 0 && Math.abs(vy) >= Math.abs(vx)) this.facingUp = vy < 0;
      else if (vx !== 0) this.facingUp = false;
      pc.dir = vx < 0 ? -1 : 1;
      if (this.moveTarget && Math.hypot(pc.x - ox, pc.y - oy) < 0.25) this.moveTarget = null;
      // Walk DOWN to the front edge of the floor → leave. Works with the D-pad AND tap-to-walk
      // toward the bottom (vy > 0 = any downward movement), so it's reachable on mobile. Where you
      // go is per-room: the overworld (exitTo null) or another room (a deeper→shallower step).
      if (this.transGuard <= 0) {
        // Walk-out exit. By default it's the front floor edge (walk down), but a room whose door is
        // on a side sets exitDown:false + exitCurtainX so you leave through the painted doorway.
        if (R.exitCurtainX != null && pc.x >= R.exitCurtainX) this.startTransition(R.exitTo ?? null);
        else if ((R.exitDown ?? true) && vy > 0 && pc.y >= R.floorBot - 8) this.startTransition(R.exitTo ?? null);
        // Reach the beaded curtain on the right → step through into the back consultation room.
        else if (R.curtain && pc.x >= R.curtain.enterX) this.startTransition(R.curtain.toArea);
      }
    }
    this.followCam(pc.x, pc.y); // camera eases to keep the avatar framed (clamped to the plate)
  }

  // Is a room-local point on the painted floor? A trapezoid lane widening toward the viewer.
  private roomCanWalk(R: AreaView, x: number, y: number): boolean {
    if (y < R.floorTop || y > R.floorBot) return false;
    const f = (y - R.floorTop) / (R.floorBot - R.floorTop);
    const half = R.halfTop + (R.halfBot - R.halfTop) * f;
    return Math.abs(x - R.cx) <= half;
  }

  // Begin a fade-through-black scene swap. `to` = room id to enter, or null to exit to overworld.
  private startTransition(to: string | null): void {
    if (this.trans) return;
    this.trans = { to, t: 0, swapped: false };
  }

  // The mid-fade swap: move the player between the overworld and a room, or between two rooms,
  // and flip `this.room`. Three cases keyed off where we are (`from`) and where we're going (`to`).
  private doRoomSwap(): void {
    if (!this.trans) return;
    this.moveTarget = null; // drop any stale tap-target so it can't leak across the scene swap
    const pc = this.controlledId ? this.npcs.find((n) => n.soul.id === this.controlledId) : null;
    const to = this.trans.to;
    const from = this.room; // the room we're currently in (null = out in the overworld)
    if (to) {
      const R = AREAS[to];
      if (!from) {
        // overworld → room: stash the world position + boulevard camera to restore on final exit.
        if (pc) this.roomReturn = { x: pc.x, y: pc.y };
        this.camReturn = { ...this.cam };
      }
      // (room → room keeps the same roomReturn/camReturn so a later exit still lands outside.)
      if (pc && R) { pc.x = R.entryX; pc.y = R.entryY; }
      this.room = to;
      this.facingUp = true; // arrive facing into the scene
      // frame the room at cover-zoom (plate fills the viewport; can't see past its edges), centred
      // on the arrival point then clamped to the plate — same camera model as the city.
      if (R) {
        this.cam.zoom = minZoomFor(this.cssW, this.cssH, R.w, R.h) * (R.entryZoom ?? 1.05);
        this.cam.x = R.entryX - this.cssW / this.cam.zoom / 2;
        this.cam.y = R.entryY - this.cssH / this.cam.zoom / 2;
        clampCamera(this.cam, this.cssW, this.cssH, R.w, R.h, false); // room: allow zoom-out to contain
      }
    } else {
      // room → overworld.
      this.room = null;
      if (pc) {
        if (from === "overture-court") {
          // return to the court just south of the enter line so you don't instantly re-trigger
          pc.x = this.roomReturn?.x ?? OVERTURE.cx;
          pc.y = COURT_ENTER_Y + 150;
        } else {
          // shop interior → step back onto the boulevard just south of the door, clear of the
          // enter-trigger band so you don't immediately walk back in.
          pc.x = this.roomReturn?.x ?? pc.x;
          pc.y = NORTH_BASELINE + 52;
        }
      }
      if (this.camReturn) {
        this.cam.x = this.camReturn.x;
        this.cam.y = this.camReturn.y;
        this.cam.zoom = this.camReturn.zoom;
        this.camReturn = null;
      }
      this.facingUp = false;
    }
    this.transGuard = 0.6; // ignore enter/exit triggers briefly so a held direction can't bounce
    this.onRoomChange?.(this.room); // let React show/hide the Leave button
  }

  // Match the backing store to the on-screen size (CSS px × device pixel ratio) and
  // keep the camera valid. Call on mount and whenever the container resizes.
  resize(cssW: number, cssH: number, dpr: number) {
    this.cssW = cssW;
    this.cssH = cssH;
    this.dpr = dpr;
    this.canvas.width = Math.max(1, Math.round(cssW * dpr));
    this.canvas.height = Math.max(1, Math.round(cssH * dpr));

    if (!this.centered && cssW > 0 && cssH > 0) {
      // Start zoomed in enough to read the sprite detail; center on the controlled
      // character when there is one, else frame the boulevard.
      const minZ = minZoomFor(cssW, cssH, WORLD_W, WORLD_H);
      this.cam.zoom = minZ * 1.9;
      const pc = this.controlledId
        ? this.npcs.find((n) => n.soul.id === this.controlledId)
        : null;
      const highland = CROSS_STREETS.find((cs) => cs.name === "HIGHLAND");
      const cx = pc ? pc.x : (highland ? highland.x : WORLD_W / 2);
      const cy = pc ? pc.y : (ROAD_TOP + ROAD_BOTTOM) / 2;
      this.cam.x = cx - cssW / this.cam.zoom / 2;
      this.cam.y = cy - cssH / this.cam.zoom / 2;
      this.centered = true;
    }
    const [ww, wh] = this.worldDims();
    clampCamera(this.cam, this.cssW, this.cssH, ww, wh, !this.room);
  }

  // ---- camera controls (called by input + zoom buttons) ----

  private panBy(dxCss: number, dyCss: number) {
    const [ww, wh] = this.worldDims();
    this.cam.x -= dxCss / this.cam.zoom;
    this.cam.y -= dyCss / this.cam.zoom;
    clampCamera(this.cam, this.cssW, this.cssH, ww, wh, !this.room);
  }

  private zoomAt(factor: number, cssX: number, cssY: number) {
    const [ww, wh] = this.worldDims();
    // Rooms may zoom out to CONTAIN (whole plate); the city stays COVER (never past the edge).
    zoomAbout(this.cam, factor, cssX, cssY, this.cssW, this.cssH, ww, wh, !this.room);
  }

  // Zoom about the viewport center — for on-screen +/- buttons.
  zoomButton(factor: number) {
    this.zoomAt(factor, this.cssW / 2, this.cssH / 2);
  }

  // Ease the camera to keep the controlled character centered.
  private followCam(x: number, y: number) {
    const [ww, wh] = this.worldDims();
    const tx = x - this.cssW / this.cam.zoom / 2;
    const ty = y - this.cssH / this.cam.zoom / 2;
    this.cam.x += (tx - this.cam.x) * 0.12;
    this.cam.y += (ty - this.cam.y) * 0.12;
    clampCamera(this.cam, this.cssW, this.cssH, ww, wh, !this.room);
  }

  // Designate the player-driven character (its patrol AI is suspended), or null
  // for observer mode (free pan/zoom, nobody driven). Clears stale input state
  // so a held direction or mid-turn facing doesn't leak from the previous
  // character.
  setControlled(id: string | null) {
    // switching characters (or to Observer) drops any active room/transition — the new soul is
    // out in the overworld, not standing in the court plate.
    const wasRoom = this.room;
    this.room = null;
    this.trans = null;
    this.moveTarget = null;
    this.controlledId = id;
    this.held.clear();
    this.facingLeft = false;
    this.facingUp = false;
    if (wasRoom) this.onRoomChange?.(null);
  }

  getControlled(): string | null {
    return this.controlledId;
  }

  // Dress a soul in one of its outfits (stem from outfits.ts). Takes effect on the next frame;
  // the new sprite (and its `_back`) load lazily and swap in once decoded.
  setOutfit(soulId: string, stem: string) {
    this.outfits.set(soulId, stem);
  }

  // Hold / release a movement direction — called by the D-pad and keyboard.
  setMove(dir: "up" | "down" | "left" | "right", pressed: boolean) {
    if (pressed) this.held.add(dir);
    else this.held.delete(dir);
  }

  setTapHandler(fn: (cssX: number, cssY: number) => void) {
    this.tapHandler = fn;
  }

  // React registers here so it can show a "Leave" button whenever a room is active (null = overworld).
  setRoomHandler(fn: (room: string | null) => void) {
    this.onRoomChange = fn;
  }

  // Public: leave the current room via its exit (the on-screen Leave button). The one guaranteed
  // way out, independent of walking to an edge. Cancels any half-finished transition first so a
  // stuck fade can't wedge the button.
  leaveRoom() {
    if (!this.room) return;
    this.trans = null;
    this.startTransition(this.activeArea()?.exitTo ?? null);
  }

  // Tap-to-walk: send the controlled character toward the tapped ground point. Works in both the
  // overworld and a room (both render through this.cam, so screenToWorld gives the right space).
  tapToWalk(cssX: number, cssY: number): void {
    if (!this.controlledId) return;
    const w = screenToWorld(this.cam, cssX, cssY);
    this.moveTarget = { x: w.x, y: w.y };
  }

  // Direction (unit vector) from the character toward the active move-target, or null once close
  // enough (which also clears the target).
  private aimAtTarget(pc: NpcRuntime): { x: number; y: number } | null {
    if (!this.moveTarget) return null;
    const dx = this.moveTarget.x - pc.x, dy = this.moveTarget.y - pc.y;
    const d = Math.hypot(dx, dy);
    if (d < 8) { this.moveTarget = null; return null; }
    return { x: dx / d, y: dy / d };
  }

  hitTest(cssX: number, cssY: number): string | null {
    const w = screenToWorld(this.cam, cssX, cssY);
    let hit: string | null = null;
    // Keep the tap target a constant ~22px on screen regardless of zoom, so people
    // stay tappable when zoomed out (where a fixed world radius would be tiny).
    const tol = 22 / this.cam.zoom;
    let best = tol * tol;
    for (const s of this.npcs) {
      const dx = s.x - w.x;
      const dy = s.y - 8 - w.y;
      const dist = dx * dx + dy * dy;
      if (dist < best) {
        best = dist;
        hit = s.soul.id;
      }
    }
    return hit;
  }

  // ---- input (pan / pinch / wheel / tap) ----

  attachInput() {
    const canvas = this.canvas;
    const rel = (e: { clientX: number; clientY: number }) => {
      const r = canvas.getBoundingClientRect();
      return { x: e.clientX - r.left, y: e.clientY - r.top };
    };

    const onDown = (e: PointerEvent) => {
      canvas.setPointerCapture(e.pointerId);
      const p = rel(e);
      this.pointers.set(e.pointerId, p);
      if (this.pointers.size === 1) {
        this.downPos = p;
        this.moved = false;
      } else if (this.pointers.size === 2) {
        const pts = [...this.pointers.values()];
        this.pinchDist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      }
    };

    const onMove = (e: PointerEvent) => {
      const prev = this.pointers.get(e.pointerId);
      if (!prev) return;
      const p = rel(e);
      this.pointers.set(e.pointerId, p);

      if (this.pointers.size >= 2) {
        const pts = [...this.pointers.values()];
        const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
        const mid = { x: (pts[0].x + pts[1].x) / 2, y: (pts[0].y + pts[1].y) / 2 };
        if (this.pinchDist > 0) this.zoomAt(dist / this.pinchDist, mid.x, mid.y);
        this.pinchDist = dist;
        this.moved = true;
      } else {
        const dx = p.x - prev.x;
        const dy = p.y - prev.y;
        if (!this.controlledId) this.panBy(dx, dy); // camera follows the player instead
        if (this.downPos && Math.hypot(p.x - this.downPos.x, p.y - this.downPos.y) > TAP_THRESHOLD) {
          this.moved = true;
        }
      }
    };

    const onUp = (e: PointerEvent) => {
      const p = rel(e);
      const wasSingle = this.pointers.size === 1;
      this.pointers.delete(e.pointerId);
      try {
        canvas.releasePointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
      if (wasSingle && !this.moved && this.tapHandler) this.tapHandler(p.x, p.y);
      if (this.pointers.size < 2) this.pinchDist = 0;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const p = rel(e);
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      this.zoomAt(factor, p.x, p.y);
    };

    // keyboard drive for the controllable character (desktop)
    const keyMap: Record<string, "up" | "down" | "left" | "right"> = {
      ArrowUp: "up", KeyW: "up",
      ArrowDown: "down", KeyS: "down",
      ArrowLeft: "left", KeyA: "left",
      ArrowRight: "right", KeyD: "right",
    };
    const onKey = (down: boolean) => (e: KeyboardEvent) => {
      const dir = keyMap[e.code];
      if (!dir) return;
      e.preventDefault();
      this.setMove(dir, down);
    };
    const onKeyDown = onKey(true);
    const onKeyUp = onKey(false);

    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointercancel", onUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);

    this.cleanupInput = () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointercancel", onUp);
      canvas.removeEventListener("wheel", onWheel);
    };
  }

  // ---- drawing ----

  // Frame dispatcher: draw the overworld or the active area, then the scene-swap fade on top.
  private render(t: number) {
    if (this.cssW === 0) return;
    const area = this.activeArea();
    if (area) this.renderArea(t, area);
    else this.renderWorld(t);
    this.drawTransition();
  }

  // Render an AREA (scene-swap room). The backdrop plate is shown through the SAME clamped camera as
  // the city (world = the plate's pixels), so it pans/zooms and never reveals an edge (min-zoom =
  // cover). HEAD-ON areas get a procedural time-of-day SKY (screen-space, behind the plate, seen
  // through the plate's transparent top) + an optional baked skyline/window layer. The avatar walks
  // the painted floor as a normal foot-Y billboard, mildly depth-scaled. All the character machinery
  // (contact shadow, walk FX, leg-blur, front/back) is reused verbatim.
  private renderArea(t: number, R: AreaView): void {
    const ctx = this.ctx;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    if (R.view === "headon") this.drawAreaSky(t); // time-reactive sky behind the plate
    else {
      ctx.fillStyle = "#0d0b09";
      ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }
    // camera transform (plate-pixel space) — clamped by worldDims() so no border ever shows
    const s = this.dpr * this.cam.zoom;
    ctx.setTransform(s, 0, 0, s, -this.cam.x * s, -this.cam.y * s);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    if (R.sky) this.drawAreaSkyline(R); // distant skyline behind the plate
    if (R.view === "headon") this.drawCelestial(t, R); // sun/moon ON TOP of the skyline, behind the plate
    // backdrop plate (storefronts + floor) — sits below the sky headroom (skyPad)
    const pad = R.skyPad ?? 0;
    const plateH = R.h - pad;
    const pc = this.controlledId ? this.npcs.find((n) => n.soul.id === this.controlledId) : null;
    // Curtain doorway: once the player nears it, show the open-curtain art (the room's other
    // furniture is identical between plates, so this reads purely as the beaded curtain opening).
    let backdropKey = R.backdrop;
    if (R.curtain && pc && pc.x >= R.curtain.openX) backdropKey = R.curtain.openBackdrop;
    const img = this.getAreaPlate(R, backdropKey);
    if (img && img.complete && img.naturalWidth > 0) {
      const night = nightAt(this.engine.clockMinutes);
      // DAY BRIGHTNESS: lift the plate's exposure in daylight so the court reads bright & sunny.
      const day = 1 - night;
      const prevFilter = ctx.filter;
      if (day > 0.02) ctx.filter = `brightness(${(1 + 0.18 * day).toFixed(3)}) saturate(${(1 + 0.06 * day).toFixed(3)})`;
      ctx.drawImage(img, 0, pad, R.w, plateH);
      ctx.filter = prevFilter;
      // NIGHT LIFT: additively re-composite the plate so its painted lit windows / signage GLOW after
      // dark (the bright pixels add, the dark ones add ~nothing) — so buildings read at night.
      if (night > 0.02) {
        ctx.save();
        ctx.globalCompositeOperation = "lighter";
        ctx.globalAlpha = 0.22 * night;
        ctx.drawImage(img, 0, pad, R.w, plateH);
        ctx.restore();
      }
    } else {
      ctx.fillStyle = "#c9b48c";
      ctx.fillRect(0, R.floorTop - 20, R.w, R.h - R.floorTop + 20);
    }
    this.drawMoveMarker(t); // tap-to-walk destination ring on the painted floor
    // Room actors: the controlled avatar + any static occupants (e.g. Yara at her counter), all
    // foot-Y sorted so the player passes correctly in front of / behind them. Each is depth-scaled
    // by how far down the painted floor it stands.
    const cs = R.charScale ?? 1; // rooms scale people UP to the painted furniture's human scale
    const depthScaleAt = (y: number) => {
      const f = Math.max(0, Math.min(1, (y - R.floorTop) / (R.floorBot - R.floorTop)));
      return (R.scaleBack + (1 - R.scaleBack) * f) * cs;
    };
    const drawPlayer = () => {
      if (!pc) return;
      const sc = depthScaleAt(pc.y);
      ctx.save();
      ctx.translate(pc.x, pc.y); ctx.scale(sc, sc); ctx.translate(-pc.x, -pc.y);
      // drawNPC anchors feet at pc.y + FEET_DROP; that small overworld nudge, ×charScale, would
      // sink the avatar ~100px. Cancel it so the feet sit at pc.y and the waist lands on the counter.
      ctx.translate(0, -FEET_DROP);
      this.drawNPC(pc, t);
      ctx.restore();
    };
    const drawOccupant = (oc: NonNullable<AreaView["occupants"]>[number]) =>
      this.drawRoomOccupant(oc.stem, oc.x, oc.y, (oc.scale ?? 1) * depthScaleAt(oc.y), oc.faceLeft ?? false);
    if (R.foreground) {
      // Counter-style room: occupants (keeper) BEHIND the foreground plate, player in FRONT of it.
      for (const oc of R.occupants ?? []) drawOccupant(oc);
      const fg = this.getAreaPlate(R, R.foreground, false); // overlay is a PNG (needs alpha)
      if (fg && fg.complete && fg.naturalWidth > 0) ctx.drawImage(fg, 0, pad, R.w, plateH);
      drawPlayer();
    } else {
      // Open room: player + occupants foot-Y sorted so you pass in front of / behind them.
      const acts: { y: number; draw: () => void }[] = [];
      if (pc) acts.push({ y: pc.y, draw: drawPlayer });
      for (const oc of R.occupants ?? []) acts.push({ y: oc.y, draw: () => drawOccupant(oc) });
      acts.sort((a, b) => a.y - b.y);
      for (const a of acts) a.draw();
    }
    // cohesion grade + vignette (screen space) so the area reads under the same exposure
    this.drawPostGrade();
  }

  // Procedural time-of-day sky (screen space): a zenith→horizon gradient keyed to the sim clock,
  // plus a sun (day) / moon (night) disc with a soft halo, plus a warm golden-hour horizon wash.
  private drawAreaSky(t: number): void {
    const ctx = this.ctx;
    const W = this.canvas.width, H = this.canvas.height;
    const mins = this.engine.clockMinutes;
    const { top, hor } = skyAt(mins);
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, rgbCss(top));
    g.addColorStop(1, rgbCss(hor));
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    const night = nightAt(mins), golden = goldenAt(mins);
    // STARS — a deterministic field scattered across the upper sky, fading in with night (twinkle
    // via a slow per-star phase). Drawn before sun/moon so the moon reads over them.
    if (night > 0.02) {
      ctx.save();
      ctx.fillStyle = "#eaf0ff";
      for (let i = 0; i < 90; i++) {
        const sx = groundHash(i * 2 + 1, 7) * W;
        const sy = groundHash(i * 2 + 2, 11) * H * 0.62;
        const tw = 0.5 + 0.5 * Math.sin(t * 0.0015 + i * 1.7);
        ctx.globalAlpha = night * (0.35 + 0.55 * tw) * (0.5 + 0.5 * groundHash(i, 3));
        const r = 1.1 + 1.4 * groundHash(i * 3, 5);
        ctx.fillRect(sx, sy, r, r);
      }
      ctx.restore();
    }
    // (Sun/moon are drawn in WORLD space by drawCelestial so they sit in the plate's sky headroom,
    // clear of the top HUD — not here in screen space.)
    if (golden > 0.02) {
      // warm horizon wash low in the sky
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      const gw = ctx.createLinearGradient(0, H * 0.45, 0, H);
      gw.addColorStop(0, "rgba(255,150,70,0)");
      gw.addColorStop(1, `rgba(255,150,70,${0.35 * golden})`);
      ctx.fillStyle = gw;
      ctx.fillRect(0, H * 0.45, W, H * 0.55);
      ctx.restore();
    }
  }

  // Sun / moon, drawn in WORLD (area) space so they ride the plate's sky HEADROOM (`skyPad`) — a band
  // that sits BELOW the top HUD, not behind it. Each sweeps a CELESTIAL ARC (cos→east/west x, sin→
  // altitude): rises in from the left, peaks up-centre, sets on the right, dipping behind the buildings
  // at the horizons. The SUN runs it across the day (sunrise→sunset), the MOON across the night, handing
  // off at dusk/dawn. Emissive GLOW = additive `lighter` bloom + a `shadowBlur`, sine-PULSED to breathe.
  private drawCelestial(t: number, R: AreaView): void {
    const pad = R.skyPad ?? 0;
    if (pad <= 0) return;
    const ctx = this.ctx;
    const mins = this.engine.clockMinutes;
    const cx = R.cx, rx = R.w * 0.42, rad = R.w * 0.05;
    // LOW, shallow arc that rides just above the skyline/rooftops (so it's in view on tall mobile
    // screens) — and drawn on TOP of the skyline silhouette.
    const peakY = pad * 0.84, horizonY = pad * 1.14, ry = horizonY - peakY;
    const arcXY = (p: number) => {
      const th = Math.PI * (1 - Math.max(0, Math.min(1, p)));
      return { x: cx + rx * Math.cos(th), y: horizonY - ry * Math.sin(th) };
    };
    const edgeFade = (p: number) => smoothstep(0, 0.05, p) * (1 - smoothstep(0.95, 1, p));
    const pulse = 1 + 0.08 * Math.sin(t * 0.0022);
    const drawBody = (p: number, stem: string, col: string, glow: string) => {
      const alpha = edgeFade(p);
      if (alpha < 0.03) return;
      const { x, y } = arcXY(p);
      const spr = this.getOverture(stem);
      const hasSpr = !!(spr && spr.complete && spr.naturalWidth > 0);
      const faint = (a: number) => glow.replace(/[\d.]+\)\s*$/, a + ")");
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.globalCompositeOperation = "lighter";
      const gr = rad * 4.4 * pulse;
      const bg = ctx.createRadialGradient(x, y, rad * 0.3, x, y, gr);
      bg.addColorStop(0, glow);
      bg.addColorStop(0.45, faint(0.16));
      bg.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = bg;
      ctx.fillRect(x - gr, y - gr, gr * 2, gr * 2);
      ctx.globalCompositeOperation = "source-over";
      ctx.shadowColor = faint(0.9);
      ctx.shadowBlur = rad * (hasSpr ? 0.7 : 1.1) * pulse;
      if (hasSpr) {
        const w = rad * 3.2, h = w * (spr!.naturalHeight / spr!.naturalWidth);
        ctx.drawImage(spr!, x - w / 2, y - h / 2, w, h);
      } else {
        ctx.beginPath();
        ctx.arc(x, y, rad, 0, Math.PI * 2);
        ctx.fillStyle = col;
        ctx.fill();
      }
      ctx.restore();
    };
    const SUNRISE = 360, SUNSET = 1140;
    const md = ((mins % 1440) + 1440) % 1440;
    if (md >= SUNRISE && md <= SUNSET) {
      drawBody((md - SUNRISE) / (SUNSET - SUNRISE), "sun", "rgba(255,246,214,1)", "rgba(255,196,90,0.55)");
    }
    const NIGHT_LEN = SUNRISE + 1440 - SUNSET;
    const nm = md >= SUNSET ? md - SUNSET : md + 1440 - SUNSET;
    if (nm <= NIGHT_LEN) {
      drawBody(nm / NIGHT_LEN, "moon", "rgba(226,232,244,1)", "rgba(170,200,255,0.45)");
    }
  }

  // Distant skyline layers in room-local space (drawn BEHIND the storefront plate). The silhouette
  // is a baked matte shape tinted toward the ambient colour by the clock; the windows layer adds
  // emissive glints after dark (alpha = nightAt). Both no-op until their assets decode.
  private drawAreaSkyline(R: AreaView): void {
    if (!R.sky) return;
    const ctx = this.ctx;
    const mins = this.engine.clockMinutes;
    const sil = this.getOverture(R.sky.skyline);
    if (sil && sil.complete && sil.naturalWidth > 0) {
      const h = R.w * (sil.naturalHeight / sil.naturalWidth);
      const y = R.sky.rooflineY - h;
      // Tint the silhouette toward the ambient colour (darkens at night) in an OFFSCREEN buffer, so
      // the tint touches only the silhouette SHAPE. Doing source-atop on the main canvas would paint
      // the whole rectangle (the sky behind is opaque) → a hard horizontal seam. Then blit the shape.
      const amb = ambientAt(mins);
      const tintA = Math.max(0, Math.min(0.7, amb.a + nightAt(mins) * 0.3));
      const buf = (this.skylineBuf ??= document.createElement("canvas"));
      if (buf.width !== sil.naturalWidth) { buf.width = sil.naturalWidth; buf.height = sil.naturalHeight; }
      const bx = buf.getContext("2d")!;
      bx.setTransform(1, 0, 0, 1, 0, 0);
      bx.globalCompositeOperation = "source-over";
      bx.globalAlpha = 1;
      bx.clearRect(0, 0, buf.width, buf.height);
      bx.drawImage(sil, 0, 0);
      bx.globalCompositeOperation = "source-atop"; // tints only where the silhouette has alpha
      bx.globalAlpha = tintA;
      bx.fillStyle = `rgb(${Math.round(amb.r)},${Math.round(amb.g)},${Math.round(amb.b)})`;
      bx.fillRect(0, 0, buf.width, buf.height);
      bx.globalAlpha = 1;
      bx.globalCompositeOperation = "source-over";
      ctx.drawImage(buf, 0, y, R.w, h);
    }
    const win = this.getOverture(R.sky.windows);
    const night = nightAt(mins);
    if (win && win.complete && win.naturalWidth > 0 && night > 0.02) {
      const h = R.w * (win.naturalHeight / win.naturalWidth);
      const y = R.sky.rooflineY - h;
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = night;
      ctx.drawImage(win, 0, y, R.w, h);
      ctx.restore();
    }
  }

  // Tap-to-walk destination marker: a soft pulsing ground ring where the character is headed.
  private drawMoveMarker(t: number): void {
    if (!this.moveTarget) return;
    const ctx = this.ctx;
    const pulse = 0.5 + 0.5 * Math.sin(t * 0.006);
    const rx = 15 + 5 * pulse, ry = rx * 0.5;
    ctx.save();
    ctx.globalAlpha = 0.3 + 0.4 * pulse;
    ctx.strokeStyle = "rgba(255,238,170,0.95)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.ellipse(this.moveTarget.x, this.moveTarget.y, rx, ry, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  // Fade-through-black overlay for a running scene swap (alpha peaks at the mid-fade swap point).
  private drawTransition(): void {
    if (!this.trans) return;
    const ctx = this.ctx;
    const a = 1 - Math.abs(2 * this.trans.t - 1);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = Math.max(0, Math.min(1, a));
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.globalAlpha = 1;
  }

  private renderWorld(t: number) {
    const ctx = this.ctx;
    if (this.cssW === 0) return;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    const s = this.dpr * this.cam.zoom;
    ctx.setTransform(s, 0, 0, s, -this.cam.x * s, -this.cam.y * s);

    // Lay out every frontage so both the ground detail and the actor pass read current building
    // x/width. Building x/width only change when a facade sprite decodes (its aspect becomes known),
    // so this runs on the first frame and then only when `layoutDirty` is re-flagged by a sprite's
    // onload — NOT every frame (was ~150–200 buildings × map/reduce/string-concat per frame).
    if (this.layoutDirty) {
      for (const f of NORTH_FRONTAGES) layoutFrontage(f, this.aspectOf);
      for (const f of SOUTH_FRONTAGES) layoutFrontage(f, this.aspectOf);
      for (const f of RES_FRONTAGES) layoutFrontage(f, this.aspectOf);
      this.layoutDirty = false;
    }

    // One-time on the first drawn frame: engine soul positions are random, so drop the controlled
    // player right in front of the enterable shop (and frame the camera on it) so the shop is the
    // first thing you see and can walk straight into — regardless of where the soul spawned.
    if (!this.startFramed && this.controlledId) {
      const pc = this.npcs.find((n) => n.soul.id === this.controlledId);
      let shop: Building | null = null;
      for (const f of ALL_FRONTAGES) { for (const b of f.buildings) if (b.enter) { shop = b; break; } if (shop) break; }
      if (pc && shop) {
        pc.x = (shop.x ?? 0) + (shop.width ?? 0) / 2;
        pc.y = NORTH_BASELINE + 46; // on the north sidewalk, just in front of the door
        this.facingUp = true;
        this.cam.zoom = minZoomFor(this.cssW, this.cssH, WORLD_W, WORLD_H) * 1.9;
        this.cam.x = pc.x - this.cssW / this.cam.zoom / 2;
        this.cam.y = pc.y - this.cssH / this.cam.zoom / 2;
        clampCamera(this.cam, this.cssW, this.cssH, WORLD_W, WORLD_H);
        this.startFramed = true;
      }
    }

    // (a) GROUND pre-pass — flat surfaces, always beneath every actor.
    this.drawGround();
    this.drawSidewalks();
    this.drawRoad();
    this.drawGroundDetail(); // aprons + landmark plazas on the walks
    this.drawOvertureFloor(); // baked plaza floor plate behind the Overture gate (walk-in court)
    this.drawSeamBlends(); // feather surface transitions + decal breakup (the "smudge")
    this.drawFloorGlow(); // lamp light cast ON the floor — UNDER the actors (they stand IN it)
    this.drawMoveMarker(t); // tap-to-walk destination ring, on the ground under the actors

    // distant skyline silhouette — always furthest back
    for (const b of BACKDROP_BUILDINGS) this.drawBuilding(b);

    // (b) UNIFIED DEPTH PASS — every upright actor (buildings, cars, lamps, props, peds, souls)
    // collected, viewport-culled, sorted by foot-Y (baseline), and drawn far→near. This is what
    // makes a character pass BEHIND a lamp/palm on the sidewalk and IN FRONT once on the street,
    // and keeps cars correctly layered against the sidewalks.
    const actors: Actor[] = [];
    this.collectActors(actors, t);
    actors.sort((a, b) => a.y - b.y);
    for (const a of actors) a.draw();

    // (c) OVERLAY post-pass — full-screen day/night grade, golden hour, night lights, then a
    // final screen-space cohesion grade + vignette so every asset reads under one exposure.
    this.drawAmbientGrade();
    this.drawGoldenHour();
    this.drawLights();
    this.drawPostGrade();
  }

  // Final cohesion pass in SCREEN space (device pixels, independent of the world camera): a real,
  // VISIBLE grade so every asset reads under one light. Research-calibrated — the old 10%
  // soft-light + edge-only vignette were below the just-noticeable threshold. Now: a contrast
  // bump (widens the value range so shadows separate), a cinematic duotone (cool shadows / warm
  // highlights), and a dual vignette (lift the center + darken the corners) so there's real
  // center-to-edge contrast. Drawn last, over everything.
  private drawPostGrade(): void {
    const ctx = this.ctx;
    const night = nightAt(this.engine.clockMinutes);
    const golden = goldenAt(this.engine.clockMinutes);
    const W = this.canvas.width, Hh = this.canvas.height;
    // Rebuild the (geometry-only) gradients only on a size change; strength is applied via alpha.
    if (!this.postGrad || this.postGrad.w !== W || this.postGrad.h !== Hh) {
      const cx = W / 2, cy = Hh * 0.5, rad = Math.hypot(W, Hh) * 0.62;
      const warm = ctx.createRadialGradient(cx, cy, rad * 0.15, cx, cy, rad);
      warm.addColorStop(0, "rgba(255,204,146,1)");
      warm.addColorStop(1, "rgba(255,204,146,0)");
      const vig = ctx.createRadialGradient(cx, cy, rad * 0.38, cx, cy, rad);
      vig.addColorStop(0, "rgba(4,4,8,0)");
      vig.addColorStop(1, "rgba(4,4,8,1)");
      this.postGrad = { w: W, h: Hh, warm, vig };
    }
    const { warm, vig } = this.postGrad;
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    // (1) cool-shadow duotone — steal a little warmth from the darks so they read cinematic cool.
    ctx.globalCompositeOperation = "multiply";
    ctx.fillStyle = `rgba(146,166,204,${0.16 + 0.08 * night})`;
    ctx.fillRect(0, 0, W, Hh);
    // (2) warm highlight lift — soft additive glow toward the lit street center, warmer at golden
    // hour, dimmer at night. Cached gradient, time strength via globalAlpha.
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = 0.2 * (1 - 0.5 * night) + 0.08 * golden;
    ctx.fillStyle = warm;
    ctx.fillRect(0, 0, W, Hh);
    ctx.globalAlpha = 1;
    // (3) overlay punch — widen contrast so shadow / body / highlight separate.
    ctx.globalCompositeOperation = "overlay";
    ctx.fillStyle = "rgba(128,128,128,0.26)";
    ctx.fillRect(0, 0, W, Hh);
    // (4) dual vignette — darken the corners; the center push from (2) gives real edge contrast.
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 0.54 + 0.16 * night;
    ctx.fillStyle = vig;
    ctx.fillRect(0, 0, W, Hh);
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  // Gather every upright actor as a { footY, draw } pair for the sorted depth pass. Each type is
  // viewport-culled here so the sort stays small; the actual drawing reuses the existing per-
  // instance draw methods unchanged.
  private collectActors(out: Actor[], t: number): void {
    const vx = this.cam.x;
    const vy = this.cam.y;
    const vR = vx + this.cssW / this.cam.zoom;
    const vB = vy + this.cssH / this.cam.zoom;
    const zoom = this.cam.zoom;

    // frontage buildings (N / S / residential)
    for (const f of [...NORTH_FRONTAGES, ...SOUTH_FRONTAGES, ...RES_FRONTAGES]) {
      for (const b of f.buildings) {
        const bw = b.width ?? 120;
        if ((b.x ?? 0) + bw < vx - 60 || (b.x ?? 0) > vR + 60) continue;
        out.push({ y: this.buildingBaseY(b), draw: () => this.drawBuilding(b) });
      }
    }
    // Overture walk-in plaza (gate + court terminus + side terraces + elephant gateposts)
    this.collectOvertureActors(out, vx, vR);
    // cars
    this.cars.forEach((car, i) => {
      if (car.x < vx - 260 || car.x > vR + 260) return;
      out.push({ y: car.y, draw: () => this.drawCar(car, i) });
    });
    // street lamps
    this.forEachLamp((x, baseY, headY) => {
      out.push({ y: baseY, draw: () => this.drawLamp(x, baseY, headY) });
    });
    // sidewalk props
    if (zoom >= 0.16) {
      this.forEachProp((name, x, footY) => {
        out.push({ y: footY, draw: () => this.drawProp(name, x, footY) });
      });
    }
    // ambient pedestrians
    if (zoom >= 0.18) {
      for (const ped of this.peds) {
        if (ped.x < vx - 60 || ped.x > vR + 60) continue;
        out.push({ y: ped.y, draw: () => this.drawPed(ped, t) });
      }
    }
    // named soul cast — plain foot-Y actors everywhere, including inside the Overture court
    for (const npc of this.npcs) {
      if (npc.x < vx - 120 || npc.x > vR + 120 || npc.y < vy - 200 || npc.y > vB + 120) continue;
      out.push({ y: npc.y, draw: () => this.drawNPC(npc, t) });
    }
  }

  // A building's foot/baseline Y (the depth key) — matches the anchor drawBuilding uses.
  private buildingBaseY(b: Building): number {
    return b.baseY ?? (b.side === "north" ? NORTH_BASELINE : SOUTH_BASELINE);
  }

  // Every boulevard street-lamp currently on screen. `baseY` is the foot on the sidewalk,
  // `headY` the luminaire. Shared by the prop pass (drawStreetLamps) and the night light
  // pass (drawLights) so the glow always sits on the actual fixture. Cross-street spans skip.
  private forEachLamp(cb: (x: number, baseY: number, headY: number) => void): void {
    const vL = this.cam.x - 170;
    const vR = this.cam.x + this.cssW / this.cam.zoom + 170;
    for (const baseY of [ROAD_TOP - 8, SOUTH_SIDEWALK_BOTTOM - 8]) {
      for (let x = 78; x < WORLD_W; x += LAMP_STEP) {
        if (x < vL || x > vR) continue;
        if (CROSS_STREETS.some((cs) => x > cs.x - CS_HALF && x < cs.x + CS_HALF)) continue;
        cb(x, baseY, baseY - LAMP_POLE_H);
      }
    }
  }

  // One physical lamp post — a vintage Hollywood twin-globe standard. Drawn day and night so the
  // boulevard has a real fixture; at night drawLights adds the glow at these same globes. Called
  // per-lamp from the depth pass so pedestrians sort in front of / behind it correctly.
  private drawLamp(x: number, baseY: number, headY: number): void {
    const ctx = this.ctx;
    {
      // foot shadow + base
      ctx.fillStyle = "#171310";
      ctx.beginPath();
      ctx.ellipse(x, baseY, 8, 3, 0, 0, Math.PI * 2);
      ctx.fill();
      // tapered pole
      ctx.fillStyle = "#2b2620";
      ctx.beginPath();
      ctx.moveTo(x - 3.4, baseY);
      ctx.lineTo(x - 2, headY);
      ctx.lineTo(x + 2, headY);
      ctx.lineTo(x + 3.4, baseY);
      ctx.closePath();
      ctx.fill();
      // cross-arm
      ctx.fillStyle = "#342d23";
      ctx.fillRect(x - LAMP_ARM, headY - 2, LAMP_ARM * 2, 3.2);
      // three warm glass globes (two on the arm ends, one crowning the top)
      for (const [gx, gy] of [
        [x - LAMP_ARM, headY - 4] as const,
        [x + LAMP_ARM, headY - 4] as const,
        [x, headY - 9] as const,
      ]) {
        ctx.fillStyle = "#3a3227";
        ctx.fillRect(gx - 3, gy - 1, 6, 4); // fitter cap
        ctx.fillStyle = "#ffe9b8";
        ctx.beginPath();
        ctx.arc(gx, gy - 4, 5, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  // Additive night lighting (composited with `lighter`): warm light radiating from each lamp
  // globe with a pool on the sidewalk, a tight glow at each storefront's window band, a
  // contained neon bloom on landmark marquees, and a faint contact pool under each person.
  // Skipped entirely by day (zero cost); everything viewport-culled.
  private drawLights() {
    const night = nightAt(this.engine.clockMinutes);
    if (night <= 0.001) return;
    const ctx = this.ctx;
    const vL = this.cam.x;
    const vR = this.cam.x + this.cssW / this.cam.zoom;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";

    // 1. street lamps — airborne light from each globe + a bloom halo (the floor pool is a
    // separate ground pre-pass, drawFloorGlow, so it sits under the actors).
    // Baked glow textures (pixel-identical to the old per-frame gradients; blitted with α=night).
    const globe = this.bakedGlow("lampGlobe", [[0, "rgba(255,216,152,1)"], [0.45, "rgba(255,196,120,0.32)"], [1, "rgba(255,196,120,0)"]]);
    const bloom = this.bakedGlow("lampBloom", [[0, "rgba(255,214,150,1)"], [1, "rgba(255,214,150,0)"]]);
    this.forEachLamp((x, _baseY, headY) => {
      const gy = headY - 8;
      for (const gx of [x - LAMP_ARM, x + LAMP_ARM, x]) this.blitBlob(globe, gx, gy, 48, 48, 0.5 * night, "lighter");
      // (the warm pool the lamp casts ON the sidewalk is drawn in drawFloorGlow, a GROUND pre-pass
      // before the actors, so people stand IN the light instead of under it — not here on top.)
      // bloom — a big soft halo over the whole lamp head so the light blooms into the dark
      this.blitBlob(bloom, x, gy, 104, 104, 0.12 * night, "lighter");
    });

    // 2. building light — a tight warm glow at the shop-window band (low on the facade, where
    // the storefront actually is) plus a contained neon bloom on landmark marquees. Radii are
    // capped and hug the base, so tall buildings no longer get sky-sized halos overhead.
    for (const f of ALL_FRONTAGES) {
      for (const b of f.buildings) {
        const bx = b.x ?? 0;
        const bw = b.width ?? 0;
        if (bw <= 0 || bx + bw < vL - 80 || bx > vR + 80) continue;
        const side = b.side ?? "north";
        const growUp = b.growUp ?? true;
        const baseY = b.baseY ?? (side === "north" ? NORTH_BASELINE : SOUTH_BASELINE);
        const H = (b.ch ?? (b.height ?? 90) / 84) * 84;
        const cx = bx + bw / 2;
        const dir = growUp ? -1 : 1;
        // storefront window glow, near the base
        const band = Math.min(H, 150);
        const gy = baseY + dir * band * 0.5;
        const rad = Math.min(bw * 0.55, 150);
        const win = this.bakedGlow("win", [[0, "rgba(255,206,140,1)"], [1, "rgba(255,206,140,0)"]]);
        this.blitBlob(win, cx, gy, rad, Math.min(band * 0.6, 88), 0.14 * night, "lighter");
        // marquee bloom, on the sign band (kept on the facade, not overhead)
        if (b.marquee) {
          const my = baseY + dir * Math.min(H * 0.55, 210);
          const mc = b.marqueeColor ?? "#e0b23a";
          const mr = Math.min(bw * 0.5, 150);
          const mg = this.bakedGlow(`mq:${mc}`, [[0, hexAlpha(mc, 1)], [1, hexAlpha(mc, 0)]]);
          this.blitBlob(mg, cx, my, mr, Math.min(H * 0.12, 44), 0.5 * night, "lighter");
        }
      }
    }

    // 3. people — a faint aura-tinted contact pool at the feet after dark (no bright halo).
    // The controlled character is marked by the "you are here" ring in drawNPC, not a glow.
    for (const s of this.npcs) {
      if (s.x < vL - 60 || s.x > vR + 60) continue;
      const aura = auraColor(s.soul);
      const r = 20;
      const fy = s.y + 6;
      const g = this.bakedGlow(`pool:${aura}`, [[0, hexAlpha(aura, 1)], [1, hexAlpha(aura, 0)]]);
      this.blitBlob(g, s.x, fy, r, r * 0.45, 0.12 * night, "lighter");
    }

    // moonlight: a faint cool wash from the top of the frame on deep, non-golden nights, so
    // the darkness reads silvery-magical rather than flat black.
    const moon = night * (1 - goldenAt(this.engine.clockMinutes));
    if (moon > 0.02) {
      const vy = this.cam.y;
      const vh = this.cssH / this.cam.zoom;
      const mw = ctx.createLinearGradient(0, vy, 0, vy + vh * 0.55);
      mw.addColorStop(0, `rgba(150,178,220,${0.07 * moon})`);
      mw.addColorStop(1, "rgba(150,178,220,0)");
      ctx.fillStyle = mw;
      ctx.fillRect(vL, vy, vR - vL, vh);
    }

    ctx.restore();
  }

  // Tint the whole visible frame toward the current time-of-day ambient colour, as a real
  // vertical gradient: cooler & bluer up top (sky-ward), the base ambient across the middle,
  // and a slightly deeper foreground. Warm/low-alpha day washes use source-over (coloured
  // light); the dark cool night tint uses multiply so it darkens without a milky flatten.
  private drawAmbientGrade() {
    const ctx = this.ctx;
    const amb = ambientAt(this.engine.clockMinutes);
    if (amb.a <= 0.001) return;
    const night = nightAt(this.engine.clockMinutes);
    const vx = this.cam.x;
    const vy = this.cam.y;
    const vw = this.cssW / this.cam.zoom;
    const vh = this.cssH / this.cam.zoom;
    const r = amb.r | 0, g = amb.g | 0, b = amb.b | 0;
    const rgba = (rr: number, gg: number, bb: number, aa: number) =>
      `rgba(${clamp255(rr)},${clamp255(gg)},${clamp255(bb)},${aa})`;
    const grad = ctx.createLinearGradient(0, vy, 0, vy + vh);
    grad.addColorStop(0, rgba(r - 16, g - 8, b + 14, amb.a)); // sky: cooler, bluer
    grad.addColorStop(0.55, rgba(r, g, b, amb.a)); // horizon: the base ambient
    grad.addColorStop(1, rgba(r - 10, g - 10, b - 2, amb.a * 1.06)); // foreground: deeper
    ctx.save();
    ctx.globalCompositeOperation = night > 0.15 ? "multiply" : "source-over";
    ctx.fillStyle = grad;
    ctx.fillRect(vx, vy, vw, vh);
    ctx.restore();
  }

  // Golden-hour horizon glow: a warm additive band raking across the boulevard at sunrise and
  // sunset — the low sun on the street. Zero (and free) at midday and deep night. Dawn skews
  // pinker/cooler, dusk hotter/oranger.
  private drawGoldenHour() {
    const golden = goldenAt(this.engine.clockMinutes);
    if (golden <= 0.001) return;
    const ctx = this.ctx;
    const vx = this.cam.x;
    const vy = this.cam.y;
    const vw = this.cssW / this.cam.zoom;
    const vh = this.cssH / this.cam.zoom;
    const dusk = ((this.engine.clockMinutes % 1440) + 1440) % 1440 > 720;
    const [wr, wg, wb] = dusk ? [255, 122, 58] : [255, 178, 130];
    const hy = (ROAD_TOP + ROAD_BOTTOM) / 2; // the street horizon the glow peaks on
    const span = 640;
    const grad = ctx.createLinearGradient(0, hy - span, 0, hy + span);
    grad.addColorStop(0, `rgba(${wr},${wg},${wb},0)`);
    grad.addColorStop(0.5, `rgba(${wr},${wg},${wb},${0.17 * golden})`);
    grad.addColorStop(1, `rgba(${wr},${wg},${wb},0)`);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.fillStyle = grad;
    ctx.fillRect(vx, vy, vw, vh);
    ctx.restore();
  }

  private drawRoad() {
    const ctx = this.ctx;
    this.fillTiled(0, ROAD_TOP, WORLD_W, ROAD_BOTTOM, "asphalt.jpg");

    ctx.strokeStyle = "#d8c96a";
    ctx.setLineDash([26, 20]);
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, (ROAD_TOP + ROAD_BOTTOM) / 2);
    ctx.lineTo(WORLD_W, (ROAD_TOP + ROAD_BOTTOM) / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Cross streets — each a full-height vertical road with flanking sidewalks, dashed
    // centre line, crosswalk stripes at the Blvd intersection, and a rotated street label.
    const crosswalk = this.getTile("crosswalk.jpg");
    const cwReady = crosswalk && crosswalk.complete && crosswalk.naturalWidth > 0;
    for (const cs of CROSS_STREETS) {
      const roadL = cs.x - CS_ROAD_HALF;
      const roadR = cs.x + CS_ROAD_HALF;
      this.fillTiled(roadL, 0, roadR, WORLD_H, "asphalt.jpg");
      ctx.strokeStyle = "#d8c96a";
      ctx.setLineDash([22, 18]);
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(cs.x, 0);
      ctx.lineTo(cs.x, WORLD_H);
      ctx.stroke();
      ctx.setLineDash([]);

      // Zebra crosswalk across the boulevard, aligned to the cross-street corridor.
      if (cwReady && cs.x + CS_ROAD_HALF > this.cam.x && cs.x - CS_ROAD_HALF < this.cam.x + this.cssW / this.cam.zoom) {
        ctx.drawImage(crosswalk!, roadL, ROAD_TOP + 2, roadR - roadL, ROAD_BOTTOM - ROAD_TOP - 4);
      } else if (!cwReady) {
        ctx.fillStyle = "#e7e2d2";
        for (let px = roadL - 6; px < roadR + 6; px += 14) {
          ctx.fillRect(px, ROAD_TOP + 6, 8, ROAD_BOTTOM - ROAD_TOP - 12);
        }
      }

      ctx.save();
      ctx.fillStyle = "#efe4bd";
      ctx.font = "bold 22px sans-serif";
      ctx.textAlign = "left";
      ctx.translate(cs.x + 8, ROAD_BOTTOM + 320);
      ctx.rotate(Math.PI / 2);
      ctx.fillText(cs.name, 0, 0);
      ctx.restore();
    }

    // "HOLLYWOOD BLVD" repeated down the asphalt, skipping the intersections.
    ctx.fillStyle = "#efe4bd";
    ctx.font = "bold 26px sans-serif";
    ctx.textAlign = "left";
    const blvdY = ROAD_TOP + (ROAD_BOTTOM - ROAD_TOP) / 2 + 9;
    for (let lx = 300; lx < WORLD_W; lx += 1300) {
      if (CROSS_STREETS.some((cs) => lx > cs.x - CS_HALF - 260 && lx < cs.x + CS_HALF + 40)) continue;
      ctx.fillText("HOLLYWOOD BLVD", lx, blvdY);
    }
  }

  private drawStar(cx: number, cy: number, outerR: number, innerR: number, color: string) {
    const ctx = this.ctx;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const r = i % 2 === 0 ? outerR : innerR;
      const a = (Math.PI / 5) * i - Math.PI / 2;
      const px = Math.cos(a) * r;
      const py = Math.sin(a) * r;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.restore();
  }

  private drawWalkOfFame(y: number) {
    const ctx = this.ctx;
    const star = this.getTile("star.png");
    const ready = star && star.complete && star.naturalWidth > 0;
    const vx = this.cam.x;
    const vR = vx + this.cssW / this.cam.zoom;
    const S = 40; // world-units per star plaque
    for (let x = 70; x < WORLD_W - 70; x += 72) {
      if (x < vx - S || x > vR + S) continue;
      if (CROSS_STREETS.some((cs) => x > cs.x - CS_HALF - 20 && x < cs.x + CS_HALF + 20)) continue;
      if (ready) {
        ctx.drawImage(star!, x - S / 2, y - S / 2, S, S);
      } else {
        ctx.fillStyle = "#6b4a86";
        ctx.beginPath();
        ctx.ellipse(x, y, 20, 9, 0, 0, Math.PI * 2);
        ctx.fill();
        this.drawStar(x, y, 8, 3.6, "#e9c96b");
      }
    }
  }

  // A cached, bilinear-smoothed NEUTRAL-grey noise pattern for the ground mottle. Baked once: a
  // tiny 12×12 deterministic value-noise grid upscaled to 256px with smoothing (organic, no hard
  // cells), then tiled at NOISE_WORLD units so the period is far larger than any building — it
  // never reads as a stamp. Neutral so it only breaks the asphalt mirror-tile's symmetry without
  // adding a colour cast. `undefined` = not built yet; `null` = build failed (skip).
  private noisePattern?: CanvasPattern | null;
  private getNoisePattern(): CanvasPattern | null {
    if (this.noisePattern !== undefined) return this.noisePattern;
    const N = 12;
    const lo = document.createElement("canvas");
    lo.width = N; lo.height = N;
    const lc = lo.getContext("2d");
    if (!lc) return (this.noisePattern = null);
    const id = lc.createImageData(N, N);
    for (let y = 0; y < N; y++)
      for (let x = 0; x < N; x++) {
        const v = (groundHash(x * 7 + 3, y * 7 + 11) - 0.5) * 2; // -1..1
        const k = 1 + v * 0.42; // brightness around the base tone
        const i = (y * N + x) * 4;
        id.data[i] = clamp255(0x2c * k + 4 * v); // neutral grey — matches the asphalt base
        id.data[i + 1] = clamp255(0x2a * k + 4 * v);
        id.data[i + 2] = clamp255(0x27 * k + 4 * v);
        id.data[i + 3] = 255;
      }
    lc.putImageData(id, 0, 0);
    const hi = document.createElement("canvas");
    hi.width = 256; hi.height = 256;
    const hc = hi.getContext("2d");
    if (!hc) return (this.noisePattern = null);
    hc.imageSmoothingEnabled = true;
    hc.imageSmoothingQuality = "high";
    hc.drawImage(lo, 0, 0, N, N, 0, 0, 256, 256);
    const pat = this.ctx.createPattern(hi, "repeat");
    if (pat) pat.setTransform(new DOMMatrix([NOISE_WORLD / 256, 0, 0, NOISE_WORLD / 256, 0, 0]));
    return (this.noisePattern = pat ?? null);
  }

  // Visible boulevard x-segments, skipping the cross-street mouths (so every edge/curb has a
  // curb-cut at each intersection). Shared by the curb + joint routines.
  private forEachStreetSpan(cb: (x0: number, x1: number) => void): void {
    const vx = this.cam.x;
    const end = vx + this.cssW / this.cam.zoom + 20;
    let cursor = vx - 20;
    const cuts = CROSS_STREETS.map((cs) => [cs.x - CS_HALF, cs.x + CS_HALF] as [number, number])
      .filter((c) => c[1] > cursor && c[0] < end)
      .sort((a, b) => a[0] - b[0]);
    for (const [c0, c1] of cuts) {
      if (c0 > cursor) cb(cursor, Math.min(c0, end));
      cursor = Math.max(cursor, c1);
    }
    if (cursor < end) cb(cursor, end);
  }

  // A concrete CURB where a raised sidewalk meets a lower surface — a crisp architectural edge, not
  // a blend ("edge the built"). `lowDy` points from the seam toward the LOW side (+1 = low is
  // down-screen/nearer, -1 = low is up-screen/farther). `kind`: "road" adds a gutter trough,
  // "grass" a green drop-shadow + overhanging blades, "lot" a plain paved lot. All code-drawn.
  private drawCurb(y: number, lowDy: 1 | -1, kind: "road" | "grass" | "lot"): void {
    const ctx = this.ctx;
    const lipH = 6;
    const shH = kind === "road" ? 9 : 10;
    const sc = kind === "grass" ? "10,18,6" : "5,5,9"; // shadow colour (green over grass, else cool)
    ctx.save();
    this.forEachStreetSpan((x0, x1) => {
      const w = x1 - x0;
      if (w <= 0) return;
      // cast shadow on the LOW side, darkest at the seam, fading away
      const sg = ctx.createLinearGradient(0, y, 0, y + lowDy * shH);
      sg.addColorStop(0, `rgba(${sc},0.5)`);
      sg.addColorStop(1, `rgba(${sc},0)`);
      ctx.fillStyle = sg;
      ctx.fillRect(x0, lowDy > 0 ? y : y - shH, w, shH);
      // concrete curb lip on the HIGH side
      const lipTop = lowDy > 0 ? y - lipH : y;
      ctx.fillStyle = "#8f8a80";
      ctx.fillRect(x0, lipTop, w, lipH);
      ctx.fillStyle = "#b0a998"; // bright outer highlight
      ctx.fillRect(x0, lowDy > 0 ? lipTop : lipTop + lipH - 1.4, w, 1.4);
      ctx.fillStyle = "rgba(28,26,22,0.5)"; // crisp seam line at the boundary
      ctx.fillRect(x0, y - 0.7, w, 1.4);
      // gutter trough for a road (a shallow channel just past the curb)
      if (kind === "road") {
        const gy = lowDy > 0 ? y + shH : y - shH - 7;
        const gg = ctx.createLinearGradient(0, gy, 0, gy + 7);
        gg.addColorStop(0, "rgba(40,40,46,0)");
        gg.addColorStop(0.5, "rgba(22,22,26,0.5)");
        gg.addColorStop(1, "rgba(40,40,46,0)");
        ctx.fillStyle = gg;
        ctx.fillRect(x0, gy, w, 7);
      }
    });
    // grass blades overhanging the curb (grass only, when readable)
    if (kind === "grass" && this.cam.zoom >= 0.3) {
      const vx = this.cam.x;
      const vR = vx + this.cssW / this.cam.zoom;
      for (let x = Math.floor(vx / 24) * 24; x < vR; x += 24) {
        if (CROSS_STREETS.some((cs) => x > cs.x - CS_HALF && x < cs.x + CS_HALF)) continue;
        if (groundHash(x, y + 3) < 0.5) continue;
        const gx = x + (groundHash(x, 5) - 0.5) * 16;
        ctx.fillStyle = groundHash(x, 9) > 0.5 ? "#5f7a3e" : "#6d8747";
        ctx.globalAlpha = 0.85;
        const bl = 3 + groundHash(x, 11) * 3;
        for (let k = -1; k <= 1; k++) {
          ctx.beginPath();
          ctx.moveTo(gx + k * 2.2, y - lowDy * 2);
          ctx.lineTo(gx + k * 2.2 - 1.1, y - lowDy * (2 + bl));
          ctx.lineTo(gx + k * 2.2 + 1.1, y - lowDy * (2 + bl));
          ctx.closePath();
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    }
    ctx.restore();
  }

  // An expansion / construction JOINT between two same-material pavements (asphalt↔asphalt) — a
  // crisp engraved groove, NOT a blend: a thin dark core with a faint highlight just below it.
  private drawExpansionJoint(y: number): void {
    const ctx = this.ctx;
    const vx = this.cam.x;
    const vw = this.cssW / this.cam.zoom;
    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,0.3)";
    ctx.fillRect(vx, y - 0.6, vw, 1.2);
    ctx.fillStyle = "rgba(255,255,255,0.07)";
    ctx.fillRect(vx, y + 0.7, vw, 1);
    ctx.restore();
  }

  // Night light that lands ON the floor — the warm pool each lamp casts on the sidewalk. Drawn as
  // a GROUND pre-pass (after the seams, before the sorted actors) with `lighter`, so souls/props
  // draw OVER it and correctly stand IN the light instead of being washed by it from on top. The
  // airborne globe glow + bloom stay in drawLights (post-pass). Alpha is boosted vs. the old
  // on-top pool because this now sits under the night grade that darkens it.
  private drawFloorGlow(): void {
    const night = nightAt(this.engine.clockMinutes);
    if (night <= 0.001) return;
    const ctx = this.ctx;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    // Each pool is a CLUSTER of a few soft, offset blobs rather than one clean ellipse — the
    // gradient is scaled to a true ellipse (so its falloff isn't a circle clipped by an
    // elliptical path, which is what left a hard edge), and the overlapping offsets smudge the
    // boundary into an organic pool of light instead of a geometric circle.
    this.forEachLamp((x, baseY) => {
      for (let k = 0; k < 3; k++) {
        const ox = (groundHash(x + k * 11, 5) - 0.5) * 42;
        const oy = (groundHash(x + k * 23, 6) - 0.5) * 14;
        const rx = 58 + groundHash(x + k * 7, 7) * 44;
        const ry = rx * 0.42;
        const cxk = x + ox, cyk = baseY + oy;
        const a = (k === 0 ? 0.5 : 0.3) * night;
        const pool = this.bakedGlow("floorPool", [[0, "rgba(255,190,110,1)"], [0.55, "rgba(255,186,106,0.38)"], [1, "rgba(255,190,110,0)"]]);
        this.blitBlob(pool, cxk, cyk, rx, ry, a, "lighter");
      }
    });
    ctx.restore();
  }

  // Core: tile a separator strip in the CURRENT (possibly rotated) coordinate frame. The band runs
  // along local +x from a0..a1, is `cross` units wide across local y, with the art's baked seam line
  // sitting at local y=0 (seamFrac into the source). `skip` is a sorted list of [lo,hi] along-ranges
  // to leave open (curb-cuts at intersections). Sub-samples the source at clipped ends so tiles meet
  // cleanly. Callers set up the transform (identity for horizontal seams, a rotation for vertical).
  private tileBand(
    img: HTMLImageElement,
    a0: number,
    a1: number,
    cross: number,
    seamFrac: number,
    skip: Array<[number, number]>,
  ): void {
    const ctx = this.ctx;
    const iw = img.naturalWidth;
    const ih = img.naturalHeight;
    const tileW = (cross * iw) / ih; // keep the art's aspect so curb blocks aren't stretched
    const yTop = -seamFrac * cross; // seam line at local y=0
    const cuts = skip
      .filter((c) => c[1] > a0 && c[0] < a1)
      .sort((p, q) => p[0] - q[0]);
    let cursor = a0;
    const spans: Array<[number, number]> = [];
    for (const [c0, c1] of cuts) {
      if (c0 > cursor) spans.push([cursor, Math.min(c0, a1)]);
      cursor = Math.max(cursor, c1);
    }
    if (cursor < a1) spans.push([cursor, a1]);
    for (const [s0, s1] of spans) {
      const start = Math.floor(s0 / tileW) * tileW; // anchor tiling to origin (adjacent spans align)
      for (let x = start; x < s1; x += tileW) {
        const dx0 = Math.max(x, s0);
        const dx1 = Math.min(x + tileW, s1);
        if (dx1 <= dx0) continue;
        const su0 = ((dx0 - x) / tileW) * iw; // sub-sample the source for clipped L/R edges
        const su1 = ((dx1 - x) / tileW) * iw;
        ctx.drawImage(img, su0, 0, su1 - su0, ih, dx0, yTop, dx1 - dx0, cross);
      }
    }
  }

  // Hand-painted tile-separator ART band (public/tiles/sep-*.png) tiled horizontally along a seam,
  // feathered top/bottom so it dissolves into the surfaces on either side. The band's `seamFrac`
  // line (the crisp boundary baked into the art) is anchored exactly to the world seam Y; `flip`
  // mirrors the band vertically about that same line (so one asset serves both orientations —
  // sidewalk-above-road AND asphalt-above-sidewalk). Drawn as a GROUND pre-pass (before the sorted
  // actors, so souls/props occlude it), viewport-culled, and skipping cross-street mouths so
  // intersections read as curb-cuts. Returns false (→ code-curb fallback) when the art isn't
  // decoded yet or we're zoomed too far out to read it.
  private drawSeparator(
    name: string,
    seamY: number,
    bandH: number,
    seamFrac: number,
    flip: boolean,
    skip: Array<[number, number]>,
  ): boolean {
    if (this.cam.zoom <= TILE_ZOOM_GATE) return false;
    const img = this.getTile(name);
    if (!img || !img.complete || img.naturalWidth === 0) return false;
    const ctx = this.ctx;
    const vx = this.cam.x;
    const a0 = vx - 20;
    const a1 = vx + this.cssW / this.cam.zoom + 20;
    ctx.save();
    ctx.translate(0, seamY);
    if (flip) ctx.scale(1, -1); // mirror across the seam line (stays put at local y=0)
    this.tileBand(img, a0, a1, bandH, seamFrac, skip);
    ctx.restore();
    return true;
  }

  // A horizontal separator band clipped to a single world-X span [x0,x1] (no tiling gaps) — used for
  // the short curb the cross-street sidewalk presents to the boulevard road south of the intersection.
  private drawSeparatorSpanH(
    name: string,
    seamY: number,
    x0: number,
    x1: number,
    bandH: number,
    seamFrac: number,
    flip: boolean,
  ): boolean {
    if (this.cam.zoom <= TILE_ZOOM_GATE) return false;
    const img = this.getTile(name);
    if (!img || !img.complete || img.naturalWidth === 0) return false;
    const ctx = this.ctx;
    const vx = this.cam.x;
    const a0 = Math.max(x0, vx - 20);
    const a1 = Math.min(x1, vx + this.cssW / this.cam.zoom + 20);
    if (a1 <= a0) return false;
    ctx.save();
    ctx.translate(0, seamY);
    if (flip) ctx.scale(1, -1);
    this.tileBand(img, a0, a1, bandH, seamFrac, []);
    ctx.restore();
    return true;
  }

  // Vertical sibling of drawSeparator for a cross-street's road↔sidewalk edge. The same horizontal
  // strip art is rotated a quarter-turn so its long run of curb blocks travels DOWN the street; the
  // baked seam line lands on the vertical world seam X. `roadOnEast` puts the road (the strip's
  // "bottom") to the +X side; otherwise to −X. `skip` leaves the boulevard mouth open.
  private drawSeparatorV(
    name: string,
    seamX: number,
    bandW: number,
    seamFrac: number,
    roadOnEast: boolean,
    skip: Array<[number, number]>,
  ): boolean {
    if (this.cam.zoom <= TILE_ZOOM_GATE) return false;
    const img = this.getTile(name);
    if (!img || !img.complete || img.naturalWidth === 0) return false;
    const ctx = this.ctx;
    const vy = this.cam.y;
    const a0 = vy - 20;
    const a1 = vy + this.cssH / this.cam.zoom + 20;
    ctx.save();
    // map local +x → world +Y (down the street), local +y → world ±X (sidewalk→road across)
    if (roadOnEast) ctx.transform(0, 1, 1, 0, seamX, 0); // road to +X (east)
    else ctx.transform(0, 1, -1, 0, seamX, 0); // road to −X (west)
    this.tileBand(img, a0, a1, bandW, seamFrac, skip);
    ctx.restore();
    return true;
  }

  // A hand-painted CORNER / RAMP tile placed once (not tiled): the art's registration point
  // (elbowFx, elbowFy as fractions of the source) is pinned to world (px, py); the piece is scaled
  // to `size` world units and optionally mirrored in X/Y so one drawing serves all four rotations.
  // Border-feathered at bake time, so it overlays the underlying tiles and dissolves at its edges.
  private drawCornerTile(
    name: string,
    px: number,
    py: number,
    size: number,
    flipX: boolean,
    flipY: boolean,
    elbowFx: number,
    elbowFy: number,
  ): boolean {
    if (this.cam.zoom <= TILE_ZOOM_GATE) return false;
    const img = this.getTile(name);
    if (!img || !img.complete || img.naturalWidth === 0) return false;
    // viewport cull
    const vx = this.cam.x;
    const vy = this.cam.y;
    const vR = vx + this.cssW / this.cam.zoom;
    const vB = vy + this.cssH / this.cam.zoom;
    if (px + size < vx || px - size > vR || py + size < vy || py - size > vB) return false;
    const iw = img.naturalWidth;
    const ih = img.naturalHeight;
    const h = (size * ih) / iw; // keep aspect
    const ctx = this.ctx;
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(flipX ? -1 : 1, flipY ? -1 : 1);
    // draw so the registration point lands at the origin (= world px,py)
    ctx.drawImage(img, -elbowFx * size, -elbowFy * h, size, h);
    ctx.restore();
    return true;
  }

  // Every boulevard ground boundary is hardscape↔hardscape, so each gets a crisp architectural
  // EDGE (curb / gutter / expansion joint), never a gradient blend ("edge the built"). We prefer
  // the hand-painted separator ART (drawSeparator); the code-drawn drawCurb/drawExpansionJoint are
  // the far-zoom / not-yet-decoded fallback so there's always an edge.
  private drawSeamBlends(): void {
    // Per-curb skip windows. The concrete curb sits at seamFrac in the art (measured: road 0.314,
    // grass 0.60), NOT the band centre — pinning that fraction to the world seam is what makes the
    // straight curb land exactly where the corner curb does (no doubled line).
    // A straight curb runs to its skip edge; a rounded corner is placed at the elbow and only rounds
    // the OUTER edge, so if the straight reaches the elbow the two straights meet in a SQUARE vertex
    // that pokes out past the arc ("stuff coming out of the corner"). Stop each straight ~one corner
    // arc-radius short of the elbow (RCUT road, GCUT grass) so the corner asset alone fills the junction.
    const csRoad: Array<[number, number]> = CROSS_STREETS.map((c) => [c.x - CS_ROAD_HALF - RCUT, c.x + CS_ROAD_HALF + RCUT]); // cross-street ROAD + corner cut
    const csHalf: Array<[number, number]> = CROSS_STREETS.map((c) => [c.x - CS_HALF, c.x + CS_HALF]); // road + flanking sidewalks (no corner here)
    const csGrass: Array<[number, number]> = CROSS_STREETS.map((c) => [c.x - CS_HALF - GCUT, c.x + CS_HALF + GCUT]); // grass corner cut at SOUTH_SIDEWALK_BOTTOM
    // Round the SIDEWALK fill's square corner at each intersection so the terrazzo can't poke past the
    // rounded curb onto the asphalt ("no sidewalk bleeding onto the street"). Runs before the curbs.
    this.drawCornerNooks();
    // back-lot(asphalt) ↔ north sidewalk — sidewalk BELOW, flip. Cut where cross-street sidewalk
    // makes it sidewalk↔sidewalk (±CS_HALF). All road curbs use the CURB-ONLY strip (just the
    // concrete lip + its shadow) so they never paint fill over the world sidewalk/asphalt.
    if (!this.drawSeparator("sep-road-curb.png", NORTH_SIDEWALK_TOP, RCH, RCF, true, csHalf))
      this.drawCurb(NORTH_SIDEWALK_TOP, -1, "lot");
    // north sidewalk ↔ boulevard road — sidewalk ABOVE. Curb continues over the cross-street
    // SIDEWALK (it's still sidewalk↔road there), so cut only at the cross-street ROAD (±CS_ROAD_HALF).
    if (!this.drawSeparator("sep-road-curb.png", ROAD_TOP, RCH, RCF, false, csRoad))
      this.drawCurb(ROAD_TOP, 1, "road");
    // road ↔ south back-lot — asphalt↔asphalt construction joint (cut around the whole crossing)
    if (!this.drawSeparator("sep-joint.png", ROAD_BOTTOM, 26, 0.5, false, csHalf))
      this.drawExpansionJoint(ROAD_BOTTOM);
    // south back-lot(asphalt) ↔ south sidewalk — sidewalk BELOW, flip
    if (!this.drawSeparator("sep-road-curb.png", SOUTH_SIDEWALK_TOP, RCH, RCF, true, csHalf))
      this.drawCurb(SOUTH_SIDEWALK_TOP, -1, "lot");
    // south sidewalk ↔ residential grass — curb+grass only (sidewalk cut, grass bleeds onto grass)
    if (!this.drawSeparator("sep-grass-curb.png", SOUTH_SIDEWALK_BOTTOM, GCH, GCF, false, csGrass))
      this.drawCurb(SOUTH_SIDEWALK_BOTTOM, 1, "grass");
    // vertical cross-street curbs + the rounded intersection/yard corners
    this.drawCrossStreetSeams();
  }

  // Round the sidewalk fill's square corner at each intersection: fill asphalt into the little nook
  // between the terrazzo's square corner and where the rounded curb sits, so the sidewalk tile can't
  // bleed past the curb onto the street. `dx,dy` point from the elbow toward the sidewalk quadrant;
  // an evenodd clip (corner square MINUS the curb-radius disc) fills only the poking nook.
  private drawCornerNooks(): void {
    if (this.cam.zoom <= TILE_ZOOM_GATE) return;
    const vx = this.cam.x;
    const vR = vx + this.cssW / this.cam.zoom;
    const r = 28; // ≈ the road corner's arc radius
    const nook = (ex: number, ey: number, dx: number, dy: number) => {
      const ctx = this.ctx;
      const sx0 = Math.min(ex, ex + dx * r);
      const sy0 = Math.min(ey, ey + dy * r);
      ctx.save();
      ctx.beginPath();
      ctx.rect(sx0, sy0, r, r);
      ctx.arc(ex + dx * r, ey + dy * r, r, 0, Math.PI * 2);
      ctx.clip("evenodd");
      this.fillTiled(sx0, sy0, sx0 + r, sy0 + r, "asphalt.jpg");
      ctx.restore();
    };
    for (const cs of CROSS_STREETS) {
      if (cs.x + CS_ROAD_HALF < vx - 40 || cs.x - CS_ROAD_HALF > vR + 40) continue;
      nook(cs.x - CS_ROAD_HALF, ROAD_TOP, -1, -1); // NW sidewalk corner
      nook(cs.x + CS_ROAD_HALF, ROAD_TOP, 1, -1); // NE
      nook(cs.x - CS_ROAD_HALF, ROAD_BOTTOM, -1, 1); // SW
      nook(cs.x + CS_ROAD_HALF, ROAD_BOTTOM, 1, 1); // SE
    }
  }

  // Cross-street edges: the vertical road↔sidewalk curbs down each cross street, the vertical
  // grass↔sidewalk curbs in the residential zone, the short curb the cross-street sidewalk shows the
  // boulevard south of the intersection, and the rounded corner pieces where a raised sidewalk turns.
  // The corner art is STROKED from the same strip (sep-corner-*), so its curb is byte-identical to
  // the straight bands' curb — arms overlap the straights seamlessly, no doubled line, no overlap
  // halo. Convex (road: sidewalk juts into the road) vs concave (grass: sidewalk wraps a lawn pocket)
  // are baked separately. Elbow fraction + world size come from the bake (curb at strip resolution).
  private drawCrossStreetSeams(): void {
    if (this.cam.zoom <= TILE_ZOOM_GATE) return;
    const vx = this.cam.x;
    const vR = vx + this.cssW / this.cam.zoom;
    // Vertical curbs also stop short of their corner elbows (RCUT/GCUT) so their square end can't poke
    // past the rounded corner at ROAD_TOP / ROAD_BOTTOM / SOUTH_SIDEWALK_BOTTOM.
    const mouth: Array<[number, number]> = [[ROAD_TOP - 2 - RCUT, ROAD_BOTTOM + 2 + RCUT]]; // road curb: open at blvd + corner cut
    const grassOnly: Array<[number, number]> = [[0, SOUTH_SIDEWALK_BOTTOM + GCUT]]; // grass curb: yards only, cut below the elbow
    // Corner geometry comes from bake_stroke.js. The road corner is baked CURB-ONLY (the strip is
    // cropped to just the concrete lip before stroking) so it never paints the flanking sidewalk/road
    // — the world tiles show through on both sides, no bright patch, no street bleed. Elbow fraction +
    // world size are read from the bake; RC is scaled so the corner's curb band == RCH (matched
    // thickness so the arc and the straight curb read as one thin, un-chunky line at the join).
    const RE = 0.847; // road-corner elbow fraction (curb-only stroked bake)
    const RC = 55; // road-corner world size (399px ÷ 7.25px/u so curb band = RCH=10)
    const GE = 0.713; // grass-corner elbow fraction (sidewalk-cut concave bake)
    const GC = 101; // grass-corner world size (516px ÷ 5.09px/u; band = GCH)
    for (const cs of CROSS_STREETS) {
      if (cs.x + CS_HALF < vx - 20 || cs.x - CS_HALF > vR + 20) continue;
      // vertical road curbs (road EAST of the west seam, WEST of the east seam), open at the blvd
      this.drawSeparatorV("sep-road-curb.png", cs.x - CS_ROAD_HALF, RCH, RCF, true, mouth);
      this.drawSeparatorV("sep-road-curb.png", cs.x + CS_ROAD_HALF, RCH, RCF, false, mouth);
      // vertical grass curbs on the cross-street's OUTER sidewalk edges, residential grass only
      this.drawSeparatorV("sep-grass-curb.png", cs.x - CS_HALF, GCH, GCF, false, grassOnly);
      this.drawSeparatorV("sep-grass-curb.png", cs.x + CS_HALF, GCH, GCF, true, grassOnly);
      // short curb the cross-street sidewalk shows the boulevard road, just SOUTH of the crossing
      // (road ABOVE, sidewalk below → flipped). Bridges the vertical road curb up to ROAD_BOTTOM.
      this.drawSeparatorSpanH("sep-road-curb.png", ROAD_BOTTOM, cs.x - CS_HALF, cs.x - CS_ROAD_HALF - RCUT, RCH, RCF, true);
      this.drawSeparatorSpanH("sep-road-curb.png", ROAD_BOTTOM, cs.x + CS_ROAD_HALF + RCUT, cs.x + CS_HALF, RCH, RCF, true);
      // (a) road corners — all four: the sidewalk wraps each corner of the intersection (convex)
      this.drawCornerTile("sep-corner-road.png", cs.x - CS_ROAD_HALF, ROAD_TOP, RC, false, false, RE, RE); // NW
      this.drawCornerTile("sep-corner-road.png", cs.x + CS_ROAD_HALF, ROAD_TOP, RC, true, false, RE, RE); // NE
      this.drawCornerTile("sep-corner-road.png", cs.x - CS_ROAD_HALF, ROAD_BOTTOM, RC, false, true, RE, RE); // SW
      this.drawCornerTile("sep-corner-road.png", cs.x + CS_ROAD_HALF, ROAD_BOTTOM, RC, true, true, RE, RE); // SE
      // (b) grass corners — the south sidewalk wraps the lawn pocket beside each cross-street (concave)
      this.drawCornerTile("sep-corner-grass.png", cs.x - CS_HALF, SOUTH_SIDEWALK_BOTTOM, GC, false, true, GE, GE); // grass SW pocket
      this.drawCornerTile("sep-corner-grass.png", cs.x + CS_HALF, SOUTH_SIDEWALK_BOTTOM, GC, true, true, GE, GE); // grass SE pocket
    }
  }

  // The ground plane, drawn first behind everything. A base tone, a smooth all-zoom mottle so the
  // land between buildings has organic texture instead of a flat void, and a grass yard under
  // the residential back-street. All viewport-culled, all deterministic.
  private drawGround() {
    const ctx = this.ctx;
    const vx = this.cam.x;
    const vy = this.cam.y;
    const vw = this.cssW / this.cam.zoom;
    const vh = this.cssH / this.cam.zoom;

    // Real paved base — dark asphalt behind/around the buildings (user art). Flat-fills its
    // neutral fallback while the texture decodes / when zoomed way out. The road, sidewalk, grass
    // and plaza tiles all draw AFTER this, so the asphalt only shows through on the open ground
    // between and behind the buildings — replacing the old ugly brown fill.
    ctx.fillStyle = GROUND_FALLBACK["backlot.jpg"];
    ctx.fillRect(vx, vy, vw, vh);
    this.fillTiled(vx, vy, vx + vw, vy + vh, "backlot.jpg");

    // A faint smooth low-frequency mottle over the base for anti-repeat only (breaks the
    // mirror-tile's symmetry without muddying the texture).
    const noise = this.getNoisePattern();
    if (noise) {
      ctx.save();
      ctx.globalAlpha = 0.22;
      ctx.fillStyle = noise;
      ctx.fillRect(vx, vy, vw, vh);
      ctx.restore();
    }

    // residential back-street: one continuous grass lawn (the houses grow up from BACK_Y and land
    // on top). Uniform grass — no per-lot soil pick — so there's no hard seam between neighbours.
    const yardTop = SOUTH_SIDEWALK_BOTTOM + 4;
    this.fillTiled(0, yardTop, WORLD_W, WORLD_H, "grass.jpg");
  }

  // Concrete aprons at every storefront's foot, and richer terrazzo plazas at the landmarks.
  // Painted onto the boulevard sidewalks after the N/S rows are laid out, in front of (not
  // over) the buildings and beneath the NPCs. Viewport-culled; landmark speckle deterministic.
  private drawGroundDetail() {
    const ctx = this.ctx;
    const vx = this.cam.x;
    const vR = vx + this.cssW / this.cam.zoom;
    for (const f of [...NORTH_FRONTAGES, ...SOUTH_FRONTAGES]) {
      const walkTop = f.side === "north" ? NORTH_SIDEWALK_TOP : SOUTH_SIDEWALK_TOP;
      for (const b of f.buildings) {
        const bx = b.x ?? 0;
        const bw = b.width ?? 0;
        if (bx + bw < vx - 40 || bx > vR + 40 || bw <= 0) continue;
        const landmark = !!b.marquee;
        if (landmark) {
          // ornate terrazzo forecourt across the landmark's whole sidewalk frontage
          this.fillTiled(bx + 4, walkTop, bx + bw - 4, walkTop + 58, "plaza.jpg");
        } else {
          // a subtle concrete apron/curb at plain storefront feet
          ctx.fillStyle = "#7a746b";
          ctx.fillRect(bx + 6, walkTop + 1, bw - 12, 12);
        }
      }
    }
  }


  private drawSidewalks() {
    // Hollywood Blvd sidewalks (full width) — real tiled terrazzo
    this.fillTiled(0, NORTH_SIDEWALK_TOP, WORLD_W, NORTH_SIDEWALK_BOTTOM, "sidewalk.jpg");
    this.fillTiled(0, SOUTH_SIDEWALK_TOP, WORLD_W, SOUTH_SIDEWALK_BOTTOM, "sidewalk.jpg");
    // Cross-street sidewalks (full height, flanking each cross road)
    for (const cs of CROSS_STREETS) {
      this.fillTiled(cs.x - CS_HALF, 0, cs.x - CS_ROAD_HALF, WORLD_H, "sidewalk.jpg");
      this.fillTiled(cs.x + CS_ROAD_HALF, 0, cs.x + CS_HALF, WORLD_H, "sidewalk.jpg");
    }
    this.drawWalkOfFame(NORTH_SIDEWALK_TOP + 30);
    this.drawWalkOfFame(SOUTH_SIDEWALK_TOP + 30);
  }

  // Live art ratio (w/h) for a building's facade — the true image aspect once loaded,
  // else the nominal `aspect` authored on the lot (so layout is right on the first frame
  // and headless). This is what makes the row re-flow when a facade is regenerated.
  private aspectOf = (b: Building): number => {
    if (b.sprite) {
      const img = this.getBuildingSprite(b.sprite);
      if (img && img.complete && img.naturalWidth > 0) return img.naturalWidth / img.naturalHeight;
    }
    return b.aspect ?? (b.width && b.height ? b.width / b.height : 0.9);
  };

  private drawBuilding(b: Building) {
    const ctx = this.ctx;

    // Real facade art, when present, replaces the code-drawn placeholder.
    if (b.sprite) {
      const img = this.getBuildingSprite(b.sprite);
      if (img && img.complete && img.naturalWidth > 0) {
        this.drawBuildingSprite(b, img);
        return;
      }
    }

    const width = b.width ?? 120;
    const height = b.height ?? 90;
    const side = b.side ?? "north";
    const depth = b.depth ?? 34;
    const skew = b.skew ?? width * 0.14;
    const df = b.dim ?? 1;
    const dk = Math.round((df - 1) * 55); // <= 0: pushes dim rows back / darker
    const facadeColor = shade(b.facadeColor ?? "#5b6b7a", dk);
    const roofColor = b.roofColor ? shade(b.roofColor, dk) : shade(facadeColor, -28);
    const sideColor = shade(facadeColor, -42);
    const x = b.x;

    // Base sits on the sidewalk line and the facade grows UP.
    const baseY = b.baseY ?? (side === "north" ? NORTH_BASELINE : SOUTH_BASELINE);
    const dir = (b.growUp ?? true) ? -1 : 1;
    const facadeTopY = baseY + dir * height;
    const topEdge = Math.min(baseY, facadeTopY);

    ctx.fillStyle = sideColor;
    ctx.beginPath();
    ctx.moveTo(x + width, baseY);
    ctx.lineTo(x + width, facadeTopY);
    ctx.lineTo(x + width - skew, facadeTopY + dir * depth);
    ctx.lineTo(x + width - skew, baseY + dir * depth);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = roofColor;
    ctx.beginPath();
    ctx.moveTo(x, facadeTopY);
    ctx.lineTo(x + width, facadeTopY);
    ctx.lineTo(x + width - skew, facadeTopY + dir * depth);
    ctx.lineTo(x - skew, facadeTopY + dir * depth);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = facadeColor;
    ctx.fillRect(x, Math.min(baseY, facadeTopY), width, height);

    ctx.fillStyle = shade(facadeColor, df < 1 ? 12 : 22);
    const rows = Math.max(1, Math.floor(height / 34) - 1);
    const cols = Math.max(2, Math.floor(width / 46));
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const wx = x + 12 + (c * (width - 24)) / cols;
        const wy = topEdge + 14 + r * 30;
        ctx.fillRect(wx, wy, 16, 18);
      }
    }

    if (b.marquee) {
      ctx.fillStyle = b.marqueeColor ?? "#e64444";
      const my = topEdge + 6;
      ctx.fillRect(x + 6, my, width - 12, 22);
      ctx.fillStyle = "#fff8e2";
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(b.marquee, x + width / 2, my + 15);
    }

    if (b.label) {
      ctx.fillStyle = "#f3ecd8";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      const labelY = baseY - 6;
      ctx.fillText(b.label, x + width / 2, labelY);
    }
  }

  private getVehicle(type: string): HTMLImageElement | null {
    const key = `v:${type}`;
    const cached = this.sprites.get(key);
    if (cached !== undefined) return cached;
    const img = new Image();
    img.decoding = "async"; // decode off the critical path — avoids a first-draw hitch mid-frame
    img.onerror = () => this.sprites.set(key, null);
    img.src = `/vehicles/${type}.png`;
    this.sprites.set(key, img);
    return img;
  }

  private getProp(name: string): HTMLImageElement | null {
    const key = `p:${name}`;
    const cached = this.sprites.get(key);
    if (cached !== undefined) return cached;
    const img = new Image();
    img.decoding = "async"; // decode off the critical path — avoids a first-draw hitch mid-frame
    img.onerror = () => this.sprites.set(key, null);
    img.src = `/props/${name}.png`;
    this.sprites.set(key, img);
    return img;
  }

  private drawProp(name: string, x: number, footY: number): void {
    const img = this.getProp(name);
    if (!img || !img.complete || img.naturalWidth === 0) return;
    const h = PROP_H[name] ?? 40;
    const w = h * (img.naturalWidth / img.naturalHeight);
    // Grounding: directional time-of-day cast shadow (silhouette-shaped) + a tight seam-only foot
    // contact (props have a small footprint, and now carry the real cast shadow).
    this.drawCastShadow(img.src, img, x, footY, w, h);
    this.drawContactShadow(x, footY, w * 0.7, h, 0.7, true);
    this.ctx.drawImage(img, x - w / 2, footY - h, w, h);
  }

  // Enumerate every sidewalk prop placement (name, x, footY): a palm-heavy scatter with an
  // occasional set-piece, plus a traffic signal at each intersection corner. Viewport-culled,
  // deterministic (placement is a pure function of x). Fed into the depth pass so props sort
  // against pedestrians.
  private forEachProp(cb: (name: string, x: number, footY: number) => void): void {
    const vx = this.cam.x;
    const vR = vx + this.cssW / this.cam.zoom;
    const feet = [NORTH_SIDEWALK_TOP + 50, SOUTH_SIDEWALK_BOTTOM - 6];
    for (let si = 0; si < feet.length; si++) {
      const footY = feet[si];
      let slot = 0;
      for (let x = 130; x < WORLD_W - 130; x += PROP_STEP, slot++) {
        if (x < vx - 260 || x > vR + 260) continue;
        if (CROSS_STREETS.some((cs) => x > cs.x - CS_HALF - 34 && x < cs.x + CS_HALF + 34)) continue;
        const jitter = (groundHash(slot * 5 + si * 61, 3) - 0.5) * 40;
        const name =
          (slot + si) % 8 === 5
            ? PROP_SETPIECES[(slot + si * 2) % PROP_SETPIECES.length]
            : PROP_SCATTER[(slot * 2 + si) % PROP_SCATTER.length];
        cb(name, x + jitter, footY);
      }
    }
    // traffic signals at the boulevard corners of each cross street
    for (const cs of CROSS_STREETS) {
      if (cs.x + 200 < vx || cs.x - 200 > vR) continue;
      cb("traffic-signal", cs.x - CS_ROAD_HALF - 16, NORTH_SIDEWALK_TOP + 50);
      cb("traffic-signal", cs.x + CS_ROAD_HALF + 16, SOUTH_SIDEWALK_BOTTOM - 6);
    }
  }

  // Measure a character sprite's non-transparent vertical extent once and cache it. Returns the
  // top/bottom of the visible body as fractions of natural height (t..b), so callers can scale the
  // content to a uniform height and plant the feet. Downsamples for a cheap one-time alpha scan.
  private spriteBounds(key: string, img: HTMLImageElement): { t: number; b: number } {
    const hit = this.boundsCache.get(key);
    if (hit) return hit;
    const full = { t: 0, b: 1 };
    if (!img.complete || img.naturalWidth === 0) return full; // not decoded yet — don't cache
    const mc = (this.measureCanvas ??= document.createElement("canvas"));
    const sw = Math.min(img.naturalWidth, 48);
    const sh = Math.min(img.naturalHeight, 240);
    mc.width = sw;
    mc.height = sh;
    const mx = mc.getContext("2d", { willReadFrequently: true });
    if (!mx) return full;
    mx.clearRect(0, 0, sw, sh);
    mx.drawImage(img, 0, 0, sw, sh);
    let top = -1;
    let bot = -1;
    try {
      const px = mx.getImageData(0, 0, sw, sh).data;
      for (let y = 0; y < sh; y++) {
        let row = false;
        for (let x = 0; x < sw; x++) {
          if (px[(y * sw + x) * 4 + 3] > 16) {
            row = true;
            break;
          }
        }
        if (row) {
          if (top < 0) top = y;
          bot = y;
        }
      }
    } catch {
      return full; // tainted canvas (shouldn't happen same-origin) — fall back to full frame
    }
    const res = top < 0 ? full : { t: top / sh, b: (bot + 1) / sh };
    this.boundsCache.set(key, res);
    return res;
  }

  private getPed(index: number): HTMLImageElement | null {
    const key = `n:${index}`;
    const cached = this.sprites.get(key);
    if (cached !== undefined) return cached;
    const img = new Image();
    img.decoding = "async"; // decode off the critical path — avoids a first-draw hitch mid-frame
    img.onerror = () => this.sprites.set(key, null);
    img.src = `/npc/ped_${String(index).padStart(3, "0")}.png`;
    this.sprites.set(key, img);
    return img;
  }

  // One ambient pedestrian: feet-anchored, mirrored to face travel, with a gentle walk bob. No
  // aura/ring — background, cheaper than the named cast. Drawn from the depth pass.
  private drawPed(ped: AmbientPed, t: number): void {
    const img = this.getPed(ped.sprite);
    if (!img || !img.complete || img.naturalWidth === 0) return;
    const ctx = this.ctx;
    // Normalize to a uniform body height, feet planted (see spriteBounds / CHAR_BODY_H).
    const b = this.spriteBounds(`n:${ped.sprite}`, img);
    const frameH = CHAR_BODY_H / Math.max(0.5, b.b - b.t);
    const w = frameH * (img.naturalWidth / img.naturalHeight);
    const bob = Math.sin((t + ped.bob) / 150) * 1.6;
    const feetY = ped.y + FEET_DROP + bob;
    const top = feetY - b.b * frameH;
    // Sun cast shadow + soft foot contact (same sun as everything else), then the smoky walk FX +
    // pendulum leg-blur behind the ped. The FX is imperceptible when zoomed out but costs ~9
    // gradient-blits + drawImages per ped per frame, so gate it to a readable zoom (FX_ZOOM).
    this.drawCastShadow(`n:${ped.sprite}`, img, ped.x, feetY, w, frameH, 0.85);
    this.drawContactShadow(ped.x, feetY, w * 0.5, frameH, 1, true);
    if (this.cam.zoom >= FX_ZOOM) {
      this.drawWalkFX(ped.x, ped.y + FEET_DROP, w, ped.dir, t, (ped.bob % 1000) / 1000);
      this.drawLegBlur(img, b, ped.x, feetY, w, ped.dir < 0, t, ped.bob);
    }
    const prev = ctx.imageSmoothingEnabled;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.save();
    if (ped.dir < 0) {
      ctx.translate(ped.x, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(img, -w / 2, top, w, frameH);
    } else {
      ctx.drawImage(img, ped.x - w / 2, top, w, frameH);
    }
    ctx.restore();
    ctx.imageSmoothingEnabled = prev;
  }

  private static CAR_FALLBACK = ["#b23b3b", "#3b5fb2", "#c9c9c9", "#e0a733"];
  // One vehicle, wheel-anchored to its lane and mirrored to face travel. Drawn from the depth pass.
  private drawCar(car: CarRuntime, i: number): void {
    const ctx = this.ctx;
    const img = this.getVehicle(car.type);
    if (img && img.complete && img.naturalWidth > 0) {
      const h = VEHICLES[car.type] ?? 54;
      const w = h * (img.naturalWidth / img.naturalHeight);
      ctx.save();
      // art faces LEFT; mirror when travelling right. Wheels sit on car.y.
      if (car.dir > 0) {
        ctx.translate(car.x + w / 2, car.y - h);
        ctx.scale(-1, 1);
        ctx.drawImage(img, -w / 2, 0, w, h);
      } else {
        ctx.drawImage(img, car.x - w / 2, car.y - h, w, h);
      }
      ctx.restore();
      return;
    }
    // fallback box until the sprite loads
    ctx.fillStyle = HollywoodRenderer.CAR_FALLBACK[i % HollywoodRenderer.CAR_FALLBACK.length];
    ctx.fillRect(car.x, car.y - 10, 46, 20);
    ctx.fillStyle = "#dff0ff";
    ctx.fillRect(car.x + 8, car.y - 7, 12, 8);
    ctx.fillRect(car.x + 26, car.y - 7, 12, 8);
  }

  // Load a spirit sprite once; returns the <img> (which may still be loading), or null
  // if it 404'd (→ code-drawn fallback). Drop a PNG into public/spirits/<id>.png and it
  // appears automatically.
  private getSprite(id: string): HTMLImageElement | null {
    const cached = this.sprites.get(id);
    if (cached !== undefined) return cached;
    const img = new Image();
    img.decoding = "async"; // decode off the critical path — avoids a first-draw hitch mid-frame
    img.onerror = () => this.sprites.set(id, null);
    img.src = `/spirits/${id}.png`;
    this.sprites.set(id, img);
    return img;
  }

  // Same drop-in idea for building facades: /buildings/<stem>.png. Cached in the same
  // map under a "b:" prefix. Returns null once it 404s (→ code-drawn placeholder). The
  // art chunk sets each slot's `sprite` and the real facade appears in place.
  private getBuildingSprite(stem: string): HTMLImageElement | null {
    const key = `b:${stem}`;
    const cached = this.sprites.get(key);
    if (cached !== undefined) return cached;
    const img = new Image();
    img.decoding = "async"; // decode off the critical path — avoids a first-draw hitch mid-frame
    img.onerror = () => this.sprites.set(key, null);
    img.onload = () => { this.layoutDirty = true; }; // true aspect known → re-flow the row once
    img.src = `/buildings/${stem}.png`;
    this.sprites.set(key, img);
    return img;
  }

  // Overture walk-in plaza art from /overture/<stem>.png (gate, court-back, court-side,
  // elephant-column). Cached under an "o:" prefix, same drop-in pattern as facades.
  private getOverture(stem: string): HTMLImageElement | null {
    const key = `o:${stem}`;
    const cached = this.sprites.get(key);
    if (cached !== undefined) return cached;
    const img = new Image();
    img.decoding = "async"; // decode off the critical path — avoids a first-draw hitch mid-frame
    img.onerror = () => this.sprites.set(key, null);
    img.src = `/overture/${stem}.png`;
    this.sprites.set(key, img);
    return img;
  }

  // A room's backdrop plate from its own asset folder: /${R.dir ?? 'overture'}/<stem>.<png|jpg>.
  // Opaque interior plates ride as .jpg (far smaller); the Overture court stays .png (needs its
  // transparent sky). Cached under an "a:" prefix keyed by the full path so folders don't collide.
  // Kick off loading + async-decoding of an interior AREA's plates BEFORE the player enters, so the
  // enter crossfade never stalls on a multi-MB decode. Idempotent (guarded by prefetchedAreas).
  // Pulls the backdrop, the open-curtain plate, the counter/foreground overlay, any head-on sky
  // plates, the occupant sprites, and (recursively) the room the curtain leads to.
  private prefetchArea(id: string): void {
    if (this.prefetchedAreas.has(id)) return;
    this.prefetchedAreas.add(id);
    const R = AREAS[id];
    if (!R) return;
    this.getAreaPlate(R, R.backdrop);
    if (R.foreground) this.getAreaPlate(R, R.foreground, false);
    if (R.curtain) { this.getAreaPlate(R, R.curtain.openBackdrop); this.prefetchArea(R.curtain.toArea); }
    if (R.sky) { this.getOverture(R.sky.skyline); this.getOverture(R.sky.windows); }
    for (const o of R.occupants ?? []) this.getSprite(o.stem);
  }

  private getAreaPlate(R: AreaView, stem: string, jpg = R.jpg): HTMLImageElement | null {
    const dir = R.dir ?? "overture";
    const ext = jpg ? "jpg" : "png";
    const path = `/${dir}/${stem}.${ext}`;
    const key = `a:${path}`;
    const cached = this.sprites.get(key);
    if (cached !== undefined) return cached;
    const img = new Image();
    img.decoding = "async"; // decode off the critical path — avoids a first-draw hitch mid-frame
    img.onerror = () => this.sprites.set(key, null);
    img.src = path;
    this.sprites.set(key, img);
    return img;
  }

  // Seamless ground texture from /tiles/<name>. Cached; null once it 404s.
  private getTile(name: string): HTMLImageElement | null {
    const cached = this.tiles.get(name);
    if (cached !== undefined) return cached;
    const img = new Image();
    img.decoding = "async"; // decode off the critical path — avoids a first-draw hitch mid-frame
    img.onerror = () => this.tiles.set(name, null);
    img.src = `/tiles/${name}`;
    this.tiles.set(name, img);
    return img;
  }

  // A cached repeating CanvasPattern for a tile, or null until the image has decoded.
  private getTilePattern(name: string): CanvasPattern | null {
    const cached = this.patterns.get(name);
    if (cached) return cached;
    const img = this.getTile(name);
    if (!img || !img.complete || img.naturalWidth === 0) return null;
    const pat = this.ctx.createPattern(img, "repeat");
    if (!pat) return null;
    this.patterns.set(name, pat);
    return pat;
  }

  // Fill a world-space rect with a repeating ground texture, viewport-culled. One copy of the
  // image spans TILE_WORLD[name] world units; the pattern is anchored to the world origin so
  // adjacent surfaces (road ↔ cross-street) tile seamlessly. Flat-fills when the texture isn't
  // ready or when zoomed too far out to read the detail.
  private fillTiled(x0: number, y0: number, x1: number, y1: number, name: string): void {
    const ctx = this.ctx;
    const vx = this.cam.x;
    const vy = this.cam.y;
    const cx0 = Math.max(x0, vx);
    const cy0 = Math.max(y0, vy);
    const cx1 = Math.min(x1, vx + this.cssW / this.cam.zoom);
    const cy1 = Math.min(y1, vy + this.cssH / this.cam.zoom);
    if (cx1 <= cx0 || cy1 <= cy0) return;
    const pat = this.cam.zoom > TILE_ZOOM_GATE ? this.getTilePattern(name) : null;
    if (!pat) {
      ctx.fillStyle = GROUND_FALLBACK[name] ?? "#2a2620";
      ctx.fillRect(cx0, cy0, cx1 - cx0, cy1 - cy0);
      return;
    }
    const img = this.getTile(name)!;
    // The pattern scale only depends on TILE_WORLD/naturalWidth (constant once decoded) — cache the
    // matrix instead of allocating a new DOMMatrix on every fill (fillTiled runs ~15–30×/frame).
    let m = this.patternMatrix.get(name);
    if (!m) {
      const k = (TILE_WORLD[name] ?? 160) / img.naturalWidth;
      m = new DOMMatrix([k, 0, 0, k, 0, 0]);
      this.patternMatrix.set(name, m);
    }
    pat.setTransform(m);
    ctx.fillStyle = pat;
    ctx.fillRect(cx0, cy0, cx1 - cx0, cy1 - cy0);
  }

  // Baked cool-dark, edge-softened silhouette of a sprite (alpha-shaped), for the directional cast
  // shadow. Built once per sprite src and cached — the soft edge is baked in so the runtime shadow
  // needs no per-frame blur filter.
  private spriteSilhouette(key: string, img: CanvasImageSource): HTMLCanvasElement | null {
    const hit = this.silCache.get(key);
    if (hit) return hit;
    const w = srcW(img), h = srcH(img);
    if (!w || !h) return null;
    const solid = document.createElement("canvas");
    solid.width = w; solid.height = h;
    const sc = solid.getContext("2d");
    if (!sc) return null;
    sc.drawImage(img, 0, 0);
    sc.globalCompositeOperation = "source-in"; // keep the sprite's alpha, recolor to a cool shadow tone
    sc.fillStyle = "rgb(14,16,30)";
    sc.fillRect(0, 0, w, h);
    // Bake a soft edge once (so no per-frame blur is needed at draw time).
    const soft = document.createElement("canvas");
    soft.width = w; soft.height = h;
    const fx = soft.getContext("2d");
    if (!fx) return solid;
    fx.filter = "blur(2px)";
    fx.drawImage(solid, 0, 0);
    this.silCache.set(key, soft);
    return soft;
  }

  // Time-of-day DIRECTIONAL cast shadow: the sprite's own silhouette, flattened FORWARD onto the
  // ground (down-screen) and skewed away from the sun, composited `multiply`. Drawn inside the
  // actor's own draw (before its sprite) so it sorts with the actor and lands on the ground it
  // stands on — nearer actors draw over it. Silhouette-shaped, so it never bleeds a rectangle onto
  // the ground/neighbours the way the old box-edge AO/skirt overlays did.
  private drawCastShadow(key: string, img: CanvasImageSource, cx: number, footY: number, w: number, H: number, strength = 1): void {
    const sun = sunShadowAt(this.engine.clockMinutes);
    if (sun.alpha <= 0) return;
    const sil = this.spriteSilhouette(key, img);
    if (!sil) return;
    const ctx = this.ctx;
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    ctx.globalAlpha = sun.alpha * strength;
    ctx.translate(cx, footY);
    // Upright sprite (foot at y=0, top at y=-H) → ground: transform(a,b,c,d,e,f) gives
    // x' = x - skewX·y (skew grows with height) and y' = -lenY·y (flatten forward, down-screen).
    ctx.transform(1, 0, -sun.skewX, -sun.lenY, 0, 0);
    ctx.drawImage(sil, -w / 2, -H, w, H);
    ctx.restore();
  }

  // Three-part grounding stack under any upright actor, drawn within the sorted pass (before the
  // actor's sprite) so it sits on exactly the ground it stands on. Research-calibrated to READ in
  // a dark, moody scene where a thin near-black multiply is invisible:
  //   (1) a faint warm ground LIFT so a dark shadow has contrast to bite into;
  //   (2) an offset, foreshortened cast BODY (the directional "sitting on the ground" cue) —
  //       cool blue-black (hue-separates when value can't), thrown down+right for ONE consistent
  //       light (upper-left), spilling forward onto the visible sidewalk;
  //   (3) a crisp dark contact SEAM at the true foot line (the glue that kills the float).
  // `w`/`h` = the actor's on-screen footprint width / height; `scale` fades it with depth.
  // `seamOnly` drops the fake directional cast BODY (part 2) — pass it for objects that now have the
  // REAL time-of-day cast shadow (buildings, props), so the two directional cues don't fight; the
  // lift + tight foot seam still glue the base to the ground. Characters keep the full stack.
  // A soft radial "blob" texture (256-step falloff) baked ONCE per color and cached, so the hot
  // grounding/FX paths can blit a pre-rendered gradient instead of calling createRadialGradient +
  // arc + fill (+ save/restore) on every actor every frame — the dominant per-frame cost.
  // One-time 1024px-tall downscale of oversized character sprites, for the OVERWORLD draw only.
  private scaledCache = new Map<string, HTMLCanvasElement | null>();
  private overworldSprite(img: HTMLImageElement): CanvasImageSource {
    const key = img.src;
    const hit = this.scaledCache.get(key);
    if (hit !== undefined) return hit ?? img;
    const nH = img.naturalHeight, nW = img.naturalWidth;
    if (!nH || nH <= OVERWORLD_MAX_H) { this.scaledCache.set(key, null); return img; } // already small enough
    const scale = OVERWORLD_MAX_H / nH;
    const c = document.createElement("canvas");
    c.width = Math.round(nW * scale); c.height = OVERWORLD_MAX_H;
    const x = c.getContext("2d");
    if (!x) { this.scaledCache.set(key, null); return img; }
    x.imageSmoothingEnabled = true; x.imageSmoothingQuality = "high";
    x.drawImage(img, 0, 0, c.width, c.height);
    this.scaledCache.set(key, c);
    return c;
  }

  private blobCache = new Map<string, HTMLCanvasElement>();
  private softBlob(r: number, g: number, b: number): HTMLCanvasElement {
    const key = `${r},${g},${b}`;
    const hit = this.blobCache.get(key);
    if (hit) return hit;
    const S = 64;
    const c = document.createElement("canvas");
    c.width = S; c.height = S;
    const x = c.getContext("2d")!;
    const grad = x.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
    grad.addColorStop(0, `rgba(${r},${g},${b},1)`);
    grad.addColorStop(0.6, `rgba(${r},${g},${b},0.5)`);
    grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
    x.fillStyle = grad;
    x.fillRect(0, 0, S, S);
    this.blobCache.set(key, c);
    return c;
  }
  // A radial glow baked ONCE from an exact set of colour stops (at full strength) and cached, so the
  // night lighting can blit it with globalAlpha=night instead of allocating a fresh radial gradient
  // per lamp/window/marquee every frame. Because globalAlpha scales all stops uniformly, blitting at
  // α reproduces the old per-stop `×night` output EXACTLY (pixel-identical), just cached.
  private glowCache = new Map<string, HTMLCanvasElement>();
  private bakedGlow(key: string, stops: [number, string][]): HTMLCanvasElement {
    const hit = this.glowCache.get(key);
    if (hit) return hit;
    const S = 128;
    const c = document.createElement("canvas");
    c.width = S; c.height = S;
    const x = c.getContext("2d")!;
    const g = x.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
    for (const [stop, col] of stops) g.addColorStop(stop, col);
    x.fillStyle = g;
    x.fillRect(0, 0, S, S);
    this.glowCache.set(key, c);
    return c;
  }

  // Blit a cached blob as an ellipse centred at (cx,cy) with half-extents (hw,hh), tinted by the
  // blob's colour, at `alpha` under composite op `op`. One drawImage — no gradient alloc, no path.
  private blitBlob(blob: HTMLCanvasElement, cx: number, cy: number, hw: number, hh: number, alpha: number, op: GlobalCompositeOperation): void {
    if (alpha <= 0 || hw <= 0 || hh <= 0) return;
    const ctx = this.ctx;
    const prevOp = ctx.globalCompositeOperation;
    ctx.globalCompositeOperation = op;
    ctx.globalAlpha = alpha;
    ctx.drawImage(blob, cx - hw, cy - hh, hw * 2, hh * 2);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = prevOp;
  }

  private drawContactShadow(cx: number, footY: number, w: number, h: number, scale = 1, seamOnly = false): void {
    const rx = Math.max(10, w * 0.5);
    const lift = this.softBlob(70, 60, 46);
    const dark = this.softBlob(7, 6, 15);
    // (1) ground lift — faint warm halo so a dark shadow has contrast to bite into.
    this.blitBlob(lift, cx, footY, rx * 1.4, rx * 1.4 * 0.22, 0.13 * scale, "lighten");
    // (2) cast body — cool blue-black, offset down+right, foreshortened. Skipped for objects that
    // carry the real directional cast shadow (buildings/props).
    if (!seamOnly) {
      const offX = Math.min(w * 0.12, 48), offY = Math.min(h * 0.12, 52), brx = rx * 1.25;
      this.blitBlob(dark, cx + offX, footY + offY, brx, brx * 0.4, 0.54 * scale, "multiply");
    }
    // (3) contact seam — crisp cool-black glue at the true foot line.
    this.blitBlob(dark, cx, footY, rx, rx * 0.15, 0.74 * scale, "multiply");
  }

  // Composite a facade image at its character-height scale, feet-anchored to the
  // building's baseline and horizontally centered on its slot.
  private drawBuildingSprite(b: Building, img: HTMLImageElement) {
    const ctx = this.ctx;
    const side = b.side ?? "north";
    const H = (b.ch ?? (b.height ?? 90) / 84) * 84;
    const w = H * (img.naturalWidth / img.naturalHeight);
    const cx = b.x + (b.width ?? 120) / 2;
    // Every building's BASE sits on its sidewalk line and grows UP. The near row's sidewalk
    // is in the foreground (below the road), so it grows up toward but never onto the road.
    const baseY = b.baseY ?? (side === "north" ? NORTH_BASELINE : SOUTH_BASELINE);
    const growUp = b.growUp ?? true;
    const top = growUp ? baseY - H : baseY;
    // Grounding: the directional time-of-day CAST shadow (the sprite's own silhouette flattened
    // onto the ground, swinging + lengthening with the sun) + a light SEAM-only contact shadow at
    // the foot. Both are silhouette/ellipse-shaped, never box rectangles, so nothing bleeds onto
    // the ground or the neighbour — this replaces the old base-skirt / inter-building-AO / far-row
    // veil rectangles that printed the vertical "black streaks" through the sprites' transparent
    // padding. Far (north) row a touch lighter so it recedes.
    const depthScale = side === "north" ? 0.85 : 1;
    const skey = img.src;
    this.drawCastShadow(skey, img, cx, baseY, w, H);
    this.drawContactShadow(cx, baseY, w, H, depthScale, true);
    const prev = ctx.imageSmoothingEnabled;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, cx - w / 2, top, w, H);
    ctx.imageSmoothingEnabled = prev;
  }

  // ── Overture walk-in court (open piazza, PARALLEL/axonometric — no vanishing point) ──────
  // Research (Gaia Online, isometric city-builders): faking a 1-point vanishing point in a flat
  // dimetric billboard scene makes the two side walls converge to an ugly "X" funnel. The fix is
  // to keep everything PARALLEL: the floor is a symmetric RECTANGLE (same half-width front and
  // back → sides can't pinch) and the terraces + back building are baked into ONE parallel-oblique
  // backdrop plate the engine merely places. All depth is painted into the art; the engine does no
  // per-object perspective scaling. Fountain + palms stay real foot-Y props for true walk-past
  // occlusion. The gate + elephant columns are the front-plane actors that frame the arch.

  // The court FLOOR — one baked non-repeating plate drawn into a symmetric world rectangle
  // (constant courtHalf at both the gate line and the back), laid in the ground pre-pass beneath
  // every actor. A neutral warm fill stands in until the plate decodes (never the old tile grid).
  private drawOvertureFloor(): void {
    if (this.cam.zoom <= TILE_ZOOM_GATE) return;
    const O = OVERTURE;
    const vx = this.cam.x, vR = vx + this.cssW / this.cam.zoom;
    if (O.cx + O.courtHalf < vx - 40 || O.cx - O.courtHalf > vR + 40) return;
    const ctx = this.ctx;
    const x = O.cx - O.courtHalf, y = O.courtBackY;
    const w = O.courtHalf * 2, h = O.gateFootY - O.courtBackY;
    const img = this.getOverture("overture-court-floor");
    if (img && img.complete && img.naturalWidth > 0) {
      const prev = ctx.imageSmoothingEnabled;
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(img, x, y, w, h);
      ctx.imageSmoothingEnabled = prev;
    } else {
      ctx.fillStyle = "#c9b48c"; // warm travertine placeholder (no marching grid)
      ctx.fillRect(x, y, w, h);
    }
    // A light multiply darken toward the back edge so the court reads as enclosed.
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    const bg = ctx.createLinearGradient(0, y, 0, y + h * 0.5);
    bg.addColorStop(0, "rgba(16,12,8,0.42)");
    bg.addColorStop(1, "rgba(16,12,8,0)");
    ctx.fillStyle = bg;
    ctx.fillRect(x, y, w, h * 0.5);
    ctx.restore();
  }

  // (The court INTERIOR is no longer an in-world backdrop — the painted plate is the Overture Court
  // area you crossfade into; see renderArea / AREAS. The seamless court is just the sparse approach:
  // floor + palms + fountain + gate.)

  // Push the court's real actors into the sorted list: fountain + palm rows (constant-size foot-Y
  // props — the player physically walks past them, so they y-sort/occlude naturally), plus the
  // gate + elephant gateposts as the full-size front plane (foot-Y makes the gate occlude anyone
  // who walks north through the arch).
  private collectOvertureActors(out: Actor[], vx: number, vR: number): void {
    const O = OVERTURE;
    if (O.cx + O.gateHalf + 320 < vx || O.cx - O.gateHalf - 320 > vR) return;
    const colPush = 300; // elephant columns flank the arch at the gate front
    const cx = O.cx;
    const at = (dy: number) => O.courtBackY + dy; // depth helper (north/far = small y)
    // The approach is composed to LEAD the eye north to the room entrance: a lit MARQUEE beacon at
    // the far terminus, flanked by event BANNERS, a mid-court STATUE pair, STANCHION posts roping the
    // central runner, URN planters + PALM rows framing the sides. All foot-Y props (constant size).
    // marquee beacon — the bright far terminus, just south of the room-enter line (you walk into it)
    out.push({ y: at(224), draw: () => this.drawOvertureBillboard("overture-marquee", cx, at(224), 4.7) });
    // event banners flanking the entrance
    out.push({ y: at(196), draw: () => this.drawOvertureBillboard("overture-banner", cx - 175, at(196), 4.4) });
    out.push({ y: at(198), draw: () => this.drawOvertureBillboard("overture-banner", cx + 175, at(198), 4.4, true) });
    // statue pair — grand mid-court beat, outside the walkable lane
    out.push({ y: at(452), draw: () => this.drawOvertureBillboard("overture-statue", cx - 300, at(452), 5) });
    out.push({ y: at(454), draw: () => this.drawOvertureBillboard("overture-statue", cx + 300, at(454), 5, true) });
    // stanchion posts roping the central runner up the middle
    for (const dy of [150, 340, 530, 720]) {
      out.push({ y: at(dy), draw: () => this.drawProp("stanchion-post", cx - 105, at(dy)) });
      out.push({ y: at(dy) + 1, draw: () => this.drawProp("stanchion-post", cx + 105, at(dy) + 1) });
    }
    // urn planters in the side gutter
    for (const dy of [300, 620]) {
      out.push({ y: at(dy), draw: () => this.drawProp("urn-topiary", cx - 215, at(dy)) });
      out.push({ y: at(dy) + 1, draw: () => this.drawProp("urn-topiary", cx + 215, at(dy) + 1) });
    }
    // palm rows framing the promenade at several depths
    const palmX = O.courtWalkHalf + 60;
    for (const dy of [90, 240, 400, 560, 700]) {
      out.push({ y: at(dy), draw: () => this.drawProp("palm", cx - palmX, at(dy)) });
      out.push({ y: at(dy) + 1, draw: () => this.drawProp("palm", cx + palmX, at(dy) + 1) });
    }
    // the gate — front plane, at the boulevard line (drawn late → occludes anyone behind it)
    out.push({ y: O.gateFootY, draw: () => this.drawOvertureBillboard("overture-gate", O.cx, O.gateFootY, O.gateCH) });
    // elephant-column gateposts — front plane, flanking the arch
    out.push({ y: O.gateFootY + 6, draw: () => this.drawOvertureBillboard("overture-elephant-column", O.cx - colPush, O.gateFootY + 6, O.columnCH) });
    out.push({ y: O.gateFootY + 7, draw: () => this.drawOvertureBillboard("overture-elephant-column", O.cx + colPush, O.gateFootY + 7, O.columnCH) });
  }

  // Draw one Overture plaza billboard, foot-anchored at (cx, footY), scaled to `ch`
  // character-heights, grounded with the shared contact-shadow stack + a foot skirt. `flip`
  // mirrors horizontally. (The perspective scale, if any, is applied by the caller.)
  private drawOvertureBillboard(stem: string, cx: number, footY: number, ch: number, flip = false): void {
    const img = this.getOverture(stem);
    if (!img || !img.complete || img.naturalWidth === 0) return;
    const ctx = this.ctx;
    const H = ch * 84;
    const w = H * (img.naturalWidth / img.naturalHeight);
    this.drawContactShadow(cx, footY, w, H, 1);
    const prev = ctx.imageSmoothingEnabled;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    if (flip) {
      ctx.save();
      ctx.translate(cx, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(img, -w / 2, footY - H, w, H);
      ctx.restore();
    } else {
      ctx.drawImage(img, cx - w / 2, footY - H, w, H);
    }
    ctx.imageSmoothingEnabled = prev;
    // Foot skirt so the base sinks into the plaza floor instead of sitting on a shelf.
    const skirtH = Math.min(16, H * 0.14);
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    const sg = ctx.createLinearGradient(0, footY - skirtH, 0, footY);
    sg.addColorStop(0, "rgba(16,12,8,0)");
    sg.addColorStop(1, "rgba(16,12,8,0.30)");
    ctx.fillStyle = sg;
    ctx.fillRect(cx - w / 2, footY - skirtH, w, skirtH);
    ctx.restore();
  }

  // Shared smoky walk FX — drawn behind a moving character's body. Three ingredients (research:
  // Gaia's leg-blur + smear "multiples" + smoke): a trailing leg-height blur, a couple of soft
  // dark smoke puffs that rise/expand/fade drifting behind travel, and a grounded contact
  // crescent. Time-tinted — cooler/bluish at night, warmer/amber at golden hour, darker overall.
  // `x`/`footY` = the feet in world space, `w` = sprite width, `dir` = travel (±1), `phase` 0..1.
  private drawWalkFX(x: number, footY: number, w: number, dir: number, t: number, phase: number): void {
    const ctx = this.ctx;
    const mins = this.engine.clockMinutes;
    const night = nightAt(mins);
    const golden = goldenAt(mins);
    // Cool slate smoke — dark & moody, but light enough to read on the asphalt; bluer/brighter
    // after dark (moonlit smoke), warmer at golden hour.
    // Cool slate smoke — dark & moody but light enough to read on the asphalt; bluer after dark
    // (moonlit), warmer at golden hour.
    const rr = Math.round(60 + golden * 34 - night * 8);
    const gg = Math.round(62 + golden * 14 + night * 8);
    const bb = Math.round(72 + night * 30);
    const back = dir >= 0 ? -1 : 1; // trailing side (behind travel)
    const step = 6 + 3 * Math.abs(Math.sin(t / 80));

    // (1) trailing leg-blur — fading smears streaking behind the shins (visible to the trailing side)
    const legY = footY - 13;
    for (let k = 1; k <= 4; k++) {
      const a = 0.34 / k;
      ctx.fillStyle = `rgba(${rr},${gg},${bb},${a})`;
      ctx.beginPath();
      ctx.ellipse(x + back * (w * 0.28 + k * step * 1.4), legY, w * 0.34, 8, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    // (2) smoke puffs — kicked up at the feet, TRAILING BACK along the ground, rising a little as
    // they expand + fade. Blit a cached soft blob (tinted rr,gg,bb) instead of allocating a radial
    // gradient per puff per moving character per frame.
    const smoke = this.softBlob(rr, gg, bb);
    for (let k = 0; k < 5; k++) {
      const p = (t / 560 + phase + k / 5) % 1;
      const px = x + back * (w * 0.3 + p * 46);
      const py = footY - 2 - p * 12;
      const rad = 5 + p * 16;
      const a = (1 - p) * (0.42 + 0.14 * night);
      this.blitBlob(smoke, px, py, rad, rad, a, "source-over");
    }

    // (3) contact crescent — the grounded dark "boat" fanning out under the feet
    const hw = w * 0.55 + step + 4;
    const lift = 7;
    const by = footY - lift;
    for (const layer of [
      { s: 1, a: 0.3 },
      { s: 0.7, a: 0.3 },
      { s: 0.45, a: 0.3 },
    ]) {
      const h = hw * layer.s;
      ctx.fillStyle = `rgba(${Math.round(rr * 0.6)},${Math.round(gg * 0.6)},${Math.round(bb * 0.75)},${layer.a})`;
      ctx.beginPath();
      ctx.moveTo(x - h, by);
      ctx.quadraticCurveTo(x, footY + 7, x + h, by);
      ctx.quadraticCurveTo(x, by - 6, x - h, by);
      ctx.closePath();
      ctx.fill();
    }
  }

  // Gaia-style leg-blur overlay (research: the "rapid blur standard walk animation" — a static
  // body that glides while the legs buzz). The legs swing like PENDULUMS from the hip: we slice
  // the bottom band of the sprite (the legs) and redraw it as a fan of fading copies, each
  // horizontally SHEARED so the top (hip) stays planted while the bottom (feet) sweeps left↔right.
  // The fan spans the full swing arc (the persistent blur); alpha peaks at the current swing angle
  // (a bright copy that tracks the legs actually moving). Drawn UNDER the crisp body. Moving-only.
  private drawLegBlur(
    img: CanvasImageSource,
    b: { t: number; b: number },
    cx: number,
    feetY: number,
    w: number,
    flip: boolean,
    t: number,
    phase: number,
  ): void {
    const ctx = this.ctx;
    const legFrac = 0.36; // fraction of the body height that is "legs" (shins, hem, feet)
    const contentFrac = b.b - b.t;
    const nW = srcW(img);
    const nH = srcH(img);
    const sy0 = (b.b - legFrac * contentFrac) * nH;
    const sH = legFrac * contentFrac * nH;
    const destLegH = legFrac * CHAR_BODY_H;
    const pivotY = feetY - destLegH; // hip line — top of the leg band, stays put
    const footSweep = 9; // px the feet swing to each side
    const shxMax = footSweep / destLegH; // shear so foot offset = footSweep at the swing extreme
    const base = shxMax * Math.sin(t / 85 + phase); // current pendulum position (legs actually moving)
    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    if (flip) {
      ctx.translate(cx, 0);
      ctx.scale(-1, 1);
      ctx.translate(-cx, 0);
    }
    const N = 4; // copies across the swing arc (was 7 — 4 reads the same at draw size, ~half the cost)
    for (let k = 0; k < N; k++) {
      const f = k / (N - 1); // 0..1
      const shx = (f * 2 - 1) * shxMax; // -shxMax .. +shxMax (left foot-sweep .. right)
      const d = Math.abs(shx - base) / (2 * shxMax); // distance from the current swing angle
      const alpha = 0.08 + 0.24 * (1 - d); // faint across the arc, brightest where the legs are now
      ctx.globalAlpha = alpha;
      ctx.save();
      ctx.translate(cx, pivotY);
      ctx.transform(1, 0, shx, 1, 0, 0); // horizontal shear by y → pendulum from the hip
      ctx.drawImage(img, 0, sy0, nW, sH, -w / 2, 0, w, destLegH);
      ctx.restore();
    }
    ctx.restore();
  }

  // A static room occupant (e.g. Yara at her counter): a plain foot-Y billboard drawn at the shared
  // uniform body height with a soft contact shadow so it grounds on the painted floor. No AI, no walk
  // FX — it just stands. Front sprite only (mirrored if faceLeft); reuses spriteBounds for scale.
  private drawRoomOccupant(stem: string, x: number, y: number, scale: number, faceLeft: boolean): void {
    const ctx = this.ctx;
    const sprite = this.getSprite(stem);
    if (!sprite || !sprite.complete || !sprite.naturalWidth) return;
    const b = this.spriteBounds(stem, sprite);
    const frameH = (CHAR_BODY_H * scale) / Math.max(0.5, b.b - b.t);
    const w = frameH * (sprite.naturalWidth / sprite.naturalHeight);
    const feetY = y + FEET_DROP;
    const top = feetY - b.b * frameH;
    // soft contact shadow so she doesn't float on the floor
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    const rx = w * 0.3, ry = rx * 0.32;
    const g = ctx.createRadialGradient(x, feetY, 1, x, feetY, rx);
    g.addColorStop(0, "rgba(10,8,6,0.5)");
    g.addColorStop(1, "rgba(10,8,6,0)");
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.ellipse(x, feetY, rx, ry, 0, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
    const prev = ctx.imageSmoothingEnabled;
    ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = "high";
    ctx.save();
    if (faceLeft) { ctx.translate(x, 0); ctx.scale(-1, 1); ctx.translate(-x, 0); }
    ctx.drawImage(sprite, x - w / 2, top, w, frameH);
    ctx.restore();
    ctx.imageSmoothingEnabled = prev;
  }

  private drawNPC(s: NpcRuntime, t: number) {
    const ctx = this.ctx;
    // Gaia-style: planted when idle, a light step-bounce ONLY while moving.
    const bob = s.moving ? -Math.abs(Math.sin(t / 90)) * 2.5 : 0;
    const pulse = 0.75 + 0.25 * Math.sin(t / 400 + s.x * 0.05);
    const y = s.y + bob;

    // Soul-tinted aura glow — a cached blob (keyed by the aura colour) blitted instead of a fresh
    // radial gradient per soul per frame.
    const aura = auraColor(s.soul);
    const auraR = 34;
    const ar = parseInt(aura.slice(1, 3), 16) || 0;
    const ag = parseInt(aura.slice(3, 5), 16) || 0;
    const ab = parseInt(aura.slice(5, 7), 16) || 0;
    this.blitBlob(this.softBlob(ar, ag, ab), s.x, y, auraR, auraR, 0.55 * pulse, "source-over");

    // "you are here" ring — anchored to the ground so it stays put while she bounces
    if (s.soul.id === this.controlledId) {
      ctx.strokeStyle = "rgba(240, 230, 200, 0.85)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.ellipse(s.x, s.y + 16, 16, 6, 0, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Active outfit → sprite stem (defaults to the soul id, i.e. the base look).
    const stem = this.outfits.get(s.soul.id) ?? s.soul.id;
    let sprite = this.getSprite(stem);
    let spriteKey = stem;
    let usingBack = false;
    // player facing away from the camera → use the back sprite for this outfit if one exists
    if (s.soul.id === this.controlledId && this.facingUp) {
      const back = this.getSprite(`${stem}_back`);
      if (back && back.complete && back.naturalWidth > 0) {
        sprite = back;
        spriteKey = `${stem}_back`;
        usingBack = true;
      }
    }
    if (sprite && sprite.complete && sprite.naturalWidth > 0) {
      // Normalize to the same body height as every other character, feet planted (spriteBounds).
      const b = this.spriteBounds(spriteKey, sprite);
      const frameH = CHAR_BODY_H / Math.max(0.5, b.b - b.t);
      const w = frameH * (sprite.naturalWidth / sprite.naturalHeight);
      // The back sprite is separate art authored facing away; mirroring it would invert any
      // text/number/logo on the back (e.g. a "SORRISO 10" jersey), so it is NEVER flipped — only
      // the front billboard mirrors by travel direction.
      let flip = usingBack ? false : s.soul.id === this.controlledId ? this.facingLeft : s.dir < 0;
      if (!usingBack && SPRITE_FACES_LEFT.has(s.soul.id)) flip = !flip; // front art faces left by default
      const feetY = s.y + FEET_DROP + bob;
      const top = feetY - b.b * frameH;
      const prev = ctx.imageSmoothingEnabled;
      ctx.imageSmoothingEnabled = true; // smooth downscale — these are painted, not pixel art
      ctx.imageSmoothingQuality = "high";

      // Overworld draw uses a one-time downscaled copy of the (large) source sprite — same output,
      // ~3× less per-frame resample. Rooms draw the full-res source elsewhere (renderArea).
      const drawImg = this.overworldSprite(sprite);
      const drawAt = (cx: number, alpha: number) => {
        ctx.save();
        ctx.globalAlpha = alpha;
        if (flip) {
          ctx.translate(cx, 0);
          ctx.scale(-1, 1);
          ctx.translate(-cx, 0);
        }
        ctx.drawImage(drawImg, cx - w / 2, top, w, frameH);
        ctx.restore();
      };

      // Grounding, under the SAME sun as the buildings: the time-of-day directional cast shadow
      // (the character's own silhouette, flattened + skewed by the sun; never flipped with the
      // sprite so it stays light-consistent) + a soft foot contact so they're grounded standing OR
      // moving. Drawn before the FX and the body.
      this.drawCastShadow(spriteKey, drawImg, s.x, feetY, w, frameH, 0.85);
      this.drawContactShadow(s.x, feetY, w * 0.5, frameH, 1, true);
      // Smoky Gaia-style walk FX behind the body, the pendulum leg-blur at the feet, then the crisp
      // body on top. Gated to a readable zoom (FX_ZOOM) — invisible but costly when zoomed way out.
      if (s.moving && this.cam.zoom >= FX_ZOOM) {
        this.drawWalkFX(s.x, feetY, w, s.dir, t, (s.x * 0.0131) % 1);
        this.drawLegBlur(drawImg, b, s.x, feetY, w, flip, t, s.x * 0.05);
      }
      drawAt(s.x, 1);
      ctx.imageSmoothingEnabled = prev;
      return;
    }

    // fallback: simple code-drawn figure
    ctx.fillStyle = "#3a2f26";
    ctx.beginPath();
    ctx.ellipse(s.x, y + 9, 5, 8, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#e7c9a3";
    ctx.beginPath();
    ctx.arc(s.x, y - 2, 7, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = "#2a2018";
    ctx.lineWidth = 2;
    const legSwing = Math.sin(t / 120 + s.x) * 3;
    ctx.beginPath();
    ctx.moveTo(s.x - 2, y + 15);
    ctx.lineTo(s.x - 2 + legSwing, y + 22);
    ctx.moveTo(s.x + 2, y + 15);
    ctx.lineTo(s.x + 2 - legSwing, y + 22);
    ctx.stroke();
  }
}
