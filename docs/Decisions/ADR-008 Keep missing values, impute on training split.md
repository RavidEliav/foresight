---
date: 2026-11-15
status: accepted
tags: [decision, data]
---
# ADR-008 Keep missing values in clean data, impute on the training split only

## Context
After dropping features with more than 50% missing values and constant features, SECOM still has 1.56% missing cells across the 446 remaining features. The official brief asks for a `clean_data.csv`; the models need complete inputs.

## Options considered
- Impute in `clean_data.csv` (median of all runs): simple, but test-set values leak into the training data
- Drop runs with any missing value: loses most of the 104 failing runs
- Keep missing values in `clean_data.csv`; impute inside the model pipeline, fitted on the training split only

## Decision
Keep the missing values in `clean_data.csv`. Imputation (median) is a step of the scikit-learn pipeline, so it's fitted on the training data in every cross-validation fold and in the final fit.

## Consequences
- No leakage from test data into training; metrics stay honest.
- `clean_data.csv` reflects the real data quality; EDA reports missingness as-is.
- Every model in Phase 2 must start with an imputer (or handle NaN natively).
- Recorded in the Data Contract assumptions and the cleaning report.
- Related: [[ADR-009 Committed reference Data Contract]], [[ADR-010 Time-ordered 75-25 split]]
