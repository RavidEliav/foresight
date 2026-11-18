import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta

import pytest

from foresight import jobs
from foresight.progress import ProgressTracker, load_progress
from foresight.settings import PROJECT_ROOT, load_settings


def _fake_run(settings, run_id, status="running", minutes_ago=0, heartbeat_s_ago=0):
    run_dir = jobs.runs_dir(settings) / run_id
    tracker = ProgressTracker.create(run_dir, run_id)
    tracker.progress.status = status
    tracker.progress.started_at = (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()
    tracker.save()
    if heartbeat_s_ago:
        progress = load_progress(run_dir)
        progress.updated_at = (datetime.now(UTC) - timedelta(seconds=heartbeat_s_ago)).isoformat()
        (run_dir / "progress.json").write_text(progress.model_dump_json())
    return run_dir


def test_tracker_records_stages_gates_and_skips_the_rest_on_failure(tmp_path):
    tracker = ProgressTracker.create(tmp_path / "run", "r1", "Uploaded CSV (x.csv)")
    tracker.running()
    tracker.stage_started("ingest")
    tracker.stage_finished("ingest", 1.23)
    tracker.gate("data_contract", "ERROR", ["raw_label_values: bad"])
    tracker.finish("failed", "data_contract: raw_label_values: bad")

    progress = load_progress(tmp_path / "run")
    assert progress.dataset == "Uploaded CSV (x.csv)"
    assert [(s.name, s.status) for s in progress.stages] == [
        ("ingest", "done"), ("analyze", "skipped"), ("model", "skipped"),
        ("investigate", "skipped"), ("report", "skipped")]
    assert progress.stages[0].seconds == 1.2
    assert progress.gates[0]["status"] == "ERROR"
    assert progress.effective_status() == "failed"


def test_run_without_heartbeat_counts_as_interrupted():
    settings = load_settings()
    run_dir = _fake_run(settings, "20260101T000000000000Z", heartbeat_s_ago=600)
    assert load_progress(run_dir).effective_status() == "interrupted"
    assert jobs.active_run(settings) is None


@pytest.mark.parametrize(("status", "reason", "heartbeat_s_ago", "expected"), [
    ("running", None, 600, True),  # interrupted: the app restarted
    ("timeout", "stopped by the timeout guard after 1200 s", 0, True),
    ("failed", "model stage error: connection reset", 0, True),
    ("failed", "features_present: test_fails: 4 failing runs", 0, False),  # same data, same stop
    ("success", None, 0, False),
    ("running", None, 0, False),
])
def test_which_runs_can_continue(status, reason, heartbeat_s_ago, expected):
    settings = load_settings()
    run_dir = _fake_run(settings, "20260101T000000000000Z", status, 0, heartbeat_s_ago)
    progress = load_progress(run_dir)
    progress.failure_reason = reason
    assert progress.can_continue is expected


def test_continuing_a_run_resets_what_did_not_finish_and_counts_toward_the_limit(monkeypatch):
    settings = load_settings()
    run_dir = _fake_run(settings, "20260101T000000000000Z", heartbeat_s_ago=600)
    tracker = ProgressTracker.create(run_dir, "20260101T000000000000Z")
    tracker.stage_finished("ingest", 1.0, artifacts={"x": str(run_dir / "progress.json")})
    tracker.stage_started("analyze")
    tracker.crew("analyst", "running")
    progress = tracker.progress
    progress.updated_at = (datetime.now(UTC) - timedelta(seconds=600)).isoformat()
    (run_dir / "progress.json").write_text(progress.model_dump_json())
    launched = []
    monkeypatch.setattr(jobs, "_launch", lambda command, _dir: launched.append(command))

    jobs.resume_run(settings, "20260101T000000000000Z")
    progress = load_progress(run_dir)
    assert progress.status == "queued" and len(progress.resumed_at) == 1
    assert [(s.status, s.crew_status) for s in progress.stages[:2]] == [("done", None),
                                                                         ("pending", None)]
    assert launched[0][-1] == "--resume"
    assert jobs.runs_in_last_hour(settings) == 2  # the start and the continue
    with pytest.raises(jobs.RunLimitError, match="still in progress"):
        jobs.resume_run(settings, "20260101T000000000000Z")


def test_only_stages_with_their_files_are_reused(tmp_path):
    from foresight.progress import StageProgress

    kept = tmp_path / "eda_summary.json"
    kept.write_text("{}")
    stage = StageProgress(name="analyze", label="EDA", status="done")
    assert not stage.reusable  # recorded before Phase 6.1: no artifacts listed
    stage.artifacts = {"eda_summary": str(kept)}
    assert stage.reusable
    kept.unlink()
    assert not stage.reusable  # a listed file is gone: redo the stage
    assert not StageProgress(name="ingest", label="x", status="done",
                             artifacts={"p": str(tmp_path)}).reusable


def test_only_one_run_at_a_time():
    settings = load_settings()
    _fake_run(settings, "20260101T000000000000Z")
    with pytest.raises(jobs.RunLimitError, match="still in progress"):
        jobs.check_can_start(settings)


def test_runs_per_hour_are_limited():
    settings = load_settings()
    settings.app.max_runs_per_hour = 2
    _fake_run(settings, "20260101T000000000001Z", status="success", minutes_ago=10)
    _fake_run(settings, "20260101T000000000002Z", status="failed", minutes_ago=20)
    _fake_run(settings, "20260101T000000000003Z", status="success", minutes_ago=90)
    with pytest.raises(jobs.RunLimitError, match="2 runs per hour"):
        jobs.check_can_start(settings)
    settings.app.max_runs_per_hour = 3
    jobs.check_can_start(settings)


def test_oldest_finished_runs_are_pruned_but_never_an_active_one():
    settings = load_settings()
    settings.app.keep_runs = 2
    _fake_run(settings, "20260101T000000000001Z")  # oldest, but still running
    for i in range(2, 6):
        _fake_run(settings, f"20260101T00000000000{i}Z", status="success")
    removed = jobs.prune_runs(settings)
    assert removed == ["20260101T000000000003Z", "20260101T000000000002Z"]
    assert sorted(p.name for p in jobs.runs_dir(settings).iterdir()) == [
        "20260101T000000000001Z", "20260101T000000000004Z", "20260101T000000000005Z"]


def _wait_until_finished(run_dir, timeout_s=180):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        progress = load_progress(run_dir)
        if progress and progress.status not in ("queued", "running"):
            return progress
        time.sleep(1)
    raise AssertionError(f"run did not finish: {load_progress(run_dir)}")


def test_background_run_on_an_upload_completes_with_progress(secom_env):
    from foresight.data.secom import load_raw, to_upload_csv

    upload = to_upload_csv(load_raw(secom_env.paths.data_raw_dir))
    run_id = jobs.start_run(secom_env, upload, "batch.csv")
    run_dir = jobs.runs_dir(secom_env) / run_id
    progress = _wait_until_finished(run_dir)

    assert progress.status == "success", (run_dir / jobs.LOG_FILE).read_text()
    assert progress.dataset == "Uploaded CSV (batch.csv)"
    assert all(s.status == "done" for s in progress.stages)
    assert [g["gate"] for g in progress.gates] == ["data_contract", "features_present",
                                                  "evidence_present"]
    assert (run_dir / "engineering_report.md").exists()
    assert "upload.csv" in (run_dir / "run_manifest.json").read_text()


def test_timeout_guard_stops_the_run(secom_env):
    run_dir = jobs.runs_dir(secom_env) / "timeout-run"
    result = subprocess.run(
        [sys.executable, "-m", "foresight.cli", "run", "--run-id", "timeout-run", "--timeout",
         "1"], cwd=PROJECT_ROOT, env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True, timeout=120)
    progress = load_progress(run_dir)
    assert result.returncode == 3
    assert progress.status == "timeout"
    assert "timeout guard after 1 s" in (run_dir / "failure_report.md").read_text()
