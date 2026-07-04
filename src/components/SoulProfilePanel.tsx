import { CHAKRA_ORDER, type SoulProfile } from "../game/sceneData";

interface Props {
  soul: SoulProfile | null;
  onClose: () => void;
}

export function SoulProfilePanel({ soul, onClose }: Props) {
  if (!soul) return null;

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
          {soul.occupation} · {soul.archetype}
        </p>

        <div className="stat-row">
          <span>Maslow Position</span>
          <span>{soul.maslow}</span>
        </div>
        <div className="stat-row">
          <span>Emotional State</span>
          <span>{soul.emotion}</span>
        </div>
        <div className="stat-row">
          <span>Age</span>
          <span>{soul.age}</span>
        </div>

        <div className="panel-narrative">{soul.narrative}</div>

        <div className="chakra-row">
          {CHAKRA_ORDER.map((name) => (
            <div className="chakra" key={name}>
              <div className={`chakra-dot ${soul.chakras[name]}`} />
              <span>{name}</span>
            </div>
          ))}
        </div>

        <button className="panel-close" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
