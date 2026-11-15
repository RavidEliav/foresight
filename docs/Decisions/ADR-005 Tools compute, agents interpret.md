---
date: 2026-11-15
status: accepted
tags: [decision]
---
# ADR-005 Tools compute, agents interpret

## Context
LLMs can invent numbers, cost tokens on raw data, and are non-deterministic.

## Options considered
- Agents analyze raw data
- Tools compute, agents interpret

## Decision
All numbers come from deterministic Python tools; LLM agents interpret computed summaries.

## Consequences
Reproducible, cheaper, traceable reports. Facts / Assumptions / Hypotheses are always labeled.
