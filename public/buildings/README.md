# Buildings — facade art (placed)

Keyed + cropped building facades for the Hollywood & Highland square. **All 14
landmarks below are done and live in the scene** — background removed, cropped
tight, downscaled/optimized, and composited in their fixed slots at
character-height (CH) scale (see `src/game/sceneData.ts`). Each renders via the
`sprite` hook on its slot; the renderer loads `/buildings/<stem>.png`.

The raw phone uploads (UUID-named originals + the 2 filler sheets) were removed
from this folder to keep the deploy lean — they live in git history at commit
`3916f37` and can be pulled back for re-keying or slicing.

See [`docs/BUILDING_PROMPTS.md`](../../docs/BUILDING_PROMPTS.md) for the prompts,
style, perspective, and the CH scale each was drawn to.

## To drop in a NEW / replacement facade

Save it as `<stem>.png` from the map below (or any name — I can recognize the
landmark and rename it). White, black, or transparent backgrounds all work; I
key + crop + downscale it and it appears in its slot with no code change.

## Filename map (fictional name → file → real basis · size) — ✅ all placed

| Save as | Building | Based on | Size |
|---|---|---|---|
| `jade-pagoda.png` | The Jade Pagoda Theatre | Chinese Theatre | 7 CH |
| `overture-hollywood.png` | Overture Hollywood | Ovation complex | 6 CH |
| `vantage-theatre.png` | The Vantage Theatre | Dolby | 6 CH |
| `wonderland-theatre.png` | The Wonderland Theatre | El Capitan | 6.5 CH |
| `madame-rousseau.png` | Madame Rousseau's Wax Museum | Madame Tussauds | 5 CH |
| `blackwood-odditorium.png` | Blackwood's Odditorium | Ripley's | 5 CH |
| `thunderclap-cafe.png` | Thunderclap Rock Cafe | Hard Rock Cafe | 4.5 CH |
| `meridian-hotel.png` | Hotel Meridian Hollywood | W Hollywood | 10 CH |
| `apex-records.png` | The Apex World Records Museum | Guinness | 5 CH |
| `crescendo-hotel.png` | The Crescendo Hotel | Loews | 11 CH |
| `sovereign-hotel.png` | The Sovereign Hollywood Hotel | Roosevelt | 7 CH |
| `marchetti-vane-grill.png` | Marchetti & Vane Grill | Musso & Frank | 4 CH |
| `reel-page-bookshop.png` | The Reel Page Bookshop | Larry Edmunds | 3.5 CH |
| `glamour-archive.png` | The Glamour Archive Museum | Hollywood Museum | 5 CH |

Generic / filler (name freely, e.g. `souvenirs.png`, `food-slice.png`,
`tour-kiosk.png`, `parking.png`, `apartment-01.png`, `backdrop-01.png`):
storefront 3 CH · food 3 CH · kiosk 2 CH · parking 5 CH · apartment 4 CH ·
backdrop dim.

`CH` = character-height (1 CH = 84 in-game units = one standing character).
Final in-game size is set in code from the CH value, not from the file's pixels.
