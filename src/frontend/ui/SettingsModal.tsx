import { useEffect, useRef } from "react";

// Small accessible settings modal: reduced-motion override, a mute placeholder (no audio system
// yet), and a UI text-size preference. Focus-trapped, Esc closes, restores focus on close.
export function SettingsModal({
  reducedMotion, onReducedMotion, muted, onMuted, textScale, onTextScale, onClose,
}: {
  reducedMotion: boolean; onReducedMotion: (v: boolean) => void;
  muted: boolean; onMuted: (v: boolean) => void;
  textScale: number; onTextScale: (v: number) => void;
  onClose: () => void;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const prevFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    prevFocus.current = document.activeElement as HTMLElement;
    cardRef.current?.querySelector<HTMLElement>("button, input, select")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && cardRef.current) {
        const f = cardRef.current.querySelectorAll<HTMLElement>('button, input, select, [tabindex]:not([tabindex="-1"])');
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prevFocus.current?.focus(); };
  }, [onClose]);

  return (
    <div className="fe-modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="fe-modal" ref={cardRef} role="dialog" aria-modal="true" aria-label="Settings">
        <h2>Settings</h2>
        <label className="fe-row">
          <span>Reduced motion</span>
          <input type="checkbox" checked={reducedMotion} onChange={(e) => onReducedMotion(e.target.checked)} />
        </label>
        <label className="fe-row">
          <span>Mute</span>
          <input type="checkbox" checked={muted} onChange={(e) => onMuted(e.target.checked)} />
        </label>
        <label className="fe-row">
          <span>Text size</span>
          <select value={textScale} onChange={(e) => onTextScale(Number(e.target.value))}>
            <option value={0.9}>Small</option>
            <option value={1}>Normal</option>
            <option value={1.15}>Large</option>
          </select>
        </label>
        <button className="fe-modal-close" onClick={onClose}>Done</button>
      </div>
    </div>
  );
}
