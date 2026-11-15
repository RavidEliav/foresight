---
date: 2026-11-15
status: accepted
tags: [decision, deployment]
---
# ADR-007 Railway Infrastructure as Code instead of railway.toml

## Context
Railway's Config as Code files (`railway.toml` / `railway.json`) are deprecated and stop being read on **2026-12-01**, before the Dec 4 submission. The project deploys one service to two environments (`main`, `dev`), each from the Git branch with the same name.

## Options considered
- Keep `railway.toml` and migrate later (risk: deploys break days before submission)
- Configure everything in the Railway dashboard (not reviewable, not in Git)
- Railway Infrastructure as Code in `.railway/railway.ts`

## Decision
Use Infrastructure as Code. One `.railway/railway.ts` file serves both environments: the GitHub branch follows `ctx.environment`. It defines the service, start command, health check (`/_stcore/health`) and non-secret variables. Secrets (`OPENAI_API_KEY`, `RUN_PASSCODE`) stay in Railway and are kept with `preserve()`; they're copied from the local `.env` with `scripts/push_secrets_to_railway.ps1`.

## Consequences
- Deployment config lives in Git and is reviewed in PRs like code.
- Config changes are applied per environment with `railway config plan` / `railway config apply`; a plan with no changes confirms there's no drift.
- Node.js is needed only for the `.railway/` folder (Railway IaC SDK).
- Related: [[ADR-003 Railway main and dev with same variables]]
