// Electron main process — wraps the built web app (dist/) into a desktop app
// for Windows and macOS.
//
//   npm run electron:dev     # live dev: runs Vite + Electron against localhost
//   npm run electron:build   # packages a distributable (.exe / .dmg) via electron-builder
//
// In dev it loads the Vite dev server (ELECTRON_START_URL); in production it
// loads the bundled dist/index.html.

const { app, BrowserWindow } = require("electron");
const path = require("node:path");

const startUrl = process.env.ELECTRON_START_URL;

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: "#0c0e14",
    title: "I AM GOD",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (startUrl) {
    win.loadURL(startUrl);
  } else {
    win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
