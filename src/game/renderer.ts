// The Hollywood & Highland renderer. Draws the dimetric street scene to a canvas
// and runs the walk-cycle animation. Ported from the Day 1 greybox prototype into
// a self-contained class the React layer can start/stop and hit-test against.
//
// Deliberately still hand-drawn canvas (no image assets, no Phaser). Phaser and
// real pixel-art sprites arrive in a later phase; this proves the deploy/test loop.

import {
  SCENE_W,
  SCENE_H,
  ROAD_TOP,
  ROAD_BOTTOM,
  NORTH_SIDEWALK_TOP,
  SOUTH_SIDEWALK_TOP,
  SOUTH_SIDEWALK_BOTTOM,
  NORTH_BASELINE,
  SOUTH_BASELINE,
  HIGHLAND_LEFT,
  HIGHLAND_RIGHT,
  NPCS,
  NORTH_BUILDINGS,
  SOUTH_BUILDINGS,
  type Building,
  type SoulProfile,
} from "./sceneData";

interface NpcRuntime {
  def: SoulProfile;
  x: number;
  y: number;
  dir: number;
}

interface CarRuntime {
  x: number;
  y: number;
  dir: number;
  speed: number;
}

const NORTH_SIDEWALK_BOTTOM = ROAD_TOP;

function clamp(v: number): number {
  return Math.max(0, Math.min(255, v));
}

function shade(hex: string, amt: number): string {
  const num = parseInt(hex.replace("#", ""), 16);
  const r = clamp((num >> 16) + amt);
  const g = clamp(((num >> 8) & 0xff) + amt);
  const b = clamp((num & 0xff) + amt);
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
  private ctx: CanvasRenderingContext2D;
  private raf = 0;
  private lastTime: number | null = null;
  private npcs: NpcRuntime[];
  private cars: CarRuntime[];

  constructor(canvas: HTMLCanvasElement) {
    canvas.width = SCENE_W;
    canvas.height = SCENE_H;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas context unavailable");
    this.ctx = ctx;

    this.npcs = NPCS.map((n) => ({
      def: n,
      x: n.xMin + Math.random() * (n.xMax - n.xMin),
      dir: Math.random() > 0.5 ? 1 : -1,
      y: n.row === "north" ? NORTH_SIDEWALK_TOP + 20 : SOUTH_SIDEWALK_TOP + 20,
    }));

    this.cars = [
      { x: 40, y: ROAD_TOP + 25, dir: 1, speed: 90 },
      { x: 900, y: ROAD_TOP + 25, dir: 1, speed: 70 },
      { x: 700, y: ROAD_BOTTOM - 25, dir: -1, speed: 80 },
    ];
  }

  start() {
    const step = (t: number) => {
      if (this.lastTime === null) this.lastTime = t;
      const dt = Math.min(0.05, (t - this.lastTime) / 1000);
      this.lastTime = t;

      for (const s of this.npcs) {
        s.x += s.dir * s.def.speed * dt;
        if (s.x > s.def.xMax) {
          s.x = s.def.xMax;
          s.dir = -1;
        }
        if (s.x < s.def.xMin) {
          s.x = s.def.xMin;
          s.dir = 1;
        }
      }
      for (const car of this.cars) {
        car.x += car.dir * car.speed * dt;
        if (car.x > SCENE_W + 60) car.x = -60;
        if (car.x < -60) car.x = SCENE_W + 60;
      }

      this.render(t);
      this.raf = requestAnimationFrame(step);
    };
    this.raf = requestAnimationFrame(step);
  }

  stop() {
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  // Returns the NPC nearest to (vx, vy) in virtual coords within a tap radius, or null.
  hitTest(vx: number, vy: number): SoulProfile | null {
    let hit: SoulProfile | null = null;
    let best = 30 * 30;
    for (const s of this.npcs) {
      const dx = s.x - vx;
      const dy = s.y - vy;
      const dist = dx * dx + dy * dy;
      if (dist < best) {
        best = dist;
        hit = s.def;
      }
    }
    return hit;
  }

  // ---- drawing ----

  private render(t: number) {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, SCENE_W, SCENE_H);

    this.drawHills();
    ctx.fillStyle = "#3a3226";
    ctx.fillRect(0, 150, SCENE_W, SCENE_H - 150);

    this.drawRoad();
    this.drawSidewalks();
    this.drawCars();

    for (const b of NORTH_BUILDINGS) {
      if (b.special === "tcl") this.drawTCL(b.x);
      else this.drawBuilding(b);
    }
    for (const b of SOUTH_BUILDINGS) this.drawBuilding(b);

    for (const s of this.npcs) this.drawNPC(s, t);

    const tint = ctx.createLinearGradient(0, 0, 0, SCENE_H);
    tint.addColorStop(0, "rgba(255, 214, 140, 0.06)");
    tint.addColorStop(1, "rgba(255, 170, 90, 0.1)");
    ctx.fillStyle = tint;
    ctx.fillRect(0, 0, SCENE_W, SCENE_H);
  }

  private drawHills() {
    const ctx = this.ctx;
    const grd = ctx.createLinearGradient(0, 0, 0, 140);
    grd.addColorStop(0, "#8fb4cf");
    grd.addColorStop(1, "#b9c9a8");
    ctx.fillStyle = grd;
    ctx.fillRect(0, 0, SCENE_W, 150);

    ctx.fillStyle = "#7c9a6d";
    ctx.beginPath();
    ctx.moveTo(0, 150);
    ctx.quadraticCurveTo(220, 60, 480, 120);
    ctx.quadraticCurveTo(760, 40, 1040, 110);
    ctx.quadraticCurveTo(1320, 55, 1600, 120);
    ctx.lineTo(1600, 150);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = "#6a8a5c";
    ctx.beginPath();
    ctx.moveTo(0, 150);
    ctx.quadraticCurveTo(300, 100, 620, 140);
    ctx.quadraticCurveTo(950, 95, 1250, 135);
    ctx.quadraticCurveTo(1450, 105, 1600, 140);
    ctx.lineTo(1600, 150);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = "#efe9de";
    const startX = 560;
    const gap = 20;
    for (let i = 0; i < 9; i++) ctx.fillRect(startX + i * gap, 78, 4, 12);
  }

  private drawRoad() {
    const ctx = this.ctx;
    ctx.fillStyle = "#33322f";
    ctx.fillRect(0, ROAD_TOP, SCENE_W, ROAD_BOTTOM - ROAD_TOP);

    ctx.strokeStyle = "#d8c96a";
    ctx.setLineDash([26, 20]);
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, (ROAD_TOP + ROAD_BOTTOM) / 2);
    ctx.lineTo(SCENE_W, (ROAD_TOP + ROAD_BOTTOM) / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.strokeStyle = "#c9c4b6";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, ROAD_TOP + 4);
    ctx.lineTo(SCENE_W, ROAD_TOP + 4);
    ctx.moveTo(0, ROAD_BOTTOM - 4);
    ctx.lineTo(SCENE_W, ROAD_BOTTOM - 4);
    ctx.stroke();

    ctx.fillStyle = "#33322f";
    ctx.fillRect(HIGHLAND_LEFT, 0, HIGHLAND_RIGHT - HIGHLAND_LEFT, SCENE_H);
    ctx.strokeStyle = "#d8c96a";
    ctx.setLineDash([22, 18]);
    ctx.beginPath();
    ctx.moveTo((HIGHLAND_LEFT + HIGHLAND_RIGHT) / 2, 0);
    ctx.lineTo((HIGHLAND_LEFT + HIGHLAND_RIGHT) / 2, SCENE_H);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = "#e7e2d2";
    for (let cx = HIGHLAND_LEFT - 6; cx < HIGHLAND_RIGHT + 6; cx += 14) {
      ctx.fillRect(cx, ROAD_TOP + 6, 8, ROAD_BOTTOM - ROAD_TOP - 12);
    }
    for (let cy = ROAD_TOP - 6; cy < ROAD_BOTTOM + 6; cy += 14) {
      ctx.fillRect(HIGHLAND_LEFT + 6, cy, HIGHLAND_RIGHT - HIGHLAND_LEFT - 12, 8);
    }

    ctx.fillStyle = "#efe4bd";
    ctx.font = "bold 13px sans-serif";
    ctx.textAlign = "left";
    ctx.fillText("HOLLYWOOD BLVD", 30, ROAD_TOP + (ROAD_BOTTOM - ROAD_TOP) / 2 + 5);
    ctx.save();
    ctx.translate((HIGHLAND_LEFT + HIGHLAND_RIGHT) / 2 + 5, 300);
    ctx.rotate(Math.PI / 2);
    ctx.fillText("HIGHLAND AVE", 0, 0);
    ctx.restore();
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
    for (let x = 70; x < SCENE_W - 70; x += 78) {
      if (x > HIGHLAND_LEFT - 40 && x < HIGHLAND_RIGHT + 40) continue;
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
    ctx.fillRect(0, NORTH_SIDEWALK_TOP, SCENE_W, NORTH_SIDEWALK_BOTTOM - NORTH_SIDEWALK_TOP);
    ctx.fillRect(0, SOUTH_SIDEWALK_TOP, SCENE_W, SOUTH_SIDEWALK_BOTTOM - SOUTH_SIDEWALK_TOP);
    ctx.strokeStyle = "#847e70";
    ctx.lineWidth = 1;
    for (let x = 0; x < SCENE_W; x += 40) {
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

  private drawBuilding(b: Building) {
    const ctx = this.ctx;
    const width = b.width ?? 120;
    const height = b.height ?? 90;
    const side = b.side ?? "north";
    const depth = b.depth ?? 34;
    const skew = b.skew ?? width * 0.14;
    const facadeColor = b.facadeColor ?? "#5b6b7a";
    const roofColor = b.roofColor ?? shade(facadeColor, -28);
    const sideColor = shade(facadeColor, -42);
    const x = b.x;

    const baseY = side === "north" ? NORTH_BASELINE : SOUTH_BASELINE;
    const dir = side === "north" ? -1 : 1;
    const facadeTopY = baseY + dir * height;

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

    ctx.fillStyle = shade(facadeColor, 22);
    const rows = Math.max(1, Math.floor(height / 34) - 1);
    const cols = Math.max(2, Math.floor(width / 46));
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const wx = x + 12 + (c * (width - 24)) / cols;
        const wy = (side === "north" ? facadeTopY + 14 : baseY + 14) + r * 30;
        ctx.fillRect(wx, wy, 16, 18);
      }
    }

    if (b.marquee) {
      ctx.fillStyle = b.marqueeColor ?? "#e64444";
      const my = side === "north" ? facadeTopY + 6 : baseY - 24;
      ctx.fillRect(x + 6, my, width - 12, 22);
      ctx.fillStyle = "#fff8e2";
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(b.marquee, x + width / 2, my + 15);
    }

    ctx.fillStyle = "#f3ecd8";
    ctx.font = "bold 12px sans-serif";
    ctx.textAlign = "center";
    const labelY = side === "north" ? baseY - 6 : baseY + 14;
    ctx.fillText(b.label ?? "", x + width / 2, labelY);
  }

  private drawTCL(x: number) {
    const ctx = this.ctx;
    const width = 260;
    const baseY = NORTH_BASELINE;
    const facadeH = 130;
    const topFacade = baseY - facadeH;

    ctx.fillStyle = "#7a1f1f";
    ctx.fillRect(x, topFacade, width, facadeH);
    ctx.fillStyle = "#2d1a12";
    ctx.fillRect(x + width * 0.32, baseY - 74, width * 0.36, 74);

    ctx.fillStyle = "#9c2a2a";
    ctx.fillRect(x + width * 0.22, topFacade - 6, 14, 90);
    ctx.fillRect(x + width * 0.78 - 14, topFacade - 6, 14, 90);

    const tiers = [
      { y: topFacade - 6, w: width + 30, h: 16 },
      { y: topFacade - 34, w: width - 10, h: 16 },
      { y: topFacade - 62, w: width - 60, h: 16 },
      { y: topFacade - 88, w: width - 110, h: 14 },
    ];
    for (const tier of tiers) {
      const tx = x + (width - tier.w) / 2;
      ctx.fillStyle = "#1f5c47";
      ctx.beginPath();
      ctx.moveTo(tx, tier.y + tier.h);
      ctx.lineTo(tx + tier.w, tier.y + tier.h);
      ctx.lineTo(tx + tier.w - 20, tier.y);
      ctx.lineTo(tx + 20, tier.y);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#c99a3f";
      ctx.fillRect(tx - 6, tier.y + tier.h - 4, 10, 4);
      ctx.fillRect(tx + tier.w - 4, tier.y + tier.h - 4, 10, 4);
    }

    ctx.fillStyle = "#c9a34a";
    ctx.beginPath();
    ctx.arc(x + width / 2, baseY + 34, 30, Math.PI, 0);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#5a86c9";
    ctx.beginPath();
    ctx.ellipse(x + width / 2, baseY + 30, 16, 8, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#111";
    ctx.font = "bold 12px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("CHINESE", x + width / 2, topFacade + 40);
    ctx.fillText("THEATRE", x + width / 2, topFacade + 56);

    ctx.fillStyle = "#f3ecd8";
    ctx.font = "bold 13px sans-serif";
    ctx.fillText("TCL CHINESE THEATRE", x + width / 2, baseY - 6);
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

  private drawNPC(s: NpcRuntime, t: number) {
    const ctx = this.ctx;
    const bob = Math.sin(t / 180 + s.x) * 2;
    const pulse = 0.75 + 0.25 * Math.sin(t / 400 + s.x * 0.05);
    const y = s.y + bob;

    const grad = ctx.createRadialGradient(s.x, y, 2, s.x, y, 26);
    grad.addColorStop(0, hexAlpha(s.def.aura, 0.55 * pulse));
    grad.addColorStop(1, hexAlpha(s.def.aura, 0));
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(s.x, y, 26, 0, Math.PI * 2);
    ctx.fill();

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
