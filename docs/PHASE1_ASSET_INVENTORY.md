# Phase 1 — Asset Inventory

Every incoming front-end asset, identified by **dimensions + visual inspection** (upload
renamed most of them). Raw sources currently live in `public/cac/pages/` (title/mode/
creator UI) and `public/cac/base/` (female body bases). Phase-1 implementation moves raws
to `public/assets/source/` and produces cleaned derivatives under `public/assets/{title,
mode-select,creator,ui,characters/base}/`.

**Alpha reality:** verified from PNG colortype bytes. `colortype 6/4` = real RGBA; `colortype
2` = RGB with a **baked checkerboard** (fake transparency — must be chroma/luma keyed); JPEG
= opaque. This is the spec's central warning, and it is real for ~half the files.

## Legend
- **Alpha**: `RGBA` (real) · `BAKED` (printed checker/white, needs keying) · `OPAQUE` (bg art)
- **Action**: `USE` · `KEY` (remove baked bg) · `CROP` · `NINE-SLICE` · `WEBP` (convert opaque→webp) · `ARCHIVE` (keep, don't ship) · `IGNORE`

---

## A. Title screen

| Raw file | Dims | Fmt / Alpha | Is (spec #) | Canonical | Action |
|---|---|---|---|---|---|
| `title-bg-desktop-src.png` | 1536×1024 | PNG OPAQUE | #1 desktop title bg (Hollywood golden hour) | `title/title-bg-desktop.webp` | WEBP, keep raw for ultrawide focal |
| `photo-3.png` | 941×1672 | PNG OPAQUE | #2 mobile title bg (portrait Hollywood) | `title/title-bg-mobile.webp` | WEBP |
| `photo.png` | 1448×1086 | PNG **BAKED** | #3 wide "I AM GOD" logo | `title/iamgod-logo-wide.png` | KEY (preserve gold/white speculars — no white-threshold), CROP, RGBA |
| `spinner.png` | 1536×1024 | PNG **RGBA** | #5 brand mark (eye/sun) — cleanest | `ui/brand-mark.png` + `ui/loading-sigil.png` | CROP tight to true center (must rotate w/o wobble), derivatives |
| `photo-2.png` | 1254×1254 | PNG BAKED | #5 medallion (dup of spinner) | — | IGNORE (spinner is cleaner) |
| `IMG_36598A88….jpeg` | 1536×1024 | JPEG BAKED(white) | #7 desktop god-rays burst | `title/title-god-rays-desktop.png` | KEY (luma→alpha), soft falloff, no rect edge |
| `IMG_6578.png` | 1920×1080 | PNG **RGBA** | vertical god-ray beam (bonus) | `title/title-god-beam.png` | USE (optional extra ray) |
| `photo-4.png` | 941×1672 | PNG BAKED(white) | #8 mobile god-rays | `title/title-god-rays-mobile.png` | KEY |
| `IMG_6572.png` | 1920×1080 | PNG **RGBA** | #9 gold dust | `title/title-gold-dust-desktop.png` | USE as-is (do NOT re-key) |
| `IMG_6573.png` | 1920×1080 | PNG **RGBA** | #10 soul sparks | `title/title-soul-sparks-desktop.png` | USE as-is |
| `IMG_6574.png` | 1920×1080 | PNG **RGBA** | #11 vignette | `title/title-vignette-desktop.png` | USE as-is |
| `photo-6.png` | 1672×941 | PNG BAKED(white) | #12 haze | `title/title-haze-desktop.png` | KEY, very low opacity |
| `photo-5.png` | 1672×941 | PNG BAKED(black) | #13 neon **source sheet** | `title/neon-accent-*.png` | Extract a FEW pieces only; else omit |
| `road-glow-desktop-src.png` | 1672×941 | PNG BAKED | #14 road-light glow | `title/title-road-glow-desktop.png` | KEY, align VP to bg boulevard |
| `photo-7.png` | 2172×724 | PNG BAKED | #15 button frame (Art Deco) | `ui/button-frame-{left,center,right}.png` | KEY + NINE-SLICE (don't stretch gems/corners) |

**Missing:** #4 stacked mobile logo (only a low-res crop exists in the concept sheet). Temporary:
render the wide logo scaled on mobile; hot-swap when the real stacked logo arrives.

## B. Mode select

| Raw file | Dims | Fmt / Alpha | Is (spec #) | Canonical | Action |
|---|---|---|---|---|---|
| `mode-select-bg-desktop-src.png` | 1920×1080 | PNG OPAQUE | #16 mode-select bg (plum dusk) | `mode-select/mode-select-bg-desktop.webp` | WEBP |
| `mode-sandbox-card-src.jpeg` | 1024×1536 | JPEG OPAQUE | #17 Sandbox / God Mode poster | `mode-select/mode-sandbox-card.webp` | WEBP, keep intact (baked title is design) |
| `mode-story-card-src.jpeg` | 1024×1536 | JPEG OPAQUE | #18 Story Mode poster | `mode-select/mode-story-card.webp` | WEBP, keep intact |
| (derive from `photo-3.png`) | — | — | #19 mobile mode bg | `mode-select/mode-select-bg-mobile.webp` | Darken/plum-tint the portrait Hollywood |
| `mode-cards-composite-ALT-src.png` | 1024×1536 | PNG | superseded 2-poster+bg composite | — | ARCHIVE |

Accessible labels (NOT from baked poster text): "Sandbox God Mode" / "Story Mode" + the
code-rendered descriptions in the spec §V.E.

## C. Character creator

| Raw file | Dims | Fmt / Alpha | Is (spec #) | Canonical | Action |
|---|---|---|---|---|---|
| `IMG_E3A69570….jpeg` | 1536×1024 | JPEG OPAQUE(dark) | #21 desktop temple stage | `creator/creator-stage-desktop.webp` | WEBP |
| `creator-bg-mobile-src.jpeg` | 1024×1536 | JPEG OPAQUE | #20 mobile creator chamber (clean beam+floor) | `creator/creator-bg-mobile.webp` | WEBP (preferred) |
| `creator-bg-mobile-alt-columns-src.png` | 1024×1536 | PNG | #20 alt (columns/sigil) | `creator/creator-bg-mobile-alt.webp` | ARCHIVE / optional |

## D. Do-not-use (archive only)

- `CONCEPT-SHEET-9up-DO-NOT-USE.png` — 9-up concept board (low-res previews) — **IGNORE**
- `mode-cards-composite-ALT-src.png` — superseded — **ARCHIVE**

---

## E. Female body bases (`public/cac/base/`) — the creator body library

All **1024×1536** on **flat hot-magenta** (keyable). 6 builds × 3 skins, front + `_back`.
Style is on-model chibi-realism (bald, blank face, grey undergarments, arms slightly out).
Derivatives: chroma-key magenta → transparent PNG (despill magenta from skin/outlines),
under `characters/base/`.

Builds: `petite, slim, average, athletic, curvy, plus` · Skins: `light, medium, deep`.

**Pairs present & clean:** athletic·{light,medium,deep}, average·{light,medium,deep},
slim·{light,medium}, curvy·{light,deep}, plus·{light,medium,deep}, petite·deep.

**Issues to fix in prep:**
| Item | Problem | Fix |
|---|---|---|
| `body_petite_light_and_back.jpeg` | front+back packed side-by-side, half-scale | split → `petite_light` + `_back`, rescale to fill frame |
| `body_petite_medium_and_back.jpeg` | same | split → `petite_medium` + `_back`, rescale |
| `body_curvy_medium.jpeg` (front) | **missing** (only `_back` exists) | disable curvy·medium until front generated |
| `body_slim_deep.png` | 2.4 MB PNG (rest are JPEG) | convert to keyed PNG derivative like the rest |

**Registration note (for later face phase, not Phase 1):** head size/vertical position
drifts across builds (~100 px). Phase 1 only swaps whole body PNGs, so it's unaffected —
but the face phase needs a per-build head-anchor table (auto-measured).

**Default base** (Reset target): `average` · `medium`.
