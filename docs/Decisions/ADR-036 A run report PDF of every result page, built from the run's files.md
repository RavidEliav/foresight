---
date: 2026-11-26
status: accepted
tags: [decision, report, ux]
---
# ADR-036 A run report PDF of every result page, built from the run's files

## Context
The requirements list an HTML or PDF version of `engineering_report.md` as an optional output. For 8.8, Ravid asked for more than that:
- the whole run in the PDF (Data Quality, EDA, Model, Investigation), not just the engineering report
- a download button in a main place that says it is the whole run, not one more button on Investigation & Report

## Options considered
- **PDF library:**
  - WeasyPrint (HTML to PDF): rejected, it needs system libraries (Pango, GTK) on Railway and Windows
  - the app's browser (Playwright, print to PDF): rejected, Chromium is not in the app's image
  - **fpdf2** (chosen): pure Python, about 0.3 MB, uses Pillow and fontTools, which matplotlib already brings
- **Where the button goes:** on Investigation & Report, in the top bar, or **in the sidebar under "Results shown"** (chosen by Ravid: on every page, and next to the choice of run it reports)

## Decision
- **Content** (`foresight/run_report.py`, about 10 A4 pages):
  - **Cover:** the run's facts (run, dataset, start, run time, model, report checks), a SYNTHETIC banner for scenario runs, the contents and the numbers at a glance
  - **1. Data Quality:** the Data Contract result, warnings and errors, the data, the cleaning decisions
  - **2. EDA & Insights:** the numbers, the Data Analyst crew's insights, fail rate over time, the sensors that differ most (table)
  - **3. Model:** the selected model and rule, test metrics with 95% CIs, the model comparison, four figures, and the model card's purpose, limitations and intended use
  - **4. Investigation & Report:** the headline numbers and the engineering report in full, then the anomaly scores
  - **5. Appendix:** the report's safety checks, the files cited and the run's facts (code version, seed, LLM, tokens, stage times, packages)
- **Traceability:** the crews' texts keep their `[source: ...]` and `[background: ...]` citations, in small gray type. A citation's tag is never split across lines.
- **Built only from the run's files:**
  - A new run saves `run_report.pdf` when it finishes; it is archived with its other files and listed in the manifest.
  - A run from before 8.8, or the reference run, gets the same report built on demand.
  - If the PDF cannot be made, the run still succeeds (logged).
- **The same run gives the same file:** the PDF's date is the run's start.
- **Fonts:** DejaVu Sans from matplotlib, so §, ≤ and → print.
- **The button:** "Download full run report" (accent) in the sidebar under "Results shown", with "All result pages of this run in one PDF". The same button sits beside "See the results" on Run Pipeline when a run completes.
  - The PDF is made when the button is pressed (a callable download), not on every page.

## Consequences
- One new runtime dependency (`fpdf2`, LGPL-3.0, used as a library) and one for tests (`pypdfium2`: reading the PDF's text and drawing its pages).
- Building the reference run's report takes about 1.4 s and gives 0.3 MB.
- Tests:
  - **Unit:** the sections, numbers and citations; the same bytes twice; a SYNTHETIC scenario; a run missing some files.
  - **App:** a finished run saves and lists the PDF, and both buttons are there.
  - **E3:** downloads the PDF from the sidebar.
