---
date: 2026-11-25
status: accepted
tags: [decision, runs, ux]
---
# ADR-035 Run pipeline replaces a running run only for other data

## Context
Only one run can go at a time ([[ADR-015 Background runs with progress, heartbeat and guards]]). After 8.5 ([[ADR-031 Stop a run through a file in its folder, one exit path with the timeout guard]]), Stop run and Resume run sat under the run's progress, and Run pipeline stayed lit while a run was going, so pressing it only produced "a run is in progress".

Ravid asked for three things:
- Stop and Resume beside Run pipeline
- Run pipeline grayed out while a run is going
- unless the chosen data changed, so the new choice can be run

## Options considered
- Disable Run pipeline whenever a run is going: rejected. Choosing other data would need Stop, a wait and another press.
- Allow a second run in parallel: rejected. One run at a time is a cost and memory guard.
- **Gray it out for the same data; for other data, stop the running run and start the new one** (chosen)

## Decision
- **The launch card** holds Run pipeline with, beside it:
  - Stop run, which becomes "Stopping the run..." (grayed out) once pressed
  - or Resume run, whose note is its tooltip
- **Same data:** `store.run_data` reads what the running run was started with:
  - SECOM
  - the uploaded file, by size
  - or the scenario's kind, intensity and seed. The run's first stage rewrites `scenario.json` as `{"scenario": recipe, ...}`, and both forms are read (#62).
  
  When the launch card's choice is the same, Run pipeline is grayed out.
- **Other data:** Run pipeline stops the running run, which keeps its finished stages and can be resumed later. The new choice waits in the session, and the page starts it on its next refresh after the old run has stopped. A note says so, and Run pipeline stays grayed out meanwhile.
- **No fixed wait:**
  - The first version waited 30 s for the stop and then gave up.
  - A run that has just started needs its process up before it can see the stop request, and on `main` that took 45 to 90 s (#65).

## Consequences
- The new run starts only while the Run Pipeline page is open: the note says to keep it open.
- An upload waiting for its start is kept in the session (its bytes), since the uploader's own object lasts one rerun.
- Tests: an app test where the stop is immediate, one where it is slow, and a browser check of the whole flow, twice in a row.
