"""Helpers shared by the result pages: run labels in local time, documents and figures
(read through app.store)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from app.store import read_json


def local_zone() -> tzinfo:
    """The viewer's time zone from the browser (UTC when it is unknown, e.g. in tests)."""
    try:
        name = st.context.timezone
        return ZoneInfo(name) if name else UTC
    except (ZoneInfoNotFoundError, ValueError, AttributeError):
        return UTC


def local_time(value: datetime | str, fmt: str = "%d %b %Y, %H:%M") -> str:
    """A UTC timestamp (datetime or ISO text) in the viewer's time zone; 'UTC' is added only
    when the browser's zone is unknown."""
    moment = datetime.fromisoformat(value) if isinstance(value, str) else value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    zone = local_zone()
    return moment.astimezone(zone).strftime(fmt) + (" UTC" if zone is UTC else "")


def run_started(run_dir: Path) -> datetime | None:
    """Run ids are UTC start times, e.g. 20261116T211713416782Z."""
    try:
        return datetime.strptime(run_dir.name[:15], "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def _dataset(run_dir: Path) -> str:
    return (read_json(run_dir, "progress.json") or {}).get("dataset", "SECOM (UCI)")


def is_upload(run_dir: Path) -> bool:
    return _dataset(run_dir).startswith("Uploaded")


def is_scenario(run_dir: Path) -> bool:
    """A synthetic Scenario Lab run (training period changed; test period original SECOM)."""
    return _dataset(run_dir).startswith("Scenario")


SYNTHETIC = ":orange-badge[Synthetic]"
SYNTHETIC_NOTE = ("Synthetic scenario: the training data was changed on purpose; every metric is "
                  "computed on the original SECOM test period.")


def analysis_name(run_dir: Path) -> str:
    """Phase 8.10: "Analysis 12", or "Reference analysis" for the committed one."""
    if run_dir.name == "reference":
        return "Reference analysis"
    from app import store

    number = store.analysis_numbers().get(run_dir.name)
    return f"Analysis {number}" if number else "Analysis"


def data_kind(run_dir: Path) -> str:
    """The data in one word: SECOM, Upload or Scenario."""
    return "Upload" if is_upload(run_dir) else "Scenario" if is_scenario(run_dir) else "SECOM"


def describe_run(run_dir: Path) -> str:
    """The analysis for the selector, e.g. 'Analysis 12 · SECOM · 16 Nov, 23:17' (local)."""
    if run_dir.name == "reference":
        return "Reference analysis · SECOM"
    started = run_started(run_dir)
    when = f" · {local_time(started, '%d %b, %H:%M')}" if started else ""
    return f"{analysis_name(run_dir)} · {data_kind(run_dir)}{when}"


def run_details(run_dir: Path) -> str:
    """The analysis's data in full, shown under the selector."""
    if run_dir.name == "reference":
        return "The reference analysis of the SECOM data, shipped with the app."
    return _dataset(run_dir)


def run_label(run_dir: Path) -> str:
    """The short line at the top of a result page; the details are in ``run_help``."""
    label = describe_run(run_dir)
    return f"{label} {SYNTHETIC}" if is_scenario(run_dir) else label


def run_help(run_dir: Path, more: str = "") -> str:
    """The tooltip of the run line: the data in full, when it started, and what a synthetic
    scenario means."""
    started = run_started(run_dir)
    parts = [run_details(run_dir)]
    if started:
        parts.append(f"Started {local_time(started)}.")
    if is_scenario(run_dir):
        parts.append(SYNTHETIC_NOTE)
    if more:
        parts.append(more)
    return " ".join(p if p.endswith(".") else p + "." for p in parts)


def run_line(run_dir: Path, more: str = "") -> None:
    """Phase 8.10: the analysis in one short line at the top of a page, the rest in its
    tooltip."""
    st.caption(run_label(run_dir), help=run_help(run_dir, more))


# Phase 8.10: a run's files by their plain names, for download buttons and file names
DOCUMENTS = {"engineering_report.md": "Engineering report", "investigation.md": "Investigation",
             "insights.md": "Insights", "model_card.md": "Model card",
             "evaluation_report.md": "Evaluation report", "eda_report.html": "Data report",
             "dataset_contract.json": "Data Contract"}
MIME = {".md": "text/markdown", ".json": "application/json", ".html": "text/html"}


def download(run_dir: Path, name: str, data: bytes | str, **kwargs) -> None:
    """A download button with a plain label ("Download the engineering report") and a file
    name a person can read: "Foresight - Analysis 12 - Engineering report.md"."""
    title = DOCUMENTS.get(name, Path(name).stem.replace("_", " ").capitalize())
    suffix = Path(name).suffix
    label = title if title.startswith("Data Contract") else title.lower()
    st.download_button(f"Download the {label}", data,
                       file_name=f"Foresight - {analysis_name(run_dir)} - {title}{suffix}",
                       mime=MIME.get(suffix, "application/octet-stream"),
                       key=kwargs.pop("key", f"download-{name}"), **kwargs)


def show_markdown_file(run_dir: Path, name: str, downloadable: bool = False) -> bool:
    """Show an AI-written document; its own level-1 title is dropped because the page has
    one."""
    from app import store

    text = store.read_text(run_dir, name)
    if text is None:
        return False
    st.markdown(re.sub(r"\A\s*#\s[^\n]*\n", "", text))
    if downloadable:
        download(run_dir, name, text.encode("utf-8"))
    return True


def no_run(what: str) -> None:
    st.info(f"No {what} yet. Start an analysis on the New analysis page.")


def show_figure(run_dir: Path, relative: str | None, caption: str | None = None) -> None:
    from app import store

    if path := store.figure(run_dir, relative):
        st.image(str(path), caption=caption, width="stretch")
