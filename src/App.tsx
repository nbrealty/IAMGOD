import { useRef, useState } from "react";
import { Hud } from "./components/Hud";
import { HollywoodScene, PLAYABLE_CHARACTERS } from "./game/HollywoodScene";
import { SoulEngine } from "./soul/engine";
import { ROSTER } from "./soul/roster";
import "./App.css";

export default function App() {
  // One engine for the whole app, created once. It owns the souls + sim clock.
  const engineRef = useRef<SoulEngine | null>(null);
  if (!engineRef.current) engineRef.current = new SoulEngine(ROSTER);
  const engine = engineRef.current;
  // Debug handle: lets dev tooling drive the sim clock (e.g. set the time to preview
  // lighting). Harmless read/write access to the running engine.
  (globalThis as unknown as { __engine?: SoulEngine }).__engine = engine;

  const [speed, setSpeed] = useState(engine.speed);
  function changeSpeed(s: number) {
    engine.speed = s;
    setSpeed(s);
  }

  // Lori is the default playable character; null = Observer Mode (free pan/zoom).
  const [controlledId, setControlledId] = useState<string | null>("lori");
  const controlledName = controlledId
    ? PLAYABLE_CHARACTERS.find((c) => c.id === controlledId)?.label ?? null
    : null;

  return (
    <div className="app">
      <Hud engine={engine} speed={speed} onSpeed={changeSpeed} />
      <main className="stage">
        <HollywoodScene engine={engine} controlledId={controlledId} onControlledChange={setControlledId} />
      </main>
      <footer className="footnote">
        {controlledName
          ? `Move ${controlledName} with the D-pad / arrows or TAP the ground to walk there · pinch or ＋/－ to zoom · tap a person for their Soul Profile`
          : "Drag to pan · pinch or ＋/－ to zoom · tap a person to read their live Soul Profile"}
        <span className="build-stamp"> · build {__BUILD_ID__}</span>
      </footer>
    </div>
  );
}
