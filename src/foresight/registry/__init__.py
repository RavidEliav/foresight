"""Run registry (ADR-027): one summary row per run, for Run history and the Trends page.

With ``SUPABASE_DB_URL`` set, finished runs are recorded in Supabase Postgres and the history
is read from there, so it survives pruning and redeploys. Without it (tests, CI, a local
checkout), the same rows are built from the run folders. Recording never fails a run: a
database problem is logged and the run goes on.
"""

from __future__ import annotations

from pathlib import Path

from foresight.registry.record import RUN_COLUMNS, chunk_records, run_record, stage_records
from foresight.settings import Settings
from foresight.utils.logging import get_logger, redact

log = get_logger("registry")

__all__ = ["RUN_COLUMNS", "backend", "chunk_records", "history", "record_run", "run_record",
           "stage_history", "stage_records", "sync"]


def backend(settings: Settings) -> str:
    return "supabase" if settings.database_url else "files"


def record_run(run_dir: Path, settings: Settings, known: dict | None = None) -> bool:
    """Write the run's summary (and, for a successful run, its chat chunks for cross-run
    search) to the database, if configured; True when it was written. ``known`` (run id ->
    status and chunk count already recorded) lets a backfill skip unchanged runs."""
    if not settings.database_url:
        return False
    try:
        from foresight.registry import db

        run = run_record(run_dir, settings)
        if run is None:
            return False
        chunks = chunk_records(run_dir) if run["status"] == "success" else []
        if known is not None and known.get(run["run_id"]) == (run["status"], len(chunks)):
            return False
        db.upsert_run(settings.database_url, run, stage_records(run_dir), chunks)
        return True
    except Exception as exc:  # a registry problem must never fail the run
        log.warning("run %s not recorded in the registry: %s", run_dir.name, redact(exc))
        return False


def _run_folders(settings: Settings) -> list[Path]:
    folder = settings.resolve(settings.paths.runs_dir)
    found = [p for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")
             and p.name != "chat_logs"] if folder.exists() else []
    reference = settings.resolve(settings.paths.reference_run_dir)
    return found + ([reference] if reference.exists() else [])


def history(settings: Settings) -> list[dict]:
    """Every recorded run (newest first): from the database, else from the run folders."""
    if settings.database_url:
        from foresight.registry import db

        return db.fetch_runs(settings.database_url)
    rows = [r for p in _run_folders(settings) if (r := run_record(p, settings)) is not None]
    return sorted(rows, key=lambda r: r["started_at"] or "", reverse=True)


def stage_history(settings: Settings, run_ids: list[str]) -> list[dict]:
    """Stage rows (run_id, name, seconds, crew_seconds, ...) of the given runs."""
    if settings.database_url:
        from foresight.registry import db

        return db.fetch_stages(settings.database_url, run_ids)
    folders = {p.name: p for p in _run_folders(settings)}
    return [{"run_id": run_id, **stage} for run_id in run_ids if run_id in folders
            for stage in stage_records(folders[run_id])]


def sync(settings: Settings) -> int:
    """Record every run on disk and the reference run that the database does not have yet, or
    has with another status or chunk count (backfill; idempotent)."""
    if not settings.database_url:
        raise SystemExit("SUPABASE_DB_URL is not set")
    from foresight.registry import db

    known = db.recorded(settings.database_url)
    return sum(record_run(p, settings, known) for p in _run_folders(settings))
