# Final Project — Consolidated Requirements
## Foresight: Multi-Agent Semiconductor Yield Intelligence (SECOM)

> **AI Developers Course · Final Project** · Industry-Simulated AI Product Workflow
>
> Framework: **CrewAI Flow** · Language: **Python** · App: **Streamlit / Flask** · Deploy: **Railway (`main` + `dev`)** · Repo: **GitHub (PRs)** · Dataset: **SECOM (UCI)**

This document combines three sources into one specification, plus the author's own decisions.

> **Author:** Ravid Eliav

| Tag | Source | Meaning |
|---|---|---|
| **[OFFICIAL]** | `final_project_brief_1.html` | Mandatory course requirement. |
| **[SUBJECT]** | `ai_developers_final_project_dashboard.html` | Requirement from the chosen semiconductor subject. Treated as mandatory for this project. |
| **[DECISION]** | Author decision | Choice made by the author. Mandatory for this project (e.g., Railway deployment). |
| **[SUGGESTED]** | Added during planning | Extra professional-quality requirement. Recommended, but cut it if time runs short. |

> **Working principle [SUBJECT]:** a working end-to-end flow matters more than adding lots of features.

---

## 1. Schedule & Milestones [SUBJECT]

| Date | Milestone | Content |
|---|---|---|
| **Nov 18** | Proposal submission | One-page project proposal (`PROJECT_PROPOSAL.md` / `.html`), sent for instructor approval. |
| **Dec 4** | Final project submission | Repository, artifacts, documentation, presentation, demo video. |
| **Dec 9** | Project presentation | Live presentation to the class, or the deck plus a ≤5-min demo if not presenting live. |
| **After Dec 9** | Project close-out **[DECISION]** | Final approved Obsidian vault update in `docs/` (artifacts, links, lessons learned) merged to `main` (see §17). |

> **[OFFICIAL] Alternative Path:** this project uses the official CrewAI Flow structure but swaps the retail domain for semiconductor manufacturing. The proposal (problem, dataset, method, expected output) **must be approved before development starts.**

---

## 2. Business Background

**[OFFICIAL]** A data-driven company wants to put AI models into production in a reproducible, team-friendly way. Management needs two perspectives:

1. **Descriptive:** "What has happened?"
2. **Predictive:** "What is likely to happen next?"

**[SUBJECT] Semiconductor adaptation:** a wafer fab collects hundreds of sensor and process signals per production run. Yield loss is expensive, and engineers struggle to find which of ~590 signals relate to failing runs. The company wants an **AI-assisted engineering system** that:

- validates the manufacturing data,
- describes process behavior (descriptive),
- predicts pass/fail outcomes (predictive),
- investigates abnormal behavior and possible causes (diagnostic),
- delivers a short, **evidence-based engineering report** to a process engineer.

---

## 3. Mission

**[OFFICIAL]** Design and implement a **CrewAI Flow** that coordinates separate multi-agent crews. The project simulates how industry AI product teams turn data into deployable insight and predictive intelligence. Team size is up to 5 students. In this project, **Ravid Eliav** covers every role in the simulated product team (analyst, data scientist, ML engineer, DevOps, reviewer), working with AI coding assistants.

**[SUBJECT]** End-to-end flow:
`Dataset → Data Contract → Statistics → Anomaly / Pass-Fail → Investigation Agents → Engineering Report`

---

## 4. Dataset [SUBJECT]

### 4.1 Selection

| Candidate | Type | Decision |
|---|---|---|
| **SECOM** (UCI ML Repository) | Tabular sensor/process data with a pass/fail label | ✅ **Primary dataset** |
| WM-811K (Kaggle) | Wafer-map images/patterns | ⏩ Future extension only (out of scope) |

**Rationale:** SECOM is tabular and labeled, so it fits the required stack (Pandas, Scikit-Learn, Matplotlib/Seaborn) and the Data Scientist Crew's modeling task directly. WM-811K would need computer-vision work that doesn't fit the timeline.

### 4.2 SECOM facts

- `secom.data`: **1,567 production runs × 590 numeric sensor features** (anonymized, space-separated, `NaN` for missing).
- `secom_labels.data`: label `-1` = **pass**, `1` = **fail**, plus a **timestamp** per run.
- **104 fails (≈6.6%)**, so the classes are heavily imbalanced.
- Known issues: many missing values, many constant or near-constant columns, anonymized feature names, high redundancy and collinearity.
- Source: <https://archive.ics.uci.edu/dataset/179/secom>. Document the source, license, and download steps in the README.

### 4.3 Data acquisition requirements

- **[OFFICIAL]** The dataset loads reproducibly, with the source and setup documented.
- **[SUGGESTED]** Provide a `scripts/download_data.py` (or a committed copy in `data/raw/` if the license and size allow). Record the file SHA-256 checksums in the run manifest.
- **[OFFICIAL – optional]** Data may also be uploaded to and read from **Supabase**.

---

## 5. System Architecture

### 5.1 High-level flow

```
+--------------+   +---------------+   +-------------------+   +--------------------+   +-----------------+
| 1. Ingestion |-->| 2. Validation |-->| 3. Analytics      |-->| 4. Investigation   |-->| 5. Reporting    |
|  load SECOM  |   | Data Contract |   | Analyst + DS Crew |   | Investigation Crew |   | Report Crew     |
+--------------+   +-------+-------+   +---------+---------+   +----------+---------+   +--------+--------+
                           |                     |                        |                      |
                   GATE: ERROR=stop      GATE: ERROR=stop         GATE: WARN=flag      engineering_report.md
                   (contract vs data)    (features present)       (evidence present)
```

### 5.2 Crew mapping (merged design)

| Flow stage | Crew | Origin | Question answered |
|---|---|---|---|
| A | **Data Analyst Crew** | [OFFICIAL] Crew 1 | What happened? Is the data trustworthy? |
| B | **Data Scientist Crew** | [OFFICIAL] Crew 2 | Can we predict fails? Which signals matter? |
| C | **Investigation Crew** | [SUBJECT] Team 1 | Why might failures happen? What are the hypotheses? |
| D | **Engineering Report Crew** | [SUBJECT] Team 2 | What should the engineer do next? |

> Crews A and B satisfy the official brief. Crews C and D add the subject-specific diagnostic and communication layer and are the project's main differentiator. **MVP minimum: A + B + D.** Crew C may be merged into D if time runs short.

---

## 6. Crew Specifications

### 6.1 Crew A: Data Analyst Crew [OFFICIAL] (≥3 agents)
**Responsibilities [OFFICIAL]:**

- Ingest and validate the dataset.
- Clean, preprocess, and document it.
- Run descriptive analytics and EDA.
- Produce visual insights and business summaries.
- Define a **dataset contract** that the Data Scientist Crew must follow.

**Suggested agents [SUGGESTED]:**

| Agent | Role | Tools |
|---|---|---|
| Data Ingestion & Quality Engineer | Load raw files, merge features with labels and timestamps, profile missing values | `load_secom`, `profile_dataset` |
| Data Cleaning Specialist | Drop columns with >X% missing or constant values, impute, record every decision | `clean_dataset` |
| EDA & Insights Analyst | Statistics, distributions, fail-rate over time, top-variance signals, charts, business summary | `compute_stats`, `make_charts` |
| Data Contract Author | Write `dataset_contract.json` from the cleaned data | `build_contract` |

**Required outputs [OFFICIAL]:**

| Artifact | Content |
|---|---|
| `clean_data.csv` | Cleaned, merged dataset (features + `label` + `timestamp`) |
| `eda_report.html` | Visual EDA report with embedded charts |
| `insights.md` | Business and engineering summary of what happened |
| `dataset_contract.json` | Schema, allowed values, assumptions, constraints |

### 6.2 Crew B: Data Scientist Crew [OFFICIAL] (≥3 agents)
**Responsibilities [OFFICIAL]:**

- Read and validate the cleaned dataset against the contract.
- Do feature engineering.
- Train at least **one** predictive model (pass/fail classifier).
- Compare at least **two model variations**.
- Write a **model card** covering purpose, training data summary, metrics, limitations, and ethical considerations.

**Suggested agents [SUGGESTED]:**

| Agent | Role |
|---|---|
| Contract Validator / Feature Engineer | Validate inputs, apply variance/correlation filtering, scale, optionally select features → `features.csv` |
| Model Trainer | Train ≥2 variations (e.g., Logistic Regression `class_weight="balanced"` vs Random Forest / Gradient Boosting; optionally with and without SMOTE), using fixed seeds and a **time-ordered or stratified split** |
| Model Evaluator & Documenter | Compare models on imbalance-aware metrics, choose the best one, write `evaluation_report.md` and `model_card.md` |

**Required outputs [OFFICIAL]:**

| Artifact | Content |
|---|---|
| `features.csv` | Engineered feature matrix |
| `model.joblib` (or `.pkl`) | Selected trained model (pipeline) |
| `evaluation_report.md` | Side-by-side comparison of model variations |
| `model_card.md` | Purpose, data, metrics, limitations, ethics |

**Metrics [SUGGESTED, strongly recommended because of the 6.6% fail rate]:** PR-AUC, ROC-AUC, recall on the *fail* class, precision, F1, balanced accuracy, confusion matrix, and the chosen decision threshold. **Do not report accuracy alone**: a model that always predicts "pass" scores 93%.

**Explainability [SUGGESTED]:** permutation importance or SHAP for the top-N signals. These feed Crew C.

### 6.3 Crew C: Investigation Crew [SUBJECT] (≥2–3 agents)
**Responsibilities [SUBJECT]:**

- Review abnormal observations and the relevant process parameters.
- Look for patterns, correlations, clusters, and unusual combinations.
- Generate possible explanations for abnormal behavior.
- **Clearly separate measured facts from AI-generated hypotheses.**

**Suggested agents [SUGGESTED]:**

| Agent | Role |
|---|---|
| Anomaly Analyst | Interpret anomaly results (e.g., IsolationForest scores, z-score/SPC out-of-limit signals) |
| Signal Correlation Investigator | Compare fail vs pass distributions, top discriminating signals, correlated sensor groups, time drift |
| Hypothesis Generator | Propose ranked hypotheses, each with its supporting evidence, a confidence level, and a way to verify it |

**Outputs:** `anomalies.csv`, `investigation.md` (structured into *Facts / Assumptions / Hypotheses*).

### 6.4 Crew D: Engineering Report Crew [SUBJECT] (≥2 agents)
**Responsibilities [SUBJECT]:**

- Turn the analysis into a short, structured engineering report.
- Summarize detections and the relevant statistics.
- Present hypotheses with their evidence and uncertainty.
- Recommend practical next investigation steps **without overstating causality**.

**Suggested agents:** Technical Report Writer and Engineering Review / Safety Editor. The editor checks that every claim is labeled and backed by evidence.

**Output:** `engineering_report.md`, plus an optional HTML/PDF version.

**[SUBJECT] The engineer-facing report must contain:**

1. What was detected
2. Supporting statistical evidence
3. Important abnormal parameters
4. Generated hypotheses (labeled, with confidence)
5. Recommended next investigation steps
6. **[SUGGESTED]** Data quality caveats and model limitations

---

## 7. CrewAI Flow Requirements [OFFICIAL] + [SUBJECT]

| # | Requirement | Implementation guidance |
|---|---|---|
| F1 | **[OFFICIAL]** Automate the handoff Analyst Crew → Scientist Crew (→ Investigation → Report) | `crewai.flow` with `@start`, `@listen`, and `@router`. Use a typed Pydantic Flow `state` holding artifact paths and key metrics |
| F2 | **[OFFICIAL]** Validation: the contract matches the cleaned dataset | Gate after Crew A: column names, dtypes, ranges, label domain `{-1,1}` or `{0,1}`, missing-value thresholds |
| F3 | **[OFFICIAL]** Validation: all required features exist before modeling | Gate before Crew B trains: `features.csv` columns ⊇ the contract's required features |
| F4 | **[SUBJECT]** Validation runs **before** any agent analysis. Failed checks produce clear errors or warnings, block unreliable downstream steps, and write `validation_summary.json` | Classify each check as `ERROR` (stop the flow) or `WARNING` (continue, but flag it in the report) |
| F5 | **[OFFICIAL]** Reproducibility: deterministic steps | Fixed `random_state` and seeds everywhere, LLM `temperature=0`, pinned `requirements.txt`, deterministic split |
| F6 | **[OFFICIAL]** Reproducibility: clear logging | Python `logging` to console and `logs/run_<id>.log` with a timestamp, stage, and status per step |
| F7 | **[OFFICIAL]** Reproducibility: artifacts saved inside the repo | `artifacts/<stage>/...`, with one example run committed |
| F8 | **[OFFICIAL]** Fail gracefully when validations break | Router sends the flow to a `handle_failure` step that writes a failure report, logs the cause, and the UI shows a friendly message (no stack trace) |
| F9 | **[SUGGESTED]** Run manifest | `artifacts/run_manifest.json`: run id, git commit, data checksums, package versions, seed, LLM model, durations, gate results |
| F10 | **[SUGGESTED]** Deterministic computation in tools, interpretation by LLMs | All math (stats, models, anomalies) runs in **Python tools**. Agents interpret the **computed summaries**, not 590 raw columns. This keeps results reproducible, avoids hallucinated numbers, and cuts token cost |

---

## 8. Data Contract Specification [OFFICIAL] + [SUBJECT]

**[SUBJECT] The contract must check:** column presence, data types, missing values, and invalid or unexpected values.

`dataset_contract.json`, suggested structure:

```json
{
  "contract_version": "1.0",
  "dataset": "SECOM",
  "source": "https://archive.ics.uci.edu/dataset/179/secom",
  "row_count": {"min": 1500},
  "target": {"name": "label", "dtype": "int", "allowed_values": [0, 1], "mapping": {"-1": 0, "1": 1}, "positive_class": "fail"},
  "timestamp": {"name": "timestamp", "dtype": "datetime", "nullable": false},
  "features": {
    "required": ["f_021", "f_059", "..."],
    "dtype": "float",
    "max_missing_ratio": 0.0,
    "ranges": {"f_021": {"min": 0.0, "max": 120.5}}
  },
  "dropped_columns": {"constant": ["..."], "high_missing": ["..."]},
  "assumptions": ["Missing values imputed with the training-set median", "Feature names are anonymized"],
  "constraints": ["No duplicate rows", "Label imbalance ≈ 6.6% fail"]
}
```
**[SUGGESTED]** Back the contract with code: a Pydantic or `pandera` schema, plus unit tests that deliberately feed broken data and check that the gate fails.

---

## 9. Application / UI [OFFICIAL]

- **[OFFICIAL]** Streamlit or Flask (or both). The frontend may use HTML + CSS.
- **[SUGGESTED] Streamlit app pages:**
    1. **Run Pipeline:** upload or select the dataset, start the Flow, show live stage status and gate results.
    2. **Data Quality:** validation summary and contract view.
    3. **EDA & Insights:** charts and `insights.md`.
    4. **Model:** model comparison table, confusion matrix, PR curve, model card.
    5. **Investigation & Report:** anomalies, hypotheses (facts vs hypotheses color-coded), downloadable engineering report.
    6. *(Optional)* **Predict:** score a new run or CSV with the saved model.
    7. *(Stretch)* **Ask Foresight:** a chat about the current run that answers only from the run's artifacts and cites its sources (see §18).

- **[OFFICIAL – optional, recommended] → [DECISION] Deployment: Railway (required).** The Streamlit app is deployed to Railway in two environments: **`main`** (stable, used for the demo) and **`dev`** (integration and testing). Each has its own public URL. Supabase (optional) may store data and run history.

### 9.1 Railway Deployment Requirements [DECISION]

| # | Requirement | Implementation guidance |
|---|---|---|
| D1 | The app is publicly reachable on a Railway-generated domain (`*.up.railway.app`) | One Railway **project** `foresight` with two **environments**, `main` and `dev`. The **service** `foresight-app` runs in both, and each environment has its own generated domain |
| D2 | Automatic deploys from GitHub, one branch per environment | The `main` environment deploys from the `main` branch and the `dev` environment from the `dev` branch. A merge to either branch triggers a deploy to the matching environment. No PR preview environments |
| D3 | Build and start are defined in code | Railway's default builder (Railpack) auto-detects Python from `requirements.txt`. A config-as-code file `railway.toml` pins the start command: `streamlit run app/streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`. Pin the Python version with `.python-version` (**3.11**; CrewAI supports 3.10–3.13) |
| D4 | Secrets live in Railway variables, never in the repo. **Both environments use the same variables** | `OPENAI_API_KEY` (or other LLM key), `LLM_MODEL`, `RUN_PASSCODE`, optional `SUPABASE_URL`/`SUPABASE_KEY`. The `dev` environment is created as a duplicate of `main`, which copies every variable. Any later variable change is applied to both environments so they stay identical. The UI environment badge reads Railway's built-in `RAILWAY_ENVIRONMENT_NAME`, so no environment-specific variable is needed. `.env.example` lists the names only |
| D5 | The demo works without waiting for a full LLM run | The deployed app ships a **committed reference run** in `artifacts/` and displays it instantly. A "Run pipeline" button triggers a fresh run, with progress shown and a timeout guard |
| D6 | Writable artifacts survive restarts (if fresh runs are enabled) | Attach a Railway **volume** (e.g., mounted at `/app/runs`), or store run outputs in Supabase. The container filesystem is otherwise temporary |
| D7 | Health and observability | Streamlit health endpoint `/_stcore/health` set as the Railway healthcheck path. Python logs go to stdout and can be viewed in Railway deploy logs |
| D8 | Cost and abuse control | Limit how often runs can be triggered, keep a small default LLM model, and optionally require a simple passcode (stored as a Railway variable) for the "Run pipeline" action |
| D9 | Documented and verified | The README lists **both** live URLs (`main` and `dev`) and has a "Deploy to Railway" section (GitHub auto-deploy, or `railway login` → `railway link` → `railway up --environment <env>`). The `main` deployment is confirmed healthy (status SUCCESS, smoke and Playwright E2E tests passed) before the demo is recorded |
| D10 | Promotion only through `dev`, with a test gate at every step | Features reach `main` only through a `dev → main` PR. Hotfixes also go through `dev`. Four test gates (see §9.2) must pass: CI + local Playwright E2E on PRs to `dev`, smoke + E2E after the `dev` deploy, CI + E2E plus a dev-health check on the `dev → main` PR, and smoke + E2E after the `main` deploy. If the `main` tests fail, roll back to the previous deployment in Railway |

Example `railway.toml`:

```toml
[build]
builder = "RAILPACK"

[deploy]
startCommand = "streamlit run app/streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true"
healthcheckPath = "/_stcore/health"
healthcheckTimeout = 120
restartPolicyType = "ON_FAILURE"
```

### 9.2 Environments, Release Workflow & Testing [DECISION]

| Railway environment | Git branch | Purpose | URL | Tests |
|---|---|---|---|---|
| `main` | `main` | Stable app for the demo, the instructor and the presentation | `foresight-app-main.up.railway.app` (example) | CI + E2E on the `dev → main` PR; smoke + E2E after every deploy |
| `dev` | `dev` | Integration and testing of new features before release | `foresight-app-dev.up.railway.app` (example) | CI + E2E on every PR into `dev`; smoke + E2E after every deploy |

Both environments run the same code path and **share identical variable values** (same LLM key and model, passcode, and Supabase). They differ only in the Git branch they deploy from and their URL. Railway keeps volumes per environment, so each has its own run-output storage.

**Release flow with test gates:**

```
feature/*  --PR-->  [GATE 1: CI + local E2E]  -->  dev branch  --auto-deploy-->  dev env  -->  [GATE 2: smoke + E2E on dev URL]
                                                                                                        |
                                                                                                        v
main env  <--auto-deploy--  main branch  <--merge--  [GATE 3: CI + local E2E + dev healthy]  <--PR dev -> main--
   |
   v
[GATE 4: smoke + E2E on main URL]  --fail-->  Railway rollback to previous deployment
```

**Test layers (test pyramid):**

| Layer | Tool | What it covers | Where it runs |
|---|---|---|---|
| Unit | `pytest` | Data Contract checks, tools (cleaning, stats, models, anomalies), Flow gate logic and router | Gates 1, 3 |
| Integration | `pytest` + mocked LLM agents | The full CrewAI Flow end to end on a small SECOM sample: artifacts are created and gates stop on broken data | Gates 1, 3 |
| App | Streamlit `AppTest` (`streamlit.testing.v1`) | Each page renders without exceptions and widgets behave correctly. Headless and fast, no browser needed | Gates 1, 3 |
| Smoke | `pytest` + `requests` | `/_stcore/health` returns 200 and the page responds | Gates 2, 4 |
| **E2E** | **Playwright** (`pytest-playwright`, Chromium) | Real user journeys in a real browser (see the scenarios below) | Gates 1, 3 against a locally started app; gates 2, 4 against the deployed URL |

**Playwright E2E scenarios:**

| # | Scenario | Expected result | Local CI (mocked LLM) | Deployed `dev` / `main` |
|---|---|---|---|---|
| E1 | Open the app | App loads with no error box; the environment badge shows the right environment (`dev` / `main`) | ✔ | ✔ |
| E2 | Navigate every page (Data Quality, EDA, Model, Investigation & Report) | Validation summary, EDA charts, the model comparison table (PR-AUC, fail-recall) and the model card are visible | ✔ | ✔ |
| E3 | Engineering report page | Facts / Assumptions / Hypotheses labels are present, and "Download report" returns a non-empty `.md` file | ✔ | ✔ |
| E4 | Start "Run pipeline" without a passcode or with a wrong one | A friendly "not authorized" message appears and no run starts | ✔ | ✔ |
| E5 | Upload a broken CSV (missing columns or a bad label value) | The contract gate shows a clear error; no stack trace; later stages don't run | ✔ | — |
| E6 | Full pipeline run with the right passcode | Stage progress moves through all crews, then the new run's report and artifacts appear | ✔ | — (no LLM spending on deployed envs) |
| E7 | *(Stretch, §18)* Ask Foresight: ask a question about the run; ask one with no answer in the artifacts | The answer cites an artifact file; the out-of-scope question gets "not found in this run's artifacts" | ✔ (mocked LLM, fixed index) | — |

**Playwright guidelines:**

- Use stable selectors: Streamlit `data-testid` attributes and visible text/roles, not CSS class names. Wait for the app to finish loading (`[data-testid="stApp"]` is present and no "Running…" status is showing) before making assertions.
- The deployed suite (gates 2 and 4) is **read-only**: it never triggers real LLM runs, because `dev` and `main` share the same LLM key and budget. E5, E6 and E7 run only in CI against a local app started with `MOCK_LLM=true`.
- `BASE_URL` selects the target: `http://localhost:8501` in CI, otherwise the Railway URL from the deployment event.
- On failure, save the Playwright **trace, screenshots and video** as GitHub Actions artifacts so the failure can be debugged.
- **[SUGGESTED]** Reuse the Playwright screenshots and video in the presentation and as a backup for the demo recording.

| Gate | When | What runs | Blocks |
|---|---|---|---|
| **1. PR CI** | Every PR into `dev` | `ruff` lint, unit + integration + `AppTest` tests, then **Playwright E2E (E1–E6)** against the app started locally in the CI runner with `MOCK_LLM=true` | Merge into `dev` |
| **2. Dev post-deploy** | After each successful deploy to `dev` | Smoke tests, then **Playwright E2E (E1–E4)** against the dev URL | Opening/merging the `dev → main` PR |
| **3. Release PR** | The `dev → main` PR | The same CI + local E2E suite as gate 1, plus a check that the latest `dev` deployment is SUCCESS and gate 2 passed | Merge into `main` (required status checks) |
| **4. Main post-deploy** | After each successful deploy to `main` | Smoke tests, then **Playwright E2E (E1–E4)** against the main URL | If it fails: roll back in Railway and open an issue. The demo is recorded only after it passes |

**Implementation:**

- `.github/workflows/ci.yml`: triggered on `pull_request` to `dev` and `main` (gates 1 and 3). It installs browsers with `playwright install --with-deps chromium`, starts `streamlit run` in the background with `MOCK_LLM=true`, waits for `/_stcore/health`, then runs `pytest tests/e2e`.
- `.github/workflows/deployed-tests.yml`: triggered by GitHub's `deployment_status` event, which Railway reports for GitHub-connected services, plus `workflow_dispatch` for manual runs (gates 2 and 4). It runs `pytest tests/smoke tests/e2e -m deployed` with `BASE_URL` set to the deployed URL.
- Smoke and deployed E2E tests make no LLM calls, so they're fast, free and deterministic.
- Branch protection on `main` and `dev` requires the CI checks (including E2E) to pass. `main` also requires the dev deployed-tests check.

**Setup commands (example):**

```bash
railway init --name foresight                           # creates the project (first environment renamed to "main" in the dashboard)
railway environment new dev --duplicate main            # dev gets the same config and variables as main
railway variable set LLM_MODEL=gpt-4o-mini --service foresight-app --environment main
railway variable set LLM_MODEL=gpt-4o-mini --service foresight-app --environment dev   # keep both identical
```

---

## 10. Engineering Safety & Ethics [SUBJECT] + [OFFICIAL]

- **[SUBJECT]** Label facts, assumptions, and hypotheses explicitly. Never present an unsupported root-cause claim as fact.
- **[SUBJECT]** Recommendations must not overstate causality. Correlation ≠ causation.
- **[OFFICIAL]** The model card covers ethical considerations: false negatives (missed fails reach customers), false positives (unnecessary scrap or rework), automation bias, and the requirement that an engineer stays in the loop.
- **[SUGGESTED]** Every number in the report must trace back to an artifact file (traceability). The Review agent rejects claims that aren't backed by one.
- **[SUGGESTED]** Keep API keys in `.env` locally and in **Railway variables** (same values in `main` and `dev`) when deployed, and never commit them. Provide a `.env.example`.

---

## 11. Tech Stack [OFFICIAL]

| Area | Requirement |
|---|---|
| Core | ✔ CrewAI ✔ Python ✔ Git + GitHub **with Pull Requests** |
| App | ✔ Streamlit and/or Flask; frontend may be HTML + CSS |
| Data/ML | ✔ Pandas ✔ Scikit-Learn ✔ Matplotlib/Seaborn |
| Deployment **[DECISION]** | ✔ **Railway** (official brief lists it as optional/recommended; this project makes it required) |
| Optional | Supabase (data / run history storage) |
| Testing **[DECISION]** | ✔ `pytest`, `ruff`, Streamlit `AppTest`, **Playwright** (`pytest-playwright`) for E2E, `requests` (smoke), GitHub Actions |
| **[SUGGESTED]** | `pydantic`/`pandera` (contract), `imbalanced-learn`, `shap` |
| **[SUGGESTED] Stretch (§18)** | Embeddings: `text-embedding-3-small` (or local `sentence-transformers`); vector store: `chromadb`/FAISS locally, or Supabase `pgvector`; CrewAI knowledge sources; scikit-learn `PCA` + `NearestNeighbors` |

---

## 12. Repository Requirements [OFFICIAL] + [SUBJECT] + [SUGGESTED]

**[SUBJECT]** The repository contains source code, configurations, the Data Contract, generated artifacts, documentation, and a clear **README** with installation and run instructions.

**[SUGGESTED] Structure:**

```
foresight/
├── README.md                 # overview, architecture, setup, run, results
├── requirements.txt          # pinned versions
├── railway.toml              # Railway build/start/healthcheck config
├── .python-version           # pinned Python for Railway build
├── .env.example
├── config/                   # settings.yaml (thresholds, seeds, LLM model)
├── data/raw/ , data/processed/
├── src/foresight/
│   ├── flow.py               # CrewAI Flow (state, gates, router)
│   ├── crews/                # analyst/, scientist/, investigation/, report/  (agents.yaml, tasks.yaml, crew.py)
│   ├── tools/                # deterministic Python tools
│   ├── validation/           # contract schema + checks
│   ├── rag/                  # (stretch) similar-run search, knowledge index, Ask Foresight retrieval
│   └── utils/                # logging, manifest, seeds
├── app/streamlit_app.py
├── artifacts/                # committed example run outputs
├── logs/
├── tests/                    # unit + integration (mocked LLM) + Streamlit AppTest
│   ├── smoke/                # health checks against the dev/main URLs
│   └── e2e/                  # Playwright user journeys (local + deployed)
├── docs/                     # Obsidian vault: docs, decisions, lessons, links, final artifacts (see §17)
└── .github/workflows/        # ci.yml (PR gates) + deployed-tests.yml (post-deploy gates)
```
**[OFFICIAL] Git workflow:** feature branches, **Pull Requests** with reviews, meaningful commits. Every PR is opened and reviewed with a self-review checklist in the PR template plus an AI code review (e.g., GitHub Copilot review), and the required CI checks must pass.

**[DECISION] Branching model:**

- Two long-lived, protected branches: `main` (release) and `dev` (integration). Each deploys to the Railway environment with the same name.
- Feature branches (`feature/<name>`) are created from `dev` and merged back into `dev` through a PR (self-review + AI review + CI).
- A release is a `dev → main` PR. Nobody pushes directly to `main` or `dev`.
- Required status checks: CI on both branches; on `main`, also the dev deployed-tests check (see §9.2).
- **[SUGGESTED]** Use a PR template (what changed, how it was tested, a screenshot from the dev URL).

---

## 13. Final Deliverables [OFFICIAL] + [SUBJECT]

| # | Deliverable | Content |
|---|---|---|
| 1 | **GitHub repository** | Code, configs, Data Contract, artifacts, docs, README with the **live Railway URL** |
| 2 | **Business presentation (10–12 slides)** | Problem, solution, architecture, workflow, results, limitations, demo |
| 3 | **Demo recording (≤ 5 min)** | Application running end to end, **on the live Railway deployment** |

**[SUGGESTED] Slide outline (12):**

1. Title & author
2. Business problem (yield loss)
3. Dataset & challenges
4. Solution overview
5. Architecture / Flow
6. Crews & agents
7. Data Contract & validation gates
8. EDA insights
9. Model results
10. Investigation & engineering report
11. Limitations, ethics, next steps
12. Demo / Q&A

---

## 14. Acceptance Checklist (Definition of Done)

| Area | Criterion | Status |
|---|---|---|
| Data | Dataset loads reproducibly with documented source and setup | REQUIRED |
| Validation | Contract checks columns, types, missing values, invalid values; `validation_summary.json` produced | REQUIRED |
| Flow | CrewAI Flow automates the crew handoffs, with gates and graceful failure | REQUIRED |
| Crews | Analyst and Scientist crews each have ≥3 agents | REQUIRED |
| Artifacts | All 8 official artifacts are generated and saved in the repo | REQUIRED |
| Analytics | Useful statistics are computed and abnormal cases identified | REQUIRED |
| Modeling | ≥1 model trained, ≥2 variations compared, model card written | REQUIRED (official) |
| Agents | Investigation and reporting outputs are traceable and clearly separated | REQUIRED |
| Engineering safety | Facts, assumptions, and hypotheses are labeled; no unsupported root cause | REQUIRED |
| Reproducibility | Deterministic, logged, re-runnable | REQUIRED |
| App | Streamlit/Flask UI runs the flow and displays the results | REQUIRED |
| Repository | README lets a reviewer install and run; PRs used | REQUIRED |
| Presentation | 10–12 slides plus a demo of ≤5 min | REQUIRED |
| Deployment | App deployed on **Railway** in the `main` and `dev` environments, both URLs healthy, same variables in both, auto-deploy from the matching branches | REQUIRED (author decision) |
| Testing & release | All 4 test gates in place and passing: CI with unit, integration, AppTest and **Playwright E2E** on PRs to `dev` and `main`, plus smoke and Playwright E2E after each deploy. Demo recorded on `main` | REQUIRED (author decision) |
| Knowledge base | `docs/` Obsidian vault holds docs, decisions, lessons learned, links and final artifacts. Final approved backup is merged to `main` after Dec 9 | REQUIRED (author decision) |
| Quality | Run manifest, explainability (SHAP / permutation importance), PR template | SUGGESTED |

---

## 15. Scope Boundaries

**In scope (MVP):** SECOM; 4-stage Flow (Crew C may merge into D); contract gates; ≥2 classifiers; anomaly detection; engineering report; Streamlit app **deployed on Railway (`main` + `dev`)**; CI, Playwright E2E and post-deploy smoke tests; README; slides; demo.

**Stretch:** RAG & embeddings (§18: similar-run search, Investigation knowledge base, "Ask Foresight" chat), Supabase storage, SHAP, a Predict page, a Flask REST endpoint (`/predict`).

**Out of scope:** WM-811K image modeling, real-time fab integration, real root-cause confirmation (would need fab domain data), deep-learning models.

---

## 16. Risks & Mitigations [SUGGESTED]

| Risk | Mitigation |
|---|---|
| Heavy class imbalance | Class weights or SMOTE, PR-AUC and fail-recall metrics, threshold tuning |
| 590 anonymized features, lots of missing data | Contract-driven filtering, imputation, correlation pruning; explain to the audience that feature names are anonymized |
| LLM hallucinated numbers | Tools compute every number, the review agent checks claims, temperature 0 |
| LLM cost and latency | Send only summaries to agents, cache results, use a small model for simple agents |
| Non-determinism | Seeds, pinned versions, run manifest, committed reference artifacts |
| Time pressure | MVP-first, then stretch goals. Deploy a "hello" Streamlit app to Railway (`main` + `dev`) and set up the CI, smoke and Playwright E2E workflows **early** (week 1) so deployment never blocks the end |
| A broken feature reaches the demo app | Work merges into `dev` first; the 4 test gates; `main` changes only through a tested `dev → main` PR; Railway rollback if the `main` smoke/E2E tests fail |
| `dev` and `main` share the same LLM key and budget | CI uses mocked agents; smoke and deployed E2E tests are read-only and use the reference run (no LLM calls); real pipeline runs need the passcode; provider spending cap |
| Long LLM runs or timeouts on Railway | Show the committed reference run by default, run fresh pipelines in the background with progress, and use a volume for outputs |
| Public LLM key abuse / cost | Keys in Railway variables, a passcode on "Run pipeline", rate limiting, and a spending cap on the LLM provider |
| RAG answers that sound right but aren't backed by the data | Answers only from retrieved passages, required citations, refusal when nothing relevant is retrieved, domain knowledge labeled "Background" (never "Evidence") |

---

## 17. Project Knowledge Base & Backup (Obsidian) [DECISION]

The repository's `docs/` folder is also an **Obsidian vault**. The project's documentation, decisions, lessons and final results are kept as linked notes there and saved together with the code. Every commit and push to GitHub backs up the vault.

### 17.1 Vault structure

```
docs/                              # open this folder as a vault in Obsidian
├── .obsidian/                     # shared vault settings (commit app.json, core plugins; ignore workspace*.json)
├── Home.md                        # index: project summary + all key links
├── Requirements/                  # PROJECT_REQUIREMENTS.md, PROJECT_PROPOSAL.md
├── Decisions/                     # decision log, one note per decision (ADR style)
├── Architecture/                  # Flow diagram, crews & agents, Data Contract
├── Model/                         # model_card.md, evaluation_report.md (final copies)
├── Results/                       # engineering_report.md, insights.md, key charts (PNG)
├── Lessons-Learned/               # retrospective notes
├── Presentation/                  # slide deck (PDF) and demo video link
└── templates/                     # note templates: decision, lesson, milestone
```

### 17.2 Content

| Area | Content |
|---|---|
| **Docs** | Requirements, proposal, README summary, model card, evaluation report, engineering report |
| **Decisions** | One note per decision with context, options considered, decision, consequences and date. Starter set: `ADR-001 SECOM as dataset`, `ADR-002 Four-crew merged Flow`, `ADR-003 Railway main + dev, same variables`, `ADR-004 Test gates and Playwright E2E`, `ADR-005 Tools compute, agents interpret` |
| **Lessons learned** | What worked, what didn't, what I'd do differently (CrewAI, data, deployment, testing, working with AI coding assistants) |
| **Links** | GitHub repo, Railway `main` and `dev` URLs, final release, presentation, demo video |
| **Artifacts** | Final copies of the key artifacts and charts, because Obsidian can only show files inside the vault. The working artifacts stay in `artifacts/` |

Notes use `[[wikilinks]]` between related notes, plus front-matter (`date`, `status`, `tags`) so the vault can be searched and graphed.

### 17.3 Update process: suggest, then approve

- **Triggers ("big changes"):**
    - a new or changed requirement or decision
    - a `dev → main` release
    - new model or evaluation results
    - a change to the architecture or deployment
    - each milestone (Nov 18, Dec 4, Dec 9)
    - the end of the project
- After a trigger, the **AI assistant suggests a vault update**: which notes to add or change, with a short summary of the change.
- The author **approves or rejects** it. Nothing is written to the vault without approval.
- Approved updates go through the normal flow (`feature/docs-*` → PR into `dev` → `dev → main`), so the vault is versioned and backed up on GitHub.
- **End of project (after Dec 9):** a final suggested update covers the final artifacts snapshot, all links, the lessons-learned retrospective and the closed decision log. Once approved and merged to `main`, it is the project's final backup.

---

## 18. AI Extensions: RAG & Embeddings [SUGGESTED] (Stretch)

**Why this is a stretch goal, not core:** SECOM is numeric and anonymized. It has no text, and its sensor names have no physical meaning, so embedding the raw data or running RAG over it adds nothing to the core pipeline. Neither course document requires RAG. The three extensions below add value in specific places. Build them **only after the MVP is working end to end on `main`**, in this order:

| Priority | Extension | Type | Value | Effort |
|---|---|---|---|---|
| 1 | **Similar-run search** | Numeric embeddings (no LLM) | Gives the Investigation crew concrete evidence: "the most similar past runs to this failed run, and how they turned out" | Low |
| 2 | **Investigation knowledge base** | RAG via CrewAI knowledge sources | Hypotheses cite real domain sources instead of the LLM's memory | Low–Medium |
| 3 | **"Ask Foresight" chat** | RAG over the run's own artifacts | The engineer asks questions in the app and gets answers with citations. Strong for the demo | Medium |

### 18.1 Similar-run search (numeric embeddings)

- Build a deterministic **run embedding** from the cleaned, scaled features: `PCA` (fixed `random_state`, e.g., 20–50 components) fitted on the training split only.
- Use `NearestNeighbors` (cosine or Euclidean) to retrieve the **k most similar historical runs** for each anomalous or failed run, along with their labels and timestamps.
- Exposed to the Investigation crew as a Python **tool** (`find_similar_runs(run_id, k)`). The output is saved to `artifacts/investigation/similar_runs.csv`.
- Shown in the report as **Evidence** ("4 of the 5 most similar runs also failed"), with the distances included.
- *(Optional)* Show a 2-D projection (PCA/UMAP) of all runs, colored by pass/fail, on the Investigation page.

### 18.2 Investigation knowledge base (RAG)

- A small, curated folder `knowledge/` of **public** sources (about 10–20 documents). Examples: SPC / Western Electric control-chart rules, a general overview of semiconductor yield-loss causes, the SECOM dataset description, and guidance on metrics for imbalanced classification. Record each document's source URL and license in `knowledge/SOURCES.md`.
- Indexed with **CrewAI knowledge sources** (or a `chromadb` collection) using a fixed embedding model. It is attached **only to the Investigation crew**.
- Every retrieved passage used in a hypothesis must be **cited** (`[source: file, section]`) and labeled **Background**, never **Evidence**. Evidence must come from this run's data and artifacts (§10).
- Because the features are anonymized, retrieved knowledge may only support **general** reasoning ("drift patterns like this are often linked to…"). It must not link a specific sensor to a physical cause.

### 18.3 "Ask Foresight" chat (RAG over run artifacts)

- A Streamlit page (§9, page 7). Each finished run's text artifacts (`insights.md`, `evaluation_report.md`, `model_card.md`, `investigation.md`, `engineering_report.md`, `validation_summary.json`) are **chunked and embedded into a per-run index**. Each run's index is stored with that run's outputs (Railway volume) or in Supabase `pgvector`.
- Answers are generated **only from the retrieved chunks**, at temperature 0. Each answer **cites the artifact file and section** it came from.
- If retrieval returns nothing relevant (similarity below a threshold), the chat answers: *"Not found in this run's artifacts."* It never answers from general knowledge.
- There is **no limit on the number of questions**. Access requires the passcode, and every question and answer is logged.

### 18.4 Guardrails, reproducibility & testing

| Concern | Rule |
|---|---|
| Reproducibility | Fixed embedding model and version, fixed chunk size and overlap, fixed `k` and threshold, and a **committed index for the reference run**. Index build parameters are recorded in `run_manifest.json` |
| Traceability | Every RAG answer and every Background claim has a citation. The Engineering Review agent rejects claims that have none |
| Safety | Background knowledge never becomes Evidence. Correlation is never presented as causation (§10) |
| Testing | Unit tests for chunking, retrieval and the refusal threshold, using a tiny fixed index. Playwright **E7** (§9.2) runs in CI with a mocked LLM and the committed index. Deployed E2E tests never call the chat (no LLM spending) |
| Cost | Embeddings are computed once per run and cached. Use a small embedding and chat model. The chat is passcode-protected but has no question limit, so watch LLM usage through the provider's spending cap |

**Done when:**

- similar-run evidence appears in `investigation.md`
- at least one hypothesis carries a cited Background source
- the chat answers with citations and refuses questions outside the artifacts
- all of the above is covered by tests
