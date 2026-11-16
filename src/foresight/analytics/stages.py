"""Analytics stages called by the Flow. Each returns artifact paths and, where a gate follows,
a ValidationSummary that the gate turns into PASS / WARNING / ERROR."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field

from foresight.analytics.anomalies import detect
from foresight.analytics.eda import build_eda
from foresight.analytics.features import SPLIT, FeatureSpec, engineer
from foresight.analytics.modeling import train_and_evaluate
from foresight.analytics.risk import rank_risk
from foresight.crews.checks import check_outputs
from foresight.crews.runner import run_crew
from foresight.settings import Settings
from foresight.validation.contract import Check, ValidationSummary
from foresight.validation.gates import GateStatus


class StageResult(BaseModel):
    artifacts: dict[str, str] = Field(default_factory=dict)
    checks: ValidationSummary | None = None
    crew_usage: dict[str, dict] = Field(default_factory=dict)


REPORT_INPUTS = ("insights.md", "model_card.md", "investigation.md")
CREW_OUTPUTS = [*REPORT_INPUTS, "engineering_report.md"]
REVISIONS_FILE = "crew_revisions.json"


def _problems(checks: ValidationSummary) -> list[str]:
    return [f"{c.name}: {c.message}" for c in checks.checks if c.status != GateStatus.PASS]


def _add_usage(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in {*a, *b}
            if isinstance(a.get(k, b.get(k)), int | float)
            and not isinstance(a.get(k, b.get(k)), bool)}


def _with_crew(result: StageResult, crew: str, settings: Settings, run_dir: Path,
               extra_inputs: dict[str, str] | None = None) -> StageResult:
    """Run a crew after the deterministic work of a stage and record its outputs and usage.
    If the deterministic checks on the crew's own output warn, the crew gets the findings and
    revises it (at most settings.llm.crew_revisions times); revisions go to crew_revisions.json."""
    inputs = dict(extra_inputs or {})
    outcome = run_crew(crew, settings, run_dir, inputs)
    usage = {"seconds": outcome.seconds, **outcome.usage}
    files = list(outcome.outputs)
    fixed: list[str] = []
    revisions = 0
    for _ in range(settings.llm.crew_revisions):
        problems = _problems(check_outputs(run_dir, files))
        if not problems:
            break
        notes = ("REVISION REQUEST: the previous version of this output failed these automatic "
                 "checks. Fix them and keep everything else as required above:\n- "
                 + "\n- ".join(problems))
        again = run_crew(crew, settings, run_dir, {**inputs, "revision_notes": notes})
        usage = _add_usage(usage, {"seconds": again.seconds, **again.usage})
        fixed += problems
        revisions += 1
    if fixed:
        path = run_dir / REVISIONS_FILE
        log = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        log[crew] = fixed
        path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    result.artifacts.update({Path(p).stem: p for p in outcome.outputs.values()})
    result.crew_usage[crew] = {**usage, "mock": outcome.mock, "revisions": revisions}
    return result


def load_clean(run_dir: Path) -> pd.DataFrame:
    return pd.read_csv(run_dir / "clean_data.csv", parse_dates=["timestamp"])


def load_features(run_dir: Path) -> tuple[pd.DataFrame, FeatureSpec]:
    frame = pd.read_csv(run_dir / "features.csv", parse_dates=["timestamp"])
    spec = FeatureSpec.model_validate_json((run_dir / "feature_spec.json").read_text())
    return frame, spec


def run_analyze(settings: Settings, run_dir: Path) -> StageResult:
    """EDA + feature engineering; checks that modeling has what it needs (features gate)."""
    cfg = settings.analytics
    cleaned = load_clean(run_dir)
    build_eda(cleaned, run_dir, cfg.top_features)
    frame, spec = engineer(cleaned, cfg.test_fraction, cfg.corr_threshold)
    frame.to_csv(run_dir / "features.csv", index=False, date_format="%Y-%m-%dT%H:%M:%S")
    (run_dir / "feature_spec.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    result = StageResult(
        artifacts={name: str(run_dir / file) for name, file in (
            ("eda_report", "eda_report.html"), ("eda_summary", "eda_summary.json"),
            ("features", "features.csv"), ("feature_spec", "feature_spec.json"))},
        checks=feature_checks(frame, spec, settings),
    )
    return _with_crew(result, "analyst", settings, run_dir)


def feature_checks(frame: pd.DataFrame, spec: FeatureSpec, settings: Settings) -> ValidationSummary:
    cfg = settings.analytics
    missing = [c for c in spec.features + ["label", SPLIT] if c not in frame.columns]
    counts = spec.split_counts
    checks = [
        Check(name="required_features", status=GateStatus.ERROR if missing else GateStatus.PASS,
              message=f"missing columns: {', '.join(missing[:5])}" if missing
              else f"all {len(spec.features)} model features present"),
        Check(name="train_fails",
              status=GateStatus.PASS if counts["train"]["fails"] >= cfg.min_fails_train
              else GateStatus.ERROR,
              message=f"{counts['train']['fails']} failing runs in training "
                      f"(minimum {cfg.min_fails_train})"),
        Check(name="test_fails",
              status=GateStatus.PASS if counts["test"]["fails"] >= cfg.min_fails_test
              else GateStatus.ERROR,
              message=f"{counts['test']['fails']} failing runs in the test period "
                      f"(minimum {cfg.min_fails_test})"),
    ]
    return ValidationSummary.from_checks(checks)


def run_model(settings: Settings, run_dir: Path) -> StageResult:
    frame, spec = load_features(run_dir)
    train_and_evaluate(frame, spec, settings.analytics, settings.seed, run_dir)
    result = StageResult(artifacts={name: str(run_dir / file) for name, file in (
        ("model", "model.joblib"), ("model_metrics", "model_metrics.json"),
        ("evaluation_report", "evaluation_report.md"), ("predictions", "predictions.csv"),
        ("oof_predictions", "oof_predictions.csv"))})
    return _with_crew(result, "scientist", settings, run_dir)


def run_investigate(settings: Settings, run_dir: Path) -> StageResult:
    """Anomaly detection and risk ranking; checks the evidence for the report (evidence gate)."""
    frame, spec = load_features(run_dir)
    anomalies = detect(frame, spec, settings.analytics, settings.seed, run_dir)
    risk = rank_risk(run_dir, settings.analytics, settings.seed)
    metrics = json.loads((run_dir / "model_metrics.json").read_text(encoding="utf-8"))
    eda = json.loads((run_dir / "eda_summary.json").read_text(encoding="utf-8"))
    result = StageResult(
        artifacts={"anomalies": str(run_dir / "anomalies.csv"),
                   "anomaly_summary": str(run_dir / "anomaly_summary.json"),
                   "risk_scores": str(run_dir / "risk_scores.csv"),
                   "risk_summary": str(run_dir / "risk_summary.json")},
        checks=evidence_checks(metrics, anomalies, eda, risk),
    )
    return _with_crew(result, "investigation", settings, run_dir)


def run_report(settings: Settings, run_dir: Path) -> StageResult:
    """Engineering Report crew, then deterministic checks on all crew outputs (revisions made
    by any crew are listed as their own checks)."""
    inputs = {Path(name).stem: (run_dir / name).read_text(encoding="utf-8")
              for name in REPORT_INPUTS if (run_dir / name).exists()}
    result = _with_crew(StageResult(), "report", settings, run_dir, inputs)
    checks = check_outputs(run_dir, CREW_OUTPUTS)
    revisions_path = run_dir / REVISIONS_FILE
    if revisions_path.exists():
        revised = json.loads(revisions_path.read_text(encoding="utf-8"))
        checks = ValidationSummary.from_checks([*checks.checks, *(
            Check(name=f"{crew} crew: revision", status=GateStatus.PASS,
                  message="revised after: " + "; ".join(problems))
            for crew, problems in revised.items())])
        result.artifacts["crew_revisions"] = str(revisions_path)
    (run_dir / "report_checks.json").write_text(checks.model_dump_json(indent=2),
                                                encoding="utf-8")
    result.artifacts["report_checks"] = str(run_dir / "report_checks.json")
    result.checks = checks
    return result


def evidence_checks(metrics: dict, anomalies: dict, eda: dict,
                    risk: dict | None = None) -> ValidationSummary:
    pr_auc = metrics["test_metrics"]["pr_auc"]
    baseline = metrics["baseline_pr_auc"]
    significant = eda.get("significant_features_q_below_0.05", 0)
    lift = anomalies.get("flag_lift")
    checks = [
        Check(name="model_metrics", status=GateStatus.PASS,
              message=f"selected model {metrics['selected_model']} evaluated"),
        Check(name="model_beats_baseline",
              status=GateStatus.PASS if pr_auc > baseline else GateStatus.WARNING,
              message=f"test PR-AUC {pr_auc:.3f} vs random {baseline:.3f}"
              + ("" if pr_auc > baseline else ": predictive evidence is weak")),
        Check(name="significant_sensors",
              status=GateStatus.PASS if significant else GateStatus.WARNING,
              message=f"{significant} sensors differ between failing and passing runs (q<0.05)"),
        Check(name="anomaly_evidence",
              status=GateStatus.PASS if lift and lift > 1 else GateStatus.WARNING,
              message=f"failing runs are flagged {lift}x as often as passing runs" if lift
              else "anomaly flags do not separate failing runs"),
    ]
    if risk is not None:
        chosen = risk["recommended_ranking"]
        recall = risk["test"][chosen]["recall_at_budget"]
        budget = risk["alarm_budget"]
        checks.append(Check(
            name="risk_ranking_adds_value",
            status=GateStatus.PASS if recall > budget else GateStatus.WARNING,
            message=f"{chosen} ranking finds {recall:.0%} of failing runs with a "
                    f"{budget:.0%} alarm budget (random: about {budget:.0%})"))
    return ValidationSummary.from_checks(checks)
