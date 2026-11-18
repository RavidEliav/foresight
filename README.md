# Foresight

**Multi-agent semiconductor yield intelligence on SECOM.** A CrewAI Flow that validates fab sensor data, describes what happened, predicts which production runs will fail, investigates abnormal behavior, and writes a short, evidence-based engineering report.

Author: **Ravid Eliav** · AI Developers Course, Final Project

> **Status:** Phase 5 (RAG stretch) done: similar-run search, a cited knowledge base for the Investigation crew, and the "Ask Foresight" chat that answers only from a run's reports. Next: Phase 6 (UX and visual design).

| Environment | Branch | URL |
|---|---|---|
| `main` (stable) | `main` | https://foresight-app-main.up.railway.app |
| `dev` (testing) | `dev` | https://foresight-app-dev.up.railway.app |

## Architecture

```
SECOM -> ingest -> [Data Contract gate] -> analyze + Data Analyst Crew -> [Features gate]
      -> model + Data Scientist Crew -> investigate + Investigation Crew -> [Evidence gate]
      -> Engineering Report Crew -> output checks -> engineering_report.md
```

Python tools compute every number; LLM agents interpret the results. Any ERROR at a gate stops the run and writes `failure_report.md`.

## Data

**SECOM** (UCI Machine Learning Repository, [dataset 179](https://archive.ics.uci.edu/dataset/179/secom)): 1,567 production runs × 590 anonymized sensor features, a pass/fail label (`-1`/`1`, about 6.6% fail) and a timestamp per run. License: CC BY 4.0.

```powershell
python scripts/download_data.py     # downloads into data/raw (not committed) and prints SHA-256
python scripts/build_contract.py    # rebuilds config/dataset_contract.json from the real data
```

The pipeline downloads the data automatically on first use (set `FORESIGHT_OFFLINE=true` to forbid downloads). Every run:

1. validates the raw files (590 numeric features, labels `-1`/`1`, parseable timestamps, enough rows),
2. cleans them: drops features with more than 50% missing values (28) and constant features (116), maps labels to `0` pass / `1` fail, sorts by time, and **keeps** the remaining missing values (imputation is fitted on the training split in the model pipeline),
3. validates the cleaned data against the committed **Data Contract** (`config/dataset_contract.json`): required columns, types, label values, unique ids, row count are ERROR checks; unexpected columns, missing ratios, value ranges (drift), fail rate and data checksums are WARNING checks.

Run outputs: `clean_data.csv`, `cleaning_report.json`, `data_profile.json`, `dataset_contract.json`, `validation_summary.json`, `run_manifest.json`. An ERROR stops the run and writes `failure_report.md`.

## Analytics

All numbers are computed by deterministic Python; the crews only interpret them, through read-only tools in `src/foresight/tools/run_tools.py`.

| Stage | What it does | Outputs |
|---|---|---|
| analyze | EDA over the whole dataset (Mann-Whitney U per sensor, Benjamini-Hochberg q-values, charts); time-ordered split (last 25% = test); drops near-duplicate sensors (\|r\| > 0.98, fitted on train); adds `missing_count` | `eda_report.html`, `eda_summary.json`, `features.csv`, `feature_spec.json` |
| *features gate* | ERROR if model features are missing or a split has too few failing runs | |
| model | 4 models (L1 logistic regression, random forest, regularized forest, forest on top-40 sensors) + always-pass baseline; selection by time-ordered CV PR-AUC on the training split; **operating point = alarm budget** (flag the riskiest 10% of runs scored; the F2-tuned fixed threshold is reported for comparison); test metrics with bootstrap 95% CIs; stratified CV as an optimistic reference; permutation importance; risk-over-time chart | `model.joblib`, `model_metrics.json`, `evaluation_report.md`, `predictions.csv`, `oof_predictions.csv` |
| investigate | IsolationForest score + SPC robust z-scores per sensor, both fitted on training runs; **risk ranking**: model probability and anomaly score combined (percentile-rank average) only if that beats the model alone in time-ordered CV | `anomalies.csv`, `anomaly_summary.json`, `risk_scores.csv`, `risk_summary.json` |
| *evidence gate* | WARNING if the model doesn't beat random guessing, no sensor differs significantly, anomaly flags don't separate failing runs, or the risk ranking finds no more failing runs than random flagging | |

Charts are written to `figures/` (PNG, for the reports); the app draws interactive versions from the same run files.

**Results on the real data.** SECOM is hard and drifts over time. The fixed threshold tuned on older runs raises no alarms in the test period; the alarm budget keeps working. The recommended ranking (model + anomaly score) flags 40 of 392 test-period runs and finds 5 of the 24 failing runs (21%, 95% CI 4–35%) with 12.5% precision, about twice the base fail rate. All choices were made with cross-validation on the training period; the test period was scored once.

## Crews

Each crew runs right after the deterministic work of its stage. Agents, tasks and prompts live in YAML (`src/foresight/crews/config/`). Every task receives **fact sheets** built from the run's JSON files (each fact tagged `[source: <file>]`) plus shared rules: use only numbers from the facts or tools, cite sources, label assumptions and hypotheses, say "is associated with" and never "causes".

| Crew | Stage | Agents | Tools | Output |
|---|---|---|---|---|
| Data Analyst | analyze | Data Quality Engineer, Exploratory Data Analyst, Business Insights Writer | `data_quality_summary`, `eda_summary`, `sensor_stats` | `insights.md` |
| Data Scientist | model | Model Evaluator, Model Risk and Ethics Reviewer, Model Card Writer | `model_metrics`, `data_quality_summary` | `model_card.md` |
| Investigation | investigate | Anomaly Analyst, Signal Investigator, Hypothesis Generator | `anomaly_summary`, `risk_ranking`, `run_details`, `find_similar_runs`, `eda_summary`, `sensor_stats`, `model_metrics`, `search_knowledge` | `investigation.md` (Facts / Assumptions / Hypotheses / Suggested verification) and `investigation_summary.json` (headline, 3 key findings, one card per hypothesis) |
| Engineering Report | report | Technical Report Writer, Engineering Review and Safety Editor | none (works from the three documents above) | `engineering_report.md` |

**Automatic output checks** (`src/foresight/crews/checks.py`, results in `report_checks.json` and on the Engineering Report page):

- the required sections are present;
- every sensor name mentioned exists in the data;
- at least 90% of the numbers can be traced to the run's files;
- every fact in the investigation cites a source file;
- every hypothesis states a confidence level, and "high" requires a quoted q < 0.001 and a named second signal (out-of-limit rate, model importance or anomaly flags);
- the investigation's Facts report the overall similar-run comparison, and a run's few similar past runs are never turned into a "failure rate";
- Background citations point at a real knowledge-base section, sit inside a numbered hypothesis, stay out of Facts, and restate their passage (embedding similarity ≥ 0.45, a heuristic); the investigation cites at least one;
- hypotheses (and the summary) use no causal wording such as "contributes to", "causes" or "leads to" (Background sentences and negations like "not a proven cause" are allowed);
- the structured summary is valid JSON with length limits, has one card per hypothesis with the same confidence level, and its key findings cite files of the run.

If a crew's own output fails a check, the crew gets the findings and revises it once (`llm.crew_revisions` in `config/settings.yaml`). Revisions are listed in `crew_revisions.json` and in the report checks. A crew is skipped when its stage's own checks already have an ERROR, so a run that a gate will stop spends no tokens.

**Mock or real LLM.** With `MOCK_LLM=true`, a deterministic mock LLM writes the outputs from the same facts and goes through the same CrewAI agents, tasks and checks. Tests and CI use it, and a session guard makes any paid call fail a test. With the real model (`gpt-4o-mini`, temperature 0), a full run takes about 3.5 minutes and about 27,000 tokens (under 1 US cent). CrewAI's cloud tracing and telemetry are turned off: they added about 15 seconds per crew, and Foresight keeps its own logs and run manifest.

**Reference run.** [`artifacts/reference/`](artifacts/reference) holds a complete real run (gpt-4o-mini, all gates and all 26 report checks PASS, no revisions, with its summary and chat index). The app shows it until a newer run exists.

## RAG and embeddings

Three extensions from requirements §18. Embeddings use a fixed local model (**all-MiniLM-L6-v2** through ONNX Runtime, 384 dimensions): free, no API key, downloaded once (about 80 MB) into `paths.models_dir`, which is on the runs volume on Railway.

| Extension | What it does | Where |
|---|---|---|
| **Similar-run search** | Each run's sensor profile is embedded (median imputation, scaling and PCA with 30 components, all fitted on training runs). For the riskiest and the failing test runs, the 5 most similar *past* runs are retrieved with their labels and distances. The evidence is reported honestly: on SECOM the neighbours of failing test runs failed 5.8% of the time vs 4.7% for passing ones (training fail rate 6.8%), so a run's overall profile says little about failure | `similar_runs.json`/`.csv`, tool `find_similar_runs`, run map on the Report page |
| **Knowledge base** | 12 short background documents written for this project from public sources ([`knowledge/SOURCES.md`](knowledge/SOURCES.md)): SPC, robust statistics, yield loss, drift and maintenance, FDC, SECOM, metrics, multiple testing, anomaly detection, missing data, verification practice. Passages are retrieved deterministically for the evidence types in the report and given to the Investigation crew with their exact citations; hypotheses cite them as `[background: file § section]`, labelled Background, never Evidence | `knowledge/`, tool `search_knowledge` |
| **Ask Foresight** | A passcode-protected chat about the run shown in the sidebar. The run's reports are chunked by section (800 characters, 120 overlap) and indexed at the end of the run (`rag_index.npz`, `rag_chunks.json`; parameters in `run_manifest.json`). Retrieval is hybrid: cosine similarity plus a bonus when the question's words match a section title. Below similarity 0.25 the chat answers "Not found in this run's artifacts." without calling the LLM; otherwise gpt-4o-mini answers only from the retrieved excerpts, citing `[source: file § section]`, or refuses. An answer that cites no retrieved excerpt is withheld. Every question and answer is logged (`chat_logs/<run>.jsonl` in the runs folder); there is no question limit | page *Ask Foresight* |

A question costs about 600–1,100 tokens (well under 0.1 cent).

## The app

| Page | What it shows |
|---|---|
| Run Pipeline | Dataset choice (built-in SECOM or an uploaded CSV), passcode, live progress as five stage tiles (green done, red failed, gray skipped, amber interrupted, cyan with a small animation of the stage's work while it runs; each tile also shows its crew's status) joined by the gates; **Continue run** for an interrupted, timed-out or crashed run; a stopped run says why in plain language and what to do, with the technical details collapsed; run history in local time (status, duration, tokens, report checks, why it stopped) |
| Data Quality | Headline numbers, Data Contract validation (the checksum warning every upload gets is explained as expected), cleaning decisions; all checks and the contract under Extended data |
| EDA & Insights | Headline numbers (with a weekly fail-rate sparkline), the Data Analyst crew's summary, interactive fail rate over time and sensor differences; sensor statistics, missing data and the full insights under Extended data |
| Model | Test metrics with 95% CIs vs random, the selected model and its alarms, interactive risk over time, precision-recall curve, alarms vs outcomes and sensor importance; model comparison, evaluation report and model card under Extended data |
| Investigation & Report | Headline numbers (failing runs caught, alarm precision, anomaly lift, sensors out of limits, similar runs that failed), key findings and one card per hypothesis (confidence, evidence, how to verify), the anomaly timeline and the run map (2D/3D); the engineering report (download), full investigation, risk ranking, similar runs, anomalies and the safety checks under Extended data |
| Ask Foresight | Chat about the selected run, answered only from its reports, with sources and similarity scores; the assistant's avatar is the Foresight logo. Once the chat is unlocked, the sidebar lists the run's recent questions (from its chat log); a click opens the answer |

The sidebar starts with the Foresight wordmark (its "o" is the wafer logo) and the page menu. **Results shown** picks which successful run the result pages display (a short label, the full description under it); it follows the newest run until you choose another one, and the committed reference run is always available. Times are shown in the viewer's time zone (from the browser). A run made before a feature existed says so instead of hiding the section.

**Design.** A dark "cleanroom" theme (`.streamlit/config.toml`): cyan and violet for lithography light, amber (the fab's yellow-room light) for failing runs, a faint die-grid background, a wafer logo, frosted-glass cards, tiles and sidebar (`app/ui.py`). Each page leads with its headline numbers and main charts; the long tables and documents sit under **Extended data**. Charts are Plotly (`app/charts.py`): hover for run ids and values, zoom, and a 3D run map. Fonts (Inter, Space Grotesk, JetBrains Mono) load from Google Fonts.

**Background runs.** "Run pipeline" starts `python -m foresight.cli run` as a separate process, so a run continues when the page is refreshed or closed. The run writes `progress.json` (stages, gates, a heartbeat every 15 s) and `run.log` into its folder. Guards (`app` in `config/settings.yaml`):

- one run at a time and at most 6 runs per hour (cost control),
- a timeout guard stops a run after 20 minutes and records why,
- a run whose heartbeat stopped (for example after a redeploy) is shown as interrupted and can be **continued**: the stages it had finished are reused (their files, gate checks and crew usage are kept in `progress.json`), the data is re-read, and the rest runs again; a continue needs the passcode and counts toward the hourly limit. A run stopped by a gate is not offered a continue (the same data would stop again),
- only the newest 20 finished runs are kept.

**Uploading data.** A CSV with `timestamp` (`dd/mm/yyyy HH:MM:SS` or ISO 8601), `label` (-1 pass, 1 fail) and the 590 sensor columns in SECOM order. The page offers SECOM itself in this format as a template. Uploads are cleaned with the committed Data Contract's feature list (so a smaller or newer batch stays comparable) and validated like the built-in data; a broken file stops at the contract gate with the failed checks listed.

From a terminal: `python -m foresight.cli run [--dataset file.csv] [--timeout 600]`, or `python -m foresight.cli run --run-id <id> --resume` to continue a run.

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
| Unit, data, crews (mock LLM), integration, background runs, Streamlit AppTest (synthetic SECOM, offline) | `pytest` |
| Smoke + Playwright E2E (app must be running) | `python -m playwright install chromium` then `pytest tests/smoke tests/e2e` |

`BASE_URL` points the smoke and E2E tests at another app (default `http://localhost:8501`).

| E2E | Scenario | Where |
|---|---|---|
| E1 | App loads, environment badge | CI, `dev`, `main` |
| E2 | Every result page shows its content (headline tiles, interactive charts) | CI, `dev`, `main` |
| E3 | Headline numbers, key findings and hypothesis cards; Facts / Assumptions / Hypotheses labels; report download | CI, `dev`, `main` |
| E4 | Wrong passcode is rejected, no run starts | CI, `dev`, `main` |
| E5 | Broken CSV upload stops at the contract gate with a plain-language error and the failed checks under Technical details | CI only (starts a run) |
| E6 | Full run: live progress through all crews, then the new run's report | CI only (mock LLM) |
| E7 | Ask Foresight: an answer with a citation; an off-topic question gets "Not found in this run's artifacts." | CI only (mock LLM) |

E5–E7 need the app's passcode in `RUN_PASSCODE` (or `E2E_PASSCODE`); start the app with `MOCK_LLM=true` and, for speed, `FORESIGHT_CONFIG=tests/fast_settings.yaml`. The deployed suite (`-m deployed`) is read-only and never spends LLM tokens.

## Release workflow

`feature/*` → PR into `dev` (CI + local E2E) → auto-deploy to Railway `dev` (smoke + E2E) → PR `dev → main` (CI + E2E) → auto-deploy to `main` (smoke + E2E, rollback on failure).

- `.github/workflows/ci.yml`: PR gates
- `.github/workflows/deployed-tests.yml`: post-deploy gates (needs repository variables `DEV_URL` and `MAIN_URL`)

## Deployment (Railway)

One project `foresight`, service `foresight-app`, environments `main` and `dev`. The service is defined with Railway Infrastructure as Code in [`.railway/railway.ts`](.railway/railway.ts): start command, health check, non-secret variables, a **volume** `foresight-runs` (500 MB, one per environment) mounted at `/app/runs` so runs survive redeploys, and a GitHub source whose branch follows the environment name. Railway's Railpack builder reads `.python-version` and `requirements.txt`. Secrets (`OPENAI_API_KEY`, `RUN_PASSCODE`) are set in Railway with the same values in both environments: fill them in your local `.env`, then run `.\scripts\push_secrets_to_railway.ps1` (values are never printed), then redeploy both environments so the new values load. The IaC file keeps them with `preserve()`.

Apply a configuration change (after merging it):

```powershell
cd .railway; npm install; cd ..
railway link --project <project-id> --environment dev;  railway config plan; railway config apply
railway link --project <project-id> --environment main; railway config plan; railway config apply
```

Code changes deploy automatically when a branch is merged (`dev` → dev environment, `main` → main environment).

## Project structure

```
app/            Streamlit app (entry point: app/streamlit_app.py; ui.py style, charts.py Plotly, messages.py plain-language errors, assets/ logo)
.streamlit/     theme (config.toml)
config/         settings.yaml (seed, LLM model, paths)
src/foresight/  flow.py, jobs.py + cli.py (background runs), progress.py, data/, analytics/, crews/, rag/, tools/, validation/, utils/
knowledge/      background documents for the Investigation crew (+ SOURCES.md)
tests/          unit/, integration/, app/, smoke/, e2e/
scripts/        data download and helper scripts
data/           raw/ and processed/ (not committed)
artifacts/      committed reference run
docs/           Obsidian vault: requirements, decisions, results, lessons learned
```

## License

MIT, see [LICENSE](LICENSE).
