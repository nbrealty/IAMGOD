import { TITLE } from "../assets";
import type { Layout } from "../useLayout";
import { GoldButton } from "../ui/GoldButton";

// Animated, responsive title screen. Layers are absolutely-positioned images stacked back→front;
// all ambient motion is CSS-keyframed (no per-frame React state) and disabled under reduced motion
// via the `reduced` class on the root. Only the current layout's heavy art is mounted.
export function TitleScreen({
  layout, canContinue, onContinue, onNewGame, onSettings,
}: {
  layout: Layout;
  canContinue: boolean;
  onContinue: () => void;
  onNewGame: () => void;
  onSettings: () => void;
}) {
  const desktop = layout === "desktop";
  const bg = desktop ? TITLE.bgDesktop : TITLE.bgMobile;

  return (
    <div className={`title-screen ${layout}`}>
      {/* 1. background (slow push toward the boulevard vanishing point) */}
      <div className="layer bg" style={{ backgroundImage: `url(${bg})` }} />
      {/* 3. road-light glow (desktop only — aligns to the boulevard) */}
      {desktop && <div className="layer road" style={{ backgroundImage: `url(${TITLE.roadGlow})` }} />}
      {/* 4. neon accents would go here (deferred) */}
      {/* 5. god rays — raster fan on desktop (blends cleanly); mobile uses the CSS top-glow only,
           since the narrow raster beam keyed with a torn seam */}
      {desktop && <div className="layer rays" style={{ backgroundImage: `url(${TITLE.raysDesktop})` }} />}
      {/* 6. haze (desktop) */}
      {desktop && <div className="layer haze" style={{ backgroundImage: `url(${TITLE.haze})` }} />}
      {/* 7. gold dust */}
      <div className="layer dust" style={{ backgroundImage: `url(${TITLE.goldDust})` }} />
      {/* 8. soul sparks (rare) */}
      <div className="layer sparks" style={{ backgroundImage: `url(${TITLE.soulSparks})` }} />
      {/* 9. vignette (readability) */}
      <div className="layer vignette" style={{ backgroundImage: `url(${TITLE.vignette})` }} />

      {/* 10. logo + 11. menu */}
      <div className="title-content">
        <img className="title-logo" src={TITLE.logoWide} alt="I AM GOD" />
        <nav className="title-menu" aria-label="Main menu">
          <GoldButton onClick={onContinue} disabled={!canContinue}>Continue</GoldButton>
          <GoldButton onClick={onNewGame} variant="cta">New Game</GoldButton>
          <GoldButton onClick={onSettings}>Settings</GoldButton>
        </nav>
      </div>
    </div>
  );
}
