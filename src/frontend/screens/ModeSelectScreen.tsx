import { MODE } from "../assets";
import type { Layout } from "../useLayout";
import { GoldButton } from "../ui/GoldButton";
import type { Mode } from "../draft";

// The two selectable posters. Baked poster lettering is decorative — the accessible name +
// description live in code (never rely on the image text alone).
const MODES: { id: Mode; card: string; label: string; desc: string }[] = [
  {
    id: "sandbox", card: MODE.sandboxCard, label: "Sandbox God Mode",
    desc: "A freeform god experience. Observe, build, alter, bless, punish, and experiment without a fixed personal storyline.",
  },
  {
    id: "story", card: MODE.storyCard, label: "Story Mode",
    desc: "Enter the world through one created character and experience a directed personal story inside the living city.",
  },
];

export function ModeSelectScreen({
  layout, mode, onSelect, onBack, onContinue,
}: {
  layout: Layout;
  mode: Mode | null;
  onSelect: (m: Mode) => void;
  onBack: () => void;
  onContinue: () => void;
}) {
  const bg = layout === "desktop" ? MODE.bgDesktop : MODE.bgMobile;
  return (
    <div className={`mode-screen ${layout}`}>
      <div className="layer bg" style={{ backgroundImage: `url(${bg})` }} />
      <div className="layer scrim" />
      <div className="mode-content">
        <h1 className="mode-title">Choose your path</h1>
        <div className="mode-cards" role="radiogroup" aria-label="Game mode">
          {MODES.map((m) => (
            <button
              key={m.id}
              className={`mode-card ${mode === m.id ? "selected" : ""} ${mode && mode !== m.id ? "quiet" : ""}`}
              role="radio"
              aria-checked={mode === m.id}
              aria-label={`${m.label}. ${m.desc}`}
              onClick={() => onSelect(m.id)}
            >
              <img src={m.card} alt="" />
              <div className="mode-card-info">
                <div className="mode-card-name">{m.label}</div>
                <div className="mode-card-desc">{m.desc}</div>
              </div>
            </button>
          ))}
        </div>
        <div className="mode-actions">
          <GoldButton variant="ghost" onClick={onBack}>← Back</GoldButton>
          <GoldButton variant="cta" onClick={onContinue} disabled={!mode}>
            {mode === "sandbox" ? "Enter as God" : mode === "story" ? "Create Character" : "Continue"}
          </GoldButton>
        </div>
      </div>
    </div>
  );
}
