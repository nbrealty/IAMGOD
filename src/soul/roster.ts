// The Hollywood & Highland roster — 12 hand-authored souls built on the locked
// archetype list. Structured for the engine to tick; a procedural generator can
// replace this file wholesale in Phase 5 without touching anything else.

import {
  type Soul,
  type Traits,
  type ChakraName,
  CHAKRA_ORDER,
} from "./types.ts";

function traits(p: Partial<Traits>): Traits {
  return {
    negativeAffectivity: 30,
    detachment: 30,
    antagonism: 25,
    disinhibition: 30,
    psychoticism: 20,
    ...p,
  };
}

function chakras(vals: [number, number, number, number, number, number, number]) {
  const out = {} as Record<ChakraName, number>;
  CHAKRA_ORDER.forEach((name, i) => {
    out[name] = vals[i];
  });
  return out;
}

type Seed = Omit<Soul, "emotion" | "activity"> & Partial<Pick<Soul, "emotion" | "activity">>;

function soul(seed: Seed): Soul {
  return {
    emotion: { primary: "neutral", intensity: 30 },
    activity: "wander",
    ...seed,
  };
}

const RAW: Soul[] = [
  soul({
    id: "danny",
    name: "Danny Rios",
    occupation: 'Costumed Character Performer ("Robo-Hero")',
    archetype: "Costumed Street Performer",
    age: 34,
    narrative:
      "Three failed auditions this year. The suit pays the rent the way the craft never did. He tells himself it's temporary — the way he has for six years.",
    needs: { survival: 26, safety: 34, belonging: 40, esteem: 30, actualization: 44 },
    traits: traits({ negativeAffectivity: 58, detachment: 20, disinhibition: 35 }),
    aceScore: 3,
    resilience: 48,
    kohlberg: 3,
    soulAge: "Mature",
    initiationLevel: 1,
    chakras: chakras([28, 40, 32, 46, 24, 40, 12]),
    consciousAspiration: "Finally get cast — become a real actor",
    soulPurpose: "Bring a moment of delight to strangers who need it",
    affinities: { perform: 1.6, work: 1.2, rest: 1.1 },
    row: "north",
    xMin: 100,
    xMax: 320,
    baseSpeed: 26,
  }),
  soul({
    id: "trish",
    name: "Trish Anderson",
    occupation: "Tourist, Dayton, Ohio",
    archetype: "Tourist",
    age: 29,
    narrative:
      "She has wanted to stand on this sidewalk since she was eleven. For a few seconds outside the Chinese Theatre, her whole chest went quiet.",
    needs: { survival: 72, safety: 68, belonging: 42, esteem: 55, actualization: 64 },
    traits: traits({ negativeAffectivity: 35, detachment: 22 }),
    aceScore: 1,
    resilience: 70,
    kohlberg: 4,
    soulAge: "Mature",
    initiationLevel: 2,
    chakras: chakras([70, 66, 54, 62, 48, 52, 34]),
    consciousAspiration: "Capture the trip of a lifetime",
    soulPurpose: "Rediscover the wonder she buried under adult routine",
    affinities: { gaze: 1.7, socialize: 1.2 },
    row: "north",
    xMin: 640,
    xMax: 1050,
    baseSpeed: 18,
  }),
  soul({
    id: "frank",
    name: "Frank Castellano",
    occupation: "Freelance Photographer",
    archetype: "Paparazzi",
    age: 47,
    narrative:
      "He hasn't sold a real cover shot in eight months. He's stopped calling it stalking, even in his own head.",
    needs: { survival: 48, safety: 44, belonging: 30, esteem: 34, actualization: 30 },
    traits: traits({ antagonism: 68, detachment: 55, disinhibition: 50, negativeAffectivity: 52 }),
    aceScore: 4,
    resilience: 40,
    kohlberg: 2,
    soulAge: "Mature",
    initiationLevel: 1,
    chakras: chakras([46, 30, 40, 22, 42, 50, 14]),
    consciousAspiration: "Land the one shot that fixes everything",
    soulPurpose: "Bear honest witness instead of feeding the machine",
    affinities: { hustle: 1.7, work: 1.1 },
    row: "south",
    xMin: 250,
    xMax: 560,
    baseSpeed: 22,
  }),
  soul({
    id: "vivian",
    name: "Vivian Laurent",
    occupation: "Former Screen Actress (credits: 1990s)",
    archetype: "Faded Star",
    age: 61,
    narrative:
      "People still recognize her — less every year. She still walks this block every afternoon, in case someone does.",
    needs: { survival: 60, safety: 38, belonging: 30, esteem: 44, actualization: 40 },
    traits: traits({ negativeAffectivity: 55, detachment: 40 }),
    aceScore: 2,
    resilience: 52,
    kohlberg: 4,
    soulAge: "Old",
    initiationLevel: 3,
    chakras: chakras([58, 48, 46, 30, 48, 54, 30]),
    consciousAspiration: "Be remembered — matter again",
    soulPurpose: "Pass her hard-won craft to someone just starting out",
    affinities: { reminisce: 1.6, socialize: 1.3, gaze: 1.1 },
    row: "north",
    xMin: 1080,
    xMax: 1500,
    baseSpeed: 14,
  }),
  soul({
    id: "bailey",
    name: "Bailey Okafor",
    occupation: "Server, Auditioning Nights",
    archetype: "Industry Aspirant",
    age: 24,
    narrative:
      "Her agent hasn't called back in nine days. She rehearses the callback she hasn't gotten yet, out loud, on her walk to work.",
    needs: { survival: 52, safety: 50, belonging: 58, esteem: 30, actualization: 56 },
    traits: traits({ negativeAffectivity: 48, detachment: 18 }),
    aceScore: 2,
    resilience: 62,
    kohlberg: 4,
    soulAge: "Young",
    initiationLevel: 2,
    chakras: chakras([56, 60, 44, 62, 30, 48, 28]),
    consciousAspiration: "Book the role that changes everything",
    soulPurpose: "Become a source of steadiness for the people she came from",
    affinities: { work: 1.4, perform: 1.3, socialize: 1.2 },
    row: "south",
    xMin: 650,
    xMax: 980,
    baseSpeed: 24,
  }),
  soul({
    id: "marcus",
    name: "Marcus Webb",
    occupation: "Rideshare Driver",
    archetype: "Local Commuter",
    age: 39,
    narrative:
      "Just passing through this block on the way to the next fare. Two kids at home; the math never quite works.",
    needs: { survival: 55, safety: 46, belonging: 58, esteem: 52, actualization: 50 },
    traits: traits({ negativeAffectivity: 38 }),
    aceScore: 1,
    resilience: 66,
    kohlberg: 4,
    soulAge: "Mature",
    initiationLevel: 2,
    chakras: chakras([60, 62, 60, 58, 62, 56, 34]),
    consciousAspiration: "Get out from under the debt",
    soulPurpose: "Be the steady presence his kids can count on",
    affinities: { work: 1.5, wander: 1.2 },
    row: "south",
    xMin: 60,
    xMax: 240,
    baseSpeed: 30,
  }),
  soul({
    id: "priya",
    name: "Priya Chandra",
    occupation: "Souvenir Shop Clerk",
    archetype: "Local Worker",
    age: 21,
    narrative:
      "Another shift, another thousand tourists asking where the stars are. She still likes the job, mostly.",
    needs: { survival: 58, safety: 60, belonging: 62, esteem: 50, actualization: 54 },
    traits: traits({ detachment: 18 }),
    aceScore: 0,
    resilience: 72,
    kohlberg: 4,
    soulAge: "Young",
    initiationLevel: 2,
    chakras: chakras([64, 66, 62, 66, 50, 58, 34]),
    consciousAspiration: "Save enough for community college",
    soulPurpose: "Offer warmth to strangers far from home",
    affinities: { socialize: 1.4, work: 1.2 },
    row: "north",
    xMin: 360,
    xMax: 560,
    baseSpeed: 16,
  }),
  soul({
    id: "hank",
    name: "Hank Torres",
    occupation: "Walking Tour Guide",
    archetype: "Local Worker",
    age: 52,
    narrative:
      "Twelve tours a week, same jokes, same facts. He still means it when he points out the stars — mostly.",
    needs: { survival: 56, safety: 58, belonging: 54, esteem: 44, actualization: 52 },
    traits: traits({ negativeAffectivity: 40 }),
    aceScore: 1,
    resilience: 60,
    kohlberg: 4,
    soulAge: "Mature",
    initiationLevel: 2,
    chakras: chakras([60, 58, 52, 60, 62, 50, 32]),
    consciousAspiration: "Be respected as the guy who knows this city",
    soulPurpose: "Keep the boulevard's real stories alive",
    affinities: { perform: 1.3, work: 1.4, socialize: 1.1 },
    row: "north",
    xMin: 1120,
    xMax: 1480,
    baseSpeed: 20,
  }),
  soul({
    id: "sasha",
    name: "Sasha Kane",
    occupation: "Lifestyle Content Creator",
    archetype: "Reality-TV Influencer",
    age: 27,
    narrative:
      "Four hundred thousand followers and she still refreshes the numbers at red lights. The camera is the only place she feels real.",
    needs: { survival: 66, safety: 60, belonging: 34, esteem: 28, actualization: 46 },
    traits: traits({ antagonism: 58, disinhibition: 60, negativeAffectivity: 50, detachment: 30 }),
    aceScore: 3,
    resilience: 44,
    kohlberg: 3,
    soulAge: "Young",
    initiationLevel: 1,
    chakras: chakras([62, 50, 44, 28, 40, 44, 16]),
    consciousAspiration: "Go viral — become undeniable",
    soulPurpose: "Risk one honest, unfiltered connection",
    affinities: { hustle: 1.5, perform: 1.5 },
    row: "south",
    xMin: 1000,
    xMax: 1200,
    baseSpeed: 23,
  }),
  soul({
    id: "gerald",
    name: "Gerald Ostrow",
    occupation: "Studio Executive",
    archetype: "Mogul / Producer",
    age: 58,
    narrative:
      "He can greenlight a hundred million dollars before lunch. He can't remember the last conversation that wasn't a negotiation.",
    needs: { survival: 88, safety: 82, belonging: 26, esteem: 70, actualization: 40 },
    traits: traits({ antagonism: 60, detachment: 62, negativeAffectivity: 30 }),
    aceScore: 4,
    resilience: 58,
    kohlberg: 2,
    soulAge: "Mature",
    initiationLevel: 1,
    chakras: chakras([80, 44, 66, 24, 50, 46, 14]),
    consciousAspiration: "Land the franchise that cements his legacy",
    soulPurpose: "Use his power to shelter the people the machine chews up",
    affinities: { work: 1.6, hustle: 1.3 },
    row: "north",
    xMin: 600,
    xMax: 900,
    baseSpeed: 21,
  }),
  soul({
    id: "cody",
    name: "Cody Vance",
    occupation: "Busker (former child actor)",
    archetype: "Former Child Star / Busker",
    age: 31,
    narrative:
      "America watched him grow up on a sitcom. The residuals ran out a decade ago. He plays the theme song for tips and hates that it still works.",
    needs: { survival: 30, safety: 32, belonging: 34, esteem: 38, actualization: 42 },
    traits: traits({ negativeAffectivity: 66, disinhibition: 58, detachment: 40 }),
    aceScore: 6,
    resilience: 34,
    kohlberg: 3,
    soulAge: "Mature",
    initiationLevel: 2,
    chakras: chakras([30, 34, 34, 38, 40, 46, 18]),
    consciousAspiration: "Engineer the comeback everyone owes him",
    soulPurpose: "Protect the next generation of kids from what happened to him",
    affinities: { perform: 1.5, reminisce: 1.4, rest: 1.1 },
    row: "south",
    xMin: 300,
    xMax: 520,
    baseSpeed: 17,
  }),
  soul({
    id: "mateo",
    name: "Mateo Ruiz",
    occupation: "Street Musician",
    archetype: "Old Soul / Street Musician",
    age: 44,
    narrative:
      "He plays where the acoustics are best, gives half his tips away, and somehow people stand a little straighter after they pass him. He'd tell you it's just the guitar.",
    needs: { survival: 58, safety: 62, belonging: 74, esteem: 66, actualization: 82 },
    traits: traits({ negativeAffectivity: 18, detachment: 15, antagonism: 12 }),
    aceScore: 5,
    resilience: 90,
    kohlberg: 6,
    soulAge: "Old",
    initiationLevel: 5,
    chakras: chakras([78, 76, 74, 78, 76, 72, 66]),
    consciousAspiration: "Just play, and pay rent",
    soulPurpose: "Be a tuning fork the whole block quietly aligns to",
    affinities: { perform: 1.3, socialize: 1.4, gaze: 1.2 },
    row: "north",
    xMin: 360,
    xMax: 620,
    baseSpeed: 15,
  }),

  // --- the Ivar Ave set: three souls in the same colors, three different truths.
  // Their clothing all reads "faction-coded" — the block can't tell them apart on
  // sight. Only the god (reading the panel) sees the shot-caller, the starving kid,
  // and the one already halfway out the door.
  soul({
    id: "hector",
    name: "Hector Reyes",
    occupation: "Corner Veteran",
    archetype: "Gang Shot-Caller",
    faction: "the Ivar Ave set",
    age: 38,
    narrative:
      "He runs this corner the only way he was ever shown — by making sure no one forgets who he is. The respect is real. So is the exhaustion he never lets anyone see.",
    needs: { survival: 58, safety: 50, belonging: 46, esteem: 62, actualization: 26 },
    traits: traits({ antagonism: 72, detachment: 60, disinhibition: 55, negativeAffectivity: 44, psychoticism: 34 }),
    aceScore: 7,
    resilience: 46,
    kohlberg: 2,
    soulAge: "Mature",
    initiationLevel: 1,
    chakras: chakras([50, 34, 52, 22, 30, 34, 12]),
    consciousAspiration: "Keep the block ours — command respect, never look weak",
    soulPurpose: "Protect his people, and find the strength to finally lay the weapon down",
    affinities: { hustle: 1.5, work: 1.1, socialize: 1.1, rest: 1.0 },
    row: "south",
    xMin: 1300,
    xMax: 1520,
    baseSpeed: 10,
  }),
  soul({
    id: "javi",
    name: "Javier Mendez",
    occupation: 'Neighborhood Kid ("Lil J")',
    archetype: "Gang Initiate",
    faction: "the Ivar Ave set",
    age: 17,
    narrative:
      "He'd never say it out loud, but he joined for the thing he never got at home — people who show up. He'd do almost anything to keep them, and the older ones know it.",
    needs: { survival: 44, safety: 32, belonging: 26, esteem: 30, actualization: 40 },
    traits: traits({ negativeAffectivity: 58, detachment: 20, antagonism: 40, disinhibition: 62, psychoticism: 22 }),
    aceScore: 8,
    resilience: 44,
    kohlberg: 3,
    soulAge: "Young",
    initiationLevel: 1,
    chakras: chakras([24, 30, 28, 40, 26, 30, 14]),
    consciousAspiration: "Prove I'm down — earn my place, make them proud",
    soulPurpose: "Find the family and safety he's actually starving for, before the street takes him",
    affinities: { socialize: 1.5, perform: 1.2, hustle: 1.2, rest: 1.0 },
    row: "south",
    xMin: 1260,
    xMax: 1500,
    baseSpeed: 16,
  }),
  soul({
    id: "ruben",
    name: "Ruben Salcedo",
    occupation: "Auto-Shop Apprentice",
    archetype: "Getting Out",
    faction: "the Ivar Ave set",
    age: 26,
    narrative:
      "He grew up in these colors and still wears them — this is his neighborhood, his people. But he clocks in at the shop now, and every day he's quietly building a door his little brother can walk through.",
    needs: { survival: 60, safety: 54, belonging: 66, esteem: 58, actualization: 62 },
    traits: traits({ negativeAffectivity: 34, detachment: 22, antagonism: 28, disinhibition: 30, psychoticism: 18 }),
    aceScore: 6,
    resilience: 74,
    kohlberg: 5,
    soulAge: "Mature",
    initiationLevel: 3,
    chakras: chakras([60, 56, 60, 62, 52, 54, 34]),
    consciousAspiration: "Keep my little brother out of the life — build something legit",
    soulPurpose: "Break the cycle on his own block, and show the younger ones a way through",
    affinities: { work: 1.5, socialize: 1.3, gaze: 1.1, rest: 1.0 },
    row: "south",
    xMin: 1320,
    xMax: 1560,
    baseSpeed: 20,
  }),

  // Rosangela "Roxy" Valente — Brazilian-American sidewalk survivor and Hidden
  // Protector. Flagged as a future side-quest anchor ("Hollywood Doesn't Sleep").
  // Her circumstance is survival-tier but her SOUL runs high: fearless Throat (she
  // calls out every fake guru on the block), strong Solar Plexus (will), and a Heart
  // kept open for the girls too new to see danger smiling at them. Charm is tactical —
  // armor, not need. She placed near Bailey on purpose: she's watching over her.
  soul({
    id: "roxy_valente",
    name: 'Rosangela "Roxy" Valente',
    occupation: "Walking Tour Guide · Hollywood Blvd",
    archetype: "Streetwise Brazilian Survivor",
    age: 46,
    narrative:
      "Book her tour for the movie trivia; stay for the truth. Tourists see attitude, curves, and sunglasses. The girls who are too new to know better see the one person on this block who'll step between them and a smiling predator. Rio to Newark to here — she survived worse than anything Hollywood can bring. Eu sobrevivi coisa pior.",
    needs: { survival: 46, safety: 48, belonging: 58, esteem: 56, actualization: 58 },
    traits: traits({ antagonism: 50, disinhibition: 42, negativeAffectivity: 38, detachment: 30, psychoticism: 15 }),
    aceScore: 7,
    resilience: 88,
    kohlberg: 5,
    soulAge: "Old",
    initiationLevel: 4,
    chakras: chakras([48, 42, 66, 62, 70, 58, 38]),
    consciousAspiration: "Run my route, stay three steps ahead, make it through another night",
    soulPurpose: "Be the protector she never had — stand between the new girls and the danger that's smiling at them",
    affinities: { work: 1.5, perform: 1.3, socialize: 1.3, gaze: 1.1, hustle: 1.0, rest: 1.0 },
    row: "south",
    xMin: 720,
    xMax: 1000,
    baseSpeed: 13,
  }),

  // Lori Castellano — "The Quiet Broker". Not the Ivar Ave crew's register: an
  // industry/nightlife-adjacent supplier who built real agency and status in a
  // marginalizing economy (grounded in the "queenpin"/psychological-empowerment
  // literature, not the corner-dealer cliché). Kohlberg 5 — a genuinely self-
  // constructed ethical code (harm reduction, hard boundaries), independent of
  // and sometimes in conflict with the law. Her low Belonging locks her Maslow
  // level at "starved for connection" no matter how high her Esteem climbs —
  // the model enforces the same irony the backstory is built on.
  soul({
    id: "lori",
    name: "Lori Castellano",
    occupation: "Independent Supplier, Industry & Nightlife Circuit",
    archetype: "The Quiet Broker",
    age: 37,
    narrative:
      "She spent her twenties as the talent coordinator everyone relied on and nobody promoted — invisible the way competent women in service roles always are. A joke question at a wrap party turned into a supply line into the industry's afterparties and unphotographed dinners. She works relationships and discretion now, not corners, and she's made more than any boss who once passed her over. Everyone in her life needs something from her; she's forgotten how to let anyone need nothing at all.",
    needs: { survival: 78, safety: 45, belonging: 28, esteem: 71, actualization: 26 },
    traits: traits({ negativeAffectivity: 55, detachment: 62, antagonism: 38, disinhibition: 18, psychoticism: 14 }),
    aceScore: 4,
    resilience: 74,
    kohlberg: 5,
    soulAge: "Mature",
    initiationLevel: 2,
    chakras: chakras([55, 45, 76, 24, 58, 34, 12]),
    consciousAspiration:
      "Get enough of a cushion to walk away clean — buy the building, go legitimate, be undeniable on paper the way I already am in practice",
    soulPurpose:
      "See the young women passing through this world the way almost no one else here can — and let that gift protect them, not just herself",
    affinities: { hustle: 1.6, socialize: 1.4, work: 1.2, gaze: 1.1, rest: 1.0 },
    row: "south",
    xMin: 900,
    xMax: 1180,
    baseSpeed: 18,
  }),

  // Nia Brooks — "The Real One". First of a 5-person friend crew being added one
  // at a time. Grounded in the real, documented history of women (especially
  // Black and Latina women) as the uncredited founders of sneaker/streetwear
  // culture — women who built their own communities because the mainstream
  // scene wouldn't recognize them. Her Solar Plexus (esteem) runs low despite
  // real mastery; her Heart is healthier than you'd expect, because the crew
  // she built for herself actually works.
  soul({
    id: "nia",
    name: "Nia Brooks",
    occupation: "Sneaker Reseller & Community Organizer",
    archetype: "The Real One (Underestimated Sneakerhead)",
    age: 24,
    narrative:
      "She's been in this culture since she was twelve, trading Jordans in middle-school hallways before half these resale apps even existed. The scene still treats her like a tourist in her own house, so she stopped waiting for an invitation — built her own group chat for the girls the culture forgets to credit, runs pop-up trades off her fanny pack like a mobile shop, and remembers every name that ever doubted her.",
    needs: { survival: 58, safety: 55, belonging: 62, esteem: 34, actualization: 48 },
    traits: traits({ negativeAffectivity: 48, detachment: 22, antagonism: 46, disinhibition: 30, psychoticism: 15 }),
    aceScore: 3,
    resilience: 78,
    kohlberg: 4,
    soulAge: "Young",
    initiationLevel: 2,
    chakras: chakras([54, 46, 38, 58, 50, 46, 16]),
    consciousAspiration:
      "Make them recognize I built this — get my name said in the culture for real, not as somebody's afterthought",
    soulPurpose:
      "Build the door she had to force open herself so the next overlooked girl never has to fight alone for a seat at the table",
    affinities: { hustle: 1.5, perform: 1.3, socialize: 1.4, work: 1.1, gaze: 1.0, rest: 1.0 },
    row: "north",
    xMin: 950,
    xMax: 1150,
    baseSpeed: 20,
  }),

  // Kiki Torres — "The Founder". Second of the 5-person friend crew. Grounded in
  // the real, documented pattern of very young bootstrap streetwear founders who
  // self-fund, self-model, and hustle their own line into existence with no
  // outside capital (sources in conversation). "citylittles" is HER brand, not
  // just something she wears — the Gucci belt is the one real designer piece she
  // let herself buy as proof it's working. Her Throat runs hot (she's the loud,
  // public-facing one); her Heart lags well behind it — the audience she built
  // isn't the same as being truly known.
  soul({
    id: "kiki",
    name: "Kiki Torres",
    occupation: "Founder & Model, \"citylittles\" Streetwear",
    archetype: "The Founder (Self-Made Streetwear Brand)",
    age: 22,
    narrative:
      "She started citylittles with a heat press in her bedroom and a duffel bag full of pieces she hand-pressed herself — no investor, no team, just her modeling every drop because she couldn't afford a photographer. Left the Bay for Hollywood chasing a bigger audience for it. Online she's all confidence; she hasn't told anyone how close the whole thing came to folding last month.",
    needs: { survival: 42, safety: 40, belonging: 38, esteem: 58, actualization: 44 },
    traits: traits({ negativeAffectivity: 52, detachment: 40, antagonism: 42, disinhibition: 28, psychoticism: 12 }),
    aceScore: 3,
    resilience: 76,
    kohlberg: 4,
    soulAge: "Young",
    initiationLevel: 1,
    chakras: chakras([40, 32, 54, 42, 64, 44, 14]),
    consciousAspiration:
      "Blow citylittles up into a real empire — prove the Bay didn't lose its best one when I left",
    soulPurpose:
      "Let herself be known for more than the brand she built to be seen at all — real connection, not just an audience",
    affinities: { hustle: 1.5, perform: 1.5, work: 1.3, socialize: 1.1, gaze: 1.0, rest: 1.0 },
    row: "north",
    xMin: 1000,
    xMax: 1200,
    baseSpeed: 17,
  }),

  // Maya Fields — "The Anchor". Third of the friend crew. Grounded in real
  // parentification research (Jurkovic, 1997) and the well-documented
  // "grandfamilies" pattern — kids raised by a grandparent when a parent can't
  // cope. Her moral reasoning is really Gilligan's "ethic of care" (a mature,
  // principled orientation Kohlberg's ladder under-recognizes because it wasn't
  // normed on it) more than textbook Kohlberg-5, encoded here as 5 anyway for
  // model consistency. Chronologically the youngest of the new crew but
  // authored as an "Old" soul on purpose — she matured on a schedule she didn't
  // choose. Low `rest` affinity is deliberate: she under-prioritizes her own
  // recovery, mechanically enacting the caretaker-neglects-self pattern.
  soul({
    id: "maya",
    name: "Maya Fields",
    occupation: "Home Health Aide",
    archetype: "The Anchor (Parentified Caretaker)",
    age: 23,
    narrative:
      "Her grandmother Rose raised her while her mom tried to get steady, and by ten Maya was the one keeping the lights paid and everyone fed. Rose passed two years ago; the tattoo up her arm says her name so she's never really gone. Now Maya works home health during the day and holds the group chat together at night — everyone's first call when it's bad, the one who never seems to need calling back.",
    needs: { survival: 52, safety: 50, belonging: 44, esteem: 40, actualization: 34 },
    traits: traits({ negativeAffectivity: 50, detachment: 18, antagonism: 20, disinhibition: 16, psychoticism: 10 }),
    aceScore: 5,
    resilience: 80,
    kohlberg: 5,
    soulAge: "Old",
    initiationLevel: 3,
    chakras: chakras([48, 30, 46, 48, 56, 46, 40]),
    consciousAspiration:
      "Keep everyone around me okay — don't let anyone else fall through the cracks I fell through",
    soulPurpose:
      "Learn that she's allowed to need someone too — love was never supposed to be a one-way job",
    affinities: { socialize: 1.6, work: 1.2, gaze: 1.0, hustle: 0.9, rest: 0.8 },
    row: "north",
    xMin: 1050,
    xMax: 1250,
    baseSpeed: 14,
  }),

  // Jordyn Hale — "The Curated Ease". Fourth of the friend crew. Grounded in the
  // real "soft life" movement (Black women deliberately trading the "strong
  // Black woman" trope for rest as reclaimed dignity, not just materialism —
  // sources in conversation) and its documented critique — the well-known
  // "labor of leisure" tension where presenting effortless calm online requires
  // real, invisible work. Distinct from Sasha (grandiose, parasocial-chasing
  // "Reality-TV Influencer") — Jordyn's whole brand is calm, not spectacle. Low
  // `rest` affinity is deliberate, same device as Maya: she sells peace without
  // actually landing on "resting" much herself. Kohlberg 3 (not the crew's
  // stage-5 tier) on purpose — she's still fundamentally living for how she's
  // perceived, a textbook conventional/social-approval orientation.
  soul({
    id: "jordyn",
    name: "Jordyn Hale",
    occupation: '"Soft Life" Content Creator',
    archetype: "The Curated Ease (Soft Life Influencer)",
    age: 26,
    narrative:
      "She posts a slow morning, a cup of tea, gold hoops catching the light — soft, unbothered, at peace. What she doesn't post: the three hours of editing before sunrise, the brand emails at midnight, the deadline calendar behind every 'day off.' She built the ease she sells because she never had it growing up, and some mornings she can't tell anymore if she's finally living it or just still performing it for the camera.",
    needs: { survival: 68, safety: 62, belonging: 42, esteem: 52, actualization: 38 },
    traits: traits({ negativeAffectivity: 46, detachment: 35, antagonism: 22, disinhibition: 20, psychoticism: 12 }),
    aceScore: 4,
    resilience: 72,
    kohlberg: 3,
    soulAge: "Young",
    initiationLevel: 1,
    chakras: chakras([60, 34, 54, 44, 60, 42, 16]),
    consciousAspiration:
      "Build the life that LOOKS as peaceful as I need people to believe it is — proof I made it out soft instead of hard",
    soulPurpose:
      "Stop performing rest long enough to actually feel it — let the peace be real instead of just well-lit",
    affinities: { perform: 1.6, work: 1.3, gaze: 1.1, socialize: 1.0, hustle: 0.9, rest: 0.7 },
    row: "north",
    xMin: 1150,
    xMax: 1350,
    baseSpeed: 13,
  }),

  // Dalia Nasser — "The Carrier". Fifth and last of the friend crew. Palestinian-
  // American; the keffiyeh is a deliberate, chosen link to a homeland she may
  // have never physically stood in — diaspora Palestinians describe wearing it
  // as "carrying home on my shoulders" (sources in conversation). Grounded in
  // real academic work on the "unsettled belonging" of Palestinian-American
  // youth (Abu El-Haj) — caught between transnational belonging and an
  // American public life that periodically casts them as not-quite-belonging.
  // Her ACE score stays low deliberately: her stressors are societal/identity-
  // based, not family dysfunction, and conflating the two would be a category
  // error — the chronic-vigilance weight lives in Safety and NegativeAffectivity
  // instead. Highest Crown seed of the new crew: she's already the furthest
  // along toward something beyond self-interest (the archive project), even
  // though she hasn't stopped needing to *prove* it yet.
  soul({
    id: "dalia",
    name: "Dalia Nasser",
    occupation: "Retail Associate — Building a Family Oral-History Archive",
    archetype: "The Carrier (Diaspora Homeland-Keeper)",
    age: 21,
    narrative:
      "She's never set foot in the village her grandfather describes in the voice memos she's been quietly collecting since she was sixteen — recording him before the stories go with him. The keffiyeh isn't a costume; it's the one thing she can wrap around herself that makes the distance feel smaller. At school she was always the one explaining herself; here on the Boulevard, surrounded by people building their own reinventions, she's stopped apologizing for carrying hers.",
    needs: { survival: 56, safety: 44, belonging: 48, esteem: 46, actualization: 52 },
    traits: traits({ negativeAffectivity: 48, detachment: 30, antagonism: 24, disinhibition: 18, psychoticism: 10 }),
    aceScore: 2,
    resilience: 74,
    kohlberg: 5,
    soulAge: "Mature",
    initiationLevel: 3,
    chakras: chakras([46, 40, 48, 48, 58, 52, 46]),
    consciousAspiration:
      "Finish the archive and prove — to everyone, maybe herself most of all — that she belongs to a place she's never even stood in",
    soulPurpose:
      "Let carrying her people's memory be enough on its own — she doesn't need anyone's permission or proof to claim what's already hers",
    affinities: { gaze: 1.5, socialize: 1.3, work: 1.2, hustle: 0.9, rest: 1.0 },
    row: "north",
    xMin: 1250,
    xMax: 1450,
    baseSpeed: 15,
  }),

  // --- New playable characters (front+back sprites in public/spirits/). Full arcs come
  // later from the user; these profiles are plausible placeholders so the panels render.
  // NOTE: "Bella Cruz" is Nathaniel's SURNAME, not a separate character; "Sorriso" (smile)
  // and "DEZ" (the playmaker's #10) are his two nicknames.
  soul({
    id: "nathaniel",
    name: 'Nathaniel "Sorriso / DEZ" Bella Cruz',
    occupation: "Brazilian Transplant · Working the Block",
    archetype: "The Newcomer (charismatic hustler)",
    age: 23,
    narrative:
      "Fresh off the plane from Brazil with a duffel, a killer smile, and a number-ten's swagger. They call him Sorriso for the grin that opens every door and DEZ for the way he reads a room like a pitch. He's chasing something on this Boulevard he can't quite name yet — his story is still being written.",
    needs: { survival: 44, safety: 48, belonging: 58, esteem: 52, actualization: 62 },
    traits: traits({ negativeAffectivity: 30, detachment: 18, antagonism: 24, disinhibition: 46, psychoticism: 14 }),
    aceScore: 3,
    resilience: 78,
    kohlberg: 4,
    soulAge: "Young",
    initiationLevel: 2,
    chakras: chakras([56, 52, 58, 60, 62, 50, 22]),
    consciousAspiration: "Make it here — turn the smile into something real and lasting",
    soulPurpose: "Learn that being truly known beats being universally liked",
    affinities: { socialize: 1.5, perform: 1.3, hustle: 1.3, gaze: 1.1, work: 1.1, rest: 1.0 },
    row: "north",
    xMin: 330,
    xMax: 420,
    baseSpeed: 24,
  }),
  soul({
    id: "elizabeth",
    name: "Elizabeth Taylor",
    occupation: "Detective",
    archetype: "The Investigator",
    age: 34,
    narrative:
      "Badge on her belt, sidearm on her hip, and a read on people most of the Boulevard never sees coming. She works the cases nobody else will touch and trusts almost no one — a discipline that keeps her sharp and keeps her lonely. Her full story is still to come.",
    needs: { survival: 62, safety: 54, belonging: 38, esteem: 60, actualization: 56 },
    traits: traits({ negativeAffectivity: 40, detachment: 52, antagonism: 38, disinhibition: 16, psychoticism: 14 }),
    aceScore: 4,
    resilience: 80,
    kohlberg: 5,
    soulAge: "Mature",
    initiationLevel: 3,
    chakras: chakras([58, 60, 44, 66, 62, 56, 30]),
    consciousAspiration: "Close the case that's haunted her — get the truth, no matter the cost",
    soulPurpose: "Let someone past the guard, and learn that justice without mercy is only control",
    affinities: { work: 1.6, gaze: 1.4, hustle: 1.2, socialize: 1.0, rest: 1.0 },
    row: "south",
    xMin: 360,
    xMax: 450,
    baseSpeed: 18,
  }),
  // Sorriso's love interest — an LA-native scene veteran. Mature and powerful, not "old":
  // high Esteem/Actualization (self-assured), strong resilience (survived LA three times over),
  // Kohlberg 5 (her own code), and enough Antagonism to see through ego instantly.
  soul({
    id: "vee_knox",
    name: 'Valentina "Vee" Knox',
    occupation: "Scene Veteran · Nightlife & Music",
    archetype: "Street-Glam Survivor",
    age: 45,
    narrative:
      "Born and raised in LA — she's watched this city reinvent itself three times, buried friends and fads both, and still walks like she owns the block. She knows the nightlife, the music, the club politics, the fake smiles, and every human disaster wearing sunglasses indoors. Sorriso is younger, intense, still proving himself; she likes him fine, but she clocked his ego in about four seconds. Somebody has to babysit male confidence before it becomes a felony.",
    needs: { survival: 58, safety: 60, belonging: 52, esteem: 74, actualization: 66 },
    traits: traits({ negativeAffectivity: 28, detachment: 40, antagonism: 44, disinhibition: 30, psychoticism: 12 }),
    aceScore: 5,
    resilience: 90,
    kohlberg: 5,
    soulAge: "Old",
    initiationLevel: 4,
    chakras: chakras([62, 58, 60, 66, 68, 60, 40]),
    consciousAspiration: "Keep her corner of the scene real — spot the fakes, protect what's worth protecting, never get played",
    soulPurpose: "Teach the hungry young ones that longevity beats a hot minute — and let herself be genuinely moved by someone again",
    affinities: { socialize: 1.5, perform: 1.3, gaze: 1.3, hustle: 1.1, work: 1.0, rest: 1.0 },
    row: "north",
    xMin: 200,
    xMax: 300,
    baseSpeed: 15,
  }),
  soul({
    id: "lua",
    name: 'Rafaela "Lua" Moreira',
    occupation: "DJ & Owner · Eclipse Nightclub",
    archetype: "Nightlife Mogul",
    age: 29,
    narrative:
      "Brazilian, born in Salvador, raised half in São Paulo's warehouse-party scene. She came to Hollywood with two crates of records and a chip on her shoulder, spun other people's rooms for six years, then bet everything and opened Eclipse — now the club everyone's trying to get into. She headlines her own booth. The brass knuckles and the blade aren't for show: a woman who owns the door in this town learns fast that charm is a tool and fear is a lock. Warm to the people she claims, ice to the ones who try her.",
    needs: { survival: 62, safety: 58, belonging: 54, esteem: 80, actualization: 72 },
    traits: traits({ negativeAffectivity: 24, detachment: 30, antagonism: 46, disinhibition: 52, psychoticism: 18 }),
    aceScore: 4,
    resilience: 88,
    kohlberg: 4,
    soulAge: "Mature",
    initiationLevel: 3,
    chakras: chakras([64, 74, 70, 60, 66, 52, 34]),
    consciousAspiration: "Make Eclipse the name in LA nightlife — and never answer to anyone again",
    soulPurpose: "Turn a room full of strangers into one heartbeat — and learn to let someone past the door she guards",
    affinities: { perform: 1.7, socialize: 1.5, hustle: 1.4, gaze: 1.2, work: 1.1, rest: 0.9 },
    row: "north",
    xMin: 480,
    xMax: 600,
    baseSpeed: 18,
  }),
  soul({
    id: "bibi",
    name: 'Beatriz "Bibi" Moreira',
    occupation: "Fashion Designer & CEO · Boss Energy",
    archetype: "Fashion Mogul",
    age: 32,
    narrative:
      "Lua's older sister. Same Salvador roots, opposite hustle — while Lua chased the booth, Bibi chased the boardroom, and built 'Boss Energy' from a market stall of hand-sewn pieces into a Hollywood fashion house dressing half the red carpets in town. Immaculate, calculating, allergic to being underestimated: BUILD, BRAND, BANK is printed on her card and tattooed on her decisions. She loves Lua fiercely and worries about the blade her sister carries — but the two of them against this city is the only partnership she fully trusts.",
    needs: { survival: 70, safety: 66, belonging: 56, esteem: 84, actualization: 74 },
    traits: traits({ negativeAffectivity: 22, detachment: 40, antagonism: 42, disinhibition: 30, psychoticism: 12 }),
    aceScore: 4,
    resilience: 86,
    kohlberg: 4,
    soulAge: "Mature",
    initiationLevel: 3,
    chakras: chakras([66, 60, 78, 58, 70, 54, 36]),
    consciousAspiration: "Make Boss Energy a global name — dress the world, answer to no one",
    soulPurpose: "Prove where she came from is a crown, not a ceiling — and let her worth rest on more than the empire",
    affinities: { hustle: 1.7, work: 1.5, gaze: 1.3, socialize: 1.3, perform: 1.0, rest: 0.9 },
    row: "north",
    xMin: 640,
    xMax: 760,
    baseSpeed: 16,
  }),
];

// The cast was authored for the old 1600-wide single boulevard. Phase 2b opened the
// world into a wider square (Hollywood Blvd + Highland Ave), so respread each soul's
// x-range across the new width and pin them to a frontage sidewalk line (patrolY).
// A few are then relocated onto Highland Ave's sidewalks so the new N/S corridor is
// populated too — the player walking up/down Highland actually meets someone.
// (Values hardcoded rather than imported to keep the soul layer independent of scene
// geometry; they mirror the constants in src/game/sceneData.ts.)
// The cast's x was authored for a 1600-wide strip; spread them across the whole 17200-wide
// district so the player meets someone on every block.
const XSCALE = 17200 / 1600;
const NORTH_FRONTAGE_Y = 1028;
const SOUTH_FRONTAGE_Y = 1818;
const HIGHLAND_W_SIDEWALK_X = 3580; // west sidewalk of Highland Ave (cross street x≈3700)
const HIGHLAND_E_SIDEWALK_X = 3820; // east sidewalk

// souls posted along Highland Ave (fixed x on a sidewalk, standing at a given y)
const HIGHLAND_POSTS: Record<string, { x: number; y: number }> = {
  ruben: { x: HIGHLAND_E_SIDEWALK_X, y: 800 }, // up Highland, north of the blvd
  javi: { x: HIGHLAND_W_SIDEWALK_X, y: 560 }, // further up
  hector: { x: HIGHLAND_E_SIDEWALK_X, y: 1520 }, // down Highland, south of the blvd
};

// Souls temporarily removed from the game (still fully defined above). To bring one back,
// delete its id from this set — nothing else needs changing.
const HIDDEN_SOULS = new Set(["roxy_valente", "maya"]);

export const ROSTER: Soul[] = RAW.filter((s) => !HIDDEN_SOULS.has(s.id)).map((s) => {
  const post = HIGHLAND_POSTS[s.id];
  if (post) {
    return { ...s, xMin: post.x, xMax: post.x, patrolY: post.y };
  }
  return {
    ...s,
    xMin: Math.round(s.xMin * XSCALE),
    xMax: Math.round(s.xMax * XSCALE),
    patrolY: s.row === "north" ? NORTH_FRONTAGE_Y : SOUTH_FRONTAGE_Y,
  };
});
