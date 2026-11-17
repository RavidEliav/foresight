---
date: 2026-11-17
status: accepted
tags: [decision, architecture, railway]
---
# ADR-020 Single service now, frontend-backend seam in Phase 7

## Context
Ravid asked whether `main` and `dev` should each be split into a frontend (Streamlit) and a backend (API + pipeline worker) service. The brief allows "Streamlit or Flask (or both)" and lists a Flask `/predict` endpoint as a stretch.

## Options considered
- Full split now, as its own phase before Phase 6
- **Keep one service; add a data-access seam in Phase 7; full split as an optional Phase 8 feature** (chosen by Ravid)
- Only a small `/predict` endpoint in Phase 8
- Drop the idea

## Decision
- One Railway service per environment stays for now.
- Phase 7 routes all app access to run data (artifacts, figures, progress, run list, chat index, starting runs) through one module (`RunStore`), with a local-filesystem implementation and no behaviour change.
- The split (`foresight-app` UI + `foresight-api` worker/API with private networking and a shared token) is a Phase 8 candidate, built only if Phases 6–7 finish with time to spare.

## Consequences
- No new failure modes, cost or test infrastructure before Dec 4.
- A Railway volume attaches to one service, so a later split must give `/app/runs` to the API (or move runs to a bucket); the seam keeps that change contained.
- Today a redeploy of the single service still stops a running pipeline.
