---
date: 2026-11-18
status: accepted
tags: [decision, crews]
---
# ADR-022 Structured investigation summary and a causal-wording check

## Context
The investigation page was too long to read. A short summary written in the app (or by a second LLM call outside the crew) would not be checked like the other outputs. The first real run with a summary also showed two honesty problems that the existing checks missed: "may be a contributing factor" and evidence about maintenance records that the data does not have.

## Options considered
- Summarize in the app with fixed rules
- A separate LLM call for the summary
- **A fourth task of the Investigation crew writing `investigation_summary.json`, checked deterministically** (chosen)

## Decision
- The crew writes a JSON summary: a headline, 3 key findings with their source file, one card per hypothesis (title, confidence, evidence, how to verify). A pydantic schema sets length limits; the runner extracts the JSON from the answer.
- Checks: valid schema; one card per numbered hypothesis with the same confidence level; key findings cite files of the run and no background; known sensors; traceable numbers.
- New check on hypotheses (investigation, report) and the summary: no causal wording ("contributes to", "contributing factor", "causes", "caused by", "leads to", "drives"); negations ("not proven causes", "rather than causes"), nouns ("leads to verify") and Background sentences are allowed.
- Prompts: evidence only from this run's facts (no maintenance or equipment records); the headline says "associations" and calls the model's evidence modest.

## Consequences
- The app shows key findings and hypothesis cards; a summary that fails its format check is reported as such, not as an older run.
- The reference run passes 26/26 checks with no revisions.
- A failed check makes the crew revise once, which costs tokens; false positives were removed after the code review.
