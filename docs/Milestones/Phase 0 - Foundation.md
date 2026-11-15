---
date: 2026-11-15
phase: 0
tags: [milestone]
---
# Phase 0: Foundation and deployment pipeline

## Delivered
- Public repo [RavidEliav/foresight](https://github.com/RavidEliav/foresight) with `main` + `dev`, PR template, MIT license
- Python 3.11 project: settings, logging, seeds, run manifest, mock-aware LLM factory
- CrewAI Flow skeleton: placeholder stages, 3 validation gates, graceful failure with `failure_report.md`
- Streamlit app shell: 5 pages, environment badge, passcode-protected "Run pipeline"
- CI (`ci.yml`) and post-deploy tests (`deployed-tests.yml`); smoke + Playwright E2E (E1, E4)
- Railway project `foresight`: environments `main` and `dev` via [[ADR-007 Railway IaC instead of railway.toml|IaC]], Wait for CI, secrets set
- Branch protection on `main` and `dev`
- Obsidian vault with ADR-001 to ADR-007

## Test results
- 19 unit, integration and AppTest tests passing
- Smoke + Playwright E2E: 4/4 on `dev` and on `main`
- All 4 test gates run automatically and pass (deployed tests: dev run 43724697702, main run 43725256529)

## Links
- `main`: https://foresight-app-main.up.railway.app
- `dev`: https://foresight-app-dev.up.railway.app
- PRs: #1 IaC · #2 CI on push · #3 deployed-tests fix · #4 secrets · #5 release to main

## Issues found (lessons)
- **Python 3.15 not supported by CrewAI** (needs <3.14) → project pinned to 3.11.
- **`railway.toml` deprecated** (stops working Dec 1) → moved to IaC ([[ADR-007 Railway IaC instead of railway.toml]]).
- **Merges didn't auto-deploy** until the Railway GitHub App was installed on the repo.
- **Post-deploy tests failed** because the shared `conftest.py` imported app code that the minimal test job doesn't install → fixtures that need the app now import it lazily.
- **Tests write run logs into the repo's `logs/` folder** (git-ignored) → to fix at the start of Phase 1.

## Next
Phase 1: SECOM data layer and Data Contract.
