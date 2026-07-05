import { useEffect, useReducer } from "react";
import type { SoulEngine } from "../soul/engine";
import { NEED_KEYS, CHAKRA_ORDER, type Soul } from "../soul/types";
import { maslowLevel, emotionLabel, chakraState } from "../soul/derive";
import { deriveAppearance } from "../soul/appearance";

interface Props {
  engine: SoulEngine;
  soulId: string | null;
  onClose: () => void;
}

const NEED_LABEL: Record<string, string> = {
  survival: "Survival",
  safety: "Safety",
  belonging: "Belonging",
  esteem: "Esteem",
  actualization: "Actualization",
};

const TRAITS: { key: keyof Soul["traits"]; label: string }[] = [
  { key: "negativeAffectivity", label: "Neg. Affectivity" },
  { key: "detachment", label: "Detachment" },
  { key: "antagonism", label: "Antagonism" },
  { key: "disinhibition", label: "Disinhibition" },
  { key: "psychoticism", label: "Psychoticism" },
];

function Bar({ value, ceiling, kind }: { value: number; ceiling?: number; kind: string }) {
  return (
    <div className="bar-track">
      <div className={`bar-fill ${kind}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      {ceiling !== undefined && ceiling < 100 && (
        <div className="bar-ceiling" style={{ left: `${ceiling}%` }} title={`natural ceiling ${Math.round(ceiling)}`} />
      )}
    </div>
  );
}

export function SoulProfilePanel({ engine, soulId, onClose }: Props) {
  // The engine mutates souls in place; re-render on an interval so the panel shows
  // live values while it's open.
  const [, force] = useReducer((x) => x + 1, 0);
  useEffect(() => {
    if (!soulId) return;
    const id = setInterval(force, 400);
    return () => clearInterval(id);
  }, [soulId]);

  if (!soulId) return null;
  const soul = engine.get(soulId);
  if (!soul) return null;

  const maslow = maslowLevel(soul.needs);
  const app = deriveAppearance(soul);

  return (
    <div
      className="panel-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="panel-card">
        <h2>{soul.name}</h2>
        <p className="panel-occ">
          {soul.occupation} · {soul.archetype} · {soul.age}
        </p>
        {soul.faction && <p className="panel-faction">Affiliated · {soul.faction}</p>}

        <div className="panel-live">
          <span className="chip">Maslow {maslow.level}</span>
          <span className="chip">{emotionLabel(soul.emotion)}</span>
          <span className="chip subtle">{app.activityLabel}</span>
        </div>
        <p className="maslow-label">{maslow.label}</p>

        <div className="section-title">Needs</div>
        {NEED_KEYS.map((k) => (
          <div className="metric" key={k}>
            <span className="metric-label">{NEED_LABEL[k]}</span>
            <Bar value={soul.needs[k]} ceiling={soul.ceilings?.[k]} kind={`need-${k}`} />
            <span className="metric-num">{Math.round(soul.needs[k])}</span>
          </div>
        ))}

        <div className="section-title">
          Emotional intensity <span className="dim">— {Math.round(soul.emotion.intensity)}</span>
        </div>
        <Bar value={soul.emotion.intensity} kind="emotion" />

        <div className="section-title">Maladaptive traits</div>
        <div className="trait-grid">
          {TRAITS.map((t) => (
            <div className="metric small" key={t.key}>
              <span className="metric-label">{t.label}</span>
              <Bar value={soul.traits[t.key]} kind="trait" />
            </div>
          ))}
        </div>

        <div className="stat-row">
          <span>ACE / Resilience / Kohlberg</span>
          <span>
            {soul.aceScore} · {Math.round(soul.resilience)} · Stage {soul.kohlberg}
          </span>
        </div>
        <div className="stat-row">
          <span>Soul age / Initiation</span>
          <span>
            {soul.soulAge} · Level {soul.initiationLevel}
          </span>
        </div>

        <div className="panel-narrative">{soul.narrative}</div>

        <div className="section-title">Chakras <span className="dim">(bottom → top)</span></div>
        <div className="chakra-row">
          {CHAKRA_ORDER.map((name) => (
            <div className="chakra" key={name}>
              <div className={`chakra-dot ${chakraState(soul.chakras[name])}`} />
              <span>{name}</span>
            </div>
          ))}
        </div>

        <div className="aspiration">
          <div className="asp-block">
            <span className="asp-label">Conscious aspiration</span>
            <span className="asp-text">{soul.consciousAspiration}</span>
          </div>
          <div className="asp-block">
            <span className="asp-label soul">Soul purpose <span className="dim">(only you can see)</span></span>
            <span className="asp-text soul">{soul.soulPurpose}</span>
          </div>
        </div>

        <div className="appearance-tags">
          <span className="tag">{app.clothingTag}</span>
          <span className="tag">{app.groomingTag}</span>
        </div>

        <button className="panel-close" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
