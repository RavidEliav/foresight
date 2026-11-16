---
date: 2026-11-16
status: accepted
tags: [decision, modeling]
---
# ADR-011 Model selection by time-ordered CV, alarm-budget operating point

## Context
SECOM drifts over time (monthly fail rate 22% → 9% → 3% → 6%). In Phase 2 the decision threshold was tuned for F2 on out-of-fold predictions of the training period. In Phase 2.1 the same rule applied to the newly selected model raised **no alarms at all** in the test period: its scores shifted below a threshold tuned on older runs.

## Options considered
- Fixed probability threshold (F2-tuned on older runs): silently stops firing under drift
- Recalibrate the threshold on recent labeled runs: needs labels that arrive late
- **Alarm budget:** flag the riskiest N% of the runs being scored

## Decision
- Choose the model by mean PR-AUC in time-ordered CV on the training split only. Candidates: L1 logistic regression, random forest, regularized random forest, forest on the top-40 sensors, always-pass baseline. The regularized forest won (0.159 ± 0.061).
- The operating point is an **alarm budget of 10%**. The F2 threshold is still reported for comparison.
- The test period is scored once; every choice is made before that.

## Consequences
- The number of alarms is predictable for engineers (40 of 392 test runs).
- Recall at the budget is reported with bootstrap CIs; with 24 test fails they are wide.
- Model scores still drift; the report recommends retraining on recent runs at a regular interval.
- Related: [[ADR-010 Time-ordered 75-25 split]], [[ADR-012 Two anomaly methods, combined with the model only if CV helps]]
