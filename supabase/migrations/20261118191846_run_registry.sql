-- Foresight run registry (ADR-027): one row per pipeline run and one per stage.
-- Server-side only: the app connects with the database URL (Session pooler). The schema is
-- not exposed to the Data API, the client roles get no privileges, and RLS is enabled with
-- no policies (deny by default) as a second layer.

create schema if not exists foresight;

create table foresight.runs (
  run_id            text primary key,
  environment       text not null,
  source            text not null,           -- secom, upload, scenario, reference
  dataset           text,
  status            text not null,           -- success, failed, timeout, interrupted
  started_at        timestamptz,
  finished_at       timestamptz,
  duration_s        real,
  rows              integer,
  fail_rate         real,
  selected_model    text,
  pr_auc            real,
  baseline_pr_auc   real,
  roc_auc           real,
  recall            real,
  precision         real,
  balanced_accuracy real,
  runs_flagged      integer,
  flag_lift         real,
  total_tokens      integer,
  llm_model         text,
  llm_mock          boolean,
  report_pass       integer,
  report_warning    integer,
  report_error      integer,
  gates             jsonb not null default '[]'::jsonb,
  failure_reason    text,
  git_commit        text,
  manifest          jsonb,
  recorded_at       timestamptz not null default now()
);

create index runs_environment_started_idx on foresight.runs (environment, started_at desc);

create table foresight.stages (
  run_id       text not null references foresight.runs (run_id) on delete cascade,
  name         text not null,
  position     smallint not null,
  status       text not null,
  crew_status  text,
  seconds      real,
  crew_seconds real,
  tokens       integer,
  primary key (run_id, name)
);

alter table foresight.runs enable row level security;
alter table foresight.stages enable row level security;

-- Supabase's client roles (absent in a plain Postgres used by CI) get nothing in this schema.
do $$
declare
  client_role text;
begin
  foreach client_role in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = client_role) then
      execute format('revoke all on schema foresight from %I', client_role);
      execute format('revoke all on all tables in schema foresight from %I', client_role);
      execute format('alter default privileges in schema foresight revoke all on tables from %I',
                     client_role);
    end if;
  end loop;
end
$$;