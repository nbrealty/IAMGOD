# Modular Part Prompts — mix-and-match spirit library

Prompts for generating the **layered part library** in `public/parts/`. Instead
of one finished PNG per soul, characters are composited from stacked transparent
layers (body → bottom → top → shoes → hair → accessory), so a small hand-made
set produces thousands of distinct NPCs. See
[`public/parts/README.md`](../public/parts/README.md) for the folders, filename
convention, and how souls map to parts.

---

## The workflow (do this in order — it's what keeps parts aligned)

AI generators can't guarantee pixel registration on their own, so we anchor
everything to one reference:

1. **Generate the base body first** (Section A). Keep the result — it is both
   `body_*.png` *and* your alignment reference for everything after it.
2. **For every other layer**, in ChatGPT: attach that base body image and say
   *"Align to this exact figure — same pose, same size, same position. Output
   ONLY the [hair / shirt / …], everything else fully transparent."* Then append
   the item's prompt from the relevant section below.
3. Save each result into the right folder under the filename in its list.
4. Additional bodies (other skin tones/builds) reuse the **same canonical pose**,
   so a top generated once sits correctly on any of them.

Generate one full character end-to-end first (a body + one of each layer),
composite-check that they stack cleanly, and only then batch out the variants.

---

## Canonical pose (identical in every single prompt)

> Standing straight, front-facing at a 3/4 high angle (seen from a slightly
> raised camera), **both arms relaxed and held a little away from the torso**,
> feet together and flat, neutral calm expression, centered on the canvas with a
> small even margin. This exact pose never changes between parts.

Arms-slightly-out matters: it keeps sleeves and jacket edges from clipping into
the body so tops stay swappable.

---

## Master Part-Style Prefix

Prepend this to every part prompt (it's the same base as the full spirits, plus
the canonical pose and the isolation rule):

> Chibi-proportioned game asset for a god-game set in a stylized 2026 Los
> Angeles. Head roughly one-third of total body height; short limbs. Clean crisp
> pixel-art / cel-shaded style, soft warm daylight from the upper-left, subtle
> rim light, **no cast shadow**. Grounded realistic American style — **absolutely
> no anime tropes** (no oversized sparkling eyes, no twin-tails, no school
> uniforms, no unnatural hair colors unless clearly dyed). Square ~512×512
> canvas, fully transparent background. Canonical pose: standing straight,
> front-facing at a 3/4 high angle, arms relaxed slightly away from the torso,
> feet flat, centered. Render ONLY the part described — everything else fully
> transparent, no body parts that aren't the part, no background, no props.

---

## A. Base bodies — `body/body_<tone>_<build>.png`

The one layer that IS the full figure. Generate these first; they define the
pose all other layers align to. Build `a` = broader shoulders, build `b` =
narrower/softer silhouette (both androgynous chibi — hair and clothing carry the
gender read).

**Worked example** (`body_tan_a.png`):
> [Master Part-Style Prefix] A bare chibi base body / mannequin with **tan skin**,
> broader-shouldered "build A" silhouette, neutral facial features, no hair,
> wearing only plain neutral-grey fitted underclothes (tank + shorts). This is a
> dress-up base — clean, symmetrical, evenly lit so other layers can be added on
> top.

Generate one per row:

| Save as              | Skin tone      | Build                  |
|----------------------|----------------|------------------------|
| `body_light_a.png`   | light/pale     | A (broader shoulders)  |
| `body_light_b.png`   | light/pale     | B (narrower/softer)    |
| `body_tan_a.png`     | tan / olive    | A                      |
| `body_tan_b.png`     | tan / olive    | B                      |
| `body_brown_a.png`   | medium brown   | A                      |
| `body_brown_b.png`   | medium brown   | B                      |
| `body_deep_a.png`    | deep brown     | A                      |
| `body_deep_b.png`    | deep brown     | B                      |

(Add more tones/builds later — the compositor just reads whatever's in the folder.)

---

## B. Hair — `hair/hair_<style>_<grooming>_NN.png`

American styles. `<grooming>` uses the engine's tags (`maintained`, `casual`,
`unkempt`, `minimal`). Generate the same style twice — once crisp, once
messy — to cover well-kept vs neglected souls.

**Worked example** (`hair_short-crop_maintained_01.png`):
> [Master Part-Style Prefix] Just the **hair**: a short, neat men's crop, dark
> brown, cleanly groomed, sitting naturally on the head of the reference figure.
> Only the hair — face and body fully transparent.

Style list (generate `maintained` + `unkempt` where it makes sense):

| Save as                                   | Style                                   |
|-------------------------------------------|-----------------------------------------|
| `hair_short-crop_maintained_01.png`       | short neat men's crop                   |
| `hair_short-crop_unkempt_01.png`          | same crop, grown-out and messy          |
| `hair_buzz-fade_maintained_01.png`        | buzz cut with a clean fade              |
| `hair_slick-back_maintained_01.png`       | slicked-back executive style            |
| `hair_tousled_casual_01.png`              | short tousled/bedhead                   |
| `hair_man-bun_casual_01.png`              | man-bun with undercut                   |
| `hair_thinning_casual_01.png`             | thinning / receding, middle-aged        |
| `hair_long-straight_maintained_01.png`    | long straight, past shoulders           |
| `hair_ponytail_maintained_01.png`         | pulled-back ponytail                    |
| `hair_bob_maintained_01.png`              | chin-length bob                         |
| `hair_updo_maintained_01.png`             | styled updo / bun                       |
| `hair_curly-natural_maintained_01.png`    | curly natural, medium                   |
| `hair_curly-natural_unkempt_01.png`       | same, uncombed                          |
| `hair_afro_natural_maintained_01.png`     | rounded natural afro                    |
| `hair_long-wavy_casual_01.png`            | long loose waves                        |

---

## C. Tops — `top/top_<clothingTag>_NN.png`

`<clothingTag>` is the exact string from `appearance.ts`, so the compositor picks
the top straight from the soul's state. Each is drawn on the reference torso with
the arms-out pose so sleeves don't clip.

**Worked example** (`top_loud-curated_01.png`):
> [Master Part-Style Prefix] Just the **upper-body clothing**: a loud, logo-heavy
> designer athleisure top in a bold saturated color, trendy and attention-seeking
> ("new money" look), fitted to the reference figure's torso and arms. Only the
> garment — head, hands, and legs fully transparent.

| Save as                              | clothingTag           | Garment                                              |
|--------------------------------------|-----------------------|-----------------------------------------------------|
| `top_worn_01.png`                    | worn                  | faded threadbare band tee / old hoodie              |
| `top_practical_01.png`               | practical             | plain solid polo or work henley                     |
| `top_practical_02.png`              | practical             | uniform polo with a clipped lanyard/name tag        |
| `top_authentic-casual_01.png`        | authentic-casual      | soft flannel or comfortable button-up               |
| `top_quiet-curated_01.png`           | quiet-curated         | impeccably tailored dark blazer, no logos           |
| `top_loud-curated_01.png`            | loud-curated          | logo-heavy designer athleisure, bold color          |
| `top_aspirational-curated_01.png`    | aspirational-curated  | fast-fashion blazer over a going-out top            |
| `top_trend-curated_01.png`           | trend-curated         | fashion-forward layered streetwear                  |
| `top_ironic-curated_01.png`          | ironic-curated        | expensive clothing styled to look thrifted          |
| `top_authentic_01.png`               | authentic             | lived-in henley, genuinely comfortable              |

**Faction / costume tops** (archetype overrides, same folder):
| Save as                          | For                                                    |
|----------------------------------|--------------------------------------------------------|
| `top_faction-flannel_01.png`     | faction-coded Pendleton/flannel + white tee            |
| `top_costume-mascot_01.png`      | scuffed silver-and-red foam superhero chestplate       |
| `top_uniform-tour_01.png`        | branded tour-company polo + lanyard                    |

---

## D. Bottoms — `bottom/bottom_<type>_NN.png`

**Worked example** (`bottom_jeans-worn_01.png`):
> [Master Part-Style Prefix] Just the **lower-body clothing**: worn, slightly
> faded blue jeans fitted to the reference figure's legs. Only the jeans — torso,
> hands, and feet fully transparent.

| Save as                      | Garment                              |
|------------------------------|--------------------------------------|
| `bottom_jeans-clean_01.png`  | clean blue jeans                     |
| `bottom_jeans-worn_01.png`   | worn/faded jeans                     |
| `bottom_jeans-ripped_01.png` | ripped/distressed jeans              |
| `bottom_chinos_01.png`       | tan chinos                           |
| `bottom_slacks_01.png`       | tailored dress slacks                |
| `bottom_cargo_01.png`        | utility cargo pants                  |
| `bottom_joggers_01.png`      | athleisure joggers                   |
| `bottom_shorts_01.png`       | casual shorts                        |
| `bottom_skirt_01.png`        | casual skirt                         |

---

## E. Shoes — `shoes/shoes_<type>_NN.png`

**Worked example** (`shoes_sneakers-clean_01.png`):
> [Master Part-Style Prefix] Just the **footwear**: a pair of clean white
> sneakers positioned at the reference figure's feet. Only the shoes —
> everything above the ankles fully transparent.

| Save as                        | Footwear                    |
|--------------------------------|-----------------------------|
| `shoes_sneakers-clean_01.png`  | clean white sneakers        |
| `shoes_sneakers-worn_01.png`   | scuffed worn sneakers       |
| `shoes_dress_01.png`           | polished dress shoes        |
| `shoes_boots-worn_01.png`      | worn work boots             |
| `shoes_sandals_01.png`         | casual sandals              |
| `shoes_heels_01.png`           | modest heels                |

---

## F. Accessories — `accessory/accessory_<slot>_<name>.png`

The archetype-defining layer — this is what makes a paparazzo read as a
paparazzo. Slots: `head`, `neck`, `prop` (held item), `costume`. A soul can
stack more than one (e.g. cap + camera).

**Worked example** (`accessory_prop_dslr.png`):
> [Master Part-Style Prefix] Just a **held prop**: a big black DSLR camera with a
> telephoto lens, positioned as if raised to the reference figure's face in both
> hands. Only the camera (and the hands gripping it if needed) — everything else
> fully transparent.

| Save as                              | Slot     | Item                                         |
|--------------------------------------|----------|----------------------------------------------|
| `accessory_head_cap_01.png`          | head     | plain baseball cap                           |
| `accessory_head_beanie_01.png`       | head     | knit beanie                                  |
| `accessory_head_sunglasses_01.png`   | head     | oversized sunglasses                         |
| `accessory_head_tourcap_01.png`      | head     | branded tour-guide cap                       |
| `accessory_neck_lanyard_01.png`      | neck     | work lanyard + name tag                      |
| `accessory_neck_scarf_01.png`        | neck     | glamorous statement scarf                    |
| `accessory_prop_dslr.png`            | prop     | DSLR + telephoto, raised                     |
| `accessory_prop_guitar.png`          | prop     | acoustic guitar, held/slung                  |
| `accessory_prop_phone-selfie.png`    | prop     | phone held up filming a selfie               |
| `accessory_prop_ringlight.png`       | prop     | phone-on-gimbal with a small ring light      |
| `accessory_prop_tote-headshots.png`  | prop     | tote bag with headshots poking out           |
| `accessory_prop_souvenir-bag.png`    | prop     | plastic "Hollywood" souvenir bag             |
| `accessory_prop_map.png`             | prop     | rolled map / pointer                         |
| `accessory_prop_coffee.png`          | prop     | to-go coffee cup                             |
| `accessory_costume_mascot-helmet.png`| costume  | robo-hero helmet tucked under one arm        |

---

## Aura is NOT a generated part

The colored glow behind each soul is drawn and tinted **in code** from live
emotional/spiritual state (`auraColor` in `src/soul/appearance.ts`) — don't
generate aura PNGs; they'd be static and wouldn't shift with the sim.

---

## How a soul becomes parts (for the future compositor)

Deterministic per soul id so a character looks identical every load:

- `clothingTag` → `top/top_<tag>_*` (and biases the `bottom/` choice)
- `groomingTag` → `hair/hair_*_<grooming>_*`
- `archetype`   → the defining `accessory/` prop(s) and any faction/costume top
- soul id hash  → base `body/` tone+build, and which numbered variant within a tag

That mapping is small, pure, and belongs next to `deriveAppearance`. Ping me to
wire the compositor once a first set of parts is in the folder.
