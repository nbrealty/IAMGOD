# Overture Hollywood — walk-in plaza art (drop here)

Art for the **first walk-in building**: Overture Hollywood becomes a real 2.5D
courtyard you walk into through the gate — no loading. Drop generated PNGs in
this folder (`public/overture/`); they serve at `/overture/<stem>.png`. I key +
crop + place each at the CH scale below with no code change on your side.

Prompts live in [`docs/OVERTURE_PROMPTS.md`](../../docs/OVERTURE_PROMPTS.md).
Generate ONE first (the gate), lock the look, then do the rest "same style,
camera angle, line weight, and lighting."

`CH` = character-height (1 CH = 84 in-game units = one standing character).
White / transparent / magenta backgrounds all fine — I key them.

## Filename map (priority → file → what it is · size)

| Priority | Save as | What it is | Size |
|---|---|---|---|
| **MUST** | `overture-gate.png` | Boulevard gateway facade — **central arch is a TRUE open hole you walk through** (leave the inside of the arch blank so it keys transparent) | 6 CH · ~2:1 wide |
| **MUST** | `overture-court-back.png` | The back "OVERTURE HOLLYWOOD" building that terminates the courtyard (seen through the arch) | 6 CH · ~1.6:1 |
| SHOULD | `overture-court-side.png` | One side of the court: stacked shop/café terraces (I mirror it for both the CAFE OVERTURE and BOUTIQUE sides) | 5 CH · ~1.3:1 |
| SHOULD | `overture-elephant-column.png` | Babylon elephant-topped column (the *Intolerance* gatepost) — isolated prop, I mirror it for the pair | ~5 CH tall |
| NICE | `overture-stair.png` | Grand ceremonial staircase rising into the court — isolated prop | ~2 CH tall, wide |
| NICE | `overture-banner.png` | A single hanging event banner (LIVE EVENTS / FILM ART MUSIC) — isolated prop | ~2 CH |

## Reuse — do NOT regenerate these (already in `public/`)
`props/fountain.png` (court fountain) · `props/palm.png` · `props/planter.png` ·
`props/streetlamp.png` · `props/string-lights.png` · `props/umbrella.png` ·
`tiles/plaza.jpg` (court terrazzo floor) · the 38 souls/peds as court occupants.

> The **gate** is the keystone: its arch must be an empty, see-through opening
> (nothing painted inside it) so the real courtyard behind shows through and the
> player can walk from the sidewalk straight into the plaza.
