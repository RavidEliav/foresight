import json
from pathlib import Path

import pytest

from foresight.flow import run_pipeline
from foresight.validation.gates import GateResult, GateStatus


def _set_gate(checks, name: str, status: GateStatus, message: str = "test") -> None:
    checks[name] = lambda _state: GateResult(gate=name, status=status, messages=[message])


def test_successful_run_completes_all_stages():
    state = run_pipeline()
    assert state.status == "success"
    assert state.stages_completed == ["ingest", "analyze", "investigate", "report"]
    assert [g.status for g in state.gates] == [GateStatus.PASS] * 3
    manifest = json.loads((Path(state.run_dir) / "run_manifest.json").read_text())
    assert manifest["status"] == "success"


@pytest.mark.parametrize(
    ("gate", "completed"),
    [
        ("data_contract", ["ingest"]),
        ("features_present", ["ingest", "analyze"]),
        ("evidence_present", ["ingest", "analyze", "investigate"]),
    ],
)
def test_error_gate_stops_flow_gracefully(gate_checks, gate, completed):
    _set_gate(gate_checks, gate, GateStatus.ERROR, "broken input")
    state = run_pipeline()
    assert state.status == "failed"
    assert state.stages_completed == completed
    assert state.failure_reason == f"{gate}: broken input"
    report = (Path(state.run_dir) / "failure_report.md").read_text()
    assert "broken input" in report


def test_warning_gate_lets_flow_continue(gate_checks):
    _set_gate(gate_checks, "evidence_present", GateStatus.WARNING, "thin evidence")
    state = run_pipeline()
    assert state.status == "success"
    assert state.gates[-1].status == GateStatus.WARNING
