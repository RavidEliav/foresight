def test_the_style_block_survives_the_html_sanitizer():
    """st.html's sanitizer drops a whole <style> whose text holds a "<" (all styling is lost:
    found in a browser in Phase 8.6, where a comment said "Hi, <name>")."""
    from app.ui import STYLE

    body = STYLE.strip().removeprefix("<style>").removesuffix("</style>")
    assert "<" not in body  # (">" is fine: CSS uses it as the child combinator)


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


def test_recorded_failure_reasons_read_as_plain_language():
    """The registry keeps the technical reason; Trends lists it in plain words."""
    from app.messages import explain_reason

    assert explain_reason("failed", "features_present: test_fails: 4 failing runs in the test "
                          "period (minimum 5)", 0.25) == ("Not enough failing runs in the newest "
                                                          "25% of the runs (used to test the "
                                                          "model): found 4, need 5.")
    assert explain_reason("failed", "data_contract: raw_label_values: unexpected label values "
                          "[2]; raw_timestamps: 3 unreadable", 0.25) == (
        "Some labels are not -1 (pass) or 1 (fail). Some timestamps are missing or are not "
        "readable dates.")
    assert explain_reason("interrupted", None, 0.25).startswith("Stopped sending updates")
    assert explain_reason("interrupted", float("nan"), 0.25).startswith("Stopped sending")  # pd
    assert explain_reason("interrupted", "The app restarted while the run was going.",
                          0.25) == "The app restarted while the run was going."
    assert explain_reason("timeout", "stopped by the timeout guard after 1200 s", 0.25) \
        == "Took longer than the time limit and was stopped."


def test_times_are_shown_in_the_viewers_time_zone(monkeypatch):
    from zoneinfo import ZoneInfo

    from app import runs

    monkeypatch.setattr(runs, "local_zone", lambda: ZoneInfo("Asia/Jerusalem"))
    assert runs.local_time("2026-11-16T20:58:00+00:00") == "16 Nov 2026, 22:58"
    monkeypatch.setattr(runs, "local_zone", lambda: runs.UTC)
    assert runs.local_time("2026-11-16T20:58:00+00:00") == "16 Nov 2026, 20:58 UTC"


def test_table_columns_fit_their_header_and_longest_value():
    """Phase 8.7: no header or value cut off; long text and wide tables wrap instead."""
    import pandas as pd
    import streamlit as st

    from app import ui

    frame = pd.DataFrame({"stratified CV (optimistic)": [0.177, None], "id": ["a", "bbbbbb"]})
    widths = ui.column_widths(frame)
    assert widths["stratified CV (optimistic)"] > widths["id"]  # the header is the widest
    assert widths["id"] == int(7.4 * len("bbbbbb") + 30)
    percent = st.column_config.NumberColumn(format="percent")
    assert ui._formatted(0.0664, percent) == "6.6%"
    assert ui._formatted(0.08512, st.column_config.NumberColumn(format="%.3f")) == "0.085"
    assert ui._formatted(float("nan"), percent) == "" and ui._formatted("x", None) == "x"
