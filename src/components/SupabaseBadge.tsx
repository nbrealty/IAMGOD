import { useEffect, useState } from "react";
import { checkSupabaseConnection, type ConnectionStatus } from "../lib/supabase";

const LABELS: Record<ConnectionStatus, string> = {
  unconfigured: "DB: not configured",
  checking: "DB: checking…",
  connected: "DB: connected",
  error: "DB: error",
};

export function SupabaseBadge() {
  const [status, setStatus] = useState<ConnectionStatus>("checking");

  useEffect(() => {
    let alive = true;
    checkSupabaseConnection().then((s) => {
      if (alive) setStatus(s);
    });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className={`db-badge ${status}`} title="Supabase connection status">
      <span className="db-dot" />
      {LABELS[status]}
    </div>
  );
}
