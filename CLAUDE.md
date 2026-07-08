# I AM GOD — project notes for Claude

God-game in a fictionalized 2026 Los Angeles (Hollywood Blvd district).
Targets: iOS App Store, Windows, Mac. Vite + React 19 + TypeScript, a canvas 2D
billboard/dimetric renderer with a pan/zoom/DPR camera.

## Rendering rules (must honor — regressions here are visible bugs)

The world is a flat billboard scene faked into 2.5D. The projection rule is:
**larger foot-Y = nearer the camera = drawn later / on top.** Every actor is
feet-anchored to one ground-Y, which is the sort key.

1. **Depth = y-sort by feet.** All upright, ground-standing art (buildings,
   cars, lamps, props/palms, pedestrians, souls) renders through the single
   y-sorted actor pass in `render()`: collect `{ y: footY, draw() }`, sort
   ascending, draw far→near. Ground surfaces (tiles, sidewalks, road,
   crosswalks, aprons) are a flat pre-pass beneath all actors; the ambient
   grade / golden-hour / lights are a post-pass on top. **Never add a new
   fixed per-type draw pass** for ground-standing art — add to the sorted list
   instead, or occlusion breaks (characters pass in front of lamps they should
   be behind, cars get clipped, etc.).

2. **No code-drawn placeholders where a real asset exists.** If an asset is
   present in `public/`, wire it in; don't leave the old coded fallback box
   showing. Fallbacks may only appear while a sprite is still decoding, and
   should be neutral, not a dark box.

3. **Every character has a front and a back.** Show the back sprite only when
   the character is moving up/away from the camera; otherwise show the front
   (front mirrored L/R is fine for sideways travel). Ambient peds walk
   horizontally, so they use the front set (see `PED_FRONT` in `renderer.ts`) —
   which lists only the front-facing pool indices; a back view left in that list
   shows as someone permanently walking away.

5. **Uniform character height.** Every character (named soul + ambient ped)
   renders at one shared body height (`CHAR_BODY_H`), feet planted. Source art
   carries different amounts of empty frame and comes in different styles (the
   chibi souls fill ~91% of frame, the pixel-art souls and peds ~100%), so we
   never draw the raw frame at a fixed height — `spriteBounds()` measures each
   sprite's non-transparent extent once and we scale the *content* to the target
   and anchor the content-bottom at `y + FEET_DROP`.

4. **Every moving character gets the walk FX — smoke + pendulum leg-blur.**
   Named cast and ambient crowd both call, when moving, the shared
   `drawWalkFX()` (a darker contact crescent, trailing ground smears, and soft
   smoke puffs that trail back and fade — time-tinted cooler/bluer at night,
   warmer at golden hour) **and** `drawLegBlur()` — the Gaia-style walk: the
   crisp body stays a static billboard while the legs (bottom ~36% of the
   sprite) shear from the hip and **swing left↔right like a pendulum**, drawn as
   a fan of fading copies with the bright copy tracking the current swing.
   Because it's sliced from the sprite at runtime, **any new character (soul or
   ped) gets the leg-blur automatically** — no per-character art or wiring. Give
   each mover a distinct `phase` so a crowd doesn't swing in sync.

## Asset pipeline

- Raw magenta/white-keyed source art lives in `art-src/` (NOT shipped).
- `public/` copies verbatim into the app bundle — only keyed/cropped finals go
  there (`tiles/`, `vehicles/`, `props/`, `npc/`, `spirits/`).
- Keying: flood-fill the key color from the image borders; slice multi-item
  sheets by connected-component blob detection + bbox merge (avoid grid-splits
  that leave neighbor bleed).
- **New ped uploads must be classified front vs back.** The `public/npc/` pool
  mixes both; only face-visible FRONT sprites go in `PED_FRONT` (renderer.ts) —
  a back-view left in that list walks the sidewalk permanently facing away.
  Verify by eye at large size (render each candidate ~500px and confirm a face
  is visible — small montages hide backwards caps/hoods; this has bitten us
  repeatedly). Back sprites stay in the pool for future toward/away wanderers.

## Verification

Build clean with `npx tsc --noEmit` + `npm run build`. Visual checks via
`npm run preview -- --port 4178 --host 127.0.0.1` + Playwright using the
`window.__engine` debug handle (`.speed=0/1/2/3`, `.clockMinutes=X`); drive the
controlled character by clicking a roster button and pressing arrow keys.

## Working agreement

- Commit + push only to `claude/game-idea-research-qgba5p`. No PRs unless asked.
