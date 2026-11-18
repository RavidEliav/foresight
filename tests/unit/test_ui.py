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


def test_failure_reasons_are_in_plain_language():
    from app.messages import explain_failure
    from foresight.progress import RunProgress

    progress = RunProgress(run_id="r", status="failed", gates=[
        {"gate": "data_contract", "status": "PASS", "messages": []},
        {"gate": "features_present", "status": "ERROR",
         "messages": ["test_fails: 4 failing runs in the test period (minimum 5)"]}])
    reasons, hint = explain_failure(progress, test_fraction=0.25)
    assert reasons == ["Not enough failing runs in the newest 25% of the runs (used to test "
                       "the model): found 4, need 5."]
    assert "longer period" in hint

    crashed = RunProgress(run_id="r", status="failed",
                          failure_reason="model stage error: disk full")
    assert explain_failure(crashed, 0.25)[0] == ["Something went wrong in the model step."]


def test_times_are_shown_in_the_viewers_time_zone(monkeypatch):
    from zoneinfo import ZoneInfo

    from app import runs

    monkeypatch.setattr(runs, "local_zone", lambda: ZoneInfo("Asia/Jerusalem"))
    assert runs.local_time("2026-11-16T20:58:00+00:00") == "16 Nov 2026, 22:58"
    monkeypatch.setattr(runs, "local_zone", lambda: runs.UTC)
    assert runs.local_time("2026-11-16T20:58:00+00:00") == "16 Nov 2026, 20:58 UTC"
