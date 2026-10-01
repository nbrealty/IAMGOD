import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import App from "./App.tsx";
import "./index.css";

// Keep the installed PWA on the LATEST build. With registerType:'autoUpdate' a new service worker
// takes over (skipWaiting/clientsClaim) the moment it's ready and reloads the page — so a pushed
// fix reaches the phone on the next open instead of a build later. Also poll for updates every
// 30s while the app is open, so a long-lived session picks up new builds without a manual refresh.
registerSW({
  immediate: true,
  onRegisteredSW(_swUrl, reg) {
    if (reg) setInterval(() => reg.update(), 30_000);
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
