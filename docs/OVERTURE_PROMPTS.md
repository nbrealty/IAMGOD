# Overture Hollywood — walk-in plaza art prompts

Paste-ready prompts for the **first walk-in building**. Overture Hollywood
becomes a real 2.5D courtyard you walk into through the gate — seamlessly, no
loading. Same workflow as the other art: generate the **gate first**, lock the
look, then do the rest referencing "same style, camera angle, line weight, and
lighting as the gate." Drop results in `public/overture/`.

Two style families are used here (same two we always use):

- **FACADES** use the building style (chunky "toy architecture", front-facing
  from a slightly elevated 3/4 HIGH ANGLE, bold dark outlines, warm daylight).
- **PROPS** use the isolated style (single subject on flat **#FF00FF magenta**,
  **neutral even daylight — never bake night or heavy shadows**, the day-night
  engine relights everything).

`CH` = character-height (1 CH = 84 in-game units = one standing character). Draw
an honest normal-height ground-floor door and let the building tower by the CH
listed. You do NOT need to match canvas sizes between images.

---

## MASTER FACADE STYLE PREFIX (prepend to every FACADE prompt)

> Chibi-style building sprite for a stylized 2026 Hollywood Boulevard god-game,
> matching a cast of chunky painted chibi/caricature characters. A SINGLE
> building, front-facing facade, straight-on but seen from a slightly elevated
> 3/4 HIGH ANGLE (a raised camera looking down the street) so the flat rooftop
> edge is just visible above the facade — no steep isometric, no big side wall.
> Chunky, slightly exaggerated "toy" architecture: thick window frames,
> oversized doors, fat readable signage, softened corners. Clean crisp painted /
> cel-shaded style with bold dark outlines, warm saturated daytime palette, soft
> warm sunlight from the upper-left, subtle grime and sun-faded wear (glamorous
> but a little gritty). Big bold READABLE signage is the focal point. Fully
> transparent background (or flat pure white), no ground, no cast shadow, no sky,
> no people, no cars. Whole building in frame with a small margin. Include a
> normal-height ground-floor entrance for scale. The building is:

## ISOLATED PROP PREFIX (prepend to every PROP prompt)

> Single game prop in the same chunky painted cel-shaded "toy" style as the
> buildings and chibi cast — bold dark outlines, warm saturated palette, soft
> warm sunlight from the upper-left, in NEUTRAL EVEN DAYLIGHT (a runtime
> day-night engine re-lights it — do NOT bake night ambient or heavy cast
> shadows). Single subject, centered, full and uncropped, isolated on a plain
> flat #FF00FF magenta background, no ground, no cast shadow off the edges, no
> glow past the silhouette, even margins. The prop is:

---

## FACADES

### `overture-gate.png` — Boulevard gateway (WALK-THROUGH) — 6 CH · very wide ~2:1  ★ generate first
> [MASTER FACADE PREFIX] the monumental Art-Deco / neo-Babylonian ceremonial
> GATEWAY of OVERTURE HOLLYWOOD facing the boulevard: a tall symmetric
> cream-sandstone facade with a huge central archway, "OVERTURE HOLLYWOOD" in
> bold gold Art-Deco letters across the top of the arch, flanking bas-relief
> pilasters and stepped Deco massing, a vertical "SHOP" blade sign, tall poster
> banners ("LIVE MUSIC", "HOLLYWOOD STYLE"), rooftop café balconies with
> umbrellas, and glass storefronts tucked under the wings — "CAFE OVERTURE" on
> the left ground floor, "BOUTIQUE" on the right.
> **CRITICAL — the central archway MUST be a TRUE OPEN PASSAGE:** the entire area
> inside the arch is EMPTY and OPEN — fill it with flat plain background (pure
> white, or the magenta key color) so it can be made fully transparent. Do NOT
> paint anything inside the arch — no courtyard, no plaza, no palms, no fountain,
> no sky, no doors, no inner gate — it must be a clean see-through hole the
> player walks through. Grand, welcoming, perfectly symmetric.

### `overture-court-back.png` — Back plaza building (court terminus) — 6 CH · ~1.6:1
> [MASTER FACADE PREFIX] the SECOND, rear "OVERTURE HOLLYWOOD" building that
> closes the far end of the open-air courtyard — the one you see framed through
> the front arch: a symmetric cream-sandstone multi-level facade with stacked
> retail terraces and balconies, warm-lit glass storefronts on the ground level,
> a central "OVERTURE HOLLYWOOD" sign, hanging event banners ("LIVE EVENTS",
> "FILM · ART · MUSIC"), and Deco/neo-Babylonian bas-relief trim. It reads as the
> grand backdrop of the plaza, a little less busy than the front gate.

### `overture-court-side.png` — Court side terraces (mirror both sides) — 5 CH · ~1.3:1
> [MASTER FACADE PREFIX] one side wall of an open-air Hollywood courtyard: a long
> run of stacked 2–3 level retail terraces in cream sandstone — ground-floor
> glass shopfronts and a café with outdoor tables and umbrellas, upper balconies
> with railings and potted palms, small blade signs and hanging banners. Designed
> to line the LEFT side of the court (it will be mirrored for the right side), so
> keep it fairly symmetric top-to-bottom and readable as a repeating terrace wall.

---

## PROPS

### `overture-elephant-column.png` — Babylon elephant column — ~5 CH tall
> [ISOLATED PROP PREFIX] a tall ceremonial Babylonian column/plinth topped by a
> large rearing ELEPHANT statue (inspired by the 1916 film "Intolerance" set that
> the real courtyard is based on): cream sandstone with neo-Babylonian bas-relief
> and lotus/palmette carving, the elephant reared up on its hind legs on the
> pedestal top, trunk raised. Tall and monumental, a vertical gatepost landmark.

### `overture-stair.png` — Grand ceremonial staircase — ~2 CH tall, wide
> [ISOLATED PROP PREFIX] a wide grand ceremonial staircase of cream stone steps
> rising away from the viewer toward the courtyard, low ornate Art-Deco
> balustrades down each side with lamp finials, seen from the same slightly
> elevated 3/4 high angle so you read the run of steps going up and back. Symmetric.

### `overture-banner.png` — Hanging event banner — ~2 CH
> [ISOLATED PROP PREFIX] a single tall vertical hanging fabric event banner for
> the courtyard, deep jewel-tone (purple or crimson) with gold Art-Deco border
> and a bold star, reading "LIVE EVENTS" (or "FILM · ART · MUSIC"), a little
> wind-rippled, with a simple top rod. Hangs flat, front-facing.

---

## After you generate
Drop the PNGs in `public/overture/` (any bg — white/transparent/magenta) and tell
me which is which. I key + crop + place them at the CH scale, wire the gate as a
walk-through opening, carve the plaza pocket behind Overture, and build the court
on the existing y-sorted pass so you walk in with no loading.
