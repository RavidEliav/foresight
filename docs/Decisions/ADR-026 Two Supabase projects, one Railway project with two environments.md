---
date: 2026-11-18
status: accepted
tags: [decision, deployment, supabase]
---
# ADR-026 Two Supabase projects, one Railway project with two environments

## Context
Phase 8 adds Supabase Postgres (run registry, cross-run memory). The free plan has no branching or environments, and `dev` and `main` must not share run history: a test run on `dev` would show up in the presentation app. ADR-003 says both Railway environments get the same variables.

## Options considered
- One Supabase project, rows tagged `dev` / `main` (keeps ADR-003 fully)
- **Two Supabase projects, `foresight-dev` and `foresight-main`** (chosen by Ravid)
- Also two Railway projects (rejected: Railway environments already isolate services, volumes, variables, URLs and deploys)

## Decision
- Two free Supabase projects in **East US (North Virginia)**, next to the Railway volume (`iad`). The first pair was created in Tokyo by mistake and recreated while empty.
- Each Railway environment gets its own `SUPABASE_DB_URL` (Session pooler); `scripts/push_secrets_to_railway.ps1` reads `SUPABASE_DB_URL_DEV` / `SUPABASE_DB_URL_MAIN` from `.env`, and the IaC keeps it with `preserve()`. This is the one exception to ADR-003.
- Railway stays one project with the environments `dev` and `main`.
- The Intel office network blocks Postgres ports (5432/6543), so the laptop never connects to the databases: deploys migrate them (ADR-027), and checks run over HTTPS (Supabase CLI with an access token: `db query --read-only`, `db advisors`, `logs`).

## Consequences
- Dev runs never appear on `main`, and a schema change reaches `main` only with a release.
- Two database passwords to keep. Both first passwords were wrong ("password authentication failed" in Supabase's pooler logs) and had to be reset; the pre-deploy message said "unreachable" for any connection error, which hid the cause.
