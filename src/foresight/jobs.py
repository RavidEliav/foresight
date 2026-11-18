"""Background pipeline runs started from the app.

A run is a separate process (``python -m foresight.cli run``), so it keeps going when the
browser is refreshed or closed. It writes progress.json and run.log into its run folder.
Limits (D8): one run at a time and ``app.max_runs_per_hour``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from foresight.flow import new_run_id
from foresight.progress import ACTIVE, ProgressTracker, RunProgress, load_progress
from foresight.settings import PROJECT_ROOT, Settings

UPLOAD_FILE = "upload.csv"
LOG_FILE = "run.log"
_START_LOCK = threading.Lock()


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


def prune_runs(settings: Settings) -> list[str]:
    """Delete the oldest finished runs beyond ``app.keep_runs``; active runs are never touched."""
    finished = [p for p in list_runs(settings) if p.effective_status() not in ACTIVE]
    removed = []
    for progress in finished[settings.app.keep_runs:]:
        shutil.rmtree(runs_dir(settings) / progress.run_id, ignore_errors=True)
        removed.append(progress.run_id)
    return removed


def start_run(settings: Settings, upload: bytes | None = None,
              upload_name: str | None = None) -> str:
    """Create the run folder and start the pipeline in a background process."""
    with _START_LOCK:
        check_can_start(settings)
        prune_runs(settings)
        run_id = new_run_id()
        run_dir = runs_dir(settings) / run_id
        run_dir.mkdir(parents=True)
        command = [sys.executable, "-m", "foresight.cli", "run", "--run-id", run_id]
        label = "SECOM (UCI)"
        if upload is not None:
            (run_dir / UPLOAD_FILE).write_bytes(upload)
            command += ["--dataset", str(run_dir / UPLOAD_FILE)]
            label = f"Uploaded CSV ({upload_name or UPLOAD_FILE})"
        ProgressTracker.create(run_dir, run_id, label)
    _launch(command, run_dir)
    return run_id


def resume_run(settings: Settings, run_id: str) -> str:
    """Continue an interrupted (or timed-out, or crashed) run from where it stopped."""
    with _START_LOCK:
        check_can_start(settings)
        run_dir = runs_dir(settings) / run_id
        progress = load_progress(run_dir)
        if progress is None or not progress.can_continue:
            raise RunLimitError(f"Run {run_id} cannot be continued.")
        command = [sys.executable, "-m", "foresight.cli", "run", "--run-id", run_id, "--resume"]
        if (run_dir / UPLOAD_FILE).exists():
            command += ["--dataset", str(run_dir / UPLOAD_FILE)]
        ProgressTracker(run_dir=run_dir, progress=progress).prepare_resume()
    _launch(command, run_dir)
    return run_id


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
