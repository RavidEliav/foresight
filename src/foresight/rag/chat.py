""""Ask Foresight": answers about one run, only from that run's artifacts, with citations.

Two refusal layers: questions whose best match is below ``rag.min_similarity`` are refused
without calling the LLM; otherwise the LLM must answer only from the retrieved excerpts and cite
them, or reply exactly with REFUSAL. An answer that cites none of the retrieved excerpts is
withheld. Every question and answer is logged: in Supabase (``foresight.questions``, ADR-033)
when the database is configured, else in ``chat_logs/<run>.jsonl`` in the runs folder.
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
from foresight.utils.logging import get_logger, redact

log = get_logger("chat")

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
REFUSAL_ALL = "Not found in the recorded runs."
SYSTEM_ALL = f"""You are Foresight, an assistant for semiconductor process engineers.
Answer the question using ONLY the excerpts below. They come from several pipeline runs,
listed under "Runs"; an excerpt's header starts with its run id.
- Say which run every statement is about (by its start date and data), and compare runs only
  through what the excerpts say. Prefer one line per run, each with its citation.
- After every statement, cite the excerpt it comes from with the excerpt's header exactly as
  shown above it, for example [source: 20261118T201632841000Z/model_card.md § Limitations].
  A closing comparison may only restate what the cited lines say, with their numbers.
- Use only numbers that appear in the excerpts. Do not use general knowledge.
- Sensor names are anonymized; never say what a sensor physically measures.
- Say "is associated with", never "causes".
- If the excerpts do not contain the answer, reply exactly: {REFUSAL_ALL}
- Keep the answer short: at most about 150 words."""


class Source(BaseModel):
    file: str
    section: str
    score: float
    text: str
    run: str = ""  # the run it comes from (All runs mode)


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


def citation_problem(answer: str, hits: list[Hit], grounded_summaries: bool = False) -> str | None:
    """At least one citation must be traceable, no citation may point outside what was
    retrieved, and every paragraph (except an introduction ending with ':') must cite.
    Traceable = a retrieved excerpt (file § section) or a source tag quoted inside the
    retrieved text (the reports cite their own data files). With ``grounded_summaries`` (All
    runs mode), a paragraph without a citation is allowed when every number in it appears in
    the retrieved excerpts or their run ids: a comparison across runs sums up cited lines."""
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
    for i, paragraph in enumerate(paragraphs):
        if CITATION.search(paragraph) or paragraph.endswith(":"):
            continue
        # a list whose closing sentence (the next paragraph) cites the excerpt it came from
        is_list = re.search(r"^\s*(?:\d+[.)]|[-*])\s", paragraph, re.MULTILINE)
        if is_list and i + 1 < len(paragraphs) and CITATION.search(paragraphs[i + 1]):
            continue
        if grounded_summaries and _numbers(paragraph) <= _numbers(
                " ".join(f"{h.chunk.source} {h.chunk.text}" for h in hits)):
            continue
        return "part of it has no citation"
    return None


def _numbers(text: str) -> set[str]:
    """Numbers as written (0.085, 95, 20261118), without trailing zeros of decimals."""
    found = set()
    for number in re.findall(r"\d+(?:\.\d+)?", text):
        found.add(number.rstrip("0").rstrip(".") if "." in number else number)
    return found


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
    return _answer(question, hits, sources, settings, SYSTEM, _prompt(question, hits), REFUSAL,
                   start)


def ask_all(question: str, settings: Settings, run_ids: list[str] | None = None) -> ChatAnswer:
    """A question about all recorded runs, or only ``run_ids`` (Supabase pgvector, else this
    server's runs)."""
    from foresight.rag.cross import retrieve_all, split_source

    start = time.perf_counter()
    question = question.strip()
    hits, runs = retrieve_all(question, settings, run_ids)
    sources = []
    for h in hits:
        run_id, file = split_source(h.chunk.source)
        sources.append(Source(file=file, section=h.chunk.section, score=h.score,
                              text=h.chunk.text, run=runs[run_id].label))
    listing = "\n".join(f"- {info.label}" for info in runs.values())
    prompt = f"Runs:\n{listing}\n\n{_prompt(question, hits)}"
    return _answer(question, hits, sources, settings, SYSTEM_ALL, prompt, REFUSAL_ALL, start,
                   grounded_summaries=True)


def _answer(question: str, hits: list[Hit], sources: list[Source], settings: Settings,
            system: str, prompt: str, refusal: str, start: float,
            grounded_summaries: bool = False) -> ChatAnswer:
    if not hits:
        return ChatAnswer(question=question, answer=refusal, refused=True,
                          reason=f"no excerpt reached similarity {settings.rag.min_similarity}",
                          seconds=round(time.perf_counter() - start, 2), mock=settings.mock_llm)

    usage: dict[str, int] = {}
    if settings.mock_llm:
        answer = mock_answer(question, hits)
    else:
        answer, usage = complete(settings, system, prompt)

    refused, reason = False, ""
    if refusal.lower().rstrip(".") in answer.lower() or \
            REFUSAL.lower().rstrip(".") in answer.lower():
        answer, refused, reason = refusal, True, "the excerpts do not contain the answer"
    elif problem := citation_problem(answer, hits, grounded_summaries):
        answer, refused, reason = refusal, True, f"answer withheld: {problem}"
    return ChatAnswer(question=question, answer=answer, refused=refused, reason=reason,
                      sources=sources, usage=usage, mock=settings.mock_llm,
                      seconds=round(time.perf_counter() - start, 2))


def log_path(settings: Settings, run_dir: Path) -> Path:
    return settings.resolve(settings.paths.runs_dir) / "chat_logs" / f"{run_dir.name}.jsonl"


def complete(settings: Settings, system: str, prompt: str) -> tuple[str, dict[str, int]]:
    """One chat completion through the OpenAI SDK. The chat runs inside the app process, where
    CrewAI's LLM wrapper would add about 70 MB and 3 s to the first question; the crews keep
    using it."""
    from openai import OpenAI

    from foresight.llm import check_api_key

    check_api_key()
    response = OpenAI().chat.completions.create(
        model=settings.llm.model, temperature=settings.llm.temperature,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
    usage = response.usage
    tokens = {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens,
              "total_tokens": usage.total_tokens} if usage else {}
    return (response.choices[0].message.content or "").strip(), tokens


def log_answer(settings: Settings, run_dir: Path, result: ChatAnswer, user: str = "") -> None:
    """Log the question and answer with who asked (Phase 8.6): in Supabase when configured;
    in the run's chat log file without it, or if the database cannot be reached (the next
    app start moves it to Supabase)."""
    record = {"time": datetime.now(UTC).isoformat(timespec="seconds"), "run": run_dir.name,
              "user": user, **result.model_dump(exclude={"sources"}),
              "sources": [f"{s.file} § {s.section} ({s.score})" for s in result.sources]}
    if settings.database_url:
        from foresight.registry import db

        try:
            db.insert_questions(settings.database_url, [record])
            return
        except Exception as exc:
            log.warning("question kept in the chat log file, not in Supabase: %s", redact(exc))
    path = log_path(settings, run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def import_chat_logs(settings: Settings) -> int:
    """Move the chat log files into Supabase (older questions, and any the database missed);
    a file is deleted once its questions are stored. Returns how many questions."""
    folder = settings.resolve(settings.paths.runs_dir) / "chat_logs"
    if not settings.database_url or not folder.exists():
        return 0
    from foresight.registry import db

    moved = 0
    for path in sorted(folder.glob("*.jsonl")):
        records = [{"run": path.stem, **r} for r in _records(path) if r.get("time")]
        db.insert_questions(settings.database_url, records)
        path.unlink()
        moved += len(records)
    return moved


def _logged(settings: Settings, run: str | None, user: str | None, limit: int) -> list[dict]:
    """Logged records, newest first: about ``run`` and/or by ``user``. From Supabase when
    configured (the files if it cannot be reached), else from the chat log files."""
    if settings.database_url:
        from foresight.registry import db

        try:
            return db.fetch_questions(settings.database_url, run, user, limit)
        except Exception as exc:
            log.warning("chat history read from the files, not Supabase: %s", redact(exc))
    folder = settings.resolve(settings.paths.runs_dir) / "chat_logs"
    paths = [folder / f"{run}.jsonl"] if run is not None else sorted(folder.glob("*.jsonl"))
    found = [r for path in paths if path.exists() for r in _records(path)
             if user is None or r.get("user", "") == user]
    return sorted(found, key=lambda r: r.get("time", ""), reverse=True)[:limit]


def _records(path: Path):
    """A chat log's records, newest first."""
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def recent_questions(settings: Settings, run_dir: Path, limit: int = 6,
                     user: str | None = None) -> list[dict]:
    """The run's latest distinct questions, newest first; only ``user``'s when given."""
    found: dict[str, dict] = {}
    for record in _logged(settings, run_dir.name, user, limit * 5):
        key = record.get("question", "").strip().lower()
        if key and key not in found:
            found[key] = record
        if len(found) == limit:
            break
    return list(found.values())


def questions_by(settings: Settings, user: str, limit: int = 100) -> list[dict]:
    """Every question ``user`` asked, about any run or about all runs, newest first."""
    return _logged(settings, None, user, limit)
