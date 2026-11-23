---
date: 2026-11-21
status: accepted
tags: [decision, runs]
---
# ADR-031 Stop a run through a file in its folder, one exit path with the timeout guard

## Context
A run takes about 2.5 minutes and spends LLM tokens. Phase 8.5 lets a person stop a run that was started by mistake and resume it later. A run is a separate process ([[ADR-015 Background runs with progress, heartbeat and guards]]) and may be inside an LLM call when asked to stop.

## Options considered
- Kill the process from the app (signal): no clean record of what finished, and different on Windows and Linux
- **A `stop.requested` file in the run folder, checked by the run's process every second** (chosen)
- A flag in the database: the run must work without Supabase too

## Decision
- **Stop run** writes `stop.requested` (with the time and who asked). A watcher thread in the run's process sees it within a second, records the run as **stopped** (`progress.json`, `failure_report.md`, the registry) and exits.
- **One exit path:** the timeout guard and a stop request share one function behind a lock, so only one of them can end a run, and never a run that already finished. A background crew still working is marked with the run's outcome. The registry write waits at most 3 s.
- **Resume run** (formerly Continue) covers stopped runs too: it clears the stop request and reuses every stage whose files are still there ([[ADR-023 Resumable runs]]).
- Stopped runs have their own colour (amber tiles with a square badge) and a plain reason in the history and on Trends.

## Consequences
- Stopping works the same locally, in CI and on Railway, without signals or a database.
- A different run can start right away after a stop; the stopped one keeps its finished stages.
- Tested with a real background run stopped and then resumed to success.
