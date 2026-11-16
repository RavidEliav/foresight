"""Helpers shared by the result pages: find the latest run and read its artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import streamlit as st


def latest_run_dir(runs_dir: Path, required: str = "validation_summary.json",
                   fallback: Path | None = None) -> Path | None:
    """Newest run folder that contains ``required`` (run ids sort by time), else ``fallback``
    (the committed reference run) if it contains it."""
    runs = sorted(p for p in runs_dir.iterdir() if (p / required).exists()) \
        if runs_dir.exists() else []
    if runs:
        return runs[-1]
    return fallback if fallback is not None and (fallback / required).exists() else None


def run_label(run_dir: Path) -> str:
    return "reference run" if run_dir.name == "reference" else f"run `{run_dir.name}`"


def show_markdown_file(run_dir: Path, name: str, download_label: str | None = None) -> bool:
    """Show a crew document; its own level-1 title is dropped because the page has one."""
    path = run_dir / name
    if not path.exists():
        return False
    st.markdown(re.sub(r"\A\s*#\s[^\n]*\n", "", path.read_text(encoding="utf-8")))
    if download_label:
        st.download_button(download_label, path.read_bytes(), file_name=name,
                           mime="text/markdown", key=f"download-{name}")
    return True


def read_json(run_dir: Path, name: str) -> dict | None:
    path = run_dir / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def no_run(what: str) -> None:
    st.info(f"No {what} yet. Start a run on the Run Pipeline page.")


def show_figure(run_dir: Path, relative: str | None, caption: str | None = None) -> None:
    if relative and (run_dir / relative).exists():
        st.image(str(run_dir / relative), caption=caption, width="stretch")
