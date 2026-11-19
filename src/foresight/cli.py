"""Command line: ``python -m foresight.cli run [--run-id ID] [--dataset CSV] [--timeout S]
[--resume]``, ``python -m foresight.cli registry-sync`` (backfill the Supabase registry) and
``python -m foresight.cli db-migrate`` (apply pending Supabase migrations).

Used by the app for background runs, and handy for runs from a terminal. Adds a heartbeat to
progress.json and a timeout guard that stops the run and records why.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from pathlib import Path

from foresight.data.scenarios import Scenario
from foresight.flow import run_pipeline
from foresight.progress import ProgressTracker, new_run_id
from foresight.registry import record_run, sync
from foresight.settings import load_settings

TIMEOUT_EXIT_CODE = 3


def stop_on_timeout(tracker: ProgressTracker, timeout_s: int, settings=None) -> None:
    reason = f"stopped by the timeout guard after {timeout_s} s"
    tracker.finish("timeout", reason)
    (tracker.run_dir / "failure_report.md").write_text(
        f"# Run {tracker.progress.run_id} stopped\n\n**Reason:** {reason}\n", encoding="utf-8")
    if settings is not None:  # at most 3 s: the guard must stop the run whatever the database does
        writer = threading.Thread(target=record_run, args=(tracker.run_dir, settings),
                                  daemon=True)
        writer.start()
        writer.join(timeout=3)
    os._exit(TIMEOUT_EXIT_CODE)  # the Flow may be inside an LLM call; stop the process now


def run_command(run_id: str | None, dataset: Path | None, timeout_s: int | None,
                resume: bool = False, scenario_path: Path | None = None) -> int:
    settings = load_settings()
    if resume and not run_id:
        raise SystemExit("--resume needs --run-id")
    scenario = None
    if scenario_path is not None:
        recipe = json.loads(scenario_path.read_text(encoding="utf-8"))
        scenario = Scenario(**recipe.get("scenario", recipe))  # a request, or a resolved recipe
    run_id = run_id or new_run_id()
    run_dir = settings.resolve(settings.paths.runs_dir) / run_id
    label = "Uploaded CSV" if dataset else scenario.label() if scenario else None
    tracker = ProgressTracker.create(run_dir, run_id, label)
    if resume and tracker.progress.status != "queued":  # the app prepares it before starting
        tracker.prepare_resume()
    timeout_s = timeout_s or settings.app.run_timeout_s

    stop = threading.Event()

    def heartbeat() -> None:
        while not stop.wait(settings.app.heartbeat_s):
            tracker.save()

    threading.Thread(target=heartbeat, daemon=True).start()
    guard = threading.Timer(timeout_s, stop_on_timeout, args=(tracker, timeout_s, settings))
    guard.daemon = True
    guard.start()
    try:
        state = run_pipeline(settings, run_id, dataset, tracker, resume=resume, scenario=scenario)
    except Exception as exc:  # the Flow handles stage errors; this is a last resort
        tracker.finish("failed", f"unexpected error: {exc}")
        record_run(run_dir, settings)
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
    run.add_argument("--scenario", type=Path,
                     help="scenario.json: a synthetic variation of SECOM's training period")
    commands.add_parser("registry-sync",
                        help="record every run on disk and the reference run in Supabase")
    commands.add_parser("db-migrate",
                        help="apply pending Supabase migrations (Railway pre-deploy command)")
    args = parser.parse_args(argv)
    if args.command == "registry-sync":
        print(f"recorded {sync(load_settings())} runs", flush=True)
        return 0
    if args.command == "db-migrate":
        from foresight.registry.migrate import main as migrate_main

        return migrate_main()
    return run_command(args.run_id, args.dataset, args.timeout, args.resume, args.scenario)


if __name__ == "__main__":
    raise SystemExit(main())
