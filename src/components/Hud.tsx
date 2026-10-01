import { useEffect, useReducer } from "react";
import type { SoulEngine } from "../soul/engine";
import { SupabaseBadge } from "./SupabaseBadge";

const SPEEDS = [
  { value: 0, label: "❚❚" },
  { value: 1, label: "1×" },
  { value: 5, label: "5×" },
  { value: 20, label: "20×" },
];

interface Props {
  engine: SoulEngine;
  speed: number;
  onSpeed: (s: number) => void;
}

export function Hud({ engine, speed, onSpeed }: Props) {
  // Poll the engine clock for display (the engine owns sim time).
  const [, force] = useReducer((x) => x + 1, 0);
  useEffect(() => {
    const id = setInterval(force, 500);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="hud">
      <div className="hud-breadcrumb">
        Hollywood, CA <span className="dim">&gt;</span> Hollywood &amp; Highland
      </div>

      <div className="hud-center">
        <div className="hud-clock">{engine.clockString()}</div>
        <div className="speed-controls">
          {SPEEDS.map((s) => (
            <button
              key={s.value}
              className={`speed-btn ${speed === s.value ? "active" : ""}`}
              onClick={() => onSpeed(s.value)}
              title={s.value === 0 ? "Pause" : `${s.value}× speed`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="hud-right">
        <div className="faith">
          <div className="gauge-row">
            <span className="gauge-label">PRESENCE</span>
            <div className="gauge-track">
              <div className="gauge-fill presence" style={{ width: "82%" }} />
            </div>
          </div>
          <div className="gauge-row">
            <span className="gauge-label">TRUST</span>
            <div className="gauge-track">
              <div className="gauge-fill trust" style={{ width: "47%" }} />
            </div>
          </div>
        </div>
        <SupabaseBadge />
      </div>
    </div>
  );
}
