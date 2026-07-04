-- I AM GOD — initial schema.
--
-- A starter `game_saves` table so save/load has a real backing store from the
-- start (the doctrine flags save/load as something to design WITH the engine,
-- not bolt on later). Row Level Security is ON and scoped to the owning user, so
-- the client-side anon key can never read or write another player's saves.
--
-- Apply this with the Supabase CLI:
--   supabase db push
-- or paste it into the Supabase dashboard → SQL Editor and run it.

create extension if not exists "pgcrypto";

create table if not exists public.game_saves (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  slot smallint not null default 0,
  label text,
  -- The full serialized world/soul state. JSONB now; can migrate to a columnar
  -- or blob layout later if saves grow large.
  state jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, slot)
);

alter table public.game_saves enable row level security;

-- Owners can do anything to their own rows; nobody can touch anyone else's.
create policy "own saves - select"
  on public.game_saves for select
  using (auth.uid() = user_id);

create policy "own saves - insert"
  on public.game_saves for insert
  with check (auth.uid() = user_id);

create policy "own saves - update"
  on public.game_saves for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "own saves - delete"
  on public.game_saves for delete
  using (auth.uid() = user_id);

-- keep updated_at fresh
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists game_saves_touch on public.game_saves;
create trigger game_saves_touch
  before update on public.game_saves
  for each row execute function public.touch_updated_at();
