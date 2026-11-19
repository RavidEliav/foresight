"""A run's registry row, built from its files (manifest, progress and summaries).

The same rows go to the database and, without one, straight to the Trends page, so both
sources show the same numbers.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from foresight.progress import load_progress
from foresight.settings import Settings

RUN_COLUMNS = (
    "run_id", "environment", "source", "dataset", "status", "started_at", "finished_at",
    "duration_s", "rows", "fail_rate", "selected_model", "pr_auc", "baseline_pr_auc", "roc_auc",
    "recall", "precision", "balanced_accuracy", "runs_flagged", "flag_lift", "total_tokens",
    "llm_model", "llm_mock", "report_pass", "report_warning", "report_error", "gates",
    "failure_reason", "git_commit", "manifest",
)


def _json(run_dir: Path, name: str) -> dict:
    path = run_dir / name
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        return {}


def _seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 1)


def _source(run_dir: Path, manifest: dict, dataset: str | None, settings: Settings) -> str:
    if run_dir.resolve() == settings.resolve(settings.paths.reference_run_dir).resolve():
        return "reference"
    if manifest.get("scenario"):
        return "scenario"
    return "upload" if dataset and dataset.startswith("Uploaded") else "secom"


def run_record(run_dir: Path, settings: Settings) -> dict | None:
    """The run's row (None if the folder holds no run)."""
    manifest = _json(run_dir, "run_manifest.json")
    progress = load_progress(run_dir)
    if not manifest and progress is None:
        return None
    metrics = _json(run_dir, "model_metrics.json")
    test = metrics.get("test_metrics", {})
    overview = _json(run_dir, "eda_summary.json").get("overview", {})
    anomalies = _json(run_dir, "anomaly_summary.json")
    usage = manifest.get("crew_usage") or {}
    checks = manifest.get("report_checks") or {}
    llm = manifest.get("llm") or {}
    dataset = progress.dataset if progress else "SECOM (UCI)"
    started = progress.started_at if progress else manifest.get("created_at")
    finished = (progress.finished_at if progress else None) or manifest.get("created_at")
    duration = _seconds(started, finished) if progress else None
    if duration is None and manifest.get("durations_s"):
        duration = round(sum(manifest["durations_s"].values()), 1)
    gates = manifest.get("gates") or (progress.gates if progress else [])
    return {
        "run_id": manifest.get("run_id") or run_dir.name,
        "environment": manifest.get("environment") or settings.environment,
        "source": _source(run_dir, manifest, dataset, settings),
        "dataset": dataset,
        "status": progress.effective_status() if progress else manifest.get("status", "unknown"),
        "started_at": started,
        "finished_at": finished,
        "duration_s": duration,
        "rows": overview.get("rows"),
        "fail_rate": overview.get("fail_rate"),
        "selected_model": metrics.get("selected_model"),
        "pr_auc": test.get("pr_auc"),
        "baseline_pr_auc": metrics.get("baseline_pr_auc"),
        "roc_auc": test.get("roc_auc"),
        "recall": test.get("recall_fail"),
        "precision": test.get("precision_fail"),
        "balanced_accuracy": test.get("balanced_accuracy"),
        "runs_flagged": anomalies.get("runs_flagged"),
        "flag_lift": anomalies.get("flag_lift"),
        "total_tokens": sum(u.get("total_tokens") or 0 for u in usage.values()) or None,
        "llm_model": llm.get("model"),
        "llm_mock": llm.get("mock"),
        "report_pass": checks.get("PASS"),
        "report_warning": checks.get("WARNING"),
        "report_error": checks.get("ERROR"),
        "gates": [{"gate": g["gate"], "status": g["status"]} for g in gates],
        "failure_reason": (progress.failure_reason if progress else None),
        "git_commit": manifest.get("git_commit"),
        "manifest": manifest or None,
    }


def stage_records(run_dir: Path) -> list[dict]:
    """One row per stage, from progress.json (runs from the CLI or the app)."""
    progress = load_progress(run_dir)
    if progress is None:
        return []
    return [{"name": s.name, "position": i, "status": s.status, "crew_status": s.crew_status,
             "seconds": s.seconds, "crew_seconds": s.crew_seconds,
             "tokens": sum(u.get("total_tokens") or 0 for u in s.crew_usage.values()) or None}
            for i, s in enumerate(progress.stages)]


def chunk_records(run_dir: Path) -> list[dict]:
    """The run's chat chunks with their stored embeddings (written at the end of the run), for
    cross-run search; nothing is embedded again."""
    chunks, vectors = run_dir / "rag_chunks.json", run_dir / "rag_index.npz"
    if not (chunks.exists() and vectors.exists()):
        return []
    import numpy as np

    meta = json.loads(chunks.read_text(encoding="utf-8"))["chunks"]
    matrix = np.load(vectors)["vectors"]
    return [{"position": i, "source": c["source"], "section": c["section"], "body": c["text"],
             "embedding": matrix[i].tolist()} for i, c in enumerate(meta)]
