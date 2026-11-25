---
date: 2026-11-20
updated: 2026-11-25
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
  - **On `dev`:** 4 runs archived (5 to 7 MB each), 45 chat questions imported, a Storage round trip checked.
- **#53:** an All runs summary may name a run by its date. The run id's date and time parts count as known numbers, so "the run on Nov 22" is no longer withheld as an ungrounded number.
- **8.7 One screen per page** (#54) ([[ADR-034 One screen per page with tabs inside cards and tables that wrap]]):
  - the summary card beside one chart card with tabs; less space at the top; long captions as tooltips
  - Investigation & Report's main part: 2,670 px → 663 px; every page fits a laptop window (1536×730) and a desktop
  - on a phone, headline numbers two per row, and the title, headline and the start of the main content on the first screen
  - tables: columns fit their header or longest value; long or wide tables wrap instead of cutting columns off
  - E9 checks the fit in CI; `scripts/measure_fit.py` measures and screenshots every page
  - **After Ravid's check (#56):** Extended data tabs stay closed until pressed; Run Pipeline fits with a run in progress; the Ask Foresight conversation scrolls in its own box under a fixed title and question bar; Play/Pause on Line Replay no longer moves the page; the sign-in page's Privacy and Terms links are no longer cut
- **Release to `main`** (#57, Nov 25): 8.3 to 8.7 and storage; `main`'s Supabase got the accounts and run-files migrations and the `runs` bucket.
- **Phone check (#58):**
  - the "Hi, name" menu opens with a tap (Streamlit's transparent header lay over it)
  - every page fits a phone: a phone view (user agent) with one card of tabs, lower charts, compact tiles, Extended data as a dropdown
  - the Run Pipeline stage cards no longer overflow
  - a signed-out link to a page such as `/activity` opens the sign-in screen instead of "Page not found"
  - Stop run and Resume run beside Run pipeline, which is grayed out while a run with the same data is going ([[ADR-035 Run pipeline replaces a running run only for other data]])
- **Second phone check (#59, #60):**
  - tapping the question bar or the Extended data dropdown no longer zooms the page (an iPhone zooms into text fields under 16 px)
  - a pinch on a 2D chart zooms it like the rest of the page (Plotly takes every touch on a 2D chart and has no pinch zoom; on a phone those charts are still pictures, 3D charts keep their own pinch)
  - the running stage's circle spins on a phone, and while the run's process starts up the first stage already spins ("starting")
  - a tap on a dropdown opens its list instead of the keyboard (no typing in short lists; long lists search on a computer only)
- **Release to `main`** (#61).
- **Check of `main` after the release (#62, #63):**
  - Stop run and Resume run on a scenario run showed KeyError 'kind': the run's first stage rewrites scenario.json as {"scenario": recipe, ...}, and the new launch card read only the first form
  - Line Replay: End reached the end, then jumped back. A timer tick in flight sent the slider's old position, which counted as a drag; slider changes while playing or just after a button are ignored
  - All runs chat: an answer citing a section that was not retrieved (another run's section) gets one more try with what was wrong, before it is withheld
  - Ask Foresight: the examples sit right above the question bar, compact; on a phone both are pinned to the bottom (#63)
  - Privacy and Terms opened from the sign-in screen lead back to it
- **Release to `main`** (#64).
- **Validation on `main` (#65):**
  - Run pipeline with other data, the first time: the page waited at most 30 s for the running run to stop, but a run that has just started needs its process up first (45 to 90 s on `main`), so it gave up. The new run now waits in the session and starts as soon as the old one has stopped.
  - Line Replay, End while playing, the first time: on the server a slow first page run can let the slider's old position arrive after the 2 s guard. Positions the playback showed are remembered and never count as a drag. A phone shows Play, Restart, Next and End as words (Next run's icon looked like End's).
- **Release to `main`** (#66, Nov 25).
- **8.8 Run report** (#68) ([[ADR-036 A run report PDF of every result page, built from the run's files]]):
  - every result page of a run in one PDF (about 10 pages): cover with the numbers at a glance, Data Quality, EDA & Insights, Model, Investigation & Report with the engineering report in full, appendix with the report's checks
  - citations kept; built only from the run's files, so older runs and the reference run get it too; a new run saves `run_report.pdf`
  - "Download full run report" in the sidebar under "Results shown" (Ravid's choice), and beside "See the results" when a run completes

Everything above is on `main` (#66, Nov 25); `main` and `dev` are the same.

## Test results
- 290 tests (unit, integration, app and E2E) pass locally and in CI, plus the Postgres test in CI (a pgvector Postgres 17 service container: registry, chunks, chat history)
- Smoke + E2E green in CI. The deployed tests check the sign-in screen and the public pages; E1–E9 run in CI against the local app, since a test browser cannot sign in with Google.
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
- **Run dates in summaries (#53):** Ravid's "all runs" question was answered "not found in recorded runs": the summary named runs by date, and the date's numbers were not in any excerpt's text, only in the run ids.
- **Swapping widgets moves the page (#56):** Line Replay's Play and Pause were two buttons. For a moment the browser showed both, and the slider disappeared while playing, so the cards jumped. One button with a fixed key whose label changes, and a slider that always shows, keep every element in place.
- **Fit on another machine (8.7):** Line Replay fit locally but measured 730 px on CI's 730 px window, because the reference run's label is longer. A fit test needs a margin.
- **A phone is not a narrow window:** the phone checks found what a narrow desktop browser could not show: the header over the menu, an iPhone zooming into small text fields, Plotly taking pinches, a dropdown opening the keyboard. The phone view keys off the user agent, and E9 runs with an iPhone user agent.
- **Browser and server race:** the browser keeps sending what it showed a moment ago (a timer tick in flight, a slider's old value). Code that reacts to a widget change must tell an echo from a real change.
- **A second reader of a file:** the launch card read `scenario.json` in the form the app writes, but the run's first stage rewrites it. The traceback was in `main`'s log within a minute of Ravid's report.
- **Fixed waits on the server:** a 30 s wait that never ran out locally gave up on `main`, where a new run's process takes much longer to start.
- **Wording:** "1175 training runs changed" counted the training period, not the 80 runs actually shifted.

## Next
Plan changed on Nov 25 (Ravid): voice and the MCP server are future features, built after the submission (Dec 4), not part of it.
- **8.9 Course extras:** retrieval evaluation and prompt-injection tests
- **8.10** Vault close-out, README and release to `main`
- **After the submission:** voice (ask by voice, answers read aloud) and an MCP server exposing Foresight's tools
