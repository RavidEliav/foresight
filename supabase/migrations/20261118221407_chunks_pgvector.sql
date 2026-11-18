-- Cross-run memory (Phase 8.2): every successful run's chat chunks with their embeddings
-- (all-MiniLM-L6-v2, 384 dimensions, unit length), so "Ask Foresight" can search all runs.
-- Same access model as the registry: server-side only, private schema, RLS with no policies.

create schema if not exists extensions;
create extension if not exists vector with schema extensions;

create table foresight.chunks (
  run_id    text not null references foresight.runs (run_id) on delete cascade,
  position  integer not null,
  source    text not null,
  section   text not null,
  body      text not null,
  embedding extensions.vector(384) not null,
  primary key (run_id, position)
);

-- Cosine distance (the vectors are unit length; similarity = 1 - distance)
create index chunks_embedding_hnsw_idx on foresight.chunks
  using hnsw (embedding extensions.vector_cosine_ops);

alter table foresight.chunks enable row level security;

do $$
declare
  client_role text;
begin
  foreach client_role in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = client_role) then
      execute format('revoke all on foresight.chunks from %I', client_role);
    end if;
  end loop;
end
$$;

-- Advisor (unused_index): each environment has its own project, so the history is read by
-- start time only.
drop index if exists foresight.runs_environment_started_idx;
create index runs_started_idx on foresight.runs (started_at desc);