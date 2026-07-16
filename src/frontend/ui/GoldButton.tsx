import type { ReactNode } from "react";
import { UI } from "../assets";

// A title/menu button dressed in the Art-Deco gold frame (nine-slice via CSS border-image, so it
// scales to any width without distorting the corners/gems). The LABEL is real HTML text — accessible,
// editable, responsive — never baked into an image.
export function GoldButton({
  children, onClick, disabled, selected, variant = "menu", ariaLabel,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  selected?: boolean;
  variant?: "menu" | "cta" | "ghost";
  ariaLabel?: string;
}) {
  return (
    <button
      type="button"
      className={`gold-btn ${variant} ${selected ? "selected" : ""}`}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-pressed={selected}
      style={variant === "ghost" ? undefined : { borderImageSource: `url(${UI.buttonFrame})` }}
    >
      <span className="gold-btn-label">{children}</span>
    </button>
  );
}
