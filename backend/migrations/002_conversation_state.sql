alter table bot_users
  add column if not exists state jsonb not null default '{}'::jsonb;

create table if not exists telegram_updates (
  workflow_id bigint not null references workflows(id) on delete cascade,
  update_id bigint not null,
  received_at timestamptz not null default now(),
  primary key (workflow_id, update_id)
);
