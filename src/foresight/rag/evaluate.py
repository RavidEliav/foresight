"""Retrieval evaluation (Phase 8.9): does Ask Foresight find the excerpts that hold the answer?

A fixed question set about the committed reference run (``config/eval/retrieval.yaml``), each
question with the file sections that answer it. Measured with the chat's own retrieval
(hybrid: dense cosine plus the section-title boost, the ``rag.min_similarity`` gate):

- hit@1: the best excerpt is a right one
- hit@k: a right one is among the ``rag.top_k`` excerpts the chat answers from
- MRR: the mean of 1 / rank of the first right excerpt (0 when none is in the top k)
- gate: every out-of-scope question is refused before any LLM call (no excerpt reaches
  ``rag.min_similarity``), and no in-scope question is refused

No LLM is involved, so the numbers are exact and repeatable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from foresight.rag.index import (
    VectorIndex,
    content_words,
    embed_question,
    retrieve,
    run_index,
)
from foresight.settings import Settings

QUESTIONS = Path("config/eval/retrieval.yaml")


@dataclass
class Result:
    question: str
    gold: list[str]
    retrieved: list[tuple[str, float]]  # (file § section, score), best first
    rank: int | None  # 1-based rank of the first right excerpt within the top k

    @property
    def hit1(self) -> bool:
        return self.rank == 1

    @property
    def hit(self) -> bool:
        return self.rank is not None


@dataclass
class Report:
    k: int
    min_similarity: float
    results: list[Result]
    out_of_scope: list[tuple[str, float]]  # (question, best score)
    in_scope_refused: list[str] = field(default_factory=list)

    @property
    def hit1(self) -> float:
        return sum(r.hit1 for r in self.results) / len(self.results)

    @property
    def hit_k(self) -> float:
        return sum(r.hit for r in self.results) / len(self.results)

    @property
    def mrr(self) -> float:
        return sum(1 / r.rank for r in self.results if r.rank) / len(self.results)

    @property
    def gate_leaks(self) -> list[str]:
        """Out-of-scope questions that would reach the LLM."""
        return [q for q, score in self.out_of_scope if score >= self.min_similarity]


def _label(hit) -> str:
    return f"{hit.chunk.source} § {hit.chunk.section}"


def evaluate(settings: Settings, questions: Path = QUESTIONS,
             index: VectorIndex | None = None) -> Report:
    spec = yaml.safe_load(settings.resolve(questions).read_text(encoding="utf-8"))
    run_dir = settings.resolve(Path(spec["run"]))
    index = index or run_index(run_dir, settings)
    k = settings.rag.top_k
    results, refused = [], []
    for item in spec["questions"]:
        hits = retrieve(index, item["q"], settings, k)
        labels = [_label(h) for h in hits]
        rank = next((i + 1 for i, label in enumerate(labels) if label in item["gold"]), None)
        results.append(Result(item["q"], item["gold"], [(_label(h), h.score) for h in hits],
                              rank))
        if not hits:
            refused.append(item["q"])
    out = []
    for question in spec["out_of_scope"]:
        best = index.search(embed_question(question, settings), 1,
                            content_words(question))
        out.append((question, best[0].score if best else 0.0))
    return Report(k, settings.rag.min_similarity, results, out, refused)


def markdown(report: Report) -> str:
    """The results note for the vault."""
    lines = [
        f"- **hit@1:** {report.hit1:.0%} (the best excerpt answers the question)",
        f"- **hit@{report.k}:** {report.hit_k:.0%} (a right excerpt is among the {report.k} "
        "the chat answers from)",
        f"- **MRR:** {report.mrr:.2f}",
        f"- **Gate:** {len(report.out_of_scope) - len(report.gate_leaks)} of "
        f"{len(report.out_of_scope)} out-of-scope questions refused before any LLM call; "
        f"{len(report.in_scope_refused)} of {len(report.results)} in-scope questions refused",
        "",
        "| Question | Rank | Best excerpt (score) |",
        "|---|---|---|",
    ]
    for r in report.results:
        best = f"{r.retrieved[0][0]} ({r.retrieved[0][1]:.2f})" if r.retrieved else "none"
        lines.append(f"| {r.question} | {r.rank or 'miss'} | {best} |")
    lines += ["", "| Out-of-scope question | Best score | Refused |", "|---|---|---|"]
    for question, score in report.out_of_scope:
        lines.append(f"| {question} | {score:.2f} | "
                     f"{'yes' if score < report.min_similarity else '**no**'} |")
    return "\n".join(lines)
