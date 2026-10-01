# Lori — story-generation prompt

A ready-to-paste prompt for generating Lori's backstory, psychology, and quest
arc in a separate Claude conversation. Grounded in real research on drug
distribution (not the stock "corner dealer" cliché) and written to output
directly into the game's soul-engine data model, so whatever comes back can be
dropped straight into `src/soul/roster.ts` with minimal editing.

Three outfits are already staged in `public/spirits/` (`lori.png` default,
`lori__shark-shorts.png`, `lori__gingham-going-out.png`, each with a `_back`
variant) — she has no soul entry yet. This prompt is step one of giving her one.

---

## The prompt

> I'm building a god-game called **I AM GOD**, set on a fictionalized Hollywood
> & Highland block in 2026 Los Angeles. The player is a deity who can observe
> and intervene in the lives of ~15 named NPCs ("souls") who live on this
> block. Each soul is simulated by a real psychological model, not a flavor
> label — I need you to design one soul's full backstory and psychology so it
> can be encoded directly into that model.
>
> **The soul model** (every field below needs a value):
> - **Needs** (0–100, Maslow-based, decay over time and get replenished by
>   activities): `survival`, `safety`, `belonging`, `esteem`, `actualization`.
> - **Traits** (0–100, slow-moving, the five maladaptive personality
>   dimensions — think PID-5): `negativeAffectivity`, `detachment`,
>   `antagonism`, `disinhibition`, `psychoticism`.
> - **Core stats**: `aceScore` (0–10, Adverse Childhood Experiences),
>   `resilience` (0–100), `kohlberg` (1–6, moral reasoning stage — 1–2 is
>   punishment/self-interest, 3–4 is social norms/law, 5–6 is
>   principled/self-chosen ethics), `soulAge` (Young/Mature/Old),
>   `initiationLevel` (0–7, spiritual development — how awake she is to
>   anything beyond her own survival and self-interest).
> - **The 7 chakras** (0–100 openness each, bottom-up: Root, Sacral, Solar
>   Plexus, Heart, Throat, Third Eye, Crown) — gated by her psychology (e.g.
>   Root is gated by survival/safety, Heart by belonging, Throat by
>   esteem+low-psychoticism, Crown by spiritual initiation).
> - **The central dramatic irony (this is the whole point of the game):**
>   every soul has a `consciousAspiration` (what she THINKS she wants, in her
>   own words) and a `soulPurpose` (what she ACTUALLY incarnated to do —
>   usually more generous, more redemptive, and something she cannot fully see
>   about herself). The gap between the two is the deep game: the player-god
>   can nudge her toward closing it, or watch her widen it.
> - **Appearance/clothing** derives from psychology automatically — I don't
>   need clothing described, just her `archetype`.
>
> **Existing roster for context/consistency** (so she feels like she belongs
> on the same block, not a different game): a costumed street performer
> chasing a real acting career, a tourist, a paparazzo, a faded 1990s actress,
> a burnt-out server auditioning nightly, a rideshare driver, two local
> shopworkers, a reality-TV influencer named Sasha (400k followers, refreshes
> her numbers at red lights), a studio-exec mogul named Gerald (quiet-curated,
> can't remember a conversation that wasn't a negotiation), a washed-up former
> child star turned busker, a transcendent street musician, and a small
> corner crew (`Hector` the tired shot-caller, `Javier` the 17-year-old
> initiate starving for belonging, `Ruben` who's quietly getting his little
> brother out). There's also **Roxy Valente**, 46, a Brazilian-American
> walking tour guide who — under the tourist-trivia cover story — hears
> everything and quietly protects the younger women on the block from men
> who are smiling trouble.
>
> **The character to build: Lori.** She's a drug dealer, but I don't want the
> corner-slinger cliché — the Ivar Ave crew above already covers that
> register. Ground her instead in the real sociology of women in
> higher-tier/nightlife-adjacent distribution: research on "queenpins" and
> successful female dealers describes **psychological empowerment through
> skill** — women who built real agency, status, and financial independence
> in a marginalizing, male-dominated economy, often using gender strategically
> (as cover, as leverage, as protection) rather than being merely victimized by
> it. Her look (fashion-forward streetwear and a sharp going-out wardrobe with
> real gold hardware, not costume jewelry) reads as embedded in Hollywood's
> **industry/nightlife/party economy** — she supplies people adjacent to the
> influencer/industry-aspirant/club scene, not a street corner. She is
> capable, sharp, and has genuinely built something most people underestimate.
> Philippe Bourgois's research on the "search for respect" driving the
> underground economy, and Bourdieu/Moyle-Coomber's work on gendered "street
> capital," are useful reference points for tone — this should read as
> earned competence and real internal cost, not glamorization and not
> moralizing.
>
> Please output:
> 1. A short prose backstory (150–250 words) — how a smart, capable woman
>    ended up here, what she actually sells and to whom, what "success" has
>    cost her.
> 2. Full stat block for every field listed above, with a one-line
>    justification for each non-obvious number (especially `kohlberg`,
>    `aceScore`, `initiationLevel`, and the chakra values).
> 3. Her `consciousAspiration` and `soulPurpose` — make sure they genuinely
>    diverge, and that the gap is legible as something a player-god could act
>    on.
> 4. 2–3 possible connections to the existing roster (who might buy from her,
>    who might be her real friend versus a client, who could become a threat).
> 5. A rough 3-beat quest arc suitable for a "watch or intervene" side quest —
>    a status quo, an escalating pressure point, and two possible outcomes
>    (one if the player intervenes with a blessing, one if they don't).
>
> Keep it psychologically real and specific — no stock "kingpin" tropes, no
> gratuitous violence for its own sake, and nothing that glamorizes the drug
> trade uncritically. She should feel like a real person the player could
> come to respect, worry about, or want to save.

---

## After you get a response

Paste it back to me — I'll translate it directly into a `roster.ts` soul entry
(same structure as Roxy's) and wire her onto the block using the art already
staged in `public/spirits/lori*.png`.

## Sources used to ground this prompt

- [In Search of Respect (Bourgois) — LitCharts summary](https://www.litcharts.com/lit/in-search-of-respect/summary)
- [In Search of Respect — street culture and drug use theme](https://www.litcharts.com/lit/in-search-of-respect/themes/street-culture-and-drug-use)
- [Queenpins: female participation in high-level drug distribution networks](https://link.springer.com/article/10.1007/s12117-024-09546-0)
- [Successful Female Crack Dealer: Case Study of a Deviant Career (NIJ)](https://nij.ojp.gov/library/publications/successful-female-crack-dealer-case-study-deviant-career)
- [Dealing with a gendered economy: female drug dealers and street capital](https://www.academia.edu/6709781/Dealing_with_a_gendered_economy_Female_drug_dealers_and_street_capital)
- [Savvy Sellers: Dealing Drugs, Doing Gender, and Doing Difference](https://pmc.ncbi.nlm.nih.gov/articles/PMC5271670/)
