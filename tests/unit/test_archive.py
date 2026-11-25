"""Run files in Supabase Storage, chat history in Postgres (ADR-033), with Storage and the
database replaced by dictionaries."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from foresight import jobs
from foresight.progress import ProgressTracker, load_progress
from foresight.registry import archive, db
from foresight.settings import load_settings, project_url

RUN = "20261123T090000000000Z"


class FakeResponse:
    def __init__(self, status_code: int, content: bytes = b""):
        self.status_code, self.content, self.text = status_code, content, ""


@pytest.fixture
def supabase(monkeypatch):
    """Storage objects and registry rows in memory; the settings point at "Supabase"."""
    monkeypatch.setenv("SUPABASE_DB_URL",
                       "postgresql://postgres.abcdefghijklmnopqrst:pw@pooler.example.com:5432/x")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")
    objects: dict[str, bytes] = {}
    rows: dict[str, dict] = {}
    calls: list[tuple[str, dict]] = []

    def request(method, url, data=None, headers=None):
        calls.append((method, headers))
        name = url.rsplit("/", 1)[-1]
        if method == "POST":
            objects[name] = data
            return FakeResponse(200)
        return FakeResponse(200, objects[name]) if name in objects else FakeResponse(400)

    def upsert_run(_url, run, stages, chunks=None):
        rows[run["run_id"]] = {**rows.get(run["run_id"], {}), **run}

    def mark_archived(_url, run_id, size):
        rows[run_id]["archive_bytes"] = size

    def fetch_archived(_url):
        return [{"run_id": r["run_id"], "progress": r["progress"], "manifest": r["manifest"]}
                for r in rows.values() if "archive_bytes" in r]

    monkeypatch.setattr(archive, "_request", request)
    monkeypatch.setattr(db, "upsert_run", upsert_run)
    monkeypatch.setattr(db, "mark_archived", mark_archived)
    monkeypatch.setattr(db, "fetch_archived", fetch_archived)
    return {"objects": objects, "rows": rows, "calls": calls}


def _finished_run(settings, run_id=RUN, status="success", by="ada@example.com"):
    folder = jobs.runs_dir(settings) / run_id
    tracker = ProgressTracker.create(folder, run_id, "SECOM (UCI)", started_by=by)
    tracker.finish(status)
    (folder / "run_manifest.json").write_text(json.dumps({"run_id": run_id, "status": status}))
    (folder / "model_metrics.json").write_text('{"test_metrics": {"pr_auc": 0.31}}')
    (folder / "figures").mkdir()
    (folder / "figures" / "pr_curve.png").write_bytes(b"\x89PNG" + bytes(2000))
    (folder / "run.log").write_text("run done\n")
    return folder


def test_the_project_url_comes_from_the_database_url():
    assert project_url("postgresql://postgres.abcdefghijklmnopqrst:pw@aws-1-us-east-1.pooler."
                       "supabase.com:5432/postgres") == "https://abcdefghijklmnopqrst.supabase.co"
    assert project_url("postgresql://postgres:pw@db.abcdefghijklmnopqrst.supabase.co:5432/x") \
        == "https://abcdefghijklmnopqrst.supabase.co"
    assert project_url("postgresql://u:p@127.0.0.1:5432/x") == ""


def test_without_the_secret_key_nothing_is_archived():
    settings = load_settings()
    assert not settings.archive
    folder = _finished_run(settings)
    assert archive.archive_run(folder, settings) is False
    settings.app.keep_runs = 0
    assert jobs.prune_runs(settings) == [RUN]  # the old way: deleted
    assert not folder.exists()


def test_a_finished_run_goes_to_storage_and_leaves_a_stub_that_still_lists(supabase):
    settings = load_settings()
    assert settings.archive and settings.storage_url == "https://abcdefghijklmnopqrst.supabase.co"
    folder = _finished_run(settings)
    files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())

    assert archive.archive_run(folder, settings)
    assert set(supabase["objects"]) == {f"{RUN}.tar.gz"}
    method, headers = supabase["calls"][0]
    assert method == "POST" and headers["x-upsert"] == "true"
    assert headers["apikey"] == "sb_secret_test"  # server-side key, never in a page
    row = supabase["rows"][RUN]
    assert row["progress"]["started_by"] == "ada@example.com" and row["archive_bytes"] > 0
    assert archive.archive_run(folder, settings) and len(supabase["calls"]) == 1  # once

    settings.app.keep_full_runs = 0
    assert jobs.prune_runs(settings) == [RUN]
    assert sorted(p.name for p in folder.iterdir()) == ["archived.json", "progress.json",
                                                         "run_manifest.json"]
    assert archive.is_stub(folder)
    # lists, labels and history still work from the stub
    assert [p.run_id for p in jobs.list_runs(settings)] == [RUN]
    assert load_progress(folder).started_by == "ada@example.com"

    assert archive.ensure_full(settings, folder)  # a page needs its files: downloaded again
    assert sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*")
                  if p.is_file()) == sorted([*files, "archived.json"])
    assert (folder / "figures" / "pr_curve.png").read_bytes() == b"\x89PNG" + bytes(2000)
    assert not archive.is_stub(folder)


def test_the_newest_runs_stay_whole_and_unarchived_runs_are_never_slimmed(supabase,
                                                                         monkeypatch):
    settings = load_settings()
    settings.app.keep_full_runs = 1
    old, new = (_finished_run(settings, f"20261123T0{h}0000000000Z") for h in (8, 9))
    assert jobs.prune_runs(settings) == [old.name]
    assert archive.is_stub(old) and not archive.is_stub(new)

    supabase["objects"].clear()
    stranded = _finished_run(settings, "20261123T070000000000Z")
    monkeypatch.setattr(archive, "_request", lambda *a, **k: FakeResponse(500))  # Storage down
    assert jobs.prune_runs(settings) == []
    assert (stranded / "run.log").exists()  # kept whole until it is safely archived


def test_a_wiped_volume_gets_its_stubs_back_from_the_registry(supabase):
    import shutil

    settings = load_settings()
    folder = _finished_run(settings)
    archive.archive_run(folder, settings)
    shutil.rmtree(jobs.runs_dir(settings))
    assert archive.restore_stubs(settings) == 1
    assert archive.is_stub(folder) and load_progress(folder).run_id == RUN
    assert json.loads((folder / "run_manifest.json").read_text())["status"] == "success"
    assert archive.restore_stubs(settings) == 0
    assert archive.ensure_full(settings, folder)
    assert (folder / "model_metrics.json").exists()


def test_an_interrupted_run_is_archived_with_its_cause(supabase, monkeypatch):
    # "the app restarted": the run went quiet before this app started. Pin the start, so the
    # test does not depend on how long the test session has been running (it took over 5 min)
    monkeypatch.setattr(jobs, "SERVER_STARTED", datetime.now(UTC))
    settings = load_settings()
    folder = jobs.runs_dir(settings) / RUN
    tracker = ProgressTracker.create(folder, RUN)
    tracker.running()
    progress = load_progress(folder)
    progress.updated_at = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    (folder / "progress.json").write_text(progress.model_dump_json())

    assert archive.archive_run(folder, settings)
    stored = load_progress(folder)
    assert stored.status == "interrupted"
    assert stored.failure_reason.startswith("The app restarted")  # kept for the stub's history
    assert supabase["rows"][RUN]["failure_reason"] == stored.failure_reason
    assert stored.can_continue


def test_resume_loads_a_stub_first(supabase, monkeypatch):
    settings = load_settings()
    monkeypatch.setattr(jobs, "_launch", lambda *_: None)
    lost = _finished_run(settings, "20261123T080000000000Z", status="stopped")
    archive.archive_run(lost, settings)
    archive.make_stub(lost)
    supabase["objects"].clear()  # Storage lost it
    with pytest.raises(jobs.RunLimitError, match="could not be loaded from Supabase"):
        jobs.resume_run(settings, lost.name)

    folder = _finished_run(settings, status="stopped")
    archive.archive_run(folder, settings)
    archive.make_stub(folder)
    jobs.resume_run(settings, RUN)
    assert not archive.is_stub(folder) and (folder / "model_metrics.json").exists()
    assert load_progress(folder).status == "queued"


def test_stubs_are_never_recorded_over_their_full_row(supabase):
    from foresight import registry

    settings = load_settings()
    folder = _finished_run(settings)
    archive.archive_run(folder, settings)
    archive.make_stub(folder)
    supabase["rows"][RUN]["pr_auc"] = 0.31
    assert registry.record_run(folder, settings) is False
    assert folder not in registry._run_folders(settings)
    assert supabase["rows"][RUN]["pr_auc"] == 0.31


def test_chat_history_goes_to_supabase_and_falls_back_to_the_file(monkeypatch):
    from pathlib import Path

    from foresight.rag import chat

    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://u:p@127.0.0.1:5432/x")
    settings = load_settings()
    stored: list[dict] = []
    monkeypatch.setattr(db, "insert_questions", lambda _u, records: stored.extend(records))
    monkeypatch.setattr(db, "fetch_questions", lambda _u, run, user, limit: [
        r for r in reversed(stored) if (run is None or r["run"] == run)
        and (user is None or r["user"] == user)][:limit])
    run = Path(RUN)
    answer = chat.ChatAnswer(question="Which sensor?", answer="f_558.", refused=False)
    chat.log_answer(settings, run, answer, "ada@example.com")
    assert [r["question"] for r in stored] == ["Which sensor?"]
    assert not chat.log_path(settings, run).exists()  # nothing on the volume
    assert chat.recent_questions(settings, run, user="ada@example.com")[0]["answer"] == "f_558."
    assert chat.questions_by(settings, "ada@example.com")[0]["run"] == RUN

    def down(*_args):
        raise OSError("database unreachable")

    monkeypatch.setattr(db, "insert_questions", down)
    chat.log_answer(settings, run, answer.model_copy(update={"question": "Later?"}), "bob")
    assert chat.log_path(settings, run).exists()  # kept in the file meanwhile
    monkeypatch.setattr(db, "insert_questions", lambda _u, records: stored.extend(records))
    assert chat.import_chat_logs(settings) == 1  # the next app start moves it
    assert stored[-1]["question"] == "Later?" and stored[-1]["run"] == RUN
    assert not chat.log_path(settings, run).exists()
