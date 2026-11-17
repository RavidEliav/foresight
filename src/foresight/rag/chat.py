""""Ask Foresight": answers about one run, only from that run's artifacts, with citations.

Two refusal layers: questions whose best match is below ``rag.min_similarity`` are refused
without calling the LLM; otherwise the LLM must answer only from the retrieved excerpts and cite
them, or reply exactly with REFUSAL. An answer that cites none of the retrieved excerpts is
withheld. Every question and answer is logged (``chat_logs/<run>.jsonl`` in the runs folder).
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from foresight.rag.index import Hit, retrieve, run_index
from foresight.settings import Settings

REFUSAL = "Not found in this run's artifacts."
CITATION = re.compile(r"\[source:\s*([^\]§]+?)\s*(?:§\s*([^\]]+?))?\s*\]", re.IGNORECASE)
SYSTEM = f"""You are Foresight, an assistant for semiconductor process engineers.
Answer the question using ONLY the excerpts from this run's artifacts given below.
- After every statement, cite the excerpt it comes from with the excerpt's header exactly as
  shown above it, for example [source: model_card.md § Limitations].
- Use only numbers that appear in the excerpts. Do not use general knowledge.
- Sensor names are anonymized; never say what a sensor physically measures.
- Say "is associated with", never "causes".
- If the excerpts do not contain the answer, reply exactly: {REFUSAL}
- Keep the answer short: at most about 120 words."""


class Source(BaseModel):
    file: str
    section: str
    score: float
    text: str


class ChatAnswer(BaseModel):
    question: str
    answer: str
    refused: bool
    reason: str = ""
    sources: list[Source] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    seconds: float = 0.0
    mock: bool = False


def _prompt(question: str, hits: list[Hit]) -> str:
    excerpts = "\n\n".join(f"[source: {h.chunk.citation}]\n{h.chunk.text}" for h in hits)
    return f"Excerpts:\n\n{excerpts}\n\nQuestion: {question}"


def citation_problem(answer: str, hits: list[Hit]) -> str | None:
    """At least one citation must be traceable, no citation may point outside what was
    retrieved, and every paragraph (except an introduction ending with ':') must cite.
    Traceable = a retrieved excerpt (file § section) or a source tag quoted inside the
    retrieved text (the reports cite their own data files)."""
    excerpts = {(h.chunk.source, h.chunk.section.lower()) for h in hits}
    files = {h.chunk.source for h in hits}
    quoted = {m.group(1).strip() for h in hits for m in CITATION.finditer(h.chunk.text)}
    citations = [(m.group(1).strip(), (m.group(2) or "").strip()) for m in
                 CITATION.finditer(answer)]

    def traceable(file: str, sec: str) -> bool:
        if (file, sec.lower()) in excerpts:
            return True
        return file in quoted and (file not in files or not sec)

    if not any(traceable(f, s) for f, s in citations):
        return "it cited no retrieved excerpt"
    for file, sec in citations:
        if not traceable(file, sec):
            return f"it cited something that was not retrieved ({file}{' § ' + sec if sec else ''})"
    # a list is one block, even when its items are separated by blank lines, and a paragraph
    # that is only a citation cites the block before it
    joined = re.sub(r"\n\s*\n(?=\s*(?:\d+[.)]|[-*])\s|\s*\[source:)", "\n", answer)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", joined) if p.strip()]
    if any(not CITATION.search(p) and not p.endswith(":") for p in paragraphs):
        return "part of it has no citation"
    return None


def cited_sources(answer: str, hits: list[Hit]) -> set[str]:
    """Files of the retrieved excerpts that the answer cites."""
    files = {h.chunk.source for h in hits}
    return {m.group(1).strip() for m in CITATION.finditer(answer)} & files


STOPWORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "can", "did", "do", "does", "for",
             "from", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "the", "this",
             "to", "was", "were", "what", "when", "where", "which", "who", "why", "will", "with",
             "you", "your"}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower())) - STOPWORDS


def mock_answer(question: str, hits: list[Hit]) -> str:
    """Deterministic extractive answer for MOCK_LLM: the sentence of the best excerpt that
    shares the most content words with the question (counting its section title), or REFUSAL
    if none shares any."""
    words = _words(question)
    best = hits[0].chunk
    title = _words(best.section)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", best.text) if s.strip()]
    sentence = max(sentences, key=lambda s: len(words & (_words(s) | title)))
    if not words & (_words(sentence) | title):
        return REFUSAL
    return f"{sentence.strip()} [source: {best.citation}]"


def ask(question: str, run_dir: Path, settings: Settings) -> ChatAnswer:
    start = time.perf_counter()
    question = question.strip()
    hits = retrieve(run_index(run_dir, settings), question, settings)
    sources = [Source(file=h.chunk.source, section=h.chunk.section, score=h.score,
                      text=h.chunk.text) for h in hits]
    if not hits:
        return ChatAnswer(question=question, answer=REFUSAL, refused=True,
                          reason=f"no excerpt reached similarity {settings.rag.min_similarity}",
                          seconds=round(time.perf_counter() - start, 2), mock=settings.mock_llm)

    usage: dict[str, int] = {}
    if settings.mock_llm:
        answer = mock_answer(question, hits)
    else:
        from foresight.llm import get_llm

        llm = get_llm(settings)
        answer = str(llm.call([{"role": "system", "content": SYSTEM},
                               {"role": "user", "content": _prompt(question, hits)}])).strip()
        usage = {k: int(v) for k, v in llm.get_token_usage_summary().model_dump().items()
                 if isinstance(v, int)}

    refused, reason = False, ""
    if REFUSAL.lower().rstrip(".") in answer.lower():
        answer, refused, reason = REFUSAL, True, "the excerpts do not contain the answer"
    elif problem := citation_problem(answer, hits):
        answer, refused, reason = REFUSAL, True, f"answer withheld: {problem}"
    return ChatAnswer(question=question, answer=answer, refused=refused, reason=reason,
                      sources=sources, usage=usage, mock=settings.mock_llm,
                      seconds=round(time.perf_counter() - start, 2))


def log_path(settings: Settings, run_dir: Path) -> Path:
    return settings.resolve(settings.paths.runs_dir) / "chat_logs" / f"{run_dir.name}.jsonl"


def log_answer(settings: Settings, run_dir: Path, result: ChatAnswer) -> None:
    path = log_path(settings, run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"time": datetime.now(UTC).isoformat(timespec="seconds"), "run": run_dir.name,
              **result.model_dump(exclude={"sources"}),
              "sources": [f"{s.file} § {s.section} ({s.score})" for s in result.sources]}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
