// The Soul Engine — a lightweight utility-AI tick (the Sims lineage): each sim
// minute, needs decay, the soul scores its candidate activities by current need
// deficits × per-soul affinities × trait modifiers, does the winner, and the winner
// replenishes the targeted needs. Then the three-system interference rules pull each
// chakra toward the psychological/social state that gates it — bottom-up, per the
// doctrine ("a blocked Root prevents everything above it").
//
// Pure and headless: no DOM, no rendering. The renderer and panel READ this; the
// sim-harness ticks it from Node.

import {
  type Soul,
  type Needs,
  type NeedKey,
  type ChakraName,
  NEED_KEYS,
  CHAKRA_ORDER,
} from "./types.ts";
import { deriveEmotion, clamp } from "./derive.ts";

// ---- activities ------------------------------------------------------------

export interface Activity {
  id: string;
  label: string;
  stationary: boolean; // does the sprite stop moving while doing this?
  // Base desirability given current soul state (before per-soul affinity).
  score: (s: Soul) => number;
  // Per-sim-minute effect on needs while performing it.
  effect: Partial<Needs>;
}

// Urgency-weighted deficit: grows linearly with the deficit, but accelerates sharply
// once a need drops below ~45 so a critically-starved need decisively wins the utility
// contest (a soul rushes to fix what it most lacks) instead of any one axis flatlining.
function urgency(value: number): number {
  const deficit = 100 - value;
  const critical = Math.max(0, 45 - value);
  return deficit + (critical * critical) / 18;
}
const D = (n: Soul["needs"], k: NeedKey) => urgency(n[k]);

// The natural ceiling for each need, derived from starting circumstance (the authored
// initial need already encodes wealth/situation) plus psychology: detachment/antagonism
// cap belonging, low resilience caps esteem, and — critically — actualization is gated
// by spiritual initiation, so only developed souls can reach Maslow 5–6 on their own.
const HEADROOM = 20;
export function computeCeilings(s: Soul): Needs {
  const t = s.traits;
  return {
    survival: clamp(s.needs.survival + HEADROOM),
    safety: clamp(s.needs.safety + HEADROOM),
    belonging: clamp(
      Math.min(s.needs.belonging + HEADROOM, 100 - t.detachment * 0.55 - t.antagonism * 0.2),
    ),
    esteem: clamp(Math.min(s.needs.esteem + HEADROOM, 100 - (100 - s.resilience) * 0.4)),
    actualization: clamp(Math.min(s.needs.actualization + HEADROOM, 40 + s.initiationLevel * 10)),
  };
}

export const ACTIVITIES: Activity[] = [
  {
    id: "rest",
    label: "resting",
    stationary: true,
    score: (s) => D(s.needs, "survival") * 1.25 + D(s.needs, "safety") * 0.6,
    effect: { survival: 1.4, safety: 0.6, esteem: -0.05 },
  },
  {
    id: "work",
    label: "working",
    stationary: true,
    score: (s) => D(s.needs, "survival") * 0.9 + D(s.needs, "esteem") * 0.35,
    effect: { survival: 0.9, esteem: 0.3, safety: 0.3, belonging: -0.05 },
  },
  {
    id: "perform",
    label: "performing",
    stationary: true,
    score: (s) =>
      D(s.needs, "esteem") * 0.8 +
      D(s.needs, "belonging") * 0.45 -
      s.traits.detachment * 0.2,
    effect: { esteem: 0.9, belonging: 0.5, survival: -0.35 },
  },
  {
    id: "socialize",
    label: "connecting with someone",
    stationary: true,
    score: (s) => D(s.needs, "belonging") * (1 - s.traits.detachment / 160),
    effect: { belonging: 1.1, esteem: 0.2, actualization: 0.1 },
  },
  {
    id: "hustle",
    label: "working an angle",
    stationary: false,
    score: (s) => D(s.needs, "esteem") * (0.4 + s.traits.antagonism / 130),
    effect: { esteem: 0.6, survival: 0.3, belonging: -0.2 },
  },
  {
    id: "gaze",
    label: "taking it all in",
    stationary: true,
    score: (s) => D(s.needs, "actualization") * 0.55 + D(s.needs, "belonging") * 0.15,
    effect: { actualization: 1.0, belonging: 0.25, esteem: 0.1 },
  },
  {
    id: "reminisce",
    label: "lost in the past",
    stationary: true,
    score: (s) => (s.needs.esteem < 45 ? D(s.needs, "belonging") * 0.5 : 8),
    effect: { belonging: -0.1, actualization: -0.05, esteem: 0.05 },
  },
  {
    id: "wander",
    label: "wandering the boulevard",
    stationary: false,
    score: () => 12, // baseline fallback so there's always something to do
    effect: { actualization: 0.15, survival: -0.1 },
  },
];

const ACTIVITY_BY_ID = new Map(ACTIVITIES.map((a) => [a.id, a]));

// ---- defaults --------------------------------------------------------------

// Per-sim-minute baseline decay. Survival ticks down fastest; meaning drifts slowly.
const DEFAULT_DECAY: Needs = {
  survival: 0.14,
  safety: 0.08,
  belonging: 0.1,
  esteem: 0.09,
  actualization: 0.05,
};

// Replenish strength when an activity satisfies a need (see tickSoul step 3). Tuned
// so equilibrium sits a bit below the ceiling — souls stay a little hungry.
const REPLENISH_GAIN = 1.4;

// How fast each chakra's openness approaches the state that gates it, per sim-minute.
const CHAKRA_RATE = 0.02;
// Bottom-up ceiling: a chakra can't be more than this much more open than the one
// below it. Enforces "chakras clear from the bottom up".
const BOTTOM_UP_MARGIN = 34;

// The target openness (0–100) each chakra is pulled toward, from the soul's
// psychological/social/spiritual state — the three-system interference map made real.
function chakraTargets(s: Soul): Record<ChakraName, number> {
  const n = s.needs;
  const t = s.traits;
  return {
    Root: (n.survival + n.safety) / 2,
    Sacral: (100 - t.negativeAffectivity) * 0.5 + n.belonging * 0.5 - s.aceScore * 3,
    "Solar Plexus": n.esteem * 0.7 + (100 - t.antagonism) * 0.3,
    Heart: n.belonging * 0.8 + s.resilience * 0.2,
    Throat: n.esteem * 0.5 + (100 - t.psychoticism) * 0.5,
    "Third Eye": n.actualization * 0.6 + (100 - t.detachment) * 0.4,
    Crown: clamp(s.initiationLevel * 13 + n.actualization * 0.3),
  };
}

// ---- tick ------------------------------------------------------------------

export interface Transition {
  soulId: string;
  name: string;
  atMinutes: number;
  text: string;
}

// Advance one soul by dtMin sim-minutes. Returns any notable transitions (activity
// change, Maslow-level shift signalled via emotion flip, chakra state crossing).
export function tickSoul(soul: Soul, dtMin: number, atMinutes: number): Transition[] {
  const transitions: Transition[] = [];
  const prevNeeds: Needs = { ...soul.needs };
  const prevActivity = soul.activity;
  const prevEmotion = soul.emotion.primary;

  // 1. decay
  const decay = soul.decay;
  for (const k of NEED_KEYS) {
    const rate = decay?.[k] ?? DEFAULT_DECAY[k];
    soul.needs[k] = clamp(soul.needs[k] - rate * dtMin);
  }

  // 2. choose the highest-utility activity (base score × per-soul affinity)
  let best = ACTIVITIES[0];
  let bestScore = -Infinity;
  for (const a of ACTIVITIES) {
    const affinity = soul.affinities[a.id] ?? 1;
    const s = a.score(soul) * affinity;
    if (s > bestScore) {
      bestScore = s;
      best = a;
    }
  }
  soul.activity = best.id;

  // 3. apply the activity's effect. Gains diminish as the need approaches this soul's
  //    ceiling (and can't exceed it), so souls settle into a psychology-shaped band
  //    instead of everyone drifting to 100. Costs (negative effects) are not
  //    ceiling-limited — anyone can be dragged down.
  const ceilings = soul.ceilings;
  for (const k of NEED_KEYS) {
    const delta = best.effect[k];
    if (!delta) continue;
    if (delta > 0) {
      const ceil = ceilings ? ceilings[k] : 100;
      const gap = Math.max(0, ceil - soul.needs[k]);
      const gain = delta * REPLENISH_GAIN * (gap / 100) * dtMin;
      soul.needs[k] = Math.min(ceil, soul.needs[k] + gain);
    } else {
      soul.needs[k] = clamp(soul.needs[k] + delta * dtMin);
    }
  }

  // 4. interference: pull chakras toward their gating targets, then enforce
  //    bottom-up clearing.
  const targets = chakraTargets(soul);
  for (const name of CHAKRA_ORDER) {
    const cur = soul.chakras[name];
    soul.chakras[name] = clamp(cur + (targets[name] - cur) * CHAKRA_RATE * dtMin);
  }
  for (let i = 1; i < CHAKRA_ORDER.length; i++) {
    const below = soul.chakras[CHAKRA_ORDER[i - 1]];
    const name = CHAKRA_ORDER[i];
    soul.chakras[name] = Math.min(soul.chakras[name], below + BOTTOM_UP_MARGIN);
  }

  // 5. recompute emotion from the new state + recent deltas
  soul.emotion = deriveEmotion(soul, prevNeeds);

  // 6. log notable transitions
  if (soul.activity !== prevActivity) {
    transitions.push({
      soulId: soul.id,
      name: soul.name,
      atMinutes,
      text: `${ACTIVITY_BY_ID.get(prevActivity)?.label ?? prevActivity} → ${best.label}`,
    });
  }
  if (soul.emotion.primary !== prevEmotion) {
    transitions.push({
      soulId: soul.id,
      name: soul.name,
      atMinutes,
      text: `emotion ${prevEmotion} → ${soul.emotion.primary} (${Math.round(soul.emotion.intensity)})`,
    });
  }

  return transitions;
}

// ---- engine ----------------------------------------------------------------

const MIN_PER_REAL_SECOND = 1; // at 1× speed, 1 real second = 1 sim minute
const TICK_MINUTES = 1; // fixed sim-timestep

export class SoulEngine {
  readonly souls: Soul[];
  private byId: Map<string, Soul>;
  speed = 1; // 0 (paused), 1, 5, 20 — set by the HUD time controls
  clockMinutes: number;
  day = 1;
  private acc = 0; // leftover sim-minutes between fixed ticks
  log: Transition[] = [];

  constructor(souls: Soul[], startMinutes = 14 * 60 + 34) {
    this.souls = souls.map((s) => {
      const clone: Soul = { ...s, needs: { ...s.needs }, chakras: { ...s.chakras } };
      clone.ceilings = s.ceilings ?? computeCeilings(clone);
      return clone;
    });
    this.byId = new Map(this.souls.map((s) => [s.id, s]));
    this.clockMinutes = startMinutes;
  }

  get(id: string): Soul | undefined {
    return this.byId.get(id);
  }

  // Advance the whole city by realDtSeconds of wall-clock, scaled by speed.
  advance(realDtSeconds: number) {
    if (this.speed <= 0) return;
    this.acc += realDtSeconds * this.speed * MIN_PER_REAL_SECOND;
    while (this.acc >= TICK_MINUTES) {
      this.acc -= TICK_MINUTES;
      this.stepClock(TICK_MINUTES);
      for (const soul of this.souls) {
        const ts = tickSoul(soul, TICK_MINUTES, this.day * 1440 + this.clockMinutes);
        if (ts.length) {
          this.log.push(...ts);
          if (this.log.length > 200) this.log.splice(0, this.log.length - 200);
        }
      }
    }
  }

  private stepClock(dtMin: number) {
    this.clockMinutes += dtMin;
    while (this.clockMinutes >= 1440) {
      this.clockMinutes -= 1440;
      this.day += 1;
    }
  }

  clockString(): string {
    const h24 = Math.floor(this.clockMinutes / 60);
    const m = Math.floor(this.clockMinutes % 60);
    const ampm = h24 >= 12 ? "PM" : "AM";
    let h12 = h24 % 12;
    if (h12 === 0) h12 = 12;
    return `Day ${this.day} | ${h12}:${m < 10 ? "0" + m : m} ${ampm}`;
  }
}

export function activityLabel(id: string): string {
  return ACTIVITY_BY_ID.get(id)?.label ?? id;
}

export function activityIsStationary(id: string): boolean {
  return ACTIVITY_BY_ID.get(id)?.stationary ?? false;
}
