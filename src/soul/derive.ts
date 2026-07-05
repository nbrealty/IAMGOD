// Pure derivation helpers — turn the numeric Soul state into the human-readable
// values the UI shows. Nothing here mutates a Soul; the engine owns mutation.

import type { Soul, Needs, ChakraState, PrimaryEmotion, EmotionState } from "./types.ts";

export function chakraState(openness: number): ChakraState {
  if (openness < 34) return "blocked";
  if (openness < 67) return "imbalanced";
  return "open";
}

export interface MaslowLevel {
  level: number; // 1–6
  label: string;
}

// The lowest genuinely-unmet need sets the level a person is operating from — you
// can't pursue esteem while survival is critical (the doctrine's core rule).
export function maslowLevel(needs: Needs): MaslowLevel {
  if (needs.survival < 40) return { level: 1, label: "Physiological — fighting to survive" };
  if (needs.safety < 40) return { level: 2, label: "Safety — stable but consumed by fear" };
  if (needs.belonging < 45) return { level: 3, label: "Belonging — starved for connection" };
  if (needs.esteem < 52) return { level: 4, label: "Esteem — hungry for recognition" };
  if (needs.actualization < 62) return { level: 5, label: "Actualization — living from purpose" };
  return { level: 6, label: "Transcendence — beyond self-interest" };
}

const EMOTION_LABELS: Record<PrimaryEmotion, string> = {
  joy: "Joy",
  trust: "Trust",
  fear: "Fear",
  surprise: "Surprise",
  sadness: "Sadness",
  disgust: "Disgust",
  anger: "Anger",
  anticipation: "Anticipation",
  neutral: "Neutral",
};

// A short compound descriptor for flavor, blending the primary with the dominant
// driver — closer to how the doctrine describes "grief wearing a smile".
export function emotionLabel(e: EmotionState): string {
  const base = EMOTION_LABELS[e.primary];
  if (e.intensity >= 75) return `Intense ${base.toLowerCase()}`;
  if (e.intensity >= 45) return base;
  return `Faint ${base.toLowerCase()}`;
}

// Derive the current primary emotion from the need vector, recent deltas, and trait
// modifiers. Priority-ordered: the most acute condition wins.
export function deriveEmotion(soul: Soul, prev: Needs): EmotionState {
  const n = soul.needs;
  const t = soul.traits;
  const rising = n.esteem + n.actualization - (prev.esteem + prev.actualization);

  let primary: PrimaryEmotion = "neutral";
  let intensity = 30;

  if (n.survival < 25) {
    primary = "fear";
    intensity = 70 + (25 - n.survival);
  } else if (n.safety < 28) {
    primary = "fear";
    intensity = 55 + (28 - n.safety) * 0.8;
  } else if (n.belonging < 30 && t.detachment > 45) {
    primary = "sadness"; // loneliness
    intensity = 55 + (30 - n.belonging);
  } else if (n.esteem < 30 && t.antagonism > 55) {
    primary = "anger"; // esteem-starved + hostile
    intensity = 50 + (30 - n.esteem);
  } else if (n.esteem < 32) {
    primary = "sadness";
    intensity = 45 + (32 - n.esteem);
  } else if (rising > 4 && n.actualization > 55) {
    primary = "joy";
    intensity = 55 + rising;
  } else if (rising > 2) {
    primary = "anticipation";
    intensity = 45 + rising * 2;
  } else if (n.actualization > 70 && n.belonging > 60) {
    primary = "trust";
    intensity = 60;
  }

  // Negative affectivity amplifies whatever negative state is present.
  const negative: PrimaryEmotion[] = ["fear", "sadness", "anger", "disgust"];
  if (negative.includes(primary)) {
    intensity += (t.negativeAffectivity - 50) * 0.3;
  }

  return { primary, intensity: clamp(intensity, 0, 100) };
}

export function clamp(v: number, lo = 0, hi = 100): number {
  return Math.max(lo, Math.min(hi, v));
}
