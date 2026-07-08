// Outfit catalog — the first step of an inventory. Each playable soul can own several outfits;
// switching one swaps the character's sprite stem live (front + its `_back`). A soul absent from
// this map (or with a single entry) just wears its default look. Each stem maps to
// `/spirits/<stem>.png` for the front and `/spirits/<stem>_back.png` for the away-facing view; if
// an outfit has no `_back` art the renderer falls back to its front sprite when facing away.
export interface Outfit {
  id: string; // stable key
  label: string; // UI label
  stem: string; // sprite stem in public/spirits (front); back is `${stem}_back`
}

// The first entry is the default look (its stem equals the soul id, matching the base sprite).
export const OUTFITS: Record<string, Outfit[]> = {
  roxy_valente: [
    { id: "everyday", label: "Everyday", stem: "roxy_valente" },
    { id: "beach", label: "Beach", stem: "roxy_valente_beach" },
  ],
  lori: [
    { id: "everyday", label: "Everyday", stem: "lori" },
    { id: "gingham", label: "Gingham", stem: "lori__gingham-going-out" },
    { id: "shark", label: "Shark Shorts", stem: "lori__shark-shorts" },
  ],
};

export function outfitsFor(soulId: string | null): Outfit[] {
  return soulId ? (OUTFITS[soulId] ?? []) : [];
}
