import { useEffect, useState } from "react";
import { CREATOR } from "../assets";
import type { Layout } from "../useLayout";
import { GoldButton } from "../ui/GoldButton";
import type { CharacterDraft } from "../draft";
import {
  BUILDS, SKINS, baseOption, isAvailable, firstSkinFor, allAvailable,
  DEFAULT_BUILD, DEFAULT_SKIN, type Build, type Skin,
} from "../creator/bodyManifest";

// PHASE 1 creator: name + body-base selection (build × skin) with a live front/back preview, zoom,
// randomize, and reset. Swaps whole keyed body PNGs — no morphs/face/hair (a later phase). The draft
// holds name/mode/build/skin; the front/back + zoom are transient preview state.
export function CreatorScreen({
  layout, draft, onChange, onBack, onConfirm,
}: {
  layout: Layout;
  draft: CharacterDraft;
  onChange: (d: CharacterDraft) => void;
  onBack: () => void;
  onConfirm: (d: CharacterDraft) => void;
}) {
  const [view, setView] = useState<"front" | "back">("front");
  const [zoom, setZoom] = useState(1);
  const [nameError, setNameError] = useState<string | null>(null);

  const build = draft.build as Build;
  const skin = draft.skin as Skin;
  const opt = baseOption(build, skin);
  const bg = layout === "desktop" ? CREATOR.stageDesktop : CREATOR.bgMobile;

  // keep the draft on a valid, available pair
  useEffect(() => {
    if (!isAvailable(build, skin)) onChange({ ...draft, skin: firstSkinFor(build) });
  }, [build, skin]); // eslint-disable-line react-hooks/exhaustive-deps

  const pickBuild = (b: Build) => onChange({ ...draft, build: b, skin: isAvailable(b, skin) ? skin : firstSkinFor(b) });
  const pickSkin = (s: Skin) => isAvailable(build, s) && onChange({ ...draft, skin: s });
  const randomize = () => { const all = allAvailable(); const r = all[Math.floor(Math.random() * all.length)]; onChange({ ...draft, build: r.build, skin: r.skin }); };
  const reset = () => { onChange({ ...draft, build: DEFAULT_BUILD, skin: DEFAULT_SKIN }); setView("front"); setZoom(1); };
  const confirm = () => {
    if (!draft.name.trim()) { setNameError("Give your incarnation a name."); return; }
    if (!isAvailable(build, skin)) return;
    onConfirm(draft);
  };

  return (
    <div className={`creator-screen ${layout}`}>
      <div className="layer bg" style={{ backgroundImage: `url(${bg})` }} />

      <div className="creator-stage">
        <div className="creator-body" style={{ transform: `scale(${zoom})` }}>
          <img src={opt[view]} alt={`${opt.label}, ${view} view`} draggable={false} />
        </div>
        {/* preload the other view so the toggle is instant */}
        <img className="creator-preload" src={view === "front" ? opt.back : opt.front} alt="" aria-hidden />
      </div>

      {/* preview controls float over the stage */}
      <div className="creator-view-tools">
        <div className="seg" role="group" aria-label="View">
          <button className={view === "front" ? "on" : ""} onClick={() => setView("front")} aria-pressed={view === "front"}>Front</button>
          <button className={view === "back" ? "on" : ""} onClick={() => setView("back")} aria-pressed={view === "back"}>Back</button>
        </div>
        <div className="seg" role="group" aria-label="Zoom">
          <button onClick={() => setZoom((z) => Math.max(0.7, +(z - 0.15).toFixed(2)))} aria-label="Zoom out">－</button>
          <button onClick={() => setZoom((z) => Math.min(2.2, +(z + 0.15).toFixed(2)))} aria-label="Zoom in">＋</button>
        </div>
      </div>

      <div className="creator-panel">
        <h1 className="creator-title">Create your incarnation</h1>

        <label className="creator-field">
          <span>Name</span>
          <input value={draft.name} maxLength={24} placeholder="Name your character"
            onChange={(e) => { onChange({ ...draft, name: e.target.value }); setNameError(null); }} />
          {nameError && <span className="creator-error">{nameError}</span>}
        </label>

        <div className="creator-field">
          <span>Body build</span>
          <div className="creator-chips">
            {BUILDS.map((b) => (
              <button key={b.id} className={`creator-chip ${build === b.id ? "on" : ""}`}
                aria-pressed={build === b.id} onClick={() => pickBuild(b.id)}>{b.label}</button>
            ))}
          </div>
        </div>

        <div className="creator-field">
          <span>Skin tone</span>
          <div className="creator-chips">
            {SKINS.map((s) => {
              const avail = isAvailable(build, s.id);
              return (
                <button key={s.id} className={`creator-chip ${skin === s.id ? "on" : ""}`}
                  disabled={!avail} title={avail ? undefined : "Not available for this build yet"}
                  aria-pressed={skin === s.id} onClick={() => pickSkin(s.id)}>{s.label}</button>
              );
            })}
          </div>
        </div>

        <div className="creator-tools">
          <button className="creator-tool" onClick={randomize}>🎲 Randomize</button>
          <button className="creator-tool" onClick={reset}>↺ Reset</button>
        </div>

        <div className="creator-actions">
          <GoldButton variant="ghost" onClick={onBack}>← Back</GoldButton>
          <GoldButton variant="cta" onClick={confirm}>Confirm</GoldButton>
        </div>
      </div>
    </div>
  );
}
