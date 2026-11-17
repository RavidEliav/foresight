---
date: 2026-11-16
status: accepted
tags: [decision, planning, ux]
---
# ADR-017 Phase order after Phase 4 and the design direction

## Context
Validating Phase 4 showed readability problems (UTC times, technical gate messages, long investigation text, cut-off labels). The app should look as advanced as it is. Final submission is Dec 4, presentation Dec 9.

## Options considered
- UX now, RAG later
- **RAG stretch first, then UX** (chosen by Ravid), then performance and new features
- Fold UX into the final phase

## Decision
| Phase | Content |
|---|---|
| 5 | RAG stretch: similar-run search, cited knowledge base, "Ask Foresight" chat; plus running the features gate before the Data Analyst crew |
| 6 | UX & visual design: local time, plain-language messages, concise investigation (structured crew summary + hypothesis cards), short run labels, interactive charts, futuristic look that gently resembles the semiconductor industry |
| 7 | Performance enhancement: faster, fewer limits, no loss of capability or accuracy (measured, with a regression test on the numbers) |
| 8 | Feature improvements and suggestions (modern, futuristic); proposed at the start of the phase |
| 9 | README, slides, demo video, release |
| 10 | Obsidian close-out after Dec 9 |

## Consequences
- Phase 9 deliverables must be ready by Dec 4; Phases 7–8 are time-boxed and become post-submission work if time runs short.
- Each phase is released on its own, so the app is always submittable.
