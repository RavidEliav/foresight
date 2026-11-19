"""Analytics stages called by the Flow. Each returns artifact paths and, where a gate follows,
a ValidationSummary that the gate turns into PASS / WARNING / ERROR."""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from concurrent.futures import Executor, Future
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from foresight.analytics.anomalies import detect
from foresight.analytics.eda import build_eda
from foresight.analytics.features import SPLIT, FeatureSpec, engineer
from foresight.analytics.modeling import train_and_evaluate
from foresight.analytics.risk import rank_risk
from foresight.analytics.similar import EMBEDDINGS_FILE, SIMILAR_CSV, SIMILAR_JSON, find_similar
from foresight.crews.checks import check_outputs
from foresight.crews.facts import all_facts, allowed_numbers, background_passages
from foresight.crews.runner import run_crew
from foresight.crews.summary import SUMMARY_FILE
from foresight.data.scenarios import CHECK_FILE as SCENARIO_CHECK_FILE
from foresight.data.scenarios import banner, ground_truth_check
from foresight.progress import CREW_STAGES, ProgressTracker
from foresight.rag.index import CHUNKS_FILE, VECTORS_FILE, build_run_index
from foresight.rag.run_data import RUN_DATA_FILE
from foresight.settings import Settings
from foresight.utils.logging import get_logger
from foresight.validation.contract import Check, ValidationSummary
from foresight.validation.gates import GateStatus

log = get_logger("stages")


class StageResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    artifacts: dict[str, str] = Field(default_factory=dict)
    checks: ValidationSummary | None = None
    crew_usage: dict[str, dict] = Field(default_factory=dict)
    # a crew still running in the background (its own StageResult when done)
    pending: Future | None = Field(default=None, exclude=True)



def ensure_similar_fact(run_dir: Path) -> None:
    """The overall similar-run comparison is a computed fact: if the crew left it out of the
    investigation's Facts, insert it as the first Facts bullet (ADR-005: tools compute)."""
    from foresight.crews.checks import section
    from foresight.crews.facts import similar_overall

    path = run_dir / "investigation.md"
    if not path.exists() or not (run_dir / SIMILAR_JSON).exists():
        return
    summary = json.loads((run_dir / SIMILAR_JSON).read_text(encoding="utf-8"))
    share = summary.get("neighbour_fail_share_for_failing_test_runs")
    text = path.read_text(encoding="utf-8")
    facts = section(text, "Facts")
    if share is None or (f"{share:.1%}" in facts and "similar_runs.json" in facts):
        return
    heading = re.search(r"^#{1,3}\s+Facts[^\n]*\n", text, re.MULTILINE | re.IGNORECASE)
    if heading:
        text = text[:heading.end()] + similar_overall(run_dir) + "\n" + text[heading.end():]
        path.write_text(text, encoding="utf-8")


REPORT_INPUTS = ("insights.md", "model_card.md", "investigation.md")
CREW_OUTPUTS = [*REPORT_INPUTS, SUMMARY_FILE, "engineering_report.md"]
REVISIONS_FILE = "crew_revisions.json"
_REVISIONS_LOCK = threading.Lock()  # crews may finish at the same time


def _problems(checks: ValidationSummary) -> list[str]:
    return [f"{c.name}: {c.message}" for c in checks.checks if c.status != GateStatus.PASS]


def _add_usage(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in {*a, *b}
            if isinstance(a.get(k, b.get(k)), int | float)
            and not isinstance(a.get(k, b.get(k)), bool)}


def _with_crew(result: StageResult, crew: str, settings: Settings, run_dir: Path,
               extra_inputs: dict[str, str] | None = None,
               postprocess: Callable[[Path], None] | None = None,
               tracker: ProgressTracker | None = None,
               allowed: set[str] | None = None,
               visible: frozenset[str] | None = None) -> StageResult:
    """Run a crew after the deterministic work of a stage and record its outputs and usage.
    If the deterministic checks on the crew's own output warn, the crew gets the findings and
    revises it (at most settings.llm.crew_revisions times); revisions go to crew_revisions.json.
    The crew is skipped when the stage's own checks already have an ERROR: the gate that follows
    will stop the run, so the LLM call would be wasted."""
    if result.checks is not None and result.checks.status == GateStatus.ERROR:
        log.info("crew %s skipped: the stage checks failed", crew)
        if tracker:
            tracker.crew(crew, "skipped")
        return result
    if tracker:
        tracker.crew(crew, "running")
    inputs = dict(extra_inputs or {})
    outcome = run_crew(crew, settings, run_dir, inputs, visible)
    if postprocess:
        postprocess(run_dir)
    usage = {"seconds": outcome.seconds, **outcome.usage}
    files = list(outcome.outputs)
    fixed: list[str] = []
    revisions = 0
    for _ in range(settings.llm.crew_revisions):
        problems = _problems(check_outputs(run_dir, files, allowed))
        if not problems:
            break
        notes = ("REVISION REQUEST: the previous version of this output failed these automatic "
                 "checks. Fix them and keep everything else as required above:\n- "
                 + "\n- ".join(problems))
        again = run_crew(crew, settings, run_dir, {**inputs, "revision_notes": notes}, visible)
        if postprocess:
            postprocess(run_dir)
        usage = _add_usage(usage, {"seconds": again.seconds, **again.usage})
        fixed += problems
        revisions += 1
    if fixed:
        path = run_dir / REVISIONS_FILE
        with _REVISIONS_LOCK:
            revised = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            revised[crew] = fixed
            path.write_text(json.dumps(revised, indent=2), encoding="utf-8")
    result.artifacts.update({Path(p).stem: p for p in outcome.outputs.values()})
    result.crew_usage[crew] = {**usage, "mock": outcome.mock, "revisions": revisions}
    if tracker:
        tracker.crew(crew, "done")
    return result


def _crew_step(result: StageResult, crew: str, settings: Settings, run_dir: Path,
               tracker: ProgressTracker | None = None,
               executor: Executor | None = None) -> StageResult:
    """Run the stage's crew now, or in the background when an executor is given (the Flow then
    goes on with the next stage and waits for the crew before the report). A background crew
    takes its fact sheets, the numbers its checks accept and the files its tools may read
    now, so it sees what a sequential run would see. When it ends, its outputs, usage and
    "done" are recorded together, so Continue never reuses a half-recorded stage."""
    skipped = result.checks is not None and result.checks.status == GateStatus.ERROR
    if executor is None or skipped:
        return _with_crew(result, crew, settings, run_dir, tracker=tracker)
    if tracker:
        tracker.crew(crew, "running")
    facts, allowed = all_facts(run_dir), allowed_numbers(run_dir)
    visible = frozenset(p.name for p in run_dir.iterdir() if p.is_file())

    def job() -> StageResult:
        done = _with_crew(StageResult(), crew, settings, run_dir, facts, None, None, allowed,
                          visible)
        if tracker:
            tracker.crew_finished(CREW_STAGES[crew], done.artifacts, done.crew_usage)
        return done

    result.pending = executor.submit(job)
    return result


def load_clean(run_dir: Path) -> pd.DataFrame:
    return pd.read_csv(run_dir / "clean_data.csv", parse_dates=["timestamp"])


def load_features(run_dir: Path) -> tuple[pd.DataFrame, FeatureSpec]:
    frame = pd.read_csv(run_dir / "features.csv", parse_dates=["timestamp"])
    spec = FeatureSpec.model_validate_json((run_dir / "feature_spec.json").read_text())
    return frame, spec


def run_analyze(settings: Settings, run_dir: Path, tracker: ProgressTracker | None = None,
                executor: Executor | None = None) -> StageResult:
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
    return _crew_step(result, "analyst", settings, run_dir, tracker, executor)


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


def run_model(settings: Settings, run_dir: Path, tracker: ProgressTracker | None = None,
              executor: Executor | None = None) -> StageResult:
    frame, spec = load_features(run_dir)
    train_and_evaluate(frame, spec, settings.analytics, settings.seed, run_dir)
    result = StageResult(artifacts={name: str(run_dir / file) for name, file in (
        ("model", "model.joblib"), ("model_metrics", "model_metrics.json"),
        ("evaluation_report", "evaluation_report.md"), ("predictions", "predictions.csv"),
        ("oof_predictions", "oof_predictions.csv"))})
    return _crew_step(result, "scientist", settings, run_dir, tracker, executor)


def run_investigate(settings: Settings, run_dir: Path,
                    tracker: ProgressTracker | None = None) -> StageResult:
    """Anomaly detection and risk ranking; checks the evidence for the report (evidence gate)."""
    frame, spec = load_features(run_dir)
    anomalies = detect(frame, spec, settings.analytics, settings.seed, run_dir)
    risk = rank_risk(run_dir, settings.analytics, settings.seed)
    find_similar(frame, spec, settings.analytics, settings.seed, run_dir)
    metrics = json.loads((run_dir / "model_metrics.json").read_text(encoding="utf-8"))
    eda = json.loads((run_dir / "eda_summary.json").read_text(encoding="utf-8"))
    result = StageResult(
        artifacts={"anomalies": str(run_dir / "anomalies.csv"),
                   "anomaly_summary": str(run_dir / "anomaly_summary.json"),
                   "risk_scores": str(run_dir / "risk_scores.csv"),
                   "risk_summary": str(run_dir / "risk_summary.json"),
                   "run_embeddings": str(run_dir / EMBEDDINGS_FILE),
                   "similar_runs": str(run_dir / SIMILAR_CSV),
                   "similar_runs_summary": str(run_dir / SIMILAR_JSON)},
        checks=evidence_checks(metrics, anomalies, eda, risk),
    )
    return _with_crew(result, "investigation", settings, run_dir,
                      {"background_passages": background_passages(settings)},
                      postprocess=ensure_similar_fact, tracker=tracker)


def run_report(settings: Settings, run_dir: Path,
               tracker: ProgressTracker | None = None) -> StageResult:
    """Engineering Report crew, then deterministic checks on all crew outputs (revisions made
    by any crew are listed as their own checks)."""
    inputs = {Path(name).stem: (run_dir / name).read_text(encoding="utf-8")
              for name in REPORT_INPUTS if (run_dir / name).exists()}
    result = _with_crew(StageResult(), "report", settings, run_dir, inputs, tracker=tracker)
    checks = check_outputs(run_dir, CREW_OUTPUTS)
    revisions_path = run_dir / REVISIONS_FILE
    if revisions_path.exists():
        revised = json.loads(revisions_path.read_text(encoding="utf-8"))
        checks = ValidationSummary.from_checks([*checks.checks, *(
            Check(name=f"{crew} crew: revision", status=GateStatus.PASS,
                  message="revised after: " + "; ".join(problems))
            for crew, problems in revised.items())])
        result.artifacts["crew_revisions"] = str(revisions_path)
    scenario = ground_truth_check(run_dir)  # synthetic runs: did the analysis find the change?
    if scenario is not None:
        evaluation, check = scenario
        checks = ValidationSummary.from_checks([*checks.checks, check])
        report_path = run_dir / "engineering_report.md"
        if report_path.exists():  # the SYNTHETIC note opens the report (after its checks)
            report, note = report_path.read_text(encoding="utf-8"), banner(evaluation)
            if report.startswith("# "):
                title, _, body = report.partition("\n")
                report = f"{title}\n\n{note}{body.lstrip()}"
            else:
                report = note + report
            report_path.write_text(report, encoding="utf-8")
        result.artifacts["scenario_check"] = str(run_dir / SCENARIO_CHECK_FILE)
    (run_dir / "report_checks.json").write_text(checks.model_dump_json(indent=2),
                                                encoding="utf-8")
    result.artifacts["report_checks"] = str(run_dir / "report_checks.json")
    build_run_index(run_dir, settings)  # "Ask Foresight" answers from this index (§18.3)
    result.artifacts.update({"rag_index": str(run_dir / VECTORS_FILE),
                             "rag_chunks": str(run_dir / CHUNKS_FILE)})
    if (run_dir / RUN_DATA_FILE).exists():
        result.artifacts["run_data"] = str(run_dir / RUN_DATA_FILE)
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
