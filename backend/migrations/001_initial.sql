create table if not exists workflows (
  id bigint generated always as identity primary key,
  name text not null check (char_length(name) between 2 and 120),
  description text not null default '',
  definition jsonb not null,
  is_published boolean not null default false,
  telegram_bot_token text,
  telegram_bot_username varchar(80),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_workflows_updated_at on workflows (updated_at desc);

-- users and dialog history (for analytics and published bot)
create table if not exists bot_users (
  id bigint generated always as identity primary key,
  workflow_id bigint not null references workflows(id) on delete cascade,
  telegram_user_id bigint not null,
  username text,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  current_node_id text,
  unique (workflow_id, telegram_user_id)
);
create index if not exists idx_bot_users_workflow on bot_users (workflow_id);

create table if not exists messages (
  id bigint generated always as identity primary key,
  workflow_id bigint not null references workflows(id) on delete cascade,
  bot_user_id bigint references bot_users(id) on delete set null,
  telegram_user_id bigint,
  direction text not null check (direction in ('in','out')),
  text text not null,
  node_id text,
  created_at timestamptz not null default now()
);
create index if not exists idx_messages_workflow_created on messages (workflow_id, created_at desc);
create index if not exists idx_messages_telegram_user on messages (telegram_user_id);

