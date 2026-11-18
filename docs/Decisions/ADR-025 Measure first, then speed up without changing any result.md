---
date: 2026-11-18
status: accepted
tags: [decision, performance]
---
# ADR-025 Measure first, then speed up without changing any result

## Context
Phase 7 goal (Ravid): remove limitations and make the app faster without losing capabilities or accuracy. A run on the 1 GB Railway trial had been killed for memory, a real run took 3.3–3.6 minutes, and the app server alone used about 500 MB.

## Options considered
- Tune by intuition (smaller models, fewer bootstrap samples, a smaller test split): faster, but changes the numbers
- **Measure each stage and each page, change only what does not change a result, and prove it with a numeric comparison** (chosen)
- Split into a UI service and an API service now: more moving parts; postponed ([[ADR-020 Single service now, frontend-backend seam in Phase 7]])

## Decision
- **Measurement tools:** `scripts/measure_run.py` (time and peak memory per stage), `scripts/measure_app.py` (app memory per page).
- **The comparison rule:** `scripts/compare_runs.py <run>` compares every number in the analytics outputs with the reference run, and a change is kept only if it reports 0 differences.
- **Memory:**
  - embeddings in batches of 8
  - the app no longer imports the Flow (run ids from `progress.py`)
  - the chat calls the OpenAI SDK directly
  - the precision-recall curve in NumPy
- **Speed:**
  - The Data Analyst and Data Scientist crews run in background threads while the next stages compute. Each crew snapshots its fact sheets, accepted numbers and visible files when it starts, so it sees what a sequential run would see.
  - The Flow joins them before the report and on failure.
  - A crew's outputs, usage and "done" are recorded together, so Continue never reuses a half-recorded stage.
  - Bootstrap metrics are in NumPy (tested equal to scikit-learn); permutation importance runs in parallel threads.
- **Seam:** all page access to runs, jobs and the chat goes through `app/store.py` (a test enforces it).

## Consequences
- Same numbers, measured gains:
  - real run 2.5 min
  - run peak memory 973 → 640 MB
  - app 521 → 323 MB
  - `dev` service at rest after a run 1,239 → 445 MB
- A stage can be finished while its crew still works. The stage tiles show such a stage as running until its crew is done (#33).
- The LLM texts still vary between real runs (gpt-4o-mini at temperature 0). The comparison covers the analytics numbers; the crew texts are covered by the output checks.
