import re
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


def _render(module: str, run_dir: Path | None, role: str = "developer") -> AppTest:
    """A result page as a signed-in developer (Extended data shown) or user (Phase 8.6)."""
    def page(module, run_dir, role):
        import importlib
        from pathlib import Path

        import streamlit as st

        from app.auth import Viewer

        st.session_state["viewer"] = Viewer(email="ada@example.com", name="Ada Lovelace",
                                            role=role)
        importlib.import_module(module).render(Path(run_dir) if run_dir else None)

    return AppTest.from_function(page, args=(module, str(run_dir) if run_dir else None, role),
                                 default_timeout=60).run()


def _extended(at: AppTest) -> list:
    """The Extended data row (Phase 8.7 feedback): tabs that are closed until one is pressed."""
    return [s for s in at.segmented_control if (s.key or "").startswith("extended-")]


def _open(at: AppTest, tab: str) -> AppTest:
    """Opens one Extended data tab."""
    _extended(at)[0].set_value(tab).run()
    assert not at.exception
    return at


@pytest.mark.parametrize("module", ["app.data_quality", "app.eda_page", "app.model_page",
                                    "app.report_page"])
def test_users_see_the_results_without_the_extended_data(run_dir, module):
    """Extended data is part of the developer view; users keep the headline numbers, the
    charts and (on the report page) the engineering report download."""
    user, developer = _render(module, run_dir, "user"), _render(module, run_dir)
    assert not user.exception and not developer.exception
    # users get the main tabs too; the Extended data row is the developer's, all closed
    assert [t.label for t in user.tabs] == [t.label for t in developer.tabs]
    assert not _extended(user) and _extended(developer)
    assert _extended(developer)[0].value is None
    assert user.get("metric") and len(user.get("metric")) == len(developer.get("metric"))
    if module == "app.report_page":
        assert [b.proto.label for b in user.get("download_button")] == [
            "Download the engineering report"]
        assert "Safety checks tab" not in " ".join(m.value for m in user.markdown)


@pytest.mark.parametrize("module", ["app.eda_page", "app.model_page", "app.report_page",
                                    "app.replay_page"])
def test_pages_explain_when_there_is_no_run(module):
    at = _render(module, None)
    assert not at.exception
    assert "No " in at.info[0].value


def test_eda_page_shows_overview_and_top_sensor(run_dir):
    at = _render("app.eda_page", run_dir)
    assert not at.exception
    assert [m.label for m in at.metric][:3] == ["Runs", "Sensors", "Fail rate"]
    assert [c.key for c in at.get("plotly_chart")] == ["weekly-fail-rate", "sensor-differences"]
    assert [t.label for t in at.tabs] == ["Fail rate over time", "Sensors that differ"]
    assert _extended(at)[0].options == ["Sensor statistics", "Missing data and redundancy",
                                        "Full insights"]
    assert not at.dataframe  # Extended data stays closed until a tab is pressed
    assert _open(at, "Sensor statistics").dataframe[0].value.iloc[0]["feature"] == "f_020"
    charts = [c.key for c in _open(at, "Missing data and redundancy").get("plotly_chart")]
    assert charts == ["weekly-fail-rate", "sensor-differences", "missing-by-sensor",
                      "correlation"]

    assert any("## Summary" in md.value for md in _open(at, "Full insights").markdown)


def test_a_phone_gets_one_card_with_tabs_and_a_closed_extended_data(run_dir, monkeypatch):
    """A phone's browser (ui.phone) gets the selected model as the first tab of one card, so
    the page fits its screen, and Extended data as one closed dropdown."""
    monkeypatch.setattr("app.ui.phone", lambda: True)
    at = _render("app.model_page", run_dir)
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Selected model", "Risk scores", "Important sensors",
                                          "Alarms vs outcomes", "Precision-recall"]
    assert at.selectbox(key="extended-model").value is None
    assert not at.table  # closed until a tab is chosen


def test_model_page_shows_metrics_with_confidence_intervals(run_dir):
    at = _render("app.model_page", run_dir)
    assert not at.exception
    assert [m.label for m in at.metric] == ["PR-AUC", "Fail recall", "Precision",
                                            "Balanced accuracy"]
    assert "95% bootstrap CI" in at.metric[0].help
    assert [t.label for t in at.tabs] == ["Risk scores", "Important sensors",
                                          "Alarms vs outcomes", "Precision-recall"]
    comparison = _open(at, "Model comparison").table[0].value  # long text: a wrapped table
    assert set(comparison["model"]) == {"logreg_l1", "random_forest", "rf_regularized",
                                        "rf_select_k", "baseline_always_pass"}


def test_report_page_leads_with_headline_numbers_and_puts_details_in_tabs(run_dir):
    at = _render("app.report_page", run_dir)
    assert not at.exception
    assert [m.label for m in at.metric] == ["Failing runs caught", "Alarm precision",
                                            "Anomaly flag lift", "Sensors out of limits",
                                            "Similar runs that failed"]
    assert " of " in at.metric[0].value and at.metric[0].delta.startswith("with ")
    assert [t.label for t in at.tabs] == ["Key findings", "Hypotheses",
                                          "Anomalies and run map", "Simulated wafer"]
    assert _extended(at)[0].options == ["Engineering report", "Full investigation",
                                        "Risk ranking", "Similar past runs", "Anomalies",
                                        "Safety checks"]
    assert len(at.get("plotly_chart")) == 3  # anomaly timeline, run map, simulated wafer
    shown = {tab: [md.value for md in _open(at, tab).markdown]
             for tab in _extended(at)[0].options}
    assert any("## What was detected" in md for md in shown["Engineering report"])
    assert not any(md.startswith("# Engineering report") for md in shown["Engineering report"])
    assert any("Recommended ranking" in md and " of " in md and "alarms" in md
               for md in shown["Risk ranking"])
    assert any("Most anomalous runs" in md for md in shown["Anomalies"])
    assert "Report safety checks: **PASS**" in at.success[0].value  # the last tab opened


def test_summary_cards_follow_the_investigation(run_dir):
    import json

    summary = json.loads((run_dir / "investigation_summary.json").read_text(encoding="utf-8"))
    at = _render("app.report_page", run_dir)
    cards = [md.value for md in at.markdown if re.match(r"\*\*H\d", md.value)]
    assert len(cards) == len(summary["hypotheses"])
    first = summary["hypotheses"][0]
    assert f"{first['confidence']} confidence" in cards[0]
    assert any(summary["headline"][:40] in h.value for h in at.get("html"))


def test_summary_with_repeated_numbers_or_bad_format_does_not_break_the_page(run_dir, tmp_path):
    import json
    import shutil

    run = tmp_path / "run"
    shutil.copytree(run_dir, run)
    path = run / "investigation_summary.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for card in data["hypotheses"]:
        card["number"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
    at = _render("app.report_page", run)
    assert not at.exception
    assert len([md for md in at.markdown if re.match(r"\*\*H1\*\*", md.value)]) == len(
        data["hypotheses"])

    path.write_text('{"headline": "too short"}', encoding="utf-8")
    at = _render("app.report_page", run)
    assert not at.exception
    assert any("did not pass its format check" in w.value for w in at.warning)


def test_older_runs_explain_what_they_lack(run_dir, tmp_path):
    import shutil

    old = tmp_path / "old"
    shutil.copytree(run_dir, old)
    for name in ("investigation_summary.json", "similar_runs.json"):
        (old / name).unlink()
    at = _render("app.report_page", old)
    assert not at.exception
    notes = [i.value for i in at.info]
    assert any("before Foresight wrote a short summary" in n for n in notes)
    assert any("Similar-run search was added after this run" in n for n in notes)


def test_investigation_is_split_into_labelled_blocks(run_dir):
    at = _open(_render("app.report_page", run_dir), "Full investigation")
    sections = {"Facts", "Assumptions", "Hypotheses", "Suggested verification"}
    labels = [md.value.split("[")[1].split("]")[0] for md in at.markdown
              if "-badge[" in md.value]
    assert [label for label in labels if label in sections] == [
        "Facts", "Assumptions", "Hypotheses", "Suggested verification"]
    assert "Download the investigation" in {b.label for b in at.get("download_button")}
    _open(at, "Engineering report")
    assert "Download the engineering report" in {b.label for b in at.get("download_button")}


def test_model_page_shows_the_model_card(run_dir):
    at = _open(_render("app.model_page", run_dir), "Model card")
    assert any("## Model purpose" in md.value for md in at.markdown)


def test_figures_saved_with_windows_paths_still_load(tmp_path):
    from app.store import figure as figure_path

    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "chart.png").write_bytes(b"png")
    expected = tmp_path / "figures" / "chart.png"
    assert figure_path(tmp_path, "figures\\chart.png") == expected
    assert figure_path(tmp_path, "figures/chart.png") == expected
    assert figure_path(tmp_path, "figures/missing.png") is None
    assert figure_path(tmp_path, None) is None


def _ask_page(run_dir: Path, role: str = "developer") -> AppTest:
    def page(run_dir, role):
        from pathlib import Path

        import streamlit as st

        from app import ask_page
        from app.auth import Viewer
        from foresight.settings import load_settings

        st.session_state["viewer"] = Viewer(email="ada@example.com", name="Ada", role=role)
        ask_page.render(Path(run_dir), load_settings())

    return AppTest.from_function(page, args=(str(run_dir), role), default_timeout=60).run()


def test_ask_page_answers_with_citations_and_logs_who_asked(run_dir):
    from foresight.rag.chat import questions_by

    at = _ask_page(run_dir)
    assert not at.exception and not at.text_input  # no passcode (Phase 8.6)
    at.chat_input[0].set_value("Which sensors differ between failing and passing runs?").run()
    assert not at.exception
    answers = [m for m in at.chat_message if m.name == "assistant"]
    # Phase 8.10: the citation shows as a plain-name chip, not the tag
    shown = answers[-1].markdown[0].value
    assert ":gray-badge[" in shown and "[source:" not in shown and ".md" not in shown
    assert any(e.label.startswith("Sources") for e in answers[-1].expander)  # developer view
    asked = questions_by(load_settings(), "ada@example.com")
    assert asked[0]["question"].startswith("Which sensors") and asked[0]["run"] == run_dir.name

    user = _ask_page(run_dir, "user")
    user.chat_input[0].set_value("Which sensors differ between failing and passing runs?").run()
    answer = [m for m in user.chat_message if m.name == "assistant"][-1]
    assert ":gray-badge[" in answer.markdown[0].value and not answer.expander  # no sources

    at.chat_input[0].set_value("What is the capital of France?").run()
    answers = [m for m in at.chat_message if m.name == "assistant"]
    assert answers[-1].markdown[0].value == "Not found in this run's artifacts."

    # All runs: no Supabase in tests, so the run folders' indexes (here the reference run)
    at.segmented_control(key="chat_scope").set_value("All runs").run()
    assert not [m for m in at.chat_message if m.name == "assistant"]  # its own history
    at.chat_input[0].set_value("What is the model's test PR-AUC?").run()
    assert not at.exception
    answer = [m for m in at.chat_message if m.name == "assistant"][-1]
    # the run is named: the reference run has no number
    assert ":gray-badge[Reference analysis › " in answer.markdown[0].value
    assert "[source:" not in answer.markdown[0].value
    assert any(e.label.startswith("Sources") for e in answer.expander)

    # a question opened from the sidebar's history belongs to this run: the scope follows
    at.session_state["chat_open"] = {"run": run_dir.name, "question": "Opened from history?",
                                     "answer": "An answer.", "refused": False, "sources": [],
                                     "time": "2026-11-18T10:00:00+00:00"}
    at.run()
    assert at.segmented_control(key="chat_scope").value == "This run"
    assert any(m.markdown[0].value == "Opened from history?" for m in at.chat_message
               if m.name == "user")


def test_viewable_runs_are_successful_runs_then_the_reference(tmp_path, run_dir):
    import json

    from app.runs import describe_run
    from app.store import viewable_runs
    from foresight.settings import load_settings

    runs = tmp_path / "runs"
    for name, status in (("20261116T100000000000Z", "success"),
                         ("20261116T110000000000Z", "failed"),
                         ("20261116T120000000000Z", "success")):
        (runs / name).mkdir(parents=True)
        (runs / name / "run_manifest.json").write_text(json.dumps({"status": status}))
    reference = tmp_path / "reference"
    reference.mkdir()
    (reference / "run_manifest.json").write_text(json.dumps({"status": "success"}))

    settings = load_settings()
    settings.paths.runs_dir, settings.paths.reference_run_dir = runs, reference
    found = viewable_runs(settings)
    assert [p.name for p in found] == ["20261116T120000000000Z", "20261116T100000000000Z",
                                      "reference"]
    # Phase 8.10: an analysis by its number among all recorded (failed ones too), its data and
    # its start (no browser zone in tests)
    assert describe_run(found[0]) == "Analysis 3 · SECOM · 16 Nov, 12:00 UTC"
    assert describe_run(found[-1]) == "Reference analysis · SECOM"
    settings.paths.runs_dir = settings.paths.reference_run_dir = tmp_path / "none"
    assert viewable_runs(settings) == []


def test_pr_points_match_scikit_learn():
    import numpy as np
    from sklearn.metrics import precision_recall_curve

    from app.charts import pr_points

    rng = np.random.default_rng(0)
    labels = rng.integers(0, 2, 300)
    scores = np.round(rng.random(300), 2)  # ties included
    precision, recall = pr_points(labels, scores)
    expected_p, expected_r, _ = precision_recall_curve(labels, scores)
    assert np.allclose(precision, expected_p) and np.allclose(recall, expected_r)


def test_pr_curve_fits_the_precision_axis_and_charts_zoom_on_scroll(monkeypatch, tmp_path):
    import pandas as pd

    from app import charts

    pd.DataFrame({"label": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0] * 5,
                  "fail_probability": [i / 50 for i in range(50)]}).to_csv(
        tmp_path / "predictions.csv", index=False)
    shown, configs = [], []
    monkeypatch.setattr(charts.st, "plotly_chart", lambda fig, **kw: (shown.append(fig),
                                                                      configs.append(kw)))
    charts.pr_curve(tmp_path, baseline=0.2)
    curve = shown[0].data[0]
    assert max(curve.y) < 1  # no made-up (recall 0, precision 1) point
    assert shown[0].layout.yaxis.range[1] == pytest.approx(max(max(curve.y), 0.2) * 1.15)
    assert configs[0]["config"]["scrollZoom"] is True


def test_trends_page_reads_the_run_folders_without_supabase():
    """No database and no new runs: the committed reference run is the history."""
    def page():
        from app import trends_page
        from foresight.settings import load_settings

        trends_page.render(load_settings())

    at = AppTest.from_function(page, default_timeout=60).run()
    assert not at.exception
    assert at.metric[0].label == "Analyses recorded" and at.metric[0].value == "1"
    assert any("run folders on this server" in c.value for c in at.caption)
    assert "trend-quality" in [c.key for c in at.get("plotly_chart")]
    assert any("No stage times recorded yet." in c.value for c in at.caption)
    assert not at.table  # the run table is under Extended data, closed until pressed
    at.segmented_control(key="extended-trends").set_value("Run table").run()
    assert at.table[0].value.iloc[0]["source"] == "Reference"  # 12 columns: wrapped
    assert any("Every recorded run completed." in c.value for c in at.caption)


def test_trends_lists_stopped_runs_with_plain_reasons():
    from foresight.progress import ProgressTracker
    from foresight.settings import load_settings

    runs = load_settings().paths.runs_dir
    failed = ProgressTracker.create(runs / "20260101T000000000000Z", "20260101T000000000000Z")
    failed.running()
    failed.finish("failed", "features_present: test_fails: 4 failing runs in the test period "
                            "(minimum 5)")
    stopped = ProgressTracker.create(runs / "20260102T000000000000Z", "20260102T000000000000Z")
    stopped.running()
    stopped.finish("timeout")  # no reason recorded: NaN in the frame

    def page():
        from app import trends_page
        from foresight.settings import load_settings

        trends_page.render(load_settings())

    at = AppTest.from_function(page, default_timeout=60).run()
    assert not at.exception
    listing = next(m.value for m in at.markdown if m.value.startswith("- :"))
    assert "Not enough failing runs in the newest 25%" in listing
    assert "Took longer than the time limit" in listing


def test_a_synthetic_run_is_labeled_and_shows_its_ground_truth(run_dir, tmp_path):
    import json
    import shutil

    scenario_run = tmp_path / "20260105T000000000000Z"
    shutil.copytree(run_dir, scenario_run)
    (scenario_run / "progress.json").write_text(json.dumps({
        "run_id": scenario_run.name, "status": "success",
        "dataset": "Scenario (synthetic): planted fault on f_031"}))
    (scenario_run / "scenario_check.json").write_text(json.dumps({
        "kind": "planted_fault", "title": "Planted fault", "sensors": ["f_031"],
        "intensity": 3.0, "seed": 7, "training_runs": 112, "training_runs_changed": 11,
        "test_runs_untouched": 38,
        "found": ["f_031"], "sensors_checked": [{"sensor": "f_031", "eda_rank": 2,
                                                 "eda_listed": 15, "model_rank": None,
                                                 "in_reports": True}]}))
    at = _render("app.report_page", scenario_run)
    assert not at.exception
    assert "Synthetic" in at.caption[0].value  # every result page's run line (short)
    assert "training data was changed on purpose" in at.caption[0].proto.help  # its tooltip
    assert any("named **1 of 1**" in m.value for m in at.markdown)
    assert any("11 of 112 training runs changed" in m.value for m in at.markdown)
    table = next(d.value for d in at.dataframe if "EDA rank" in d.value.columns)
    assert table.iloc[0]["EDA rank"] == "2 of 15"


def test_line_replay_plays_the_test_period_and_ends_on_the_runs_own_totals(run_dir):
    import json

    at = _render("app.replay_page", run_dir)
    assert not at.exception
    assert [m.label for m in at.metric] == ["Runs replayed", "Alarms raised",
                                            "Failing runs caught", "Alarm precision"]
    total = int(at.metric[0].value.split(" of ")[1])
    assert at.metric[0].value == f"0 of {total}"

    at.button(key="replay-step").click().run()
    assert at.metric[0].value == f"1 of {total}"
    assert len(at.get("plotly_chart")) == 2  # the stream and the newest run's wafer
    assert any("Simulated wafer" in (m.proto.help or "") for m in at.markdown)  # a tooltip

    at.button(key="replay-toggle").click().run()  # Play: one tick at the default speed (3 runs/s)
    assert not at.exception
    assert at.metric[0].value == f"4 of {total}"
    assert at.button(key="replay-toggle").label == "Pause"
    at.button(key="replay-toggle").click().run()
    assert at.button(key="replay-toggle").label == "Play"

    at.button(key="replay-end").click().run()
    risk = json.loads((run_dir / "risk_summary.json").read_text(encoding="utf-8"))
    test = risk["test"][risk["recommended_ranking"]]
    assert at.metric[0].value == f"{total} of {total}"
    assert at.metric[1].value == str(test["alarms"])
    assert at.metric[2].value == f"{test['fails_found']} of {test['fails_total']}"
    assert "Replay finished" in at.success[0].value

    at.button(key="replay-restart").click().run()
    assert at.metric[0].value == f"0 of {total}"


def test_line_replay_explains_a_run_without_the_risk_ranking(run_dir, tmp_path):
    import shutil

    older = tmp_path / "older"
    shutil.copytree(run_dir, older)
    (older / "risk_scores.csv").unlink()
    at = _render("app.replay_page", older)
    assert not at.exception
    assert "added after this run was made" in at.info[0].value
