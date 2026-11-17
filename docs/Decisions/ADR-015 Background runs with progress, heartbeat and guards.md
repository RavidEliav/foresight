---
date: 2026-11-16
status: accepted
tags: [decision, app, deployment]
---
# ADR-015 Background runs with progress, heartbeat and guards

## Context
A full run takes about 3.5 minutes. Running it inside the Streamlit request blocked the page, and a refresh or a closed tab lost the run. The requirements ask for live progress, a timeout guard and cost/abuse control (D5, D8).

## Options considered
- Keep synchronous runs: simple, but fragile and blocks the page
- A thread inside the Streamlit process: dies with the script session, hard to see from other sessions
- A task queue (Celery/Redis): an extra service to run and pay for
- **A separate process per run** (`python -m foresight.cli run`) that writes `progress.json`

## Decision
- The app starts the run as a detached process; the Flow and the runner write `progress.json` (stages, crews, gates, a heartbeat every 15 s) and `run.log` into the run folder.
- The page reads `progress.json` every 2 s (`st.fragment(run_every=2)`), so any visitor sees the live run.
- Guards (`app` in `config/settings.yaml`): one run at a time, at most 6 runs per hour, a 20-minute timeout guard, a run without a heartbeat for 90 s counts as interrupted, the newest 20 finished runs are kept.

## Consequences
- Runs survive a refresh and a closed tab; a redeploy interrupts a running run (shown as interrupted).
- No extra infrastructure. Revisit the limits in the performance phase (a queue instead of one-at-a-time).
- Related: [[ADR-016 Uploads through the Data Contract, runs on a Railway volume]]
