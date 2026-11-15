from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.data_quality import latest_run_dir


def _render(run_dir: str | None) -> AppTest:
    def page(run_dir):
        from pathlib import Path

        from app.data_quality import render

        render(Path(run_dir) if run_dir else None)

    return AppTest.from_function(page, args=(run_dir,), default_timeout=60).run()


def test_latest_run_dir_picks_newest_validated_run(tmp_path):
    assert latest_run_dir(tmp_path / "missing") is None
    for name in ("20260101T000000Z", "20260102T000000Z"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "validation_summary.json").write_text("{}")
    (tmp_path / "20260103T000000Z").mkdir()  # no summary yet
    assert latest_run_dir(tmp_path) == tmp_path / "20260102T000000Z"


def test_page_without_runs_explains_what_to_do():
    at = _render(None)
    assert not at.exception
    assert "No run yet" in at.info[0].value


def test_page_shows_validation_cleaning_and_contract(secom_env):
    from foresight.flow import run_pipeline

    state = run_pipeline()
    at = _render(state.run_dir)
    assert not at.exception
    assert "PASS" in at.success[0].value
    assert [m.label for m in at.metric] == ["Runs", "Features kept", "Fail rate", "Missing cells"]
    assert at.metric[0].value == "150"


def test_page_shows_errors_for_a_failed_validation(secom_env):
    from foresight.data.secom import LABELS_FILE
    from foresight.flow import run_pipeline

    labels = Path(secom_env.paths.data_raw_dir) / LABELS_FILE
    labels.write_text(labels.read_text().replace('-1 "', '7 "', 1))
    state = run_pipeline()
    at = _render(state.run_dir)
    assert not at.exception
    assert "ERROR" in at.error[0].value
