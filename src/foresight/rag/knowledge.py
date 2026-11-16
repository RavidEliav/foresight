"""Background knowledge for the Investigation crew (requirements §18.2).

Passages come from ``knowledge/*.md`` and are cited as ``[background: <file> § <section>]``.
Background is general knowledge: it is never Evidence, never in the Facts section, and never
used to say what an anonymized sensor physically measures.
"""

from __future__ import annotations

import re

from foresight.rag.index import Hit, knowledge_files, knowledge_index, retrieve, sections
from foresight.settings import Settings

BACKGROUND = re.compile(r"\[background:\s*([^\]§]+?)\s*§\s*([^\]]+?)\s*\]", re.IGNORECASE)


def search_knowledge(query: str, settings: Settings, k: int | None = None) -> list[Hit]:
    return retrieve(knowledge_index(settings), query, settings, k or settings.rag.knowledge_k)


def cite(hit: Hit) -> str:
    return f"[background: {hit.chunk.source} § {hit.chunk.section}]"


def known_sections(settings: Settings) -> dict[str, set[str]]:
    """Section titles per knowledge file (the citations a report may use)."""
    return {p.name: {title.lower() for title, _ in sections(p.read_text(encoding="utf-8"),
                                                            p.stem)}
            for p in knowledge_files(settings)}


def background_citations(text: str) -> list[tuple[str, str]]:
    return [(m.group(1).strip(), m.group(2).strip()) for m in BACKGROUND.finditer(text)]
