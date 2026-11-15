---
date: 2026-11-15
status: accepted
tags: [decision, modeling]
---
# ADR-010 Time-ordered 75-25 split

## Context
SECOM runs are ordered in time (Jul 19 – Oct 17, 2008) and the fail rate drifts by month: July 22%, August 9%, September 3%, October 6%. Only 104 of 1,567 runs fail.

## Options considered
| Split | Train fails | Test fails | Notes |
|---|---|---|---|
| Time 60/40 | 76 (8.1%) | 28 (4.5%) | biggest train/test gap |
| Time 70/30 | 78 (7.1%) | 26 (5.5%) | |
| **Time 75/25** | **80 (6.8%)** | **24 (6.1%)** | closest fail rates |
| Time 80/20 | 87 (6.9%) | 17 (5.4%) | too few test fails |
| Stratified random 80/20 | ~83 | ~21 | mixes future into training, optimistic |

## Decision
- Hold out the **last 25% of runs** (392 runs, 24 fails, from Sep 29) as the test set, used once for final scores.
- Choose the model and decision threshold with **time-ordered cross-validation** (`TimeSeriesSplit`, 5 folds) inside the training data.
- Fit imputation and scaling on training data only ([[ADR-008 Keep missing values, impute on training split]]).
- Report **bootstrap 95% confidence intervals** on the test metrics.
- Report stratified random 5-fold CV as a clearly labeled, optimistic comparison.

## Consequences
- Scores reflect real use: predicting future runs from past ones, under drift.
- 24 test fails make single numbers noisy; confidence intervals show the uncertainty.
- Expect lower scores than a random split would give; the report explains why.
