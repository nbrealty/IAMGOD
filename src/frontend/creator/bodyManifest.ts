// Data-driven body-base manifest — the single source of truth for the creator. Derived from the
// keyed sprites in public/assets/characters/base/ (produced by tools/asset-pipeline/proc-bodies).
// Designed so face/hair/clothing/morph fields can be appended later without rewriting the creator.
export type Skin = "light" | "medium" | "deep";
export type Build = "petite" | "slim" | "average" | "athletic" | "curvy" | "plus";

export const BUILDS: { id: Build; label: string }[] = [
  { id: "petite", label: "Petite" },
  { id: "slim", label: "Slim" },
  { id: "average", label: "Average" },
  { id: "athletic", label: "Athletic" },
  { id: "curvy", label: "Curvy" },
  { id: "plus", label: "Plus" },
];
export const SKINS: { id: Skin; label: string }[] = [
  { id: "light", label: "Light" },
  { id: "medium", label: "Medium" },
  { id: "deep", label: "Deep" },
];

const BASE = "/assets/characters/base";
// Every build×skin with BOTH a keyed front and back on disk. curvy·medium's front was never
// generated (only a back exists), so that one combo is unavailable — never fabricated.
const UNAVAILABLE = new Set<string>(["curvy_medium"]);

export interface BaseOption {
  build: Build; skin: Skin; label: string;
  front: string; back: string; available: boolean;
}

export function baseOption(build: Build, skin: Skin): BaseOption {
  const key = `${build}_${skin}`;
  return {
    build, skin,
    label: `${BUILDS.find((b) => b.id === build)?.label} · ${SKINS.find((s) => s.id === skin)?.label}`,
    front: `${BASE}/body_${key}.png`,
    back: `${BASE}/body_${key}_back.png`,
    available: !UNAVAILABLE.has(key),
  };
}

export const isAvailable = (build: Build, skin: Skin) => !UNAVAILABLE.has(`${build}_${skin}`);

// First available skin for a build (used when switching to a build whose current skin is missing).
export function firstSkinFor(build: Build): Skin {
  return (SKINS.find((s) => isAvailable(build, s.id))?.id ?? "medium") as Skin;
}

// All available (build, skin) pairs — for Randomize.
export function allAvailable(): { build: Build; skin: Skin }[] {
  const out: { build: Build; skin: Skin }[] = [];
  for (const b of BUILDS) for (const s of SKINS) if (isAvailable(b.id, s.id)) out.push({ build: b.id, skin: s.id });
  return out;
}

export const DEFAULT_BUILD: Build = "average";
export const DEFAULT_SKIN: Skin = "medium";
