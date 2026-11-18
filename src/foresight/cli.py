"""Command line: ``python -m foresight.cli run [--run-id ID] [--dataset CSV] [--timeout S]
[--resume]``.

Used by the app for background runs, and handy for runs from a terminal. Adds a heartbeat to
progress.json and a timeout guard that stops the run and records why.
"""

from __future__ import annotations

import argparse
import os
import threading
from pathlib import Path

from foresight.flow import new_run_id, run_pipeline
from foresight.progress import ProgressTracker
from foresight.settings import load_settings

TIMEOUT_EXIT_CODE = 3


def stop_on_timeout(tracker: ProgressTracker, timeout_s: int) -> None:
    reason = f"stopped by the timeout guard after {timeout_s} s"
    tracker.finish("timeout", reason)
    (tracker.run_dir / "failure_report.md").write_text(
        f"# Run {tracker.progress.run_id} stopped\n\n**Reason:** {reason}\n", encoding="utf-8")
    os._exit(TIMEOUT_EXIT_CODE)  # the Flow may be inside an LLM call; stop the process now


def run_command(run_id: str | None, dataset: Path | None, timeout_s: int | None,
                resume: bool = False) -> int:
    settings = load_settings()
    if resume and not run_id:
        raise SystemExit("--resume needs --run-id")
    run_id = run_id or new_run_id()
    run_dir = settings.resolve(settings.paths.runs_dir) / run_id
    tracker = ProgressTracker.create(run_dir, run_id, "Uploaded CSV" if dataset else None)
    if resume and tracker.progress.status != "queued":  # the app prepares it before starting
        tracker.prepare_resume()
    timeout_s = timeout_s or settings.app.run_timeout_s

    stop = threading.Event()

    def heartbeat() -> None:
        while not stop.wait(settings.app.heartbeat_s):
            tracker.save()

    threading.Thread(target=heartbeat, daemon=True).start()
    guard = threading.Timer(timeout_s, stop_on_timeout, args=(tracker, timeout_s))
    guard.daemon = True
    guard.start()
    try:
        state = run_pipeline(settings, run_id, dataset, tracker, resume=resume)
    except Exception as exc:  # the Flow handles stage errors; this is a last resort
        tracker.finish("failed", f"unexpected error: {exc}")
        raise
    finally:
        guard.cancel()
        stop.set()
    print(f"run {state.run_id}: {state.status}"
          + (f" ({state.failure_reason})" if state.failure_reason else ""), flush=True)
    return 0 if state.status == "success" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foresight", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run the whole pipeline")
    run.add_argument("--run-id", help="run folder name (default: a new time-based id)")
    run.add_argument("--dataset", type=Path, help="CSV to analyze instead of the SECOM files")
    run.add_argument("--timeout", type=int, help="seconds before the timeout guard stops the run")
    run.add_argument("--resume", action="store_true",
                     help="continue the interrupted run --run-id, reusing its finished stages")
    args = parser.parse_args(argv)
    return run_command(args.run_id, args.dataset, args.timeout, args.resume)


if __name__ == "__main__":
    raise SystemExit(main())
