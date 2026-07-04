# Testing I AM GOD — Phone, Web, Desktop

One web codebase (`src/`) is built once and shipped three ways:

| Target | Wrapper | Use for |
| --- | --- | --- |
| **Web / phone** | Vercel + PWA | Day-to-day testing, fast iteration, "Add to Home Screen" on iPhone |
| **iOS App Store** | Capacitor | The real installable iOS app / TestFlight |
| **Windows & Mac** | Electron | Desktop `.exe` / `.dmg` |

**Your primary loop is Vercel + your phone.** Everything else is for producing the actual store/desktop builds when you're ready.

---

## The fast phone loop (do this first, every day)

Because the game *is* a website, the fastest way to test on your iPhone is: push to git → Vercel auto-deploys → refresh Safari. No Xcode, no cable, no rebuild.

### One-time setup

1. **Import the repo into Vercel.** vercel.com → Add New → Project → import `nbrealty/IAMGOD`. Vercel auto-detects Vite (there's a `vercel.json` that pins it). It builds `npm run build` and serves `dist/`.
2. **Add your Supabase keys as env vars.** In the Vercel project → Settings → Environment Variables, add:
   - `VITE_SUPABASE_URL` — your Supabase Project URL
   - `VITE_SUPABASE_ANON_KEY` — the **anon / public** key (never the service_role key)

   Find both in Supabase → Project Settings → API. Redeploy after adding them.
3. **Deploy.** Every push to the branch triggers a deploy; you get a URL like `https://iamgod.vercel.app`.

### The loop

```
edit code  →  git push  →  Vercel builds (~30s)  →  refresh Safari on your phone
```

### Install it to your home screen (feels like a real app)

Open the Vercel URL in **Safari** on your iPhone → Share → **Add to Home Screen**. It launches full-screen with the star icon, no browser chrome, and works offline (the PWA service worker caches it). This is the closest thing to the App Store build without any native tooling — use it for all day-to-day testing.

> Caveat: a Safari PWA runs in Safari's web view, which is ~99% identical to Capacitor's. Do your daily testing here; do a real Capacitor build check (below) at the end of each phase to catch anything Safari-specific before it piles up.

---

## Local development

```bash
npm install          # first time (downloads deps; Electron fetches its binary here)
npm run dev          # Vite dev server at http://localhost:5173
```

`npm run dev` prints a **Network** URL (e.g. `http://192.168.x.x:5173`). If your computer and phone are on the same Wi-Fi, open that URL in your phone's browser to test locally without deploying — even faster than Vercel for rapid tweaks.

For Supabase locally: copy `.env.example` to `.env` and paste your two values in. `.env` is gitignored.

```bash
npm run build        # production build (typecheck + bundle) into dist/
npm run preview      # serve the production build locally to sanity-check it
```

---

## Supabase

- The app reads `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` from env vars (local `.env`, or Vercel env vars).
- The **DB status badge** in the top-right of the HUD is your live connection test: it shows `not configured` (no keys), `connected` (reachable + key accepted), or `error`.
- Apply the starter schema: Supabase dashboard → SQL Editor → paste `supabase/migrations/0001_init.sql` → Run. This creates a `game_saves` table with Row Level Security so each player can only read/write their own saves. (Or, with the Supabase CLI: `supabase db push`.)
- **Only the anon key ever goes in the app.** It's safe in the browser because RLS enforces access. The service_role key must never appear in client code or the repo.

---

## iOS build (App Store / TestFlight) — run on a Mac

Requires macOS + Xcode + an Apple Developer account.

```bash
npm run build
npx cap add ios          # one-time: generates the /ios native project
npm run cap:ios          # syncs dist/ into iOS and opens Xcode
```

Then in Xcode: set your signing team, pick a device/simulator, and Run — or Archive → distribute to TestFlight. The `/ios` folder is gitignored; regenerate it with `cap add ios` rather than committing it.

---

## Desktop build (Windows & Mac) — run on the target OS

Electron downloads its binary on first `npm install` on your machine (it's skipped in the cloud dev environment, which is why the committed lockfile still lists it).

```bash
npm run electron:dev     # live desktop dev: Vite + Electron against localhost
npm run electron:build   # packages a distributable into release/
```

`electron:build` produces a `.exe` (NSIS installer) on Windows and a `.dmg` on macOS, per `electron-builder.yml`. Build on the OS you're targeting (or set up CI later for cross-builds). Add a `build/icon.ico` (Windows) and `build/icon.icns` (Mac) when you have final art — placeholders are noted in the config.

---

## Quick reference

| I want to… | Command / action |
| --- | --- |
| Test on my phone, fastest | `npm run dev`, open the Network URL on your phone (same Wi-Fi) |
| Test on my phone, from anywhere | `git push` → open the Vercel URL in Safari |
| Install to iPhone home screen | Vercel URL in Safari → Share → Add to Home Screen |
| Check the production bundle | `npm run build && npm run preview` |
| Build the iOS app | `npm run cap:ios` (on a Mac) |
| Build the Windows/Mac app | `npm run electron:build` (on that OS) |
| Verify DB connection | Look at the DB badge in the HUD |
