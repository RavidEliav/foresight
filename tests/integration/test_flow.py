import json
from pathlib import Path

import pytest

from foresight.data.secom import LABELS_FILE
from foresight.flow import run_pipeline
from foresight.validation.gates import GateResult, GateStatus

pytestmark = pytest.mark.usefixtures("secom_env")

INGEST_ARTIFACTS = {
    "clean_data.csv",
    "cleaning_report.json",
    "data_profile.json",
    "dataset_contract.json",
    "validation_summary.json",
}


def _set_gate(checks, name: str, status: GateStatus, message: str = "test") -> None:
    checks[name] = lambda _state: GateResult(gate=name, status=status, messages=[message])


def test_successful_run_validates_data_and_completes_all_stages():
    state = run_pipeline()
    assert state.status == "success"
    assert state.stages_completed == ["ingest", "analyze", "investigate", "report"]
    assert [g.status for g in state.gates] == [GateStatus.PASS] * 3
    assert state.validation["status"] == "PASS"

    run_dir = Path(state.run_dir)
    assert {p.name for p in run_dir.iterdir()} >= INGEST_ARTIFACTS
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert manifest["status"] == "success"
    assert set(manifest["data_sha256"]) == {"secom.data", "secom_labels.data"}


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
        ("evidence_present", ["ingest", "analyze", "investigate"]),
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
