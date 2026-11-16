---
date: 2026-11-16
status: accepted
tags: [decision, data, deployment]
---
# ADR-016 Uploads through the Data Contract, runs on a Railway volume

## Context
Users can analyze their own CSV. A smaller or newer batch would get different cleaning decisions (other features constant or sparse) and could not be compared with the reference. Runs written to the container filesystem were lost on every redeploy (D6).

## Options considered
- Clean each upload on its own: results not comparable with the reference
- **Clean uploads with the committed Data Contract's feature list**, then validate like the built-in data
- Store runs in Supabase: an extra service; **a Railway volume** is enough for files

## Decision
- Upload format: `timestamp`, `label` (-1/1) and the 590 sensors in SECOM order; a template is downloadable. Uploads keep exactly the contract's features and go through the same raw checks and contract gate; a broken file stops at the gate with the failed checks listed.
- A Railway volume `foresight-runs` (500 MB, one per environment) is mounted at `/app/runs`, defined in `.railway/railway.ts`. Size and region are pinned in the IaC file because Railway fills in defaults that otherwise show up as drift.

## Consequences
- Uploads always warn on `data_checksums` (they are not the original files); to be shown as info in the UX phase.
- Runs survive redeploys (verified on `dev`).
- Related: [[ADR-009 Committed reference Data Contract]] · [[ADR-015 Background runs with progress, heartbeat and guards]]
