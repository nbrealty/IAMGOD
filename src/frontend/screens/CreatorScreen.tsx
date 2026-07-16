import { useState } from "react";
import { CREATOR } from "../assets";
import type { Layout } from "../useLayout";
import { GoldButton } from "../ui/GoldButton";
import type { CharacterDraft } from "../draft";

// PHASE 1 creator — SCAFFOLD. Name + build/skin selection + confirm, on the creation-chamber stage.
// The live body preview, front/back toggle, zoom, randomize, reset and the data-driven body manifest
// (from the keyed base sprites) land in the next step; this establishes the screen + draft flow.
const BUILDS = ["petite", "slim", "average", "athletic", "curvy", "plus"];
const SKINS = [
  { id: "light", label: "Light" },
  { id: "medium", label: "Medium" },
  { id: "deep", label: "Deep" },
];

export function CreatorScreen({
  layout, draft, onChange, onBack, onConfirm,
}: {
  layout: Layout;
  draft: CharacterDraft;
  onChange: (d: CharacterDraft) => void;
  onBack: () => void;
  onConfirm: (d: CharacterDraft) => void;
}) {
  const [nameError, setNameError] = useState<string | null>(null);
  const bg = layout === "desktop" ? CREATOR.stageDesktop : CREATOR.bgMobile;

  const set = (patch: Partial<CharacterDraft>) => onChange({ ...draft, ...patch });
  const confirm = () => {
    if (!draft.name.trim()) { setNameError("Give your incarnation a name."); return; }
    onConfirm(draft);
  };

  return (
    <div className={`creator-screen ${layout}`}>
      <div className="layer bg" style={{ backgroundImage: `url(${bg})` }} />
      <div className="creator-stage" aria-hidden>
        {/* body preview mounts here in the next step */}
        <div className="creator-body-placeholder" />
      </div>

      <div className="creator-panel">
        <h1 className="creator-title">Create your incarnation</h1>

        <label className="creator-field">
          <span>Name</span>
          <input
            value={draft.name}
            maxLength={24}
            placeholder="Name your character"
            onChange={(e) => { set({ name: e.target.value }); setNameError(null); }}
          />
          {nameError && <span className="creator-error">{nameError}</span>}
        </label>

        <div className="creator-field">
          <span>Body build</span>
          <div className="creator-chips">
            {BUILDS.map((b) => (
              <button key={b} className={`creator-chip ${draft.build === b ? "on" : ""}`} onClick={() => set({ build: b })}>
                {b[0].toUpperCase() + b.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="creator-field">
          <span>Skin tone</span>
          <div className="creator-chips">
            {SKINS.map((s) => (
              <button key={s.id} className={`creator-chip ${draft.skin === s.id ? "on" : ""}`} onClick={() => set({ skin: s.id })}>
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="creator-actions">
          <GoldButton variant="ghost" onClick={onBack}>← Back</GoldButton>
          <GoldButton variant="cta" onClick={confirm}>Confirm</GoldButton>
        </div>
      </div>
    </div>
  );
}
