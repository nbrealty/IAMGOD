# Spirits — drop-in character art

This folder holds the chibi "spirit" sprite for each named soul on the
Hollywood & Highland block. The renderer auto-loads them at runtime; until a
file exists, that character falls back to the code-drawn placeholder figure
(no broken-image icons, nothing to wire up).

## How to add art

1. Generate the image in ChatGPT (or any tool) using the matching prompt in
   [`docs/SPIRIT_PROMPTS.md`](../../docs/SPIRIT_PROMPTS.md).
2. Save it as a **transparent PNG** named exactly `<soulId>.png` (see the table
   below — lowercase, no spaces).
3. Drop it in this folder (`public/spirits/`) and commit. It's served at
   `/spirits/<soulId>.png` and appears in the game on the next load.

The moment a PNG lands here, that soul's real art replaces the placeholder with
zero code changes. You can add them one at a time.

## Spec

| Property     | Value                                                              |
|--------------|-------------------------------------------------------------------|
| Format       | PNG, **transparent background** (alpha), no drop shadow            |
| Size         | ~512 × 512 px, square canvas, figure centered                      |
| View         | Single **3/4 high-angle** chibi, front-facing, matching the dimetric camera |
| Proportions  | Chibi — head roughly 1/2 to 1/3 of total height                    |
| Framing      | Full body, feet near the bottom edge, small margin all around      |
| Lighting     | Warm daylight from upper-left, consistent across all 12            |
| Style        | Clean pixel art / crisp cel shading — **no anime tropes**          |

Keep scale and lighting consistent across all twelve so they read as one cast
standing on the same street.

## Filenames

| Save as        | Soul                | Archetype                       |
|----------------|---------------------|---------------------------------|
| `danny.png`    | Danny Rios          | Costumed Street Performer       |
| `trish.png`    | Trish Anderson      | Tourist                         |
| `frank.png`    | Frank Castellano    | Paparazzi                       |
| `vivian.png`   | Vivian Laurent      | Faded Star                      |
| `bailey.png`   | Bailey Okafor       | Industry Aspirant               |
| `marcus.png`   | Marcus Webb         | Local Commuter (rideshare)      |
| `priya.png`    | Priya Chandra       | Local Worker (souvenir clerk)   |
| `hank.png`     | Hank Torres         | Local Worker (tour guide)       |
| `sasha.png`    | Sasha Kane          | Reality-TV Influencer           |
| `gerald.png`   | Gerald Ostrow       | Mogul / Producer                |
| `cody.png`     | Cody Vance          | Former Child Star / Busker      |
| `mateo.png`    | Mateo Ruiz          | Old Soul / Street Musician      |
