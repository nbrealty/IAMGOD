# Parts — modular mix-and-match character art

This is the **layered sprite library**. Instead of one finished PNG per soul,
a character is composited in code from stacked transparent layers:

```
aura (code-tinted, drawn behind)  ← already handled by the renderer
└ base body        e.g. body/body_tan_a.png
  └ bottom         e.g. bottom/bottom_jeans-worn_01.png
    └ top          e.g. top/top_loud-curated_01.png
      └ shoes      e.g. shoes/shoes_sneakers-clean_01.png
        └ hair     e.g. hair/hair_short-crop_maintained_01.png
          └ accessory(s)  e.g. accessory/accessory_prop_dslr.png
```

A dozen tops × a dozen hairstyles × a handful of bodies, bottoms, and props =
thousands of distinct-looking NPCs from ~50 hand-generated assets. See
[`docs/SPIRIT_PART_PROMPTS.md`](../../docs/SPIRIT_PART_PROMPTS.md) for the
prompts and the workflow that keeps every part aligned.

> A single finished `public/spirits/<id>.png` still wins if present (hero art).
> The part compositor is the fallback for everyone else, and the code-drawn
> figure is the fallback under *that*.

## The one rule that makes this work: registration

Every part must be drawn on the **same 512×512 canvas, in the same canonical
pose, at the same position**, with everything else transparent — otherwise the
hair won't sit on the head and the shirt won't sit on the torso. The prompt doc
enforces this by having you generate one **base body** first and then align
every other layer to that exact reference image.

## Folders & filename convention

The slot lives in the folder **and** the filename prefix, so the code can pick a
part by tag without opening the file:

| Folder         | Filename pattern                          | Example                                  |
|----------------|-------------------------------------------|------------------------------------------|
| `body/`        | `body_<tone>_<build>.png`                 | `body_deep_b.png`                        |
| `hair/`        | `hair_<style>_<grooming>_NN.png`          | `hair_afro_natural_maintained_01.png`    |
| `top/`         | `top_<clothingTag>_NN.png`                | `top_aspirational-curated_01.png`        |
| `bottom/`      | `bottom_<type>_NN.png`                    | `bottom_chinos_01.png`                   |
| `shoes/`       | `shoes_<type>_NN.png`                     | `shoes_boots-worn_01.png`                |
| `accessory/`   | `accessory_<slot>_<name>.png`             | `accessory_prop_guitar.png`              |

`<clothingTag>` and `<grooming>` use the **exact strings** the soul engine
already emits in `src/soul/appearance.ts`, so the future compositor maps a soul
straight to its parts:

- **clothingTag** → picks the `top/` (and biases `bottom/`): `worn`,
  `practical`, `authentic-casual`, `quiet-curated`, `loud-curated`,
  `aspirational-curated`, `trend-curated`, `ironic-curated`, `authentic`.
- **groomingTag** → picks the `hair/` variant: `unkempt`, `minimal`,
  `maintained`, `casual`.
- **archetype** → picks the defining `accessory/` prop(s) (camera, guitar,
  ring-light, tour cap, mascot helmet…).
- **skin tone + build** → chosen deterministically per soul id so a character
  looks the same every load.

Accessory `<slot>` is one of: `head` (caps, sunglasses), `neck` (lanyard,
scarf), `prop` (held items — camera, guitar, phone, bag), `costume` (mascot
pieces, etc.).

## Spec (same as full spirits)

Transparent PNG, ~512×512, chibi at the canonical pose, warm daylight from
upper-left, clean pixel-art / cel shading, no cast shadow, no anime tropes.
Nothing in the frame except the one part.
