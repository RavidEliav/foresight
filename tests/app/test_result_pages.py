from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from foresight.analytics.stages import run_analyze, run_investigate, run_model, run_report
from foresight.data.ingest import run_ingest
from foresight.settings import load_settings
from tests.conftest import write_synthetic_secom


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    base = tmp_path_factory.mktemp("pages")
    settings = load_settings(Path(__file__).parents[1] / "fast_settings.yaml")
    settings.paths.data_raw_dir = base / "data"
    settings.paths.contract_path = base / "dataset_contract.json"
    write_synthetic_secom(settings.paths.data_raw_dir)
    run = base / "run"
    run.mkdir()
    for stage in (run_ingest, run_analyze, run_model, run_investigate, run_report):
        stage(settings, run)
    return run


def _render(module: str, run_dir: Path | None) -> AppTest:
    def page(module, run_dir):
        import importlib
        from pathlib import Path

        importlib.import_module(module).render(Path(run_dir) if run_dir else None)

    return AppTest.from_function(page, args=(module, str(run_dir) if run_dir else None),
                                 default_timeout=60).run()


@pytest.mark.parametrize("module", ["app.eda_page", "app.model_page", "app.report_page"])
def test_pages_explain_when_there_is_no_run(module):
    at = _render(module, None)
    assert not at.exception
    assert "No " in at.info[0].value


def test_eda_page_shows_overview_and_top_sensor(run_dir):
    at = _render("app.eda_page", run_dir)
    assert not at.exception
    assert [m.label for m in at.metric][:3] == ["Runs", "Sensors", "Fail rate"]
    assert at.dataframe[0].value.iloc[0]["feature"] == "f_020"
    assert [h.value for h in at.subheader] == [
        "Fail rate over time", "Sensors that differ between failing and passing runs"]
    assert any("## Summary" in md.value for md in at.markdown)


def test_model_page_shows_metrics_with_confidence_intervals(run_dir):
    at = _render("app.model_page", run_dir)
    assert not at.exception
    assert [m.label for m in at.metric] == ["PR-AUC", "Fail recall", "Precision",
                                            "Balanced accuracy"]
    assert "95% bootstrap CI" in at.metric[0].help
    comparison = at.dataframe[0].value
    assert set(comparison["model"]) == {"logreg_l1", "random_forest", "rf_regularized",
                                        "rf_select_k", "baseline_always_pass"}


def test_report_page_shows_anomalies(run_dir):
    at = _render("app.report_page", run_dir)
    assert not at.exception
    assert [m.label for m in at.metric] == ["Runs flagged", "Flag rate: failing runs",
                                            "Flag rate: passing runs",
                                            "Sensors out of limits per run"]
    assert [h.value for h in at.subheader] == ["Engineering report", "Investigation",
                                               "Risk ranking", "Anomalies"]
    assert "Report safety checks: **PASS**" in at.success[0].value
    assert any("## What was detected" in md.value for md in at.markdown)
    assert not any(md.value.startswith("# Engineering report") for md in at.markdown)
    assert any("Recommended ranking" in md.value and " of " in md.value and "alarms" in md.value
               for md in at.markdown)
    assert any("Most anomalous runs" in md.value for md in at.markdown)


def test_investigation_is_split_into_labelled_blocks(run_dir):
    at = _render("app.report_page", run_dir)
    labels = [md.value for md in at.markdown if "-badge[" in md.value]
    assert [label.split("[")[1].split("]")[0] for label in labels] == [
        "Facts", "Assumptions", "Hypotheses", "Suggested verification"]
    assert {b.label for b in at.get("download_button")} >= {"Download engineering_report.md",
                                                            "Download investigation.md"}


def test_model_page_shows_the_model_card(run_dir):
    at = _render("app.model_page", run_dir)
    assert any("## Model purpose" in md.value for md in at.markdown)


def test_figures_saved_with_windows_paths_still_load(tmp_path):
    from app.runs import figure_path

    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "chart.png").write_bytes(b"png")
    expected = tmp_path / "figures" / "chart.png"
    assert figure_path(tmp_path, "figures\\chart.png") == expected
    assert figure_path(tmp_path, "figures/chart.png") == expected
    assert figure_path(tmp_path, "figures/missing.png") is None
    assert figure_path(tmp_path, None) is None


def test_viewable_runs_are_successful_runs_then_the_reference(tmp_path, run_dir):
    import json

    from app.runs import describe_run, viewable_runs

    runs = tmp_path / "runs"
    for name, status in (("20261116T100000000000Z", "success"),
                         ("20261116T110000000000Z", "failed"),
                         ("20261116T120000000000Z", "success")):
        (runs / name).mkdir(parents=True)
        (runs / name / "run_manifest.json").write_text(json.dumps({"status": status}))
    reference = tmp_path / "reference"
    reference.mkdir()
    (reference / "run_manifest.json").write_text(json.dumps({"status": "success"}))

    found = viewable_runs(runs, reference)
    assert [p.name for p in found] == ["20261116T120000000000Z", "20261116T100000000000Z",
                                      "reference"]
    assert describe_run(found[0]) == "2026-11-16 12:00 UTC · SECOM (UCI)"
    assert describe_run(found[-1]) == "Reference run (committed)"
    assert viewable_runs(tmp_path / "none", None) == []
