---
date: 2026-11-21
status: accepted
tags: [decision, app, replay]
---
# ADR-030 Line Replay replays stored scores; the wafer is a labeled simulation

## Context
Phase 8.4 adds a page that shows how the model would have behaved on the line: the test period played back run by run, with alarms as they would have been raised. The director asked for a visual that engineers recognise, and SECOM has no die positions or wafer maps.

## Options considered
- Re-score each run live in the page with the saved model
- **Play back the run's own `risk_scores.csv` (scores and alarms from the alarm budget)** (chosen)
- A real wafer map: impossible, the data has no spatial information

## Decision
- **Nothing is re-scored.** The replay walks `risk_scores.csv` in time order; the alarms are the run's own alarm-budget alarms. The totals at the end therefore match Investigation & Report (reference run: 40 alarms, 5 of 24 failing runs caught, precision 12.5%).
- **Controls:** Play/Pause, Restart, Next run, End, four speeds (1 to 30 runs per second) and a position slider; running totals for runs, alarms (false alarms), failing runs caught (missed) and alarm precision.
- **Simulated 3D wafer** (`app/wafer.py`), labeled as a simulation wherever it appears:
  - reproducible from the run id;
  - scattered defects grow with the risk score; a failing run also gets one typical pattern (cluster, edge ring, scratch, center);
  - it feeds nothing back into the analysis, the crews or the reports.
- Investigation & Report gets a wafer card with a run picker (riskiest first).

## Consequences
- The page cannot disagree with the report: both read the same file.
- The wafer helps the story in a demo but carries no evidence; the label keeps that clear (the same rule as synthetic data, [[ADR-029 Synthetic scenarios change only the training period]]).
- E8 (replay plays and ends on 5 of 24) runs in CI only: the deployed apps need Google sign-in, which a test browser cannot do (#48).
