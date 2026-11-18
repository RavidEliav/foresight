---
date: 2026-11-18
status: accepted
tags: [decision, rag]
---
# ADR-024 The chat also indexes the run's tables

## Context
Ravid asked "Ask Foresight" about a row of the Similar past runs table (run 1456, nearest distance 25102) and was refused: the chat only indexed the written reports ([[ADR-018 RAG with local embeddings, hybrid retrieval and validated citations]]), not the data behind the app's tables.

## Options considered
- Give the LLM tools to query the run's files
- Index the raw JSON/CSV files
- **Write the tables as text (`run_data.md`) and index it with the reports** (chosen)

## Decision
- `run_data.md` is written from the run's JSON/CSV files only (numbers copied, no LLM): model test metrics, risk ranking, anomaly detection, the similar-run method and overall result, the riskiest and most anomalous runs in order, and one section per run that appears in a table (scores, top signals, its similar past runs). A nearest distance far above the typical one (10x the median) is called out.
- Retrieval adds a strong boost when a number in the question matches a section title ("Run 1456").
- Runs indexed before this change are re-indexed on their next question.
- A list followed by a closing sentence that cites the excerpt counts as cited.
- Chat errors are logged (stdout and the run's chat log).

## Consequences
- Real check on the reference run: 10/10 in-scope questions answered with citations, 3/3 out-of-scope refused.
- The run index grows (the reference run's index has 102 chunks); retrieval stays well under a second.
- The file is human-readable, so a citation to `run_data.md § Run 1456` can be checked.
