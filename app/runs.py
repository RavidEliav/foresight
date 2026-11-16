"""Helpers shared by the result pages: find the runs to show and read their artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import streamlit as st


def successful_runs(runs_dir: Path) -> list[Path]:
    """Finished, successful runs, newest first (failed runs are shown on the Run page)."""
    if not runs_dir.exists():
        return []
    found = []
    for path in sorted(runs_dir.iterdir(), reverse=True):
        manifest = read_json(path, "run_manifest.json") if path.is_dir() else None
        if manifest and manifest.get("status") == "success":
            found.append(path)
    return found


def viewable_runs(runs_dir: Path, reference: Path | None) -> list[Path]:
    runs = successful_runs(runs_dir)
    if reference is not None and (reference / "run_manifest.json").exists():
        runs.append(reference)
    return runs


def describe_run(run_dir: Path) -> str:
    """Short label for the run selector, e.g. '2026-11-16 15:14 UTC · SECOM (UCI)'."""
    if run_dir.name == "reference":
        return "Reference run (committed)"
    progress = read_json(run_dir, "progress.json") or {}
    name = run_dir.name
    when = (f"{name[:4]}-{name[4:6]}-{name[6:8]} {name[9:11]}:{name[11:13]} UTC"
            if len(name) >= 13 and name[8] == "T" else name)
    return f"{when} · {progress.get('dataset', 'SECOM (UCI)')}"


def run_label(run_dir: Path) -> str:
    return "Reference run" if run_dir.name == "reference" else f"Run `{run_dir.name}`"


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
