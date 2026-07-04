import { useEffect, useRef, useState } from "react";
import { HollywoodRenderer } from "./renderer";
import { SCENE_W, SCENE_H, type SoulProfile } from "./sceneData";
import { SoulProfilePanel } from "../components/SoulProfilePanel";

export function HollywoodScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<HollywoodRenderer | null>(null);
  const [selected, setSelected] = useState<SoulProfile | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const renderer = new HollywoodRenderer(canvas);
    rendererRef.current = renderer;
    renderer.start();
    return () => {
      renderer.stop();
      rendererRef.current = null;
    };
  }, []);

  function handleClick(evt: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    const renderer = rendererRef.current;
    if (!canvas || !renderer) return;
    const rect = canvas.getBoundingClientRect();
    const vx = (evt.clientX - rect.left) * (SCENE_W / rect.width);
    const vy = (evt.clientY - rect.top) * (SCENE_H / rect.height);
    const hit = renderer.hitTest(vx, vy);
    if (hit) setSelected(hit);
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
      <SoulProfilePanel soul={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
