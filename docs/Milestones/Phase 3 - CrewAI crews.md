---
date: 2026-11-16
phase: 3
tags: [milestone]
---
# Phase 3: CrewAI crews

## Delivered
- Four crews from YAML ([[ADR-013 Crews from YAML with fact sheets, mock LLM and output checks]]):
    - Data Analyst → `insights.md`
    - Data Scientist → `model_card.md`
    - Investigation → `investigation.md` (Facts / Assumptions / Hypotheses / Suggested verification)
    - Engineering Report → `engineering_report.md`
- Fact sheets, shared safety rules, deterministic output checks (`report_checks.json`), one self-revision
- MockLLM for offline tests; paid-call guard in the test session
- CrewAI tracing and telemetry off ([[ADR-014 CrewAI tracing and telemetry off]])
- App: insights, model card, investigation and report with a safety-checks banner; pages fall back to the committed reference run (`artifacts/reference/`)

## Results on the real data
- Reference run: all gates PASS, 15/15 report checks PASS
- Hypotheses follow the rubric: f_059, f_103 and f_247 rated high (q < 0.001 plus model importance); f_205 medium (q = 0.0027)
- Cost: about 22k tokens per run (under 1 cent), about 3.5 minutes; live run on `dev`: 157 s

## Test results
- 115 tests (crews with the mock LLM, checks, revision loop, usage accounting, app pages)
- Smoke + Playwright E2E pass locally, on `dev` and on `main`

## Links
- PRs: #14 vault · #15 Phase 3 · #16 release
- Live: https://foresight-app-main.up.railway.app/report

## Issues found (lessons)
- CrewAI tracing added about 15 s per crew → turned off.
- The first real report rated a hypothesis "high" on weak evidence → confidence rubric in the prompt and an automatic check.
- An AI code review found token usage counted once per agent (2–3× too high) → usage read from the LLM instance.
- The number check split "1,567" and skipped negative numbers → stricter parsing.
- Running git branch commands in parallel with file edits put a commit on the wrong branch → git steps always run one at a time.
- A Playwright error log printed the run passcode → passcode rotated; scripts hide secrets in error output.
- Railway secrets set with `--skip-deploys` only apply after a redeploy.

## Next
Phase 4: full app (background runs with progress and a timeout, a Railway volume for runs, dataset upload, Playwright E1–E6).
