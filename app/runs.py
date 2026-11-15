"""Helpers shared by the result pages: find the latest run and read its artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st


def latest_run_dir(runs_dir: Path, required: str = "validation_summary.json") -> Path | None:
    """Newest run folder that contains ``required`` (run ids sort by time)."""
    if not runs_dir.exists():
        return None
    runs = sorted(p for p in runs_dir.iterdir() if (p / required).exists())
    return runs[-1] if runs else None


def read_json(run_dir: Path, name: str) -> dict | None:
    path = run_dir / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def no_run(what: str) -> None:
    st.info(f"No {what} yet. Start a run on the Run Pipeline page.")


def show_figure(run_dir: Path, relative: str | None, caption: str | None = None) -> None:
    if relative and (run_dir / relative).exists():
        st.image(str(run_dir / relative), caption=caption, width="stretch")
