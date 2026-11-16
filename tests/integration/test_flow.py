import json
from pathlib import Path

import pytest

from foresight.data.secom import LABELS_FILE
from foresight.flow import run_pipeline
from foresight.validation.gates import GateResult, GateStatus

pytestmark = pytest.mark.usefixtures("secom_env")

RUN_ARTIFACTS = {
    "clean_data.csv", "cleaning_report.json", "data_profile.json", "dataset_contract.json",
    "validation_summary.json", "eda_report.html", "eda_summary.json", "features.csv",
    "feature_spec.json", "model.joblib", "model_metrics.json", "evaluation_report.md",
    "predictions.csv", "oof_predictions.csv", "anomalies.csv", "anomaly_summary.json",
    "risk_scores.csv", "risk_summary.json", "run_manifest.json", "insights.md",
    "model_card.md", "investigation.md", "engineering_report.md", "report_checks.json",
}
ALL_STAGES = ["ingest", "analyze", "model", "investigate", "report"]


def _set_gate(checks, name: str, status: GateStatus, message: str = "test") -> None:
    checks[name] = lambda _state: GateResult(gate=name, status=status, messages=[message])


def test_successful_run_produces_all_artifacts_through_all_stages():
    state = run_pipeline()
    assert state.status == "success"
    assert state.stages_completed == ALL_STAGES
    assert [g.status for g in state.gates[:2]] == [GateStatus.PASS] * 2
    assert state.gates[2].status in (GateStatus.PASS, GateStatus.WARNING)
    assert state.validation["status"] == "PASS"
    assert state.feature_checks["status"] == "PASS"

    run_dir = Path(state.run_dir)
    assert {p.name for p in run_dir.iterdir()} >= RUN_ARTIFACTS
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert manifest["status"] == "success"
    assert set(manifest["data_sha256"]) == {"secom.data", "secom_labels.data"}
    assert "model.joblib" in manifest["artifacts"]
    assert set(manifest["crew_usage"]) == {"analyst", "scientist", "investigation", "report"}
    assert all(usage["mock"] for usage in manifest["crew_usage"].values())
    assert state.report_checks["status"] == "PASS"


def test_invalid_raw_labels_stop_the_run_at_the_contract_gate(secom_env):
    labels = secom_env.paths.data_raw_dir / LABELS_FILE
    labels.write_text(labels.read_text().replace('-1 "', '7 "', 3))

    state = run_pipeline()
    assert state.status == "failed"
    assert state.stages_completed == ["ingest"]
    assert "raw_label_values" in state.failure_reason
    run_dir = Path(state.run_dir)
    assert (run_dir / "failure_report.md").exists()
    assert not (run_dir / "clean_data.csv").exists()
    summary = json.loads((run_dir / "validation_summary.json").read_text())
    assert summary["status"] == "ERROR"


def test_data_missing_contract_feature_stops_the_run(secom_env):
    contract_path = secom_env.paths.contract_path
    contract = json.loads(contract_path.read_text())
    contract["features"]["required"].append("f_777_not_in_data")
    contract["features"]["ranges"]["f_777_not_in_data"] = [0, 1]
    contract_path.write_text(json.dumps(contract))

    state = run_pipeline()
    assert state.status == "failed"
    assert "required_columns" in state.failure_reason
    assert "f_777_not_in_data" in state.failure_reason


def test_missing_data_offline_fails_gracefully(secom_env):
    for path in secom_env.paths.data_raw_dir.iterdir():
        path.unlink()
    state = run_pipeline()
    assert state.status == "failed"
    assert "load_raw" in state.failure_reason


def test_missing_contract_is_bootstrapped_with_a_warning(secom_env):
    secom_env.paths.contract_path.unlink()
    state = run_pipeline()
    assert state.status == "success"
    assert state.gates[0].status == GateStatus.WARNING
    assert any("contract_bootstrap" in m for m in state.gates[0].messages)


@pytest.mark.parametrize(
    ("gate", "completed"),
    [
        ("features_present", ["ingest", "analyze"]),
        ("evidence_present", ["ingest", "analyze", "model", "investigate"]),
    ],
)
def test_later_error_gates_stop_flow_gracefully(gate_checks, gate, completed):
    _set_gate(gate_checks, gate, GateStatus.ERROR, "broken input")
    state = run_pipeline()
    assert state.status == "failed"
    assert state.stages_completed == completed
    assert state.failure_reason == f"{gate}: broken input"
    assert "broken input" in (Path(state.run_dir) / "failure_report.md").read_text()


def test_warning_gate_lets_flow_continue(gate_checks):
    _set_gate(gate_checks, "evidence_present", GateStatus.WARNING, "thin evidence")
    state = run_pipeline()
    assert state.status == "success"
    assert state.gates[-1].status == GateStatus.WARNING


def test_too_few_test_fails_stop_the_run_at_the_features_gate(secom_env):
    secom_env.analytics.min_fails_test = 1000
    state = run_pipeline(secom_env)
    assert state.status == "failed"
    assert state.stages_completed == ["ingest", "analyze"]
    assert "test_fails" in state.failure_reason


def test_exception_inside_a_stage_fails_gracefully(monkeypatch):
    import foresight.flow as flow_module

    def broken(*_args):
        raise RuntimeError("disk full")

    monkeypatch.setattr(flow_module, "run_model", broken)
    state = run_pipeline()
    assert state.status == "failed"
    assert state.stages_completed == ["ingest", "analyze"]
    assert state.failure_reason == "model stage error: disk full"
    assert "disk full" in (Path(state.run_dir) / "failure_report.md").read_text()


def test_report_crew_failure_fails_the_run_gracefully(monkeypatch):
    import foresight.flow as flow_module

    def broken(*_args):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(flow_module, "run_report", broken)
    state = run_pipeline()
    assert state.status == "failed"
    assert state.stages_completed == ["ingest", "analyze", "model", "investigate"]
    assert state.failure_reason == "report stage error: LLM provider unavailable"
