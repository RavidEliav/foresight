---
date: 2026-11-17
status: accepted
tags: [decision, crews, rag]
---
# ADR-019 Deterministic knowledge retrieval and inserted computed facts for crews

## Context
The Investigation crew should use the knowledge base and the similar-run result. In real gpt-4o-mini runs, letting the agent search freely gave different passages each run, citations to sections that did not exist, and background claims placed under Facts. The similar-run line was sometimes dropped or given invented percentages.

## Options considered
- Let the agent call `search_knowledge` freely and trust the output
- **Retrieve passages in code and check how the crew uses them** (chosen)

## Decision
- Python retrieves the background passages from fixed queries (`BACKGROUND_QUERIES`) and passes them to the prompt as `{background_passages}`; the agent picks one and restates it.
- Checks: the citation names a real knowledge section, sits inside a numbered hypothesis, is not under Facts, and restates its passage (embedding similarity ≥ 0.45, a heuristic). The investigation must cite at least one.
- The similar-run result reaches the crews as one computed line (`similar_overall`). If the crew leaves it out of Facts, `ensure_similar_fact` inserts it; any percentage on a similar-run line other than the computed rates fails a check.
- A stage whose deterministic checks have an ERROR skips its crew (no tokens spent), and a crew whose output fails the checks is revised once.

## Consequences
- Same inputs give the same passages, so runs are comparable and checks are reproducible.
- The agent still writes the interpretation; code owns which evidence it sees and every number ([[ADR-005 Tools compute, agents interpret]]).
- The 0.45 faithfulness threshold is a heuristic and may need retuning if the knowledge base changes.
