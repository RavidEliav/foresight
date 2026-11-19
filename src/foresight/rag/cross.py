"""Retrieval across all recorded runs ("Ask Foresight" in All runs mode, Phase 8.2).

With Supabase, the nearest chunks come from pgvector (``foresight.chunks``, HNSW cosine
index); without it, from the successful runs' own indexes on this server. Both rank with the
same score as a single run (cosine + the section-title bonus), and every chunk's source names
its run, so citations say which run a statement comes from.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from foresight.rag.index import (
    Chunk,
    Hit,
    VectorIndex,
    content_words,
    embed_question,
    title_boost,
)
from foresight.settings import Settings

CANDIDATES = 40  # nearest chunks fetched before the title bonus re-ranks them


@dataclass
class RunInfo:
    run_id: str
    started_at: str | None
    dataset: str | None

    @property
    def label(self) -> str:
        when = (self.started_at or "")[:16].replace("T", " ")
        return f"run {self.run_id}: started {when} UTC, data {self.dataset or 'unknown'}"


def cited_source(run_id: str, file: str) -> str:
    return f"{run_id}/{file}"


def split_source(source: str) -> tuple[str, str]:
    """(run id, file) of a cross-run source."""
    run_id, _, file = source.partition("/")
    return run_id, file


def _rank(hits: list[Hit], words: set[str], k: int, minimum: float) -> list[Hit]:
    for hit in hits:
        hit.score = round(hit.score + title_boost(words, hit.chunk.section), 4)
    hits.sort(key=lambda h: -h.score)
    return [h for h in hits[:k] if h.score >= minimum]


def _from_database(query: np.ndarray, settings: Settings) -> tuple[list[Hit], dict]:
    from foresight.registry import db

    rows = db.search_chunks(settings.database_url, query, CANDIDATES)
    runs = {r["run_id"]: RunInfo(r["run_id"], r["started_at"], r["dataset"]) for r in rows}
    hits = [Hit(Chunk(cited_source(r["run_id"], r["source"]), r["section"], r["body"]),
                float(r["score"])) for r in rows]
    return hits, runs


@lru_cache(maxsize=4)
def _merged(folders: tuple[tuple[str, float], ...]) -> tuple[VectorIndex, dict]:
    """One index over the given run folders (cached per folder version)."""
    from foresight.progress import load_progress

    chunks, vectors, runs = [], [], {}
    for folder, _mtime in folders:
        path = Path(folder)
        index = VectorIndex.load(path)
        if index is None:
            continue
        manifest = json.loads((path / "run_manifest.json").read_text(encoding="utf-8"))
        run_id = manifest.get("run_id") or path.name
        progress = load_progress(path)
        runs[run_id] = RunInfo(run_id, progress.started_at if progress else
                               manifest.get("created_at"),
                               progress.dataset if progress else "SECOM (UCI)")
        chunks += [Chunk(cited_source(run_id, c.source), c.section, c.text)
                   for c in index.chunks]
        vectors.append(index.vectors)
    matrix = np.vstack(vectors) if vectors else np.zeros((0, 384), dtype=np.float32)
    return VectorIndex(chunks, matrix, {}), runs


def _run_folders(settings: Settings) -> list[Path]:
    folder = settings.resolve(settings.paths.runs_dir)
    found = [p for p in sorted(folder.iterdir()) if p.is_dir()] if folder.exists() else []
    found.append(settings.resolve(settings.paths.reference_run_dir))
    good = []
    for path in found:
        manifest = path / "run_manifest.json"
        if manifest.exists() and (path / "rag_chunks.json").exists() and json.loads(
                manifest.read_text(encoding="utf-8")).get("status") == "success":
            good.append(path)
    return good


def _from_files(query: np.ndarray, settings: Settings) -> tuple[list[Hit], dict]:
    folders = tuple((str(p), (p / "rag_index.npz").stat().st_mtime)
                    for p in _run_folders(settings))
    index, runs = _merged(folders)
    return index.search(query, CANDIDATES), runs


def retrieve_all(question: str, settings: Settings) -> tuple[list[Hit], dict[str, RunInfo]]:
    """The best chunks across all runs (at most ``rag.all_runs_k``, at or above
    ``rag.min_similarity``) and the runs they come from."""
    query = embed_question(question, settings)
    hits, runs = (_from_database if settings.database_url else _from_files)(query, settings)
    ranked = _rank(hits, content_words(question), settings.rag.all_runs_k,
                   settings.rag.min_similarity)
    return ranked, {split_source(h.chunk.source)[0]: runs[split_source(h.chunk.source)[0]]
                    for h in ranked}
