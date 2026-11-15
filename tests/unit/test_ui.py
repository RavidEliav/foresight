from app.ui import passcode_ok
from foresight.settings import load_settings


def test_runs_disabled_without_configured_passcode():
    assert passcode_ok(load_settings(), "") is False
    assert passcode_ok(load_settings(), "anything") is False


def test_passcode_must_match(monkeypatch):
    monkeypatch.setenv("RUN_PASSCODE", "s3cret")
    settings = load_settings()
    assert passcode_ok(settings, "s3cret") is True
    assert passcode_ok(settings, "wrong") is False
