import { useState } from "react";
import type { Soul } from "../soul/types";
import { formatMoney } from "../soul/derive";

// The front-desk conversation at Águas Douradas: greet Yara, ask how she's doing (how much she
// opens up scales with the player's initiation/progress), or request a búzios reading. Choosing the
// reading quotes a price and asks the player to accept + pay; on accept the parent deducts the fee,
// kicks off her "walk to the back" beat, and the reading proper happens in the back room.

// How open Yara is about herself, tiered by the player's initiation level (readings raise it).
const LIFE_TIERS: string[] = [
  // 0 — guarded, professional
  "Kind of you to ask, love. I keep the shop, I keep the faith — Oxum sees to the rest. But you didn't come all this way to fret over me.",
  // 1–2 — opening up
  "Bahia raised me — Salvador, right by the sea. My avó threw búzios before me, and hers before her. I carried it here so the tradition keeps breathing, even on this boulevard.",
  // 3–4 — warm
  "Some days Hollywood forgets there's anything sacred left under all that neon. But the lost still find my door. That's the work — I hold it open, and Oxum does the rest.",
  // 5+ — intimate
  "You've sat with me enough times now — so I'll tell you true. I left Bahia running from something I couldn't name. These shells are how I found the road back to myself. Stay on the path and they'll do the same for you.",
];

function lifeTier(level: number): string {
  const i = level <= 0 ? 0 : level <= 2 ? 1 : level <= 4 ? 2 : 3;
  return LIFE_TIERS[i];
}

export function YaraFrontDesk({
  soul, price, onAccept, onClose,
}: {
  soul: Soul;
  price: number;
  onAccept: () => void;
  onClose: () => void;
}) {
  const [step, setStep] = useState<"root" | "life" | "price">("root");
  const money = soul.money ?? 0;
  const canAfford = money >= price;
  const first = (soul.name.split(/\s+/)[0]) || "traveler";

  return (
    <div className="panel-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="panel-card yara-desk">
        <h2>Yara <span className="dim">· Águas Douradas</span></h2>

        {step === "root" && (
          <>
            <p className="yara-line">“Bem-vindo, {first}. The waters are calm today — what do you seek?”</p>
            <div className="yara-choices">
              <button onClick={() => setStep("life")}>How are you, Yara?</button>
              <button className="primary" onClick={() => setStep("price")}>🐚 Consult the búzios</button>
              <button className="ghost" onClick={onClose}>Just looking</button>
            </div>
          </>
        )}

        {step === "life" && (
          <>
            <p className="yara-line">“{lifeTier(soul.initiationLevel)}”</p>
            <div className="yara-choices">
              <button onClick={() => setStep("root")}>← Back</button>
            </div>
          </>
        )}

        {step === "price" && (
          <>
            <p className="yara-line">
              “To read the búzios is <b>{formatMoney(price)}</b> — the shells, the cloth, and my hands
              between you and the orixás. When you're ready, I'll go and prepare the table.”
            </p>
            <p className="yara-wallet">Your wallet: {formatMoney(money)}</p>
            <div className="yara-choices">
              {canAfford ? (
                <button className="primary" onClick={onAccept}>Accept · pay {formatMoney(price)}</button>
              ) : (
                <button className="disabled" disabled>Not enough — come back with {formatMoney(price)}</button>
              )}
              <button className="ghost" onClick={() => setStep("root")}>Not now</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
