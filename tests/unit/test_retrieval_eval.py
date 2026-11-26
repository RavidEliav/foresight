"""The retrieval evaluation (Phase 8.9) as a regression guard: Ask Foresight must keep finding
the excerpts that answer the question set, and keep refusing out-of-scope questions before
any LLM call. The floors are the measured values (scripts/eval_retrieval.py writes the full
results into docs/Results)."""

from foresight.rag.evaluate import evaluate
from foresight.settings import load_settings

HIT_1, HIT_K, MRR = 0.85, 0.92, 0.88  # measured 2026-11-26: 0.857, 0.929, 0.893


def test_ask_foresight_finds_the_answering_excerpts_and_refuses_off_topic_questions():
    report = evaluate(load_settings())
    assert len(report.results) >= 25 and len(report.out_of_scope) >= 8
    assert report.hit1 >= HIT_1 and report.hit_k >= HIT_K and report.mrr >= MRR, (
        f"hit@1 {report.hit1:.3f}, hit@{report.k} {report.hit_k:.3f}, MRR {report.mrr:.3f}")
    assert report.gate_leaks == []  # no out-of-scope question reaches the model
    assert report.in_scope_refused == []  # and no real question is refused
