"""Run Pipeline page: choose the data, start a background run, follow it live, see past runs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from app import store, ui
from foresight.progress import ACTIVE, RunProgress
from foresight.settings import Settings

SECOM = "SECOM (UCI, built in)"
UPLOAD = "Upload a CSV"
SCENARIO = "Scenario (synthetic)"
STATUS_TEXT = {"queued": "is starting", "running": "is running", "success": "completed",
               "failed": "stopped", "timeout": "was stopped by the time limit",
               "interrupted": "was interrupted", "stopped": "was stopped"}
NEW_RUN_KEY = "new_run"  # read by the sidebar run selector


def render(settings: Settings, results_page=None) -> None:
    ui.page_header("Run Pipeline")
    st.caption("Validate the data, analyze it, investigate failures and write the report. "
               "Runs continue in the background: you can refresh or leave this page.")

    with st.container(key="card-launch"):
        ui.label("Start a run")
        source = st.radio("Dataset", [SECOM, UPLOAD, SCENARIO], key="source", horizontal=True)
        upload = scenario = None
        if source == SCENARIO:
            scenario = _scenario_inputs()
        if source == UPLOAD:
            upload = st.file_uploader("CSV file", type=["csv"], key="upload")
            st.caption("Columns: `timestamp` (dd/mm/yyyy HH:MM:SS or ISO), `label` (-1 pass, "
                       "1 fail) and the 590 sensor columns in SECOM order. The file goes "
                       "through the same Data Contract checks as the built-in data.")
            template = store.upload_template(settings)
            if template is not None:
                st.download_button("Download a template (SECOM in this format)", template,
                                   file_name="secom_upload_format.csv", mime="text/csv")
        if st.button("Run pipeline", key="run", type="primary"):
            _start(settings, source, upload, scenario)

    watched = st.session_state.get("watch_run")
    active = store.active_run(settings) or _continuable(settings)
    run_id = watched or (active.run_id if active else None)
    if run_id:
        st.session_state["watch_run"] = run_id  # keep showing it after it finishes
        st.divider()
        _show_run(settings, run_id, results_page)
    _history(settings)


def _scenario_inputs() -> dict:
    """Scenario Lab: which synthetic change, how strong, and the seed that makes it
    reproducible."""
    kinds = store.scenario_kinds()
    kind = st.selectbox("Scenario", list(kinds), format_func=lambda k: kinds[k][0],
                        key="scenario_kind", width=360)
    title, description, default, _ = kinds[kind]
    st.caption(f"{description} **Only the training period changes**: the test period stays "
               "the original SECOM data, so every metric is computed on real runs. The run is "
               "labeled SYNTHETIC everywhere.")
    left, right, _ = st.columns([2, 1, 2])
    if kind == "sensor_outage":
        intensity = left.slider("Share of the training period without data", 0.1, 0.6,
                                default, 0.05, key=f"intensity-{kind}")
    else:
        intensity = left.slider("Strength (standard deviations)", 0.25, 4.0, default, 0.25,
                                key=f"intensity-{kind}")
    seed = right.number_input("Seed", 0, 9999, 7, key="scenario_seed",
                              help="The same seed gives the same synthetic data and sensors.")
    return {"kind": kind, "intensity": float(intensity), "seed": int(seed)}


def _start(settings: Settings, source: str, upload, scenario=None) -> None:
    if source == UPLOAD and upload is None:
        ui.friendly_error("Choose a CSV file to upload first.")
        return
    try:
        run_id = store.start_run(settings, upload.getvalue() if upload else None,
                                 upload.name if upload else None,
                                 scenario if source == SCENARIO else None, ui.user_email())
    except store.RunLimitError as exc:
        st.warning(str(exc), icon=":material/hourglass_top:")
        return
    st.session_state["watch_run"] = run_id


def _continuable(settings: Settings) -> RunProgress | None:
    """After a restart nothing is watched any more: show the newest run if it can continue."""
    runs = store.all_runs(settings)
    return runs[0] if runs and runs[0].can_continue else None


def _continue(settings: Settings, run_id: str) -> None:
    try:
        store.resume_run(settings, run_id, ui.user_email())
    except store.RunLimitError as exc:
        st.warning(str(exc), icon=":material/hourglass_top:")
        return
    st.session_state["watch_run"] = run_id
    st.rerun()


def _show_run(settings: Settings, run_id: str, results_page) -> None:
    run_dir = store.run_folder(settings, run_id)
    progress = store.progress(run_dir)
    if progress is None:
        return
    if progress.effective_status() in ACTIVE:
        _live(settings, str(run_dir))
    else:
        _render_progress(progress, run_dir, results_page,
                         on_continue=lambda: _continue(settings, run_id))


STOP_ERROR = "stop_error"


def _stop(settings: Settings, run_id: str) -> None:
    """Button callback: ask the running run to stop (Phase 8.5); it can be resumed
    afterwards. It runs before the redraw, so "Stopping" shows at once."""
    try:
        store.stop_run(settings, run_id, ui.user_email())
    except store.RunLimitError as exc:  # it finished in the meantime
        st.session_state[STOP_ERROR] = str(exc)


@st.fragment(run_every=2)
def _live(settings: Settings, run_dir: str) -> None:
    progress = store.progress(Path(run_dir))
    if progress is None:
        return
    _render_progress(progress, Path(run_dir))
    if progress.effective_status() in ACTIVE:
        if store.stop_requested(Path(run_dir)):
            st.caption("Stopping the run: it records what it has finished and stops within a "
                       "few seconds.")
        else:
            st.button("Stop run", key="stop", icon=":material/stop_circle:", on_click=_stop,
                      args=(settings, progress.run_id))
            if error := st.session_state.pop(STOP_ERROR, None):
                ui.friendly_error(error)
            st.caption("Stopping keeps the stages that have finished, so the run can be resumed "
                       "later. You can then start a different run.")
    if progress.effective_status() not in ACTIVE:
        if progress.status == "success":
            st.session_state[NEW_RUN_KEY] = progress.run_id
        st.rerun()


GATE_NAMES = {"data_contract": "Data Contract", "features_present": "Features",
              "evidence_present": "Evidence"}


def _render_progress(progress: RunProgress, run_dir: Path, results_page=None,
                     on_continue=None) -> None:
    from app.messages import explain_failure
    from app.runs import local_time

    status = progress.effective_status()
    took = _minutes(progress)
    message = (f"Run {STATUS_TEXT.get(status, status)} · {progress.dataset} · started "
               f"{local_time(progress.started_at)}"
               + (f" · {took} min" if took is not None and status not in ACTIVE else ""))
    if status in ACTIVE:
        current = progress.current
        st.info(message + (f" · now: {current.label}" if current else ""),
                icon=":material/progress_activity:")
    elif status == "success":
        st.success(message, icon=":material/check_circle:")
    else:
        reasons, hint = explain_failure(progress, _test_fraction())
        text = f"{message}\n\n" + "\n".join(f"- {r}" for r in reasons)
        if status == "interrupted":
            st.warning(text, icon=":material/pause_circle:")
        elif status == "stopped":
            st.warning(text, icon=":material/stop_circle:")
        else:
            ui.friendly_error(text)
        if hint:
            st.info(hint, icon=":material/lightbulb:")
        if on_continue is not None and progress.can_continue:
            done = sum(s.reusable for s in progress.stages)
            reused = f"the {done} finished stage{'s' if done != 1 else ''}" if done else \
                "nothing (no stage had finished)"
            if st.button("Resume run", key="continue", type="primary",
                         icon=":material/play_circle:"):
                on_continue()
            st.caption(f"Resume reuses {reused} and runs the rest. It counts toward the "
                       "hourly run limit.")

    from app.stepper import stepper_html

    st.html(stepper_html(progress))
    if progress.gates:
        st.markdown("Gates: " + " ".join(
            f":{ui.STATUS_COLORS.get(g['status'], 'gray')}-badge["
            f"{GATE_NAMES.get(g['gate'], g['gate'])}: {g['status']}]" for g in progress.gates))

    if status == "success":
        if results_page is not None:
            st.page_link(results_page, label="See the results, starting with Data Quality",
                         icon=":material/verified:")
    elif status not in ACTIVE and ui.developer():
        with st.expander("Technical details"):
            if progress.failure_reason:
                st.code(progress.failure_reason, language=None, wrap_lines=True)
            _show_failed_checks(run_dir)


def _test_fraction() -> float:
    from foresight.settings import load_settings

    return load_settings().analytics.test_fraction


def _show_failed_checks(run_dir: Path) -> None:
    summary = store.read_json(run_dir, "validation_summary.json")
    if not summary:
        return
    failed = [c for c in summary["checks"] if c["status"] != "PASS"]
    if failed:
        st.markdown("**Data checks that did not pass**")
        ui.table(pd.DataFrame(failed)[["status", "name", "message"]])


def _history(settings: Settings) -> None:
    from app.messages import explain_failure
    from app.runs import local_time

    runs = store.all_runs(settings)
    if not runs:
        return
    developer = ui.developer()
    with st.expander(f"Run history ({len(runs)})"):
        rows = []
        for p in runs[:30]:
            manifest = store.read_json(store.run_folder(settings, p.run_id),
                                       store.MANIFEST) or {}
            usage = manifest.get("crew_usage", {})
            checks = manifest.get("report_checks") or {}
            status = p.effective_status()
            reason = ("" if status in (*ACTIVE, "success")
                      else " ".join(explain_failure(p, settings.analytics.test_fraction)[0]))
            row = {
                "started": local_time(p.started_at, "%d %b, %H:%M"),
                "dataset": p.dataset,
                "status": status,
                "minutes": _minutes(p),
                "report checks": f"{checks.get('PASS', 0)} PASS" if checks else "",
                "why it stopped": reason,
            }
            if developer:  # technical details: tokens and who started the run
                row["tokens"] = sum(u.get("total_tokens", 0) for u in usage.values()) or None
                row["started by"] = p.started_by or "command line"
            rows.append(row)
        ui.table(pd.DataFrame(rows), max_rows=30)


def _minutes(p: RunProgress) -> float | None:
    end = p.finished_at or (p.updated_at if p.effective_status() in ACTIVE else None)
    if end is None:
        return None
    start = datetime.fromisoformat(p.started_at)
    return round((datetime.fromisoformat(end) - start).total_seconds() / 60, 1)
