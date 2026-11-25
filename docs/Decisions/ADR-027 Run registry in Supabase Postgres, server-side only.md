---
date: 2026-11-18
status: accepted
tags: [decision, supabase, data]
---
# ADR-027 Run registry in Supabase Postgres, server-side only

## Context
Runs live as files on a 500 MB volume per environment; only the newest 20 are kept, and nothing can be compared across runs. Phase 8.1 adds a run history and a Trends page.

## Options considered
- Supabase Data API (REST) with the client library and RLS policies
- **Direct Postgres from the server (psycopg 3 through the Session pooler), private schema** (chosen)
- Keep files only

## Decision
- **Tables:** `foresight.runs` (one row per run: status, times, rows and fail rate, selected model and test metrics, anomaly lift, tokens, gates, report checks, full manifest) and `foresight.stages`.
- **Security:**
  - The schema `foresight` is not exposed to the Data API.
  - `anon` and `authenticated` get no privileges.
  - RLS is enabled on every table with no policies (deny by default).
  - Only the server holds the URL; no key reaches the browser.
- **Writes:** when a run finishes, fails or times out (the timeout guard waits at most 3 s). A database problem is logged and never fails a run. Every connection sets a statement timeout and TCP keepalives.
- **Reads:** registry rows are built from the run files. Without `SUPABASE_DB_URL` (tests, CI, a laptop) the app reads the run folders and shows the same numbers.
- **Migrations:** versioned SQL in `supabase/migrations` (created with `supabase migration new`). Railway's **pre-deploy command** (`scripts/db_migrate.py`) applies pending ones to the environment's own project:
  - recorded in `supabase_migrations.schema_migrations`, the CLI's table
  - an advisory lock and one transaction per migration
  - a failing migration stops the deploy; an unreachable database does not
- **Backfill:** at app start, a background thread records the runs on the volume, skipping unchanged ones.
- **CI:** a pgvector Postgres 17 service container runs the database tests.

## Consequences
- History survives pruning and redeploys; Trends charts model quality, stage times and tokens per run.
- Supabase advisors report only INFO notes: "RLS enabled, no policy" (intended) and new indexes not used yet. The unused `(environment, started_at)` index they flagged was replaced by one on `started_at`.
