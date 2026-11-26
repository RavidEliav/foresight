"""Phase 8.9: the retrieval evaluation of Ask Foresight on the reference run, written into the
vault (docs/Results/Retrieval evaluation.md). No LLM is called.

    python scripts/eval_retrieval.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from foresight.rag.evaluate import QUESTIONS, evaluate, markdown  # noqa: E402
from foresight.settings import load_settings  # noqa: E402

NOTE = ROOT / "docs" / "Results" / "Retrieval evaluation.md"


def main() -> int:
    settings = load_settings()
    report = evaluate(settings)
    in_scope = min(r.retrieved[0][1] for r in report.results if r.retrieved)
    off = max(score for _, score in report.out_of_scope)
    rag = settings.rag
    adr = "[[ADR-018 RAG with local embeddings, hybrid retrieval and validated citations]]"
    text = f"""---
date: {date.today().isoformat()}
tags: [results, rag, evaluation]
---
# Retrieval evaluation of Ask Foresight

How well the chat finds the excerpts that answer a question, measured on the committed reference
run with the chat's own retrieval ({adr}):
{rag.embedding_model} embeddings, cosine similarity plus the section-title boost, the
{rag.top_k} best excerpts, and the gate at similarity {rag.min_similarity}. No LLM is involved, so
the numbers are exact and repeatable.

- **Question set:** `{QUESTIONS.as_posix()}`, {len(report.results)} questions with the file
  sections that answer them (any one counts), and {len(report.out_of_scope)} out-of-scope
  questions
- **Reproduce:** `python scripts/eval_retrieval.py`. `tests/unit/test_retrieval_eval.py` fails in
  CI if a result drops below these values.

## Results
{markdown(report)}

## Reading the results
- **The gate sits in the gap:** the strongest out-of-scope question scores {off:.2f} and the
  weakest in-scope question's best excerpt {in_scope:.2f}, with the gate at
  {rag.min_similarity}. It is closer to the in-scope side: a vaguer real question can be
  refused, which is the safe direction (it never reaches the model).
- **Misses** are listed with rank "miss". The chat answers from the {rag.top_k} excerpts it
  found; when none holds the answer it should reply "Not found in this run's artifacts.", and
  the citation check withholds an answer that cites an excerpt it was not given.
"""
    NOTE.parent.mkdir(parents=True, exist_ok=True)
    NOTE.write_text(text, encoding="utf-8")
    print(f"hit@1 {report.hit1:.3f}  hit@{report.k} {report.hit_k:.3f}  MRR {report.mrr:.3f}  "
          f"gate leaks {len(report.gate_leaks)}  -> {NOTE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
