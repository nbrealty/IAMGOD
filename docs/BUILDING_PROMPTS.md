# Building Art Prompts — Hollywood & Highland square

Paste-ready prompts for generating every building in the first square, in the
same style as the chibi character cast. Same workflow as the spirits: generate
ONE first, lock the look, then do the rest referencing "same style, camera
angle, line weight, and lighting as before." Drop results anywhere; I key +
crop + place them at the correct in-game scale.

---

## How buildings complement the chibi characters

The characters are chunky, painted/cel-shaded, bold-outlined, warm, and a
little lived-in. Buildings match by being **"toy architecture"** — real
Hollywood landmarks, but with the same exaggeration the characters have:

- **Chunky, oversized details** — thick window frames, big doors, fat signage,
  softened corners. The same visual "roundness" that makes the chibis read as
  toys, applied to buildings.
- **Bold dark outlines + soft painted shading** — identical line/shade language
  to the character sprites, so a person standing in a doorway looks like they
  belong to the same drawing.
- **Signage is the hero.** Hollywood Blvd IS its signs. Big, bold, readable
  marquees and blade signs — that's the identity of every building.
- **Glamorous but grimy.** A little grime, sun-fade, and wear, matching the
  souls' lived-in feel. Not pristine renders.
- **Same warm daylight from the upper-left** on every asset, so lighting is
  consistent across the whole street.

## Perspective (critical — this makes them line up)

Every building is drawn **front-facing, straight-on, but from a slightly
elevated 3/4 HIGH ANGLE** — the same raised, looking-down-the-street camera the
characters are drawn for. You see the full facade and just a sliver of the flat
rooftop edge above it. **No dramatic side walls, no steep isometric.** This is
the "paper-doll building" look: flat facades that composite cleanly along a 2D
street with chibi characters walking in front of them.

## Format

Transparent PNG preferred; **flat pure-white background is fine** (I key it out
like I do the characters). No ground, no cast shadow, no sky, no people, no
cars — just the building, small margin around it.

## Scale system — the character is the yardstick

In-game, every character renders **84 units tall**. Call that **1 CH (character
height)**. Building heights below are given in CH.

**You do NOT need to match canvas sizes between images** — I set each building's
final in-game height from the table when I place it. What matters is each
building's OWN internal proportions: **draw a normal-height ground-floor
door/entrance, and let the building tower over it by the multiple listed.** A
standing character should come up to roughly the door handle. Keep that door
honest and the scale takes care of itself.

Rough size classes (height × how it reads):
- **Storefront (1 story + sign):** 3 CH — a person is ~⅓ the facade
- **Two-story shop:** 5 CH
- **Grand movie palace:** 6.5–7 CH
- **Museum / mid-rise:** 5–6 CH
- **Hotel tower:** 10–12 CH (towers; may extend once the world grows taller)
- **Parking structure:** 5 CH, wide
- **Apartment / residential:** 4 CH

Suggested generation resolution (for consistent detail density): landmarks
~1536 px on the tall side, storefronts ~1024 px. Aspect ratio per building.

---

## MASTER BUILDING STYLE PREFIX

Prepend this to every building prompt:

> Chibi-style building sprite for a stylized 2026 Hollywood Boulevard god-game,
> matching a cast of chunky painted chibi/caricature characters. A SINGLE
> building, front-facing facade, straight-on but seen from a slightly elevated
> 3/4 HIGH ANGLE (a raised camera looking down the street) so the flat rooftop
> edge is just visible above the facade — no steep isometric, no big side wall.
> Chunky, slightly exaggerated "toy" architecture: thick window frames,
> oversized doors, fat readable signage, softened corners — but still clearly
> the real landmark. Clean crisp painted / cel-shaded style with bold dark
> outlines, warm saturated daytime palette, soft warm sunlight from the
> upper-left, subtle grime and sun-faded wear (glamorous but a little gritty,
> like the real Boulevard). Big bold READABLE signage is the focal point. Fully
> transparent background (or flat pure white), no ground, no cast shadow, no
> sky, no people, no cars. Whole building in frame with a small margin. Include
> a normal-height ground-floor entrance for scale.
>
> The building is:

---

## LANDMARK PROMPTS (fictionalized real places)

### The Jade Pagoda Theatre  — *(TCL/Grauman's Chinese)* — 7 CH · wide ~1.5:1
> a grand ornate Chinese pagoda movie palace: a tall tiered jade-green pagoda
> roof with dramatically upturned eaves, deep red lacquered columns and walls,
> gold trim, two big stone guardian lion-dog statues flanking a tall central
> entrance, a small forecourt of handprint slabs. Ornamental, ceremonial,
> iconic. Big sign reads "JADE PAGODA".

### Overture Hollywood  — *(Ovation/Hollywood & Highland complex)* — 6 CH · very wide ~2:1
> a large open-air shopping-and-entertainment complex: a monumental tiered
> ceremonial archway/gateway framing a view through to a courtyard, wide stone
> steps, palm trees, hanging event banners, modern cream stone with glass
> storefronts tucked beneath. Grand and welcoming. Sign reads "OVERTURE
> HOLLYWOOD".

### The Vantage Theatre  — *(Dolby Theatre)* — 6 CH · ~1:1
> a sleek modern awards-show theatre: a curved glass-and-steel marquee canopy
> over a red-carpet entrance, tall elegant columns engraved with rows of years,
> a vertical illuminated blade sign. Polished, prestigious, Oscar-night glamour.
> Sign reads "VANTAGE".

### The Wonderland Theatre  — *(El Capitan)* — 6.5 CH · ~0.9:1
> an ornate Spanish Colonial Baroque movie palace: richly decorated cream-and-
> gold plasterwork facade with red accents, an elaborate arched entrance, a
> tall vertical blade marquee sign lit with bulbs, a small ticket booth.
> Whimsical, old-Hollywood, family-magical. Vertical sign reads "WONDERLAND".

### Madame Rousseau's Wax Museum  — *(Madame Tussauds)* — 5 CH · ~1.1:1
> a classical wax museum with a columned stone facade, tall banners printed with
> stylized celebrity wax figures, a grand lit sign, one street-level window
> showing a posed wax figure. Elegant, slightly kitschy. Sign reads "MADAME
> ROUSSEAU'S WAX MUSEUM".

### Blackwood's Odditorium  — *(Ripley's Believe It or Not!)* — 5 CH · ~1.2:1
> a quirky oddities museum with a deliberately crooked, off-kilter facade,
> mismatched windows, a dramatic bright sign, and a giant fake shark (or dinosaur
> head) bursting comically out through the brick wall. Mysterious dark palette,
> loud sign. Sign reads "BLACKWOOD'S ODDITORIUM".

### Thunderclap Rock Cafe  — *(Hard Rock Cafe)* — 4.5 CH · ~1.2:1
> a rock-n-roll themed cafe/restaurant: a huge round emblem sign, electric
> guitars and a vintage neon lightning bolt mounted on the facade, a classic car
> or oversized guitar bursting from above the entrance, bold red-and-chrome.
> Loud and fun. Round sign reads "THUNDERCLAP ROCK CAFE".

### Hotel Meridian Hollywood  — *(W Hollywood)* — 10 CH · tall/narrow ~0.55:1
> a sleek modern boutique hotel tower: dark glass and stone, glowing accent
> lighting, a stylish cantilevered canopy over the entrance, a tall vertical
> illuminated sign running up the tower. Cool, upscale, nightlife energy. Sign
> reads "MERIDIAN".

### The Apex World Records Museum  — *(Guinness World Records)* — 5 CH · ~1:1
> a fun records museum: a facade built around a giant open record-book motif,
> oversized "world's biggest / tallest" gag props sticking out (a giant shoe, a
> huge coin), bright primary colors, a bold sign. Sign reads "APEX WORLD
> RECORDS".

### The Crescendo Hotel  — *(Loews)* — 11 CH · tall/narrow ~0.5:1
> a grand modern hotel tower in warm cream stone with rows of balconies, an
> elegant porte-cochère entrance with valet lamps, a refined vertical sign near
> the top. Classy, warm, upscale. Sign reads "CRESCENDO".

### The Sovereign Hollywood Hotel  — *(Roosevelt)* — 7 CH · ~0.8:1
> a historic Spanish Colonial Revival grand hotel: cream stucco walls, a red
> clay-tile roof, tall arched windows, wrought-iron balconies, a lush entrance
> with palms, a classic vertical rooftop sign. Timeless old-Hollywood glamour.
> Sign reads "SOVEREIGN".

### Marchetti & Vane Grill  — *(Musso & Frank Grill)* — 4 CH · narrow ~0.7:1
> a dignified historic steakhouse storefront: a dark hunter-green facade and
> awning, gold serif lettering, brass fixtures, warm glowing windows with
> curtains, an old-money supper-club feel. Sign reads "MARCHETTI & VANE GRILL —
> EST. 1919".

### The Reel Page Bookshop  — *(Larry Edmunds Bookshop)* — 3.5 CH · narrow ~0.8:1
> a small charming film-memorabilia bookshop: a narrow storefront with a big
> display window crammed with vintage movie posters and stacked books, a
> hand-painted wooden sign, a warm inviting glow. Cozy and cluttered. Sign reads
> "THE REEL PAGE".

### The Glamour Archive Museum  — *(Hollywood Museum / Max Factor Building)* — 5 CH · ~1:1
> an elegant Art Deco museum: a pale blush-pink and cream facade with geometric
> deco detailing, tall fluted pilasters, a stylish deco-lettered sign, brass
> doors. Refined, vintage-Hollywood. Deco sign reads "GLAMOUR ARCHIVE".

---

## GENERIC / FILLER TEMPLATES (reuse with different signs & colors)

### Tourist souvenir shop — 3 CH · ~1.1:1
> a bright cluttered single-story tourist souvenir storefront: windows packed
> with "I ❤ LA" tees, mini Oscar statues, sunglasses racks, postcards; a
> loud awning and a cheap bold sign. Fun and garish. Sign reads "[STAR CITY
> SOUVENIRS / VARY IT]".

### Fast-food / pizza / cafe — 3 CH · ~1:1
> a small casual food storefront with a serving counter visible through the
> glass, a menu board, a bright awning, a couple of sidewalk stools. Sign reads
> "[VARY: e.g. BOULEVARD SLICE]".

### Tour-ticket kiosk / small stand — 2 CH · wide-ish ~1.4:1
> a small open-air ticket & tour-booking kiosk with a striped canopy, a rack of
> flyers, a big "BUS TOURS / STAR MAPS" board. Low and small. Sign reads "[VARY:
> STARLINE TOURS]".

### Parking structure — 5 CH · very wide ~1.8:1
> a plain multi-deck concrete parking structure: open horizontal levels with
> ramps and rows of parked cars faintly visible, a simple entry gate, a big
> plain sign. Utilitarian, gray. Sign reads "PUBLIC PARKING $".

### Apartment / residential mid-rise — 4 CH · ~0.9:1
> a modest older apartment building: stucco facade in a warm faded color, rows
> of simple windows with a few AC units and potted plants on small balconies, a
> plain entrance stoop. Lived-in, no signage (or a small street number).

### Backdrop skyline block (distant, low detail) — any size · dim
> a simple distant mid-rise office/apartment silhouette building, low detail,
> muted/desaturated cool palette, meant to sit far in the background behind the
> main street. Flat, plain windows, no signage.

---

## After you generate

Drop the files anywhere and tell me which is which. I'll key out the background,
crop tight, and place each at its table height (in CH) at the right spot in the
square — and this is the step where the world finally opens up north/south so
you can walk a full block, not just left/right.
