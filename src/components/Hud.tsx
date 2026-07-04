import { useEffect, useState } from "react";
import { SupabaseBadge } from "./SupabaseBadge";

function formatClock(totalMinutes: number, day: number): string {
  const h24 = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  const ampm = h24 >= 12 ? "PM" : "AM";
  let h12 = h24 % 12;
  if (h12 === 0) h12 = 12;
  const mStr = m < 10 ? `0${m}` : `${m}`;
  return `Day ${day} | ${h12}:${mStr} ${ampm}`;
}

export function Hud() {
  const [minutes, setMinutes] = useState(14 * 60 + 34);
  const [day, setDay] = useState(1);

  useEffect(() => {
    const id = setInterval(() => {
      setMinutes((m) => {
        const next = m + 1;
        if (next >= 24 * 60) {
          setDay((d) => d + 1);
          return next - 24 * 60;
        }
        return next;
      });
    }, 2000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="hud">
      <div className="hud-breadcrumb">
        Hollywood, CA <span className="dim">&gt;</span> Hollywood &amp; Highland
      </div>
      <div className="hud-clock">{formatClock(minutes, day)}</div>
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
