import { useEffect, useRef, useState } from "react";
import type { Soul } from "../soul/types";
import { castReading, type Reading } from "../soul/buzios";

// First-person búzios reading: drop into the POV table plate, TAP to cast, and 16 cowrie shells
// fly from Yara's hands and scatter onto the cloth — landing to match the odù (predetermined by
// castReading, then tweened; no physics engine, per the research). When they settle, onCast fires
// with the Reading so the parent can apply it + show the reading panel over the settled shells.
const N = 16;
// Peneira / cast zone in normalized plate coords (the woven sieve sits centre, a touch low).
const HAND_Y = 0.34; // shells launch from around her hands (upper-centre)
const ZONE = { cx: 0.5, cy: 0.6, rx: 0.19, ry: 0.12 }; // scatter ellipse on the cloth

interface Shell {
  face: "open" | "closed";
  sx: number; sy: number; // start (norm)
  ex: number; ey: number; // end (norm)
  rot: number; // final rotation
  delay: number; // ms before it launches
  hop: number; // bounce height factor
}

function easeOut(t: number): number { return 1 - Math.pow(1 - t, 3); }

export function BuziosReadingScene({
  soul, seed, onCast, onExit,
}: {
  soul: Soul;
  seed: number;
  onCast: (r: Reading) => void;
  onExit: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<"ready" | "throwing" | "done">("ready");
  const imgs = useRef<{ pov?: HTMLImageElement; open?: HTMLImageElement; closed?: HTMLImageElement }>({});
  const shells = useRef<Shell[]>([]);
  const throwStart = useRef(0);
  const casted = useRef(false);
  const lastReading = useRef<Reading | null>(null);

  // Load the three images once.
  useEffect(() => {
    const load = (src: string) => { const i = new Image(); i.src = src; return i; };
    imgs.current = { pov: load("/aguas/buzios-pov.jpg"), open: load("/props/buzio-open.png"), closed: load("/props/buzio-closed.png") };
  }, []);

  // Render loop: draw the cover-fit plate + the shells at their current tween position.
  useEffect(() => {
    let raf = 0;
    const draw = () => {
      const cv = canvasRef.current, wrap = wrapRef.current;
      if (cv && wrap) {
        const dpr = window.devicePixelRatio || 1;
        const W = wrap.clientWidth, H = wrap.clientHeight;
        if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
        const ctx = cv.getContext("2d")!;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, W, H);
        const pov = imgs.current.pov;
        if (pov && pov.complete && pov.naturalWidth) {
          // cover-fit
          const s = Math.max(W / pov.naturalWidth, H / pov.naturalHeight);
          const dw = pov.naturalWidth * s, dh = pov.naturalHeight * s;
          ctx.drawImage(pov, (W - dw) / 2, (H - dh) / 2, dw, dh);
        } else {
          ctx.fillStyle = "#241812"; ctx.fillRect(0, 0, W, H);
        }
        // shells
        const shH = H * 0.055; // shell draw height
        const now = performance.now();
        for (const sh of shells.current) {
          const img = sh.face === "open" ? imgs.current.open : imgs.current.closed;
          if (!img || !img.complete || !img.naturalWidth) continue;
          let t = 0;
          if (phase === "throwing") t = Math.max(0, Math.min(1, (now - throwStart.current - sh.delay) / 520));
          else if (phase === "done") t = 1;
          const e = easeOut(t);
          const x = (sh.sx + (sh.ex - sh.sx) * e) * W;
          const y = (sh.sy + (sh.ey - sh.sy) * e) * H - Math.sin(Math.PI * t) * sh.hop * H; // little arc
          const w = shH * (img.naturalWidth / img.naturalHeight);
          ctx.save();
          ctx.translate(x, y);
          ctx.rotate(sh.rot * e);
          // soft contact shadow once landed
          if (t > 0.85) { ctx.globalAlpha = 0.28; ctx.fillStyle = "#1a0f08"; ctx.beginPath(); ctx.ellipse(0, shH * 0.4, w * 0.5, shH * 0.16, 0, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1; }
          ctx.drawImage(img, -w / 2, -shH / 2, w, shH);
          ctx.restore();
        }
      }
      // fire onCast once the throw has settled
      if (phase === "throwing" && !casted.current) {
        const last = shells.current.reduce((m, s) => Math.max(m, s.delay), 0);
        if (performance.now() - throwStart.current > last + 620) {
          casted.current = true;
          setPhase("done");
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [phase]);

  // When the throw settles, hand the reading up (parent applies it + shows the panel).
  useEffect(() => {
    if (phase !== "done") return;
    const r = lastReading.current;
    if (r) { const id = setTimeout(() => onCast(r), 450); return () => clearTimeout(id); }
  }, [phase, onCast]);

  const cast = () => {
    if (phase !== "ready") return;
    const reading = castReading(soul, seed);
    lastReading.current = reading;
    // Assign faces: openCount open, rest closed, shuffled deterministically from the seed.
    const faces: ("open" | "closed")[] = Array.from({ length: N }, (_, i) => (i < reading.openCount ? "open" : "closed"));
    let a = seed >>> 0;
    const rng = () => { a = (a * 1664525 + 1013904223) >>> 0; return a / 4294967296; };
    for (let i = faces.length - 1; i > 0; i--) { const j = Math.floor(rng() * (i + 1)); [faces[i], faces[j]] = [faces[j], faces[i]]; }
    shells.current = faces.map((face, i) => {
      const ang = rng() * Math.PI * 2, rad = Math.sqrt(rng());
      return {
        face,
        sx: 0.5 + (rng() - 0.5) * 0.06, sy: HAND_Y + (rng() - 0.5) * 0.03,
        ex: ZONE.cx + Math.cos(ang) * ZONE.rx * rad, ey: ZONE.cy + Math.sin(ang) * ZONE.ry * rad,
        rot: (rng() - 0.5) * 2.2, delay: i * 22, hop: 0.05 + rng() * 0.05,
      };
    });
    throwStart.current = performance.now();
    casted.current = false;
    setPhase("throwing");
  };

  return (
    <div className="buzios-scene" ref={wrapRef} onPointerUp={cast}>
      <canvas ref={canvasRef} className="buzios-scene-canvas" />
      {phase === "ready" && <div className="buzios-prompt">Tap to cast the búzios</div>}
      <button className="buzios-exit" onPointerUp={(e) => { e.stopPropagation(); onExit(); }}>← Back</button>
    </div>
  );
}
