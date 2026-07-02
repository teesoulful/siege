-- Squad Ops Board — Supabase schema
-- Run this in the Supabase SQL Editor (Project → SQL Editor → New query).
-- Safe to run once on a fresh project. See seed.sql for the follow-up step
-- that needs the squad's real email addresses.

-- Helper functions used by every RLS policy below. Written as SECURITY
-- DEFINER so the internal lookup against `players` runs with the
-- function owner's privileges and bypasses `players`' own RLS — without
-- this, a policy on `players` (or any table) that subqueries `players`
-- triggers that same policy again recursively ("infinite recursion
-- detected in policy for relation players").
create or replace function is_squad_member()
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (select 1 from players where email = auth.email());
$$;

create or replace function is_own_player(pid text)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (select 1 from players where id = pid and email = auth.email());
$$;


-- ---------------------------------------------------------------------
-- players: fixed roster of 4. Login identity is resolved by matching the
-- authenticated user's email against this table — no manual "who am I"
-- step needed once logged in.
-- ---------------------------------------------------------------------
create table players (
  id text primary key,           -- 'tee' | 'tamiym' | 'eman' | 'stefan'
  name text not null,
  email text not null unique
);

alter table players enable row level security;

-- Only visible to the 4 registered squad emails, not any random signup.
create policy "squad can view players" on players
  for select
  using (is_squad_member());


-- ---------------------------------------------------------------------
-- match_state: ONE shared row (id fixed = 1). Map/side/site/bans/picks/
-- round/overtime/who's-active-tonight — anyone in the squad can change
-- this, and everyone's device updates live. This is the deliberately
-- shared state from the design doc's §12.
-- ---------------------------------------------------------------------
create table match_state (
  id int primary key default 1,
  map text not null default 'Bank',
  side text not null default 'Defense',
  site text not null default '',
  round int not null default 1,
  overtime boolean not null default false,
  active_squad jsonb not null default '["tee","tamiym","eman","stefan"]',
  banned jsonb not null default '[]',
  ban_history jsonb not null default '{"Defense": [], "Attack": []}',
  picks jsonb not null default '{"tee": "", "tamiym": "", "eman": "", "stefan": ""}',
  constraint single_row check (id = 1)
);

alter table match_state enable row level security;

create policy "squad can view match state" on match_state
  for select
  using (is_squad_member());

create policy "squad can update match state" on match_state
  for update
  using (is_squad_member())
  with check (is_squad_member());


-- ---------------------------------------------------------------------
-- player_status: one row per player. Only THAT player can write their
-- own alive/dead status — matches §10/§12: everyone can read everyone's
-- status (for the squad strip), but each row is writable only by the
-- squad member it belongs to.
-- ---------------------------------------------------------------------
create table player_status (
  player_id text primary key references players(id),
  alive boolean not null default true
);

alter table player_status enable row level security;

create policy "squad can view player status" on player_status
  for select
  using (is_squad_member());

create policy "only own row is writable" on player_status
  for update
  using (is_own_player(player_id))
  with check (is_own_player(player_id));


-- ---------------------------------------------------------------------
-- Realtime: so every open device gets pushed changes instantly instead
-- of needing to poll or refresh.
-- ---------------------------------------------------------------------
alter publication supabase_realtime add table match_state;
alter publication supabase_realtime add table player_status;
