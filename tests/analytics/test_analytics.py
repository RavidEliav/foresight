import json

import joblib
import numpy as np
import pandas as pd
import pytest

from foresight.analytics.anomalies import detect, robust_z
from foresight.analytics.eda import _bh, build_eda, discriminating_features
from foresight.analytics.features import FeatureSpec, engineer, time_split, xy
from foresight.analytics.modeling import (
    BASELINE,
    bootstrap_ci,
    build_models,
    choose_threshold,
    classification_metrics,
    time_cv,
    train_and_evaluate,
)
from foresight.analytics.stages import (
    evidence_checks,
    feature_checks,
    load_clean,
    run_analyze,
    run_investigate,
    run_model,
)
from foresight.settings import AnalyticsSettings
from foresight.validation.gates import GateStatus


@pytest.fixture
def cleaned(analytics_run):
    return load_clean(analytics_run[1])


def test_time_split_holds_out_the_latest_runs():
    frame = pd.DataFrame({"x": range(100)})
    split = time_split(frame, 0.25)
    assert (split == "train").sum() == 75
    assert (split.iloc[:75] == "train").all() and (split.iloc[75:] == "test").all()


def test_engineer_drops_duplicates_fitted_on_train_and_adds_missing_count(cleaned):
    cleaned = cleaned.assign(f_500=cleaned["f_020"] * 2 + 1)  # perfect copy of f_020
    frame, spec = engineer(cleaned, 0.25, 0.98)
    assert "f_500" in spec.dropped_correlated and "f_020" in spec.features
    assert spec.features[-1] == "missing_count"
    assert frame["missing_count"].equals(
        cleaned.filter(like="f_").isna().sum(axis=1).rename("missing_count"))
    assert spec.split_counts["train"]["runs"] + spec.split_counts["test"]["runs"] == len(cleaned)
    X, y = xy(frame, spec, "test")
    assert list(X.columns) == spec.features and len(y) == spec.split_counts["test"]["runs"]


def test_shifted_sensor_is_the_top_discriminating_feature(cleaned):
    table = discriminating_features(cleaned)
    top = table.iloc[0]
    assert top["feature"] == "f_020"
    assert top["direction"] == "higher in fails"
    assert top["q_value"] < 0.05


def test_benjamini_hochberg_is_monotonic_and_bounded():
    p = np.array([0.01, 0.04, 0.03, 0.2, 0.9])
    q = _bh(p)
    order = np.argsort(p)
    assert np.all(np.diff(q[order]) >= 0)
    assert np.all(q >= p) and np.all(q <= 1)


def test_build_eda_writes_report_summary_and_figures(cleaned, tmp_path):
    summary = build_eda(cleaned, tmp_path, top_n=5)
    assert (tmp_path / "eda_report.html").read_text().count("data:image/png;base64") == 4
    assert summary["top_discriminating_features"][0]["feature"] == "f_020"
    assert all((tmp_path / p).exists() for p in summary["figures"].values())
    assert json.loads((tmp_path / "eda_summary.json").read_text())["overview"]["rows"] == 150


def test_threshold_and_metrics():
    y = np.array([0, 0, 0, 0, 1, 1])
    proba = np.array([0.1, 0.2, 0.3, 0.6, 0.7, 0.9])
    threshold = choose_threshold(y, proba)
    assert threshold == pytest.approx(0.7)
    metrics = classification_metrics(y, proba, threshold)
    assert metrics["recall_fail"] == 1.0 and metrics["precision_fail"] == 1.0
    assert choose_threshold(y, np.full(6, np.nan)) == 0.5


def test_bootstrap_ci_is_reproducible_and_contains_the_point_estimate():
    rng = np.random.default_rng(0)
    y = np.r_[np.zeros(80), np.ones(20)].astype(int)
    proba = np.clip(y * 0.4 + rng.random(100) * 0.6, 0, 1)
    first = bootstrap_ci(y, proba, 0.5, 200, seed=1)
    assert first == bootstrap_ci(y, proba, 0.5, 200, seed=1)
    point = classification_metrics(y, proba, 0.5)["pr_auc"]
    assert first["pr_auc"][0] <= point <= first["pr_auc"][1]


def test_time_cv_skips_folds_without_failing_runs():
    X = pd.DataFrame({"a": np.arange(60.0)})
    y = pd.Series([0] * 40 + [1, 0] * 10)
    model = build_models(AnalyticsSettings(rf_trees=5, select_k=1), 0)["logreg_l1"][1]
    scores, oof = time_cv(model, X, y, folds=3)
    assert len(scores) == 1
    assert np.isnan(oof[:40]).all()


def test_train_and_evaluate_selects_a_real_model_and_writes_artifacts(analytics_run):
    settings, run_dir = analytics_run
    run_analyze(settings, run_dir)
    frame = pd.read_csv(run_dir / "features.csv", parse_dates=["timestamp"])
    spec = FeatureSpec.model_validate_json((run_dir / "feature_spec.json").read_text())
    metrics = train_and_evaluate(frame, spec, settings.analytics, settings.seed, run_dir)

    assert metrics["selected_model"] != BASELINE
    assert set(metrics["comparison"]) == {"logreg_l1", "random_forest", "rf_select_k", BASELINE}
    assert 0 <= metrics["threshold"] <= 1
    assert metrics["test_metrics"]["pr_auc"] > metrics["baseline_pr_auc"]
    assert sum(metrics["confusion_matrix"].values()) == spec.split_counts["test"]["runs"]
    report = (run_dir / "evaluation_report.md").read_text()
    assert metrics["selected_model"] in report and "95% bootstrap CI" in report

    bundle = joblib.load(run_dir / "model.joblib")
    X_test, _ = xy(frame, spec, "test")
    assert bundle["model"].predict_proba(X_test).shape == (len(X_test), 2)
    predictions = pd.read_csv(run_dir / "predictions.csv")
    assert len(predictions) == len(X_test)


def test_training_is_deterministic(analytics_run):
    settings, run_dir = analytics_run
    run_analyze(settings, run_dir)
    first = run_model(settings, run_dir)
    metrics_a = json.loads((run_dir / "model_metrics.json").read_text())
    run_model(settings, run_dir)
    metrics_b = json.loads((run_dir / "model_metrics.json").read_text())
    assert first.artifacts and metrics_a == metrics_b


def test_robust_z_uses_training_statistics():
    train = pd.DataFrame({"a": [1.0, 2, 3, 4, 5], "flat": [1.0] * 5})
    z = robust_z(pd.DataFrame({"a": [3.0, 103], "flat": [1.0, 2]}), train)
    assert z.loc[0, "a"] == 0 and z.loc[1, "a"] > 30
    assert z["flat"].isna().all()


def test_detect_flags_extreme_runs(analytics_run):
    settings, run_dir = analytics_run
    run_analyze(settings, run_dir)
    frame = pd.read_csv(run_dir / "features.csv", parse_dates=["timestamp"])
    spec = FeatureSpec.model_validate_json((run_dir / "feature_spec.json").read_text())
    sensors = [f for f in spec.features if f not in spec.engineered]
    frame.loc[frame.index[-1], sensors] = 10_000.0  # extreme on every sensor
    frame.loc[frame.index[-2], sensors[:30]] = 10_000.0  # extreme on 30 sensors only
    summary = detect(frame, spec, settings.analytics, settings.seed, run_dir)

    result = pd.read_csv(run_dir / "anomalies.csv")
    everywhere, few = result.iloc[-1], result.iloc[-2]
    assert bool(everywhere["is_anomaly"])
    assert summary["most_anomalous_runs"][0]["run_id"] == int(everywhere["run_id"])
    # SPC catches localized problems that IsolationForest dilutes over ~575 sensors
    assert few["n_out_of_limit"] >= 30
    assert few["top_signals"].count(":+") == 3


def test_feature_checks_error_when_too_few_test_fails(analytics_run):
    settings, run_dir = analytics_run
    frame, spec = engineer(load_clean(run_dir), 0.25, 0.98)
    settings.analytics.min_fails_test = 1000
    summary = feature_checks(frame, spec, settings)
    assert summary.status == GateStatus.ERROR
    assert {c.name: c.status for c in summary.checks}["test_fails"] == GateStatus.ERROR


def test_evidence_checks_warn_when_model_is_no_better_than_random():
    metrics = {"test_metrics": {"pr_auc": 0.05}, "baseline_pr_auc": 0.06,
               "selected_model": "logreg_l1"}
    summary = evidence_checks(metrics, {"flag_lift": 0.9},
                              {"significant_features_q_below_0.05": 0})
    assert summary.status == GateStatus.WARNING
    assert summary.counts["WARNING"] == 3


def test_investigate_stage_returns_evidence_checks(analytics_run):
    settings, run_dir = analytics_run
    run_analyze(settings, run_dir)
    run_model(settings, run_dir)
    result = run_investigate(settings, run_dir)
    assert result.checks.status in (GateStatus.PASS, GateStatus.WARNING)
    assert (run_dir / "anomalies.csv").exists()
