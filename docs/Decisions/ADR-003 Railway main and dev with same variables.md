---
date: 2026-11-15
status: accepted
tags: [decision]
---
# ADR-003 Railway main and dev with same variables

## Context
Need a stable demo app and a place to test features before release.

## Options considered
- Single environment
- main + dev with separate variables
- main + dev with the same variables

## Decision
Railway project with `main` and `dev` environments, each auto-deployed from the matching branch, with identical variables.

## Consequences
dev is a true pre-release copy of main. Both share one LLM key and budget, so automated tests never call the LLM.
