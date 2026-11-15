"""Foresight Streamlit app (entry point used by Railway and local runs)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import streamlit as st  # noqa: E402

from app import ui  # noqa: E402
from foresight.settings import load_settings  # noqa: E402

st.set_page_config(page_title="Foresight", page_icon=":material/insights:", layout="wide")
settings = load_settings()


def run_pipeline_page() -> None:
    st.title("Run Pipeline")
    st.caption("Validate SECOM data, analyze it, investigate failures and produce the report.")

    if not settings.run_passcode:
        st.info("Pipeline runs are disabled: RUN_PASSCODE is not configured.")
    entered = st.text_input("Passcode", type="password", key="passcode")
    if st.button("Run pipeline", key="run", type="primary"):
        if not ui.passcode_ok(settings, entered):
            ui.friendly_error("Not authorized: wrong or missing passcode.")
            return
        from foresight.flow import run_pipeline

        with st.status("Running pipeline...", expanded=True) as status:
            try:
                state = run_pipeline(settings)
            except Exception as exc:  # show a friendly message, never a stack trace
                status.update(label="Run failed", state="error")
                ui.friendly_error(f"The run could not complete: {exc}")
                return
            done = state.status == "success"
            status.update(label=f"Run {state.run_id} {'completed' if done else 'stopped'}",
                          state="complete" if done else "error", expanded=False)

        for gate in state.gates:
            st.write(f"Gate **{gate.gate}**: {gate.status.value}")
        if not done:
            ui.friendly_error(f"Stopped at a validation gate: {state.failure_reason}")
        st.page_link(DATA_QUALITY, label="See the Data Quality results",
                     icon=":material/verified:")


def data_quality_page() -> None:
    from app import data_quality

    data_quality.render(data_quality.latest_run_dir(settings.resolve(settings.paths.runs_dir)))


def eda_page() -> None:
    st.title("EDA & Insights")
    ui.coming_soon("Phase 2")


def model_page() -> None:
    st.title("Model")
    ui.coming_soon("Phase 2")


def report_page() -> None:
    st.title("Investigation & Report")
    ui.coming_soon("Phase 3")


st.sidebar.title("Foresight")
st.sidebar.caption("Semiconductor yield intelligence")
ui.environment_badge(settings)

DATA_QUALITY = st.Page(data_quality_page, title="Data Quality", icon=":material/verified:",
                       url_path="data-quality")
navigation = st.navigation(
    [
        st.Page(run_pipeline_page, title="Run Pipeline", icon=":material/play_arrow:",
                url_path="run", default=True),
        DATA_QUALITY,
        st.Page(eda_page, title="EDA & Insights", icon=":material/bar_chart:", url_path="eda"),
        st.Page(model_page, title="Model", icon=":material/model_training:", url_path="model"),
        st.Page(report_page, title="Investigation & Report", icon=":material/description:",
                url_path="report"),
    ]
)
navigation.run()
