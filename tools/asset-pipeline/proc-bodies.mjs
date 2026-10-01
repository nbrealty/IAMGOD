import { chromium } from "/opt/node22/lib/node_modules/playwright/index.mjs";
import fs from "fs";
const ROOT = "/home/user/IAMGOD";
const SRC = ROOT + "/public/cac/base/";
const OUT = ROOT + "/public/assets/characters/base/";
fs.mkdirSync(OUT, { recursive: true });
const mime = (f) => /\.jpe?g$/i.test(f) ? "image/jpeg" : "image/png";
const dataURL = (f) => `data:${mime(f)};base64,` + fs.readFileSync(SRC + f).toString("base64");

// Canonical framing: feet near the bottom, small top margin (matches the proper single-file bodies).
const TARGET = { feetY: 1490, headY: 62, cx: 512, W: 1024, H: 1536 };

// build -> { skin -> {front, back} } from the actual files on disk
const singles = [
  ["athletic", ["light", "medium", "deep"]],
  ["average", ["light", "medium", "deep"]],
  ["curvy", ["light", "deep"]], // curvy_medium front missing → omitted
  ["plus", ["light", "medium", "deep"]],
  ["slim", ["light", "medium", "deep"]],
];
const jobs = [];
for (const [build, skins] of singles) for (const skin of skins) {
  const frontPng = `body_${build}_${skin}.png`, frontJpg = `body_${build}_${skin}.jpeg`;
  const front = fs.existsSync(SRC + frontPng) ? frontPng : frontJpg;
  const backJpg = `body_${build}_${skin}_back.jpeg`, backPng = `body_${build}_${skin}_back.png`;
  const back = fs.existsSync(SRC + backJpg) ? backJpg : backPng;
  jobs.push({ src: front, out: `body_${build}_${skin}.png`, mode: "single" });
  jobs.push({ src: back, out: `body_${build}_${skin}_back.png`, mode: "single" });
}
// petite: deep is a proper single; light+medium are front+back COMBO sheets → split
jobs.push({ src: "body_petite_deep.jpeg", out: "body_petite_deep.png", mode: "single" });
jobs.push({ src: "body_petite_deep_back.jpeg", out: "body_petite_deep_back.png", mode: "single" });
jobs.push({ src: "body_petite_light_and_back.jpeg", out: "body_petite_light", mode: "combo" });
jobs.push({ src: "body_petite_medium_and_back.jpeg", out: "body_petite_medium", mode: "combo" });

const browser = await chromium.launch();
const page = await browser.newPage();
const log = [];

for (const j of jobs) {
  if (!fs.existsSync(SRC + j.src)) { log.push(`MISSING ${j.src}`); continue; }
  const url = dataURL(j.src);
  const r = await page.evaluate(async ({ url, mode, TARGET }) => {
    const img = new Image(); img.src = url; await img.decode();
    const W = img.naturalWidth, H = img.naturalHeight;
    const cv = new OffscreenCanvas(W, H); const ctx = cv.getContext("2d");
    ctx.drawImage(img, 0, 0);
    const id = ctx.getImageData(0, 0, W, H); const d = id.data;

    // sample magenta key from corners
    const keys = [];
    for (const [x, y] of [[2, 2], [W - 3, 2], [2, H - 3], [W - 3, H - 3], [(W / 2) | 0, 2]]) { const i = (y * W + x) * 4; keys.push([d[i], d[i + 1], d[i + 2]]); }
    const tol = 62;
    const isKey = (i) => keys.some(k => Math.abs(d[i] - k[0]) <= tol && Math.abs(d[i + 1] - k[1]) <= tol && Math.abs(d[i + 2] - k[2]) <= tol);
    // border-seeded flood fill
    const seen = new Uint8Array(W * H); const st = [];
    for (let x = 0; x < W; x++) { st.push(x, (H - 1) * W + x); }
    for (let y = 0; y < H; y++) { st.push(y * W, y * W + W - 1); }
    while (st.length) { const pi = st.pop(); if (seen[pi]) continue; seen[pi] = 1; const i = pi * 4; if (!isKey(i)) continue; d[i + 3] = 0; const x = pi % W, y = (pi / W) | 0; if (x > 0) st.push(pi - 1); if (x < W - 1) st.push(pi + 1); if (y > 0) st.push(pi - W); if (y < H - 1) st.push(pi + W); }
    // global key-color match (enclosed pockets) + magenta despill on the fringe
    for (let i = 0; i < d.length; i += 4) {
      if (d[i + 3] === 0) continue;
      if (isKey(i)) { d[i + 3] = 0; continue; }
      const r = d[i], g = d[i + 1], b = d[i + 2];
      if (b > g + 14 && r > g + 6) { d[i + 2] = g; if (r > g + 40) d[i] = g + (r - g) * 0.6; } // kill magenta cast
    }
    ctx.putImageData(id, 0, 0);

    // content bbox
    const bbox = () => { let a = W, b = H, c = 0, e = 0; for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { if (d[(y * W + x) * 4 + 3] > 16) { if (x < a) a = x; if (x > c) c = x; if (y < b) b = y; if (y > e) e = y; } } return { minx: a, miny: b, maxx: c, maxy: e }; };

    const draw = (sx, sy, sw, sh) => {
      const out = new OffscreenCanvas(TARGET.W, TARGET.H); const octx = out.getContext("2d");
      octx.imageSmoothingEnabled = true; octx.imageSmoothingQuality = "high";
      const scale = (TARGET.feetY - TARGET.headY) / sh;
      const dw = sw * scale, dh = sh * scale;
      octx.drawImage(cv, sx, sy, sw, sh, TARGET.cx - dw / 2, TARGET.feetY - dh, dw, dh);
      return out;
    };

    const enc = async (canvas) => { const blob = await canvas.convertToBlob({ type: "image/png" }); const buf = new Uint8Array(await blob.arrayBuffer()); let s = ""; for (let i = 0; i < buf.length; i++) s += String.fromCharCode(buf[i]); return btoa(s); };

    if (mode === "single") {
      const bb = bbox();
      const out = draw(bb.minx, bb.miny, bb.maxx - bb.minx + 1, bb.maxy - bb.miny + 1);
      return { one: await enc(out) };
    } else {
      // combo: front = left half, back = right half. Find each half's figure bbox, refit.
      const half = (x0, x1) => { let a = W, b = H, c = 0, e = 0; for (let y = 0; y < H; y++) for (let x = x0; x < x1; x++) { if (d[(y * W + x) * 4 + 3] > 16) { if (x < a) a = x; if (x > c) c = x; if (y < b) b = y; if (y > e) e = y; } } return { minx: a, miny: b, maxx: c, maxy: e }; };
      const mid = (W / 2) | 0;
      const L = half(0, mid), R = half(mid, W);
      const fOut = draw(L.minx, L.miny, L.maxx - L.minx + 1, L.maxy - L.miny + 1);
      const bOut = draw(R.minx, R.miny, R.maxx - R.minx + 1, R.maxy - R.miny + 1);
      return { front: await enc(fOut), back: await enc(bOut) };
    }
  }, { url, mode: j.mode, TARGET });

  if (j.mode === "single") { fs.writeFileSync(OUT + j.out, Buffer.from(r.one, "base64")); log.push(`${j.out}`); }
  else { fs.writeFileSync(OUT + j.out + ".png", Buffer.from(r.front, "base64")); fs.writeFileSync(OUT + j.out + "_back.png", Buffer.from(r.back, "base64")); log.push(`${j.out}.png + _back (split)`); }
}
await browser.close();
console.log(log.join("\n"));
console.log("\ncount:", fs.readdirSync(OUT).filter(f => f.endsWith(".png")).length);
