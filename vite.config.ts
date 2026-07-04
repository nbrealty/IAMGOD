import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// https://vite.dev/config/
export default defineConfig({
  // Relative base so the same build works when wrapped by Capacitor (file://) and
  // Electron (file://) as well as served from a web root (Vercel).
  base: "./",
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
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
