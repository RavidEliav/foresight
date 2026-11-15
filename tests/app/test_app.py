from pathlib import Path

from streamlit.testing.v1 import AppTest

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
    at = _app()
    at.text_input(key="passcode").input("wrong")
    at.button(key="run").click().run()
    assert any("Not authorized" in err.value for err in at.error)


def test_correct_passcode_runs_mocked_pipeline(monkeypatch):
    monkeypatch.setenv("RUN_PASSCODE", "s3cret")
    at = _app()
    at.text_input(key="passcode").input("s3cret")
    at.button(key="run").click().run()
    assert not at.exception
    assert not at.error
    assert any("data_contract" in md.value for md in at.markdown)
