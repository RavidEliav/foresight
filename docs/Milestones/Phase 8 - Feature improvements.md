---
date: 2026-11-20
updated: 2026-11-23
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

Added on the way: Stop/Resume, sign-in with roles (Nov 20), one screen per page (Nov 22).

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
- **8.4 Line Replay and a simulated 3D wafer** (#44):
  - the test period played back run by run from the run's own scores and alarms, so the totals match the report (reference run: 40 alarms, 5 of 24 failing runs) ([[ADR-030 Line Replay replays stored scores; the wafer is a labeled simulation]])
  - a 3D wafer per run, labeled as a simulation everywhere (SECOM has no die positions)
- **8.5 Stop run and Resume run** (#45): a `stop.requested` file checked every second, one exit path shared with the timeout guard, finished stages kept for Resume ([[ADR-031 Stop a run through a file in its folder, one exit path with the timeout guard]])
- **8.6 Sign-in, access requests and roles** (#46, #49) ([[ADR-032 Google sign-in with emailed approval and two roles]]):
  - Google sign-in for the whole app; sessions end on sign-out, browser close or 1 hour idle
  - access requests emailed to the developers with one-click Approve / Deny links
  - two roles: users see only their own runs plus the reference run; developers see everything plus Trends and Users & access
  - "Hi, name", My activity, and no passcodes
- **Fixes after 8.6:**
  - **#47:** secrets reach Railway without a byte-order mark, and no password appears in logs.
  - **#48:** E8 runs in CI only.
  - **#49:** All runs questions now show in Recent questions.
- **Storage** (#50, #51) ([[ADR-033 Run files and chat history in Supabase, stubs on the volume]]):
  - **The incident (Nov 22):** the dev volume filled up.
  - **#50:** interrupted runs name their real cause; Start and Resume check free space first; the embedding model cache moved off the volume.
  - **#51:** run files go to Supabase Storage and chat history to Postgres; the volume keeps stubs of older runs.

8.3 to 8.6 are on `dev`; `main` runs 8.1 and 8.2 (#40). #50 and #51 are open.

## Test results
- 282 tests pass locally, plus the Postgres test in CI (a pgvector Postgres 17 service container: registry, chunks, chat history)
- Smoke + E2E green in CI. The deployed tests check the sign-in screen and the public pages; E1–E8 run in CI against the local app, since a test browser cannot sign in with Google.
- Supabase advisors on both projects: INFO notes only

## Issues found (lessons)
- **Region:** the first Supabase projects were in Tokyo (the dashboard default) while Railway runs in Virginia. They were recreated while empty.
- **Office network:**
  - It blocks Postgres (5432) and SSH (22). Migrations run in Railway's pre-deploy step, checks go over HTTPS (Supabase CLI and MCP with an access token), and the full-volume cleanup ran as a one-time start command.
  - Railway's "redeploy" reuses the old deployment's variables and start command; a fresh deploy (`railway up` or a push) picks up new ones.
- **Database passwords:** both URLs first had a wrong password. Supabase's pooler logs showed "password authentication failed", while the app's message said "unreachable" for any connection error.
- **Secrets with a byte-order mark (#47):** Windows PowerShell piped every secret to the Railway CLI with U+FEFF in front. The database URL stopped parsing, and psycopg's error printed the whole URL, password included, into the deploy log. The script now writes exact bytes and reads them back, and `redact()` hides URL passwords.
- **Sign-in:**
  - Ravid's Intel account cannot complete Google sign-in (most likely Intel IT policy), and registering a Microsoft (Entra) app is blocked too, so the Gmail account is used.
  - A stale OAuth callback from browser back/forward keeps the previous cookie, which looked like one account signing in as another.
  - Approval emails go only to people who ask for access themselves, not to accounts the developer adds.
- **What a user sees (#49):** a user first saw all 21 runs, and questions asked in All runs mode never reached Recent questions. Testing as a second account found both.
- **Full volume (Nov 22):**
  - The embedding model cache took 167 MB of the 500 MB volume, and runs take 12–36 MB each.
  - Two runs died silently. The page said "interrupted, for example because the app restarted", and Resume crashed. The run could not even write its own error.
  - Lesson: store data where it can grow (Supabase), and report a failure's real cause.
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
Plan renumbered on Nov 22:
- **8.7 One screen per page:** the main part of each page fits the screen on desktop and phone, and every table's columns fit their content.
- **8.8** PDF export
- **8.9** Voice
- **8.10 Course extras:** retrieval evaluation, prompt-injection tests, MCP server
- **8.11** Vault close-out, README and release to `main`
