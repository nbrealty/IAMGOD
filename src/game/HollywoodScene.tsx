import { useEffect, useRef, useState } from "react";
import { HollywoodRenderer } from "./renderer";
import type { SoulEngine } from "../soul/engine";
import { SoulProfilePanel } from "../components/SoulProfilePanel";

export function HollywoodScene({ engine }: { engine: SoulEngine }) {
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

  return (
    <div className="scene-stage" ref={wrapRef}>
      <canvas ref={canvasRef} className="scene-canvas" />
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
