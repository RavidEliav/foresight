---
date: 2026-11-15
phase: 1
tags: [milestone]
---
# Phase 1: SECOM data layer and Data Contract

## Delivered
- SECOM download from UCI with SHA-256 checksums; offline switch for tests
- Raw loader and raw checks (590 numeric features, labels, timestamps, row count)
- Deterministic cleaning: 28 features dropped (>50% missing), 116 dropped (constant), 446 kept; labels mapped to 0/1; sorted by time; missing values kept ([[ADR-008 Keep missing values, impute on training split]])
- Committed reference contract `config/dataset_contract.json` and 11 clean-vs-contract checks ([[ADR-009 Committed reference Data Contract]])
- Flow `ingest` stage and a real data-contract gate; failure report on ERROR
- Data Quality page in the app

## Results on the real data
- 16/16 checks PASS: 1,567 runs, 446 of 590 features, 6.6% fail rate, 1.56% missing cells
- Same result on Railway `dev` (live run downloads SECOM)

## Test results
- 52 tests (unit, data, integration, AppTest) on synthetic SECOM, offline
- Smoke + Playwright E2E: 4/4 locally, on `dev` and on `main`

## Links
- PRs: #6 vault (Phase 0) · #7 Phase 1 · #8 release to `main`
- Live page: https://foresight-app-main.up.railway.app/data-quality

## Issues found (lessons)
- Run status box collapsed when finished and hid the follow-up link → results and link moved outside it.
- Windows PowerShell `Set-Content -Encoding utf8` adds a BOM → write project files with Python or `[IO.File]` without BOM.
- Fail rate drifts strongly by month → drove the split decision ([[ADR-010 Time-ordered 75-25 split]]).

## Next
Phase 2: deterministic analytics (EDA, features, models, anomalies) as CrewAI tools.
