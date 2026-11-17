---
date: 2026-11-17
phase: 5
tags: [milestone, rag]
---
# Phase 5: RAG stretch

## Delivered
- Similar-run search: median impute, scaling and PCA (30 components) fitted on training runs; nearest training runs per test run; run map figure; "Similar past runs" report section
- Knowledge base: 12 cited background documents in `knowledge/` with `SOURCES.md`
- "Ask Foresight" chat over the selected run's artifacts and the knowledge base ([[ADR-018 RAG with local embeddings, hybrid retrieval and validated citations]])
- Investigation crew uses retrieved background passages and the computed similar-run line, with new checks ([[ADR-019 Deterministic knowledge retrieval and inserted computed facts for crews]])
- Features gate runs before the Data Analyst crew, so a stopped run spends no tokens
- Playwright E7 (chat); new reference run with its chat index

## Results
- Similar runs: failing test runs had 5.8% failing neighbours vs 4.7% for passing runs (training rate 6.8%) → weak evidence, reported as such
- Chat on real questions: 7/7 in-scope answered with valid citations, 3/3 out-of-scope refused; live on `main` in 9 s
- Reference run: 18/18 report checks PASS

## Test results
- 158 tests; CI E1–E7 green; deployed tests green on `dev` and `main`

## Links
- PRs: #20 vault · #21 Phase 5 · #22 watchdog · #23 warm-up · #24 release

## Issues found (lessons)
- Free agent search gave unstable passages and invented section citations → retrieve in code, check usage ([[ADR-019 Deterministic knowledge retrieval and inserted computed facts for crews]]).
- Citation rules that were too strict refused good answers (lists, a final citation line) → retuned on real chat logs.
- The first chat on `dev` hung with idle CPU after the model download; root cause not confirmed → watchdog, lock timeout, `TOKENIZERS_PARALLELISM=false`, warm-up at app start.
- Runs made before Phase 5 have no similar-run data, so the section silently disappears → an "older run" note in Phase 6.
- Ravid asked about a frontend/backend split → deferred with a seam in Phase 7 ([[ADR-020 Single service now, frontend-backend seam in Phase 7]]).

## Next
Phase 6: UX & visual design.
