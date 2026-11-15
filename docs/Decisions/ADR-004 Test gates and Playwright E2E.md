---
date: 2026-11-15
status: accepted
tags: [decision]
---
# ADR-004 Test gates and Playwright E2E

## Context
Changes must be verified before they reach the demo app.

## Options considered
- Unit tests only
- Unit + smoke
- Full pyramid with Playwright E2E

## Decision
Four test gates: CI + local E2E on PRs to dev and main, smoke + E2E after each deploy, rollback on main failure.

## Consequences
Broken features are caught on dev. Deployed E2E tests are read-only to protect the LLM budget.
