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
- Phase 5: RAG stretch: similar runs, knowledge base, "Ask Foresight" (in progress)
- Next: 6 UX & visual design · 7 performance · 8 feature improvements · 9 README, slides, video · 10 close-out ([[ADR-017 Phase order after Phase 4 and the design direction]])
- Proposal submitted Nov 18, awaiting the professor's feedback

## Links
- GitHub: https://github.com/RavidEliav/foresight
- Railway `main`: https://foresight-app-main.up.railway.app
- Railway `dev`: https://foresight-app-dev.up.railway.app
- Presentation: _pending_
- Demo video: _pending_

## Notes
- [[PROJECT_REQUIREMENTS|Requirements]] · [[PROJECT_PROPOSAL|Proposal]]
- Decisions: [[ADR-001 SECOM as dataset]] · [[ADR-002 Four-crew merged Flow]] · [[ADR-003 Railway main and dev with same variables]] · [[ADR-004 Test gates and Playwright E2E]] · [[ADR-005 Tools compute, agents interpret]] · [[ADR-006 RAG and embeddings as stretch]] · [[ADR-007 Railway IaC instead of railway.toml]] · [[ADR-008 Keep missing values, impute on training split]] · [[ADR-009 Committed reference Data Contract]] · [[ADR-010 Time-ordered 75-25 split]] · [[ADR-011 Time CV model selection and alarm budget]] · [[ADR-012 Two anomaly methods, combined with the model only if CV helps]] · [[ADR-013 Crews from YAML with fact sheets, mock LLM and output checks]] · [[ADR-014 CrewAI tracing and telemetry off]] · [[ADR-015 Background runs with progress, heartbeat and guards]] · [[ADR-016 Uploads through the Data Contract, runs on a Railway volume]] · [[ADR-017 Phase order after Phase 4 and the design direction]]
- Milestones: [[Phase 0 - Foundation]] · [[Phase 1 - Data layer and Data Contract]] · [[Phase 2 - Deterministic analytics]] · [[Phase 3 - CrewAI crews]] · [[Phase 4 - Full app]]

## Milestones
| Date | Milestone |
|---|---|
| Nov 18 | Proposal submission |
| Dec 4 | Final submission |
| Dec 9 | Presentation |
| After Dec 9 | Close-out backup |
