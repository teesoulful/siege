-- Squad Ops Board — seed data
-- Run AFTER schema.sql. Fill in the 4 real email addresses before running.

insert into players (id, name, email) values
  ('tee',    'Tee',    'REPLACE_WITH_TEE_EMAIL'),
  ('tamiym', 'TAMIYM', 'REPLACE_WITH_TAMIYM_EMAIL'),
  ('eman',   'Eman',   'REPLACE_WITH_EMAN_EMAIL'),
  ('stefan', 'Stefan', 'REPLACE_WITH_STEFAN_EMAIL');

insert into match_state (id) values (1);

insert into player_status (player_id, alive) values
  ('tee', true), ('tamiym', true), ('eman', true), ('stefan', true);
