---
date: 2026-11-16
status: accepted
tags: [decision, crews, performance]
---
# ADR-014 CrewAI tracing and telemetry off

## Context
CrewAI's optional cloud tracing waited on timeouts (about 5 s per task, about 15 s per crew) and printed banners, even without a CrewAI account.

## Options considered
- Keep tracing: about a minute slower per run, plus noisy logs
- **Turn tracing and telemetry off** and rely on Foresight's own logs and run manifest

## Decision
`CREWAI_TRACING_ENABLED=false`, `CREWAI_DISABLE_TELEMETRY=true` and `OTEL_SDK_DISABLED=true` are set as defaults in code (`crews/runner.py`), in `.env.example` and in the Railway IaC. Crews are built with `tracing=False`.

## Consequences
- About 15 s saved per crew.
- Observability comes from the run log, `run_manifest.json` (stage durations, crew tokens and seconds) and Railway deploy logs.
- Related: [[ADR-013 Crews from YAML with fact sheets, mock LLM and output checks]]
