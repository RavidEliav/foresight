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

st.set_page_config(page_title="Foresight", page_icon=str(ui.LOGO), layout="wide")
ui.apply_style()
settings = load_settings()
VIEW_KEY = "view_run"
PINNED_KEY = "view_pinned"  # True once the user picks a run in the sidebar


@st.cache_resource(show_spinner=False)
def _warm_embedding_model(models_dir: str) -> bool:
    """Once per server process: get the chat's embedding model ready in the background."""
    from app import store

    store.warm_up_chat(settings)
    return True


_warm_embedding_model(str(settings.resolve(settings.paths.models_dir)))


@st.cache_resource(show_spinner=False)
def _sync_registry(database_url: str) -> bool:
    """Once per server process: record the runs on this server in the Supabase registry."""
    from app import store

    store.sync_registry_in_background(settings)
    return True


_sync_registry(settings.database_url)


def run_pipeline_page() -> None:
    from app import run_page

    run_page.render(settings, DATA_QUALITY)


def _run_selector() -> Path | None:
    """Sidebar choice of the run shown on the result pages (newest successful run first)."""
    from app import store
    from app.run_page import NEW_RUN_KEY
    from app.runs import describe_run, run_details

    runs = store.viewable_runs(settings)
    if not runs:
        return None
    options = [str(p) for p in runs]
    if new := st.session_state.pop(NEW_RUN_KEY, None):  # a run just finished: show it
        st.session_state[VIEW_KEY] = str(store.run_folder(settings, new))
        st.session_state[PINNED_KEY] = False
    if not st.session_state.get(PINNED_KEY) or st.session_state.get(VIEW_KEY) not in options:
        st.session_state[VIEW_KEY] = options[0]  # follow the newest run until one is picked
    choice = st.sidebar.selectbox("Results shown", options, key=VIEW_KEY,
                                  format_func=lambda p: describe_run(Path(p)),
                                  help="The run whose results the pages show. Times are in "
                                       "your local time zone.",
                                  on_change=lambda: st.session_state.update({PINNED_KEY: True}))
    st.sidebar.caption(run_details(Path(choice)))
    return Path(choice)


def _latest(required: str) -> Path | None:
    run_dir = SELECTED
    from app import store

    return run_dir if run_dir is not None and store.exists(run_dir, required) else None


def data_quality_page() -> None:
    from app import data_quality

    data_quality.render(_latest("validation_summary.json"))


def eda_page() -> None:
    from app import eda_page as page

    page.render(_latest("eda_summary.json"))


def model_page() -> None:
    from app import model_page as page

    page.render(_latest("model_metrics.json"))


def report_page() -> None:
    from app import report_page as page

    page.render(_latest("anomaly_summary.json"))


def ask_page() -> None:
    from app import ask_page as page

    page.render(_latest("engineering_report.md"), settings)


def replay_page() -> None:
    from app import replay_page as page

    page.render(SELECTED)  # the page explains a run made before the risk ranking


def trends_page() -> None:
    from app import trends_page as page

    page.render(settings)


DATA_QUALITY = st.Page(data_quality_page, title="Data Quality", icon=":material/verified:",
                       url_path="data-quality")
ASK = st.Page(ask_page, title="Ask Foresight", icon=":material/forum:", url_path="ask")
PAGES = [
    st.Page(run_pipeline_page, title="Run Pipeline", icon=":material/play_arrow:", default=True),
    DATA_QUALITY,
    st.Page(eda_page, title="EDA & Insights", icon=":material/bar_chart:", url_path="eda"),
    st.Page(model_page, title="Model", icon=":material/model_training:", url_path="model"),
    st.Page(report_page, title="Investigation & Report", icon=":material/description:",
            url_path="report"),
    st.Page(replay_page, title="Line Replay", icon=":material/slow_motion_video:",
            url_path="replay"),
    st.Page(trends_page, title="Trends", icon=":material/trending_up:", url_path="trends"),
    ASK,
]
# Streamlit draws its own page menu above everything else in the sidebar; it is hidden so that
# the brand comes first and the menu is drawn with page links (ui.sidebar_nav).
navigation = st.navigation(PAGES, position="hidden")
ui.brand()
ui.environment_badge(settings)
ui.sidebar_nav(PAGES, navigation)
SELECTED = _run_selector()
ui.recent_questions(SELECTED, settings, ASK)
navigation.run()
