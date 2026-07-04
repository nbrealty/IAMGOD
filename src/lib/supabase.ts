// Supabase client for I AM GOD.
//
// SECURITY: only the *anon* (public) key belongs here. It is safe to ship in the
// client because access is enforced by Row Level Security policies in the database
// (see supabase/migrations). NEVER put the service_role key in this file or any
// client code — it bypasses RLS.
//
// Both values come from env vars so you can point at different projects per
// environment without code changes. Locally they live in `.env` (gitignored);
// on Vercel set them in Project Settings → Environment Variables.

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const isSupabaseConfigured = Boolean(url && anonKey);

export const supabase: SupabaseClient | null = isSupabaseConfigured
  ? createClient(url as string, anonKey as string)
  : null;

export type ConnectionStatus = "unconfigured" | "checking" | "connected" | "error";

// Lightweight reachability + key-validity check. Hits the PostgREST root with the
// anon key; a 200 confirms the project URL resolves and the key is accepted,
// without assuming any particular table exists yet.
export async function checkSupabaseConnection(): Promise<ConnectionStatus> {
  if (!url || !anonKey) return "unconfigured";
  try {
    const res = await fetch(`${url.replace(/\/$/, "")}/rest/v1/`, {
      headers: { apikey: anonKey, Authorization: `Bearer ${anonKey}` },
    });
    return res.ok ? "connected" : "error";
  } catch {
    return "error";
  }
}
