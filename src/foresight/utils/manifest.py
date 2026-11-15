"""Run manifest: everything needed to reproduce or audit a run."""

from __future__ import annotations

import json
import os
import platform
import subprocess
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from foresight.settings import PROJECT_ROOT, Settings

TRACKED_PACKAGES = ("crewai", "pandas", "scikit-learn", "numpy", "streamlit")


def git_commit() -> str:
    if sha := os.getenv("RAILWAY_GIT_COMMIT_SHA"):
        return sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def package_versions() -> dict[str, str]:
    versions = {}
    for name in TRACKED_PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return versions


def build_manifest(run_id: str, settings: Settings, **extra: Any) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "environment": settings.environment,
        "python": platform.python_version(),
        "packages": package_versions(),
        "seed": settings.seed,
        "llm": {
            "model": settings.llm.model,
            "temperature": settings.llm.temperature,
            "mock": settings.mock_llm,
        },
        **extra,
    }


def write_manifest(manifest: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return path
