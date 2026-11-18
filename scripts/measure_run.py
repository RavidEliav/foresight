"""Measure a pipeline run: wall time per stage and peak memory (RSS) of the run process.

Starts ``python -m foresight.cli run`` (mock LLM unless --real), samples its RSS (with child
processes) every 0.2 s, and reads the stage being run from progress.json. Prints a table and
writes ``measure.json`` into the run folder. Needs ``psutil`` (pip install psutil); it is a
measurement tool, not an app dependency.

    python scripts/measure_run.py [--real]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from foresight.progress import load_progress, new_run_id  # noqa: E402
from foresight.settings import load_settings  # noqa: E402


def rss_mb(process: psutil.Process) -> float:
    total = 0
    for p in [process, *process.children(recursive=True)]:
        with contextlib.suppress(psutil.Error):
            total += p.memory_info().rss
    return total / 2**20


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="use the real LLM (costs tokens)")
    args = parser.parse_args()
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONUNBUFFERED="1",
               MOCK_LLM="false" if args.real else "true")
    settings = load_settings()
    run_id = new_run_id()
    run_dir = settings.resolve(settings.paths.runs_dir) / run_id
    start = time.perf_counter()
    child = subprocess.Popen([sys.executable, "-m", "foresight.cli", "run", "--run-id", run_id],
                             cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    process = psutil.Process(child.pid)
    peaks: dict[str, float] = {}
    while child.poll() is None:
        progress = load_progress(run_dir)
        stage = progress.current.name if progress and progress.current else "startup"
        with contextlib.suppress(psutil.Error):
            peaks[stage] = max(peaks.get(stage, 0.0), rss_mb(process))
        time.sleep(0.2)
    total = time.perf_counter() - start
    progress = load_progress(run_dir)
    seconds = {s.name: s.seconds for s in progress.stages} if progress else {}
    print(f"run {run_id}: {progress.status if progress else '?'} in {total:.1f} s")
    print(f"{'stage':<12}{'seconds':>9}{'peak MB':>9}")
    for name in ["startup", *seconds]:
        print(f"{name:<12}{seconds.get(name) or 0:>9.1f}{peaks.get(name, 0):>9.0f}")
    result = {"run_id": run_id, "total_s": round(total, 1), "stage_s": seconds,
              "peak_mb": {k: round(v) for k, v in peaks.items()}, "real_llm": args.real}
    (run_dir / "measure.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
