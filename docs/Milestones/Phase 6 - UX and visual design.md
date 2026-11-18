---
date: 2026-11-18
phase: 6
tags: [milestone, ux]
---
# Phase 6: UX & visual design (with 6.1 polish)

## Delivered
- Phase 6: cleanroom design system, headline-first pages, Extended data tabs, Plotly charts, plain-language failures, local time, short sidebar labels, older-run notes ([[ADR-021 Headline-first pages in a cleanroom design system]])
- Structured investigation summary (key findings, hypothesis cards) with checks, and a causal-wording check ([[ADR-022 Structured investigation summary and a causal-wording check]])
- Phase 6.1 (Ravid's review): animated stage tiles, Continue run ([[ADR-023 Resumable runs]]), equal-height rows, interactive missing data and correlation, side-by-side tables, sidebar wordmark and menu, recent chat questions, logo avatar
- Chat answers about the run's tables ([[ADR-024 The chat also indexes the run's tables]])
- New reference run: all gates PASS, 26/26 report checks, no revisions

## Results
- Validated by Ravid on `dev`; released to `main` (#30), deployed tests green on both
- Chat on the reference run: 10/10 in-scope answered with citations, 3/3 refused

## Test results
- 198 tests; smoke + E2E E1–E7 green locally and in CI

## Links
- PRs: #25 vault · #26 Phase 6 · #27 E2E fix · #28 Phase 6.1 · #29 chat on run data · #30 release

## Issues found (lessons)
- **Memory:** a run on `dev` was killed in its 4th stage; the service had a 1 GB limit and peaked at 1,009 MB (app + chat model + run process). Ravid moved Railway to the Hobby plan (8 GB). Memory is measured and reduced in Phase 7.
- The chat could not answer about table rows (run 1456) → `run_data.md`.
- Chat errors were not logged, so a failed question could not be traced → now logged.
- The first real summary said "may be a contributing factor" and cited maintenance records the data does not have → causal-wording check and stricter prompts.
- PowerShell 5 here-strings piped to Python mangle non-ASCII characters ("·", "≥"), and `Set-Content -Encoding utf8` adds a BOM → edit scripts are written as UTF-8 files first.
- `st.html` drops inline SVG → drawings as SVG data URIs.
- The deployed E3 assumed the newest run was the reference run → E2/E3 select it explicitly.
- The code review found the checksum warning treated as expected for built-in data, duplicate card keys and a Continue note that promised reuse the Flow would not do.

## Next
Phase 7: performance (memory first, then speed and the data-access seam).
