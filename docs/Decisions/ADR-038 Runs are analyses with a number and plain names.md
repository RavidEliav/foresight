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
- **Downloads:** "Download the engineering report", saved as `Foresight - Analysis 12 - Engineering report.md`. The full PDF is "Download the full report".
- **`main` shows no environment badge.** `dev` and a local checkout still do.

## Consequences
- A deleted registry record would renumber the later analyses; nothing deletes records.
- Without Supabase, the numbers come from the run folders on this server.
- The tests, the end-to-end tests and the README follow the new names.
- The home page, the Streamlit look and the sign-in page are the next 8.10 PR; readable sources and the developer's My activity for anyone are the third.
