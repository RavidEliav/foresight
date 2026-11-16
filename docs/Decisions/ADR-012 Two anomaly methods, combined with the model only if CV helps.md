---
date: 2026-11-16
status: accepted
tags: [decision, anomalies]
---
# ADR-012 Two anomaly methods, combined with the model only if CV helps

## Context
The model alone is weak on SECOM. Anomaly detection is a second, label-free signal. With ~446 sensors, IsolationForest dilutes problems that appear in only a few sensors.

## Options considered
- IsolationForest only: misses localized problems (a run extreme in 30 of ~575 sensors was not flagged in tests)
- Per-sensor SPC limits only: no single overall score
- **Both**, plus an optional combination with the model

## Decision
- **IsolationForest** (200 trees, fitted on training runs) gives one anomaly score per run; flag = above the 95% quantile of training scores.
- **SPC robust z-scores** per sensor (training median and MAD) count sensors out of limits (|z| > 3) and name the strongest signals.
- **Risk ranking:** percentile ranks of the model probability and the anomaly score are averaged within the batch being scored. It's used only if it beats the model alone in time-ordered CV on the training period.

## Consequences
- On the real data the combined ranking won in CV (PR-AUC 0.183 vs 0.159) and on the test period found 5 of 24 fails with 35 false alarms (12.5% precision, twice the base rate).
- Sensors that barely vary in training get huge z-scores for small changes; reports must treat those with caution.
- Related: [[ADR-011 Time CV model selection and alarm budget]]
