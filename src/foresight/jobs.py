"""Background pipeline runs started from the app.

A run is a separate process (``python -m foresight.cli run``), so it keeps going when the
browser is refreshed or closed. It writes progress.json and run.log into its run folder.
Limits (D8): one run at a time and ``app.max_runs_per_hour``, and enough free space on the
runs volume (a full volume killed two runs on 2026-11-22).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from foresight.progress import (
    ACTIVE,
    STOP_FILE,
    ProgressTracker,
    RunProgress,
    load_progress,
    new_run_id,
)
from foresight.settings import PROJECT_ROOT, Settings

UPLOAD_FILE = "upload.csv"
LOG_FILE = "run.log"
_START_LOCK = threading.Lock()
SERVER_STARTED = datetime.now(UTC)  # this app process: a run quiet since before was cut off
MIN_FREE_MB = 50                    # below this a run cannot start (it could not save its files)
DISK_FULL = "No space left on device"


class RunLimitError(RuntimeError):
    """A run can't start now (one is already running, or the hourly limit is reached)."""


def runs_dir(settings: Settings) -> Path:
    return settings.resolve(settings.paths.runs_dir)


def list_runs(settings: Settings) -> list[RunProgress]:
    """Runs started from the app or the CLI, newest first."""
    folder = runs_dir(settings)
    if not folder.exists():
        return []
    found = (load_progress(p) for p in sorted(folder.iterdir(), reverse=True) if p.is_dir())
    return [p for p in found if p is not None]


def active_run(settings: Settings) -> RunProgress | None:
    return next((p for p in list_runs(settings) if p.effective_status() in ACTIVE), None)


def runs_in_last_hour(settings: Settings) -> int:
    """Starts and continues in the last hour (both spend LLM tokens)."""
    since = datetime.now(UTC) - timedelta(hours=1)
    return sum(datetime.fromisoformat(t) > since for p in list_runs(settings)
               for t in (p.started_at, *p.resumed_at))


def check_can_start(settings: Settings) -> None:
    if running := active_run(settings):
        raise RunLimitError(f"Run {running.run_id} is still in progress. Only one run can "
                            "run at a time; its progress is shown below.")
    limit = settings.app.max_runs_per_hour
    if runs_in_last_hour(settings) >= limit:
        raise RunLimitError(f"The limit of {limit} runs per hour is reached. Please try again "
                            "later; the latest results stay available on every page.")


def prune_runs(settings: Settings, keep: set[str] | None = None) -> list[str]:
    """Free space on the runs volume (never touching an active run, nor the runs in ``keep``).

    With Supabase Storage (ADR-033) every finished run is archived there, and beyond the newest
    ``app.keep_full_runs`` only its stub stays. Without it, the oldest finished runs beyond
    ``app.keep_runs`` are deleted. The embedding model's old copy on the volume goes too when
    the model now lives elsewhere (about 170 MB)."""
    finished = [p for p in list_runs(settings)
                if p.effective_status() not in ACTIVE and p.run_id not in (keep or set())]
    removed = []
    if settings.archive:
        from foresight.registry.archive import archive_run, is_stub, make_stub

        for position, progress in enumerate(finished):
            folder = runs_dir(settings) / progress.run_id
            if not is_stub(folder) and archive_run(folder, settings) \
                    and position >= settings.app.keep_full_runs:
                make_stub(folder)
                removed.append(progress.run_id)
    else:
        for progress in finished[settings.app.keep_runs:]:
            shutil.rmtree(runs_dir(settings) / progress.run_id, ignore_errors=True)
            removed.append(progress.run_id)
    old_models = runs_dir(settings) / ".models"
    if old_models.exists() and settings.resolve(settings.paths.models_dir) != old_models:
        shutil.rmtree(old_models, ignore_errors=True)
    return removed


def tidy(settings: Settings) -> list[str]:
    """``prune_runs`` from the app's startup thread, never at the same time as a start."""
    with _START_LOCK:
        return prune_runs(settings)


def free_mb(settings: Settings) -> float | None:
    """Free space on the runs volume, in MB (None if it cannot be read)."""
    folder = runs_dir(settings)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(folder).free / 1e6
    except OSError:
        return None


def check_space(settings: Settings) -> None:
    free = free_mb(settings)
    if free is not None and free < MIN_FREE_MB:
        raise RunLimitError(f"The server's storage is full ({free:.0f} MB free), so a run "
                            "could not save its files. Please tell the developer.")


def log_tail(run_dir: Path, size: int = 8000) -> str:
    """The end of the run's log (its process's own output, errors included)."""
    path = run_dir / LOG_FILE
    try:
        with path.open("rb") as handle:
            handle.seek(max(0, path.stat().st_size - size))
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def interruption_cause(settings: Settings, run_dir: Path,
                       progress: RunProgress) -> tuple[str, str]:
    """Why a run stopped sending updates, in plain words, and what to do: the storage was
    full, the run crashed (its last error), the app restarted, or the process was killed
    without a word (usually memory)."""
    from foresight.utils.logging import redact

    resume = "Resume the run below: the stages it had finished are reused."
    tail = log_tail(run_dir)
    free = free_mb(settings)
    if DISK_FULL in tail or (free is not None and free < MIN_FREE_MB):
        return ("The server's storage was full, so the run could not save its files.",
                "Old runs are deleted when a run starts; if Resume fails again, please tell "
                "the developer.")
    if "Traceback" in tail:
        lines = [line.strip() for line in tail.splitlines() if line.strip()]
        error = next((line for line in reversed(lines)
                      if ":" in line and line.split(":", 1)[0].replace(".", "").isidentifier()
                      and not line.startswith("File ")), lines[-1])
        return f"The run crashed: {redact(error)[:300]}", resume
    if datetime.fromisoformat(progress.updated_at) < SERVER_STARTED:
        return ("The app restarted while the run was going (a new version was deployed, or "
                "the server restarted)."), resume
    return ("The run's process stopped without an error message, most likely because the "
            "server ran out of memory."), resume


def start_run(settings: Settings, upload: bytes | None = None,
              upload_name: str | None = None, scenario: dict | None = None,
              user: str = "") -> str:
    """Create the run folder and start the pipeline in a background process. ``scenario``
    (kind, intensity, seed) runs a synthetic variation of SECOM instead (Phase 8.3); ``user``
    is the signed-in email that started it (Phase 8.6)."""
    with _START_LOCK:
        check_can_start(settings)
        prune_runs(settings)
        check_space(settings)
        run_id = new_run_id()
        run_dir = runs_dir(settings) / run_id
        run_dir.mkdir(parents=True)
        command = [sys.executable, "-m", "foresight.cli", "run", "--run-id", run_id]
        label = "SECOM (UCI)"
        if upload is not None:
            (run_dir / UPLOAD_FILE).write_bytes(upload)
            command += ["--dataset", str(run_dir / UPLOAD_FILE)]
            label = f"Uploaded CSV ({upload_name or UPLOAD_FILE})"
        elif scenario is not None:
            from foresight.data.scenarios import SCENARIO_FILE, Scenario

            request = Scenario(**scenario)
            (run_dir / SCENARIO_FILE).write_text(request.model_dump_json(), encoding="utf-8")
            command += ["--scenario", str(run_dir / SCENARIO_FILE)]
            label = request.label()
        ProgressTracker.create(run_dir, run_id, label, started_by=user)
    _launch(command, run_dir)
    return run_id


def resume_run(settings: Settings, run_id: str, user: str = "") -> str:
    """Continue an interrupted (or timed-out, or crashed) run from where it stopped."""
    with _START_LOCK:
        check_can_start(settings)
        run_dir = runs_dir(settings) / run_id
        from foresight.registry.archive import ensure_full, is_stub

        if is_stub(run_dir) and not ensure_full(settings, run_dir):
            raise RunLimitError("The run's files could not be loaded from Supabase. Please try "
                                "again in a minute.")
        progress = load_progress(run_dir)
        if progress is None or not progress.can_continue:
            raise RunLimitError(f"Run {run_id} cannot be continued.")
        prune_runs(settings, keep={run_id})
        check_space(settings)
        command = [sys.executable, "-m", "foresight.cli", "run", "--run-id", run_id, "--resume"]
        if (run_dir / UPLOAD_FILE).exists():
            command += ["--dataset", str(run_dir / UPLOAD_FILE)]
        elif (run_dir / "scenario.json").exists():  # resolved recipe: same data again
            command += ["--scenario", str(run_dir / "scenario.json")]
        (run_dir / STOP_FILE).unlink(missing_ok=True)  # an earlier stop request is done
        ProgressTracker(run_dir=run_dir, progress=progress).prepare_resume(user)
    _launch(command, run_dir)
    return run_id


def stop_run(settings: Settings, run_id: str, user: str = "") -> None:
    """Ask a running run to stop (Phase 8.5). The run's process checks every second, records
    the run as stopped (the stages it finished stay reusable, so it can be resumed) and
    exits. The request names who asked (Phase 8.6)."""
    import json

    run_dir = runs_dir(settings) / run_id
    progress = load_progress(run_dir)
    if progress is None or progress.effective_status() not in ACTIVE:
        raise RunLimitError(f"Run {run_id} is not running.")
    (run_dir / STOP_FILE).write_text(json.dumps(
        {"at": datetime.now(UTC).isoformat(timespec="seconds"), "by": user}), encoding="utf-8")


def stop_requested(run_dir: Path) -> bool:
    return (run_dir / STOP_FILE).exists()


def _launch(command: list[str], run_dir: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(PROJECT_ROOT / "src"), env.get("PYTHONPATH")) if p)
    env["PYTHONUNBUFFERED"] = "1"
    detach = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
              else {"start_new_session": True})
    with (run_dir / LOG_FILE).open("ab") as log:
        process = subprocess.Popen(command, cwd=PROJECT_ROOT, env=env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, **detach)
    threading.Thread(target=process.wait, daemon=True).start()  # reap the finished process
