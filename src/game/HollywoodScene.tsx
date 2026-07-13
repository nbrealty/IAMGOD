import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { HollywoodRenderer } from "./renderer";
import type { SoulEngine } from "../soul/engine";
import { SoulProfilePanel } from "../components/SoulProfilePanel";
import { InventoryGrid } from "../components/InventoryGrid";
import { ROSTER } from "../soul/roster";
import { equippedStem } from "./inventory";
import { applyReading, type ReadingOutcome, type Reading } from "../soul/buzios";
import { formatMoney } from "../soul/derive";
import { BuziosReadingScene } from "../components/BuziosReadingScene";

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
  "vee_knox",
  "lua",
  "bibi",
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
  const [invOpen, setInvOpen] = useState(false); // inventory sheet for the controlled character
  const [roomId, setRoomId] = useState<string | null>(null); // current interior room id (null = outside)
  const [reading, setReading] = useState<ReadingOutcome | null>(null); // resolved reading panel
  const [povOpen, setPovOpen] = useState(false); // first-person búzios reading scene
  const [povSeed, setPovSeed] = useState(0);
  const castCount = useRef(0); // varies the reading seed per cast
  // Equipped outfit stem per soul (any soul absent here wears its default look). Remembered across
  // character switches; applied live to the renderer. Drives both inventory grids.
  const [equipped, setEquipped] = useState<Record<string, string>>({});
  const equippedRef = useRef(equipped);
  const equip = (soulId: string, stem: string) => setEquipped((m) => ({ ...m, [soulId]: stem }));

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    const renderer = new HollywoodRenderer(canvas, engine);
    rendererRef.current = renderer;
    renderer.setTapHandler((cssX, cssY) => {
      const id = renderer.hitTest(cssX, cssY);
      if (id) setSelectedId(id); // tapped a person → open their Soul Profile
      else renderer.tapToWalk(cssX, cssY); // tapped the ground → walk the controlled soul there
    });
    renderer.setRoomHandler((room) => { setRoomId(room); if (room === null) setReading(null); }); // track room; close reading on exit

    const fit = () => {
      const r = wrap.getBoundingClientRect();
      renderer.resize(r.width, r.height, window.devicePixelRatio || 1);
    };
    fit();
    renderer.attachInput();
    // Dress everyone in their remembered outfit before the first frame.
    for (const [id, stem] of Object.entries(equippedRef.current)) renderer.setOutfit(id, stem);
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

  // Push equip changes to the renderer live and keep the mount-time ref in sync.
  useEffect(() => {
    equippedRef.current = equipped;
    const r = rendererRef.current;
    if (r) for (const [id, stem] of Object.entries(equipped)) r.setOutfit(id, stem);
  }, [equipped]);

  const hold =
    (dir: "up" | "down" | "left" | "right", pressed: boolean) =>
    (e: ReactPointerEvent) => {
      e.preventDefault();
      rendererRef.current?.setMove(dir, pressed);
    };

  // Open the first-person búzios scene (tap-to-cast happens in there). Only in Yara's back room.
  const openReading = () => {
    if (!controlledId) return;
    setPovSeed(Math.floor(engine.clockMinutes) * 131 + castCount.current++);
    setPovOpen(true);
  };
  // The scene hands back the cast Reading once the shells settle; apply it to the soul + show the
  // reading panel over the settled shells. (castReading ran in the scene to drive the throw; this
  // applies the consequence — Axé + chakra-power — exactly once.)
  const onCast = (r: Reading) => {
    const soul = controlledId ? engine.souls.find((s) => s.id === controlledId) : null;
    if (soul) setReading(applyReading(soul, r));
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
        <button className="inv-open-btn" onClick={() => setInvOpen(true)}>
          🎒 Inventory
        </button>
      )}

      {(() => {
        const wallet = controlledId ? engine.souls.find((s) => s.id === controlledId)?.money : undefined;
        return wallet !== undefined ? <div className="wallet-chip">💵 {formatMoney(wallet)}</div> : null;
      })()}

      {roomId === "aguas-back" && controlledId !== null && !povOpen && (
        <button
          className="buzios-btn"
          onPointerUp={(e) => { e.preventDefault(); openReading(); }}
        >
          🐚 Consult the búzios
        </button>
      )}

      {povOpen && controlledId !== null && (
        <BuziosReadingScene
          soul={engine.souls.find((s) => s.id === controlledId)!}
          seed={povSeed}
          onCast={onCast}
          onExit={() => { setPovOpen(false); setReading(null); }}
        />
      )}

      {roomId !== null && (
        <button
          className="leave-room-btn"
          // Use pointer events (like the D-pad) rather than onClick — some mobile PWA webviews drop
          // synthetic click on dynamically-shown buttons. onPointerUp fires reliably on touch.
          onPointerUp={(e) => {
            e.preventDefault();
            rendererRef.current?.leaveRoom();
          }}
        >
          ← Leave
        </button>
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
      {invOpen && controlledId !== null && (
        <div className="panel-overlay" onClick={(e) => e.target === e.currentTarget && setInvOpen(false)}>
          <div className="panel-card inv-card">
            <h2>
              {PLAYABLE_CHARACTERS.find((c) => c.id === controlledId)?.label ?? "Inventory"}{" "}
              <span className="dim">· Inventory</span>
            </h2>
            <p className="inv-hint">Tap an outfit to wear it. Empty slots hold future items.</p>
            <InventoryGrid
              soulId={controlledId}
              equippedStem={equippedStem(controlledId, equipped)}
              onEquip={(stem) => equip(controlledId, stem)}
            />
            <button className="panel-close" onClick={() => setInvOpen(false)}>
              Close
            </button>
          </div>
        </div>
      )}

      {reading && (
        <div className="panel-overlay" onClick={(e) => e.target === e.currentTarget && setReading(null)}>
          <div className="panel-card buzios-card">
            <h2>Águas Douradas <span className="dim">· o jogo de búzios</span></h2>
            <p className="buzios-yara">Yara scatters the shells and lets Exu open the road.</p>
            <p className="buzios-cast">{reading.reading.openCount} of the sixteen fell open.</p>
            <div className={`buzios-odu ${reading.reading.ire ? "ire" : "osogbo"}`}>
              <div className="buzios-odu-name">
                Odù {reading.reading.odu.n} · {reading.reading.odu.name}
                <span className="buzios-orixa"> — {reading.reading.odu.orixa}</span>
              </div>
              <div className="buzios-tag">{reading.reading.ire ? "IRE · blessing" : "OSOGBO · obstacle"}</div>
            </div>
            <p className="buzios-present">“{reading.reading.present}”</p>
            <p className="buzios-future">“{reading.reading.future}”</p>
            <div className="buzios-effect">
              <div>Axé +{reading.reading.axeGain} — spiritual strength rises{reading.tieredUp ? `, and you cross into initiation ${reading.newInitiation}.` : "."}</div>
              <div>The {reading.reading.chakra} stirs awake.</div>
              {reading.unlockedPower && (
                <div className="buzios-power">◆ Power awakened — <b>{reading.unlockedPower.name}</b>: {reading.unlockedPower.blurb}</div>
              )}
            </div>
            <button className="panel-close" onClick={() => { setReading(null); setPovOpen(false); }}>Close</button>
          </div>
        </div>
      )}

      <SoulProfilePanel
        engine={engine}
        soulId={selectedId}
        equipped={equipped}
        onEquip={equip}
        onClose={() => setSelectedId(null)}
      />
    </div>
  );
}
