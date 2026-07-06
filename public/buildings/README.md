# Buildings — drop-in facade art

Generated building facades for the Hollywood & Highland square. Drop the raw
generated images straight in here — **backgrounds are fine** (white /
checkerboard / transparent all work); I key + crop them the same way I do the
character sprites, then place each at its correct in-game scale.

See [`docs/BUILDING_PROMPTS.md`](../../docs/BUILDING_PROMPTS.md) for the prompts,
style, perspective, and the character-height (CH) scale each was drawn to.

## How to add them

Put your phone's `building` folder contents here (`public/buildings/`). Easiest
path if you're on your phone: rename them to the filenames below so I can map
each one automatically. If renaming 15 files is a pain, just dump them with
whatever names — I can recognize each landmark and rename them when I wire them
in; only cost is you telling me "these are all of them."

## Filename map (fictional name → file → real basis · size)

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
