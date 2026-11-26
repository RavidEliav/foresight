"""Plain names for what Foresight cites (Phase 8.10).

The AI's text cites its files with tags such as ``[source: model_metrics.json]`` or, across
analyses, ``[source: 20261118T201632841000Z/insights.md § Data quality]``. The tags stay in
the stored text (the chat's and the reports' checks read them); what a person sees is
"Model metrics" or "Analysis 12 › Insights › Data quality".
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import PurePosixPath

TITLES = {
    "engineering_report.md": "Engineering report",
    "investigation.md": "Investigation",
    "insights.md": "Insights",
    "model_card.md": "Model card",
    "evaluation_report.md": "Evaluation report",
    "run_data.md": "Analysis data",
    "eda_report.html": "Data report",
    "dataset_contract.json": "Data Contract",
    "model_metrics.json": "Model metrics",
    "eda_summary.json": "Data insights",
    "anomaly_summary.json": "Anomaly results",
    "data_profile.json": "Data profile",
    "risk_summary.json": "Risk ranking",
    "validation_summary.json": "Data checks",
    "similar_runs.json": "Similar past runs",
    "cleaning_report.json": "Data cleaning",
    "investigation_summary.json": "Investigation summary",
    "feature_spec.json": "Feature list",
    "report_checks.json": "Report checks",
}
TAG = re.compile(r"\[(source|background):\s*([^\]]*?)\s*\]", re.IGNORECASE)
RUN_ID = re.compile(r"\b\d{8}T\d{6}\d*Z\b")
# "run 20261118T201632841000Z", "Run 20261118T201632841000Z's": the word goes with the id
RUN_WORD = re.compile(r"\b(?:the\s+)?[Rr]un\s+(?=\d{8}T\d{6}\d*Z\b)")
REFERENCE = "Reference analysis"


def file_title(name: str) -> str:
    """``model_metrics.json`` -> "Model metrics"; a file not listed gets its words."""
    name = name.strip()
    return TITLES.get(name) or PurePosixPath(name).stem.replace("_", " ").strip().capitalize()


def run_name(run_id: str, names: dict[str, str]) -> str:
    """An analysis's name; a run id with no number is the reference analysis."""
    return names.get(run_id, REFERENCE)


def label(kind: str, body: str, names: dict[str, str] | None = None) -> str:
    """The plain name of one tag: ``insights.md § Data quality`` -> "Insights › Data
    quality"; a background document is "Background: Process drift and maintenance › Drift"."""
    where, _, section = body.partition("§")
    parts = []
    run, slash, file = where.strip().partition("/")
    if slash and RUN_ID.fullmatch(run):
        parts.append(run_name(run, names or {}))
    else:
        file = where
    parts.append(file_title(file))
    if section.strip():
        parts.append(section.strip())
    text = " › ".join(p.replace("[", "(").replace("]", ")") for p in parts)
    return f"Background: {text}" if kind.lower() == "background" else text


def readable(text: str, names: dict[str, str] | None = None,
             chip: Callable[[str], str] = lambda name: f"({name})") -> str:
    """``text`` with each tag as ``chip(plain name)``. With ``names`` (run id -> analysis
    name), the run ids written in the text become analysis names too."""
    out, pos = [], 0
    for match in TAG.finditer(text):
        out.append(_runs(text[pos:match.start()], names))
        out.append(chip(label(match.group(1), match.group(2), names)))
        pos = match.end()
    out.append(_runs(text[pos:], names))
    return "".join(out)


def _runs(text: str, names: dict[str, str] | None) -> str:
    if names is None:
        return text
    text = RUN_WORD.sub("", text)
    return RUN_ID.sub(lambda m: run_name(m.group(0), names), text)
