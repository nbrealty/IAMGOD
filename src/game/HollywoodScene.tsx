import { useEffect, useRef, useState } from "react";
import { HollywoodRenderer } from "./renderer";
import { SCENE_W, SCENE_H } from "./sceneData";
import type { SoulEngine } from "../soul/engine";
import { SoulProfilePanel } from "../components/SoulProfilePanel";

export function HollywoodScene({ engine }: { engine: SoulEngine }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<HollywoodRenderer | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const renderer = new HollywoodRenderer(canvas, engine);
    rendererRef.current = renderer;
    renderer.start();
    return () => {
      renderer.stop();
      rendererRef.current = null;
    };
  }, [engine]);

  function handleClick(evt: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    const renderer = rendererRef.current;
    if (!canvas || !renderer) return;
    const rect = canvas.getBoundingClientRect();
    const vx = (evt.clientX - rect.left) * (SCENE_W / rect.width);
    const vy = (evt.clientY - rect.top) * (SCENE_H / rect.height);
    const hitId = renderer.hitTest(vx, vy);
    if (hitId) setSelectedId(hitId);
  }

  return (
    <div className="scene-stage">
      <canvas
        ref={canvasRef}
        className="scene-canvas"
        width={SCENE_W}
        height={SCENE_H}
        onClick={handleClick}
      />
      <SoulProfilePanel engine={engine} soulId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
