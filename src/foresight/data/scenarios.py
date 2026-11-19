"""Scenario Lab (Phase 8.3): synthetic variations of SECOM, clearly labeled and kept separate.

A scenario changes **only the training period** of the original SECOM data: sensor drift, a
planted fault with known ground truth, a sensor outage, or a noisier line. The test period
is left untouched, so every evaluation metric (PR-AUC and the rest) is computed on the
original SECOM runs only, and is comparable with a run on the real data. The ingest stage
checks this (``test_period_is_original_secom``): if a single test-period value differs from
the original, the Data Contract gate stops the run.

The recipe (``scenario.json``) and the generated data (``scenario_data.csv``) are saved in the
run folder; the original SECOM files are never modified.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from foresight.analytics.features import time_split
from foresight.data.cleaning import CleaningConfig, clean
from foresight.validation.contract import Check
from foresight.validation.gates import GateStatus

SCENARIO_FILE = "scenario.json"
DATA_FILE = "scenario_data.csv"
Kind = Literal["drift", "planted_fault", "sensor_outage", "noise"]

# title, what it does, default intensity (in training standard deviations), sensors changed
KINDS: dict[str, tuple[str, str, float, int]] = {
    "planted_fault": ("Planted fault", "One sensor is shifted on the failing training runs: a "
                      "known cause, to see whether Foresight finds it.", 1.5, 1),
    "drift": ("Sensor drift", "A few sensors drift steadily over the training period, as a "
              "tool ages between maintenance.", 2.0, 5),
    "sensor_outage": ("Sensor outage", "A few sensors stop reporting (missing values) for a "
                      "stretch of the training period.", 0.3, 10),
    "noise": ("Noisy line", "Every sensor gets extra random noise in the training period.",
              0.5, 0),
}


class Scenario(BaseModel):
    kind: Kind
    intensity: float | None = None  # std units (outage: share of the training period)
    seed: int = 7
    sensors: list[str] = Field(default_factory=list)  # chosen with the seed when empty

    def resolved_intensity(self) -> float:
        return self.intensity if self.intensity is not None else KINDS[self.kind][2]

    @property
    def title(self) -> str:
        return KINDS[self.kind][0]

    def label(self) -> str:
        """Dataset label used everywhere the run is listed."""
        target = f" on {', '.join(self.sensors[:3])}" if self.sensors else ""
        more = f" +{len(self.sensors) - 3}" if len(self.sensors) > 3 else ""
        return f"Scenario (synthetic): {self.title.lower()}{target}{more}"


def load_scenario(run_dir: Path) -> dict | None:
    path = run_dir / SCENARIO_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _training_ids(raw: pd.DataFrame, config: CleaningConfig, test_fraction: float) -> set[int]:
    """The run ids that the pipeline will put in the training period (same cleaning and time
    split as the model stage)."""
    cleaned, _ = clean(raw, config)
    split = time_split(cleaned, test_fraction)
    return set(cleaned.loc[split == "train", "run_id"])


def _candidates(raw: pd.DataFrame, train: pd.Series, features: list[str]) -> list[str]:
    """Well-measured sensors that do not already separate failing from passing runs (so a
    planted signal is the scenario's, not SECOM's)."""
    part = raw.loc[train, features]
    stats = pd.DataFrame({"missing": part.isna().mean(), "std": part.std()})
    usable = stats[(stats.missing < 0.05) & (stats["std"] > 0)].index
    fail = raw.loc[train, "label_raw"] == 1
    effect = ((part.loc[fail, usable].median() - part.loc[~fail, usable].median()).abs()
              / stats.loc[usable, "std"])
    return sorted(effect.sort_values().index[: max(10, len(usable) // 2)])


def generate(raw: pd.DataFrame, scenario: Scenario, config: CleaningConfig,
             test_fraction: float) -> tuple[pd.DataFrame, Scenario, dict]:
    """The scenario's dataset (same runs and timestamps; only training rows changed), the
    scenario with its sensors resolved, and the ground truth to record."""
    # one generator per random step, so a saved recipe (sensors already chosen) gives the same
    # data again: picking the sensors must not shift the outage window or the noise
    pick, window, noise = (np.random.default_rng([scenario.seed, step]) for step in range(3))
    features = config.contract_features or [c for c in raw.columns if c.startswith("f_")]
    train_ids = _training_ids(raw, config, test_fraction)
    train = raw.run_id.isin(train_ids)
    title, _, _, count = KINDS[scenario.kind]
    sensors = scenario.sensors
    if not sensors and count:
        pool = _candidates(raw, train, features)
        sensors = sorted(pick.choice(pool, size=min(count, len(pool)), replace=False).tolist())
    scenario = scenario.model_copy(update={"sensors": sensors})
    intensity = scenario.resolved_intensity()
    data = raw.copy()
    std = raw.loc[train, features].std().fillna(0.0)
    order = data.loc[train].sort_values(["timestamp", "run_id"]).index

    if scenario.kind == "planted_fault":
        failing = train & (data.label_raw == 1)
        for sensor in sensors:
            data.loc[failing, sensor] += intensity * std[sensor]
    elif scenario.kind == "drift":
        ramp = pd.Series(np.linspace(0.0, 1.0, len(order)), index=order)
        for sensor in sensors:
            data.loc[order, sensor] += ramp * intensity * std[sensor]
    elif scenario.kind == "sensor_outage":
        length = max(1, int(len(order) * min(intensity, 0.9)))
        start = int(window.integers(0, len(order) - length + 1))
        data.loc[order[start:start + length], sensors] = np.nan
    elif scenario.kind == "noise":
        values = data.loc[train, features]
        data.loc[train, features] = values + noise.normal(size=values.shape) * (
            intensity * std.to_numpy())

    changed = (data[features].fillna(-1e300) != raw[features].fillna(-1e300)).any(axis=1)
    truth = {"kind": scenario.kind, "title": title, "sensors": sensors, "intensity": intensity,
             "seed": scenario.seed, "training_runs": int(train.sum()),
             "training_runs_changed": int(changed.sum()),
             "test_runs_untouched": int((~train).sum()), "synthetic": True,
             "evaluated_on": "the original SECOM test period (unchanged)"}
    return data, scenario, truth


def check_test_period(original: pd.DataFrame, scenario_data: pd.DataFrame,
                      config: CleaningConfig, test_fraction: float) -> Check:
    """PASS only if the cleaned test period equals the original SECOM test period exactly, so
    the model is evaluated on real data only."""
    def test_rows(raw: pd.DataFrame) -> pd.DataFrame:
        cleaned, _ = clean(raw, config)
        return cleaned.loc[time_split(cleaned, test_fraction) == "test"].reset_index(drop=True)

    expected, found = test_rows(original), test_rows(scenario_data)
    same = expected.shape == found.shape and expected.equals(found)
    return Check(name="test_period_is_original_secom",
                 status=GateStatus.PASS if same else GateStatus.ERROR,
                 message=(f"the {len(found)} test-period runs are the original SECOM runs, "
                          "unchanged; metrics are computed on real data only") if same else
                         "the test period differs from the original SECOM data: a synthetic "
                         "scenario may change only the training period")


CHECK_FILE = "scenario_check.json"


def _rank(names: list[str], sensor: str) -> int | None:
    return names.index(sensor) + 1 if sensor in names else None


def ground_truth_check(run_dir: Path) -> tuple[dict, Check] | None:
    """Did the analysis find what the scenario changed? For every target sensor: its rank
    among the sensors that differ most between failing and passing runs (EDA), its rank in
    the model's importance (measured on the real test period, where the change does not
    exist), and whether the investigation or the report names it. Writes scenario_check.json."""
    import re

    recipe = load_scenario(run_dir)
    if recipe is None:
        return None
    truth = recipe["ground_truth"]

    def read(name: str) -> dict:
        path = run_dir / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    eda = [f["feature"] for f in read("eda_summary.json").get("top_discriminating_features", [])]
    model = [f["feature"] for f in read("model_metrics.json").get("top_features_permutation")
             or []]
    text = " ".join((run_dir / n).read_text(encoding="utf-8") for n in
                    ("investigation.md", "engineering_report.md") if (run_dir / n).exists())
    rows = [{"sensor": s, "eda_rank": _rank(eda, s), "eda_listed": len(eda),
             "model_rank": _rank(model, s), "in_reports": bool(re.search(rf"\b{s}\b", text))}
            for s in truth["sensors"]]
    found = [r["sensor"] for r in rows if r["eda_rank"] or r["in_reports"]]
    result = {**truth, "label": recipe["label"], "sensors_checked": rows, "found": found}
    (run_dir / CHECK_FILE).write_text(json.dumps(result, indent=2), encoding="utf-8")
    if truth["kind"] == "planted_fault":
        status = GateStatus.PASS if found else GateStatus.WARNING
        message = (f"planted sensor {', '.join(truth['sensors'])} "
                   + ("found by the analysis" if found else "not found by the analysis"))
    else:
        status = GateStatus.PASS
        message = (f"{truth['title'].lower()} on {len(truth['sensors']) or 'all'} sensors; "
                   f"{len(found)} named by the analysis")
    return result, Check(name="scenario_ground_truth", status=status, message=message)


def banner(result: dict) -> str:
    """The note that opens a scenario run's engineering report (deterministic, not LLM)."""
    found = ", ".join(result["found"]) or "none"
    sensors = ", ".join(result["sensors"]) or "all sensors"
    return (f"> **SYNTHETIC SCENARIO: {result['title']}.** {KINDS[result['kind']][1]} Only the "
            f"training period was changed (sensors: {sensors}); the test period is the "
            "original SECOM data, so every metric in this report is computed on real runs "
            f"only. Changed sensors that the analysis named: {found}.\n\n")
