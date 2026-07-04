// Electron preload — runs in an isolated context bridging the renderer and main.
// Intentionally minimal for now; expose native capabilities here later (e.g. a
// safe save-file API) via contextBridge rather than enabling nodeIntegration.

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("iamgod", {
  platform: "electron",
  version: process.versions.electron,
});
