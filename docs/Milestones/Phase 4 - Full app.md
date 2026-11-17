---
date: 2026-11-16
phase: 4
tags: [milestone]
---
# Phase 4: Full app

## Delivered
- Background runs with live progress, heartbeat, timeout guard, run limits and retention ([[ADR-015 Background runs with progress, heartbeat and guards]])
- CSV upload through the Data Contract, with a template; Railway volume for runs ([[ADR-016 Uploads through the Data Contract, runs on a Railway volume]])
- Run Pipeline page: dataset choice, live stages and crews, failed data checks, run history
- Sidebar run selector; colour-labelled investigation; failing-run count, sensors out of limits, exact risk-ranking counts
- Confidence rubric: "high" needs q < 0.001 and a named second signal
- Playwright E1–E6 (E5/E6 in CI with the mock LLM; deployed suite read-only)

## Results
- Live on `dev`: real background run in 201 s, all gates PASS, 15/15 report checks; survived a page refresh and a redeploy
- Validation by Ravid: broken uploads stop at the right gate; a valid 1,200-run upload succeeds with the expected contract WARNING

## Test results
- 134 tests; 8 smoke/E2E locally; CI E1–E6 green; deployed E1–E4 green on `dev` and `main`

## Links
- PRs: #17 vault · #18 Phase 4 · #19 release

## Issues found (lessons)
- The reference run was made on Windows, so its chart paths had backslashes and charts were missing on Linux/Railway → paths written in POSIX form and read with either separator.
- Railway fills in volume defaults (size, region) that the IaC file must pin, or every plan shows drift.
- pandas 3 refuses to write timestamps of another precision or time zone into an existing column → parse formats separately and combine.
- The AI code review found a finished run vanishing after a refresh and E5/E6 able to start paid runs on a deployed app.
- Deleting and recreating a file in parallel tool calls raced → file operations on one path run one at a time.
- Validation feedback (UTC times, technical messages, long investigation text, cut-off labels) → a dedicated UX phase ([[ADR-017 Phase order after Phase 4 and the design direction]]).
- A run stopped at the features gate still paid for the Data Analyst crew (4,657 tokens) → gate before crew in Phase 5.

## Next
Phase 5: RAG stretch (similar-run search, knowledge base, "Ask Foresight").
