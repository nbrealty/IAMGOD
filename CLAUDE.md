# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**I AM GOD** — a god-game set in fictionalized 2026 America. The player reads the three-layer souls of a living city (psychology, sociology, spirituality) and intervenes. The first vertical slice is **Hollywood & Highland**. Currently in **Phase 0**: a tech skeleton proving the build/deploy/test loop, with a hand-authored, code-drawn scene (no image assets or Phaser yet).

One web codebase (`src/`) ships to three targets: Web/phone (Vercel + PWA), iOS (Capacitor), Windows/Mac (Electron).

## Commands

```bash
npm install           # first time; Electron fetches its binary here (skipped in cloud/CI envs)
npm run dev            # Vite dev server at http://localhost:5173 (+ a Network URL for phone testing on same Wi-Fi)
npm run build          # typecheck (tsc -b) + production bundle into dist/
npm run preview        # serve the production build locally
npm run lint           # actually just `tsc -b --noEmit` — there is no ESLint config in this repo
```

There is no test framework configured yet (no Vitest/Jest, no `*.test.*` files) — don't assume one exists.

Native/desktop builds (require the target OS/tooling; see `docs/TESTING.md` for the full flow):

```bash
npm run cap:ios         # build, cap sync, open Xcode (macOS + Xcode required)
npm run electron:dev    # live desktop dev: Vite + Electron against localhost
npm run electron:build  # package .exe (NSIS)/.dmg into release/ via electron-builder
```

The primary day-to-day test loop is **not** any native build — it's `git push` → Vercel auto-deploy → refresh Safari on a phone (or Add to Home Screen for PWA install). Do a real Capacitor build check only occasionally to catch Safari-specific issues.

## Architecture

### Rendering: hand-drawn canvas, not Phaser (yet)

`src/game/` is the whole "engine" for now:
- `sceneData.ts` — all scene constants (canvas dimensions, road/sidewalk/building baselines), the `NPCS` roster (hand-authored `SoulProfile` objects), and `NORTH_BUILDINGS`/`SOUTH_BUILDINGS` footprints. This is the single source of truth for where everything sits in the 1600×900 virtual coordinate space.
- `renderer.ts` — `HollywoodRenderer` is a plain class (not a React component) that owns a `requestAnimationFrame` loop, mutates NPC/car runtime positions each frame, and draws directly to a `CanvasRenderingContext2D`. It also does hit-testing (`hitTest(vx, vy)`) against NPC positions for tap/click selection.
- `HollywoodScene.tsx` — the React wrapper: creates one `HollywoodRenderer` per mount via `useRef`, starts/stops it in a `useEffect`, and translates canvas click coordinates into the renderer's virtual coordinate space (`SCENE_W`/`SCENE_H`) before calling `hitTest`.

This split (data / imperative renderer / thin React shell) is deliberate — the doctrine is that Phaser and real pixel-art sprite assets replace `renderer.ts`'s drawing calls in a later phase, but `sceneData.ts`'s shape is meant to be the seam the future NPC engine plugs into. When extending NPCs or buildings, add to `sceneData.ts`, not by hardcoding into the renderer.

### Soul model

Each NPC (`SoulProfile` in `sceneData.ts`) currently carries: Maslow hierarchy position, an emotional state, a free-text narrative, and a 7-chakra state map (`ChakraState`: `blocked` | `imbalanced` | `open` per `CHAKRA_ORDER`). This is stub/hand-authored data for Phase 0. `SoulProfilePanel.tsx` is the read-only UI for it, opened by tapping an NPC in the scene.

### App shell

`App.tsx` composes `Hud` (top status bar: in-game clock, PRESENCE/TRUST gauges, Supabase status badge) + `HollywoodScene` (the canvas) — that's the entire UI tree today. `Hud.tsx` runs its own in-game clock via `setInterval`, independent of the renderer's animation loop.

### Supabase (save data)

`src/lib/supabase.ts` creates the client only if `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` are both set (`isSupabaseConfigured`); otherwise `supabase` is `null` and the app runs with no persistence. **Only the anon key ever belongs in client code** — Row Level Security (see `supabase/migrations/0001_init.sql`) is what makes that safe; the service_role key must never appear in the repo or client bundle. The `game_saves` table is keyed by `(user_id, slot)` with RLS policies scoped to `auth.uid()`. `checkSupabaseConnection()` does a lightweight PostgREST reachability check consumed by `SupabaseBadge.tsx`'s HUD status dot.

### Multi-target shell

- `vite.config.ts` uses `base: "./"` (relative paths) specifically so the same `dist/` build works under Capacitor/Electron's `file://` loading and a normal web root.
- `capacitor.config.ts` wraps `dist/` for iOS; the generated `/ios` project is gitignored — regenerate with `cap add ios` rather than committing it.
- `electron/main.cjs` loads `ELECTRON_START_URL` in dev or `dist/index.html` in production, with `contextIsolation: true` / `nodeIntegration: false`; `electron/preload.cjs` is the `contextBridge` surface for exposing native APIs later — add to it rather than enabling `nodeIntegration`.

## Environment

Copy `.env.example` to `.env` (gitignored) with `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. Same two variables go in Vercel under Project → Settings → Environment Variables (must be `VITE_`-prefixed to reach the browser bundle).
