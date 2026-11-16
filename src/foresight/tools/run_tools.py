"""Read-only CrewAI tools over one run's artifacts.

Agents never see raw sensor data: every tool returns a compact JSON summary of numbers that
deterministic Python code already computed (ADR-005). Each value can be traced to a file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

MAX_CHARS = 6000


def _dump(payload: dict, source: list[str]) -> str:
    text = json.dumps({"source_files": source, **payload}, default=str)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + '..."(truncated)"'


def _read(run_dir: Path, name: str) -> dict:
    return json.loads((run_dir / name).read_text(encoding="utf-8"))


class _RunTool(BaseTool):
    run_dir: Path

    def _missing(self, *names: str) -> str | None:
        absent = [n for n in names if not (self.run_dir / n).exists()]
        return _dump({"error": f"not available yet: {', '.join(absent)}"}, []) if absent else None


class DataQualityTool(_RunTool):
    name: str = "data_quality_summary"
    description: str = ("Data Contract validation results, cleaning decisions and dataset "
                        "profile (rows, features, fail rate, missing values).")

    def _run(self) -> str:
        files = ["validation_summary.json", "cleaning_report.json", "data_profile.json"]
        if error := self._missing(*files):
            return error
        validation = _read(self.run_dir, files[0])
        cleaning = _read(self.run_dir, files[1])
        return _dump({
            "validation_status": validation["status"],
            "validation_counts": validation["counts"],
            "non_passing_checks": [c for c in validation["checks"] if c["status"] != "PASS"],
            "cleaning_decisions": cleaning["decisions"],
            "features_kept": cleaning["features_out"],
            "features_in": cleaning["features_in"],
            "profile": _read(self.run_dir, files[2]),
        }, files)


class EdaSummaryTool(_RunTool):
    name: str = "eda_summary"
    description: str = ("Exploratory analysis: monthly fail rates, missing data, and the sensors "
                        "that differ most between failing and passing runs (with q-values).")

    def _run(self) -> str:
        if error := self._missing("eda_summary.json"):
            return error
        eda = _read(self.run_dir, "eda_summary.json")
        eda.pop("figures", None)
        eda.pop("weekly_fail_rate", None)
        return _dump(eda, ["eda_summary.json"])


class ModelMetricsTool(_RunTool):
    name: str = "model_metrics"
    description: str = ("Model comparison (time-ordered CV and test PR-AUC), selected model, "
                        "decision threshold, test metrics with 95% confidence intervals, "
                        "confusion matrix and most important sensors.")

    def _run(self) -> str:
        if error := self._missing("model_metrics.json"):
            return error
        metrics = _read(self.run_dir, "model_metrics.json")
        metrics.pop("figures", None)
        return _dump(metrics, ["model_metrics.json"])


class AnomalySummaryTool(_RunTool):
    name: str = "anomaly_summary"
    description: str = ("Anomaly detection results: how often failing vs passing runs are "
                        "flagged, sensors more often out of control limits in failing runs, and "
                        "the most anomalous runs.")

    def _run(self) -> str:
        if error := self._missing("anomaly_summary.json"):
            return error
        summary = _read(self.run_dir, "anomaly_summary.json")
        summary.pop("figures", None)
        return _dump(summary, ["anomaly_summary.json"])


class RiskRankingTool(_RunTool):
    name: str = "risk_ranking"
    description: str = ("Risk ranking of the test-period runs: which ranking is recommended "
                        "(model alone or model + anomaly score, chosen by cross-validation), "
                        "how many failing runs it finds with the alarm budget, and the "
                        "riskiest runs with their strongest signals.")

    def _run(self) -> str:
        if error := self._missing("risk_summary.json"):
            return error
        return _dump(_read(self.run_dir, "risk_summary.json"), ["risk_summary.json"])


class RunLookupInput(BaseModel):
    run_id: int = Field(description="Production run id (0-1566)")


class RunLookupTool(_RunTool):
    name: str = "run_details"
    description: str = ("Details of one production run: label, timestamp, anomaly score and "
                        "flag, number of sensors out of limits, strongest signals, and, for "
                        "test-period runs, the model's fail probability and the risk rank.")
    args_schema: type[BaseModel] = RunLookupInput

    def _run(self, run_id: int) -> str:
        if error := self._missing("anomalies.csv"):
            return error
        anomalies = pd.read_csv(self.run_dir / "anomalies.csv")
        row = anomalies[anomalies["run_id"] == run_id]
        if row.empty:
            return _dump({"error": f"run {run_id} not found"}, ["anomalies.csv"])
        details = row.iloc[0].to_dict()
        sources = ["anomalies.csv"]
        predictions = self.run_dir / "predictions.csv"
        if predictions.exists():
            pred = pd.read_csv(predictions)
            match = pred[pred["run_id"] == run_id]
            if not match.empty:
                details["fail_probability"] = float(match.iloc[0]["fail_probability"])
                details["predicted_fail"] = int(match.iloc[0]["predicted_fail"])
                sources.append("predictions.csv")
        risk = self.run_dir / "risk_scores.csv"
        if risk.exists():
            ranked = pd.read_csv(risk).reset_index(drop=True)
            match = ranked[ranked["run_id"] == run_id]
            if not match.empty:
                details["risk_score"] = float(match.iloc[0]["risk_score"])
                details["risk_rank_in_test"] = int(match.index[0]) + 1
                details["flagged_by_alarm_budget"] = int(match.iloc[0]["flagged"])
                sources.append("risk_scores.csv")
        return _dump({"run": details}, sources)


class SensorInput(BaseModel):
    feature: str = Field(description="Sensor name, for example f_059")


class SensorStatsTool(_RunTool):
    name: str = "sensor_stats"
    description: str = ("Everything computed about one sensor: pass vs fail medians and test "
                        "result, how often it is out of limits in failing vs passing runs, and "
                        "its importance rank in the model.")
    args_schema: type[BaseModel] = SensorInput

    def _run(self, feature: str) -> str:
        if error := self._missing("eda_summary.json", "anomaly_summary.json",
                                  "model_metrics.json"):
            return error
        eda = _read(self.run_dir, "eda_summary.json")
        anomalies = _read(self.run_dir, "anomaly_summary.json")
        metrics = _read(self.run_dir, "model_metrics.json")
        ranks = [r["feature"] for r in metrics["top_features_permutation"]]
        return _dump({
            "feature": feature,
            "pass_vs_fail_test": next((r for r in eda["top_discriminating_features"]
                                       if r["feature"] == feature), None),
            "out_of_limit": next((r for r in anomalies["sensors_more_often_out_of_limit_in_fails"]
                                  if r["feature"] == feature), None),
            "importance_rank": ranks.index(feature) + 1 if feature in ranks else None,
            "note": "None means the sensor is not in that top list.",
        }, ["eda_summary.json", "anomaly_summary.json", "model_metrics.json"])


def build_tools(run_dir: Path) -> dict[str, BaseTool]:
    tools = [DataQualityTool, EdaSummaryTool, ModelMetricsTool, AnomalySummaryTool,
             RiskRankingTool, RunLookupTool, SensorStatsTool]
    return {tool.model_fields["name"].default: tool(run_dir=run_dir) for tool in tools}
