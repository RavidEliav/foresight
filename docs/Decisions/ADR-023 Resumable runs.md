---
date: 2026-11-18
status: accepted
tags: [decision, runs]
---
# ADR-023 Resumable runs

## Context
A run on `dev` stopped in its fourth stage: the background process was killed (memory) while the app kept running. A restart or redeploy also interrupts a run. Starting again costs the full run time and tokens.

## Options considered
- "Run again" with the same data, from the start
- **Continue from the interrupted stage, reusing the finished ones** (chosen by Ravid)

## Decision
- Each finished stage records in `progress.json` its artifacts, gate checks, crew usage and crew status.
- `python -m foresight.cli run --run-id <id> --resume` reuses a stage only if it finished and all its files still exist; ingest is always redone (about a second, and it re-reads the data checksums). Gates are re-evaluated from the saved checks.
- The app offers **Continue run** for interrupted, timed-out and crashed runs, not for runs a gate stopped (the same data would stop again). It needs the passcode and counts toward the hourly limit; after a restart the newest continuable run is shown.

## Consequences
- Tokens spent by a crew that was cut off mid-way are lost; tokens of finished stages are kept in the totals.
- Runs from before this change have no stage records, so Continue reruns them from the start (the button says so).
