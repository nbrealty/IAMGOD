import { chromium } from "/opt/node22/lib/node_modules/playwright/index.mjs";
import fs from "fs";
const SRC = "/home/user/IAMGOD/public/cac/base/";
const OUT = "/home/user/IAMGOD/public/assets/characters/base/";
const dURL = (f) => `data:image/jpeg;base64,` + fs.readFileSync(SRC + f).toString("base64");
const TARGET = { feetY: 1490, headY: 62, cx: 512, W: 1024, H: 1536 };

const browser = await chromium.launch();
const page = await browser.newPage();

const r = await page.evaluate(async ({ backURL, frontURL, TARGET }) => {
  const load = async (url) => { const img = new Image(); img.src = url; await img.decode(); const W = img.naturalWidth, H = img.naturalHeight; const cv = new OffscreenCanvas(W, H); const ctx = cv.getContext("2d"); ctx.drawImage(img, 0, 0); return { cv, ctx, id: ctx.getImageData(0, 0, W, H), W, H }; };
  const keyDespill = (d, W, H) => {
    const keys = []; for (const [x, y] of [[2, 2], [W - 3, 2], [2, H - 3], [W - 3, H - 3], [(W / 2) | 0, 2]]) { const i = (y * W + x) * 4; keys.push([d[i], d[i + 1], d[i + 2]]); }
    const tol = 62; const isKey = (i) => keys.some(k => Math.abs(d[i] - k[0]) <= tol && Math.abs(d[i + 1] - k[1]) <= tol && Math.abs(d[i + 2] - k[2]) <= tol);
    const seen = new Uint8Array(W * H); const st = []; for (let x = 0; x < W; x++) { st.push(x, (H - 1) * W + x); } for (let y = 0; y < H; y++) { st.push(y * W, y * W + W - 1); }
    while (st.length) { const pi = st.pop(); if (seen[pi]) continue; seen[pi] = 1; const i = pi * 4; if (!isKey(i)) continue; d[i + 3] = 0; const x = pi % W, y = (pi / W) | 0; if (x > 0) st.push(pi - 1); if (x < W - 1) st.push(pi + 1); if (y > 0) st.push(pi - W); if (y < H - 1) st.push(pi + W); }
    for (let i = 0; i < d.length; i += 4) { if (!d[i + 3]) continue; if (isKey(i)) { d[i + 3] = 0; continue; } const r = d[i], g = d[i + 1], b = d[i + 2]; if (b > g + 14 && r > g + 6) { d[i + 2] = g; if (r > g + 40) d[i] = g + (r - g) * 0.6; } }
  };
  // skin mask: opaque, warm (R>G>=B), saturated (not the grey band), not dark outline
  const isSkin = (d, i) => { const r = d[i], g = d[i + 1], b = d[i + 2]; if (d[i + 3] < 200) return false; const mx = Math.max(r, g, b), mn = Math.min(r, g, b); return r > g && g >= b - 4 && (r - b) > 14 && (mx - mn) > 16 && r > 55; };
  const meanSkin = (d) => { let R = 0, G = 0, B = 0, n = 0; for (let i = 0; i < d.length; i += 4) if (isSkin(d, i)) { R += d[i]; G += d[i + 1]; B += d[i + 2]; n++; } return n ? [R / n, G / n, B / n] : [0, 0, 0]; };
  const bbox = (d, W, H) => { let a = W, b = H, c = 0, e = 0; for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { if (d[(y * W + x) * 4 + 3] > 16) { if (x < a) a = x; if (x > c) c = x; if (y < b) b = y; if (y > e) e = y; } } return { minx: a, miny: b, maxx: c, maxy: e }; };
  const refit = (cv, bb) => { const out = new OffscreenCanvas(TARGET.W, TARGET.H); const o = out.getContext("2d"); o.imageSmoothingEnabled = true; o.imageSmoothingQuality = "high"; const sw = bb.maxx - bb.minx + 1, sh = bb.maxy - bb.miny + 1; const scale = (TARGET.feetY - TARGET.headY) / sh; const dw = sw * scale, dh = sh * scale; o.drawImage(cv, bb.minx, bb.miny, sw, sh, TARGET.cx - dw / 2, TARGET.feetY - dh, dw, dh); return out; };
  const enc = async (canvas) => { const blob = await canvas.convertToBlob({ type: "image/png" }); const buf = new Uint8Array(await blob.arrayBuffer()); let s = ""; for (let i = 0; i < buf.length; i++) s += String.fromCharCode(buf[i]); return btoa(s); };

  // BACK (authentic medium) → key, get target tone, refit
  const bk = await load(backURL); keyDespill(bk.id.data, bk.W, bk.H); bk.ctx.putImageData(bk.id, 0, 0);
  const target = meanSkin(bk.id.data);
  const backPng = await enc(refit(bk.cv, bbox(bk.id.data, bk.W, bk.H)));

  // FRONT (curvy light) → key, get source tone, recolor skin → target, refit
  const fr = await load(frontURL); keyDespill(fr.id.data, fr.W, fr.H);
  const src = meanSkin(fr.id.data);
  const tf = [target[0] / src[0], target[1] / src[1], target[2] / src[2]];
  const d = fr.id.data;
  for (let i = 0; i < d.length; i += 4) if (isSkin(d, i)) { d[i] = Math.min(255, d[i] * tf[0]); d[i + 1] = Math.min(255, d[i + 1] * tf[1]); d[i + 2] = Math.min(255, d[i + 2] * tf[2]); }
  fr.ctx.putImageData(fr.id, 0, 0);
  const frontPng = await enc(refit(fr.cv, bbox(fr.id.data, fr.W, fr.H)));

  return { backPng, frontPng, target, src, tf };
}, { backURL: dURL("body_curvy_medium_back.jpeg"), frontURL: dURL("body_curvy_light.jpeg"), TARGET });

fs.writeFileSync(OUT + "body_curvy_medium.png", Buffer.from(r.frontPng, "base64"));
fs.writeFileSync(OUT + "body_curvy_medium_back.png", Buffer.from(r.backPng, "base64"));
console.log("target medium tone:", r.target.map(Math.round), "| src light tone:", r.src.map(Math.round), "| factor:", r.tf.map(x => x.toFixed(2)));
console.log("wrote body_curvy_medium.png + _back.png");
await browser.close();
