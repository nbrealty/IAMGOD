import { inventorySlots } from "../game/inventory";

interface Props {
  soulId: string;
  equippedStem: string; // stem currently worn by this soul
  onEquip: (stem: string) => void;
}

// A touch-friendly 4×5 grid of inventory slots (research: fixed grid, tap-to-equip, clear
// highlight on the equipped item, dim placeholders for empty slots). Filled slots show the
// outfit's sprite; tapping one equips it live. Reused by the controlled-character sheet and the
// Soul Profile panel, so any character or NPC can be dressed from the same component.
export function InventoryGrid({ soulId, equippedStem, onEquip }: Props) {
  const slots = inventorySlots(soulId);
  return (
    <div className="inv-grid">
      {slots.map((slot, i) => {
        if (!slot) {
          return <div className="inv-slot empty" key={i} aria-hidden="true" />;
        }
        const active = slot.stem === equippedStem;
        return (
          <button
            key={i}
            className={`inv-slot ${active ? "active" : ""}`}
            onClick={() => onEquip(slot.stem)}
            aria-pressed={active}
            title={slot.label}
          >
            <img
              className="inv-thumb"
              src={`/spirits/${slot.stem}.png`}
              alt={slot.label}
              draggable={false}
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.visibility = "hidden";
              }}
            />
            <span className="inv-label">{slot.label}</span>
            {active && <span className="inv-worn">✓ Worn</span>}
          </button>
        );
      })}
    </div>
  );
}
