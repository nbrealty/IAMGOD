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
  type Building,
} from "./sceneData";
import type { Soul } from "../soul/types";
import { auraColor } from "../soul/appearance";
import { SoulEngine, activityIsStationary } from "../soul/engine";
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

// One entry in the unified depth pass: an upright actor keyed by its foot-Y (baseline), with a
// closure that draws it. Sorted ascending → far (small y) drawn first, near (large y) on top.
interface Actor {
  y: number;
  draw: () => void;
}

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
};
const GROUND_FALLBACK: Record<string, string> = {
  "asphalt.jpg": "#33322f",
  "sidewalk.jpg": "#6b665d",
  "grass.jpg": "#3b4a2e",
  "soil.jpg": "#38301f",
  "plaza.jpg": "#b6a877",
};
// Below this zoom the whole district is in frame; skip pattern tiling and just flat-fill.
const TILE_ZOOM_GATE = 0.24;

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
  // Active outfit per soul: soulId → sprite stem (see outfits.ts). Absent → wears its default
  // (stem = soul id). Swapping an entry changes which sprite (front + `_back`) drawNPC loads.
  private outfits = new Map<string, string>();
  private held = new Set<string>();
  private facingLeft = false;
  private facingUp = false; // moving away from camera → show the back sprite

  private sprites = new Map<string, HTMLImageElement | null>();
  private tiles = new Map<string, HTMLImageElement | null>();
  private patterns = new Map<string, CanvasPattern>();
  // Cached non-transparent vertical bounds per character sprite ({ t, b } as fractions of natural
  // height), so we normalize every actor to one body height. Measured once, lazily, on first draw.
  private boundsCache = new Map<string, { t: number; b: number }>();
  private measureCanvas?: HTMLCanvasElement;
  private tapHandler: ((cssX: number, cssY: number) => void) | null = null;

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
        const stationary = activityIsStationary(s.soul.activity);
        s.moving = !stationary; // planted while doing a stationary activity
        const spd = s.soul.baseSpeed * (stationary ? 0.2 : 1) * moveScale;
        s.x += s.dir * spd * dt;
        if (s.x > s.soul.xMax) {
          s.x = s.soul.xMax;
          s.dir = -1;
        }
        if (s.x < s.soul.xMin) {
          s.x = s.soul.xMin;
          s.dir = 1;
        }
      }

      // ambient crowd — walk the sidewalks, turn around at the world edges
      for (const ped of this.peds) {
        ped.x += ped.dir * ped.speed * dt * moveScale;
        if (ped.x > WORLD_W - 100) ped.dir = -1;
        else if (ped.x < 100) ped.dir = 1;
      }

      // player-controlled character: WASD / arrows / on-screen D-pad. Real-time speed
      // (not scaled by sim time-speed), and the camera eases to follow.
      if (this.controlledId) {
        const pc = this.npcs.find((n) => n.soul.id === this.controlledId);
        if (pc) {
          const vx = (this.held.has("right") ? 1 : 0) - (this.held.has("left") ? 1 : 0);
          const vy = (this.held.has("down") ? 1 : 0) - (this.held.has("up") ? 1 : 0);
          pc.moving = vx !== 0 || vy !== 0;
          if (vx || vy) {
            const m = Math.hypot(vx, vy) || 1;
            const dx = (vx / m) * PLAYER_SPEED * dt;
            const dy = (vy / m) * PLAYER_SPEED * dt;
            // Move axis-independently against the street "+" corridor: try the full
            // step, else slide along the wall on whichever axis stays walkable — so you
            // hug the sidewalk and can turn the corner at the intersection.
            if (canWalk(pc.x + dx, pc.y + dy)) {
              pc.x += dx;
              pc.y += dy;
            } else {
              if (canWalk(pc.x + dx, pc.y)) pc.x += dx;
              if (canWalk(pc.x, pc.y + dy)) pc.y += dy;
            }
            if (vx < 0) this.facingLeft = true;
            else if (vx > 0) this.facingLeft = false;
            // vertical dominates → face toward/away camera (front/back sprite)
            if (vy !== 0 && Math.abs(vy) >= Math.abs(vx)) this.facingUp = vy < 0;
            else if (vx !== 0) this.facingUp = false;
            pc.dir = vx < 0 ? -1 : 1;
          }
          this.followCam(pc.x, pc.y);
        }
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
    clampCamera(this.cam, this.cssW, this.cssH, WORLD_W, WORLD_H);
  }

  // ---- camera controls (called by input + zoom buttons) ----

  private panBy(dxCss: number, dyCss: number) {
    this.cam.x -= dxCss / this.cam.zoom;
    this.cam.y -= dyCss / this.cam.zoom;
    clampCamera(this.cam, this.cssW, this.cssH, WORLD_W, WORLD_H);
  }

  private zoomAt(factor: number, cssX: number, cssY: number) {
    zoomAbout(this.cam, factor, cssX, cssY, this.cssW, this.cssH, WORLD_W, WORLD_H);
  }

  // Zoom about the viewport center — for on-screen +/- buttons.
  zoomButton(factor: number) {
    this.zoomAt(factor, this.cssW / 2, this.cssH / 2);
  }

  // Ease the camera to keep the controlled character centered.
  private followCam(x: number, y: number) {
    const tx = x - this.cssW / this.cam.zoom / 2;
    const ty = y - this.cssH / this.cam.zoom / 2;
    this.cam.x += (tx - this.cam.x) * 0.12;
    this.cam.y += (ty - this.cam.y) * 0.12;
    clampCamera(this.cam, this.cssW, this.cssH, WORLD_W, WORLD_H);
  }

  // Designate the player-driven character (its patrol AI is suspended), or null
  // for observer mode (free pan/zoom, nobody driven). Clears stale input state
  // so a held direction or mid-turn facing doesn't leak from the previous
  // character.
  setControlled(id: string | null) {
    this.controlledId = id;
    this.held.clear();
    this.facingLeft = false;
    this.facingUp = false;
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

  private render(t: number) {
    const ctx = this.ctx;
    if (this.cssW === 0) return;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    const s = this.dpr * this.cam.zoom;
    ctx.setTransform(s, 0, 0, s, -this.cam.x * s, -this.cam.y * s);

    // Lay out every frontage once so both the ground detail and the actor pass read current
    // building x/width.
    for (const f of NORTH_FRONTAGES) layoutFrontage(f, this.aspectOf);
    for (const f of SOUTH_FRONTAGES) layoutFrontage(f, this.aspectOf);
    for (const f of RES_FRONTAGES) layoutFrontage(f, this.aspectOf);

    // (a) GROUND pre-pass — flat surfaces, always beneath every actor.
    this.drawGround();
    this.drawSidewalks();
    this.drawRoad();
    this.drawGroundDetail(); // aprons + landmark plazas on the walks

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
    const cx = W / 2, cy = Hh * 0.5;
    const rad = Math.hypot(W, Hh) * 0.62;
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    // (1) cool-shadow duotone — steal a little warmth from the darks so they read cinematic cool.
    ctx.globalCompositeOperation = "multiply";
    ctx.fillStyle = `rgba(150,170,205,${0.12 + 0.06 * night})`;
    ctx.fillRect(0, 0, W, Hh);
    // (2) warm highlight lift — a soft additive glow toward the center (the lit street), warmer at
    // golden hour, cooler/dimmer at night.
    ctx.globalCompositeOperation = "lighter";
    const warm = ctx.createRadialGradient(cx, cy, rad * 0.15, cx, cy, rad);
    warm.addColorStop(0, `rgba(255,206,150,${0.14 * (1 - 0.5 * night) + 0.06 * golden})`);
    warm.addColorStop(1, "rgba(255,206,150,0)");
    ctx.fillStyle = warm;
    ctx.fillRect(0, 0, W, Hh);
    // (3) overlay punch — widen contrast so the value structure (shadow / body / highlight)
    // separates. `overlay` darkens darks and lightens lights around mid-grey.
    ctx.globalCompositeOperation = "overlay";
    ctx.fillStyle = "rgba(128,128,128,0.16)";
    ctx.fillRect(0, 0, W, Hh);
    // (4) dual vignette — darken the corners (heavier than before) AND the center push from (2)
    // gives the center-to-edge contrast that makes a vignette actually read.
    ctx.globalCompositeOperation = "source-over";
    const vg = ctx.createRadialGradient(cx, cy, rad * 0.4, cx, cy, rad);
    vg.addColorStop(0, "rgba(4,4,8,0)");
    vg.addColorStop(1, `rgba(4,4,8,${0.42 + 0.14 * night})`);
    ctx.fillStyle = vg;
    ctx.fillRect(0, 0, W, Hh);
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
    // named soul cast
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

    // 1. street lamps — light from each globe, and a warm pool cast on the sidewalk below
    this.forEachLamp((x, baseY, headY) => {
      const gy = headY - 8;
      for (const gx of [x - LAMP_ARM, x + LAMP_ARM, x]) {
        const rr = 48;
        const g = ctx.createRadialGradient(gx, gy, 1, gx, gy, rr);
        g.addColorStop(0, `rgba(255,216,152,${0.5 * night})`);
        g.addColorStop(0.45, `rgba(255,196,120,${0.16 * night})`);
        g.addColorStop(1, "rgba(255,196,120,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(gx, gy, rr, 0, Math.PI * 2);
        ctx.fill();
      }
      // ground pool at the foot
      const pr = 74;
      const pg = ctx.createRadialGradient(x, baseY, 2, x, baseY, pr);
      pg.addColorStop(0, `rgba(255,190,110,${0.32 * night})`);
      pg.addColorStop(1, "rgba(255,190,110,0)");
      ctx.fillStyle = pg;
      ctx.beginPath();
      ctx.ellipse(x, baseY, pr, pr * 0.4, 0, 0, Math.PI * 2);
      ctx.fill();
      // bloom — a big soft halo over the whole lamp head so the light blooms into the dark
      const br = 104;
      const bg = ctx.createRadialGradient(x, gy, 4, x, gy, br);
      bg.addColorStop(0, `rgba(255,214,150,${0.12 * night})`);
      bg.addColorStop(1, "rgba(255,214,150,0)");
      ctx.fillStyle = bg;
      ctx.beginPath();
      ctx.arc(x, gy, br, 0, Math.PI * 2);
      ctx.fill();
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
        const gr = ctx.createRadialGradient(cx, gy, 2, cx, gy, rad);
        gr.addColorStop(0, `rgba(255,206,140,${0.14 * night})`);
        gr.addColorStop(1, "rgba(255,206,140,0)");
        ctx.fillStyle = gr;
        ctx.beginPath();
        ctx.ellipse(cx, gy, rad, Math.min(band * 0.6, 88), 0, 0, Math.PI * 2);
        ctx.fill();
        // marquee bloom, on the sign band (kept on the facade, not overhead)
        if (b.marquee) {
          const my = baseY + dir * Math.min(H * 0.55, 210);
          const mc = b.marqueeColor ?? "#e0b23a";
          const mr = Math.min(bw * 0.5, 150);
          const mg = ctx.createRadialGradient(cx, my, 2, cx, my, mr);
          mg.addColorStop(0, hexAlpha(mc, 0.5 * night));
          mg.addColorStop(1, hexAlpha(mc, 0));
          ctx.fillStyle = mg;
          ctx.beginPath();
          ctx.ellipse(cx, my, mr, Math.min(H * 0.12, 44), 0, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }

    // 3. people — a faint aura-tinted contact pool at the feet after dark (no bright halo).
    // The controlled character is marked by the "you are here" ring in drawNPC, not a glow.
    for (const s of this.npcs) {
      if (s.x < vL - 60 || s.x > vR + 60) continue;
      const aura = auraColor(s.soul);
      const r = 20;
      const a = 0.12 * night;
      const fy = s.y + 6;
      const g = ctx.createRadialGradient(s.x, fy, 1, s.x, fy, r);
      g.addColorStop(0, hexAlpha(aura, a));
      g.addColorStop(1, hexAlpha(aura, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.ellipse(s.x, fy, r, r * 0.45, 0, 0, Math.PI * 2);
      ctx.fill();
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

    ctx.strokeStyle = "#c9c4b6";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, ROAD_TOP + 4);
    ctx.lineTo(WORLD_W, ROAD_TOP + 4);
    ctx.moveTo(0, ROAD_BOTTOM - 4);
    ctx.lineTo(WORLD_W, ROAD_BOTTOM - 4);
    ctx.stroke();

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

  // The ground plane, drawn first behind everything. A base tone, a zoom-gated mottle so the
  // land between buildings has texture instead of a flat void, and a grass/dirt yard under
  // each house of the residential back-street. All viewport-culled, all deterministic.
  private drawGround() {
    const ctx = this.ctx;
    const vx = this.cam.x;
    const vy = this.cam.y;
    const vw = this.cssW / this.cam.zoom;
    const vh = this.cssH / this.cam.zoom;
    const vR = vx + vw;
    const vB = vy + vh;

    ctx.fillStyle = "#241f18";
    ctx.fillRect(vx, vy, vw, vh);

    // coarse mottle — only worth drawing (and paying for) when zoomed in enough to read it
    if (this.cam.zoom > 0.5) {
      const CELL = 92;
      const x0 = Math.floor(vx / CELL) * CELL;
      const y0 = Math.floor(vy / CELL) * CELL;
      ctx.globalAlpha = 0.5;
      for (let gx = x0; gx < vR; gx += CELL) {
        for (let gy = y0; gy < vB; gy += CELL) {
          const d = Math.round((groundHash(gx, gy) - 0.5) * 20);
          ctx.fillStyle = shade("#241f18", d);
          ctx.fillRect(gx, gy, CELL, CELL);
        }
      }
      ctx.globalAlpha = 1;
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
    // Grounding shadow stack — tighter/lighter than a building's (props have a small footprint).
    this.drawContactShadow(x, footY, w * 0.7, h, 0.7);
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
    // smoky walk FX + pendulum leg-blur behind the ped (they're always walking)
    this.drawWalkFX(ped.x, ped.y + FEET_DROP, w, ped.dir, t, (ped.bob % 1000) / 1000);
    this.drawLegBlur(img, b, ped.x, feetY, w, ped.dir < 0, t, ped.bob);
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
    img.onerror = () => this.sprites.set(key, null);
    img.src = `/buildings/${stem}.png`;
    this.sprites.set(key, img);
    return img;
  }

  // Seamless ground texture from /tiles/<name>. Cached; null once it 404s.
  private getTile(name: string): HTMLImageElement | null {
    const cached = this.tiles.get(name);
    if (cached !== undefined) return cached;
    const img = new Image();
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
    const k = (TILE_WORLD[name] ?? 160) / img.naturalWidth;
    pat.setTransform(new DOMMatrix([k, 0, 0, k, 0, 0]));
    ctx.fillStyle = pat;
    ctx.fillRect(cx0, cy0, cx1 - cx0, cy1 - cy0);
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
  private drawContactShadow(cx: number, footY: number, w: number, h: number, scale = 1): void {
    const ctx = this.ctx;
    const rx = Math.max(10, w * 0.5);
    // one light everywhere: upper-left → shadow falls down (+Y, toward camera) and right (+X).
    const offX = Math.min(w * 0.1, 40);
    const offY = Math.min(h * 0.1, 42);

    // (1) ground lift — faint warm halo, `lighten` so it only ever raises the ground a touch.
    ctx.save();
    ctx.globalCompositeOperation = "lighten";
    const lr = rx * 1.4;
    const lift = ctx.createRadialGradient(cx, footY, 1, cx, footY, lr);
    lift.addColorStop(0, `rgba(64,56,44,${0.09 * scale})`);
    lift.addColorStop(1, "rgba(64,56,44,0)");
    ctx.translate(cx, footY); ctx.scale(1, 0.22); ctx.translate(-cx, -footY);
    ctx.fillStyle = lift;
    ctx.beginPath(); ctx.arc(cx, footY, lr, 0, Math.PI * 2); ctx.fill();
    ctx.restore();

    // (2) cast body — cool blue-black, offset down+right, foreshortened, soft falloff.
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    const bcx = cx + offX, bcy = footY + offY, brx = rx * 1.2;
    const body = ctx.createRadialGradient(bcx, bcy, 1, bcx, bcy, brx);
    body.addColorStop(0, `rgba(8,7,16,${0.42 * scale})`);
    body.addColorStop(0.7, `rgba(8,7,16,${0.2 * scale})`);
    body.addColorStop(1, "rgba(8,7,16,0)");
    ctx.translate(bcx, bcy); ctx.scale(1, 0.4); ctx.translate(-bcx, -bcy);
    ctx.fillStyle = body;
    ctx.beginPath(); ctx.arc(bcx, bcy, brx, 0, Math.PI * 2); ctx.fill();
    ctx.restore();

    // (3) contact seam — crisp cool-black glue at the true foot line.
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    const seam = ctx.createRadialGradient(cx, footY, 1, cx, footY, rx);
    seam.addColorStop(0, `rgba(8,7,16,${0.6 * scale})`);
    seam.addColorStop(0.55, `rgba(8,7,16,${0.3 * scale})`);
    seam.addColorStop(1, "rgba(8,7,16,0)");
    ctx.translate(cx, footY); ctx.scale(1, 0.15); ctx.translate(-cx, -footY);
    ctx.fillStyle = seam;
    ctx.beginPath(); ctx.arc(cx, footY, rx, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
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
    // Grounding: the three-part shadow stack, drawn before the sprite so it reads as ground the
    // wall stands on. Fade with depth — far (north) row a touch lighter so it recedes.
    const depthScale = side === "north" ? 0.85 : 1;
    this.drawContactShadow(cx, baseY, w, H, depthScale);
    const prev = ctx.imageSmoothingEnabled;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, cx - w / 2, top, w, H);
    ctx.imageSmoothingEnabled = prev;
    // Base skirt: darken the wall's foot so it sinks into the ground seam rather than sitting
    // on a clean shelf edge.
    const skirtH = Math.min(16, H * 0.14);
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    const sg = ctx.createLinearGradient(0, baseY - skirtH, 0, baseY);
    sg.addColorStop(0, "rgba(16,12,8,0)");
    sg.addColorStop(1, "rgba(16,12,8,0.32)");
    ctx.fillStyle = sg;
    ctx.fillRect(cx - w / 2, baseY - skirtH, w, skirtH);
    ctx.restore();
    // Inter-building AO: darken the facade's vertical side edges so two adjacent buildings form a
    // shaded seam/valley between them — grounds the streetwall as one solid mass, not floating
    // cards. (On isolated landmarks it just reads as gentle form shading on the sides.)
    const edgeW = Math.max(6, w * 0.07);
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    const lAO = ctx.createLinearGradient(cx - w / 2, 0, cx - w / 2 + edgeW, 0);
    lAO.addColorStop(0, "rgba(10,10,20,0.34)");
    lAO.addColorStop(1, "rgba(10,10,20,0)");
    ctx.fillStyle = lAO;
    ctx.fillRect(cx - w / 2, top, edgeW, H);
    const rAO = ctx.createLinearGradient(cx + w / 2, 0, cx + w / 2 - edgeW, 0);
    rAO.addColorStop(0, "rgba(10,10,20,0.34)");
    rAO.addColorStop(1, "rgba(10,10,20,0)");
    ctx.fillStyle = rAO;
    ctx.fillRect(cx + w / 2 - edgeW, top, edgeW, H);
    ctx.restore();
    // Far-row atmospheric veil: wash the distant (north) streetwall toward a cool haze via a
    // light multiply, so the far row loses a little contrast and recedes from the near (south)
    // row. Multiply keeps it correct day and night (scales with the pixel it's over). Near row
    // untouched.
    if (side === "north" && growUp) {
      ctx.save();
      ctx.globalCompositeOperation = "multiply";
      ctx.globalAlpha = 0.16;
      ctx.fillStyle = "rgb(150,162,185)";
      ctx.fillRect(cx - w / 2, top, w, H);
      ctx.restore();
    }
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

    // (2) smoke puffs — kicked up at the feet, TRAILING BACK along the ground (so they read behind
    // the body instead of being hidden by the torso), rising only a little as they expand + fade.
    for (let k = 0; k < 5; k++) {
      const p = (t / 560 + phase + k / 5) % 1;
      const px = x + back * (w * 0.3 + p * 46);
      const py = footY - 2 - p * 12;
      const rad = 5 + p * 16;
      const a = (1 - p) * (0.42 + 0.14 * night);
      const g = ctx.createRadialGradient(px, py, 0, px, py, rad);
      g.addColorStop(0, `rgba(${rr},${gg},${bb},${a})`);
      g.addColorStop(0.55, `rgba(${rr},${gg},${bb},${a * 0.5})`);
      g.addColorStop(1, `rgba(${rr},${gg},${bb},0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(px, py, rad, 0, Math.PI * 2);
      ctx.fill();
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
    img: HTMLImageElement,
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
    const nW = img.naturalWidth;
    const nH = img.naturalHeight;
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
    const N = 7; // copies across the swing arc
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

  private drawNPC(s: NpcRuntime, t: number) {
    const ctx = this.ctx;
    // Gaia-style: planted when idle, a light step-bounce ONLY while moving.
    const bob = s.moving ? -Math.abs(Math.sin(t / 90)) * 2.5 : 0;
    const pulse = 0.75 + 0.25 * Math.sin(t / 400 + s.x * 0.05);
    const y = s.y + bob;

    const aura = auraColor(s.soul);
    const auraR = 34;
    const grad = ctx.createRadialGradient(s.x, y, 2, s.x, y, auraR);
    grad.addColorStop(0, hexAlpha(aura, 0.55 * pulse));
    grad.addColorStop(1, hexAlpha(aura, 0));
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(s.x, y, auraR, 0, Math.PI * 2);
    ctx.fill();

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
    // player facing away from the camera → use the back sprite for this outfit if one exists
    if (s.soul.id === this.controlledId && this.facingUp) {
      const back = this.getSprite(`${stem}_back`);
      if (back && back.complete && back.naturalWidth > 0) {
        sprite = back;
        spriteKey = `${stem}_back`;
      }
    }
    if (sprite && sprite.complete && sprite.naturalWidth > 0) {
      // Normalize to the same body height as every other character, feet planted (spriteBounds).
      const b = this.spriteBounds(spriteKey, sprite);
      const frameH = CHAR_BODY_H / Math.max(0.5, b.b - b.t);
      const w = frameH * (sprite.naturalWidth / sprite.naturalHeight);
      let flip = s.soul.id === this.controlledId ? this.facingLeft : s.dir < 0;
      if (SPRITE_FACES_LEFT.has(s.soul.id)) flip = !flip; // this sprite's art faces left by default
      const feetY = s.y + FEET_DROP + bob;
      const top = feetY - b.b * frameH;
      const prev = ctx.imageSmoothingEnabled;
      ctx.imageSmoothingEnabled = true; // smooth downscale — these are painted, not pixel art
      ctx.imageSmoothingQuality = "high";

      const drawAt = (cx: number, alpha: number) => {
        ctx.save();
        ctx.globalAlpha = alpha;
        if (flip) {
          ctx.translate(cx, 0);
          ctx.scale(-1, 1);
          ctx.translate(-cx, 0);
        }
        ctx.drawImage(sprite, cx - w / 2, top, w, frameH);
        ctx.restore();
      };

      // Smoky Gaia-style walk FX behind the body, the pendulum leg-blur at the feet, then the
      // crisp body on top. Every moving character gets both (see drawLegBlur).
      if (s.moving) {
        this.drawWalkFX(s.x, feetY, w, s.dir, t, (s.x * 0.0131) % 1);
        this.drawLegBlur(sprite, b, s.x, feetY, w, flip, t, s.x * 0.05);
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
