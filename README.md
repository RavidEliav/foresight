# Foresight

**Multi-agent semiconductor yield intelligence on SECOM.** A CrewAI Flow that validates fab sensor data, describes what happened, predicts which production runs will fail, investigates abnormal behavior, and writes a short, evidence-based engineering report.

Author: **Ravid Eliav** · AI Developers Course, Final Project

> **Status:** Phase 8 (feature improvements) is done and on `main`: the Supabase run registry and Trends page, the All runs chat, the Scenario Lab, the Line Replay with a simulated 3D wafer, stopping and resuming analyses, Google sign-in with access requests and roles, one screen per page and a phone view, the full report and every download as PDF, a retrieval evaluation with prompt-injection guards, and a product look (Home page, analyses with a number, plain names and sources). Next: Phase 9, the deliverables (README, slides, demo video) for Dec 4. After the submission: voice, an MCP server and a light mode.

| Environment | Branch | URL |
|---|---|---|
| `main` (stable) | `main` | https://foresight-ai.up.railway.app |
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

**Mock or real LLM.** With `MOCK_LLM=true`, a deterministic mock LLM writes the outputs from the same facts and goes through the same CrewAI agents, tasks and checks. Tests and CI use it, and a session guard makes any paid call fail a test. With the real model (`gpt-4o-mini`, temperature 0), a full run takes about 2.5 minutes on Railway and about 25,500 tokens (under 1 US cent). CrewAI's cloud tracing and telemetry are turned off: they added about 15 seconds per crew, and Foresight keeps its own logs and run manifest.

**Reference run.** [`artifacts/reference/`](artifacts/reference) holds a complete real run (gpt-4o-mini, all gates and all 26 report checks PASS, no revisions, with its summary and chat index). The app shows it until a newer run exists.

## RAG and embeddings

Three extensions from requirements §18. Embeddings use a fixed local model (**all-MiniLM-L6-v2** through ONNX Runtime, 384 dimensions): free, no API key, downloaded once (about 80 MB) into `paths.models_dir` (on Railway the container's own disk, so the runs volume keeps its space for runs).

| Extension | What it does | Where |
|---|---|---|
| **Similar-run search** | Each run's sensor profile is embedded (median imputation, scaling and PCA with 30 components, all fitted on training runs). For the riskiest and the failing test runs, the 5 most similar *past* runs are retrieved with their labels and distances. The evidence is reported honestly: on SECOM the neighbours of failing test runs failed 5.8% of the time vs 4.7% for passing ones (training fail rate 6.8%), so a run's overall profile says little about failure | `similar_runs.json`/`.csv`, tool `find_similar_runs`, run map on the Report page |
| **Knowledge base** | 12 short background documents written for this project from public sources ([`knowledge/SOURCES.md`](knowledge/SOURCES.md)): SPC, robust statistics, yield loss, drift and maintenance, FDC, SECOM, metrics, multiple testing, anomaly detection, missing data, verification practice. Passages are retrieved deterministically for the evidence types in the report and given to the Investigation crew with their exact citations; hypotheses cite them as `[background: file § section]`, labelled Background, never Evidence | `knowledge/`, tool `search_knowledge` |
| **Ask Foresight** | A chat about the run shown in the sidebar. The run's reports, plus `run_data.md` (the run's tables written out as text from its JSON/CSV files: model metrics, risk ranking, anomalies, similar-run method, the riskiest and most anomalous runs in order, and one section per run that appears in a table, e.g. "Run 1456" with its scores, top signals and similar past runs), are chunked by section (800 characters, 120 overlap) and indexed at the end of the run (`rag_index.npz`, `rag_chunks.json`; parameters in `run_manifest.json`); a run indexed before `run_data.md` existed is re-indexed on its next question. Retrieval is hybrid: cosine similarity plus a bonus when the question's words match a section title, and a larger one when a number in the question (a run id) does. Below similarity 0.25 the chat answers "Not found in this run's artifacts." without calling the LLM; otherwise gpt-4o-mini answers only from the retrieved excerpts, citing `[source: file § section]`, or refuses. An answer that cites no retrieved excerpt is withheld, and so is one that repeats the chat's instructions or holds anything shaped like a secret, states a cause, or uses a number that is not in the excerpts (one more try first, except for leaks; Phase 8.9, `tests/unit/test_injection.py`). Live, 23 prompt-injection attacks on gpt-4o-mini got no unsafe answer through, and 8 of 8 ordinary questions were still answered (`python scripts/eval_injection.py`, results in `docs/Results/Prompt injection evaluation.md`). The retrieval is measured on 28 questions about the reference run (`python scripts/eval_retrieval.py`: hit@1 86%, hit@4 93%, every out-of-scope question refused before any LLM call; results in `docs/Results/Retrieval evaluation.md`) Every question and answer is logged with who asked (`chat_logs/<run>.jsonl` in the runs folder), including questions that failed with an error; there is no question limit | page *Ask Foresight* |

A question costs about 600–1,100 tokens (well under 0.1 cent).

**Cross-run memory (pgvector).** When the registry records a successful run, it also stores the run's chat chunks with their embeddings (already computed for the run's own index, so nothing is embedded twice) in `foresight.chunks` (`vector(384)`, HNSW cosine index, same private schema and RLS). "Ask Foresight" in **All runs** mode embeds the question, takes the 40 nearest chunks across all runs from Postgres, re-ranks them with the same section-title bonus as a single run, and answers from the best 6 (`rag.all_runs_k`) with the same refusal threshold and citation checks; each excerpt's header names its run, and the prompt lists the runs (start time and data). A comparison may close with a summary paragraph without a citation only if every number in it appears in the retrieved excerpts. Without Supabase, the successful runs' own indexes on the server are merged instead. Questions about all runs are logged as `chat_logs/all_runs.jsonl`.

## The app

| Page | What it shows |
|---|---|
| Home | Where the app opens: what Foresight does, **Start a new analysis** and **Ask Foresight** buttons, an analysis that is running (with a link to follow it), the analysis shown at a glance (failing runs caught, alarm precision, model PR-AUC, sensors that differ), its top finding with a link to the findings, and your recent analyses and questions |
| New analysis (was Run Pipeline) | Dataset choice (built-in SECOM, an uploaded CSV, or a synthetic **Scenario**), live progress as five stage tiles (green done, red failed, gray skipped, amber interrupted or stopped, cyan with a small animation of the stage's work while it runs; each tile also shows its crew's status) joined by the checks; **Stop analysis** while one is going (it stops within a few seconds, so a different run can start); **Resume analysis** for a stopped, interrupted, timed-out or crashed run; a stopped run says why in plain language and what to do (developers also get the technical details); the analysis history in local time (status, duration, report checks, why it stopped; developers also see tokens and who started each run) |
| Data quality | Headline numbers, Data Contract validation (the checksum warning every upload gets is explained as expected), cleaning decisions; all checks and the contract under Extended data |
| Data insights (was EDA & Insights) | Headline numbers (with a weekly fail-rate sparkline), the Data Analyst crew's summary, interactive fail rate over time and sensor differences; sensor statistics, missing data and the full insights under Extended data |
| Model | Test metrics with 95% CIs vs random, the selected model and its alarms, interactive risk over time, precision-recall curve, alarms vs outcomes and sensor importance; model comparison, evaluation report and model card under Extended data |
| Findings (was Investigation & Report) | Headline numbers (failing runs caught, alarm precision, anomaly lift, sensors out of limits, similar runs that failed), key findings and one card per hypothesis (confidence, evidence, how to verify), the anomaly timeline, the run map (2D/3D) and a simulated 3D wafer of any test-period run (riskiest first); the engineering report (download), full investigation, risk ranking, similar runs, anomalies and the safety checks under Extended data |
| Line replay | The run's test period played back run by run, in time order (Play/Pause, next run, end, 4 speeds, a position slider): running totals (runs replayed, alarms, failing runs caught, alarm precision), the risk score of each run as it comes off the line with the alarms appearing as rings, the latest alarms, and a **simulated 3D wafer** of the newest run. Nothing is re-scored: the alarms are the run's own alarm budget, so the totals at the end match the Investigation & Report page. SECOM has no die positions, so the wafer is a labeled simulation reproducible from the run id (scattered defects grow with the risk score; a failing run also gets one typical defect pattern: cluster, edge ring, scratch or center) and feeds nothing back into the analysis |
| Trends (developers) | Every recorded run over time, from the run registry: runs, median run time and tokens, latest PR-AUC; model quality over runs (PR-AUC and fail recall against random guessing), where the run time goes (seconds per stage, crews included), LLM tokens per run, run outcomes with their reasons; the full run table under Extended data. A filter picks the data source (SECOM, upload, reference) |
| Ask Foresight | Chat about the selected run, answered only from its reports, with citations (developers also see the sources and similarity scores); the assistant's avatar is the Foresight logo. **All runs** switches the chat to every recorded run: the answer says which run each statement is about and cites it; sources show as chips with plain names ("Analysis 12 › Insights › Data quality"; the stored tag is `[source: <run id>/<file> § <section>]`). The sidebar lists your recent questions about the run and about all runs (from the chat logs); a click opens the answer in its scope |
| My activity | Your own runs (started, resumed or stopped, kept in the registry after the run folder is pruned) and your chat questions; a developer can choose anyone with an account and see theirs |
| Users & access (developers) | Waiting access requests (approve or deny), adding a person with a role, the account list, changing a role or removing access |

**Sign-in and roles.** The whole app is behind **Google sign-in** (Streamlit's `st.login`, OpenID Connect; `app/auth.py`), with Google's account picker so a person with several Google accounts chooses which one to use. Someone new signs in, then asks for access (with an optional message): the request is stored and the developers get an email (Resend's HTTP API, since Railway blocks SMTP) with the requester's details and **Approve** / **Deny** links. A link carries a signed token (HMAC with `AUTH_COOKIE_SECRET`) naming that one request; it expires after 7 days, stops working once the request is decided or renewed, and opens a page that asks for one more click, so a mail scanner that opens links decides nothing. From then on the person only clicks "Continue with Google". There are no passcodes.
- A session ends on **Sign out**, when the **browser closes** (the sign-in cookie is a session cookie: Streamlit's 30-day cookie is shortened, and a test fails if a Streamlit upgrade changes how it is set) and after **an hour without activity** (a clock per sign-in, saved on the runs volume so a restart does not reset it; an open page is signed out without waiting for a click).
- Two roles. **Users** get New analysis (run, stop, resume), the result pages' headline numbers, charts and hypothesis cards, the engineering report download, Line replay, Ask Foresight and My activity. **Developers** (`FORESIGHT_DEVELOPERS`, always approved, plus anyone given the role) also get the environment badge, technical details (failed-run details, tokens, chat sources), every Extended data section, Trends and Users & access. Users see only their own runs (in the run picker, the run history and the All runs chat) plus the reference run; developers see every run.
- After signing in, "Hi, <first name>" sits at the top right of every page (the account menu: My activity, Privacy, Terms, Sign out), and a greeting appears once per sign-in. Runs record who started, stopped or resumed them (`progress.json`, the registry's `started_by`), and chat questions who asked.
- Accounts live in Supabase (`foresight.accounts`, private schema, RLS, no client access), else in `.access/accounts.json` on the runs volume; each environment approves separately. The Privacy and Terms pages are public (Google's consent screen links to them).
- A local checkout without `GOOGLE_CLIENT_ID` (and CI) opens as a local developer; on Railway sign-in is always required, and without the keys nobody gets in.

The sidebar starts with the Foresight wordmark (its "o" is the wafer logo) and the page menu. **Analysis shown** picks which successful run the result pages display (a short label, the full description under it); it follows the newest run until you choose another one, and the committed reference run is always available. Times are shown in the viewer's time zone (from the browser). A run made before a feature existed says so instead of hiding the section.

**Design.** A dark "cleanroom" theme (`.streamlit/config.toml`): cyan and violet for lithography light, amber (the fab's yellow-room light) for failing runs, a faint die-grid background, a wafer logo, frosted-glass cards, tiles and sidebar (`app/ui.py`). Each page leads with its headline numbers and main charts; the long tables and documents sit under **Extended data**.

**A product, not a project (Phase 8.10).** Each run is an *analysis* with a number ("Analysis 12 · SECOM · 25 Nov, 15:18"): its place in start order among all the analyses the environment recorded, so the number needs no storing and does not change; the committed one is the "Reference analysis". The name is used in the sidebar, the top line of every page (short, with the details in its tooltip), the analysis history, My activity, Trends and the PDF (`app/runs.py`, `store.analysis_numbers`). It also keeps the pipeline's runs apart from SECOM's production runs ("Run 1289"). The menu speaks to process engineers: New analysis, Data quality, Data insights, Model, Findings, Line replay; the AI steps are "AI data analyst", "AI data scientist", "AI investigator" and "AI report writer", and checks between steps are "checks". Downloads say what they are ("Download the engineering report") and are all PDFs, saved as `Foresight - Analysis 12 - Engineering report.pdf`: the engineering report, the investigation, the model card, the evaluation report (its tables as tables), the Data insights (numbers, insights, the fail-rate chart and the sensors that differ; it replaces the HTML data report) and the Data Contract (its rules, assumptions, the sensors left out and every sensor's range). They are made when the button is pressed, from the run's files, in the reader's time zone (`run_report.document`). Only the upload template and the SECOM example stay CSV files. `main` shows no environment badge. The app opens on a **Home** page (`app/home_page.py`); New analysis moved to `/new`. The sign-in page is one centred card: the Foresight wordmark, what it does for an engineer, a white **Continue with Google** button with Google's G, and Privacy and Terms below; no sidebar. Less of Streamlit shows: no colour strip on top, the spinner is the Foresight logo turning, the browser tab says the page ("Findings · Foresight"), and while a page works a thin cyan line runs across the top (only after 0.6 s, so the timed refreshes don't flash it). Sources read as plain names: the AI's citation tags stay in its stored text (the checks read them), but the chat, the result pages and the PDF show `[source: 20261118T201632841000Z/insights.md § Data quality]` as a chip, "Analysis 12 › Insights › Data quality", and `[source: model_metrics.json]` as "Model metrics" (`foresight/sources.py`); run ids in a cross-analysis answer become analysis names.

**Run report (Phase 8.8).** "Download the full report" in the sidebar, under the choice of run, gives every result page of that run in one PDF (about 10 pages): a cover with the run's facts and the numbers at a glance, Data Quality, EDA & Insights, Model (metrics with confidence intervals, the model comparison, figures, the model card's purpose and limits), Investigation & Report (the engineering report in full, with its citations) and an appendix with the report's safety checks and the run's facts. A new run saves it as `run_report.pdf`; older runs and the reference run get it built from their files when the button is pressed. Built with `fpdf2` (`src/foresight/run_report.py`).

**One screen per page (Phase 8.7).** The main part of every page fits a laptop's browser window (1920×1080 at 125%, about 1536×730) without scrolling. To get there, charts and cards share a card through tabs (Model, EDA, Trends, Line Replay, Investigation & Report, My activity), and the "Hi, name" menu sits on the title's line. Only Extended data and technical details need scrolling, and Extended data is a row of tabs that stay closed until one is pressed. Run Pipeline fits with a run in progress and the run history closed. On Ask Foresight the title and the question bar stay in place and the conversation scrolls in its own box. On Line Replay, Play and Pause redraw the same elements in the same places, so the page does not jump. A phone's browser (its user agent says Mobile) gets a phone view, and every page fits an iPhone's Safari with its bars shown (390×664). Each page's cards become the tabs of one card, charts are lower, the headline tiles compact, long tabs scroll inside the card and Extended data is one dropdown. Run Pipeline's stages become one-line rows. Text fields use 16 px, so tapping one does not zoom the page, and 2D charts are still pictures, so a pinch zooms them like the rest of the page (Plotly has no pinch zoom of its own); 3D charts keep their own pinch and turn. Tables are plain tables on a phone, so a swipe on one scrolls the page (Streamlit's grid kept it). Every table is as wide as its content: each column fits its header and longest value, and a table with long text, or one wider than the page, wraps its cells instead of cutting columns off. Check it with `python scripts/measure_fit.py` (every page at laptop, desktop and phone size, with screenshots) or the E9 test. Charts are Plotly (`app/charts.py`): hover for run ids and values, zoom, and a 3D run map. Fonts (Inter, Space Grotesk, JetBrains Mono) load from Google Fonts.

**Background runs.** "Run analysis" starts `python -m foresight.cli run` as a separate process, so a run continues when the page is refreshed or closed. The run writes `progress.json` (stages, gates, a heartbeat every 15 s) and `run.log` into its folder. Guards (`app` in `config/settings.yaml`):

- one run at a time and at most 6 runs per hour (cost control),
- a timeout guard stops a run after 20 minutes and records why,
- **Stop analysis** writes `stop.requested` into the run folder; the run's process checks every second, records the run as stopped (in the history and the registry, with `failure_report.md`) and exits, keeping the stages it had finished,
- a run that was stopped, or whose heartbeat stopped (for example after a redeploy, shown as interrupted), can be **resumed**: the stages it had finished are reused (their files, gate checks and crew usage are kept in `progress.json`), the data is re-read, and the rest runs again; a resume counts toward the hourly limit. A run stopped by a gate is not offered a resume (the same data would stop again),
- **Stop analysis** and **Resume analysis** sit beside **Run analysis**. While a run is going, Run analysis is grayed out for the same data. Choosing other data (another dataset, upload or scenario setting) lights it up again, and it then stops the running run (which can be resumed later) and starts the new one,
- a run that stopped sending updates says why: the storage was full, the run crashed (its last error), the app restarted, or the process stopped without a word (usually memory); Start and Resume first check for 50 MB free,
- with Supabase Storage configured, every finished run is archived there and the server keeps only the newest 3 whole (older runs keep a few-KB stub, and their files are downloaded again when you pick one); without it, the newest 10 finished runs are kept.

**Uploading data.** A CSV with `timestamp` (`dd/mm/yyyy HH:MM:SS` or ISO 8601), `label` (-1 pass, 1 fail) and the 590 sensor columns in SECOM order. The page always offers a small template (`app/assets/upload_template.csv`: the columns in order with 10 SECOM runs, 2 of them failing) and, on request, all of SECOM in this format (about 6 MB, downloaded from UCI first if the server has no copy yet). Uploads are cleaned with the committed Data Contract's feature list (so a smaller or newer batch stays comparable) and validated like the built-in data; a broken file stops at the contract gate with the failed checks listed.

From a terminal: `python -m foresight.cli run [--dataset file.csv] [--timeout 600]`, or `python -m foresight.cli run --run-id <id> --resume` to resume a run.

**Scenario Lab (synthetic data).** The third dataset choice builds a synthetic variation of SECOM, reproducible from its seed:
- **planted fault:** one sensor shifted on the failing runs, a known cause
- **sensor drift:** a few sensors ramp up over time
- **sensor outage:** a few sensors missing for a stretch
- **noisy line:** extra noise on every sensor

A scenario changes **only the training period**. The test period stays the original SECOM runs, so every evaluation metric, PR-AUC included, is computed on real data only and is comparable with a run on the real data. The ingest stage enforces this: a Data Contract check (`test_period_is_original_secom`) cleans the original data too and stops the run if a single test-period value differs.

Synthetic data is labeled and kept separate:
- The recipe and ground truth are in `scenario.json`, and the generated data in `scenario_data.csv`, in the run folder. The SECOM files are never modified.
- The run's dataset reads "Scenario (synthetic): …".
- Every result page shows a SYNTHETIC badge.
- The manifest records the scenario, the engineering report opens with a deterministic SYNTHETIC note, and Trends lists the run as Synthetic.

At the end of the run, `scenario_check.json` records whether the analysis found the change:
- each changed sensor's rank among the sensors that differ most (EDA)
- its rank in model importance on the real test period
- whether the investigation or report names it

A planted fault that the analysis misses makes the report check `scenario_ground_truth` a WARNING. On SECOM with the default settings, the planted sensor ranks first in the EDA.

**Run registry (Supabase).** Every finished, failed or timed-out run writes one summary row (status, times, data rows and fail rate, selected model and its test metrics, anomaly lift, tokens, gates, report checks, the full manifest) and one row per stage to **Supabase Postgres**, so the history survives pruning and redeploys and the Trends page can chart it. Each Railway environment has its own Supabase project (`foresight-dev`, `foresight-main`). The app connects from the server only, through the **Session pooler** (`SUPABASE_DB_URL`, IPv4); no key reaches the browser. The tables live in a private schema `foresight` that is not exposed to Supabase's REST API, the client roles get no privileges, and Row Level Security is enabled with no policies (deny by default). The schema is a versioned migration in [`supabase/migrations`](supabase/migrations). Without `SUPABASE_DB_URL` (tests, a local checkout), the same rows are built from the run folders, and a database problem never fails a run (it is logged). `python -m foresight.cli registry-sync` records every run still on disk and the reference run (backfill).

**Run files and chat history in Supabase (ADR-033).** The Railway volume is 500 MB and filled up on 2026-11-22. Now everything a run leaves behind is kept in Supabase:
- **Files:** when a run ends, its folder is packed into one `<run id>.tar.gz` (a few MB) in the private Storage bucket `runs`, using the project's secret key (`SUPABASE_SECRET_KEY`, server-side only; there are no storage policies, so the client roles cannot read it). The registry row also gets the run's whole progress.
- **The volume** keeps the newest 3 runs whole and, of older ones, only `progress.json`, `run_manifest.json` and `archived.json`, so every list, label and history works. Picking an older run in the sidebar, or resuming it, downloads its files again. On a new or wiped volume the app rebuilds these stubs from the registry at startup.
- **Chat history** goes to `foresight.questions`; the old `chat_logs/*.jsonl` files are imported at startup and deleted. If the database cannot be reached, a question is written to the file meanwhile and imported later.
- A Storage problem never fails a run: a run folder stays whole until it is safely archived.

## Performance

Measured, then changed without changing any result: `scripts/compare_runs.py <run>` compares every number in a run's analytics outputs (JSON summaries and CSV tables) with the reference run and must report 0 differences.

| | Before (Phase 6) | After (Phase 7) |
|---|---|---|
| Real run on Railway (`dev`) | 3.3–3.6 min | 2.5 min |
| Mock run, local (deterministic work only) | 168 s | 87 s |
| Model stage, local | 118 s | 57 s |
| Peak memory of a run process | 973 MB | 640 MB |
| App server after visiting every page and asking the (mock) chat | 521 MB | 323 MB (the real chat adds about 30 MB for the OpenAI SDK) |
| `dev` service at rest after a real run | 1,239 MB | 445 MB |

What changed:
- **Crews in the background:** the Data Analyst crew writes its insights while the models train, and the Data Scientist crew writes the model card while the investigation runs; the Flow waits for both before the report. Each takes its fact sheets and the numbers its checks accept when it starts, from the same files a sequential run would see.
- **Bootstrap confidence intervals** use the same metrics in plain NumPy (tested equal to scikit-learn), about 28 s faster.
- **Permutation importance** scores its (pre-drawn) shuffles in parallel threads.
- **Embeddings** are computed in batches of 8: ONNX Runtime keeps memory for the largest batch it has seen (100 chunks at once cost about 430 MB).
- **The app no longer imports the pipeline:** run ids come from `progress.py` instead of the Flow (CrewAI and scikit-learn stayed out of the app: about 270 MB), the chat calls the OpenAI SDK directly instead of CrewAI's LLM wrapper (about 70 MB and 3 s on the first question), and the precision-recall chart is computed with NumPy.
- **Data access in one module:** every page reads runs, starts and continues runs and asks the chat through `app/store.py` (a test enforces it), so a later split into a UI service and an API service only replaces that module.

Measure yourself: `python scripts/measure_run.py [--real]` (time and peak memory per stage) and `python scripts/measure_app.py` (app memory per page); both need `psutil` (in `requirements-dev.txt`).

## Quick start

Requires **Python 3.11** (CrewAI supports 3.10–3.13).

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env          # then fill in OPENAI_API_KEY (Google keys optional locally)
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
| E0 | Visitors see only the sign-in screen (a deep link too); Privacy and Terms are public | `dev`, `main` (skipped by an app without sign-in) |
| E1 | App loads, environment badge | CI |
| E2 | Every result page shows its content (headline tiles, interactive charts) | CI |
| E3 | Headline numbers, key findings and hypothesis cards; Facts / Assumptions / Hypotheses labels; report download | CI |
| E4 | A forged approve/deny link decides nothing | CI, `dev`, `main` |
| E5 | Broken CSV upload stops at the contract gate with a plain-language error and the failed checks under Technical details | CI only (starts a run) |
| E6 | Full run: live progress through all crews, then the new run's report | CI only (mock LLM) |
| E7 | Ask Foresight: an answer with a citation; an off-topic question gets "Not found in this run's artifacts." | CI only (mock LLM) |
| E8 | Line replay plays the reference test period and ends on 5 of 24 failing runs caught | CI |
| E9 | Every page's main part fits a laptop window (1536×730); on a phone (390×844) the headline is on the first screen | CI |

The deployed apps need Google sign-in, which a test browser cannot do, so the deployed suite (`-m deployed`) checks what a visitor sees before signing in; it is read-only and never spends LLM tokens. E1–E9 run in CI against a local app without Google keys (it opens as a local developer); start it with `MOCK_LLM=true` and, for speed, `FORESIGHT_CONFIG=tests/fast_settings.yaml`. Sign-in itself (users, developers, access requests, emailed links, the idle sign-out) is covered by AppTest with a simulated Google user (`tests/app/test_sign_in.py`).

## Release workflow

`feature/*` → PR into `dev` (CI + local E2E) → auto-deploy to Railway `dev` (smoke + E2E) → PR `dev → main` (CI + E2E) → auto-deploy to `main` (smoke + E2E, rollback on failure).

- `.github/workflows/ci.yml`: PR gates
- `.github/workflows/deployed-tests.yml`: post-deploy gates (needs repository variables `DEV_URL` and `MAIN_URL`)

## Deployment (Railway)

One project `foresight`, service `foresight-app`, environments `main` and `dev`. The service is defined with Railway Infrastructure as Code in [`.railway/railway.ts`](.railway/railway.ts): start command, health check, non-secret variables, a **volume** `foresight-runs` (500 MB, one per environment) mounted at `/app/runs` so runs survive redeploys, and a GitHub source whose branch follows the environment name. Railway's Railpack builder reads `.python-version` and `requirements.txt`. Secrets (`OPENAI_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `AUTH_COOKIE_SECRET`, `FORESIGHT_DEVELOPERS`, `RESEND_API_KEY`) are set in Railway with the same values in both environments: fill them in your local `.env`, then run `.\scripts\push_secrets_to_railway.ps1` (values are never printed; a missing `AUTH_COOKIE_SECRET` is generated), and the next deploy loads them. The IaC file keeps them with `preserve()`. The app writes the `[auth]` section `st.login` needs to `.streamlit/secrets.toml` (git-ignored) from these variables, with the redirect URI built from Railway's public domain.

**Google sign-in.** An OAuth client (Web application) in Google Cloud, published to production, with the redirect URIs `https://<dev and main domains>/oauth2callback` and `http://localhost:8501/oauth2callback`, and the app's home page, `/privacy` and `/terms` on the consent screen.

**Supabase.** Two free projects, `foresight-dev` and `foresight-main` (region East US, near the Railway volume). Put each project's Session pooler URL (Dashboard → Connect → Session pooler, with the database password) in `.env` as `SUPABASE_DB_URL_DEV` and `SUPABASE_DB_URL_MAIN`; the push script gives each Railway environment its own `SUPABASE_DB_URL`. For the run files, also put each project's secret key (Dashboard → Project Settings → API Keys → Secret keys, `sb_secret_...`) in `.env` as `SUPABASE_SECRET_KEY_DEV` and `SUPABASE_SECRET_KEY_MAIN`; the project URL is derived from the database URL. A local checkout uses Supabase only when `SUPABASE_DB_URL` itself is set (office networks often block Postgres ports). Every deploy runs `python scripts/db_migrate.py` as Railway's **pre-deploy command**: it applies the migrations its project has not had (recorded in `supabase_migrations.schema_migrations`, the Supabase CLI's table), so `dev` migrates the dev project and `main` the main project; a failing migration stops the deploy, an unreachable database does not. On startup the app records the runs on its volume in the background (backfill; `python -m foresight.cli registry-sync` does the same from a shell). Supabase's security and performance advisors run over HTTPS with an access token:

```powershell
$env:SUPABASE_ACCESS_TOKEN = "<token>"   # Supabase account → Access Tokens
npx supabase@3.2.0 db advisors --remote=<project-ref> --type all
```

Apply a configuration change (after merging it):

```powershell
cd .railway; npm install; cd ..
railway link --project <project-id> --environment dev;  railway config plan; railway config apply
railway link --project <project-id> --environment main; railway config plan; railway config apply
```

Code changes deploy automatically when a branch is merged (`dev` → dev environment, `main` → main environment).

## Project structure

```
app/            Streamlit app (entry point: app/streamlit_app.py; store.py all access to run data, ui.py style, charts.py Plotly, stepper.py stage tiles, messages.py plain-language errors, trends_page.py run registry, assets/ logo)
.streamlit/     theme (config.toml)
config/         settings.yaml (seed, LLM model, paths)
src/foresight/  flow.py, jobs.py + cli.py (background runs), progress.py, data/, analytics/, crews/, rag/, registry/ (Supabase run registry), tools/, validation/, utils/
supabase/       Supabase CLI project: config.toml and versioned SQL migrations
knowledge/      background documents for the Investigation crew (+ SOURCES.md)
tests/          unit/, integration/, app/, smoke/, e2e/
scripts/        data download, helper scripts, db_migrate.py (Railway pre-deploy), measure_run.py / measure_app.py / compare_runs.py (performance), measure_fit.py (one screen per page)
data/           raw/ and processed/ (not committed)
artifacts/      committed reference run
docs/           Obsidian vault: requirements, decisions, results, lessons learned
```

## License

MIT, see [LICENSE](LICENSE).
