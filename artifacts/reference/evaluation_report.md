# Evaluation report

## Setup
- **Split:** time-ordered. Train: 1175 runs (80 fails).
  Test: 392 runs (24 fails), from 2008-09-29 11:53:00.
- **Model selection:** highest mean PR-AUC in time-ordered CV on the training split.
- **Selected model:** `rf_regularized`
- **Operating point:** alarm budget: flag the riskiest 10% of the runs scored (40 alarms in the test period).
- **Fixed threshold (for comparison):** 0.2472 (maximizes F2 (recall weighted 2x) on out-of-fold CV predictions).

## Model comparison (PR-AUC; random guessing = fail rate)
| Model | Time CV (train) | Stratified CV (optimistic) | Test PR-AUC | Test ROC-AUC | Description |
|---|---|---|---|---|---|
| logreg_l1 | 0.130 ± 0.089 | 0.177 | 0.093 | 0.566 | L1 logistic regression (balanced classes, sparse and interpretable) |
| random_forest | 0.116 ± 0.067 | 0.202 | 0.069 | 0.520 | Random forest on all features (balanced subsamples) |
| rf_regularized | 0.159 ± 0.061 | 0.194 | 0.085 | 0.583 | Regularized random forest (min 10 runs per leaf, 10% of features per split) |
| rf_select_k | 0.111 ± 0.061 | 0.199 | 0.071 | 0.530 | Random forest on the top 40 features (ANOVA F-test, chosen inside each training fold) |
| baseline_always_pass | 0.052 ± 0.040 | n/a | 0.061 | 0.500 | Always predicts pass (reference) |

Random-guessing PR-AUC on the test period: **0.061**.

## Selected model on the test period
| Metric | Alarm budget | 95% bootstrap CI | Fixed threshold |
|---|---|---|---|
| pr_auc | 0.085 | 0.054 – 0.151 | 0.085 |
| roc_auc | 0.583 | 0.460 – 0.708 | 0.583 |
| recall_fail | 0.125 | 0.000 – 0.313 | 0.000 |
| precision_fail | 0.075 | 0.000 – 0.175 | 0.000 |
| f1_fail | 0.094 | 0.000 – 0.227 | 0.000 |
| balanced_accuracy | 0.512 | 0.446 – 0.610 | 0.496 |

With the alarm budget: 3 failing runs caught, 21 missed, 37 false
alarms, 331 passing runs correctly passed.

In time-ordered CV on the training split, the alarm budget found
0.315 of failing runs per fold on average (precision
0.130); the fixed threshold found 0.446
(precision 0.096, optimistic because it was tuned on the same
predictions).

## Most important sensors (permutation importance on the test period)
| Sensor | Drop in PR-AUC when shuffled |
|---|---|
| f_103 | 0.0128 ± 0.0013 |
| f_205 | 0.0067 ± 0.0029 |
| f_460 | 0.0052 ± 0.0032 |
| f_130 | 0.0030 ± 0.0022 |
| f_153 | 0.0023 ± 0.0016 |
| f_033 | 0.0023 ± 0.0031 |
| f_468 | 0.0019 ± 0.0019 |
| f_028 | 0.0018 ± 0.0018 |
| f_129 | 0.0017 ± 0.0024 |
| f_290 | 0.0010 ± 0.0015 |
| f_021 | 0.0006 ± 0.0017 |
| f_079 | 0.0006 ± 0.0011 |
| f_377 | 0.0002 ± 0.0017 |
| f_064 | 0.0002 ± 0.0051 |
| f_065 | 0.0001 ± 0.0015 |

## Caveats
- The test period has only 24 failing runs, so the confidence intervals
  are wide.
- The fail rate drifts over time (see the risk-over-time chart). A fixed probability threshold
  tuned on older runs may stop firing; the alarm budget keeps the number of alarms stable.
  Retraining on recent runs at a regular interval is recommended.
- Stratified CV mixes future runs into training and is shown only as an optimistic reference.
- Sensor names are anonymized; important sensors point to where to look, not to a cause.
