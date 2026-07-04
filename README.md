# I AM GOD

A god-game set in fictionalized 2026 America. You read the three-layer souls of a
living city — psychology, sociology, spirituality — and intervene. The first
vertical slice is **Hollywood & Highland**.

One web codebase, three targets: **Web/phone** (Vercel + PWA), **iOS** (Capacitor),
**Windows & Mac** (Electron).

## Quick start

```bash
npm install
npm run dev        # http://localhost:5173 (+ a Network URL for phone testing)
```

Copy `.env.example` to `.env` and add your Supabase URL + anon key to enable the
database. See **[docs/TESTING.md](docs/TESTING.md)** for the full phone / web /
desktop / iOS testing loops.

## Stack

- **Vite + React + TypeScript** — the app shell and UI (HUD, Soul Profile panel)
- **Canvas renderer** — the dimetric Hollywood & Highland street scene (`src/game/`).
  Phaser + real pixel-art sprites arrive in a later phase; this proves the deploy loop.
- **Supabase** — auth + save storage (`game_saves`, Row Level Security). Client uses
  the anon key only; schema in `supabase/migrations/`.
- **vite-plugin-pwa** — installable, offline-capable web app for phone testing
- **Capacitor** — iOS wrapper · **Electron** — desktop wrapper

## Layout

```
src/
  game/        renderer + scene data (Hollywood & Highland)
  components/  HUD, Soul Profile panel, DB status badge
  lib/         Supabase client
electron/      desktop main + preload
supabase/      SQL migrations
prototypes/    the original Day 1 code-drawn greybox (historical reference)
docs/          TESTING.md
```

## Status

Phase 0 — tech skeleton and test loop. The scene is code-drawn with hand-authored
NPC souls. Next phases add a real utility-AI soul engine, modular chibi sprite
assets, a pre-generated dialogue/prayer content pipeline, and the core
prayer/blessing gameplay loop.
