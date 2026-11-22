"""Run registry (ADR-027): rows built from run files, recorded in Postgres when configured."""

import os
from pathlib import Path

import pytest

from foresight import registry
from foresight.flow import run_pipeline
from foresight.settings import load_settings

pytestmark = pytest.mark.usefixtures("secom_env")
MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
TEST_DB_URL = os.getenv("FORESIGHT_TEST_DB_URL")  # a throwaway Postgres (CI service container)


def test_history_from_run_folders_and_a_registry_problem_never_fails_a_run():
    state = run_pipeline()
    settings = load_settings()
    assert registry.backend(settings) == "files" and not registry.record_run(
        Path(state.run_dir), settings)

    rows = {r["run_id"]: r for r in registry.history(settings)}
    run = rows[state.run_id]
    assert run["status"] == "success" and run["source"] == "secom"
    assert run["pr_auc"] is not None and run["rows"] == 150 and run["llm_mock"] is True
    assert [g["gate"] for g in run["gates"]] == ["data_contract", "features_present",
                                                 "evidence_present"]
    assert any(r["source"] == "reference" for r in rows.values())  # the committed reference run
    stages = registry.stage_history(settings, [state.run_id])
    assert [s["name"] for s in stages] == ["ingest", "analyze", "model", "investigate", "report"]

    unreachable = settings.model_copy(update={"database_url": "postgresql://u:p@127.0.0.1:1/x"})
    assert registry.record_run(Path(state.run_dir), unreachable) is False  # logged, not raised


@pytest.mark.skipif(not TEST_DB_URL, reason="set FORESIGHT_TEST_DB_URL to a throwaway Postgres")
def test_runs_are_recorded_in_postgres_and_read_back():
    import psycopg

    from foresight.registry.migrate import migrate

    with psycopg.connect(TEST_DB_URL, autocommit=True) as conn:
        conn.execute("drop schema if exists foresight cascade")
        conn.execute("drop schema if exists supabase_migrations cascade")
    assert migrate(TEST_DB_URL) == [p.name for p in sorted(MIGRATIONS.glob("*.sql"))]
    assert migrate(TEST_DB_URL) == []  # already applied: the pre-deploy is a no-op

    state = run_pipeline()  # no database yet: recorded below, like the backfill does
    settings = load_settings().model_copy(update={"database_url": TEST_DB_URL})
    assert registry.record_run(Path(state.run_dir), settings)
    assert registry.record_run(Path(state.run_dir), settings)  # idempotent upsert
    assert registry.sync(settings) == 1  # the reference run; this run is unchanged
    assert registry.sync(settings) == 0

    stored = {r["run_id"]: r for r in registry.history(settings)}
    files = {r["run_id"]: r for r in registry.history(
        settings.model_copy(update={"database_url": ""}))}
    for key in ("status", "source", "rows", "selected_model", "report_pass", "gates"):
        assert stored[state.run_id][key] == files[state.run_id][key]
    assert stored[state.run_id]["pr_auc"] == pytest.approx(files[state.run_id]["pr_auc"])
    assert len(registry.stage_history(settings, [state.run_id])) == 5
    with psycopg.connect(TEST_DB_URL) as conn:
        rls = conn.execute("select bool_and(relrowsecurity) from pg_class c join pg_namespace n "
                           "on n.oid = c.relnamespace where n.nspname = 'foresight' "
                           "and c.relkind = 'r'").fetchone()[0]
    assert rls  # RLS on every registry table

    # Cross-run memory: the runs' chat chunks in pgvector rank like the run folders' indexes
    from foresight.rag.cross import retrieve_all
    from foresight.registry import db

    known = db.recorded(TEST_DB_URL)
    assert known[state.run_id][1] == len(registry.chunk_records(Path(state.run_dir))) > 0
    question = "What is the model's test PR-AUC?"
    stored_hits, runs = retrieve_all(question, settings)
    file_hits, _ = retrieve_all(question, settings.model_copy(update={"database_url": ""}))
    assert stored_hits and stored_hits[0].chunk.source == file_hits[0].chunk.source
    assert stored_hits[0].score == pytest.approx(file_hits[0].score, abs=1e-3)
    assert set(runs) <= {state.run_id, *known}
    only, runs = retrieve_all(question, settings, run_ids=[state.run_id])  # a user's runs
    assert only and set(runs) == {state.run_id}
    assert retrieve_all(question, settings, run_ids=[]) == ([], {})


def test_a_stopped_scenario_run_without_a_manifest_is_still_synthetic(tmp_path):
    from foresight.progress import ProgressTracker
    from foresight.registry import run_record
    from foresight.settings import load_settings

    run = tmp_path / "20260101T000000000000Z"
    tracker = ProgressTracker.create(run, run.name, "Scenario (synthetic): sensor drift")
    tracker.finish("timeout", "stopped by the timeout guard after 1200 s")
    assert run_record(run, load_settings())["source"] == "scenario"
