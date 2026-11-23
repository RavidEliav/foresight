-- Everything a run leaves behind is kept in Supabase (ADR-033), so the Railway volume only
-- holds the newest runs whole and a small stub of the others.

-- The run's progress (stages, who started, resumed or stopped it), so a run's stub can be
-- rebuilt on an empty volume, and when its files were archived in Storage.
alter table foresight.runs
  add column progress      jsonb,
  add column archived_at   timestamptz,
  add column archive_bytes bigint;

-- Chat history: every question and answer, about one run or about all runs ("all_runs").
create table foresight.questions (
  id         bigint generated always as identity primary key,
  asked_at   timestamptz not null,
  run        text not null,
  user_email text not null default '',
  question   text not null,
  record     jsonb not null,             -- the whole logged answer, as the app shows it
  unique (asked_at, run, user_email, question)
);

create index questions_run_asked_at on foresight.questions (run, asked_at desc);
create index questions_user_asked_at on foresight.questions (user_email, asked_at desc);

alter table foresight.questions enable row level security;

do $$
declare
  client_role text;
begin
  foreach client_role in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = client_role) then
      execute format('revoke all on foresight.questions from %I', client_role);
    end if;
  end loop;
end
$$;

-- A private bucket for the run archives (one .tar.gz per run, at most 50 MB). Only the server
-- uses it, with the project's secret key; there are no storage policies, so the client roles
-- cannot read it. A plain Postgres (CI) has no storage schema and skips this.
do $$
begin
  if exists (select 1 from pg_namespace where nspname = 'storage') then
    insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
    values ('runs', 'runs', false, 52428800, array['application/gzip'])
    on conflict (id) do nothing;
  end if;
end
$$;
