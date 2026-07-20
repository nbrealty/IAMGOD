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
   Buildings, props, AND characters/peds (`drawNPC`, `drawPed`) ALSO draw a
   **directional time-of-day CAST shadow** (`drawCastShadow`): the sprite's OWN
   silhouette (baked cool-dark + soft-edged, `spriteSilhouette`), flattened forward
   onto the ground and skewed away from a single global sun
   (`sunShadowAt(clockMinutes)`) — and **never flipped with the sprite** (a shadow
   follows the light, not the character's facing). It **swings + lengthens with the
   clock** — short & straight at solar noon, long & leaning one way in the morning,
   long & leaning the other at golden hour, and **gone at night** (signage light
   takes over). Everything that carries the real cast shadow uses the **seam-only**
   contact shadow (`drawContactShadow(..., seamOnly=true)`) so the two directional
   cues don't fight; characters keep their moving walk FX (crescent + smoke +
   leg-blur) on top. Room interiors have no sun, so they keep their plain soft
   contact shadow (no cast shadow indoors).
   **NEVER re-add axis-aligned box overlays** (the old base-skirt / inter-building
   AO / far-row haze `fillRect`s) — they printed onto the ground/neighbour through
   the sprites' transparent padding as vertical "black streaks." All grounding must
   be **silhouette- or ellipse-shaped**, never a rectangle keyed to the sprite's
   bounding box. A final **screen-space** grade + vignette (`drawPostGrade`, reset
   to the identity transform first) unifies every asset under one exposure.

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

   **7d. A seated/posed host is BAKED INTO the plate, never a sprite — and a sprite can't go behind
   baked furniture.** The room's furniture (table, counter, altar) lives in the backdrop plate, which
   draws first; every character composites ON TOP via the foot-Y sort, so a sprite can never render
   *behind* a painted table (its legs can't tuck under). For a static host who sits AT a table (Yara
   at her búzios reading table, `aguas-back`), paint her into the plate — the art sizes her to the
   furniture and hides her legs under the table for free. Then calibrate the *player's* `charScale`
   so the incoming avatar reads at the baked host's scale (an adult standing at the empty chair: head
   above the chair back, head ≈ the baked host's head), NOT child-sized. The alternative to baking
   (keep her a sprite) is a `foreground` table-skirt overlay like the counter — fiddlier to cut
   cleanly from a draped round table, so prefer baking for a static host.

   **7e. The reading is a paid front-desk transaction, and the baked host only appears once it's
   paid for.** `aguas-back` has TWO plates: `backdrop` = the EMPTY room (open chairs), and
   `readingBackdrop` = the SAME room with Yara baked in. The state is `readingActive` (set by
   `beginReading()` when the player accepts + pays at the front desk — the `YaraFrontDesk` panel,
   opened by the "🔮 Speak with Yara" button in `aguas-front`; cleared when they leave the botanica
   for the street, and on character-switch). `renderArea` picks `readingBackdrop` when `readingActive`,
   else the empty plate — so **wandering into the back without paying shows an empty room**, and the
   host materialises only for a paid reading. `readingActive` also hides her front-counter `occupant`
   (anti-double-presence — she "went to the back"), and on accept plays a one-time "walk to the back"
   beat (`yaraWalkT`: her counter sprite slides toward the beaded curtain and fades through it). React
   mirrors `readingActive` via `setReadingHandler` to swap the "Speak with Yara" / "Sit for your
   reading" buttons; the "Sit" button (gated `!casted`, one cast per payment) opens the POV cast.

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

---

# Narrative design & worldbuilding — STORY CONTEXT ONLY (do NOT implement)

> This is a **context sync**, not a build order. It supplements (does not replace) the external
> *I Am God Novela Storytelling Master Document*. **No code, gameplay systems, scenes, missions,
> assets, DB schemas, or production work** may begin from anything here until Nelson explicitly
> asks. Provisional ideas are NOT final canon. Later revelations should **reclassify** earlier
> behavior, not erase it. Status tags used below: **[CANON]** locked / **[DIR]** strong working
> direction / **[PROV]** provisional possibility / **[RESEARCH]** needs historical or cultural
> consultation before use.

## N1. Novela storytelling — character reclassification
- **[CANON] The core reveal is "true but incomplete," not "everything was false."** Establish a
  clear role (protector, father, healer, lawgiver, loyal servant, leader, guide, victim,
  benefactor, con artist, sacrifice sovereign), show the character succeeding at it and others
  depending on it — then introduce ONE person/fact/object/obligation/history that attacks the
  *center* of that identity. It opens a hidden room; it does not delete the genuine role.
  Model: **Juvenal Antena** (*Duas Caras*) — feared protector/symbolic father of Portelinha; a
  teenage girl arrives: "I'm your daughter." The reveal hits the exact role he's known by. His
  real protection of the neighborhood stays true *and* he failed as a literal father.
- **[DIR] Identity-Targeted Reveal (for supporting cast, villains, selected entities):**
  1) establish accepted identity → 2) show them performing it → 3) make others depend on it →
  4) plant small sealed-off contradictions → 5) introduce the identity challenger →
  6) give the challenger a one-sentence "detonation" that opens the hidden room →
  7) force old + current identity into the same social world → 8) reveal the pressure truth via
  their response → 9) spread consequences through family/allies/enemies/reputation/institutions/
  neighborhoods/supernatural ties.
  Example detonation lines (one sentence, understandable immediately; consequences span chapters):
  "I'm your daughter." / "You knew where I was." / "You broke the first law." / "That building
  belongs to me." / "Your husband didn't save you. I did." / "The man you buried is alive." /
  "You didn't found this neighborhood. You stole it." / "You asked them to forget me." /
  "You were the offering." / "I remember you from before you changed your face."
- **[DIR] New character-design field — Identity Challenger.** Every major supporting character,
  villain, and major entity should eventually consider: accepted identity · public role ·
  human/supernatural dependence on that role · private contradiction · buried origin · identity
  challenger · why the challenger has authority · one-sentence detonation · prepared denial ·
  the audience before whom it's most devastating · pressure response · uneven judgment afterward ·
  persistent consequences.
- **[CANON] Main vs supporting.** Protagonists are understood by *accumulation* — "what will this
  person become?" (the player lives inside their choices). Supporting characters / villains /
  entities are more often understood by a strong role then reclassified — "who have they already
  been this whole time?" Not absolute, but it guides structure.
- **[DIR] Entity version of the hidden-room reveal — attack the entity's DOMAIN, not a random
  scandal.** A protector confronted by someone they knowingly failed to protect; a lawgiver by the
  law they broke; a healer by someone harmed by their cure; a memory entity by someone it ordered
  forgotten; a "loyal" angel revealed to have enabled the rebellion; a sacrifice sovereign revealed
  to have once *been* the sacrifice; a tester shown the test was never fair. The entity stays truly
  bound to its domain; the reveal complicates the domain's meaning, it doesn't replace it.

## N2. Lucifer as an occasional reveal mechanism
- **[CANON] Lucifer may sometimes hand someone the KEY to another character's hidden room and make
  sure the important people are watching when it opens — he does NOT manufacture the room.** The
  character created their own secret/failure/betrayal/contradiction. Lucifer is NOT the source of
  every secret, not behind every betrayal, not secretly controlling all human choices, not a
  substitute for human responsibility, not the writer in disguise.
- He *may*: introduce the returning person, provide an address, deliver evidence, secure an
  invitation, arrange timing, ensure the reveal lands before the most damaging audience, give a
  victim courage/resources, collide two sealed social worlds. Use when the revelation also works as
  a **philosophical test** (will the leader acknowledge the one they failed? will God reveal a truth
  knowing innocents may suffer? will the community still protect a useful leader? justice vs revenge
  vs humiliation vs belonging vs money? will God intervene or preserve free will?).
  Sample tones: "You're looking for your father? I believe he'll be speaking tonight." /
  "You wanted the truth. I never promised it would make anyone love you." / "One seat opened at the
  wedding. It seemed wasteful to leave it empty."
- **[DIR]** Characters/players should *sometimes* suspect Lucifer arranged an event when he didn't —
  paranoia is part of his influence. But keep clues fair: **not** every coincidence, stranger,
  helper, or reveal is Lucifer.

## N3. Subconscious story bridges & fair misdirection
- **[DIR]** Editing can imply relationships/futures that aren't (yet) true. *Duas Caras* example:
  Dona Branca curses her betrayer and vows to find a better man → hard cut to Ferraço (a known con
  artist) reading a paper → the juxtaposition plants "she may end up with him — terrible," though
  nothing was stated. Use as a **Subconscious Story Bridge** (desire→the person who'd fulfill/destroy
  it; threat→a plausible victim; prayer→an entity; a symbol/song/object/location across two worlds;
  a reaction shot inviting an inference of guilt or romance).
- **[CANON] Distinguish three modes: real foreshadowing / ambiguous implication / deliberate
  misdirection.** Misdirection is allowed and desirable **when fair** — you may lead the audience to
  a wrong conclusion, but must never later pretend explicit evidence said something it didn't.
  Principle: **sneaky, not fraudulent.**

## N4. Samson storytelling lessons (principles, not plot to copy)
- **[DIR] God begins big changes in hidden/dismissed places** — the recurring "impossible womb"
  pattern (Sarah/Isaac, Rebekah/Jacob, Rachel/Joseph, Hannah/Samuel, Manoah's wife/Samson,
  Elizabeth/John, Mary/Jesus). When God means to change a civilization, the first sign appears inside
  a life that civilization already dismissed — private grief, infertility, an overlooked/older/
  powerless woman, a helpless child. The answer exists before the world recognizes it. **This shapes
  the Create-a-Character intro.**
- **[DIR] A character may misunderstand the source of their own power.** Samson's strength was the
  sign of consecration; the real source was God. Violating parts of the vow without losing power
  taught him the wrong lesson ("the strength is mine"). He mistook a **gift for a possession**. For
  I Am God: a character may know they have a gift without knowing its source; confuse access with
  ownership; have success reinforce spiritual ignorance; keep power while abusing it; and lose it
  "suddenly" only because they never saw the sustaining relationship.
- **[CANON] Divine purpose does not erase human responsibility.** God may work *through* a flawed
  decision without making it good. A bad choice can advance a larger purpose; a compassionate choice
  can cause harm. The player must **never** excuse harmful conduct with "it advanced the plan."
- **[DIR] "The gift is enormous, the aim is tiny."** Cosmic power ≠ cosmic perspective; the player
  may spend divine power on romance, jealousy, reputation, revenge, status, private loyalty,
  humiliation, winning an argument, protecting one at the expense of many.
- **[DIR] Recurring symbols evolve in MEANING, not just foreshadow.** Samson's fire (holy offering →
  weapon → uncontrolled destruction → himself as wildfire); eyes (choosing what pleases him →
  appetite/impulse → taken from him); betrayal (spouse → community → nation → his own calling).
  For I Am God: Lucifer's open hand (guidance/rescue/bargain/invitation/judgment); Molache's offering
  (generosity → obligation → coercion → sacrifice); a hospital heartbeat (medical data → evidence of
  incarnation); fire (purification/ambition/spectacle/destruction/rebirth); a gold coin (harmless
  eccentricity → evidence of Lucifer).
- **[DIR] Oppressed people may resist rescue** because they've adapted to the oppressive system —
  Judges: the people hand the deliverer to the oppressor to keep their fragile peace ("do you not
  understand that the Philistines rule over us?"). **Critical for LA under Molache:** artists depend
  on predatory studios; employees on exploitative bosses; neighborhoods on corrupt patrons; victims
  on offenders' reputations; politicians on compromised donors; spiritual communities on corrupted
  protection; families fear truth will end their livelihood; people born under the system can't
  imagine outside it. Molache's greatest protection may be **everyone who adapted to his rule.**
  Confrontation seed: "Do you understand what will happen to us if you expose him?"
- **[DIR] True use of power may require surrender/dependence.** Samson's final act works only once he
  stops assuming strength is automatically his and *asks* for it. So: power can be unlocked before
  the wisdom to use it; advanced/evolved forms may require responsibility, restraint, dependence,
  humility, willing surrender, accepting consequence, acting without personal gain, or *choosing not
  to use* power. **Do not reduce enlightenment to an XP ladder.**
- **[RESEARCH] Theological caution.** Some Samson readings are *interpretations*, not uncontested
  text (Angel of the Lord as pre-incarnate Christ; the two eyes as the two dove offerings; Samson as
  the lamb offering restoring the Nazarite vow; direct Christological parallels). They may inspire
  architecture/symbolism/design but must NOT become objective theological fact in-game without
  further design discussion.

## N5. Create-a-Character — miraculous origin system
- **[DIR]** The CaC story begins *before* the player's adult life; the player will eventually choose
  where/how their incarnation began. **Every origin is miraculous in some form** — "this person
  entered the world through a door that should not have opened." The miracle does NOT determine
  morality — a miraculous birth does not guarantee a miraculous adult.
- **[DIR] Origin-design fields (each origin eventually defines):** biological/medical impossibility ·
  spiritual event · principal witness · what the mother/family believes · what doctors believe ·
  what supernatural entities sensed · who knows the truth · who concealed it · unresolved family
  consequence · unresolved supernatural consequence · how publicly known it became.
- **[PROV] Possible origin categories (not all canon):** 1) The Impossible Womb (infertile mother
  conceives) · 2) The Child After Menopause · 3) The Last Embryo (final "nonviable" embryo survives;
  love/expectation/guilt/pressure) · 4) The Pregnancy That Survived Death (mother nearly dies; fetus
  "couldn't" survive but does) · 5) **The Second Heartbeat** (baby dies at birth + is resuscitated;
  God takes the original soul's place at death — **current default, see N6**) · 6) The Unannounced
  Twin (scans show one; a second is delivered — the child with no name/room/place prepared) ·
  7) The Child of the Coma · 8) The Dream Before Conception (unrelated people dream the same child;
  descriptions partly agree, partly contradict) · 9) The Found Child (newborn in an impossible/sealed
  location — **must respect adoptive parenthood as fully real/meaningful**) · 10) The Unrecognized
  Pregnancy (cryptic pregnancy with details medicine can't explain) · 11) The Child Born During the
  Impossible Hour (citywide anomaly: clocks stop, one room keeps power, wrong-time celestial event,
  ward goes silent, animals turn toward the hospital, dead monitors restart) · 12) The Answer to Two
  Prayers ("Your mother wasn't the only person who asked for you.").
- **[PROV] Origin visibility (second setting):** Private / Disputed / Public / Hidden miracle.

## N6. Current default origin — THE SECOND HEARTBEAT
- **[CANON] Status:** current default CaC origin; the broader origin-selection system stays planned;
  organize the opening conceptually around this. **Do not implement yet.**
- **[DIR] Medical sequence** (grounded enough to feel plausible; **[RESEARCH]** get real neonatal-
  resuscitation + emergency C-section terminology/timing before scripting — no fake-drama medical
  language): dangerous delivery complication → OR → mother unconscious (anesthesia/blood loss/
  emergency) → baby delivered with no detectable breathing/heartbeat → staff recognize death/cardiac
  arrest → neonatal resuscitation → brief non-response → the heart beats again (to staff: an
  extraordinary resuscitation).
- **[CANON] Spiritual sequence:** the pregnancy originally belongs to an **ordinary human soul** (God
  is NOT occupying the fetus the whole pregnancy). At the newborn's death the original soul leaves;
  God intercepts it at the threshold — meaning ≈ "This incarnation is mine. You've carried it far
  enough. Go rest." (**[PROV]** wording). The original soul is **not** destroyed/consumed/erased/
  condemned/punished — it peacefully returns to the spiritual world, rests, may reincarnate later.
  God then takes the newborn body; the heart restarts.
- **[CANON] The two heartbeats:** first = the original human soul; second = God entering physical
  existence. The player didn't merely survive — they **returned as someone else**. The family
  believes the same child died and came back; the deeper truth is the post-resuscitation soul is not
  the pre-death soul. **[PROV]** reveal line: "Your mother gave birth to someone else. You are the
  one who came back."
- **[CANON] The beacon:** the second heartbeat is a supernatural beacon across LA — "**I am awake.**"
  Different entities feel it differently:
  - **Lucifer** — recognizes almost immediately that God has incarnated; may grasp its meaning more
    than anyone. Reaction ≠ simple fear: recognition, surprise, affection, excitement, vindication,
    curiosity, awareness the ancient father-son argument entered a new stage.
  - **Molache** — senses an ancient divine claim entering/reactivating his territory; may not know
    the child's location/identity; knows LA's territorial order changed; unlike fear-driven beings,
    quickly considers how the incarnation could be cultivated/manipulated/hidden/indebted/used.
  - **The Broken Choir** (loyal or "loyal" angels) — detect the presence they've sought; read it
    variously as command / rescue / crisis / test / return of legitimate authority / threat to
    angelic stability / proof the rebellion enters a new phase.
  - **[RESEARCH] Indigenous, ancestral, culturally-rooted powers** — NOT one generic reaction: an
    absent presence returning to relationship / a new claim on the land / disruption / possible
    restoration / a foreign authority / responsibility / danger / a question not an answer.
    Interpretations must stay specific to each tradition — do not invent carelessly.
  - **The Audience & urban entities** — shared dreams, attention anomalies, repeated images,
    electronic interference, viral coincidences, collective anxiety, a brief unexplained citywide
    fixation.
  - **Lesser entities** — hide, migrate, turn aggressive, seek protection, prepare offerings, hunt
    the child, attach to nearby humans, mistake the signal for another entity, spread contradictory
    rumors.
- **[DIR] Human interpretation:** family told ≈ "We lost your baby for several minutes." Beliefs vary
  by witness (died and returned / doctors saved it / God's miracle / medical error / protected for a
  reason / something entered the OR / never speak of it). The mother does not initially know the
  post-resuscitation soul differs from the one she carried.
- **[CANON] Narrative purpose:** before the player speaks, remembers divinity, or uses a power, the
  incarnation has already announced God's return. The birth is simultaneously a medical emergency, a
  family miracle, a hidden death, a reincarnation, a supernatural beacon, a territorial event, the
  first move against Molache, a new stage in Lucifer's relationship with God, and the awakening of
  the larger supernatural board — the first major world event, though the adult won't understand that
  until much later.

## N7. [PROV] Possible CaC intro structure (do NOT implement)
Choose/see the origin → briefly follow mother/guardian/doctor/witness → the supernatural event →
witnesses interpret differently → relevant entities react from elsewhere in LA → the child survives/
appears → cut forward to the adult → adult character creator begins → the origin persists in family
history + later supernatural reveals. Possible closing line: "Everyone remembers the day you were
born differently." The opening plants **mystery**, not a cosmology lecture — the player is NOT
immediately told they are God / that a soul was replaced / which entity sensed the beacon / which
witness is truthful / whether every reaction was benevolent.

## N8. [RESEARCH] Indigenous spiritual research & representation
- **[CANON] Foundational rule:** "Native American spirituality" is NOT one unified religion/pantheon/
  faction. The LA region holds multiple living peoples, communities, histories, languages,
  territories, and traditions. Research order: peoples/communities → territory & sacred geography →
  publicly documented figures → source lineage → living-community interpretation → restricted vs
  public knowledge → cultural-consultation needs → ONLY THEN game adaptation.
- **Peoples currently identified (labels ≠ political unity; preserve modern distinctions):**
  Gabrieleño / Tongva / Kizh; Fernandeño Tataviam; Chumash; Acjachemen.
- **Puvungna** — a **living sacred place** (Tongva/Gabrieleño/Kizh & Acjachemen). **Never** treat as
  ruin / dungeon / dead religion / loot site / a place the player "discovers" / a generic power
  source. Living communities remain connected. **[PROV]** contemporary contexts: land protection,
  university/development disputes, ceremonial continuity, community disagreement, youth/elder tension,
  representation questions, non-Native allies centering themselves, Molache-linked development
  pressure, social media turning sacred conflict into entertainment.
- **Wiyot / Ouiot / Wewyot** — accounts vary (creator / sacred ruler / primordial being / earlier
  sacred order / tied to Puvungna / death by betrayal or poisoning / a gathering after death /
  promised return). **Do NOT lock** whether he is supreme Creator vs created ruler vs both-by-
  tradition, exact genealogy, or whether missionary descriptions preserve Indigenous categories.
  **[DIR]** (provisional): may function as an absent/fragmented primordial presence; dead without
  being spiritually gone; distributed through land/memory/ancestors/sites; understood differently by
  different communities; his absence may mirror God's absence. **[PROV]** line: "You call my absence
  death. What do they call yours?"
- **Chinigchinich / Chungichnish / Chingichnish** — publicly tied to Puvungna, sacred law, teaching,
  obligation, ceremony, proper relationship, spiritual leadership, living practice. **Do NOT reduce
  to "the Native god of LA."** **[DIR]** (provisional): law embodied; concern is conduct not divine
  title; may judge whether God abandoned obligations; does NOT auto-submit to the reincarnated God;
  his law is relational not transactional — ideologically opposite Molache (who turns obligation into
  debt/sacrifice). **[PROV]** first question to God: "What obligations did you abandon when you left?"
- **Ouiamot** — unstable as an independent concept (human teacher / embodied appearance / localized
  manifestation of Chinigchinich / a title / a historical incarnation / a misunderstood personal
  name). **Do NOT create as a separate major deity yet.**
- **Coyote** — appears in some accounts of Wiyot's death/cremation. **Do NOT generalize to "Coyote is
  evil"** (traditions vary widely). **[RESEARCH]** possible functions: boundary-breaker, trickster,
  agent of irreversible change, consumer of sacred power, one blamed for an outcome others wanted, a
  being who prevents restoration of the old order. No personality/morality/design/role locked.
- **Chumash candidates [RESEARCH]:** **Hutash** (Earth Mother, creation, Limuw, homeland, migration,
  reciprocity, transformation, dolphin relatives — not a generic "Mother Nature"); **Alchupo'osh**
  (Sky Snake, Milky Way, lightning, fire, dangerous/transformative gifts, relationship with Hutash —
  a fire-gift could be transformed by modern California into industry/electricity/weapons/wildfire/
  consumption/development). Need deeper research before characterization.
- **[CANON] Indigenous entity reclassification rule:** for Lucifer/Molache/fallen angels/invented
  urban entities you have broad freedom to invent hidden histories. For beings tied to **living**
  traditions, do NOT invent a scandalous secret "real mythology" or imply the game uncovered truths
  communities forgot. Reclassification there must come through competing human interpretations,
  present-day fictional choices, conflicts among custodians, questions of law/mercy/authority/land/
  memory/obligation, publicly documented differences, fictional intermediaries/guardians, the
  entity's response to current events, or human misuse of sacred authority. A **human custodian**
  may be challenged: "You keep calling it sacred law because you're afraid to admit it's your
  decision."
- **[CANON] Cultural boundaries — NEVER:** reproduce restricted ceremonies just because an
  anthropologist recorded them; reveal confidential sacred-site locations; make burial areas loot
  dungeons; treat ceremonial objects as collectible buffs; merge Tongva/Acjachemen/Tataviam/Chumash/
  Vodou/Hoodoo/Candomblé into one system; use generic pan-Indigenous costumes; treat conflicting
  traditions as errors to solve; villainize a sacred being just for dramatic imagery; use colonial
  missionary categories as unquestioned truth.

## N9. [PROV] Puvungna supernatural structure (strong direction, NOT locked)
Do NOT call everyone associated with Puvungna one faction. Possible convergence (not a "Native king-
god's palace"): **The Keepers of Return** (living descendants/elders/protectors/practitioners) ·
**The Law** (Chinigchinich as obligation/ceremony/relationship/consequence) · **The Memory of Wiyot**
(vast fragmented presence of absence/death/land/memory/possible return) · **The Unresolved Gathering**
(ancestors/animals/powers/presences from the gathering after Wiyot's death).

## N10. [PROV] Entity hidden-room examples (exploratory, NOT canon)
- **Molache** — established: sovereign of sacrifice, cold/calculating, presents sacrifice as universal
  law, seemingly in total control of LA. Hidden room should challenge his *own* relationship with
  sacrifice: was once sacrificed / once refused to sacrifice what he valued / his philosophy began
  with a sacrifice that failed / he was meant to *prevent* sacrifice / someone survived an offering
  he believes completed / he disguises one personal wound as universal truth. Accusation: "You keep
  asking people to pay a price you were too frightened to pay yourself."
- **Lucifer — two levels.** (1) the helpful guide is revealed to be Lucifer ("he helped me" → "he
  studied me while helping me" — both true). (2) deeper: challenge his identity as a *fair tester* —
  "You don't test people to discover who they are. You test them until they become what you
  predicted." Pressure truth: he rigs conditions because he can't emotionally survive humanity
  proving him wrong.
- **Broken Choir leader** — established: loyal angel who resisted Lucifer, severe, "incorruptible."
  Hidden room: was among the first to gain independent awareness / nearly joined Lucifer / helped
  spread sentience / returned to obedience and hid it. Accusation: "You didn't resist him. You taught
  him how to spread it."
- **The Audience** — collective urban entity of fame/attention/scandal/humiliation/parasocial
  obsession. Hidden room: born not from celebrity worship but from people desperate to be
  acknowledged (ignored workers, erased performers, unnamed victims, people treated as statistics).
  Accusation: "You were born because nobody saw us. Now you make sure nobody sees anyone."
- **Protector/healer entity (reusable structure)** — genuinely saves a community by excluding/
  sealing/sacrificing/forgetting one person or line; the excluded one returns. Accusation: "You saved
  everyone by deciding I no longer counted as one of them."

## N11. Canon status summary
- **[CANON] / locked direction:** novela principles at the structural level; reveals reclassify
  rather than replace; supporting cast & villains suit identity-targeted reveals; entities challenged
  at the center of their domains; Lucifer may arrange the return/exposure of an *existing* secret but
  is not behind every secret/coincidence; subtle editing may imply untrue developments but
  misdirection must stay fair; large divine actions can begin in private/impossible births; a
  character may misunderstand the source/purpose of their power; divine purpose ≠ erasing human
  responsibility; oppressed communities may resist rescue; the player's powers may start morally
  narrow; CaC will allow miraculous-origin selection; **The Second Heartbeat is the current default
  origin** (ordinary soul → baby dies/arrests → original soul peacefully leaves → God takes the body
  → heartbeat returns → beacon; Lucifer/Molache/Broken Choir/others sense it differently); Indigenous
  traditions researched separately with cultural specificity; Puvungna is a living sacred place, not
  a dungeon; never invent secret "true mythology" for living communities.
- **[DIR] Strong working directions:** Second Heartbeat intro during emergency surgical delivery,
  mother unconscious; team reads it as neonatal resuscitation; family remembers differently; first
  heartbeat = original soul, second = incarnation; "I am awake" captures the beacon; CaC may open with
  a short pre-birth/birth prologue; origins may carry private/disputed/public/hidden visibility;
  Wiyot as absent/fragmented primordial presence; Chinigchinich as sacred law/obligation embodied;
  Puvungna as supernatural convergence not a conventional faction.
- **[PROV] Provisional:** exact words God says to the departing soul; the final name "The Second
  Heartbeat"; the intro's length/playable structure; whether the player controls mother/doctor/
  guardian/witness; all alternate origins; visibility as a formal setting; Molache's personal hidden
  history; Lucifer's deeper reclassification; the Broken Choir leader's concealed rebellion; the
  Audience's exact origin; Puvungna group names; specific Wiyot/Chinigchinich/Ouiamot/Coyote/Hutash/
  Alchupo'osh characterizations; the exact confrontation lines quoted above.
- **[RESEARCH] Needs research/consultation:** neonatal-resuscitation details; emergency C-section
  procedure/terminology; how doctors would explain it to the mother; time windows/outcomes; specific
  Indigenous teachings; community-preferred terminology; public vs restricted knowledge; visual design
  of culturally-rooted beings; use of ceremonial objects/language/regalia/songs/sacred geography;
  political distinctions among modern Indigenous communities.

> **This material is narrative context only. No implementation, scripting, asset generation, database
> work, or production changes should begin until Nelson explicitly requests the next task.**
