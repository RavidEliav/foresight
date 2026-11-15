import json
from pathlib import Path

import pytest

from foresight.analytics.stages import run_analyze, run_investigate, run_model
from foresight.data.ingest import run_ingest
from foresight.settings import load_settings
from foresight.tools.run_tools import build_tools
from tests.conftest import write_synthetic_secom


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """One analytics run shared by all tool tests (the tools only read it)."""
    base = tmp_path_factory.mktemp("tools")
    settings = load_settings(Path(__file__).parents[1] / "fast_settings.yaml")
    settings.paths.data_raw_dir = base / "data"
    settings.paths.contract_path = base / "dataset_contract.json"
    write_synthetic_secom(settings.paths.data_raw_dir)
    run_dir = base / "run"
    run_dir.mkdir()
    run_ingest(settings, run_dir)
    run_analyze(settings, run_dir)
    run_model(settings, run_dir)
    run_investigate(settings, run_dir)
    return build_tools(run_dir), run_dir


@pytest.fixture
def tools(built):
    return built[0]


def call(tool, **kwargs):
    return json.loads(tool.run(**kwargs))


def test_all_tools_are_registered(tools):
    assert set(tools) == {"data_quality_summary", "eda_summary", "model_metrics",
                          "anomaly_summary", "run_details", "sensor_stats"}


@pytest.mark.parametrize("name", ["data_quality_summary", "eda_summary", "model_metrics",
                                  "anomaly_summary"])
def test_summary_tools_return_traceable_compact_json(tools, name):
    raw = tools[name].run()
    payload = json.loads(raw)
    assert payload["source_files"]
    assert "figures" not in payload
    assert len(raw) <= 6100


def test_model_metrics_tool_reports_selected_model_and_ci(tools):
    payload = call(tools["model_metrics"])
    assert payload["selected_model"] in payload["comparison"]
    assert "pr_auc" in payload["test_metrics_ci95"]


def test_run_details_includes_test_period_prediction(tools, built):
    import pandas as pd

    run_id = int(pd.read_csv(built[1] / "predictions.csv")["run_id"].iloc[0])
    payload = call(tools["run_details"], run_id=run_id)
    assert payload["run"]["run_id"] == run_id
    assert "fail_probability" in payload["run"]
    assert "predictions.csv" in payload["source_files"]


def test_run_details_unknown_run(tools):
    assert "not found" in call(tools["run_details"], run_id=999_999)["error"]


def test_sensor_stats_for_the_shifted_sensor(tools):
    payload = call(tools["sensor_stats"], feature="f_020")
    assert payload["pass_vs_fail_test"]["direction"] == "higher in fails"


def test_tools_explain_missing_artifacts(tmp_path):
    payload = json.loads(build_tools(tmp_path)["model_metrics"].run())
    assert "not available yet" in payload["error"]
