// The Phase-1 character draft: mode + basic body-base selection + name. Persisted to
// localStorage so it survives a reload and the mode↔creator hop. Versioned for future migration.
export type Mode = "sandbox" | "story";

export interface CharacterDraft {
  v: 1;
  name: string;
  mode: Mode | null;
  build: string; // body build id (see creator/bodyManifest)
  skin: string; // skin tone id
}

const KEY = "iamgod.phase1.draft.v1";

export const DEFAULT_DRAFT: CharacterDraft = { v: 1, name: "", mode: null, build: "average", skin: "medium" };

export function loadDraft(): CharacterDraft | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const d = JSON.parse(raw);
    if (d && d.v === 1) return d as CharacterDraft;
  } catch { /* ignore */ }
  return null;
}

export function saveDraft(d: CharacterDraft): void {
  try { localStorage.setItem(KEY, JSON.stringify(d)); } catch { /* ignore */ }
}

// A valid saved character (enables "Continue"): a real, complete draft — never faked.
export function hasValidSave(): boolean {
  const d = loadDraft();
  return !!(d && d.name.trim() && d.mode && d.build && d.skin);
}
