---
date: 2026-11-16
phase: 2
tags: [milestone]
---
# Phase 2 and 2.1: Deterministic analytics

## Delivered
- EDA: monthly/weekly fail rates, missingness, Mann-Whitney U per sensor with Benjamini-Hochberg q-values, 4 charts, `eda_report.html`
- Features: time-ordered 75/25 split ([[ADR-010 Time-ordered 75-25 split]]), near-duplicate sensors dropped on train, `missing_count`; features gate
- Models: 4 candidates + baseline, time-CV selection, alarm-budget operating point ([[ADR-011 Time CV model selection and alarm budget]]), bootstrap CIs, permutation importance, `model.joblib`, `evaluation_report.md`
- Anomalies and risk ranking ([[ADR-012 Two anomaly methods, combined with the model only if CV helps]])
- 7 read-only CrewAI tools returning compact, source-tagged JSON
- App pages: EDA & Insights, Model, Investigation (anomalies + risk ranking)
- Stage exceptions now fail gracefully with a failure report

## Results on the real data
- 20 sensors differ between failing and passing runs (q < 0.05), led by f_059
- Selected model `rf_regularized`, test PR-AUC 0.085 (random 0.061)
- Fixed F2 threshold: 0 of 24 test fails (stops firing under drift)
- Recommended ranking (model + anomaly score) at a 10% alarm budget: 5 of 24 fails, 35 false alarms, 12.5% precision
- Full run: about 80 s locally, 50 s on Railway; identical numbers on both

## Test results
- 90 tests (unit, data, analytics, integration, AppTest); fast settings via `FORESIGHT_CONFIG`
- Smoke + Playwright E2E pass locally, on `dev` and on `main`

## Links
- PRs: #9 vault · #10 Phase 2 · #11 release · #12 Phase 2.1 · #13 release
- Live: https://foresight-app-main.up.railway.app/model

## Issues found (lessons)
- scikit-learn 1.8 deprecated `penalty="l1"` → use `l1_ratio=1.0`.
- IsolationForest misses problems confined to a few of ~446 sensors → kept SPC z-scores as well.
- A fixed threshold silently stopped firing under drift → alarm budget.
- Permutation importance on a random forest was slow → 20 sensors × 5 repeats.
- Tests were slow when every tool/page test rebuilt the pipeline → module-scoped shared runs.

## Next
Phase 3: CrewAI crews that interpret these results.
