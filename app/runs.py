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


def describe_run(run_dir: Path) -> str:
    """Short label for the run selector, e.g. '16 Nov, 23:17 · SECOM' (local time)."""
    if run_dir.name == "reference":
        return "Reference run"
    started = run_started(run_dir)
    when = local_time(started, "%d %b, %H:%M") if started else run_dir.name
    return f"{when} · {'Upload' if is_upload(run_dir) else 'SECOM'}"


def run_details(run_dir: Path) -> str:
    """Full description of a run, shown under the selector."""
    if run_dir.name == "reference":
        return "Committed reference run on the SECOM data (UCI), shipped with the app."
    started = run_started(run_dir)
    dataset = _dataset(run_dir)
    return (f"{dataset} · started {local_time(started)}" if started else dataset)


def run_label(run_dir: Path) -> str:
    if run_dir.name == "reference":
        return "Reference run · SECOM (UCI), committed with the app"
    started = run_started(run_dir)
    return (f"Run started {local_time(started)} · {_dataset(run_dir)}" if started
            else f"Run `{run_dir.name}`")


def show_markdown_file(run_dir: Path, name: str, download_label: str | None = None) -> bool:
    """Show a crew document; its own level-1 title is dropped because the page has one."""
    from app import store

    text = store.read_text(run_dir, name)
    if text is None:
        return False
    st.markdown(re.sub(r"\A\s*#\s[^\n]*\n", "", text))
    if download_label:
        st.download_button(download_label, text.encode("utf-8"), file_name=name,
                           mime="text/markdown", key=f"download-{name}")
    return True


def no_run(what: str) -> None:
    st.info(f"No {what} yet. Start a run on the Run Pipeline page.")


def show_figure(run_dir: Path, relative: str | None, caption: str | None = None) -> None:
    from app import store

    if path := store.figure(run_dir, relative):
        st.image(str(path), caption=caption, width="stretch")
