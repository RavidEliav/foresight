from pathlib import Path

from streamlit.testing.v1 import AppTest

from foresight import jobs
from foresight.flow import run_pipeline

APP = str(Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py")


def _app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


DEVELOPER_MENU = ["Run Pipeline", "Data Quality", "EDA & Insights", "Model",
                  "Investigation & Report", "Line Replay", "Trends", "Ask Foresight",
                  "My activity", "Users & access"]


def test_app_loads_with_brand_menu_and_environment_badge():
    """A local checkout without Google keys opens as a local developer (Phase 8.6)."""
    at = _app()
    assert not at.exception
    assert at.title[0].value == "Run Pipeline"
    assert any("Environment: local" in md.value for md in at.sidebar.markdown)
    brand = at.sidebar.get("html")[0].proto.body
    assert "Semiconductor yield intelligence" in brand and "data:image/svg+xml" in brand
    links = [link.proto.label for link in at.sidebar.get("page_link")]
    assert links == DEVELOPER_MENU
    assert not at.text_input  # no passcode anywhere
    assert at.get("popover")[0].proto.popover.label == "Hi, Local"


def test_upload_without_a_file_is_rejected():
    at = _app()
    at.radio(key="source").set_value("Upload a CSV").run()
    at.button(key="run").click().run()
    assert any("Choose a CSV file" in err.value for err in at.error)


def test_run_limit_is_explained(monkeypatch):
    def busy(*_args, **_kwargs):
        raise jobs.RunLimitError("Run X is still in progress.")

    monkeypatch.setattr(jobs, "start_run", busy)
    at = _app()
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


def test_interrupted_run_can_be_resumed(monkeypatch):
    """After a restart nothing is watched; the newest run shows up if it can continue."""
    from datetime import UTC, datetime, timedelta

    from foresight.progress import ProgressTracker, load_progress
    from foresight.settings import load_settings

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
    monkeypatch.setattr(jobs, "resume_run",
                        lambda _s, run_id, user="": continued.append((run_id, user)))

    at = _app()
    assert any("was interrupted" in w.value and "The app restarted while the run was going"
               in w.value for w in at.warning)  # the cause, not "for example"
    stepper = next(h.proto.body for h in at.get("html") if "fs-stepper" in h.proto.body)
    assert 'class="fs-stage fs-interrupted"' in stepper  # not animated as running
    at.button(key="continue").click().run()
    assert continued == [("20260101T000000000000Z", "")]  # local checkout: no email

    # Two hours later it no longer takes over the page; it waits in the history, with its cause
    progress.updated_at = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    (run_dir / "progress.json").write_text(progress.model_dump_json())
    at = _app()
    assert not any("was interrupted" in w.value for w in at.warning)
    assert not [b for b in at.button if b.key == "continue"]
    history = at.dataframe[0].value
    assert history.iloc[0]["why it stopped"].startswith("The app restarted")


def test_a_full_volume_gives_a_message_not_a_crash_page(monkeypatch):
    import errno

    def full(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(jobs, "start_run", full)
    at = _app()
    at.button(key="run").click().run()
    assert not at.exception
    assert any("the server's storage is full" in e.value for e in at.error)


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

    def run_now(settings, *_upload, **_user):
        return run_pipeline(settings).run_id

    monkeypatch.setattr(jobs, "start_run", run_now)
    at = _app()
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

    raw = load_raw(secom_env.paths.data_raw_dir)
    raw.loc[:4, "label_raw"] = 2
    upload = tmp_path / "broken.csv"
    upload.write_bytes(to_upload_csv(raw))

    def run_upload(settings, *_upload, **_user):
        return run_pipeline(settings, dataset=upload).run_id

    monkeypatch.setattr(jobs, "start_run", run_upload)
    at = _app()
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
    started = []
    monkeypatch.setattr(jobs, "start_run", lambda *a, **k: started.append(a) or "r1")
    at = _app()
    at.radio(key="source").set_value("Scenario (synthetic)").run()
    assert any("Only the training period changes" in c.value for c in at.caption)
    at.selectbox(key="scenario_kind").set_value("drift").run()
    at.button(key="run").click().run()
    assert started and started[0][1] is None  # no upload
    assert started[0][3] == {"kind": "drift", "intensity": 2.0, "seed": 7}


def test_a_running_run_can_be_stopped_then_resumed(monkeypatch):
    """Phase 8.5: Stop run asks the run to stop; a stopped run offers Resume run."""
    from foresight.progress import ProgressTracker
    from foresight.settings import load_settings

    settings = load_settings()
    run_id = "20260101T000000000000Z"
    run_dir = jobs.runs_dir(settings) / run_id
    tracker = ProgressTracker.create(run_dir, run_id)
    tracker.running()
    tracker.stage_started("ingest")

    at = _app()
    assert any("is running" in i.value for i in at.info)
    at.button(key="stop").click().run()
    assert jobs.stop_requested(run_dir)
    assert any("Stopping the run" in c.value for c in at.caption)

    tracker.finish("stopped", "stopped by the user")  # what the run's process does
    resumed = []
    monkeypatch.setattr(jobs, "resume_run", lambda _s, rid, user="": resumed.append(rid))
    at = _app()
    assert any("was stopped" in w.value for w in at.warning)
    stepper = next(h.proto.body for h in at.get("html") if "fs-stepper" in h.proto.body)
    assert 'class="fs-stage fs-stopped"' in stepper
    assert at.button(key="continue").label == "Resume run"
    at.button(key="continue").click().run()
    assert resumed == [run_id]


def test_an_archived_run_is_loaded_again_when_picked(monkeypatch):
    """ADR-033: an older run is only a stub on the server; picking it downloads its files."""
    import json

    from foresight.progress import ProgressTracker
    from foresight.registry import archive
    from foresight.settings import load_settings

    monkeypatch.setenv("SUPABASE_DB_URL",
                       "postgresql://postgres.abcdefghijklmnopqrst:pw@127.0.0.1:1/x")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")
    settings = load_settings()
    run_id = "20261123T090000000000Z"
    folder = jobs.runs_dir(settings) / run_id
    ProgressTracker.create(folder, run_id, "SECOM (UCI)").finish("success")
    (folder / "run_manifest.json").write_text(json.dumps({"run_id": run_id, "status": "success"}))
    (folder / "validation_summary.json").write_text('{"checks": []}')
    stored = archive.pack(folder)

    class Found:
        status_code, content, text = 200, stored, ""

    monkeypatch.setattr(archive, "_request", lambda *_a, **_k: Found())
    archive._write_marker(folder, {"updated_at": "x", "stub": True})
    archive.make_stub(folder)
    assert not (folder / "validation_summary.json").exists()

    at = _app()
    assert not at.exception
    assert at.sidebar.selectbox(key="view_run").options[0].endswith("SECOM")
    assert (folder / "validation_summary.json").exists()  # loaded for the result pages
    assert not archive.is_stub(folder)
