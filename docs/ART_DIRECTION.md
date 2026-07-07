# I AM GOD — Art Direction & Asset Prompt Bible

**Purpose:** get our game to look like the reference (detailed pixel-art Hollywood Blvd at
night) instead of a patchwork of mismatched AI renders. This is the document to paste FROM
when generating assets, and the thing to keep consistent across every asset.

## Context to remember (per Nelson)
- We are **still in Phase 2**: populating the district with buildings. "Actual gaming"
  (mechanics, arcs) comes *after* the place is built out and looks right.
- Structurally we're **far from the reference**, and that's expected right now.
- Playable cast is locked to the 9 art-backed souls; everyone else is an NPC until told
  otherwise.
- Our Hollywood Blvd is **longer** than the reference (a full multi-block boulevard, not one
  dense block) — so assets must **tile/repeat cleanly**, not be one-off hero pieces.

---

## 1. Why the reference (left) reads GOOD and ours (right) doesn't

Look past "it's just nicer art." Five concrete, fixable gaps:

| # | Reference (goal) | Ours now | The real problem |
|---|---|---|---|
| 1 | **One unified style** — every building, tile, person shares the same pixel resolution, line weight, palette, and baked lighting. | Blackwood's is dark painterly, Apex is a glossy 3D-ish render **with a soft oval halo/vignette that was never keyed out**, the houses are bright flat cartoon, the taco shop another style again. | **Style drift.** Each asset was generated as its own thing. Nothing agrees on light, resolution, or palette. |
| 2 | **High-oblique dimetric/isometric** camera — you see facades *and* rooftops/depth; the street plane recedes. | **Flat front billboard** — buildings stand face-on on a line, no depth, no roofs. | **Projection mismatch.** A cohesive scene needs ONE camera/projection for every asset. |
| 3 | **Multi-story buildings with real floors**, shoulder-to-shoulder, forming a continuous streetwall. | Short, isolated single-story-ish sprites with **gaps and mismatched heights/scale**. | **No streetwall + no consistent scale.** Buildings float apart instead of forming a block. |
| 4 | **Richly tiled ground**: patterned sidewalk, Walk-of-Fame stars embedded in the tiling, road lane dashes, **crosswalks**, wet-sheen reflections. | Flat dark ground + star ellipses + code lamps. | **Ground is empty.** The tiling/reflections are half the "expensive" look. |
| 5 | **Dense**: crowds, cars, palms, kiosks, umbrellas, fountains, a carousel — the frame is packed and alive. | Sparse; big empty dark areas. | **Density.** Emptiness reads as "unfinished." |

**Takeaway:** the reference's magic is **cohesion + density + tiled ground + baked neon
lighting** — NOT any single hero building. We already generate nice individual pieces; the
problem is they don't *agree* with each other. Fix agreement first.

---

## 2. The one decision that controls everything: projection

Pick ONE and generate **every** asset in it. Do not mix.

- **Option A — Flat 2D elevation (side-scroller streetwall).** Buildings drawn straight-on,
  no roof/depth, stacked into a continuous wall (think *Kingdom: Two Crowns*, classic beat-
   'em-up streets). **Closest to our current engine** — minimal code change, we mostly need
  *taller, multi-story, consistently-lit, gapless* facades + tiled ground. Gets ~80% of the
  reference's charm (density, neon, tiling) without a projection rewrite.
- **Option B — True dimetric/isometric (like the reference).** Buildings show depth and roofs,
  ground is an iso tile grid. **Matches the reference exactly** but is a real engine change
  (iso camera, iso tile map, depth-sorting, iso character movement) and every asset must be
  redrawn in 2:1 dimetric.

**Recommendation:** ship the look in Option A first (unify style + go multi-story + tile the
ground + add density) because it reuses the engine. Treat Option B as a later "phase 3.5"
if we still want the full bird's-eye. The prompt library below has a block for **both**.

---

## 3. THE STYLE BIBLE (lock this — paste it into every asset prompt)

> **Detailed HD pixel art** (high-resolution pixel illustration — crisp clean pixels, fine
> dithering, painterly-pixel hybrid, *not* chunky 8-bit), cozy 2.5D game diorama of
> **Hollywood Boulevard at night**. Cohesive cinematic night lighting: deep indigo-blue
> ambient, **saturated neon marquee glow**, warm amber street-lamp pools, soft bloom, subtle
> reflections on the pavement. **Single key light from the upper-left**, consistent shadows.
> Unified muted-jewel palette: indigo, teal, magenta, warm gold, brass. Nintendo-DS-era JRPG
> town / HD-2D (Octopath-Traveler) aesthetic — ultra-detailed, charming, richly lit.

**Style anchors that steer models toward this look:** "detailed pixel art", "HD-2D",
"isometric pixel diorama", "Octopath Traveler style", "1990s point-and-click adventure
background", "detailed JRPG town at night". Avoid "8-bit / NES / minimalist / chunky" — those
pull toward crude low-res.

**Locked constants (never vary between assets):**
- **Light direction:** upper-left key, warm. **Time:** night.
- **Palette:** the jewel palette above (indigo/teal/magenta/gold/brass).
- **Resolution/detail:** high-detail pixel; same apparent pixel size on every asset.
- **Scale:** 1 "floor" ≈ a fixed height; a chibi person ≈ 1/3 of a storefront floor. Keep
  people/buildings/cars in proportion across all assets.
- **Prohibited:** perspective convergence (keep it orthographic), soft photographic blur,
  drop-shadow halos/vignettes, watermark, text other than requested signage, white paper
  background.

---

## 4. Prompt-engineering rules (from research)

1. **Art bible, not one-off prompts.** Consistency comes from *constraints set before
   generation* — camera, palette, light, scale, tile size, prohibited details — reused
   verbatim. A prompt is not art direction; the bible is. (SEELE AI; Sloyd; Scenario.)
2. **Feed the reference as a STYLE image.** In whatever generator, attach the reference and
   say "match the art style, lighting, palette, and level of detail of this image; ignore its
   content." The model takes *what* from your text and *how* from the image. This is the
   single biggest consistency lever. (seeles.ai consistency guide; Layer.)
3. **State the projection explicitly** when doing Option B: "true 2:1 dimetric/isometric
   projection, ~30° parallel axes, orthographic, **no perspective convergence, parallel lines
   stay parallel**, high oblique bird's-eye camera." Use pixel-friendly 2:1 dimetric, not pure
   120° isometry. (Aituts; glima.ai; Wikipedia: isometric projection.)
4. **Generate isolated, transparent, centered** for modular assets: "single subject, centered,
   full and uncropped, **isolated on a plain flat background, transparent, no ground, no
   shadow bleeding off the edges, no glow halo past the silhouette, even margins**." Then key
   it (our PIL keyer) — this is exactly what fixes the Apex-style halo problem.
5. **Batch for agreement.** Generate a *set* in one go ("a row of five different storefronts,
   same style/scale/lighting, side by side") so the model self-matches, then slice — or lock a
   **seed** and reuse it. (Wayline; easy-peasy.ai sprite-sheet guide.)
6. **AI is a starting point.** Expect to key, crop, scale, and occasionally touch up every
   asset. Don't expect drop-in perfection. (iXie; Wayline.)

---

## 5. COPY-PASTE PROMPT LIBRARY

**How to build a prompt:** `[STYLE BIBLE §3]` + `[PROJECTION line]` + `[subject]` +
`[framing/background rule §4.4]`. Always attach the reference image as the style guide (§4.2).

### Projection lines (paste one)
- **Option A (flat elevation):** `Flat front elevation, straight-on orthographic storefront
  view, no perspective, no visible roof or side wall, building fills the frame vertically.`
- **Option B (dimetric):** `True 2:1 dimetric/isometric projection, ~30° parallel axes,
  orthographic, no perspective convergence, parallel lines stay parallel, high oblique
  bird's-eye camera, visible facade + a sliver of roof.`

### Framing/background rule (paste on every MODULAR asset)
`Single asset, centered, full and uncropped, isolated on a plain flat #FF00FF magenta
background, transparent-ready, no ground plane, no cast shadow bleeding off the edges, no
glow/vignette extending past the silhouette, even margins on all sides.`

### 5A. Buildings (the streetwall)
- **Multi-story theatre / landmark:** `…a grand 4-story Hollywood movie-palace facade at
  night: ornate cornice, marquee with glowing neon letters reading "OVERTURE", vertical blade
  sign, arched lit windows on every floor, brass doors, warm interior glow spilling out.`
- **Storefront shop (repeatable filler):** `…a narrow 2-story Hollywood storefront at night:
  lit shop window on the ground floor, small neon sign, apartment window above, awning, warm
  glow. Generic tenant (record shop / diner / tattoo parlor / boutique).`
- **Corner building:** (Option B only) `…an L-shaped corner building wrapping a street corner,
  two lit facades meeting at the corner, neon on both.`
- **Apartment block (fills gaps, adds height):** `…a plain 5-story brick apartment building at
  night, rows of identical lit windows, fire escape, flat roof — background streetwall filler.`
- **Spanish-revival bungalow (residential row):** `…a small 1-story Spanish-revival stucco
  house, red-tile roof, arched door, little front yard — cohesive with the night palette.`

> **Consistency tip:** generate storefronts as a **strip of 5 at once** ("a continuous row of
> five different but stylistically identical 2-story Hollywood storefronts, shoulder to
> shoulder, one night scene, even lighting") and slice — this guarantees they agree and butt
> together into a streetwall with no gaps.

### 5B. Ground tiles (the half of the look we're missing)
- **Walk-of-Fame sidewalk tile (seamless):** `…a seamless top-down tileable Hollywood sidewalk
  texture: charcoal terrazzo squares with brass seams and a pink-and-brass Walk-of-Fame star
  set into it, wet night sheen, seamless on all four edges.` (say **"seamless tileable, edges
  wrap"**).
- **Asphalt road tile (seamless):** `…a seamless tileable night asphalt road texture, faint
  yellow center lane dashes, subtle neon reflections, wet sheen.`
- **Crosswalk tile:** `…a top-down zebra crosswalk on wet night asphalt, glowing under a
  street lamp, tileable across its width.`
- **Plaza/terrazzo (landmark forecourt):** `…an ornate terrazzo plaza pattern, brass inlay
  starburst, seamless tileable, night reflections.`

### 5C. Props (density)
- **Street lamp:** `…a single vintage Hollywood twin-globe street lamp post, warm glowing
  glass globes, wrought-iron, night.` *(we currently code-draw these — a real asset upgrades
  them.)*
- **Palm tree, ticket kiosk, café umbrella + bistro set, sidewalk fountain, tour-map pylon,
  neon blade sign, planter** — each: `…a single [prop] at night, warm-lit,` + framing rule.
- Generate props as a **sheet**: `a sheet of Hollywood Blvd street props (lamp, palm, kiosk,
  fountain, umbrella, planter, bench), same style/scale/night lighting, on magenta, evenly
  spaced.`

### 5D. Characters (chibi crowd) — keep matching our existing sprites
- `…a full-body chibi character, [description], standing, front view, cohesive detailed-
  pixel style, soft night rim-light,` + framing rule. Also request `_back.png` view:
  `…same character, seen from behind (back of head/outfit), for walking away from camera.`
- For crowd-fill NPCs, generate a **sheet of 8 varied pedestrians**, same style/scale.

### 5E. Cars
- `…a single [red convertible / yellow taxi / black limo / silver sedan], [Option A: side
  profile] / [Option B: 3/4 dimetric top view], glossy night reflections,` + framing rule.

---

## 6. Asset workflow (per asset)
1. Prompt = §3 bible + projection line + subject + framing rule; **attach the reference** as
   style guide.
2. Generate a batch (strip/sheet) so pieces self-match; pick the best.
3. **Key + crop** with our PIL keyer (`scratchpad/key_*.py` pattern) → transparent, tight
   bbox. This is what kills the Apex-style background halo.
4. Drop into `public/buildings/<stem>.png` (or `public/spirits/`, `public/parts/`); the engine
   auto-loads by filename. Rendered width follows the art's aspect, so scale is set by the
   `ch` (character-heights tall) value in `sceneData.ts`.
5. Eyeball scale against a neighbor; adjust `ch` so floors/heights line up into a streetwall.

## 7. Immediate wins (no projection change, biggest look-jump)
1. **Re-key the halo assets** (Apex etc.) so nothing has a soft vignette background.
2. **Add real ground tiles** (§5B) — sidewalk + road + crosswalks — biggest bang for buck.
3. **Go multi-story**: regenerate filler as 2–5 story buildings so the streetwall has height.
4. **Density pass**: props sheet (§5C) + more pedestrians (§5D).
Do those four in Option A and we jump most of the way to the reference without touching the
camera.

## Sources
- SEELE AI — *Consistent AI game assets workflow* & *sprite tools*: https://www.seeles.ai/resources/blogs/consistent-ai-game-assets-workflow
- Sloyd — *Style-consistent AI assets*: https://www.sloyd.ai/blog/how-to-style-consistent
- Scenario / Layer — style-training for consistency: https://www.scenario.com/ · https://www.layer.ai/
- Aituts — *Midjourney isometric prompts*: https://aituts.com/midjourney-isometric/
- glima.ai — *3D isometric with AI*: https://glima.ai/blog/3-d-isometric/
- Wikipedia — *Isometric projection* (2:1 dimetric, 116.57°/126.87°): https://en.wikipedia.org/wiki/Isometric_projection
- Wayline — *AI art workflow for indie game assets*: https://www.wayline.io/blog/ai-art-generation-game-assets-workflow-tools-indie-developers
- easy-peasy.ai — *Generate sprite sheets with AI*: https://easy-peasy.ai/blog/how-to-generate-sprite-sheets-with-ai-free-guide-for-game-developers
