# I AM GOD — Starting-Missions Skeleton & ChatGPT Authoring Guide

> A **framework for co-writing the opening story with ChatGPT** while character-creation assets are
> generated in parallel. Goal: have the first 2–3 **starting missions** specced tightly enough that we
> can begin building them the moment the CaC assets are ready. This is a *planning* doc — it does not
> write final scenes or build anything. Everything must stay consistent with `docs/STORY_BIBLE.md`
> (N-series novela rules + E-series entity bible). Status tags: **[CANON] / [DIR] / [PROV] / [RESEARCH]**.

---

## 0. How to use this
1. Paste **§6 "ChatGPT preamble"** into ChatGPT first — it loads the canon + guardrails so it stays on-model.
2. Work **one mission at a time** through the **Mission Spec Template (§4)**. ChatGPT fills every field;
   you review against the guardrails (§1) and the continuity ledger (§7).
3. When a mission's spec meets the **"ready to build" bar (§8)**, it's queued for implementation.
4. Keep the **continuity ledger (§7)** updated as you go, so novela reveals stay *fair* (planted, not retconned).

## 1. Guardrails (non-negotiable — from the Story Bible)
- **Reveals reclassify, never erase.** "True but incomplete," not "everything was fake." Plant fair clues.
- **Misdirection allowed but fair** — you may lead the audience wrong; never later pretend evidence said
  something it didn't. Sneaky, not fraudulent.
- **God's power arranges circumstances, doesn't override wills** (missed elevator, delayed car, a truth
  reaching the right ears). Humans keep responsibility for their choices.
- **Entities act through human systems + advance on their own world clocks** even when the player is busy
  with unrelated drama. Every mission should tick at least one clock (usually in the background).
- **"Demon" = only angels who fell with Lucifer.** Molache, orixás, Exus, lwa, ancestral/Indigenous
  beings, urban collectives are NOT demons. Characters may misclassify; lore keeps the distinction.
- **Lucifer:** begins as a genuinely helpful guide (warmth is real *and* manipulative), identity concealed
  at first; wants **vindication**, not God dead; may open others' hidden rooms but isn't behind everything;
  bargains follow his rules (can't create love, can't force acceptance, a price always exists + connects to
  the gift, every bargain has an exit that costs the original desire). Never an "always refuse" button.
- **Molache:** shows up as institutions/events, not a monster in a room; asks "how can I *use* God?"; his
  weakness is a **freely given gift** (no debt/audience/exchange). Adult sacrifice systems; child-sacrifice
  imagery only restrained/indirect/environmental. **Never accuse real people** — fictional composites only.
- **Yara is human.** Águas Douradas is research-gated Afro-diasporic; **[RESEARCH]** any orixá/Exu/Pombagira/
  lwa specifics before scripting; never merge traditions; never invent a secret "true mythology" for a
  living tradition; Puvungna is a living sacred place, not a dungeon.
- **Don't resolve [PROV]/[RESEARCH]/theological questions in a mission.** If a beat needs one, flag it and
  route around it; don't lock it by writing it into a scene.

## 2. Opening-arc map (where the first missions sit)  [DIR, sequence provisional]
```
PROLOGUE  →  CREATOR  →  M1 Ordinary Life  →  M2 The Reading  →  M3 The First Favor  →  (arc continues…)
(Second      (build a    (a small human      (Águas Douradas    (Lucifer's help pays a
 Heartbeat    body-base   want; first hint    búzios reading      real debt; a world clock
 birth beat)  avatar)     of the guide)       reads God's soul    ticks in the open)
                                              "wrong")
```
- **PROLOGUE = The Second Heartbeat** [CANON origin]. A short, mostly-authored birth beat: emergency
  delivery → the beacon "I am awake" → different entities feel it → cut forward to the adult. Plants
  mystery, does NOT explain (player is not told they are God). Likely a cinematic/low-interaction beat.
- **CREATOR** = the built CaC flow (body base for now; more later).
- **M1–M3 = "the first couple of starting missions."** Provisional beats in §5. Their job: establish the
  ordinary human life, introduce the guide (Lucifer, concealed), deliver the first supernatural *hint*
  through a **built mechanic** (the búzios reading), and start one background world clock — all without
  info-dumping the cosmology.

## 3. What the engine can do TODAY (design missions to this palette)
Buildable beats **right now** (reuse these; they cost little):
- Walk the boulevard (tap-to-walk / D-pad), pan/zoom, **day-night clock** (time-gate a beat).
- **Enter interior rooms** (AREAS scene-swap) with a Leave button; e.g. Yara's botanica (front + back),
  Overture court.
- **Yara flow (fully built):** front-desk conversation (greet · ask about her life, tiered by initiation ·
  consult the búzios → price → accept & pay) → she walks to the back → sit → **first-person búzios POV
  cast** → **reading** with odù + Axé/chakra/power consequence.
- Tap a soul → **Soul Profile panel** (needs, traits, chakras, initiation, money, etc.).
- **Wallet/currency** per soul (pay/receive). Soul stat changes (Axé, chakra openness, initiation, powers,
  emotion, needs). **Outfits/inventory.**
- Roster of named souls to populate scenes (Lori, Nia, Sorriso, Lua, Bibi, …).

**New systems the first missions will likely need** (flag, don't assume): a lightweight **quest/flag +
objective tracker**; a **dialogue/cutscene runner** (beyond the ad-hoc panels); **world-clock state**;
a **full-screen "meanwhile, elsewhere" card** (the `BuziosReadingScene` full-bleed pattern is a good base).
Design missions so the *human-facing* beats use built systems and the *new-system* needs are explicit and small.

## 4. Mission Spec Template (ChatGPT fills ALL fields, per mission)
```
MISSION ID + TITLE:            (e.g. M2 — "The Reading")
LOGLINE:                       one sentence, human-surface framing
ARC POSITION / PREREQS:        where it sits; flags/missions required first
SCOPE:                         short beat | standard mission | multi-part
PLAYER-STATE ASSUMPTIONS:      powers unlocked, initiation/Axé, key relationships, wallet, moral tendencies
HUMAN SURFACE:                 the mundane story the player thinks it's about
SUPERNATURAL UNDERCURRENT:     what's actually happening on the board (may be hidden from the player)
ACTIVE ENTITIES + CLOCK TICK:  which entities act; which world clock advances one step (usually background)
CAST:                          named characters + roles (reuse roster where possible; new = flag)
SETTING(S):                    which built rooms/areas; new areas = flag
BEATS:                         ordered sequence of what happens
OBJECTIVES:                    primary + optional
CHOICES & CONSEQUENCES:        branch points; each option's cost/gain; Lucifer-bargain rules honored;
                               Sacrificial-Logic delta (if any); what's fair-clue vs misdirection
POWERS:                        introduced / used, and HOW (circumstance-arrangement, not override)
REVEAL SEEDS PLANTED:          which hidden-room/identity clue is set up for later; note it's FAIR
PERSISTENCE:                   what sticks (soul stats, relationships, world flags, draft) into later missions
TONE / REFERENCES:            
CULTURAL / THEOLOGICAL GATES:  anything touching [RESEARCH]/[PROV] → flag, route around, do not lock
ASSETS REQUIRED:               art / audio / UI — mark EXISTS vs NEW
BUILD FEASIBILITY:             works on current engine? which new system (if any) is needed?
SUCCESS / FAIL / SOFT-FAIL:    end states + how failure is handled (novela = few hard fails)
OPEN QUESTIONS / [PROV]:      
```

## 5. Proposed first missions — SKELETON to develop with ChatGPT  [PROV — beats are placeholders]
> These are *seeds* to react to and expand, not locked. Each anchors on a **built** mechanic so it's
> cheap to prototype, and each ticks one clock quietly.

- **PROLOGUE — "The Second Heartbeat"** [CANON origin]. Emergency delivery; mother unconscious; the baby
  arrests, the original soul leaves, God takes the body, the heart restarts → beacon. Brief entity
  reactions (Lucifer recognizes; Molache senses a claim; the Audience registers an anomaly) shown as
  quick "elsewhere" cards. Cut to adult. *Plants mystery; explains nothing.* Clock ticks: all beacons.
  **[RESEARCH]** accurate neonatal-resuscitation / emergency-C-section detail before scripting.

- **M1 — "Ordinary Life"** (introduce the human + the guide). A small, human want/problem (a job, a rent
  gap, a relationship, a favor owed) on the built boulevard. **Lucifer appears in concealed guide form**
  and does one *unsolicited* small kindness that solves a piece of the problem — creating gratitude +
  a faint social obligation, **not** a bargain, **not** binding. Identity concealed. Clock: **Lucifer /
  First Favor** step 1–3 (identify → trust → offer help). Built beats: walk, dialogue panel w/ choices,
  maybe a wallet nudge. Reveal seed: a fair clue about the guide (the gold coin, a too-perfect
  coincidence) the player can later re-read.

- **M2 — "The Reading"** (first supernatural hint, via a built mechanic). The player is drawn to
  **Águas Douradas** and sits for a **búzios reading** (fully built). The reading lands "wrong" — the
  shells/odù read a soul that shouldn't be here; **Yara senses something she can't name** (careful:
  she's human, no cosmology dump). This opens a small quest hook with Yara (spiritual-strength / Axé
  path) and plants the incarnation mystery *fairly*. Clock: a spiritual-community beat (background).
  Built beats: front-desk convo → pay → POV cast → reading + Axé/chakra consequence. **[RESEARCH]** keep
  Yara's language within researched Afro-diasporic bounds.

- **M3 — "The First Favor"** (the guide's help acquires a price shape). Lucifer's earlier kindness or a
  new small crisis makes his help *matter*; the player feels the pull of a real (still-small) bargain or
  a deepening trust. A **world clock ticks in the open** for the first time — a visible Molache-adjacent
  event (a studio/awards/redevelopment item as set-dressing) so the board feels alive. No identity reveal
  yet. Reveal seed: contrast Lucifer's warmth with the first hint he's *studying* the player.

*(Guide identity reveal, first real bargain, and the first overt power belong slightly later — end of the
opening quest line — per Lucifer's state progression. Keep the first three missions about establishing
life, guide, mystery, and a living board.)*

## 6. ChatGPT preamble (paste this to ChatGPT before authoring)
```
You are co-writing the OPENING STORY of "I AM GOD," a Brazilian-novela-structured game where the
player-character is God reincarnated as a human (default origin "The Second Heartbeat": the baby dies at
birth, the original soul peacefully leaves, God takes the body, the heartbeat returns as a citywide
supernatural beacon "I am awake"). Setting: fictionalized 2026 Hollywood, Los Angeles.

HARD RULES:
- Reveals RECLASSIFY established identities ("true but incomplete"), never erase them. Plant fair clues.
  Misdirection is allowed but must be fair — never retcon evidence.
- God influences by ARRANGING CIRCUMSTANCES, never by overriding free will. Humans keep responsibility.
- Supernatural entities act THROUGH human systems (studios, clubs, botanicas, hospitals, media, politics)
  and advance on their own "world clocks" even when the player is busy elsewhere.
- "Demon" means ONLY an angel who fell with Lucifer. Molache (LA's sovereign of sacrifice), orixás, Exus,
  Pombagiras, Vodou lwa, ancestral/Indigenous sacred beings, and urban collectives are NOT demons.
- Lucifer starts as a genuinely helpful guide (warmth real AND manipulative), identity concealed; he wants
  VINDICATION from God, not God dead; his bargains can't create love, can't be forced, always carry a
  price connected to the gift, and always have an exit that costs the original desire. He is never an
  "always refuse" button and is not behind every secret.
- Molache asks "how can I USE God?"; he appears as institutions/events; his weakness is a freely given
  gift (no debt, audience, or exchange). Never accuse real people — fictional composites only.
- Yara is HUMAN. Anything touching Candomblé/Umbanda/Quimbanda/Vodou/Hoodoo/Indigenous SoCal traditions is
  RESEARCH-GATED: do not invent secret "true mythology," do not merge traditions, do not script sacred
  detail — flag it [RESEARCH] and route around it. Puvungna is a living sacred place, not a dungeon.
- Do NOT resolve any question I have marked provisional or theological. Flag it, don't lock it.

TASK: We are specifying the first 2–3 STARTING MISSIONS. Work ONE mission at a time. Fill EVERY field of
the Mission Spec Template I give you. Tag statements [CANON]/[DIR]/[PROV]/[RESEARCH]. Prefer beats that use
these already-built systems: walking the boulevard, entering interior rooms, the Yara búzios reading flow
(front desk → pay → first-person cast → reading with Axé/chakra consequence), soul-stat changes, wallet,
tapping NPCs for a Soul Profile. When a beat needs a NEW system (quest/flag tracker, dialogue runner,
world-clock state, a "meanwhile elsewhere" card), say so explicitly and keep it small. End every mission
with its OPEN QUESTIONS.
```

## 7. Continuity ledger (keep updated so reveals stay fair)
Track, across missions, so novela payoffs are planted-not-retconned:
- **Planted secrets / hidden rooms:** which reveal each clue serves; where it was planted; where it pays off.
- **Fair clues vs deliberate misdirection:** log which is which, so we never "cheat" later.
- **World-clock state:** current step of each active clock (Lucifer/First Favor, Molache/Covenant Renewal,
  Broken Choir, The Audience, Águas-Douradas schism, Land Awakening).
- **Relationships:** trust/debt with Lucifer, Yara, roster souls.
- **Player soul state:** initiation/Axé, chakra openness, powers unlocked, wallet.
- **Moral tendencies:** Sacrificial-Logic tally (shortcuts / replacement victims / cost-transfer choices).
- **Persistent world flags:** what each mission changed that later missions must respect.

## 8. "Ready to build" bar (a mission graduates from spec to implementation when…)
- Every Mission-Spec-Template field is filled and passes the §1 guardrails.
- Beats map cleanly to **built systems**, with any **new system** named, scoped small, and agreed.
- Choices have defined consequences + persistence; no branch dead-ends silently.
- `[RESEARCH]`/`[PROV]` items are flagged and **routed around**, not scripted.
- Required assets are listed as EXISTS vs NEW (so art/audio can be queued alongside CaC assets).
- The continuity ledger is updated with what this mission plants and pays off.

---

> Planning scaffold only. No missions, dialogue, systems, or assets are built from this until Nelson
> explicitly says go. Develop the mission specs with ChatGPT against the Story Bible; when a spec clears
> the §8 bar, we implement it.
