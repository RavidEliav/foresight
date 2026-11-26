"""Plain names for citations (Phase 8.10, foresight.sources)."""

from foresight.sources import file_title, label, readable

RUN = "20261118T201632841000Z"
NAMES = {RUN: "Analysis 12"}


def test_files_have_plain_names():
    assert file_title("model_metrics.json") == "Model metrics"
    assert file_title("insights.md") == "Insights"
    assert file_title("some_new_table.csv") == "Some new table"  # a file not listed


def test_a_tag_reads_as_file_and_section():
    assert label("source", "insights.md § Data quality") == "Insights › Data quality"
    assert label("source", "model_metrics.json") == "Model metrics"
    assert label("background", "process_drift_and_maintenance.md § Drift") == \
        "Background: Process drift and maintenance › Drift"


def test_an_all_runs_tag_names_the_analysis():
    assert label("source", f"{RUN}/insights.md § Data quality", NAMES) == \
        "Analysis 12 › Insights › Data quality"
    # a run with no number is the reference analysis
    assert label("source", "20261117T144953604456Z/model_card.md § Limits", NAMES) == \
        "Reference analysis › Model card › Limits"


def test_readable_replaces_tags_and_run_ids():
    text = (f"In run {RUN} the PR-AUC was 0.085 [source: {RUN}/model_card.md § Metrics]. "
            "Sensor 59 differs [source: eda_summary.json].")
    shown = readable(text, NAMES, chip=lambda name: f"<{name}>")
    assert shown == ("In Analysis 12 the PR-AUC was 0.085 <Analysis 12 › Model card › "
                     "Metrics>. Sensor 59 differs <Data insights>.")
    # without names the run ids stay (a single analysis's text has none); default chip
    assert readable("Lift 1.76 [source: anomaly_summary.json]") == "Lift 1.76 (Anomaly results)"
    # brackets inside a section can't break the chip's markdown
    assert label("source", "run_data.md § Run 10 [test]") == "Analysis data › Run 10 (test)"
