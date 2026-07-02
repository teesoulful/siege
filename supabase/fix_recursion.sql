-- Squad Ops Board — fixes "infinite recursion detected in policy for
-- relation players" from schema.sql. Cause: the players SELECT policy
-- queried players from inside its own policy (and match_state/
-- player_status's policies queried players too, which recursed into
-- that same broken policy). Fix: two SECURITY DEFINER helper functions
-- that check squad membership *without* going back through RLS, then
-- point every policy at those instead of subquerying players directly.
-- Run this in the SQL Editor after schema.sql.

drop policy if exists "squad can view players" on players;
drop policy if exists "squad can view match state" on match_state;
drop policy if exists "squad can update match state" on match_state;
drop policy if exists "squad can view player status" on player_status;
drop policy if exists "only own row is writable" on player_status;

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

create policy "squad can view players" on players
  for select
  using (is_squad_member());

create policy "squad can view match state" on match_state
  for select
  using (is_squad_member());

create policy "squad can update match state" on match_state
  for update
  using (is_squad_member())
  with check (is_squad_member());

create policy "squad can view player status" on player_status
  for select
  using (is_squad_member());

create policy "only own row is writable" on player_status
  for update
  using (is_own_player(player_id))
  with check (is_own_player(player_id));
