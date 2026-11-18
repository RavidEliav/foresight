"""Chunking, a small numpy vector index, and retrieval with a refusal threshold.

A run's index (``rag_index.npz`` + ``rag_chunks.json``) is built once at the end of the run and
stored with its outputs; the build parameters are recorded with it. The knowledge index is
cached in ``paths.models_dir`` under a hash of the documents, so editing a document rebuilds it.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from foresight.rag.embedding import MODEL_NAME, get_embedder
from foresight.rag.run_data import RUN_DATA_FILE, TABLE_FILES, write_run_data
from foresight.settings import Settings

RUN_SOURCES = ("insights.md", "evaluation_report.md", "model_card.md", "investigation.md",
               "engineering_report.md", "validation_summary.json", RUN_DATA_FILE)
VECTORS_FILE = "rag_index.npz"
CHUNKS_FILE = "rag_chunks.json"
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


STOPWORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "can", "did", "do", "does", "for",
             "from", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "the", "this",
             "to", "was", "were", "what", "when", "where", "which", "who", "why", "will", "with",
             "you", "your", "run", "runs"}
TITLE_BOOST = 0.3  # hybrid retrieval: + 0.3 x share of the question's words in the section title
ID_BOOST = 0.3  # + 0.3 when a number in the question (e.g. a run id) is in the section title


def content_words(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9_]+", text.lower())} - \
        {w.rstrip("s") for w in STOPWORDS}


@dataclass
class Chunk:
    source: str
    section: str
    text: str

    @property
    def citation(self) -> str:
        return f"{self.source} § {self.section}"


@dataclass
class Hit:
    chunk: Chunk
    score: float


def sections(markdown: str, default: str) -> list[tuple[str, str]]:
    """(section title, body) pairs; text before the first heading belongs to ``default``."""
    found: list[tuple[str, list[str]]] = [(default, [])]
    for line in markdown.splitlines():
        match = HEADING.match(line)
        if match:
            if len(match.group(1)) == 1:  # the document title names the default section
                found[0] = (match.group(2), found[0][1])
                continue
            found.append((match.group(2), []))
        else:
            found[-1][1].append(line)
    return [(title, "\n".join(body).strip()) for title, body in found if "\n".join(body).strip()]


def split_text(text: str, size: int, overlap: int) -> list[str]:
    """Pack sentences into chunks of about ``size`` characters, repeating about ``overlap``
    characters (whole sentences) at the start of the next chunk."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n(?=[-*\d])", text) if s.strip()]
    chunks: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        if current and len(" ".join(current + [sentence])) > size:
            chunks.append(" ".join(current))
            tail: list[str] = []
            for previous in reversed(current):
                if len(" ".join([previous, *tail])) > overlap:
                    break
                tail.insert(0, previous)
            current = tail
        current.append(" ".join(sentence.split()))
    if current:
        chunks.append(" ".join(current))
    return chunks


def json_text(payload: dict) -> str:
    """validation_summary.json as readable lines (what the chat should be able to quote)."""
    counts = payload.get("counts", {})
    lines = [f"Data Contract validation status: {payload.get('status')} "
             f"({counts.get('PASS', 0)} checks passed, {counts.get('WARNING', 0)} warnings, "
             f"{counts.get('ERROR', 0)} errors)."]
    for check in payload.get("checks", []):
        lines.append(f"Check {check['name']}: {check['status']}. {check['message']}.")
    return "\n".join(lines)


def chunk_file(path: Path, size: int, overlap: int) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        parts = [("Validation checks", json_text(json.loads(raw)))]
    else:
        parts = sections(raw, path.stem.replace("_", " "))
    return [Chunk(path.name, title, piece) for title, body in parts
            for piece in split_text(body, size, overlap)]


class VectorIndex:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray, params: dict):
        self.chunks, self.vectors, self.params = chunks, vectors, params

    def search(self, query: np.ndarray, k: int, words: set[str] | None = None) -> list[Hit]:
        """Dense cosine similarity, plus TITLE_BOOST x the share of the question's content
        words found in the chunk's section title (short questions such as "What are the
        recommended next steps?" embed poorly against long chunk bodies)."""
        if not self.chunks:
            return []
        scores = self.vectors @ query
        if words:
            ids = {w for w in words if w.isdigit() and len(w) >= 2}
            boost = np.array([TITLE_BOOST * len(words & content_words(c.section)) / len(words)
                              + ID_BOOST * bool(ids & content_words(c.section))
                              for c in self.chunks])
            scores = scores + boost
        order = np.argsort(-scores, kind="stable")[:k]
        return [Hit(self.chunks[i], round(float(scores[i]), 4)) for i in order]

    def save(self, folder: Path, stem: str = "rag") -> None:
        np.savez_compressed(folder / f"{stem}_index.npz", vectors=self.vectors)
        (folder / f"{stem}_chunks.json").write_text(json.dumps(
            {"params": self.params, "chunks": [asdict(c) for c in self.chunks]}, indent=2),
            encoding="utf-8")

    @classmethod
    def load(cls, folder: Path, stem: str = "rag") -> VectorIndex | None:
        vectors, chunks = folder / f"{stem}_index.npz", folder / f"{stem}_chunks.json"
        if not (vectors.exists() and chunks.exists()):
            return None
        meta = json.loads(chunks.read_text(encoding="utf-8"))
        return cls([Chunk(**c) for c in meta["chunks"]], np.load(vectors)["vectors"],
                   meta["params"])


def _embedder(settings: Settings):
    return get_embedder(str(settings.resolve(settings.paths.models_dir)))


def _embed_text(chunk: Chunk) -> str:
    """What gets embedded: the document and section names carry meaning the body lacks
    (e.g. "Recommended next steps", "Hypotheses")."""
    document = Path(chunk.source).stem.replace("_", " ")
    return f"{document}, {chunk.section}: {chunk.text}"


def _build(paths: list[Path], settings: Settings) -> VectorIndex:
    cfg = settings.rag
    chunks = [c for p in paths for c in chunk_file(p, cfg.chunk_chars, cfg.overlap_chars)]
    params = {"embedding_model": MODEL_NAME, "retrieval": f"cosine + {TITLE_BOOST} x section-"
              "title keyword share", "chunk_chars": cfg.chunk_chars,
              "overlap_chars": cfg.overlap_chars, "top_k": cfg.top_k,
              "min_similarity": cfg.min_similarity, "files": [p.name for p in paths],
              "chunks": len(chunks)}
    return VectorIndex(chunks, _embedder(settings).embed([_embed_text(c) for c in chunks]),
                       params)


def build_run_index(run_dir: Path, settings: Settings) -> dict:
    """Index the run's text artifacts and save it in the run folder; returns its parameters.
    run_data.md (the run's tables as text) is written first."""
    write_run_data(run_dir)
    index = _build([run_dir / n for n in RUN_SOURCES if (run_dir / n).exists()], settings)
    index.save(run_dir)
    return index.params


def run_index(run_dir: Path, settings: Settings) -> VectorIndex:
    """The run's saved index, built now for runs made before indexing existed, and rebuilt
    once for runs indexed before run_data.md existed."""
    index = VectorIndex.load(run_dir)
    outdated = index is not None and RUN_DATA_FILE not in index.params.get("files", []) and \
        any((run_dir / name).exists() for name in TABLE_FILES)
    if index is None or outdated:
        build_run_index(run_dir, settings)
        index = VectorIndex.load(run_dir)
    return index


def knowledge_files(settings: Settings) -> list[Path]:
    folder = settings.resolve(settings.paths.knowledge_dir)
    return sorted(p for p in folder.glob("*.md") if p.name != "SOURCES.md")


def knowledge_index(settings: Settings) -> VectorIndex:
    files = knowledge_files(settings)
    digest = hashlib.sha256(b"".join(p.read_bytes() for p in files)
                            + json.dumps(settings.rag.model_dump()).encode()).hexdigest()[:12]
    cache = settings.resolve(settings.paths.models_dir)
    cached = VectorIndex.load(cache, f"knowledge_{digest}")
    if cached is not None:
        return cached
    index = _build(files, settings)
    cache.mkdir(parents=True, exist_ok=True)
    index.save(cache, f"knowledge_{digest}")
    return index


def retrieve(index: VectorIndex, question: str, settings: Settings,
             k: int | None = None) -> list[Hit]:
    """The top ``k`` chunks with similarity at or above ``rag.min_similarity``."""
    query = _embedder(settings).embed([question])[0]
    hits = index.search(query, k or settings.rag.top_k, content_words(question))
    return [h for h in hits if h.score >= settings.rag.min_similarity]
