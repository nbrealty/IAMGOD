# Phase 1 — UI Implementation Plan

Front-end shell: **Title → Mode Select → Basic Character Creator → enter game**. Preserves
the existing Hollywood renderer. Stops at body-base selection (no morph/face/hair/clothing).

## 1. Screen flow & navigation (no new dependency)

The app has **no router and no state library** today — `App.tsx` renders `Hud` + `HollywoodScene`
with local `useState`. Smallest maintainable solution: a **screen state machine** in `App`.

```
type Screen = "title" | "mode" | "creator" | "game";
```

- `App` owns `screen`, `mode` (`"sandbox" | "story" | null`), and `characterDraft`.
- Renders exactly one screen; `game` mounts the existing `<Hud/> + <HollywoodScene/>` unchanged.
- Transitions are plain setState + a short CSS crossfade (fade-through-black), reusing the
  visual language we already use for room swaps.
- Draft + mode persist to `localStorage` (`iamgod.phase1.draft.v1`) so they survive a reload and
  the mode↔creator hop. A "New Game" always starts a fresh draft.

**Boot:** `main.tsx` unchanged; `App` starts on `title` (not straight into the game).

## 2. Component structure

```
src/frontend/
  FrontEnd.tsx            // screen switch + transitions + draft/mode state, localStorage
  screens/
    TitleScreen.tsx       // animated layered title + menu (Continue/New Game/Settings)
    ModeSelectScreen.tsx  // Sandbox/Story posters + descriptions + Back/Continue
    CreatorScreen.tsx     // stage + body preview + controls
  ui/
    LayerStack.tsx        // absolutely-positioned responsive image layers
    GoldButton.tsx        // nine-slice frame + HTML label (accessible)
    SettingsModal.tsx     // reduced-motion / mute / text-size, focus-trapped
    useTitleAnimation.ts  // rAF, time-based, visibility + reduced-motion aware
  creator/
    bodyManifest.ts       // data-driven from discovered base files (see §7)
    useCharacterDraft.ts
public/assets/{source,title,mode-select,creator,ui,characters/base}/
```

`App.tsx` becomes a thin host: `screen==="game" ? <Game/> : <FrontEnd onEnterGame=…/>`. The
game path stays byte-for-byte what exists now.

## 3. State flow

- `FrontEnd` holds `{screen, mode, draft}`; passes setters down.
- `Continue` enabled only if a valid saved draft exists (real check, never faked).
- `New Game` → `mode` screen (fresh draft). Mode pick persists; `Continue` on mode → `creator`.
- Creator edits mutate `draft`; `Confirm` validates then either enters the game driving a
  synthesized soul, or shows a Phase-1 completion state if game integration isn't safe.
- Game screen keeps its own engine/`controlledId` state as today.

## 4. Responsive behavior

- **Breakpoint** by orientation/width: desktop (landscape, ≥900px) vs mobile (portrait/narrow).
- Pick the matching background + logo + overlays per layout; only load the current layout's heavy
  art (§8). `100dvh`, `env(safe-area-inset-*)` padding on mobile; menu in lower-middle safe band.
- Title menu: horizontal-ish lower-center on desktop, vertical stack on mobile.
- Mode: posters side-by-side (desktop) vs one-at-a-time scroll-snap carousel (mobile).
- Creator: body centered in the beam, controls in a right panel (desktop) / bottom sheet (mobile);
  full body stays visible when the sheet is collapsed.

## 5. Animation strategy

- **One rAF loop** (`useTitleAnimation`) driving transforms via refs/CSS vars — **no per-frame React
  state**. Time-based (`performance.now`), so it's frame-rate independent.
- Layer motions (all subtle): background slow push toward the vanishing point; god-rays opacity
  breathe; haze crawl; gold dust upward drift w/ per-particle speed variance (CSS keyframes with
  varied durations, or transform on the whole layer); soul sparks rare; road glow subtle toward
  viewer; neon flicker irregular; logo restrained glow.
- **Intro:** fade from black → bg slightly scaled-in settling → logo fades+rises → buttons stagger in.
- **Pause** the loop on `document.hidden`.
- **`prefers-reduced-motion`:** disable camera zoom + road motion, reduce/stop particles, keep only
  brief fades. Fully complete visually.

## 6. Asset-loading strategy

- Title: load only the active layout's bg + overlays; the logo eagerly. Defer mode posters +
  body bases (preload posters once the title is interactive; preload the selected body pair on
  entering the creator). Show the cleaned `loading-sigil` (rotating, from `spinner.png`) while creator
  assets prepare.
- Opaque bgs → WebP; transparent line art (logo/frame/rays) → RGBA PNG (never JPEG). Tight-crop
  transparent canvases. Reserve box sizes to avoid layout shift.

## 7. Character-base manifest strategy

Data-driven, discovered from the actual keyed files — **no hard-coded paths in components**.

```ts
type Skin = "light" | "medium" | "deep";
type Build = "petite"|"slim"|"average"|"athletic"|"curvy"|"plus";
interface BaseOption { build: Build; skin: Skin; label: string;
  front: string; back: string; thumb: string; available: boolean; }
export const BODY_BASES: BaseOption[]  // built from characters/base/, missing pairs → available:false
```

Extensible: face/hair/clothing/morph fields append later without rewriting the creator. A build×skin
whose front or back is absent is included but `available:false` (disabled in UI); Randomize/Reset
only pick `available` options. Default = `average·medium`.

## 8. Accessibility

- All actions are real `<button>`/semantic controls; visible focus rings; disabled states correct.
- Posters wrapped in `<button>` with `aria-label` = the code label + description (never the baked
  text). Keyboard-selectable; screen-reader announces mode name + description.
- Skin swatches carry text labels (Light/Medium/Deep) — never color-only.
- Settings & any modal: focus-trapped, Esc closes, restores focus.
- Honor `prefers-reduced-motion`; sufficient contrast; ≥44px touch targets.

## 9. Verification procedure

- `npm run build` (tsc -b + vite) + `npm run lint` (tsc --noEmit) clean.
- Existing Hollywood scene still mounts/plays (drive Lori) — no regression.
- Playwright screen-grabs at desktop 1920×1080 / 1440×900 / 1280×720 and mobile 390×844 / 430×932 /
  small; check logo size, safe areas, card readability, focal points, body head+feet visible,
  bottom-sheet, notch spacing.
- Assert: no checkerboard in any production asset; no magenta fringe on bodies (inspect on black AND
  light); front/back pairs align; Continue not falsely enabled; New Game→mode; both modes→creator;
  mode persists; build/skin/toggle/randomize/reset/name-validate/confirm-draft all work;
  reduced-motion behaves; keyboard + touch work.

## 10. Build order (checkpointed)

1. **Asset pipeline** — move raws to `source/`; key the baked ones (logo, frame, rays, haze, road,
   bodies); convert opaque→WebP; crop the mark; split the two combined petite sheets. Verify on
   black + light. *(No app code yet.)*
2. **Shell + navigation** — `FrontEnd` screen machine, transitions, draft persistence; `App` hosts it;
   game path preserved.
3. **Title screen** — layer stack + rAF animation + menu + settings modal (desktop + mobile).
4. **Mode select** — bg + posters + selection + descriptions + Back/Continue (carousel on mobile).
5. **Creator** — stage + body manifest + build/skin/front-back/zoom/reset/randomize/name/confirm.
6. **Verify + screenshots + commit** each step.

## 11. Phase boundary

Ships: animated title, working menu, mode select, responsive creator stage, female body-base
discovery+cleanup, build/skin select, front/back, zoom, reset, randomize, name, confirm+draft.
**Does NOT ship** (architected-for, not built): morph/face/expand-contract/mesh/liquify/rig/
clothing-deform/face-overlays/hair/tattoo/makeup/DNA/procedural-NPC/advanced-saves.
