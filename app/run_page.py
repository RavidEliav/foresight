"""Run Pipeline page: choose the data, start a background run, follow it live, see past runs."""

from __future__ import annotations

import contextlib
import errno
import time
from datetime import UTC, datetime, timedelta
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
PIN_MINUTES = 30  # an interrupted run stays at the top this long after it went quiet
STOP_WAIT_S = 30  # Run pipeline with other data: how long to wait for the current run to stop


def render(settings: Settings, results_page=None) -> None:
    ui.page_header("Run Pipeline")
    st.caption("Validate the data, analyze it, investigate failures, write the report.",
               help="Runs continue in the background: you can refresh or leave this page.")

    watched = st.session_state.get("watch_run")
    user = None if ui.developer() else ui.user_email()  # a user sees only their own runs
    active = store.active_run(settings) or _continuable(settings)
    someone_else = False
    if active and user is not None and not store.owns(active, user):
        someone_else = active.effective_status() in ACTIVE and not watched
        active = None
    run_id = watched or (active.run_id if active else None)
    run_dir = store.run_folder(settings, run_id) if run_id else None
    progress = store.progress(run_dir) if run_dir else None
    if progress is not None:
        st.session_state["watch_run"] = run_id  # keep showing it after it finishes

    _launch(settings, run_dir, progress)
    if someone_else:
        st.info("Someone else's run is in progress. You can start yours when it finishes, in a "
                "few minutes.", icon=":material/hourglass_top:")
    if error := st.session_state.pop(STOP_ERROR, None):
        ui.friendly_error(error)
    if progress is not None:
        _show_run(settings, run_dir, progress, results_page)
    _history(settings)


def _launch(settings: Settings, run_dir: Path | None, progress: RunProgress | None) -> None:
    """Start a run, with Stop run or Resume run beside Run pipeline. While a run is going,
    Run pipeline is grayed out for the same data; other data lights it up again, and it then
    stops the current run and starts the new one (one run at a time)."""
    running = progress is not None and progress.effective_status() in ACTIVE
    resumable = (progress is not None and not running and progress.status != "success"
                 and progress.can_continue)
    with st.container(key="card-launch"):
        ui.label("Start a run")
        if ui.phone():  # one line instead of three options on two lines
            source = st.selectbox("Dataset", [SECOM, UPLOAD, SCENARIO], key="source",
                                  label_visibility="collapsed", filter_mode=None)
        else:
            source = st.radio("Dataset", [SECOM, UPLOAD, SCENARIO], key="source",
                              horizontal=True, label_visibility="collapsed")
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
        same = running and _chosen(source, upload, scenario) == store.run_data(run_dir)
        with st.container(key="launch-actions", horizontal=True, vertical_alignment="center"):
            clicked = st.button(
                "Run pipeline", key="run", type="primary", disabled=same,
                help="A run with this data is in progress. Choose other data to stop it and "
                     "run that instead." if same else
                     "Stops the run in progress and starts this one." if running else None)
            if running:
                _stop_control(settings, progress, run_dir)
            elif resumable:
                done = sum(s.reusable for s in progress.stages)
                reused = (f"the {done} finished stage{'s' if done != 1 else ''}" if done
                          else "nothing (no stage had finished)")
                if st.button("Resume run", key="continue", icon=":material/play_circle:",
                             help=f"Resume reuses {reused} and runs the rest. It counts toward "
                                  "the hourly run limit."):
                    _continue(settings, progress.run_id)
    if clicked:
        if running:
            _replace(settings, progress.run_id, source, upload, scenario)
        else:
            _start(settings, source, upload, scenario)


def _chosen(source: str, upload, scenario: dict | None) -> tuple:
    """The data chosen in the launch card, comparable with ``store.run_data``."""
    if source == SCENARIO and scenario:
        return ("scenario", scenario["kind"], round(float(scenario["intensity"]), 4),
                int(scenario["seed"]))
    if source == UPLOAD:
        return ("upload", len(upload.getvalue()) if upload is not None else None)
    return ("secom",)


def _replace(settings: Settings, run_id: str, source: str, upload, scenario) -> None:
    """Run pipeline with other data while a run is going: stop it (its finished stages stay,
    so it can be resumed later), wait until it has stopped, then start the new one."""
    if source == UPLOAD and upload is None:
        ui.friendly_error("Choose a CSV file to upload first.")
        return
    with contextlib.suppress(store.RunLimitError):  # it finished in the meantime
        store.stop_run(settings, run_id, ui.user_email())
    with st.spinner("Stopping the run in progress, then starting the new one..."):
        deadline = time.monotonic() + STOP_WAIT_S
        while store.active_run(settings) is not None and time.monotonic() < deadline:
            time.sleep(1)
    _start(settings, source, upload, scenario)


def _scenario_inputs() -> dict:
    """Scenario Lab: which synthetic change, how strong, and the seed that makes it
    reproducible."""
    kinds = store.scenario_kinds()
    kind = st.selectbox("Scenario", list(kinds), format_func=lambda k: kinds[k][0],
                        key="scenario_kind", width=360, filter_mode=None)
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
    except OSError as exc:  # e.g. a full volume: a message, not a crash page
        ui.friendly_error(_not_written(exc, "start"))
        return
    st.session_state["watch_run"] = run_id
    st.rerun()  # show the new run


def _not_written(exc: OSError, action: str) -> str:
    if exc.errno == errno.ENOSPC:
        return (f"The run could not {action}: the server's storage is full. Please tell the "
                "developer.")
    return (f"The run could not {action}: the server could not write its files "
            f"({exc.strerror or type(exc).__name__}).")


def _continuable(settings: Settings) -> RunProgress | None:
    """After a restart nothing is watched any more: show the newest run if it can continue
    and went quiet less than PIN_MINUTES ago (later it waits in the history, with Resume)."""
    runs = store.all_runs(settings)
    if not runs or not runs[0].can_continue:
        return None
    quiet = datetime.now(UTC) - datetime.fromisoformat(runs[0].updated_at)
    return runs[0] if quiet < timedelta(minutes=PIN_MINUTES) else None


def _continue(settings: Settings, run_id: str) -> None:
    try:
        store.resume_run(settings, run_id, ui.user_email())
    except store.RunLimitError as exc:
        st.warning(str(exc), icon=":material/hourglass_top:")
        return
    except OSError as exc:
        ui.friendly_error(_not_written(exc, "resume"))
        return
    st.session_state["watch_run"] = run_id
    st.rerun()


def _show_run(settings: Settings, run_dir: Path, progress: RunProgress,
              results_page) -> None:
    if progress.effective_status() in ACTIVE:
        _live(str(run_dir))
    else:
        cause = (store.interruption_cause(settings, run_dir, progress)
                 if progress.effective_status() == "interrupted"
                 and not progress.failure_reason else None)
        _render_progress(progress, run_dir, results_page, cause=cause)


STOP_ERROR = "stop_error"


def _stop(settings: Settings, run_id: str) -> None:
    """Button callback: ask the running run to stop (Phase 8.5); it can be resumed
    afterwards. It runs before the redraw, so "Stopping" shows at once."""
    try:
        store.stop_run(settings, run_id, ui.user_email())
    except store.RunLimitError as exc:  # it finished in the meantime
        st.session_state[STOP_ERROR] = str(exc)


@st.fragment(run_every=2)
def _live(run_dir: str) -> None:
    progress = store.progress(Path(run_dir))
    if progress is None:
        return
    _render_progress(progress, Path(run_dir))
    if progress.effective_status() not in ACTIVE:  # Stop run becomes Resume run: redraw all
        if progress.status == "success":
            st.session_state[NEW_RUN_KEY] = progress.run_id
        st.rerun()


def _stop_control(settings: Settings, progress: RunProgress, run_dir: Path) -> None:
    """Stop run, beside Run pipeline; grayed out as "Stopping the run" once pressed."""
    if store.stop_requested(run_dir):
        st.button("Stopping the run...", key="stopping", icon=":material/stop_circle:",
                  disabled=True, help="It records what it has finished and stops within a "
                                      "few seconds.")
    else:
        st.button("Stop run", key="stop", icon=":material/stop_circle:", on_click=_stop,
                  args=(settings, progress.run_id),
                  help="Stopping keeps the stages that have finished, so the run can be "
                       "resumed later. You can then start a different run.")


GATE_NAMES = {"data_contract": "Data Contract", "features_present": "Features",
              "evidence_present": "Evidence"}


def _render_progress(progress: RunProgress, run_dir: Path, results_page=None,
                     cause: tuple[str, str] | None = None) -> None:
    from app.messages import explain_failure
    from app.runs import local_time

    status = progress.effective_status()
    took = _minutes(progress)
    message = (f"Run {STATUS_TEXT.get(status, status)} · {progress.dataset} · started "
               f"{local_time(progress.started_at)}"
               + (f" · {took} min" if took is not None and status not in ACTIVE else ""))
    if status in ACTIVE:
        current = progress.current
        # a phone leaves out the current stage: it is the highlighted row just below
        st.info(message + (f" · now: {current.label}" if current and not ui.phone() else ""),
                icon=":material/progress_activity:")
    elif status == "success":
        st.success(message, icon=":material/check_circle:")
    else:
        reasons, hint = explain_failure(progress, _test_fraction(), cause)
        text = f"{message}\n\n" + "\n".join(f"- {r}" for r in reasons)
        if status == "interrupted":
            st.warning(text, icon=":material/pause_circle:")
        elif status == "stopped":
            st.warning(text, icon=":material/stop_circle:")
        else:
            ui.friendly_error(text)
        if hint:
            st.info(hint, icon=":material/lightbulb:")

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

    developer = ui.developer()
    runs = store.all_runs(settings) if developer else store.runs_of(settings, ui.user_email())
    if not runs:
        return
    with st.expander(f"Run history ({len(runs)})" if developer else f"Your runs ({len(runs)})"):
        rows = []
        for p in runs[:30]:
            folder = store.run_folder(settings, p.run_id)
            manifest = store.read_json(folder, store.MANIFEST) or {}
            usage = manifest.get("crew_usage", {})
            checks = manifest.get("report_checks") or {}
            status = p.effective_status()
            cause = (store.interruption_cause(settings, folder, p)
                     if status == "interrupted" and not p.failure_reason else None)
            reason = ("" if status in (*ACTIVE, "success") else " ".join(
                explain_failure(p, settings.analytics.test_fraction, cause)[0]))
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
