---
date: 2026-11-18
phase: 7
tags: [milestone, performance]
---
# Phase 7: Performance

## Delivered
- Measurement tools: `measure_run`, `measure_app`, and `compare_runs` (0 differences from the reference run) ([[ADR-025 Measure first, then speed up without changing any result]])
- Lower memory: batched embeddings, an app without the pipeline imports, the chat on the OpenAI SDK, a NumPy precision-recall curve
- Faster runs: background Data Analyst and Data Scientist crews with input snapshots, NumPy bootstrap, parallel permutation importance
- Data-access seam `app/store.py` with a guard test ([[ADR-020 Single service now, frontend-backend seam in Phase 7]])
- Validation fixes (#33):
  - stage tiles agree with their crew line while a crew runs in the background
  - scroll to zoom on every chart
  - the precision-recall chart fits its precision axis to the data

## Results
| | Before | After |
|---|---|---|
| Real run on Railway | 3.3–3.6 min | 2.5 min (about 25,500 tokens, 26/26 report checks PASS) |
| Run peak memory | 973 MB | 640 MB |
| App server | 521 MB | 323 MB |
| `dev` service at rest after a run | 1,239 MB | 445 MB |

## Test results
- 210 tests, ruff clean
- Smoke + E2E green on `dev` and `main`
- A real local run with every tile recorded every 2 s showed 0 tile/crew mismatches

## Links
- PRs: #32 Phase 7 · #33 validation fixes · release to `main`

## Issues found (lessons)
- **Name clash:** the Flow field `resume` shadowed CrewAI's `Flow.resume()`, so Continue silently did nothing until it was renamed to `continue_run`. Check the base class before naming fields in a subclass.
- **Windows:** `os.replace` fails while another process reads the file, so the progress writer retries.
- **ONNX Runtime memory:** it keeps memory for the largest batch it has seen. One batch of 100 chunks cost about 430 MB.
- **Imports cost memory:** importing the Flow in the app pulled in CrewAI and scikit-learn (about 270 MB) just to make a run id.
- **Background work:** it changes what "done" means. A stage marked done while its crew still worked showed a green tile next to "working", and Ravid caught it during validation.
- **Flaky E5:** the "Technical details" expander sometimes missed the first click, so the test retries the click.
- **Code review findings:**
  - a background crew's result must be recorded in one step
  - crew tools must see a frozen file list
  - stage records must merge instead of overwrite

## Next
Phase 8: feature improvements (menu from the course materials, the BanAI project and the Supabase options).
