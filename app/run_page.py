"""Run Pipeline page: choose the data, start a background run, follow it live, see past runs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from app import ui
from foresight import jobs
from foresight.progress import ACTIVE, RunProgress, load_progress
from foresight.settings import Settings

SECOM = "SECOM (UCI, built in)"
UPLOAD = "Upload a CSV"
STAGE_ICON = {"pending": ":material/radio_button_unchecked:", "running": ":material/pending:",
              "done": ":material/check_circle:", "failed": ":material/cancel:",
              "skipped": ":material/block:"}
STATUS_TEXT = {"queued": "is starting", "running": "is running", "success": "completed",
               "failed": "stopped", "timeout": "was stopped by the timeout guard",
               "interrupted": "was interrupted (the app restarted)"}
NEW_RUN_KEY = "new_run"  # read by the sidebar run selector


def render(settings: Settings, results_page=None) -> None:
    st.title("Run Pipeline")
    st.caption("Validate the data, analyze it, investigate failures and write the report. "
               "Runs continue in the background: you can refresh or leave this page.")
    if not settings.run_passcode:
        st.info("Pipeline runs are disabled: RUN_PASSCODE is not configured.")

    source = st.radio("Dataset", [SECOM, UPLOAD], key="source", horizontal=True)
    upload = None
    if source == UPLOAD:
        upload = st.file_uploader("CSV file", type=["csv"], key="upload")
        st.caption("Columns: `timestamp` (dd/mm/yyyy HH:MM:SS or ISO), `label` (-1 pass, 1 fail) "
                   "and the 590 sensor columns in SECOM order. The file goes through the same "
                   "Data Contract checks as the built-in data.")
        template = _template(settings)
        if template is not None:
            st.download_button("Download a template (SECOM in this format)", template,
                               file_name="secom_upload_format.csv", mime="text/csv")

    entered = st.text_input("Passcode", type="password", key="passcode")
    if st.button("Run pipeline", key="run", type="primary"):
        _start(settings, entered, source, upload)

    watched = st.session_state.get("watch_run")
    active = jobs.active_run(settings)
    run_id = watched or (active.run_id if active else None)
    if run_id:
        st.session_state["watch_run"] = run_id  # keep showing it after it finishes
        st.divider()
        _show_run(settings, run_id, results_page)
    _history(settings)


def _start(settings: Settings, entered: str, source: str, upload) -> None:
    if not ui.passcode_ok(settings, entered):
        ui.friendly_error("Not authorized: wrong or missing passcode.")
        return
    if source == UPLOAD and upload is None:
        ui.friendly_error("Choose a CSV file to upload first.")
        return
    try:
        run_id = jobs.start_run(settings, upload.getvalue() if upload else None,
                                upload.name if upload else None)
    except jobs.RunLimitError as exc:
        st.warning(str(exc), icon=":material/hourglass_top:")
        return
    st.session_state["watch_run"] = run_id


def _show_run(settings: Settings, run_id: str, results_page) -> None:
    run_dir = jobs.runs_dir(settings) / run_id
    progress = load_progress(run_dir)
    if progress is None:
        return
    if progress.effective_status() in ACTIVE:
        _live(str(run_dir))
    else:
        _render_progress(progress, run_dir, results_page)


@st.fragment(run_every=2)
def _live(run_dir: str) -> None:
    progress = load_progress(Path(run_dir))
    if progress is None:
        return
    _render_progress(progress, Path(run_dir))
    if progress.effective_status() not in ACTIVE:
        if progress.status == "success":
            st.session_state[NEW_RUN_KEY] = progress.run_id
        st.rerun()


def _render_progress(progress: RunProgress, run_dir: Path, results_page=None) -> None:
    status = progress.effective_status()
    message = f"Run {progress.run_id} {STATUS_TEXT.get(status, status)} · {progress.dataset}"
    if status in ACTIVE:
        current = progress.current
        st.info(message + (f" · now: {current.label}" if current else ""),
                icon=":material/progress_activity:")
    elif status == "success":
        st.success(message, icon=":material/check_circle:")
    elif status == "interrupted":
        st.warning(message + ". Start a new run.", icon=":material/warning:")
    else:
        ui.friendly_error(f"{message}: {progress.failure_reason}")

    for stage in progress.stages:
        crew = f" + {stage.crew}" if stage.crew else ""
        took = f" · {stage.seconds:.0f} s" if stage.seconds is not None else ""
        st.markdown(f"{STAGE_ICON[stage.status]} **{stage.label}**{crew}{took}")
    for gate in progress.gates:
        st.markdown(f"Gate **{gate['gate']}**: {gate['status']}")

    if status == "success":
        if results_page is not None:
            st.page_link(results_page, label="See the results, starting with Data Quality",
                         icon=":material/verified:")
    elif status not in ACTIVE:
        _show_failed_checks(run_dir)


def _show_failed_checks(run_dir: Path) -> None:
    path = run_dir / "validation_summary.json"
    if not path.exists():
        return
    summary = json.loads(path.read_text(encoding="utf-8"))
    failed = [c for c in summary["checks"] if c["status"] != "PASS"]
    if failed:
        st.markdown("**Data checks that did not pass**")
        st.dataframe(pd.DataFrame(failed)[["status", "name", "message"]], hide_index=True,
                     width="stretch")


def _history(settings: Settings) -> None:
    runs = jobs.list_runs(settings)
    if not runs:
        return
    with st.expander(f"Run history ({len(runs)})"):
        rows = []
        for p in runs[:30]:
            manifest = _manifest(jobs.runs_dir(settings) / p.run_id)
            usage = manifest.get("crew_usage", {})
            checks = manifest.get("report_checks") or {}
            rows.append({
                "run": p.run_id,
                "started (UTC)": p.started_at.replace("T", " ")[:16],
                "dataset": p.dataset,
                "status": p.effective_status(),
                "minutes": _minutes(p),
                "tokens": sum(u.get("total_tokens", 0) for u in usage.values()) or None,
                "report checks": f"{checks.get('PASS', 0)} PASS" if checks else "",
                "reason": p.failure_reason or "",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _manifest(run_dir: Path) -> dict:
    path = run_dir / "run_manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _minutes(p: RunProgress) -> float | None:
    end = p.finished_at or (p.updated_at if p.effective_status() in ACTIVE else None)
    if end is None:
        return None
    start = datetime.fromisoformat(p.started_at)
    return round((datetime.fromisoformat(end) - start).total_seconds() / 60, 1)


@st.cache_data(show_spinner=False)
def _template_bytes(raw_dir: str) -> bytes:
    from foresight.data.secom import load_raw, to_upload_csv

    return to_upload_csv(load_raw(Path(raw_dir)))


def _template(settings: Settings) -> bytes | None:
    from foresight.data.secom import DATA_FILE, LABELS_FILE

    raw_dir = settings.resolve(settings.paths.data_raw_dir)
    if not all((raw_dir / name).exists() for name in (DATA_FILE, LABELS_FILE)):
        return None
    return _template_bytes(str(raw_dir))
