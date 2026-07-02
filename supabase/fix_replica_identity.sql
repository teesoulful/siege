-- Squad Ops Board — Supabase Realtime requires REPLICA IDENTITY FULL on a
-- table for UPDATE events to reliably deliver the full row (and for RLS to
-- evaluate correctly on those events) when subscribing via postgres_changes.
-- Without this, UPDATE broadcasts can silently fail to reach subscribed
-- clients even though the write itself succeeds and the table is in the
-- publication. Run this in the SQL Editor.

alter table match_state replica identity full;
alter table player_status replica identity full;
