---
date: 2026-11-15
status: accepted
tags: [decision]
---
# ADR-001 SECOM as dataset

## Context
Two candidate datasets: SECOM (tabular sensor data, pass/fail label) and WM-811K (wafer-map images).

## Options considered
- SECOM: fits pandas/scikit-learn and the Data Scientist crew directly
- WM-811K: needs computer vision, too heavy for the timeline

## Decision
SECOM (UCI) is the primary dataset; WM-811K is a future extension only.

## Consequences
Heavy class imbalance (~6.6% fail) drives the metric choice (PR-AUC, fail recall). Anonymized features limit physical interpretation. Pending the professor's feedback on the proposal.
