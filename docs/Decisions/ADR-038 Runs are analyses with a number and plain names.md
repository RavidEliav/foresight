---
date: 2026-11-26
status: accepted
tags: [decision, ux]
---
# ADR-038 Runs are analyses with a number and plain names

## Context
Ravid asked for Foresight to look like a real app rather than a developer's project (step 8.10, before the close-out). A first look found:
- **Runs:** named by timestamps and ids (`20261125T152828…`, "25 Nov, 15:18 · SECOM").
- **Pages and messages:** data-science and CrewAI words such as "EDA & Insights", "Investigation & Report", "crew", "gate", "Run pipeline".
- **Downloads:** file names as labels ("Download engineering_report.md").
- **On `main`:** the environment name shown in the sidebar.

"Run" also meant two things: a pipeline run, and SECOM's production runs ("Run 1289").

## Options considered
- **Naming:**
  - **Store a number in each run when it starts:** rejected. Older runs have none, and two environments would need a counter.
  - **Let people name their runs:** left out for now. It needs a field, and a name nobody gives is worse than a number.
  - **Number each analysis by its place in start order** (chosen). Run ids are UTC start times, so sorting all recorded ids gives the numbers without storing anything, and they do not change.
- **Audience:** process engineers (Ravid's choice). Keep the metric names they know with tooltips; remove internal words.

## Decision
- **Analyses:**
  - A pipeline run is an **analysis**: "Analysis 12 · SECOM · 25 Nov, 15:18". The number is the run's place among the ids in the run registry and the run folders on the server (`store.analysis_numbers`, cached 20 s).
  - The committed run is the **Reference analysis**.
  - Production runs keep the word "run".
- **Where the name is used:**
  - the sidebar's **Analysis shown**
  - the top line of every result page: short, with the dataset, start time and synthetic note in its tooltip
  - the analysis history and My activity
  - Trends
  - the PDF's cover, footer and file name
- **Menu:** New analysis, Data quality, Data insights, Model, Findings, Line replay, Ask Foresight and My activity. Developers also get Trends and Users & access. The page addresses are unchanged, so saved links still work.
- **Words:**
  - "AI data analyst", "AI data scientist", "AI investigator" and "AI report writer" instead of crews
  - "checks" instead of gates
  - "Run analysis", "Stop analysis" and "Resume analysis"
  - failure messages that point at the Resume analysis button, which is above them since #58
- **Downloads:** "Download the engineering report", saved as `Foresight - Analysis 12 - Engineering report.pdf`. Every download is a PDF (PR 4, #77, Ravid: markdown is no use to a user): each document is built like the full report, and the Data insights PDF replaces the HTML data report. The upload template stays a CSV, since it is data to fill in. The full PDF is "Download the full report".
- **`main` shows no environment badge.** `dev` and a local checkout still do.

## Consequences
- A deleted registry record would renumber the later analyses; nothing deletes records.
- Without Supabase, the numbers come from the run folders on this server.
- The tests, the end-to-end tests and the README follow the new names.
- PR 2 (#75) added the rest of the look: the app opens on a Home page (New analysis moved to `/new`), the sign-in page is one centred card with a "Continue with Google" button, the spinner is the Foresight logo, the tab title names the page, and a thin cyan line at the top shows that a page is working (Streamlit's own badge is not shown with `toolbarMode = "minimal"`).
- PR 3 (#76): sources by plain names. The tags stay in the stored text, since the chat's citation guard and the report checks read them; only what is shown changes (`foresight/sources.py`: chips in the app, "(Model metrics)" in the PDF, its appendix "Sources cited"). A developer's My activity has an "Activity of" picker over the accounts.
