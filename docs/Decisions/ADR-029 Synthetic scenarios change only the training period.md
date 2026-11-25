---
date: 2026-11-19
status: accepted
tags: [decision, data, evaluation]
---
# ADR-029 Synthetic scenarios change only the training period

## Context
Ravid wanted more data to get different results and reports. No public semiconductor dataset like SECOM (sensors, pass/fail, time) can be downloaded by a server without a login. The director's comment on the proposal: synthetic data must be **explicitly labeled and kept separate**, and all evaluation metrics, PR-AUC in particular, must be computed **only on the original SECOM data**.

## Options considered
- A second public dataset (APS Scania, Tennessee Eastman): not semiconductor data, each needs its own Data Contract
- **A: scenarios change only the training period; the test period stays the original SECOM runs** (chosen by Ravid)
- B: scenario runs show no model metrics at all

## Decision
- **Four reproducible kinds** (seeded, one random generator per step):
  - **planted fault:** a known cause
  - **sensor drift**
  - **sensor outage**
  - **noisy line**

  Target sensors are well-measured sensors that do not already separate failing from passing runs.
- **Training period only:** the generator finds the training runs exactly as the pipeline does (cleaning, then the time split).
- **Enforced in ingest:** the Data Contract check `test_period_is_original_secom` cleans the original data too and stops the run if any test-period value differs.
- **Labeled and separate:**
  - `scenario.json` (recipe and ground truth) and `scenario_data.csv` sit in the run folder; the SECOM files are never modified
  - the dataset label "Scenario (synthetic): …" and a SYNTHETIC badge on every result page
  - the manifest's `scenario`, a deterministic SYNTHETIC note opening the engineering report, and the Trends source "Synthetic"
- **Ground truth:** `scenario_check.json` (EDA rank, model rank on the real test period, named in the reports) and the report check `scenario_ground_truth`.

## Consequences
- Every metric of a scenario run is comparable with a run on the real data (same 392 test runs, 24 fails).
- Real SECOM, default settings (reference PR-AUC 0.085):

  | Scenario | Found by the analysis | PR-AUC on the real test period |
  |---|---|---|
  | Planted fault | EDA rank 1 | 0.079 |
  | Drift | 2 of 5 sensors | 0.077 |
  | Outage | 1 named | 0.083 |
  | Noise | none (as expected) | 0.123 |

  With 24 real failing test runs the intervals are wide.
- A scenario tests the pipeline (does it find a known cause?) and the model's robustness; it does not create new real evidence.
