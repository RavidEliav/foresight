"""Compare the analytics outputs of two runs: every number must be identical.

Phase 7 makes runs faster without changing results. The deterministic outputs (JSON summaries
and CSV tables) of a new run are compared value by value with a baseline run (default: the
committed reference run); LLM-written documents are not compared.

    python scripts/compare_runs.py <run_dir> [baseline_dir]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
JSON_FILES = ("validation_summary.json", "data_profile.json", "cleaning_report.json",
              "eda_summary.json", "feature_spec.json", "model_metrics.json",
              "anomaly_summary.json", "risk_summary.json", "similar_runs.json")
CSV_FILES = ("clean_data.csv", "features.csv", "predictions.csv", "oof_predictions.csv",
             "anomalies.csv", "risk_scores.csv", "similar_runs.csv", "run_embeddings.csv")
IGNORED_KEYS = {"figures"}  # file paths, not results


def differences(a, b, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            if key in IGNORED_KEYS:
                continue
            if key not in a or key not in b:
                out.append(f"{path}/{key}: only in {'baseline' if key in b else 'new run'}")
            else:
                out += differences(a[key], b[key], f"{path}/{key}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: {len(a)} items vs {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b, strict=True))
                for d in differences(x, y, f"{path}[{i}]")]
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return []
    return [] if a == b else [f"{path}: {a!r} vs {b!r}"]


def compare(run: Path, baseline: Path) -> list[str]:
    found = []
    for name in JSON_FILES:
        if (baseline / name).exists():
            new = json.loads((run / name).read_text(encoding="utf-8"))
            old = json.loads((baseline / name).read_text(encoding="utf-8"))
            found += [f"{name}{d}" for d in differences(new, old)]
    for name in CSV_FILES:
        if (baseline / name).exists():
            new, old = pd.read_csv(run / name), pd.read_csv(baseline / name)
            if not new.equals(old):
                found.append(f"{name}: tables differ")
    return found


def main(argv: list[str]) -> int:
    run = Path(argv[0])
    baseline = Path(argv[1]) if len(argv) > 1 else ROOT / "artifacts" / "reference"
    found = compare(run, baseline)
    for line in found[:40]:
        print("DIFF", line)
    print(f"{len(found)} differences between {run.name} and {baseline.name}")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
