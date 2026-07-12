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
    { id: "floral", label: "Floral", stem: "roxy_valente_floral" },
  ],
  lori: [
    { id: "everyday", label: "Everyday", stem: "lori" },
    { id: "gingham", label: "Gingham", stem: "lori__gingham-going-out" },
    { id: "shark", label: "Shark Shorts", stem: "lori__shark-shorts" },
  ],
  // Sorriso (soul id "nathaniel"). Brasil jersey is his default look; the rest are streetwear
  // fits (fronts only for now — no `_back` art yet, so the renderer shows the front when he walks
  // away, which is the documented fallback until back art lands).
  nathaniel: [
    { id: "brasil", label: "Brasil", stem: "nathaniel" },
    { id: "dodgers-tee", label: "Dodgers Tee", stem: "nathaniel_dodgers-tee" },
    { id: "tank", label: "White Tank", stem: "nathaniel_tank" },
    { id: "la-jersey", label: "LA Jersey", stem: "nathaniel_la-jersey" },
    { id: "palm-tee", label: "Palm Tee", stem: "nathaniel_palm-tee" },
    { id: "camp", label: "Camp Shirt", stem: "nathaniel_camp" },
  ],
  // Lua (Rafaela "Lua" Moreira) — Eclipse DJ/owner. Black bomber "club owner" fit is her default.
  lua: [{ id: "eclipse", label: "Eclipse", stem: "lua" }],
  // Beatriz "Bibi" Moreira — Lua's sister, "Boss Energy" fashion CEO. Black/gold baroque trench default.
  bibi: [{ id: "boss-energy", label: "Boss Energy", stem: "bibi" }],
  // Vee Knox. "Rock Forever" street-glam look is her default.
  vee_knox: [
    { id: "rock", label: "Rock", stem: "vee_knox" },
    { id: "bodysuit", label: "Bodysuit", stem: "vee_knox_bodysuit" },
    { id: "casual", label: "Casual", stem: "vee_knox_casual" },
  ],
};

export function outfitsFor(soulId: string | null): Outfit[] {
  return soulId ? (OUTFITS[soulId] ?? []) : [];
}
