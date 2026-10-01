import { useEffect, useState } from "react";

// Which responsive layout to render: portrait/narrow phones get the "mobile" treatment
// (stacked logo, portrait bg, vertical menu), everything else "desktop". Driven by matchMedia
// so we only mount the heavy art for the current layout (see the per-layout asset picks).
export type Layout = "desktop" | "mobile";

const QUERY = "(max-width: 820px), (orientation: portrait)";

export function useLayout(): Layout {
  const [layout, setLayout] = useState<Layout>(() =>
    typeof window !== "undefined" && window.matchMedia(QUERY).matches ? "mobile" : "desktop",
  );
  useEffect(() => {
    const mq = window.matchMedia(QUERY);
    const on = () => setLayout(mq.matches ? "mobile" : "desktop");
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return layout;
}

// Whether the user asked for reduced motion (title/particle animation respects this).
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReduced(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}
