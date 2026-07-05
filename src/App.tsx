import { useRef, useState } from "react";
import { Hud } from "./components/Hud";
import { HollywoodScene } from "./game/HollywoodScene";
import { SoulEngine } from "./soul/engine";
import { ROSTER } from "./soul/roster";
import "./App.css";

export default function App() {
  // One engine for the whole app, created once. It owns the souls + sim clock.
  const engineRef = useRef<SoulEngine | null>(null);
  if (!engineRef.current) engineRef.current = new SoulEngine(ROSTER);
  const engine = engineRef.current;

  const [speed, setSpeed] = useState(engine.speed);
  function changeSpeed(s: number) {
    engine.speed = s;
    setSpeed(s);
  }

  return (
    <div className="app">
      <Hud engine={engine} speed={speed} onSpeed={changeSpeed} />
      <main className="stage">
        <HollywoodScene engine={engine} />
      </main>
      <footer className="footnote">
        Move Roxy with the D-pad (or WASD / arrows) · pinch or ＋/－ to zoom · tap a person to read their live Soul Profile
      </footer>
    </div>
  );
}
