import { OUTFITS, type Outfit } from "./outfits";

// Every character and NPC carries a fixed-size inventory. For now it holds outfits (the wardrobe);
// later it can hold other item kinds. 20 slots — a clean 4×5 grid — most of them empty until the
// player earns/receives more. "For now" = a hard 20; a future upgrade can grow it.
export const INVENTORY_SLOTS = 20;

// Every soul owns at least its default look (slot 0, stem = soul id). Souls with wardrobe art get
// their extra outfits after it. Souls with no art still get a default entry so their inventory is
// real (the thumbnail just falls back to a placeholder).
export function ownedOutfits(soulId: string): Outfit[] {
  const list = OUTFITS[soulId];
  if (list && list.length) return list;
  return [{ id: "everyday", label: "Everyday", stem: soulId }];
}

// The 20 slots for a soul: owned outfits first, then empty (null) padding.
export function inventorySlots(soulId: string): (Outfit | null)[] {
  const owned = ownedOutfits(soulId);
  const slots: (Outfit | null)[] = [];
  for (let i = 0; i < INVENTORY_SLOTS; i++) slots.push(owned[i] ?? null);
  return slots;
}

// The stem a soul currently wears — an explicit equip override, else its default look.
export function equippedStem(soulId: string, overrides: Record<string, string>): string {
  return overrides[soulId] ?? soulId;
}
