from pathlib import Path

from streamlit.testing.v1 import AppTest

from foresight import jobs
from foresight.flow import run_pipeline

APP = str(Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py")


def _app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def test_app_loads_with_brand_menu_and_environment_badge():
    at = _app()
    assert not at.exception
    assert at.title[0].value == "Run Pipeline"
    assert any("Environment: local" in md.value for md in at.sidebar.markdown)
    brand = at.sidebar.get("html")[0].proto.body
    assert "Semiconductor yield intelligence" in brand and "data:image/svg+xml" in brand
    links = [link.proto.label for link in at.sidebar.get("page_link")]
    assert links == ["Run Pipeline", "Data Quality", "EDA & Insights", "Model",
                     "Investigation & Report", "Line Replay", "Trends", "Ask Foresight"]


def test_runs_disabled_message_without_passcode():
    at = _app()
    assert any("RUN_PASSCODE is not configured" in info.value for info in at.info)


def test_wrong_passcode_is_rejected(monkeypatch):
    monkeypatch.setenv("RUN_PASSCODE", "s3cret")
    started = []
    monkeypatch.setattr(jobs, "start_run", lambda *a: started.append(a))
    at = _app()
    at.text_input(key="passcode").input("wrong")
    at.button(key="run").click().run()
    assert any("Not authorized" in err.value for err in at.error)
    assert not started


def test_upload_without_a_file_is_rejected(monkeypatch):
    monkeypatch.setenv("RUN_PASSCODE", "s3cret")
    at = _app()
    at.radio(key="source").set_value("Upload a CSV").run()
    at.text_input(key="passcode").input("s3cret")
    at.button(key="run").click().run()
    assert any("Choose a CSV file" in err.value for err in at.error)


def test_run_limit_is_explained(monkeypatch):
    monkeypatch.setenv("RUN_PASSCODE", "s3cret")

    def busy(*_args):
        raise jobs.RunLimitError("Run X is still in progress.")

    monkeypatch.setattr(jobs, "start_run", busy)
    at = _app()
    at.text_input(key="passcode").input("s3cret")
    at.button(key="run").click().run()
    assert any("still in progress" in w.value for w in at.warning)


def test_run_found_by_progress_stays_visible_after_it_finishes(monkeypatch):
    """A visitor who didn't start the run (e.g. after a refresh) still sees how it ended."""
    from foresight.progress import ProgressTracker
    from foresight.settings import load_settings

    settings = load_settings()
    tracker = ProgressTracker.create(jobs.runs_dir(settings) / "20260101T000000000000Z",
                                     "20260101T000000000000Z")
    tracker.running()
    tracker.stage_started("ingest")
    at = _app()
    assert any("is running" in i.value for i in at.info)

    tracker.finish("timeout", "stopped by the timeout guard after 1200 s")
    at.run()
    assert any("took longer than the time limit" in e.value for e in at.error)
    assert any("timeout guard after 1200 s" in c.value for c in at.code)  # technical details


def test_interrupted_run_can_be_continued_with_the_passcode(monkeypatch):
    """After a restart nothing is watched; the newest run shows up if it can continue."""
    from datetime import UTC, datetime, timedelta

    from foresight.progress import ProgressTracker, load_progress
    from foresight.settings import load_settings

    monkeypatch.setenv("RUN_PASSCODE", "s3cret")
    settings = load_settings()
    run_dir = jobs.runs_dir(settings) / "20260101T000000000000Z"
    tracker = ProgressTracker.create(run_dir, "20260101T000000000000Z")
    tracker.running()
    tracker.stage_started("ingest")
    tracker.stage_finished("ingest", 1.0, artifacts={"p": str(run_dir / "progress.json")})
    tracker.stage_started("analyze")
    progress = load_progress(run_dir)
    progress.updated_at = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    (run_dir / "progress.json").write_text(progress.model_dump_json())
    continued = []
    monkeypatch.setattr(jobs, "resume_run", lambda _s, run_id: continued.append(run_id))

    at = _app()
    assert any("was interrupted" in w.value for w in at.warning)
    stepper = next(h.proto.body for h in at.get("html") if "fs-stepper" in h.proto.body)
    assert 'class="fs-stage fs-interrupted"' in stepper  # not animated as running
    at.button(key="continue").click().run()
    assert any("Not authorized" in e.value for e in at.error) and not continued

    at.text_input(key="passcode").input("s3cret")
    at.button(key="continue").click().run()
    assert continued == ["20260101T000000000000Z"]


def test_stage_tile_matches_its_crew_line(tmp_path):
    """A stage whose crew works in the background shows as running until the crew is done;
    a stage that finishes after its crew says what it is still doing."""
    from app.stepper import stepper_html
    from foresight.progress import ProgressTracker

    tracker = ProgressTracker.create(tmp_path, "r")
    tracker.running()
    tracker.stage_started("analyze")
    tracker.crew("analyst", "running")
    tracker.stage_finished("analyze", 3.0)
    tracker.stage_started("report")
    tracker.crew("report", "done")
    tiles = stepper_html(tracker.progress).split('<div class="fs-stage ')[1:]
    analyze, report = tiles[1], tiles[4]
    assert analyze.startswith("fs-running") and "crew working" in analyze
    assert report.startswith("fs-running") and "indexing for chat" in report

    tracker.crew_finished("analyze", {}, {"analyst": {"seconds": 40.2}})
    analyze = stepper_html(tracker.progress).split('<div class="fs-stage ')[2]
    assert analyze.startswith("fs-done") and "done · 43 s" in analyze  # stage + crew time


def test_finished_run_shows_stages_gates_and_becomes_viewable(monkeypatch, secom_env):
    """start_run replaced by a synchronous run: the page shows the finished run's progress."""
    monkeypatch.setenv("RUN_PASSCODE", "s3cret")

    def run_now(settings, *_upload):
        return run_pipeline(settings).run_id

    monkeypatch.setattr(jobs, "start_run", run_now)
    at = _app()
    at.text_input(key="passcode").input("s3cret")
    at.button(key="run").click().run()
    assert not at.exception
    assert any("completed" in s.value for s in at.success)
    assert any("Data Contract: PASS" in md.value for md in at.markdown)
    stepper = next(h.proto.body for h in at.get("html") if "fs-stepper" in h.proto.body)
    assert stepper.count('class="fs-stage fs-done"') == 5
    assert "Data Analyst crew · done" in stepper
    assert stepper.count("fs-gate-pass") + stepper.count("fs-gate-warning") == 3
    assert "Run history (1)" in [e.label for e in at.expander]
    at.run()  # the next rerun lists the new run first in the sidebar selector
    selector = at.sidebar.selectbox(key="view_run")
    assert Path(selector.value).parent == jobs.runs_dir(secom_env)


def test_failed_upload_run_lists_the_failed_data_checks(monkeypatch, secom_env, tmp_path):
    from foresight.data.secom import load_raw, to_upload_csv

    monkeypatch.setenv("RUN_PASSCODE", "s3cret")
    raw = load_raw(secom_env.paths.data_raw_dir)
    raw.loc[:4, "label_raw"] = 2
    upload = tmp_path / "broken.csv"
    upload.write_bytes(to_upload_csv(raw))

    def run_upload(settings, *_upload):
        return run_pipeline(settings, dataset=upload).run_id

    monkeypatch.setattr(jobs, "start_run", run_upload)
    at = _app()
    at.text_input(key="passcode").input("s3cret")
    at.button(key="run").click().run()
    assert not at.exception
    assert any("stopped" in err.value and "Some labels are not -1 (pass) or 1 (fail)"
               in err.value for err in at.error)
    assert any("upload it again" in i.value for i in at.info)
    failed = at.dataframe[0].value  # technical details: the failed checks by name
    assert "raw_label_values" in set(failed["name"])


def test_only_the_store_touches_run_data():
    """ADR-020: pages read runs, start runs and ask the chat through app/store.py only."""
    import re

    forbidden = re.compile(r"(?<!store\.)read_text\(|(?<!store\.)read_bytes\(|\.exists\(\)|"
                           r"pd\.read_csv|json\.loads|iterdir|from foresight import jobs|"
                           r"foresight\.rag|foresight\.registry|load_progress")
    app_dir = Path(APP).parent
    offenders = [f"{path.name}: {line.strip()}" for path in app_dir.glob("*.py")
                 if path.name != "store.py"
                 for line in path.read_text(encoding="utf-8").splitlines()
                 if forbidden.search(line) and "LOGO" not in line]
    assert offenders == []


def test_a_scenario_run_is_started_with_its_recipe(monkeypatch):
    monkeypatch.setenv("RUN_PASSCODE", "s3cret")
    started = []
    monkeypatch.setattr(jobs, "start_run", lambda *a: started.append(a) or "r1")
    at = _app()
    at.radio(key="source").set_value("Scenario (synthetic)").run()
    assert any("Only the training period changes" in c.value for c in at.caption)
    at.selectbox(key="scenario_kind").set_value("drift").run()
    at.text_input(key="passcode").input("s3cret")
    at.button(key="run").click().run()
    assert started and started[0][1] is None  # no upload
    assert started[0][3] == {"kind": "drift", "intensity": 2.0, "seed": 7}


def test_a_running_run_can_be_stopped_with_the_passcode_then_resumed(monkeypatch):
    """Phase 8.5: Stop run asks the run to stop; a stopped run offers Resume run."""
    from foresight.progress import ProgressTracker
    from foresight.settings import load_settings

    monkeypatch.setenv("RUN_PASSCODE", "s3cret")
    settings = load_settings()
    run_id = "20260101T000000000000Z"
    run_dir = jobs.runs_dir(settings) / run_id
    tracker = ProgressTracker.create(run_dir, run_id)
    tracker.running()
    tracker.stage_started("ingest")

    at = _app()
    assert any("is running" in i.value for i in at.info)
    at.button(key="stop").click().run()
    assert any("Not authorized" in e.value for e in at.error)
    assert not jobs.stop_requested(run_dir)

    at.text_input(key="passcode").input("s3cret")
    at.button(key="stop").click().run()
    assert jobs.stop_requested(run_dir)
    assert any("Stopping the run" in c.value for c in at.caption)

    tracker.finish("stopped", "stopped by the user")  # what the run's process does
    resumed = []
    monkeypatch.setattr(jobs, "resume_run", lambda _s, rid: resumed.append(rid))
    at = _app()
    assert any("was stopped" in w.value for w in at.warning)
    stepper = next(h.proto.body for h in at.get("html") if "fs-stepper" in h.proto.body)
    assert 'class="fs-stage fs-stopped"' in stepper
    assert at.button(key="continue").label == "Resume run"
    at.text_input(key="passcode").input("s3cret")
    at.button(key="continue").click().run()
    assert resumed == [run_id]
