import { useEffect, useRef, useState } from "react";
import { useLayout, useReducedMotion } from "./useLayout";
import { TitleScreen } from "./screens/TitleScreen";
import { ModeSelectScreen } from "./screens/ModeSelectScreen";
import { CreatorScreen } from "./screens/CreatorScreen";
import { SettingsModal } from "./ui/SettingsModal";
import { DEFAULT_DRAFT, hasValidSave, loadDraft, saveDraft, type CharacterDraft, type Mode } from "./draft";
import "./frontend.css";

type Screen = "title" | "mode" | "creator";

// The Phase-1 front-end shell: TITLE → MODE SELECT → CREATOR, then hand a confirmed draft to the
// game. A tiny screen state machine (no router/state dep — the app had neither). The chosen mode +
// draft persist to localStorage so they survive the mode↔creator hop and a reload.
export function FrontEnd({ onEnterGame }: { onEnterGame: (mode: Mode | null, draft: CharacterDraft | null) => void }) {
  const layout = useLayout();
  const prefersReduced = useReducedMotion();
  const [reducedOverride, setReducedOverride] = useState<boolean | null>(null);
  const reduced = reducedOverride ?? prefersReduced;

  const [screen, setScreen] = useState<Screen>("title");
  const [draft, setDraft] = useState<CharacterDraft>(() => loadDraft() ?? { ...DEFAULT_DRAFT });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [muted, setMuted] = useState(false);
  const [textScale, setTextScale] = useState(1);
  const [fading, setFading] = useState(false);
  const canContinue = hasValidSave();

  // Crossfade-through-black between screens (skipped under reduced motion).
  const timers = useRef<number[]>([]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  const go = (next: Screen | "game") => {
    const commit = () => {
      if (next === "game") onEnterGame(draft.mode, draft.mode ? draft : null);
      else setScreen(next);
    };
    if (reduced) { commit(); return; }
    setFading(true);
    timers.current.push(window.setTimeout(() => { commit(); setFading(false); }, 260));
  };

  const setMode = (mode: Mode) => setDraft((d) => ({ ...d, mode }));
  const confirmCharacter = (final: CharacterDraft) => { saveDraft(final); setDraft(final); go("game"); };

  return (
    <div className={`frontend ${reduced ? "reduced" : ""}`} style={{ fontSize: `${textScale}em` }}>
      {screen === "title" && (
        <TitleScreen
          layout={layout}
          canContinue={canContinue}
          onContinue={() => { const d = loadDraft(); if (d) { setDraft(d); go("game"); } }}
          onNewGame={() => { setDraft({ ...DEFAULT_DRAFT }); go("mode"); }}
          onSettings={() => setSettingsOpen(true)}
        />
      )}
      {screen === "mode" && (
        <ModeSelectScreen
          layout={layout}
          mode={draft.mode}
          onSelect={setMode}
          onBack={() => go("title")}
          onContinue={() => draft.mode && go("creator")}
        />
      )}
      {screen === "creator" && (
        <CreatorScreen
          layout={layout}
          draft={draft}
          onChange={setDraft}
          onBack={() => go("mode")}
          onConfirm={confirmCharacter}
        />
      )}

      {settingsOpen && (
        <SettingsModal
          reducedMotion={reduced}
          onReducedMotion={setReducedOverride}
          muted={muted} onMuted={setMuted}
          textScale={textScale} onTextScale={setTextScale}
          onClose={() => setSettingsOpen(false)}
        />
      )}

      <div className={`fe-fade ${fading ? "on" : ""}`} aria-hidden />
    </div>
  );
}
