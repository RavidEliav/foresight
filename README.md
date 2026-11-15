# Foresight

**Multi-agent semiconductor yield intelligence on SECOM.** A CrewAI Flow that validates fab sensor data, describes what happened, predicts which production runs will fail, investigates abnormal behavior, and writes a short, evidence-based engineering report.

Author: **Ravid Eliav** · AI Developers Course, Final Project

> **Status:** Phase 0 (foundation). The Flow stages are placeholders; the data layer, analytics and crews are added in the next phases.

| Environment | Branch | URL |
|---|---|---|
| `main` (stable) | `main` | _set after the first deploy_ |
| `dev` (testing) | `dev` | _set after the first deploy_ |

## Architecture

```
SECOM -> [Data Contract gate] -> Data Analyst Crew -> Data Scientist Crew -> [Features gate]
      -> Investigation Crew -> [Evidence gate] -> Engineering Report Crew -> engineering_report.md
```

Python tools compute every number; LLM agents interpret the results. Any ERROR at a gate stops the run and writes `failure_report.md`.

## Quick start

Requires **Python 3.11** (CrewAI supports 3.10–3.13).

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env          # then fill in OPENAI_API_KEY and RUN_PASSCODE
streamlit run app/streamlit_app.py
```

Set `MOCK_LLM=true` in `.env` to work without any LLM calls.

## Tests

| Layer | Command |
|---|---|
| Unit, integration, Streamlit AppTest | `pytest` |
| Smoke + Playwright E2E (app must be running) | `python -m playwright install chromium` then `pytest tests/smoke tests/e2e` |

`BASE_URL` points the smoke and E2E tests at another app (default `http://localhost:8501`).

## Release workflow

`feature/*` → PR into `dev` (CI + local E2E) → auto-deploy to Railway `dev` (smoke + E2E) → PR `dev → main` (CI + E2E) → auto-deploy to `main` (smoke + E2E, rollback on failure).

- `.github/workflows/ci.yml`: PR gates
- `.github/workflows/deployed-tests.yml`: post-deploy gates (needs repository variables `DEV_URL` and `MAIN_URL`)

## Deployment (Railway)

One project `foresight`, service `foresight-app`, environments `main` and `dev` with identical variables (`OPENAI_API_KEY`, `LLM_MODEL`, `RUN_PASSCODE`). Build and start are defined in [`railway.toml`](railway.toml); Railway's Railpack builder reads `.python-version` and `requirements.txt`.

## Project structure

```
app/            Streamlit app (entry point: app/streamlit_app.py)
config/         settings.yaml (seed, LLM model, paths)
src/foresight/  flow.py, crews/, tools/, validation/, utils/
tests/          unit/, integration/, app/, smoke/, e2e/
scripts/        data download and helper scripts
data/           raw/ and processed/ (not committed)
artifacts/      committed reference run
docs/           Obsidian vault: requirements, decisions, results, lessons learned
```

## License

MIT, see [LICENSE](LICENSE).
