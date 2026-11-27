---
tags: [home]
---
# Foresight: Project Home

Multi-agent semiconductor yield intelligence on SECOM. Author: Ravid Eliav.

## Status
- Phase 0: foundation and deployment pipeline (done, see [[Phase 0 - Foundation]])
- Phase 1: SECOM data layer and Data Contract (done, see [[Phase 1 - Data layer and Data Contract]])
- Phase 2 and 2.1: deterministic analytics (done, see [[Phase 2 - Deterministic analytics]])
- Phase 3: CrewAI crews (done, see [[Phase 3 - CrewAI crews]])
- Phase 4: full app: background runs, volume, upload, E2E (done, see [[Phase 4 - Full app]])
- Phase 5: RAG stretch: similar runs, knowledge base, "Ask Foresight" (done, see [[Phase 5 - RAG stretch]])
- Phase 6 and 6.1: UX & visual design, Continue run, chat on run data (done, see [[Phase 6 - UX and visual design]])
- Phase 7: performance: same numbers, 2.5 min runs, about half the memory (done, see [[Phase 7 - Performance]])
- Phase 8: feature improvements: run registry + Trends, All runs chat, Scenario Lab, Line Replay + 3D wafer, Stop/Resume, Google sign-in with roles, run files in Supabase, one screen per page and a phone view, the full report and every download as PDF, retrieval evaluation and prompt-injection guards, and a real app look (Home page, analyses with a number, plain names and sources) (done, all on `main` Nov 26, see [[Phase 8 - Feature improvements]])
- Next: Phase 9 README, slides (10 to 12), demo video (at most 5 min, on `main`) for Dec 4 · after the submission: voice, an MCP server, a light mode ([[ADR-017 Phase order after Phase 4 and the design direction]])
- Railway: Hobby plan since Nov 18 (8 GB memory per service)
- Supabase: `foresight-dev` and `foresight-main` (free, East US), one per Railway environment: registry, accounts, chat history and run files ([[ADR-033 Run files and chat history in Supabase, stubs on the volume]])
- Proposal submitted Nov 18; director's feedback Nov 19 (direction approved; synthetic data rule, see [[ADR-029 Synthetic scenarios change only the training period]])

## Links
- GitHub: https://github.com/RavidEliav/foresight
- Railway `main`: https://foresight-ai.up.railway.app
- Railway `dev`: https://foresight-app-dev.up.railway.app
- Supabase dev: https://supabase.com/dashboard/project/lfnfhwmrqijrdpzwbeqd · main: https://supabase.com/dashboard/project/qfzqtuzzfsorieczisjn
- Presentation: _pending_
- Demo video: _pending_

## Notes
- [[PROJECT_REQUIREMENTS|Requirements]] · [[PROJECT_PROPOSAL|Proposal]] · [[Technical reference]] (the detail moved out of the README in Phase 9)
- Decisions: [[ADR-001 SECOM as dataset]] · [[ADR-002 Four-crew merged Flow]] · [[ADR-003 Railway main and dev with same variables]] · [[ADR-004 Test gates and Playwright E2E]] · [[ADR-005 Tools compute, agents interpret]] · [[ADR-006 RAG and embeddings as stretch]] · [[ADR-007 Railway IaC instead of railway.toml]] · [[ADR-008 Keep missing values, impute on training split]] · [[ADR-009 Committed reference Data Contract]] · [[ADR-010 Time-ordered 75-25 split]] · [[ADR-011 Time CV model selection and alarm budget]] · [[ADR-012 Two anomaly methods, combined with the model only if CV helps]] · [[ADR-013 Crews from YAML with fact sheets, mock LLM and output checks]] · [[ADR-014 CrewAI tracing and telemetry off]] · [[ADR-015 Background runs with progress, heartbeat and guards]] · [[ADR-016 Uploads through the Data Contract, runs on a Railway volume]] · [[ADR-017 Phase order after Phase 4 and the design direction]] · [[ADR-018 RAG with local embeddings, hybrid retrieval and validated citations]] · [[ADR-019 Deterministic knowledge retrieval and inserted computed facts for crews]] · [[ADR-020 Single service now, frontend-backend seam in Phase 7]] · [[ADR-021 Headline-first pages in a cleanroom design system]] · [[ADR-022 Structured investigation summary and a causal-wording check]] · [[ADR-023 Resumable runs]] · [[ADR-024 The chat also indexes the run's tables]] · [[ADR-025 Measure first, then speed up without changing any result]] · [[ADR-026 Two Supabase projects, one Railway project with two environments]] · [[ADR-027 Run registry in Supabase Postgres, server-side only]] · [[ADR-028 Cross-run chat with pgvector and grounded summaries]] · [[ADR-029 Synthetic scenarios change only the training period]] · [[ADR-030 Line Replay replays stored scores; the wafer is a labeled simulation]] · [[ADR-031 Stop a run through a file in its folder, one exit path with the timeout guard]] · [[ADR-032 Google sign-in with emailed approval and two roles]] · [[ADR-033 Run files and chat history in Supabase, stubs on the volume]] · [[ADR-034 One screen per page with tabs inside cards and tables that wrap]] · [[ADR-035 Run pipeline replaces a running run only for other data]] · [[ADR-036 A run report PDF of every result page, built from the run's files]] · [[ADR-037 Prompt-injection guards on every chat answer]] · [[ADR-038 Runs are analyses with a number and plain names]]
- Milestones: [[Phase 0 - Foundation]] · [[Phase 1 - Data layer and Data Contract]] · [[Phase 2 - Deterministic analytics]] · [[Phase 3 - CrewAI crews]] · [[Phase 4 - Full app]] · [[Phase 5 - RAG stretch]] · [[Phase 6 - UX and visual design]] · [[Phase 7 - Performance]] · [[Phase 8 - Feature improvements]]

## Milestones
| Date | Milestone |
|---|---|
| Nov 18 | Proposal submission |
| Dec 4 | Final submission |
| Dec 9 | Presentation |
| After Dec 9 | Close-out backup |
