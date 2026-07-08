import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { HollywoodRenderer } from "./renderer";
import type { SoulEngine } from "../soul/engine";
import { SoulProfilePanel } from "../components/SoulProfilePanel";
import { ROSTER } from "../soul/roster";
import { OUTFITS, outfitsFor } from "./outfits";

// A short chip label: the quoted nickname if the soul has one, else the first name.
function chipLabel(name: string): string {
  const m = name.match(/["“”]([^"“”]+)["“”]/);
  if (m) return m[1].split("/")[0].trim();
  return name.split(/\s+/)[0];
}

// Only souls with real sprite art are playable — the rest live as autonomous NPCs (they
// still spawn, walk, and open their Soul Profile on tap; they just can't be driven). This
// is the user-owned allowlist: add an id here the moment a character becomes playable.
const PLAYABLE_IDS = new Set([
  "roxy_valente",
  "lori",
  "nia",
  "kiki",
  "maya",
  "jordyn",
  "dalia",
  "nathaniel",
  "elizabeth",
]);

// `id: null` is Observer Mode (free pan/zoom, nobody driven), pinned first. The rest are the
// art-backed souls above, in roster order, so new playable characters appear automatically.
export const PLAYABLE_CHARACTERS: { id: string | null; label: string }[] = [
  { id: null, label: "Observe" },
  ...ROSTER.filter((s) => PLAYABLE_IDS.has(s.id)).map((s) => ({ id: s.id, label: chipLabel(s.name) })),
];

interface Props {
  engine: SoulEngine;
  controlledId: string | null;
  onControlledChange: (id: string | null) => void;
}

export function HollywoodScene({ engine, controlledId, onControlledChange }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<HollywoodRenderer | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Wardrobe: the chosen outfit stem per soul (defaults to each soul's first/base outfit).
  // Remembered across character switches so a look sticks until you change it again.
  const [outfitByChar, setOutfitByChar] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const [id, list] of Object.entries(OUTFITS)) init[id] = list[0].stem;
    return init;
  });
  const outfitRef = useRef(outfitByChar);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    const renderer = new HollywoodRenderer(canvas, engine);
    rendererRef.current = renderer;
    renderer.setTapHandler((cssX, cssY) => {
      const id = renderer.hitTest(cssX, cssY);
      if (id) setSelectedId(id);
    });

    const fit = () => {
      const r = wrap.getBoundingClientRect();
      renderer.resize(r.width, r.height, window.devicePixelRatio || 1);
    };
    fit();
    renderer.attachInput();
    // Dress everyone in their remembered outfit before the first frame.
    for (const [id, stem] of Object.entries(outfitRef.current)) renderer.setOutfit(id, stem);
    renderer.start();

    const ro = new ResizeObserver(fit);
    ro.observe(wrap);
    window.addEventListener("resize", fit);

    return () => {
      renderer.stop();
      ro.disconnect();
      window.removeEventListener("resize", fit);
      rendererRef.current = null;
    };
  }, [engine]);

  // Apply the controlled-character selection whenever it changes (including
  // the first render, once the renderer above has mounted).
  useEffect(() => {
    rendererRef.current?.setControlled(controlledId);
  }, [controlledId]);

  // Push wardrobe changes to the renderer live and keep the mount-time ref in sync.
  useEffect(() => {
    outfitRef.current = outfitByChar;
    const r = rendererRef.current;
    if (r) for (const [id, stem] of Object.entries(outfitByChar)) r.setOutfit(id, stem);
  }, [outfitByChar]);

  const hold =
    (dir: "up" | "down" | "left" | "right", pressed: boolean) =>
    (e: ReactPointerEvent) => {
      e.preventDefault();
      rendererRef.current?.setMove(dir, pressed);
    };

  return (
    <div className="scene-stage" ref={wrapRef}>
      <canvas ref={canvasRef} className="scene-canvas" />

      <div className="char-switcher">
        {PLAYABLE_CHARACTERS.map((c) => (
          <button
            key={c.label}
            className={`char-chip ${controlledId === c.id ? "active" : ""}`}
            onClick={() => onControlledChange(c.id)}
          >
            {c.id === null ? "👁 " : ""}
            {c.label}
          </button>
        ))}
      </div>

      {outfitsFor(controlledId).length > 1 && (
        <div className="outfit-switcher">
          <span className="outfit-label">👗 Wardrobe</span>
          {outfitsFor(controlledId).map((o) => (
            <button
              key={o.id}
              className={`outfit-chip ${outfitByChar[controlledId!] === o.stem ? "active" : ""}`}
              onClick={() => setOutfitByChar((m) => ({ ...m, [controlledId!]: o.stem }))}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}

      {controlledId !== null && (
        <div className="dpad">
          <button
            className="dpad-btn up"
            aria-label="Move up"
            onPointerDown={hold("up", true)}
            onPointerUp={hold("up", false)}
            onPointerLeave={hold("up", false)}
            onPointerCancel={hold("up", false)}
          >
            ▲
          </button>
          <div className="dpad-row">
            <button
              className="dpad-btn left"
              aria-label="Move left"
              onPointerDown={hold("left", true)}
              onPointerUp={hold("left", false)}
              onPointerLeave={hold("left", false)}
              onPointerCancel={hold("left", false)}
            >
              ◀
            </button>
            <button
              className="dpad-btn down"
              aria-label="Move down"
              onPointerDown={hold("down", true)}
              onPointerUp={hold("down", false)}
              onPointerLeave={hold("down", false)}
              onPointerCancel={hold("down", false)}
            >
              ▼
            </button>
            <button
              className="dpad-btn right"
              aria-label="Move right"
              onPointerDown={hold("right", true)}
              onPointerUp={hold("right", false)}
              onPointerLeave={hold("right", false)}
              onPointerCancel={hold("right", false)}
            >
              ▶
            </button>
          </div>
        </div>
      )}

      <div className="zoom-controls">
        <button onClick={() => rendererRef.current?.zoomButton(1.3)} aria-label="Zoom in">
          ＋
        </button>
        <button onClick={() => rendererRef.current?.zoomButton(1 / 1.3)} aria-label="Zoom out">
          －
        </button>
      </div>
      <SoulProfilePanel engine={engine} soulId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
