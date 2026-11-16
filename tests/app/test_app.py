from pathlib import Path

from streamlit.testing.v1 import AppTest

from foresight import jobs
from foresight.flow import run_pipeline

APP = str(Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py")


def _app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def test_app_loads_with_environment_badge():
    at = _app()
    assert not at.exception
    assert at.title[0].value == "Run Pipeline"
    assert any("Environment: local" in md.value for md in at.sidebar.markdown)


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
    assert any("data_contract" in md.value and "PASS" in md.value for md in at.markdown)
    assert any("Data Analyst crew" in md.value for md in at.markdown)
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
    assert any("stopped" in err.value and "raw_label_values" in err.value for err in at.error)
    failed = at.dataframe[0].value
    assert "raw_label_values" in set(failed["name"])
