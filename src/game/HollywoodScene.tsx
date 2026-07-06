import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { HollywoodRenderer } from "./renderer";
import type { SoulEngine } from "../soul/engine";
import { SoulProfilePanel } from "../components/SoulProfilePanel";
import { ROSTER } from "../soul/roster";

// A short chip label: the quoted nickname if the soul has one, else the first name.
function chipLabel(name: string): string {
  const m = name.match(/["“”]([^"“”]+)["“”]/);
  if (m) return m[1].split("/")[0].trim();
  return name.split(/\s+/)[0];
}

// Every soul is playable — step into any of them. `id: null` is Observer Mode (free
// pan/zoom, nobody driven), pinned first. Built from the live roster so new souls appear
// automatically.
export const PLAYABLE_CHARACTERS: { id: string | null; label: string }[] = [
  { id: null, label: "Observe" },
  ...ROSTER.map((s) => ({ id: s.id, label: chipLabel(s.name) })),
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
