---
date: 2026-11-20
phase: 8
tags: [milestone, features]
---
# Phase 8: Feature improvements (in progress)

Ravid's picks:
- Supabase run registry and Trends
- cross-run chat
- Scenario Lab
- line replay with a 3D wafer
- PDF export
- voice
- course extras: retrieval evaluation, injection tests, MCP server

Sources: the course `Final_Project` folder, Daniel's lectures, the BanAI project, and the Phase 7 list. The phase is time-boxed before Phase 9 (deliverables due Dec 4).

## Director's feedback on the proposal (Nov 19)
- The direction and specification are right; no change needed.
- Synthetic data must be labeled and kept separate, and metrics computed only on the original SECOM data → [[ADR-029 Synthetic scenarios change only the training period]].
- The RAG chat is an enhancement; the end-to-end workflow ending with `engineering_report` is the primary deliverable. Ravid decided no further RAG changes or extra end-to-end evidence run are needed: the workflow has run end to end since Phase 4, and the reference run passes 26/26 report checks.

## Delivered so far
- **8.1 Run registry and Trends** (#36, #39):
  - Supabase Postgres, server-side only; migrations on deploy; startup backfill ([[ADR-026 Two Supabase projects, one Railway project with two environments]], [[ADR-027 Run registry in Supabase Postgres, server-side only]])
  - the Trends page: KPIs, model quality, time per stage, tokens, outcomes as a plain-language list
- **8.2 All runs chat** (#37, #38): pgvector cross-run memory, per-run citations, grounded summaries ([[ADR-028 Cross-run chat with pgvector and grounded summaries]]). The Ask passcode now sits in a card like Run Pipeline (#39).
- **8.3 Scenario Lab** (#41, #42):
  - four seeded synthetic scenarios that change only the training period, with a guard check, SYNTHETIC labels everywhere and a ground-truth card ([[ADR-029 Synthetic scenarios change only the training period]])
  - live run on `dev`: 2.7 min, 28/28 report checks, planted sensor f_558 at EDA rank 1 of 15
- **Release to `main`** (#40): both Supabase projects migrated; deployed tests green.

## Test results
- 225+ tests; CI includes a pgvector Postgres 17 service container (registry, chunks, pgvector search ranked like the run folders)
- Smoke + E2E green in CI and as deployed tests on `dev` and `main`
- Supabase advisors on both projects: INFO notes only

## Issues found (lessons)
- **Region:** the first Supabase projects were in Tokyo (the dashboard default) while Railway runs in Virginia. They were recreated while empty.
- **Office network:** it blocks Postgres ports, so the design moved migrations into Railway's pre-deploy step and checks to HTTPS (Supabase CLI with an access token).
- **Database passwords:** both URLs first had a wrong password. Supabase's pooler logs showed "password authentication failed", while the app's message said "unreachable" for any connection error.
- **Citations across runs:** the strict citation rule withheld every real cross-run answer (uncited summaries) until summaries with grounded numbers were allowed.
- **Pandas NaN:** a missing failure reason arrives as NaN and broke the Trends outcomes card halfway.
- **Code reviews found:**
  - a timeout guard that could wait on a slow database
  - a second wait on an unreachable database in Trends
  - a question opened from the sidebar that vanished in All runs mode
  - a sensor-outage recipe whose window moved on Continue (one random generator shared by two steps)
  - stopped scenario runs recorded as SECOM
- **Wording:** "1175 training runs changed" counted the training period, not the 80 runs actually shifted.

## Next
8.4 line replay + 3D wafer simulation · 8.5 PDF export · 8.6 voice · 8.7 course extras (retrieval evaluation, injection tests, MCP server) · vault close-out and release.
