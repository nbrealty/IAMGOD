# Create-a-Character — home flow, builder architecture & the full art-prompt library

God reincarnates as a human with no memories. **Create-a-Character (CaC)** is where
the player chooses that human form. This document specifies:

1. the **home page + mode flow** (Sandbox / Story),
2. how CaC **fits the existing engine** (the "bake-on-confirm" architecture),
3. the **shared style contract + alignment templates** every prompt reuses, and
4. **paste-ready art prompts** for the pages and for every part category — eyes,
   brows, nose, mouth, ears, hair, body types, plus separate clothing and accessories.

Everything is authored in the house **chibi-realism** style (see the "Character art
style" block in `CLAUDE.md` and `docs/CHARACTER_PROMPT.md` — this doc references it,
it does not restate it). Old `docs/SPIRIT_PART_PROMPTS.md` / `public/parts/` is the
*legacy* 3/4-angle pixel system — **do not reuse it**; CaC is the current straight-on
chibi-realism look.

---

## 0. TL;DR decisions (the ones that shape everything)

- **Bake-on-confirm, not live paper-doll.** The builder composites layers for the
  *preview*, but on **Confirm** it flattens the stack to a single `front` + `_back`
  PNG that becomes the soul's sprite. The whole renderer (walk-FX leg-slice, uniform
  height via `spriteBounds`, back-facing, contact/cast shadow, outfits/inventory) then
  works **unchanged** — CaC produces exactly what the engine already eats. Identity is
  fixed at "birth," like a real reincarnation; re-customizing = re-bake.
- **Registration by reference, not by coordinates.** AI generators can't hit pixel
  anchors on a blank canvas. So every part is generated **onto a provided alignment
  template** (base body or base head) and delivered keyed — the SPIRIT_PART lesson,
  applied to the current style. Same template → parts stack cleanly.
- **Face cohesion caveat.** Independently-generated eyes/nose/mouth can look "collaged"
  in a painted style. Two mitigations, both used: (a) every face part is drawn on the
  **same base-head template** with the **same light + outline weight**, and (b) each
  face category ships as a *small curated set* (not infinite sliders) so combinations
  stay on-model. Skin tone and build are chosen on the **base body**, not re-tinted.
- **Clothing & accessories stay separate** (as the user asked) and are the categories
  most worth keeping swappable — but they still bake into the final sprite on confirm,
  and post-birth wardrobe changes ride the **existing `OUTFITS`/inventory system**
  (whole-sprite swaps), so nothing new is needed there.

---

## 1. Home page & mode flow

New front-end shell that runs **before** the world mounts (today the app boots
straight into the scene). Route/state machine:

```
TITLE ("I AM GOD")
 ├─ SANDBOX — God Mode (Observe)         → world with controlledId = null (free pan/zoom,
 │                                          observe/drive any existing soul; today's "Observe")
 └─ STORY MODE
     ├─ Create a Character (reincarnate)  → the CaC builder → bakes a soul → enter world driving it
     └─ Select a Soul                     → roster picker (existing ROSTER) → enter world driving it
```

- **Sandbox = God Mode**: the omniscient observer. No avatar; the player is God watching
  the boulevard. This is literally today's `controlledId = null` path, given a front door.
- **Story Mode = incarnated**: God takes a body. Either **build one** (CaC) or **inhabit
  an existing soul**. Both end by handing a `controlledId` to `HollywoodScene`.
- The title/mode screens are their own React views above the canvas; picking a mode
  mounts the world (or the builder) the same way `controlledId` already drives things.

### Page art needed (prompts in §4)

| Key | Purpose |
|---|---|
| `pages/title-bg` | Full-bleed title backdrop (the boulevard at golden hour, the divine POV) |
| `pages/mode-sandbox` | Card art for **Sandbox / God Mode** (an all-seeing eye over the city) |
| `pages/mode-story` | Card art for **Story Mode** (a soul descending into a body) |
| `pages/builder-bg` | Neutral studio backdrop behind the character on the builder screen |

---

## 2. Engine-fit architecture (bake-on-confirm)

### 2.1 The canonical frame

- **1024 × 1536** portrait (2:3). One figure, **straight-on, feet planted**, ~90% of
  frame height, centered, small even margin — the definitive chibi-realism framing.
- Every base body, every overlay part, and both alignment templates are authored at
  **exactly this frame** so they stack pixel-for-pixel.

### 2.2 Two alignment templates (generate these FIRST, keep them)

These are the reference images you attach to every subsequent prompt.

- **`base-body-guide`** — the canonical bald, blank-faced figure (see §5's base-body
  prompt, "Average" build, mid skin) with faint guide marks: shoulder line, waist line,
  hip line, knee line, ankle/feet line, and the neck base. Used to register hair,
  clothing, shoes, tattoos, body accessories.
- **`base-head-guide`** — a **head-and-shoulders crop** of that same figure (bald,
  blank skin-only face) with faint crosshair guides for: **eye-line** (pupils),
  **nose base**, **mouth line**, **ear top/bottom**, and the head centerline. Used to
  register eyes, brows, nose, mouth, ears, glasses, earrings, headwear.

> Rule for every part prompt: *"Attach this template. Align to this exact figure —
> same size, same position, same straight-on angle, same top-light. Output ONLY the
> [part], everything else fully transparent (or flat hot-magenta)."*

### 2.3 Layer stack (back → front)

**FRONT sprite** composites in this order:

1. `hair-back` (long hair behind the shoulders; empty for short styles)
2. `base body` (build + skin; **bald, blank-faced** head + neck + torso + arms + legs + bare feet)
3. `tattoos` (on skin, before clothing)
4. `clothing-bottom` (pants / skirt / shorts)
5. `clothing-top` **or** `dress` (a dress supplies both and suppresses top+bottom)
6. `shoes`
7. `ears`
8. `nose`
9. `mouth`
10. `eyes`
11. `brows`
12. `hair-front`
13. `headwear` (hat / headwrap / durag)
14. `glasses`
15. `jewelry` (earrings at ear anchors, necklace at neck, watch at wrist)

**BACK sprite** is much simpler (no face): `hair-back(full)` → `base-body-back` →
`tattoos-back` → `clothing-bottom-back` → `clothing-top/dress-back` → `shoes-back` →
`headwear-back` → back jewelry. Each clothing/hair/accessory item ships a `_back`
companion (same as every existing sprite needs one).

### 2.4 Bake + wire

- The builder keeps the current selection per layer and draws the stack to an
  **offscreen 1024×1536 canvas** for live preview (front; a small toggle previews back).
- **Confirm** flattens front → `<soulId>.png` and back → `<soulId>_back.png`, writes them
  into the sprite cache (data-URL/blob), and registers the new soul: pushed into the
  roster/engine with a generated `Soul` (see §12), `OUTFITS` default stem = soulId.
- From there it's a normal playable soul: `spriteBounds` measures it, walk-FX slices it,
  `SPRITE_FACES_LEFT` if authored facing left, contact/cast shadow, inventory, etc.
- Post-birth outfit changes = additional baked sprites via the **existing** `OUTFITS`
  system; accessories that toggle (glasses on/off) = baked outfit variants or a second
  bake. **No renderer changes** are required for CaC beyond the builder UI + the bake.

---

## 3. The shared style prefix (prepend to EVERY prompt below)

> **CHIBI-REALISM GAME ASSET** — house style for a god-game in a stylized 2026 Los
> Angeles. A caricatured **oversized chibi head + big expressive face on a fully
> REALISTIC adult body** (~3.5–4.5 heads tall — heads-bigger and shorter than life
> but unmistakably an adult, NEVER a toddler mini). Body rendered with true adult
> anatomy: real muscle (quads, calves, abs, biceps), real curves and build, correct
> hands and feet — honor the build, never slim it. Face is caricature-realism:
> enlarged detailed eyes with painted irises, catchlights and lashes; strong groomed
> brows; full lips; real nose/jaw; contouring, blush, freckles; warm slight confident
> smile. **Bold clean BLACK ink outlines** (heavy outer contour, finer interior lines)
> over **glossy cel-shading blended with airbrushed gradient volume — NOT flat fills**;
> high saturation, high contrast; glossy specular highlights on skin, hair sheen, fabric
> gloss. Photoreal materials (denim, leather, knit, jersey; legible logos/tattoos).
> **Bright, even, gently TOP-LIT; strong rounded form shadows + glossy highlights; NO
> cast ground shadow.** Grounded American streetwear — **absolutely no anime tropes**
> (no sparkle-eyes, no twin-tails, no unnatural hair unless chosen). Straight-on, front-
> facing, near eye-level. Canvas **1024×1536**, flat solid **HOT-MAGENTA** background
> (or transparent) for clean keying.

Then append the section's block + fill the 【SLOTS】.

---

## 4. Page / screen art

### 4.1 Title backdrop — `pages/title-bg`
```
【shared style prefix — but NO figure; this is a SCENE, keep the render style/lighting】
SCENE: a wide, cinematic view of the fictional 2026 Hollywood Blvd district at GOLDEN
HOUR from a slightly elevated, god's-eye vantage — the dimetric billboard boulevard
receding: palms, marquees, neon just warming up, the crowd small below. Sky glowing
amber→rose. Empty lower third for the title lockup. Painterly, warm, reverent, epic.
Flat full-bleed (NOT keyed) — this is a background plate, 1536×1024 landscape and a
1024×1536 portrait crop.
```

### 4.2 Mode card — Sandbox / God Mode — `pages/mode-sandbox`
```
【shared style prefix — icon/emblem, no character】
EMBLEM for "SANDBOX — GOD MODE": a luminous all-seeing eye / radiant sun-disc floating
high above a tiny stylized boulevard, golden light rays fanning down over the city.
Serene, omniscient, watching-from-above. Centered emblem on a deep warm-dusk gradient,
room around it. Square-ish, keyed hot-magenta OR transparent.
```

### 4.3 Mode card — Story Mode — `pages/mode-story`
```
【shared style prefix】
EMBLEM for "STORY MODE": a glowing soul-spark / comet of golden light descending from
the sky toward a waiting human silhouette on the boulevard below — divinity taking a
body. Warm, hopeful, cinematic. Centered on a deep dusk gradient. Keyed hot-magenta OR
transparent.
```

### 4.4 Builder backdrop — `pages/builder-bg`
```
【shared style prefix — SCENE only, no figure】
SCENE: a soft, neutral "creation" studio — a warm dark-to-mid gradient void with a
faint golden floor pool of light where the character will stand, gentle god-rays from
above, a few drifting light motes. Uncluttered, so a full-body character reads clearly
in front of it. Flat full-bleed plate, 1024×1536 portrait (NOT keyed).
```

---

## 5. Base bodies (body types) — the foundation layer

The base body carries **build + skin tone + the bald, blank-faced head**. Everything
else overlays it. Generate the **Average / mid-skin** body first — it is also the
`base-body-guide` template (§2.2). Then the other builds reuse the **identical pose**.

**Build set (MVP — inclusive, honoring real bodies):**
`petite`, `slim`, `average`, `athletic`, `curvy`, `plus`, `muscular`, `tall-lean`.
**Skin set:** `porcelain`, `fair`, `light`, `medium`, `tan`, `brown`, `deep`, `rich-ebony`
(each build generated per skin you want to offer — start with 3–4 skins × all builds,
expand later).

### 5.1 Base body — front — `base/body_<build>_<skin>.png`
```
【shared style prefix】
A single full-body figure, straight-on, feet flat and planted, both arms relaxed and
held a LITTLE AWAY from the torso (so sleeves/edges never clip when clothing overlays),
neutral calm closed-mouth expression. The HEAD is BALD (no hair, no eyebrows) and the
FACE is BLANK — smooth skin only, NO eyes, nose, mouth, or ears drawn (those overlay
later); keep the head/skull shape, brow ridge, cheeks, jaw and neck fully rendered and
top-lit. Wearing ONLY plain neutral undergarments (simple grey sports bra/band top +
briefs) so the body's true shape reads for clothing fitting. Bare hands, bare feet.
BUILD: 【e.g. "athletic — defined shoulders, visible abs, strong quads and calves"】
SKIN: 【e.g. "warm medium-brown, glossy top-lit sheen"】
Centered, small even margin, exact 1024×1536, flat hot-magenta key.
```
> The **first** one you generate (average, mid skin) → also save as `base-body-guide`
> and add faint guide marks per §2.2 before using it as the alignment reference.

### 5.2 Base body — back — `base/body_<build>_<skin>_back.png`
```
【shared style prefix】
Attach the finished FRONT base body. The SAME figure seen from directly BEHIND — same
build, same skin, same size/position/pose, arms slightly out. BALD head from the back
(skull + nape + neck), no face. Same plain neutral undergarments from the back. Back
muscle/curve definition rendered and top-lit. Do NOT mirror any text. Exact 1024×1536,
flat hot-magenta key.
```

---

## 6. Face parts (overlay decals on `base-head-guide`)

Every face part is generated **onto the base-head template** and delivered as a keyed
overlay so it drops onto any base body's head. Attach `base-head-guide` each time and
isolate the part. Keep each category a **small curated set** for cohesion.

### 6.1 Eyes — `eyes/eyes_<style>.png`
```
【shared style prefix — CLOSE-UP overlay, not a full body】
Attach base-head-guide. Draw ONLY the PAIR OF EYES, aligned exactly to the guide's
eye-line and centerline (correct spacing, symmetric), sized for the big chibi face.
Chibi-realism eyes: enlarged but adult (never anime-huge), detailed painted IRISES with
catchlights, defined upper lash line and lashes, subtle lower lid, glossy highlight.
Bold black outline matching the house line weight; top-lit. Everything else fully
transparent. 1024×1536 frame (part sits where it belongs on the head), keyed.
STYLE: 【e.g. "almond, warm brown iris" / "round, hazel" / "hooded, dark brown" /
"upturned, green" / "monolid, deep brown" / "downturned, grey-blue"】
```
Suggested MVP set: `almond-brown, round-hazel, hooded-dark, upturned-green, monolid-brown, wide-blue`.

### 6.2 Eyebrows — `brows/brows_<style>.png`
```
【shared style prefix — overlay】
Attach base-head-guide. Draw ONLY the PAIR OF EYEBROWS just above the guide eye-line,
matched to the head. Strong groomed chibi-realism brows, natural hair strokes, top-lit,
house outline weight. Everything else transparent. Keyed, 1024×1536.
SHAPE/COLOR: 【e.g. "thick straight, black" / "soft arched, brown" / "sharp arched,
dark" / "natural feathered, auburn"】
```

### 6.3 Nose — `nose/nose_<style>.png`
```
【shared style prefix — overlay】
Attach base-head-guide. Draw ONLY the NOSE, centered on the guide centerline with the
base at the guide's nose line. Real, rendered chibi-realism nose (bridge, tip, nostrils)
with soft top-lit form shadow and a glossy highlight on the tip; house outline weight,
kept subtle (interior lines finer than the outer contour). Everything else transparent.
Keyed, 1024×1536.
SHAPE: 【e.g. "straight narrow" / "rounded button" / "broad flat" / "aquiline" /
"upturned"】
```

### 6.4 Mouth / lips — `mouth/mouth_<style>.png`
```
【shared style prefix — overlay】
Attach base-head-guide. Draw ONLY the MOUTH on the guide mouth line, centered. Full
realistic chibi-realism lips with a WARM slight confident closed or barely-parted smile,
painted volume, subtle gloss highlight, defined cupid's bow; house outline weight.
Everything else transparent. Keyed, 1024×1536.
SHAPE: 【e.g. "full, neutral warm smile" / "wide grin, teeth" / "soft small smile" /
"pouty full lips" / "subtle smirk"】  COLOR: 【bare / nude / berry / red gloss】
```

### 6.5 Ears — `ears/ears_<style>.png`
```
【shared style prefix — overlay】
Attach base-head-guide. Draw ONLY the PAIR OF EARS on the head sides between the guide's
ear-top and ear-bottom marks, correct size/placement for the chibi head. Rendered
top-lit ear form, house outline weight (earrings will attach at the lobe later).
Everything else transparent. Keyed, 1024×1536.
STYLE: 【"attached lobe" / "detached lobe" / "small" / "larger"】
```

---

## 7. Hair (front + back layers)

Hair is two layers so it reads in front of the face AND behind the shoulders/back sprite.

### 7.1 Hair front — `hair-front/hair_<style>_<color>.png`
```
【shared style prefix — overlay on the FULL figure frame】
Attach base-body-guide. Draw ONLY the HAIR as seen from the FRONT — crown, hairline,
fringe/part, and any lengths that fall in FRONT of the shoulders — sized to sit on the
bald head exactly, framing (not covering) the face. Chibi-realism hair: bold black
outline, glossy cel-shaded strands with airbrushed volume and sheen highlights, real
texture. Everything else fully transparent. Keyed, 1024×1536.
STYLE: 【e.g. "long loose waves" / "box braids to mid-back" / "short afro" / "high
ponytail" / "buzzcut" / "curtain bangs bob" / "locs" / "slicked bun" / "cornrows"】
COLOR: 【natural black / dark brown / auburn / blonde / grey / dyed 【color】】
```

### 7.2 Hair back — `hair-back/hair_<style>_<color>_back.png`
```
【shared style prefix — overlay】
Attach the finished hair-front + base-body-guide. Draw ONLY the BACK of the SAME
hairstyle/color, sized to the head/back from directly behind (for the back sprite AND
the length that falls behind the shoulders on the front). Same outline/shading/sheen.
Do NOT mirror any part/text. Everything else transparent. Keyed, 1024×1536.
```
> Short styles that don't fall behind the shoulders still need a `_back` (the back of the
> head). Long styles: the portion behind the shoulders shows on the FRONT sprite too, so
> author `hair-back` to include it.

---

## 8. Clothing (separate — tops, bottoms, dresses, shoes)

Overlays fitted to `base-body-guide`. Each item ships a `_back`. A **dress** covers top
+ bottom and suppresses those slots. Arms-slightly-out pose keeps sleeves swappable.

### 8.1 Top — `clothing/top_<name>.png` (+ `_back`)
```
【shared style prefix — overlay】
Attach base-body-guide. Draw ONLY the TOP fitted to this exact torso/arms — natural
drape, wrinkles, and the material's real texture; legible logo/graphic if any. House
outline + glossy cel-shade, top-lit. Sleeves end cleanly (no floating threads).
Everything else (head, lower body, background) fully transparent. Keyed, 1024×1536.
ITEM: 【e.g. "white ribbed tank" / "oversized graphic tee, 'Los Angeles' script" /
"cropped hoodie" / "soccer jersey #10" / "denim jacket" / "silk blouse"】
COLOR/DETAIL: 【…】
```
Back companion: *"…the SAME top from BEHIND, fitted to the back; do not mirror text/numbers."*

### 8.2 Bottom — `clothing/bottom_<name>.png` (+ `_back`)
```
【shared style prefix — overlay】
Attach base-body-guide. Draw ONLY the BOTTOMS fitted to these exact hips/legs — real
drape and material. House outline + glossy cel-shade, top-lit. Everything else
transparent. Keyed, 1024×1536.
ITEM: 【e.g. "blue skinny jeans, ripped knees" / "denim shorts" / "cargo pants" /
"pleated mini skirt" / "wide-leg trousers" / "leggings"】
```
Back companion mirrors the item from behind (no mirrored text).

### 8.3 Dress / one-piece — `clothing/dress_<name>.png` (+ `_back`)
```
【shared style prefix — overlay】
Attach base-body-guide. Draw ONLY the DRESS / JUMPSUIT covering torso AND lower body,
fitted and draped to this exact figure. House outline + glossy cel-shade, top-lit.
Everything else transparent. Keyed, 1024×1536.
ITEM: 【e.g. "slip dress" / "sundress, floral" / "bodycon" / "boho maxi" / "romper"】
```

### 8.4 Shoes — `shoes/shoes_<name>.png` (+ `_back`)
```
【shared style prefix — overlay】
Attach base-body-guide. Draw ONLY the PAIR OF SHOES on the guide's feet, correct
size/placement, real material (leather/canvas/mesh), legible logo if any. House outline
+ gloss, top-lit. Everything else transparent. Keyed, 1024×1536.
ITEM: 【e.g. "white sneakers, swoosh" / "Havaianas flip-flops" / "black boots" /
"heels" / "Converse" / "barefoot → SKIP this layer"】
```

---

## 9. Accessories (separate)

Small overlays at fixed anchors. Toggleable; most ship a `_back` only if visible from
behind (hats do; glasses don't).

### 9.1 Glasses — `accessories/glasses_<name>.png` (face overlay)
```
【shared style prefix — overlay on base-head-guide】
Attach base-head-guide. Draw ONLY the EYEWEAR sitting on the nose/ears at the guide's
eye-line, sized to the chibi face. Real frame + lens material, subtle lens reflection,
house outline, top-lit. Everything else transparent. Keyed, 1024×1536.
ITEM: 【"round wire" / "black rectangular" / "cat-eye" / "aviator sunglasses" / "clout"】
```

### 9.2 Earrings — `accessories/earrings_<name>.png`
```
【shared style prefix — overlay on base-head-guide】
Attach base-head-guide. Draw ONLY the PAIR OF EARRINGS at the earlobe marks (pair with
the chosen ears). Real metal/stone gloss, house outline, top-lit. Everything else
transparent. Keyed, 1024×1536.
ITEM: 【"gold hoops" / "studs" / "dangly" / "small huggies"】
```

### 9.3 Necklace(s) — `accessories/necklace_<name>.png` (+ `_back` if it wraps)
```
【shared style prefix — overlay on base-body-guide】
Attach base-body-guide. Draw ONLY the NECKLACE(S) at the neck/collarbone, resting
naturally. Real bead/metal gloss (e.g. layered Candomblé beads, gold chain, pendant),
house outline, top-lit. Everything else transparent. Keyed, 1024×1536.
ITEM: 【…】
```

### 9.4 Headwear — `accessories/hat_<name>.png` (+ `_back`)
```
【shared style prefix — overlay on base-body/​head guide】
Attach base-head-guide. Draw ONLY the HEADWEAR sitting on the crown/hairline, correct
size, real material, legible logo. House outline + gloss, top-lit. Everything else
transparent. Keyed, 1024×1536. (Provide a `_back` — hats read from behind.)
ITEM: 【"snapback" / "beanie" / "durag" / "headwrap" / "bucket hat" / "cowboy"】
```

### 9.5 Wrist / hands — `accessories/wrist_<name>.png`
```
【shared style prefix — overlay on base-body-guide】
Attach base-body-guide. Draw ONLY the WATCH/BRACELET(S) at the guide wrist(s), real
metal/leather gloss, house outline, top-lit. Everything else transparent. Keyed.
ITEM: 【"gold watch" / "stack of bangles" / "beaded bracelet"】
```

### 9.6 Tattoos — `accessories/tattoo_<name>.png` (skin layer; + `_back`)
```
【shared style prefix — overlay on base-body-guide, drawn on SKIN under clothing】
Attach base-body-guide. Draw ONLY the TATTOO(S) on the guide skin at 【placement:
"left forearm sleeve" / "right thigh rose" / "chest script" / "back piece"】, following
the limb's form/shading, house-consistent ink line. Everything else transparent. Keyed.
MOTIF: 【"rose + palm" / "'Los Angeles' script" / "fine-line florals" / "tribal"】
```

---

## 10. Keying, registration & folders (pipeline)

- **Folders:** raw in `art-src/cac/<category>/`; keyed finals in
  `public/cac/{pages,base,tattoos,hair-back,hair-front,eyes,brows,nose,mouth,ears,clothing,shoes,accessories}/`.
- **Naming:** `<category>_<descriptor>[_<variant>][_back].png` (lowercase-kebab), e.g.
  `hair_box-braids_black.png`, `top_graphic-tee-la.png`, `eyes_almond-brown.png`.
- **Keying:** same magenta flood-fill + connected-component crop as the rest of the
  pipeline (see `CLAUDE.md` → Asset pipeline). Overlays with transparent fields skip the
  flood-fill; just trim to the 1024×1536 frame so alpha registration is preserved —
  **never re-center/crop an overlay** or it loses alignment.
- **Registration check:** after keying a new part, composite it over `base-body-guide`
  (or `base-head-guide`) at 100% and eyeball the fit before batching variants.

---

## 11. Builder UI/UX (the CaC screen)

- Left/right: the live character on `pages/builder-bg`, front by default with a
  **↺ turn** toggle to preview the back.
- Bottom: a **category rail** — `Body · Skin · Eyes · Brows · Nose · Mouth · Ears ·
  Hair · Top · Bottom · Dress · Shoes · Glasses · Earrings · Necklace · Headwear ·
  Wrist · Tattoos`. Tapping a category opens a horizontal **thumbnail strip** of that
  category's keyed parts; tap to equip → the preview recomposites instantly.
- **🎲 Randomize** (weighted, on-model), **Reset**, and **Confirm**.
- **Name + pronoun** field; optional **starting outfit** presets (a curated bundle of
  the clothing/accessory layers) so a player can one-tap a "look."
- Confirm → bake front+back (§2.4) → drop into the world driving the new soul.

The builder reuses the **same layer compositor** the bake uses (draw stack to an
offscreen canvas), so preview and final are pixel-identical.

---

## 12. Data model + engine wiring

- **New soul from CaC:** synthesize a `Soul` (see `src/soul/types.ts`) — God-incarnate
  defaults: `initiationLevel: 0`, blank/again-fresh needs, `axe: 0`, `money:
  DEFAULT_MONEY`, a chosen name/pronoun; appearance tags derived from the picked layers.
  Add it to the roster/engine and set it `controlledId`.
- **Sprite registration:** the baked `front`/`_back` blobs register under the new
  `soulId` stem in the renderer's sprite cache; `OUTFITS` gets a default entry
  (`stem = soulId`). Everything downstream (bounds, walk-FX, back-facing, shadows,
  inventory) is unchanged.
- **`SPRITE_FACES_LEFT`:** the CaC pose is authored facing RIGHT (art-faces-right
  convention), so new CaC souls do **not** go in that set.
- **Persistence:** baked sprites are session/local (IndexedDB/localStorage blob) until a
  save system exists; the layer selection (a small JSON of chosen part ids) is the true
  save — re-bake from it on load. (Store the recipe, not just the pixels.)

---

## 13. Suggested build order

1. **Home/mode shell** (code-only, no art blockers): TITLE → Sandbox / Story → Select.
   Wire Sandbox = `controlledId:null`, Select = existing roster. Ship it.
2. **Alignment templates** (`base-body-guide`, `base-head-guide`) + **one full test
   character** end-to-end (1 body + 1 of each face part + hair + a top/bottom/shoes) →
   prove the composite stacks cleanly and the **bake→playable** path works.
3. **Builder UI** against that minimal library (categories, strips, randomize, confirm).
4. **Batch the libraries** (more builds/skins, then eyes/hair/clothing/accessory sets).
5. Wardrobe post-birth via existing `OUTFITS`/inventory.

Start with step 1 (pure code) so there's a real front door while the art library grows.
```
```
