---
date: 2026-11-15
status: accepted
tags: [decision, data, validation]
---
# ADR-009 Committed reference Data Contract

## Context
The official brief requires a `dataset_contract.json` and a Flow step that confirms the contract matches the cleaned dataset. A contract rebuilt from each run's own data would always match, so the check would prove nothing.

## Options considered
- Build the contract from every run's data (check always passes)
- Hand-write the contract
- Generate it once from the real data with a script, review it, and commit it; validate every run against it

## Decision
`scripts/build_contract.py` generates `config/dataset_contract.json` from the real SECOM data (446 required features, observed value ranges, label mapping, file checksums). It's committed and reviewed like code. Every run validates its cleaned data against it.

- **ERROR** (stops the run): missing required columns, non-numeric features, invalid labels, missing timestamps, duplicate run ids, too few rows; raw files with the wrong shape, labels or timestamps.
- **WARNING** (reported, run continues): unexpected columns, features above 50% missing, values outside the reference ranges (possible drift), fail rate outside 2–20%, raw files that differ from the contract checksums.

If no contract exists, the run builds one and reports a `contract_bootstrap` WARNING.

## Consequences
- The contract gate catches real problems (shown by tests that break the data on purpose).
- Changing the cleaning rules means rebuilding and re-committing the contract.
- Range checks are warnings, so new data with drift is flagged but not rejected.
- Related: [[ADR-008 Keep missing values, impute on training split]]
