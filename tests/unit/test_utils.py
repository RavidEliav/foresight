import json

import numpy as np

from foresight.settings import load_settings
from foresight.utils.manifest import build_manifest, write_manifest
from foresight.utils.seeds import set_seeds
from foresight.validation.gates import GateStatus, run_gate


def test_seeds_make_numpy_deterministic():
    set_seeds(7)
    first = np.random.rand(3)
    set_seeds(7)
    assert np.array_equal(first, np.random.rand(3))


def test_manifest_records_reproducibility_info(monkeypatch, tmp_path):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc123")
    manifest = build_manifest("run-1", load_settings(), status="success")
    assert manifest["git_commit"] == "abc123"
    assert manifest["seed"] == 42
    assert manifest["llm"]["mock"] is True
    assert "crewai" in manifest["packages"]

    path = write_manifest(manifest, tmp_path / "nested" / "run_manifest.json")
    assert json.loads(path.read_text())["status"] == "success"


def test_crashing_gate_check_becomes_error(gate_checks):
    def broken(_state):
        raise ValueError("boom")

    gate_checks["data_contract"] = broken
    result = run_gate("data_contract", state=None)
    assert result.status == GateStatus.ERROR
    assert result.blocks
    assert "boom" in result.messages[0]
