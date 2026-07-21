# I AM GOD — Ready-to-Paste Asset Prompt Pack (Option A, flat elevation)

Copy-paste prompts for **every** asset needed to complete the Hollywood-Blvd district in the
unified reference style. Companion to `ART_DIRECTION.md`. Fully self-contained — just copy a
block. **Attach the reference image (IMG_FF61) as the style guide** each time.

## ⚠️ READ FIRST — two rules that make or break the set

1. **Light NEUTRAL, not night.** We have a runtime **day-night engine** that tints the whole
   scene (bright noon → golden dusk → deep-blue night). So generate every asset in **neutral,
   even, soft daylight with minimal baked shadows** — do **NOT** bake a dark night ambient into
   the art (that would double-darken at night and look muddy at noon). Neon signs, marquees, and
   windows may glow (they're emissive). *Match the reference's detail, linework, palette family,
   and charm — but ignore its darkness.*
2. **Two framing modes.** Ground = **seamless full-frame tiles**. Everything else = **isolated
   on magenta** so I can key it transparent.
   - **SEAMLESS TILE:** "seamless tileable texture, flat top-down view, orthographic, no
     perspective, no single object, the pattern continues off all four edges so copies butt
     together with no visible seam, square image, fills the frame."
   - **ISOLATED ASSET:** "single subject, centered, full and uncropped, isolated on a plain flat
     #FF00FF magenta background, no ground, no cast shadow off the edges, no glow past the
     silhouette, even margins."

After you generate: send me the PNGs. I key + crop, drop into `public/`, add a tile-based
ground renderer for the seamless tiles, and set scale/placement.

---

## 1. GROUND / SEAMLESS TILES (the biggest missing layer)

**Road — main boulevard asphalt**
> Detailed HD pixel art game texture, matching the detail/palette/charm of the reference
> Hollywood-Blvd image but in NEUTRAL EVEN DAYLIGHT (a runtime day-night engine re-lights it —
> do not bake night or shadows). A dark charcoal asphalt road surface with subtle aggregate
> speckle, faint oil staining, hairline cracks — clean, no lane markings. Seamless tileable on
> all four edges, flat top-down orthographic, square image, fills the frame.

**Sidewalk — Hollywood terrazzo (plain)**
> [same neutral-daylight texture prefix] A Hollywood sidewalk of warm charcoal terrazzo paving
> squares with fine brass seams, subtle per-tile tone variation, tiny speckle. Seamless tileable
> on all four edges, flat top-down, square, fills the frame.

**Walk-of-Fame star (drop-on accent, not seamless)**
> [same neutral-daylight prefix] A single Hollywood Walk of Fame star tile: a coral-pink
> five-point star with a polished brass border and brass ring, set flush into a charcoal
> terrazzo square, top-down flat view. Single tile centered, isolated on a plain flat #FF00FF
> magenta background, even margins.

**Crosswalk**
> [same neutral-daylight prefix] A top-down zebra crosswalk: even cream-white stripes on charcoal
> asphalt, clean edges. Seamless tileable across its width (left/right edges wrap), flat top-down,
> rectangular.

**Grass / residential lawn**
> [same neutral-daylight prefix] A lush lawn texture: healthy medium-green grass with fine blade
> detail, a few clover sprigs, faint mowing lines. Seamless tileable on all four edges, flat
> top-down, square, fills the frame.

**Garden soil / planter dirt**
> [same neutral-daylight prefix] Dark garden soil and bark-mulch texture, fine detail. Seamless
> tileable on all four edges, flat top-down, square.

**Landmark plaza / forecourt terrazzo**
> [same neutral-daylight prefix] An ornate terrazzo plaza: a brass starburst inlay pattern on
> polished cream-and-charcoal stone. Seamless tileable on all four edges, flat top-down, square.

**Curb + gutter strip (optional, road↔sidewalk seam)**
> [same neutral-daylight prefix] A tileable curb-and-gutter strip: a pale concrete curb above a
> darker gutter channel meeting dark asphalt, top-down. Seamless left-to-right, thin horizontal
> strip.

---

## 2. PROPS (isolated on magenta — density)

Generate the common ones as **one sheet** to guarantee they match:
> Detailed HD pixel art game asset SHEET, HD-2D Octopath detail, matching the reference
> Hollywood-Blvd style/palette but in NEUTRAL EVEN DAYLIGHT with minimal baked shadows (a runtime
> day-night engine re-lights it); neon may glow. A sheet of Hollywood Blvd street props, all the
> same style/scale, evenly spaced, each fully separated: a tall palm tree, a vintage wrought-iron
> twin-globe street lamp, a ticket/info kiosk, a café umbrella with a bistro table + 2 chairs, a
> small tiered sidewalk fountain, a stone planter with flowers, a wooden bench, a trash can.
> Flat front elevation, orthographic, no perspective. On a plain flat #FF00FF magenta background,
> no ground, no shadows off the edges, even spacing.

Individual extras (same prefix, ISOLATED framing): **neon vertical blade sign**, **traffic
signal**, **fire hydrant**, **newsstand**, **bus-stop shelter**, **valet/tour podium**,
**bike rack**, **string-light garland**.

---

## 3. VEHICLES (isolated, side profile for the flat street)

> [same neutral-daylight isolated-asset prefix] A [YELLOW HOLLYWOOD TAXI CAB], exact left-side
> profile view, orthographic, no perspective, glossy clean paint, detailed wheels/windows.
> Single vehicle centered, full and uncropped, isolated on a plain flat #FF00FF magenta
> background, no ground, no cast shadow off the edges, even margins.

Swap the subject for each: **black luxury SUV/limo**, **red convertible sports car**, **silver
sedan**, **city bus with ad panel**, **open-top tour bus**, **police cruiser**, **delivery van**.

---

## 4. CHARACTERS / CROWD (isolated, to match our existing chibi sprites)

**Pedestrian crowd sheet (NPC filler):**
> [same neutral-daylight isolated-asset prefix, chibi] A sheet of 8 varied full-body chibi
> pedestrians, front view, standing, same cute HD-pixel style and scale as the reference crowd —
> mixed ages/outfits (tourist with camera, businesswoman, skater, couple, street performer, cop,
> vendor, kid). Each fully separated on a plain flat #FF00FF magenta background, even spacing,
> no shadows off the edges.

**Back views (for walking away from camera):**
> [same] The same 8 chibi pedestrians seen from BEHIND (back of head/outfit), same order, same
> style/scale, on magenta.

*(Named playable characters — Roxy, Lori, Nia, Kiki, Maya, Jordyn, Dalia, Sorriso, Elizabeth —
already have art. New playable characters get their own front+back like these.)*

---

## 5. BUILDINGS (recap — see also ART_DIRECTION.md §5A)

All buildings: **flat front elevation, straight-on orthographic, no roof/perspective**, neutral
daylight, ISOLATED on magenta. Types we still want, to build a real multi-story streetwall:

- **Regenerate Apex** as a proper 2-story record shop (its current art is a book on a card).
- **Multi-story filler strip** — "a continuous row of five different but stylistically identical
  3–4 story Hollywood buildings, shoulder to shoulder, ground-floor shops with lit windows +
  small neon, apartments above, cornices; row fills the frame edge to edge" (I slice it).
- **Apartment block** (5-story brick filler), **corner building**, more **storefront shops**
  (diner, deli, theater, pharmacy, club), extra **Spanish bungalows** for the residential row.

---

## Priority order (what unlocks the biggest look-jump)
1. **Road + sidewalk + grass + crosswalk tiles** (§1) → I wire a tile ground renderer; the whole
   floor jumps to reference quality.
2. **Multi-story filler strip + regenerated Apex** (§5) → real streetwall with floors.
3. **Prop sheet + pedestrian sheet** (§2, §4) → density.
4. **Vehicles** (§3) → the boulevard comes alive.
