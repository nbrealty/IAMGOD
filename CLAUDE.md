# I AM GOD — project notes for Claude

God-game in a fictionalized 2026 Los Angeles (Hollywood Blvd district).
Targets: iOS App Store, Windows, Mac. Vite + React 19 + TypeScript, a canvas 2D
billboard/dimetric renderer with a pan/zoom/DPR camera.

## Character art style — "chibi-realism" (the house look for all souls)

Every character sprite (playable soul, NPC, friend cameo) is drawn in one house
style we call **chibi-realism**: a caricatured chibi head/proportion on a fully
realistic, detailed body. It is NOT flat pixel-art and NOT baby-proportioned
classic chibi — it's a premium caricature / high-end sticker-avatar look. When
you write an art prompt or judge a delivered sprite, hold it to these traits:

- **Proportion (semi-chibi caricature).** An oversized head with a big expressive
  face on a body that is roughly **3.5–4.5 heads tall** — shorter and heads-bigger
  than real life, but clearly an adult, never a toddler-proportioned mini. Head is
  ~¼–⅓ of total height, not the tiny 1/3-head classic chibi.
- **Body = realism.** Full, truthful adult anatomy rendered with real volume —
  visible muscle (quads, calves, abs, biceps), real curves and build, correct
  hands and feet. The person's actual build/weight is honored, not slimmed or
  idealized.
- **Face = caricature-realism.** Enlarged, detailed eyes with painted irises,
  catchlights and long lashes; strong groomed brows; full realistic lips; a real
  nose/jaw; contouring, blush, freckles, moles. Very expressive and warm, usually
  a slight confident smile. The face must stay a **true likeness** of the source
  person — keep face shape, features, hair, skin tone, glasses/facial hair/tattoos.
- **Line & color.** Bold, clean **black ink outlines** (heavy outer contour, finer
  interior lines) over rich **glossy cel-shading blended with airbrushed gradient
  volume** — not flat fills. High saturation, high contrast, punchy; specular
  highlights on skin, hair sheen, fabric gloss.
- **Material detail.** Photoreal textures — denim rips, leather sheen, knit ribbing,
  jersey fabric, studs, chains, jewelry, watches; **legible logos/crests/tattoos**
  (e.g. a CBF crest, a Nike swoosh, "Los Angeles" script, rose/palm tattoos).
- **Framing.** A single full-body figure, standing, **feet planted, front-facing
  near eye-level (straight-on)**, centered with a small even margin. (Note this is
  straight-on, flatter than the older cast's raised 3/4 dimetric angle — chibi-
  realism is the current, definitive look; the reference set lives in
  `/root/.claude/uploads` and characters like the Brazilian tank-top/shorts woman,
  the soccer-jersey man, the rock-tee woman, the detective, and the Oxum figure.)
- **Lighting.** Bright, even, gently top-lit; strong rounded form shadows plus
  glossy highlights; **no cast ground shadow** (grounding is added by the engine).
- **Background / keying.** Delivered on a **flat solid hot-magenta** key field (or
  transparent) so the pipeline can crop cleanly; grounded American streetwear,
  **no anime tropes** (no sparkle-eyes, no twin-tails, no unnatural hair unless the
  real person dyes theirs).

`docs/CHARACTER_PROMPT.md` holds the paste-ready, reusable prompt (with WEARING /
POSE / NAME slots + a back-view companion) built from these traits — use it for
every new likeness sprite. Save keyed finals to `public/spirits/` per the outfits
spec below.

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

   **Grounding (anti-sticker).** Every ground-standing object draws its own
   `multiply` contact shadow at its foot-Y **inside its own draw, just before the
   sprite** (`drawContactShadow` in `renderer.ts`) so the shadow sorts with the
   actor and lands on the ground it stands on — never as a separate pass.
   Buildings also get a base-skirt gradient (wall foot sinks into the pavement)
   and the far/north row gets a light `multiply` haze veil so it recedes. A
   final **screen-space** grade + vignette (`drawPostGrade`, reset to the
   identity transform first) unifies every asset under one exposure.

3. **Every character has a front and a back.** Show the back sprite only when
   the character is moving up/away from the camera; otherwise show the front
   (front mirrored L/R is fine for sideways travel). Ambient peds walk
   horizontally, so they use the front set (see `PED_FRONT` in `renderer.ts`) —
   which lists only the front-facing pool indices; a back view left in that list
   shows as someone permanently walking away.

6. **Every character faces its horizontal travel direction.** Walking left shows
   the left-facing orientation, walking right the right-facing — the renderer
   horizontally mirrors the single front sprite based on travel (`facingLeft`
   for the controlled soul, `dir` for everyone else). The base convention is
   *art faces right when unflipped*; any sprite whose art's native lean already
   faces **left** must be listed in `SPRITE_FACES_LEFT` (renderer.ts) so the flip
   stays correct (e.g. `nathaniel`/Sorriso, `elizabeth`). When you add a
   character, drive them left and right once and, if they face against travel,
   add their soul id to that set. (These are front billboards, so this is a
   mirror, not a true side-profile turn — a real profile would need new art.)

   **Back sprites are never mirrored.** The `${stem}_back` art is authored facing
   away, so the horizontal travel-mirror (and `SPRITE_FACES_LEFT`) must NOT apply
   to it — mirroring a back view inverts any text/number/logo on it (a "SORRISO 10"
   jersey would read backwards). In `drawNPC`, `usingBack` forces `flip = false`.
   Only the **front** billboard mirrors by travel.

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

   **The walk FX is gated ONLY on `moving`, NEVER on being selected.** It fires
   for a character whether the player is driving them or they're wandering
   autonomously as an unselected NPC — the controlled soul and every other soul
   run the *same* `if (s.moving) { drawWalkFX(); drawLegBlur(); }` in `drawNPC`.
   **`moving` MUST track real per-frame displacement, not the activity flag.**
   Autonomous souls stroll their `xMin`→`xMax` patrol at `baseSpeed`, and the
   update loop sets `s.moving = Math.abs(dx) > 0`. (The original code drifted
   "stationary"-activity souls at 0.2× while hard-setting `moving = false`, so
   they GLIDED with no FX — the "not firing on auto walk" bug. The leg-blur swing
   is time-based, so a soul must translate at a real walking pace or a slow drift
   moonwalks — do not reintroduce a sub-walking-pace drift.) So the rule for a
   NEW playable/NPC character is: **do nothing** — dropping its sprite in and
   adding the soul is enough; it strolls and blurs, selected or not. Never gate
   the walk FX on selection, and never derive `moving` from anything but actual
   movement. When you add a character, verify in observe mode that the leg-blur +
   smoke show while they walk unselected.

7. **Overture is a WALK-IN court — PARALLEL / axonometric, NEVER a fake vanishing point.**
   `OVERTURE` (sceneData.ts) pins a monumental gate on block-2 north (Overture is
   removed from the auto-layout; the block's other 3 landmarks start east of the
   gate). Behind the gate is an open-air courtyard modelled on the real Babylon
   Court (Ovation Hollywood): elephant-column gateposts, palm rows, a fountain,
   shop terraces + a back building. You walk in through the gate's TRUE open arch —
   no loading.
   - **The X-funnel lesson (do NOT relearn it).** An earlier build faked a 1-point
     vanishing point — court actors scaled about a pivot `(cx, vpY)` by a
     `courtScale(footY)`, plus baked-perspective side-wall billboards riding a
     receding trapezoid floor. In a flat dimetric billboard scene that makes the two
     side walls converge to a pinched **"X" funnel** — ugly, and it fought the one
     projection rule the whole game obeys (parallel-in, constant actor size). Research
     across isometric city-builders + Gaia Online (single painted plate per zone,
     billboard avatars, z-order, one committed angle, never "all sides", never real
     3D) all say the same thing: **keep it parallel, bake the depth into the art.**
   - **Walkability is flat WORLD space.** `canWalk` opens a keyhole: a narrow arch
     *throat* (only under the arch opening, so the solid gate wings can't be walked
     through) widening into the *court pocket*. Unchanged — this was never the problem.
   - **Floor = a symmetric RECTANGLE** (`drawOvertureFloor`): constant `courtHalf`
     at both `gateFootY` and `courtBackY`, so the side rails are parallel and a funnel
     is geometrically impossible. One baked non-repeating plate
     (`overture-court-floor.png`) drawn with a single `drawImage` (a warm fill stands
     in until it decodes — never a repeating tile grid).
   - **Fountain + palms are plain foot-Y props** (constant size) in the seamless
     approach court — the player walks past them, so they y-sort/occlude for real.
   - The **gate + elephant columns** stay full-size foot-Y actors at `gateFootY`, so
     walking north (foot-Y < 1000) sorts the player BEHIND the gate → framed through
     the arch. The follow-camera tracks the player's true `x/y` (no projection branch).
   - **Never reintroduce** `courtScale` / `projCourt` / a `court` actor flag / a
     scale-about-pivot wrap / a trapezoid floor. If a future space needs more
     enclosure, bake a single-angle plate (Gaia-style) — do not compute a VP.

   **7b. Enterable spaces are Gaia-style SCENE-SWAP ROOMS (`renderArea` / `AREAS`).**
   The detailed court interior is NOT drawn in the overworld — it's a room you crossfade
   into. Walk deep enough up the court (`pc.y < COURT_ENTER_Y` on the axis) and
   `startTransition("overture-court")` runs a fade-through-black; at the mid-fade
   `doRoomSwap` stashes the world position + camera and sets `this.room`. `render()` then
   dispatches to `renderArea`. Rooms live in an `AREAS` registry: each area DECLARES its
   `view` (`'topdown'` city vs `'headon'` elevated), backdrop plate, floor band, and optional
   `sky` — so adding a rooftop/interior is DATA, not new render code. The plate is shown
   through the **same clamped camera as the city** (world = the plate's pixels via
   `worldDims()`), so a room **pans + zooms and NEVER reveals an edge** (min-zoom = cover;
   position clamped) — never contain-fit/letterbox, which showed borders. The avatar walks the
   painted floor as a **normal foot-Y billboard** (mild depth-scale by `y`), reusing contact
   shadow / walk FX / leg-blur / front-back **verbatim**. Movement is bounded to a floor
   trapezoid (`roomCanWalk`); walking down off the front edge exits. **Head-on areas draw a
   procedural time-of-day SKY** (`drawAreaSky`: zenith→horizon gradient + sun/moon disc-or-sprite
   + stars + golden wash, all keyed to the clock) behind the plate, seen through the plate's
   transparent top, plus an optional baked skyline (`skyline-silhouette` + emissive
   `skyline-windows`, feathered base tucked behind the buildings). A night additive re-composite
   of the plate makes its lit windows/signage glow. `setControlled` drops any active room. This
   is the generic mechanism for ALL future enterable buildings — add an `AREAS` entry + one plate.

   **RULE — every enterable area ALWAYS shows an on-screen "← Leave" button.** Walking to an edge /
   tapping the exact exit is too fiddly on touch, so the guaranteed way out is a button. It's wired
   generically: the renderer calls `onRoomChange(room)` (set via `setRoomHandler`) on every room
   swap; `HollywoodScene` shows the `.leave-room-btn` whenever `room !== null`; tapping it calls
   `renderer.leaveRoom()`, which transitions along the area's `exitTo` (room→room steps out one
   level, e.g. back consultation → botanica → street). The button uses `onPointerUp` (not `onClick`,
   which some mobile PWA webviews drop) and `leaveRoom()` cancels any half-finished transition
   first. Any new `AREAS` entry inherits the button for free — never ship an enterable area without
   a working Leave, and never gate the only exit behind a walk-to-edge trigger.

   **7c. Room human scale — people are sized to the PAINTED FURNITURE, not the overworld.** A room
   plate is a small interior; the overworld `CHAR_BODY_H` is a fraction of it, so an un-scaled avatar
   renders child-sized. Each `AREAS` entry sets `charScale` (multiplier on `CHAR_BODY_H`, applied to
   the avatar AND static `occupants`) calibrated to the art: an adult is ≈0.8×door / ≈2×chair-back /
   ≈1.8×counter height (research-backed). **Counter rooms obey the COUNTER RULE: the counter line
   must meet a person at the WAIST (at least)** — anything higher reads as a child at an adult
   counter. A keeper stands BEHIND the counter via a `foreground` overlay plate (the counter band,
   transparent above it, drawn in front of `occupants` but behind the player) so the counter hides
   their legs and the waist-on-counter proportion reads for free; the player stands in front. Size a
   new room by measuring its door/chair/counter in the plate and setting `charScale` so the rule holds.

## Asset pipeline

- Raw magenta/white-keyed source art lives in `art-src/` (NOT shipped).
- `public/` copies verbatim into the app bundle — only keyed/cropped finals go
  there (`tiles/`, `vehicles/`, `props/`, `npc/`, `spirits/`).
- Keying: flood-fill the key color from the image borders; slice multi-item
  sheets by connected-component blob detection + bbox merge (avoid grid-splits
  that leave neighbor bleed).
- **Tile separators** (`public/tiles/sep-*.png`) are hand-painted ground-boundary
  art, NOT code-drawn curbs. Straight strips (`sep-road`/`sep-grass`/`sep-joint`)
  are baked from the source curb strips with the outer edges feathered to alpha,
  then tiled along each seam by `drawSeparator` (horizontal) / `drawSeparatorV`
  (vertical, one quarter-turn) with the art's **measured curb fraction** pinned to
  the world seam Y/X (road curb-only strip 0.625; grass curb+fringe strip 0.654 —
  NOT the band centre), so the straight curb lands exactly where a corner's curb
  does. The **grass** strip keeps only the curb + a thin blade fringe (its far
  grass cropped off and the fringe **tone-matched to `grass.jpg`** and ramped to
  alpha 0), so the bleed dissolves into the lawn as a soft rounded fringe instead
  of a wide band whose square inner corner tone-stepped against the world grass.
  A flip serves both
  orientations; each horizontal curb skips only the surfaces that make it a
  non-curb there (ROAD_TOP skips just the cross-street road ±CS_ROAD_HALF, the
  sidewalk↔sidewalk/backlot curbs skip ±CS_HALF). **Corners are STROKED from the
  same strip** (`bake_stroke.js` sweeps the strip along a rounded-L path →
  `sep-corner-road` convex, `sep-corner-grass` concave), so the corner curb is
  byte-identical to the straight curb — its arms overlap the straights seamlessly
  (no doubled line), and being a thin band it can't print a picture-frame halo.
  The curb art is stone BLOCKS with dark mortar joints and a ragged, bright-rimmed
  painted edge; three bake passes keep the built edge CLEAN (the recurring "stuff
  coming out of the edge"): (a) the corner strokes a **joint-free window** of the
  strip (shorter than one block) so the arc is one smooth continuous curb, no
  joints; (b) a **clean-edge mask** (`bake_stroke` cleanOut/cleanIn) — one filled
  path (offset concentric arc + straight arms, NOT swept rects, which would scallop
  the convex side) — trims the bumpy hand-painted silhouette to a smooth curve on
  the outer (sidewalk/road) side; grass keeps its inner (blade)
  side loose; the straight strips get the matching top/edge trim (`trim_straight`);
  (c) `clean_edges` caps the luminance of the semi-transparent feather so the edge
  blends into the sidewalk instead of glowing as a bright scalloped lace.
  `drawCornerTile` pins the baked elbow fraction to the junction and mirrors to
  all four rotations; all four road corners exist (the cross-street sidewalk runs
  both N and S of the boulevard). Code-drawn `drawCurb`/`drawExpansionJoint`
  remain only as the far-zoom / not-yet-decoded fallback. **Edge the built.**
- **CORNERS — the invariant (do not relearn this the hard way).** A rounded curb
  corner only rounds the CURB. Everything else must already be round or stop short,
  or it "sticks out" past the arc. Checklist for every corner (road + grass):
  1. **Nothing layered underneath may reach the elbow.** Each straight curb stops
     ~one corner arc-radius short of the elbow (`RCUT`/`GCUT` in the skip windows +
     the vertical `mouth`/`grassOnly` skips + the `drawSeparatorSpanH` spans), so the
     two straights never meet in a SQUARE vertex that pokes past the arc. The corner
     asset alone fills the junction.
  2. **The surface FILL must not bleed past the curb onto the neighbour.** Fills are
     rectangles with square corners; the curb rounds the line, not the fill. Round
     the fill's corner too — `drawCornerNooks` fills asphalt into the nook between the
     terrazzo's square corner and the curb arc (evenodd clip: corner square MINUS the
     arc disc) so the sidewalk can't bleed onto the street. Grass is concave (sidewalk
     wraps it) so its fill can't poke out; the blades overhanging the curb are wanted.
  3. **The corner sprite's own edge must be smooth** (see the bake passes above:
     joint-free window, offset-arc clean mask, feather de-glow) — never swept rects.
  4. **No stray markings at the seam.** The road has no painted edge-line; the curb
     IS the road edge. (Don't reintroduce a `#c9c4b6` stroke at `ROAD_TOP/BOTTOM`.)
  Verify at high zoom, day: smooth arc, no square vertex, no fill bleeding across, no
  white line, no gap where a straight meets the corner arm.
- **New ped uploads must be classified front vs back.** The `public/npc/` pool
  mixes both; only face-visible FRONT sprites go in `PED_FRONT` (renderer.ts) —
  a back-view left in that list walks the sidewalk permanently facing away.
  Verify by eye at large size (render each candidate ~500px and confirm a face
  is visible — small montages hide backwards caps/hoods; this has bitten us
  repeatedly). Back sprites stay in the pool for future toward/away wanderers.
- **Outfits / wardrobe (inventory).** A soul can own several looks. Drop the
  keyed art in `public/spirits/` as `<stem>.png` (+ optional `<stem>_back.png`)
  and add an entry to `OUTFITS` in `src/game/outfits.ts` (first entry = the
  default, its stem = the soul id). The inventory grid and the live sprite swap
  are automatic — no renderer changes. `spriteBounds`/leg-blur/back-facing all
  key off the active stem, so a new outfit inherits uniform height + walk FX.
- **Inventory.** Every soul (playable + NPC) has a fixed `INVENTORY_SLOTS` (20)
  grid — `src/game/inventory.ts` derives it from `OUTFITS` (owned outfits first,
  then empty). The reusable `InventoryGrid` (tap-to-equip, worn highlight, dim
  empty slots) is shown for the controlled character via the 🎒 button and
  inside every soul's Soul Profile panel, so any NPC can be dressed too. Equip
  state lives in `HollywoodScene` (`equipped: soulId→stem`) and is pushed to the
  renderer with `setOutfit`. New item kinds beyond outfits slot in here later.

## Verification

Build clean with `npx tsc --noEmit` + `npm run build`. Visual checks via
`npm run preview -- --port 4178 --host 127.0.0.1` + Playwright using the
`window.__engine` debug handle (`.speed=0/1/2/3`, `.clockMinutes=X`); drive the
controlled character by clicking a roster button and pressing arrow keys.

## Working agreement

- Commit + push only to `claude/game-idea-research-qgba5p`. No PRs unless asked.
