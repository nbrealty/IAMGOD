# Character prompt — reusable "chibi-realism" likeness sprite

Paste-ready template for turning a real person (or an original character) into a
game sprite in our house **chibi-realism** style (see the "Character art style"
section in `CLAUDE.md`). Attach **1–3 clear reference photos** of the person (a
straight-on face shot + a full-body shot works best), then fill the three slots:
`NAME`, `WEARING`, `POSE / EXPRESSION`. Leave the STYLE and LIKENESS blocks
untouched every time — they keep the whole cast on-model.

---

## Front view (the main prompt)

```
CHIBI-REALISM CHARACTER SPRITE — a likeness of a real person, for a god-game set
in a stylized 2026 Los Angeles. Match the attached reference photo(s).

STYLE (do not deviate) — "chibi mixed with realism":
A single full-body figure in a caricatured chibi proportion — an OVERSIZED head
with a big, expressive face on a body about 3.5–4.5 heads tall (shorter and
heads-bigger than real life, but clearly an adult, NEVER baby/toddler-proportioned).
The BODY is rendered with full realistic adult anatomy — real muscle definition
(quads, calves, abs, biceps), real curves and build, correct hands and feet. Bold
clean BLACK ink outlines (heavy outer contour, finer interior lines) over rich
glossy cel-shading blended with airbrushed gradient volume — NOT flat fills. High
saturation, high contrast, punchy color; specular highlights on skin, hair sheen,
and fabric gloss. Photoreal material detail — denim, leather, knit, jersey fabric,
studs, chains, jewelry, watches — and any logos, crests, or tattoos rendered
legibly. Figure standing, feet planted, FRONT-FACING near eye-level (straight-on),
centered on a FLAT SOLID HOT-MAGENTA background with a small even margin. Bright,
even, gently top-lit; strong rounded form shadows plus glossy highlights; NO cast
shadow on the ground. Grounded, realistic American styling — ABSOLUTELY NO anime
tropes (no oversized sparkling anime eyes, no twin-tails, no unnatural hair colors
unless the real person dyes theirs). Square-ish tall canvas, ~1024 tall.

LIKENESS (top priority — the sprite must be UNMISTAKABLY this person):
Keep the reference person's real, identity-defining features even inside the
caricature — face shape (round / oval / square / long, jawline, chin), eye shape
and spacing, nose and mouth shape, eyebrows, real skin tone, and their actual
hairstyle, hair texture, hair color, and hairline. Preserve their real BODY BUILD
and proportions — slim, athletic, broad, curvy, heavyset, tall or short — plus any
signature details (glasses, facial hair, freckles, moles, piercings, tattoos,
jewelry they always wear). Do NOT beautify, slim down, lighten skin, or generic-ify
the face. A friend should recognize them instantly.

NAME: 【NAME】

WEARING: 【full outfit — top, bottom, shoes, and any accessories: colors, logos,
jewelry, hat, bag, watch】

POSE / EXPRESSION: 【stance + mood — e.g. "hand on hip, confident slight smile" /
"hands in pockets, relaxed" / "mid-wave, big warm smile" / "arms crossed, smirk"】
```

---

## Back view (companion — run after you like the front)

The engine needs a matching `_back.png` for every character so they render
correctly walking away. Attach the finished FRONT image, then run:

```
Now the SAME chibi-realism character, SAME outfit, hair, build, colors, scale, and
style — but seen from directly BEHIND (back of the head and body facing the camera,
face not visible). Same flat solid hot-magenta background, same straight-on
eye-level framing, feet planted, same lighting, no ground shadow. Keep any
back-of-outfit details accurate (hood, backpack, jersey number/name, hairstyle,
back tattoos). Do NOT mirror or flip any text, numbers, or logos.
```

---

## After generating

Key + crop each result and save into `public/spirits/` as `<stem>.png` (+
`<stem>_back.png`), then register the look in `OUTFITS` (`src/game/outfits.ts`) per
the outfits/wardrobe spec in `CLAUDE.md`. Uniform height, walk-FX, leg-blur, and
back-facing are all automatic once the stem exists.
