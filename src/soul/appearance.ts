// deriveAppearance — maps live Soul state to what the player SEES: the aura color
// (shown now) and the clothing / grooming tags (consumed by real sprites in Phase 2).
//
// The clothing tag implements the locked "5 curated sub-flavors" decision: at the
// esteem tier, WHY someone curates their look (old money vs new money vs aspirant vs
// trend vs ironic) is psychologically distinct, so the tag distinguishes them.

import type { Soul } from "./types.ts";
import { maslowLevel, chakraState } from "./derive.ts";
import { activityLabel } from "./engine.ts";

export interface Appearance {
  auraColor: string;
  clothingTag: string;
  groomingTag: string;
  activityLabel: string;
}

// Aura reflects the soul's emotional + spiritual state, per the doctrine's aura
// system (warm gold = open, grey = despair, red = anger, cyan = ascended, etc.).
export function auraColor(soul: Soul): string {
  const crownOpen = chakraState(soul.chakras.Crown) === "open";

  // Ascended-tier reads unmistakably different — rare.
  if (soul.initiationLevel >= 5 && crownOpen) return "#57e0d6"; // cyan
  // Peak experience: very high meaning + open crown.
  if (soul.needs.actualization > 85 && crownOpen) return "#f2ede0"; // white shimmer

  const e = soul.emotion;
  switch (e.primary) {
    case "anger":
      return "#c94d2c"; // red-tinged
    case "fear":
      return "#d98a3a"; // anxious orange
    case "sadness":
      return soul.resilience < 35 ? "#8a8a8a" : "#9aa6b0"; // grey despair / muted blue
    case "joy":
      return "#e8c85a"; // warm gold
    case "anticipation":
      return "#d9a24a"; // amber
    case "trust":
      return "#b7d8c2"; // soft green
    default:
      return "#a9c7e8"; // pale blue — content / stable
  }
}

// Clothing tag: survival/safety tier → worn/practical; esteem tier → one of the 5
// curated sub-flavors (inferred from archetype + traits); actualization → authentic.
export function clothingTag(soul: Soul): string {
  // Faction colors are a cluster-level uniform worn regardless of need tier, so they
  // override the Maslow-driven flavor. Deliberately the same read for every member —
  // the player has to open the soul to tell the shot-caller from the kid getting out.
  if (soul.faction) return "faction-coded";

  const level = maslowLevel(soul.needs).level;
  const arc = soul.archetype.toLowerCase();
  const t = soul.traits;

  if (level <= 1) return "worn";
  if (level === 2) return soul.needs.survival < 45 ? "worn" : "practical";
  if (level === 3) return t.detachment > 55 ? "practical" : "authentic-casual";

  if (level === 4) {
    // the five curated sub-flavors
    if (/mogul|executive|producer/.test(arc) && (soul.soulAge === "Old" || soul.resilience > 65))
      return "quiet-curated";
    if (/influencer|reality/.test(arc) || (t.antagonism > 55 && t.disinhibition > 45))
      return "loud-curated";
    if (/aspirant|actress|actor|performer|busker/.test(arc)) return "aspirational-curated";
    if (/trend|fashion/.test(arc)) return "trend-curated";
    if (soul.needs.actualization > 55) return "ironic-curated";
    return "aspirational-curated";
  }

  return "authentic"; // level 5–6
}

export function groomingTag(soul: Soul): string {
  if (soul.needs.survival < 35 || soul.traits.disinhibition > 62) return "unkempt";
  if (soul.traits.detachment > 60) return "minimal";
  if (soul.needs.esteem > 52 && soul.traits.disinhibition < 45) return "maintained";
  return "casual";
}

export function deriveAppearance(soul: Soul): Appearance {
  return {
    auraColor: auraColor(soul),
    clothingTag: clothingTag(soul),
    groomingTag: groomingTag(soul),
    activityLabel: activityLabel(soul.activity),
  };
}
