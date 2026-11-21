-- Sign-in (Phase 8.6): who may use Foresight, and who started each run.
-- Same access model as the registry: server-side only, private schema, RLS with no policies.

create table foresight.accounts (
  email        text primary key check (email = lower(email) and position('@' in email) > 1),
  name         text not null default '',
  role         text not null default 'user' check (role in ('user', 'developer')),
  status       text not null default 'pending' check (status in ('pending', 'approved', 'denied')),
  message      text not null default '',     -- what the requester wrote
  requested_at timestamptz,
  decided_at   timestamptz,
  decided_by   text,
  created_at   timestamptz not null default now()
);

alter table foresight.accounts enable row level security;

-- The signed-in email that started a run (empty for runs from the command line)
alter table foresight.runs add column started_by text;

do $$
declare
  client_role text;
begin
  foreach client_role in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = client_role) then
      execute format('revoke all on foresight.accounts from %I', client_role);
    end if;
  end loop;
end
$$;
