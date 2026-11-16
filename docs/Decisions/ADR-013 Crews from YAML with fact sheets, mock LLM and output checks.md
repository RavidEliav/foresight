---
date: 2026-11-16
status: accepted
tags: [decision, crews, llm, testing]
---
# ADR-013 Crews from YAML with fact sheets, mock LLM and output checks

## Context
Four crews turn the deterministic results into insights, a model card, an investigation and an engineering report. LLM text can invent numbers, overstate confidence or claim causes, and tests and CI must never pay for LLM calls.

## Options considered
- Agents with tools only: agents pick their own facts and often skip important ones
- Prompts in Python code: hard to review and change
- Human review of every report: doesn't scale and can't run in CI
- **YAML crews + fact sheets + a mock LLM + deterministic checks with one self-revision**

## Decision
- Agents and tasks are defined in YAML (`src/foresight/crews/config/`). Each crew runs after the deterministic work of its stage.
- Every task receives **fact sheets** built from the run's JSON files, each fact tagged `[source: <file>]`, plus shared rules: only numbers from facts or tools, cite sources, label hypotheses, "is associated with" and never "causes".
- **Deterministic output checks** run on every crew output: required sections, sensor names exist, at least 90% of numbers traceable to the run files, every fact cites a source, and a **confidence rubric** ("high" needs a quoted q < 0.001).
- If a crew's own output fails a check, the crew gets the findings and **revises once** (`llm.crew_revisions`).
- A **MockLLM** drives the real CrewAI agents and tasks offline with deterministic drafts. Tests use it, and a session guard fails any test that would make a paid call.
- Token usage is read from the crew's own LLM instance (CrewAI's crew total counts a shared LLM once per agent).

## Consequences
- A real run costs about 22k tokens (under 1 cent with gpt-4o-mini) and about 3.5 minutes.
- Wording differs between real runs; the checks, not the wording, are the quality bar.
- The checks catch invented numbers and overstated confidence, but not every weak argument (for example a "high" rating whose stated second signal is wrong).
- Related: [[ADR-005 Tools compute, agents interpret]] · [[ADR-002 Four-crew merged Flow]]
