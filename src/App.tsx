import { Hud } from "./components/Hud";
import { HollywoodScene } from "./game/HollywoodScene";
import "./App.css";

export default function App() {
  return (
    <div className="app">
      <Hud />
      <main className="stage">
        <HollywoodScene />
      </main>
      <footer className="footnote">
        Tap a person on the street to read their Soul Profile. Phase 0 skeleton —
        code-drawn scene, one shared web codebase (Vercel · iOS · Windows/Mac).
      </footer>
    </div>
  );
}
