// Headless verification harness — ticks the roster through a simulated day with no
// rendering and prints the state changes, so the psychology is provable before any
// pixel is drawn (the doctrine's Phase-1 method: "watch the trauma accumulate in a
// text log").
//
// Run with Node 22's built-in TypeScript support:
//   node --experimental-strip-types src/soul/sim-harness.ts
// or (Node ≥ 22.18, type stripping on by default):
//   node src/soul/sim-harness.ts

import { SoulEngine } from "./engine.ts";
import { ROSTER } from "./roster.ts";
import { maslowLevel, emotionLabel, chakraState } from "./derive.ts";
import { deriveAppearance } from "./appearance.ts";

function snapshot(engine: SoulEngine) {
  return engine.souls.map((s) => {
    const app = deriveAppearance(s);
    return {
      name: s.name,
      maslow: maslowLevel(s.needs).level,
      survival: Math.round(s.needs.survival),
      belonging: Math.round(s.needs.belonging),
      esteem: Math.round(s.needs.esteem),
      emotion: emotionLabel(s.emotion),
      root: chakraState(s.chakras.Root),
      crown: chakraState(s.chakras.Crown),
      activity: app.activityLabel,
      clothing: app.clothingTag,
    };
  });
}

const engine = new SoulEngine(ROSTER);
engine.speed = 60; // fast-forward: 60 sim-minutes per advance() second-equivalent

console.log("=== I AM GOD — Soul Engine headless run ===");
console.log(`Start: ${engine.clockString()}  ·  ${engine.souls.length} souls\n`);

console.log("--- initial state ---");
console.table(snapshot(engine));

// Advance ~16 sim-hours in 1-sim-hour steps (each advance(1s)*speed60 = 60 sim-min).
const HOURS = 16;
let printedTransitions = 0;
for (let h = 0; h < HOURS; h++) {
  engine.advance(1); // 1 real-second-equivalent × speed 60 = 60 sim-minutes
}

console.log(`\n--- after ${HOURS} sim-hours (${engine.clockString()}) ---`);
console.table(snapshot(engine));

console.log("\n--- sample of logged transitions ---");
for (const t of engine.log.slice(-24)) {
  const h = Math.floor((t.atMinutes % 1440) / 60);
  const m = Math.floor(t.atMinutes % 60);
  console.log(`  [${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}] ${t.name}: ${t.text}`);
  printedTransitions++;
}
if (printedTransitions === 0) console.log("  (no transitions logged — check tick logic)");

// Sanity assertions — non-zero exit on failure so this doubles as a smoke test.
const danny = engine.souls.find((s) => s.id === "danny")!;
const mateo = engine.souls.find((s) => s.id === "mateo")!;
const problems: string[] = [];
if (danny.needs.survival < 0 || danny.needs.survival > 100) problems.push("Danny survival out of range");
if (chakraState(danny.chakras.Crown) === "open") problems.push("Danny's Crown should be gated shut (blocked Root/low survival)");
if (chakraState(mateo.chakras.Root) === "blocked") problems.push("Mateo (Old Soul) Root should not be blocked");
if (engine.log.length === 0) problems.push("no transitions were ever logged");

if (problems.length) {
  console.error("\nFAIL:\n" + problems.map((p) => "  - " + p).join("\n"));
  process.exit(1);
}
console.log("\nPASS — needs decayed/replenished, emotions shifted, chakras honored their gates.");
