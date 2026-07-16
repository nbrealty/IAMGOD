// Production asset paths for the Phase-1 front-end (title / mode / creator).
// Cleaned derivatives produced by tools/asset-pipeline/ from the raws in public/cac/pages/.
const A = "/assets";

export const TITLE = {
  bgDesktop: `${A}/title/title-bg-desktop.webp`,
  bgMobile: `${A}/title/title-bg-mobile.webp`,
  logoWide: `${A}/title/iamgod-logo-wide.png`, // #4 stacked logo pending → wide used on mobile too, for now
  raysDesktop: `${A}/title/title-god-rays-desktop.png`,
  raysMobile: `${A}/title/title-god-rays-mobile.png`,
  haze: `${A}/title/title-haze-desktop.png`,
  goldDust: `${A}/title/title-gold-dust-desktop.png`,
  soulSparks: `${A}/title/title-soul-sparks-desktop.png`,
  vignette: `${A}/title/title-vignette-desktop.png`,
  roadGlow: `${A}/title/title-road-glow-desktop.png`,
} as const;

export const MODE = {
  bgDesktop: `${A}/mode-select/mode-select-bg-desktop.webp`,
  bgMobile: `${A}/mode-select/mode-select-bg-mobile.webp`,
  sandboxCard: `${A}/mode-select/mode-sandbox-card.webp`,
  storyCard: `${A}/mode-select/mode-story-card.webp`,
} as const;

export const CREATOR = {
  stageDesktop: `${A}/creator/creator-stage-desktop.png`, // keyed (checker removed) → shown on a dark bg
  bgMobile: `${A}/creator/creator-bg-mobile.webp`,
} as const;

export const UI = {
  brandMark: `${A}/ui/brand-mark.png`,
  buttonFrame: `${A}/ui/button-frame.png`,
} as const;
