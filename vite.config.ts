import { execSync } from "node:child_process";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// A visible build stamp so we can tell exactly which build a device is running (git short sha +
// build time). Shown in a corner of the UI; if the phone shows an old stamp, it's a stale cache.
let buildId = "dev";
try {
  buildId = execSync("git rev-parse --short HEAD").toString().trim();
} catch {
  /* not a git checkout — leave 'dev' */
}
const BUILD_STAMP = `${buildId}`;

// https://vite.dev/config/
export default defineConfig({
  define: { __BUILD_ID__: JSON.stringify(BUILD_STAMP) },
  // Relative base so the same build works when wrapped by Capacitor (file://) and
  // Electron (file://) as well as served from a web root (Vercel).
  base: "./",
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      // Activate a new service worker immediately and drop stale precaches, so an update never
      // gets stuck behind an old cached build.
      workbox: {
        clientsClaim: true,
        skipWaiting: true,
        cleanupOutdatedCaches: true,
      },
      includeAssets: ["favicon.svg", "apple-touch-icon.png"],
      manifest: {
        name: "I AM GOD",
        short_name: "I AM GOD",
        description:
          "A god-game set in fictionalized 2026 America. Read the souls of the city and intervene.",
        theme_color: "#0c0e14",
        background_color: "#0c0e14",
        display: "standalone",
        orientation: "any",
        icons: [
          { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
          { src: "pwa-512x512.png", sizes: "512x512", type: "image/png" },
          {
            src: "pwa-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
    }),
  ],
  server: {
    host: true,
    port: 5173,
  },
});
