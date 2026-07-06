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
  layoutFrontage,
  BACKDROP_BUILDINGS,
  RESIDENTIAL_BUILDINGS,
  type Building,
  type Frontage,
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
}

const NORTH_SIDEWALK_BOTTOM = ROAD_TOP;
const TAP_THRESHOLD = 7; // css px of movement below which a pointer-up counts as a tap

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

export class HollywoodRenderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private raf = 0;
  private lastTime: number | null = null;
  private npcs: NpcRuntime[];
  private cars: CarRuntime[];
  private engine: SoulEngine;

  private cam: Camera = { x: 0, y: 0, zoom: 0.1 };
  private cssW = 0;
  private cssH = 0;
  private dpr = 1;
  private centered = false;

  // player control
  private controlledId: string | null = null;
  private held = new Set<string>();
  private facingLeft = false;
  private facingUp = false; // moving away from camera → show the back sprite

  private sprites = new Map<string, HTMLImageElement | null>();
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

    this.cars = [
      { x: 40, y: ROAD_TOP + 25, dir: 1, speed: 90 },
      { x: 900, y: ROAD_TOP + 25, dir: 1, speed: 70 },
      { x: 700, y: ROAD_BOTTOM - 25, dir: -1, speed: 80 },
    ];
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

    // ground (no sky)
    ctx.fillStyle = "#241f18";
    ctx.fillRect(0, 0, WORLD_W, WORLD_H);

    for (const b of BACKDROP_BUILDINGS) this.drawBuilding(b);
    this.drawFrontages(NORTH_FRONTAGES);
    this.drawSidewalks();
    this.drawRoad();
    this.drawCars();
    this.drawFrontages(SOUTH_FRONTAGES);
    for (const b of RESIDENTIAL_BUILDINGS) this.drawBuilding(b);
    this.drawFrontages(RES_FRONTAGES);
    for (const npc of this.npcs) this.drawNPC(npc, t);

    const tint = ctx.createLinearGradient(0, 0, 0, WORLD_H);
    tint.addColorStop(0, "rgba(255, 214, 140, 0.05)");
    tint.addColorStop(1, "rgba(255, 170, 90, 0.08)");
    ctx.fillStyle = tint;
    ctx.fillRect(0, 0, WORLD_W, WORLD_H);
  }

  private drawRoad() {
    const ctx = this.ctx;
    ctx.fillStyle = "#33322f";
    ctx.fillRect(0, ROAD_TOP, WORLD_W, ROAD_BOTTOM - ROAD_TOP);

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
    for (const cs of CROSS_STREETS) {
      const roadL = cs.x - CS_ROAD_HALF;
      const roadR = cs.x + CS_ROAD_HALF;
      ctx.fillStyle = "#2c2b28";
      ctx.fillRect(roadL, 0, roadR - roadL, WORLD_H);
      ctx.strokeStyle = "#d8c96a";
      ctx.setLineDash([22, 18]);
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(cs.x, 0);
      ctx.lineTo(cs.x, WORLD_H);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = "#e7e2d2";
      for (let px = roadL - 6; px < roadR + 6; px += 14) {
        ctx.fillRect(px, ROAD_TOP + 6, 8, ROAD_BOTTOM - ROAD_TOP - 12);
      }
      for (let py = ROAD_TOP - 6; py < ROAD_BOTTOM + 6; py += 14) {
        ctx.fillRect(roadL + 6, py, roadR - roadL - 12, 8);
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
    for (let x = 70; x < WORLD_W - 70; x += 78) {
      if (CROSS_STREETS.some((cs) => x > cs.x - CS_HALF - 20 && x < cs.x + CS_HALF + 20)) continue;
      ctx.fillStyle = "#6b4a86";
      ctx.beginPath();
      ctx.ellipse(x, y, 20, 9, 0, 0, Math.PI * 2);
      ctx.fill();
      this.drawStar(x, y, 8, 3.6, "#e9c96b");
    }
  }

  private drawSidewalks() {
    const ctx = this.ctx;
    ctx.fillStyle = "#9a9488";
    // Hollywood Blvd sidewalks (full width)
    ctx.fillRect(0, NORTH_SIDEWALK_TOP, WORLD_W, NORTH_SIDEWALK_BOTTOM - NORTH_SIDEWALK_TOP);
    ctx.fillRect(0, SOUTH_SIDEWALK_TOP, WORLD_W, SOUTH_SIDEWALK_BOTTOM - SOUTH_SIDEWALK_TOP);
    // Cross-street sidewalks (full height, flanking each cross road)
    for (const cs of CROSS_STREETS) {
      ctx.fillRect(cs.x - CS_HALF, 0, CS_HALF - CS_ROAD_HALF, WORLD_H);
      ctx.fillRect(cs.x + CS_ROAD_HALF, 0, CS_HALF - CS_ROAD_HALF, WORLD_H);
    }

    ctx.strokeStyle = "#847e70";
    ctx.lineWidth = 1;
    for (let x = 0; x < WORLD_W; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, NORTH_SIDEWALK_TOP);
      ctx.lineTo(x, NORTH_SIDEWALK_BOTTOM);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x, SOUTH_SIDEWALK_TOP);
      ctx.lineTo(x, SOUTH_SIDEWALK_BOTTOM);
      ctx.stroke();
    }
    this.drawWalkOfFame(NORTH_SIDEWALK_TOP + 20);
    this.drawWalkOfFame(SOUTH_SIDEWALK_TOP + 20);
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

  // Justify each frontage to its buildable land, then paint its buildings in order.
  private drawFrontages(frontages: Frontage[]) {
    for (const f of frontages) {
      layoutFrontage(f, this.aspectOf);
      for (const b of f.buildings) this.drawBuilding(b);
    }
  }

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

  private drawCars() {
    const ctx = this.ctx;
    const colors = ["#b23b3b", "#3b5fb2", "#c9c9c9", "#e0a733"];
    this.cars.forEach((car, i) => {
      ctx.fillStyle = colors[i % colors.length];
      ctx.fillRect(car.x, car.y - 10, 46, 20);
      ctx.fillStyle = "#dff0ff";
      ctx.fillRect(car.x + 8, car.y - 7, 12, 8);
      ctx.fillRect(car.x + 26, car.y - 7, 12, 8);
    });
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
    const prev = ctx.imageSmoothingEnabled;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, cx - w / 2, top, w, H);
    ctx.imageSmoothingEnabled = prev;
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

    let sprite = this.getSprite(s.soul.id);
    // player facing away from the camera → use the back sprite if one exists
    if (s.soul.id === this.controlledId && this.facingUp) {
      const back = this.getSprite(`${s.soul.id}_back`);
      if (back && back.complete && back.naturalWidth > 0) sprite = back;
    }
    if (sprite && sprite.complete && sprite.naturalWidth > 0) {
      const targetH = 84; // bigger, Gaia-style — shows the sprite detail
      const w = targetH * (sprite.naturalWidth / sprite.naturalHeight);
      const flip = s.soul.id === this.controlledId ? this.facingLeft : s.dir < 0;
      const top = y - targetH + 12;
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
        ctx.drawImage(sprite, cx - w / 2, top, w, targetH);
        ctx.restore();
      };

      // Gaia-style walk: the body stays crisp down to the ankles, and the FEET
      // dissolve into a soft "boat" — a smear that curves UP at the ends. Each foot
      // copy is fanned out horizontally and lifted by offset^2 (edges rise), so the
      // union forms a concave-up crescent. Feet render ONLY as this smear while moving.
      const footTop = top + targetH * 0.83;
      if (s.moving) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(s.x - w, top - 2, w * 2, footTop - top + 2);
        ctx.clip();
        drawAt(s.x, 1); // crisp head-to-ankles
        ctx.restore();

        const spread = 8 + 4 * Math.abs(Math.sin(t / 80));
        const lift = 7;
        const footBaseY = y + 12;

        // ONE motion blur spanning BOTH feet: a single soft dark crescent (concave-up),
        // built from a few stacked translucent layers so it reads as one fused blur
        // instead of two feet. Its width/curve pulse with the step.
        const hw = w * 0.5 + spread;
        ctx.save();
        for (const layer of [
          { s: 1, a: 0.24 },
          { s: 0.72, a: 0.24 },
          { s: 0.46, a: 0.24 },
        ]) {
          const h = hw * layer.s;
          ctx.fillStyle = `rgba(14, 12, 9, ${layer.a})`;
          ctx.beginPath();
          ctx.moveTo(s.x - h, footBaseY - lift);
          ctx.quadraticCurveTo(s.x, footBaseY + 6, s.x + h, footBaseY - lift);
          ctx.quadraticCurveTo(s.x, footBaseY - lift - 5, s.x - h, footBaseY - lift);
          ctx.closePath();
          ctx.fill();
        }
        ctx.restore();
      } else {
        drawAt(s.x, 1);
      }
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
