import { chromium } from "/opt/node22/lib/node_modules/playwright/index.mjs";
import fs from "fs";
const ROOT = "/home/user/IAMGOD";
const SRC = ROOT + "/public/cac/pages/";
const OUT = ROOT + "/public/assets/";
const mime = (f) => /\.jpe?g$/i.test(f) ? "image/jpeg" : "image/png";
const dataURL = (f) => `data:${mime(f)};base64,` + fs.readFileSync(SRC + f).toString("base64");

const jobs = [
  ["title-bg-desktop-src.png",       "title/title-bg-desktop.webp",             "webp", { q: 0.9 }],
  ["photo-3.png",                    "title/title-bg-mobile.webp",              "webp", { q: 0.9 }],
  ["mode-select-bg-desktop-src.png", "mode-select/mode-select-bg-desktop.webp", "webp", { q: 0.9 }],
  ["mode-sandbox-card-src.jpeg",     "mode-select/mode-sandbox-card.webp",      "webp", { q: 0.92 }],
  ["mode-story-card-src.jpeg",       "mode-select/mode-story-card.webp",        "webp", { q: 0.92 }],
  ["IMG_E3A69570-935F-4B6A-B7DC-2CED2FDE00C6.jpeg", "creator/creator-stage-desktop.webp", "webp", { q: 0.9 }],
  ["creator-bg-mobile-src.jpeg",     "creator/creator-bg-mobile.webp",          "webp", { q: 0.9 }],
  ["photo-3.png",                    "mode-select/mode-select-bg-mobile.webp",  "tint", { q: 0.9, mul: [0.62, 0.5, 0.66], add: [12, 0, 18] }],

  ["IMG_6572.png", "title/title-gold-dust-desktop.png",   "copy", {}],
  ["IMG_6573.png", "title/title-soul-sparks-desktop.png", "copy", {}],
  ["IMG_6574.png", "title/title-vignette-desktop.png",    "copy", {}],
  ["spinner.png",  "ui/brand-mark.png",                   "cropAlpha", { pad: 8 }],

  ["photo.png",                  "title/iamgod-logo-wide.png",        "floodKey", { tol: 46, crop: true }],
  ["photo-7.png",                "ui/button-frame.png",               "floodKey", { tol: 46, crop: true }],
  ["road-glow-desktop-src.png",  "title/title-road-glow-desktop.png", "floodKey", { tol: 40, crop: false }],
  ["IMG_36598A88-884C-4478-A759-438831BA4DCD.jpeg", "title/title-god-rays-desktop.png", "floodKey", { tol: 42, crop: false, glowClean: true }],
  ["photo-4.png",                "title/title-god-rays-mobile.png",   "floodKey", { tol: 52, crop: false, glowClean: true }],
  ["photo-6.png",                "title/title-haze-desktop.png",      "floodKey", { tol: 52, crop: false, glowClean: true }],
];

const browser = await chromium.launch();
const page = await browser.newPage();
const results = [];

for (const [srcF, outRel, op, p] of jobs) {
  if (!fs.existsSync(SRC + srcF)) { console.log("MISSING:", srcF); continue; }
  const url = dataURL(srcF);
  const type = outRel.endsWith(".webp") ? "image/webp" : "image/png";
  const r = await page.evaluate(async ({ url, op, p, type }) => {
    const img = new Image(); img.src = url; await img.decode();
    const W = img.naturalWidth, H = img.naturalHeight;
    const cv = new OffscreenCanvas(W, H); const ctx = cv.getContext("2d");
    ctx.drawImage(img, 0, 0);
    const id = ctx.getImageData(0, 0, W, H); const d = id.data;

    if (op === "floodKey") {
      const keys = [];
      for (const [x,y] of [[0,0],[W-1,0],[0,H-1],[W-1,H-1],[(W/2)|0,0],[0,(H/2)|0]]){ const i=(y*W+x)*4; keys.push([d[i],d[i+1],d[i+2]]); }
      const tol = p.tol;
      const isBg = (i) => keys.some(k => Math.abs(d[i]-k[0])<=tol && Math.abs(d[i+1]-k[1])<=tol && Math.abs(d[i+2]-k[2])<=tol);
      const seen = new Uint8Array(W*H); const stack = [];
      for (let x=0;x<W;x++){ stack.push(x, (H-1)*W+x); }
      for (let y=0;y<H;y++){ stack.push(y*W, y*W+W-1); }
      while (stack.length){ const pxi = stack.pop(); if (seen[pxi]) continue; seen[pxi]=1;
        const i=pxi*4; if(!isBg(i)) continue; d[i+3]=0;
        const x=pxi%W, y=(pxi/W)|0;
        if(x>0)stack.push(pxi-1); if(x<W-1)stack.push(pxi+1); if(y>0)stack.push(pxi-W); if(y<H-1)stack.push(pxi+W);
      }
      if (p.glowClean){ // fade gray specks: alpha follows luminance so only bright glow stays opaque
        for(let i=0;i<d.length;i+=4){ if(d[i+3]>0){ const luma=0.299*d[i]+0.587*d[i+1]+0.114*d[i+2]; const f=Math.max(0,Math.min(1,(luma-40)/150)); let a=d[i+3]*f; d[i+3]=a<10?0:a; } }
      }
    } else if (op === "glowKey") {
      for (let i=0;i<d.length;i+=4){
        const r=d[i],g=d[i+1],b=d[i+2];
        const M=Math.max(r,g,b), m=Math.min(r,g,b), sat=M-m;
        let a = Math.max(sat*1.6, (M-215)*3) - Math.max(0,(m-235))*4;
        d[i+3]=Math.max(0,Math.min(255,a));
      }
    } else if (op === "tint") {
      for (let i=0;i<d.length;i+=4){ d[i]=Math.min(255,d[i]*p.mul[0]+p.add[0]); d[i+1]=Math.min(255,d[i+1]*p.mul[1]+p.add[1]); d[i+2]=Math.min(255,d[i+2]*p.mul[2]+p.add[2]); }
    }
    ctx.putImageData(id, 0, 0);

    let ox=0, oy=0, ow=W, oh=H;
    if (op==="cropAlpha" || (op==="floodKey" && p.crop)){
      let minx=W,miny=H,maxx=0,maxy=0;
      for(let y=0;y<H;y++)for(let x=0;x<W;x++){ if(d[(y*W+x)*4+3]>8){ if(x<minx)minx=x;if(x>maxx)maxx=x;if(y<miny)miny=y;if(y>maxy)maxy=y; } }
      const pad=p.pad||0;
      minx=Math.max(0,minx-pad);miny=Math.max(0,miny-pad);maxx=Math.min(W-1,maxx+pad);maxy=Math.min(H-1,maxy+pad);
      ox=minx;oy=miny;ow=maxx-minx+1;oh=maxy-miny+1;
    }
    const out = new OffscreenCanvas(ow, oh); const octx = out.getContext("2d");
    octx.drawImage(cv, ox, oy, ow, oh, 0, 0, ow, oh);
    const blob = await out.convertToBlob({ type, quality: p.q ?? 0.9 });
    const buf = new Uint8Array(await blob.arrayBuffer());
    let bin=""; for(let i=0;i<buf.length;i++) bin+=String.fromCharCode(buf[i]);
    return { b64: btoa(bin), w: ow, h: oh };
  }, { url, op, p, type });
  fs.writeFileSync(OUT + outRel, Buffer.from(r.b64, "base64"));
  results.push(`${outRel}  ${r.w}x${r.h}  ${(fs.statSync(OUT+outRel).size/1024|0)}KB`);
}
await browser.close();
console.log(results.join("\n"));
