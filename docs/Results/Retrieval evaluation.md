---
date: 2026-11-26
tags: [results, rag, evaluation]
---
# Retrieval evaluation of Ask Foresight

How well the chat finds the excerpts that answer a question, measured on the committed reference
run with the chat's own retrieval ([[ADR-018 RAG with local embeddings, hybrid retrieval and validated citations]]):
all-MiniLM-L6-v2 embeddings, cosine similarity plus the section-title boost, the
4 best excerpts, and the gate at similarity 0.25. No LLM is involved, so
the numbers are exact and repeatable.

- **Question set:** `config/eval/retrieval.yaml`, 28 questions with the file
  sections that answer them (any one counts), and 8 out-of-scope
  questions
- **Reproduce:** `python scripts/eval_retrieval.py`. `tests/unit/test_retrieval_eval.py` fails in
  CI if a result drops below these values.

## Results
- **hit@1:** 86% (the best excerpt answers the question)
- **hit@4:** 93% (a right excerpt is among the 4 the chat answers from)
- **MRR:** 0.89
- **Gate:** 8 of 8 out-of-scope questions refused before any LLM call; 0 of 28 in-scope questions refused

| Question | Rank | Best excerpt (score) |
|---|---|---|
| What is the model's test PR-AUC? | 1 | evaluation_report.md § Model comparison (PR-AUC; random guessing = fail rate) (0.68) |
| What is the recall on failing runs? | miss | engineering_report.md § Hypotheses (0.59) |
| Which model was selected, and by which rule? | 1 | model_card.md § Model purpose (0.42) |
| How do the candidate models compare? | 1 | evaluation_report.md § Model comparison (PR-AUC; random guessing = fail rate) (0.61) |
| Which sensors does the model rely on most? | 1 | evaluation_report.md § Most important sensors (permutation importance on the test period) (0.70) |
| Which sensors differ most between failing and passing runs? | 1 | insights.md § Notable sensors (0.81) |
| Is sensor f_059 associated with failures? | 1 | engineering_report.md § Hypotheses (0.83) |
| Did the data pass the Data Contract validation? | 2 | model_card.md § Training data (0.51) |
| How much data is missing after cleaning? | 1 | insights.md § Data quality (0.70) |
| How many runs and failing runs are in the data? | 1 | insights.md § What happened (0.68) |
| How did the fail rate change over time? | 1 | insights.md § What happened (0.55) |
| What are the hypotheses? | 1 | investigation.md § Hypotheses (0.57) |
| How confident are the hypotheses? | 1 | investigation.md § Hypotheses (0.44) |
| What should engineers do next? | 1 | engineering_report.md § Recommended next steps (0.28) |
| How should the hypotheses be verified? | miss | engineering_report.md § Hypotheses (0.37) |
| What facts did the investigation establish? | 2 | investigation.md § Assumptions (0.34) |
| What assumptions does the investigation make? | 1 | investigation.md § Assumptions (0.50) |
| What are the model's limitations? | 1 | model_card.md § Limitations (0.65) |
| What is the model intended to be used for? | 1 | model_card.md § Intended use (0.59) |
| Are there ethical considerations for this model? | 1 | model_card.md § Ethical considerations (0.72) |
| What data was the model trained on? | 1 | model_card.md § Training data (0.82) |
| What are the business implications? | 1 | insights.md § Business implications (0.43) |
| How many runs were flagged as anomalous? | 1 | run_data.md § Anomaly detection (0.68) |
| Which runs are the most anomalous? | 1 | run_data.md § Most anomalous runs (0.83) |
| Which test-period runs have the highest risk scores? | 1 | run_data.md § Riskiest test-period runs (0.84) |
| How many failing runs did the alarms catch? | 1 | run_data.md § Risk ranking (0.69) |
| Do similar past runs tell us whether a run will fail? | 1 | run_data.md § Similar past runs: method and overall result (0.62) |
| What do we know about run 1289? | 1 | run_data.md § Run 1289 (0.81) |

| Out-of-scope question | Best score | Refused |
|---|---|---|
| What is the capital of France? | 0.06 | yes |
| Write a short poem about the sea. | 0.07 | yes |
| Who won the 2018 football World Cup? | 0.11 | yes |
| How do I bake sourdough bread? | 0.11 | yes |
| What will the weather be tomorrow? | 0.14 | yes |
| Translate "good morning" into Spanish. | 0.11 | yes |
| Recommend a good movie for tonight. | 0.12 | yes |
| What is the price of Bitcoin today? | 0.18 | yes |

## Reading the results
- **The gate sits in the gap:** the strongest out-of-scope question scores 0.18 and the
  weakest in-scope question's best excerpt 0.28, with the gate at
  0.25. It is closer to the in-scope side: a vaguer real question can be
  refused, which is the safe direction (it never reaches the model).
- **Misses** are listed with rank "miss". The chat answers from the 4 excerpts it
  found; when none holds the answer it should reply "Not found in this run's artifacts.", and
  the citation check withholds an answer that cites an excerpt it was not given.
