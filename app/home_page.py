"""Home (Phase 8.10): where the app opens. What Foresight does, the analysis shown at a
glance (its key numbers and top finding), a clear way to start a new analysis, an analysis that
is running, and your recent analyses and questions."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app import store, ui
from app.runs import analysis_name, describe_run, local_time, read_json, run_help
from foresight.progress import ACTIVE
from foresight.settings import Settings

STATUS_WORDS = {"success": "completed", "failed": "stopped", "timeout": "stopped (time limit)",
                "interrupted": "interrupted", "stopped": "stopped", "running": "running",
                "queued": "starting"}


def render(settings: Settings, viewer, run_dir: Path | None, pages: dict) -> None:
    ui.page_header("Home")
    st.caption("Foresight finds failing production runs early, shows which sensors go with them "
               "and writes a cited engineering report, on the SECOM fab data.")
    user = None if viewer.developer else viewer.email
    with st.container(key="home-actions", horizontal=True, vertical_alignment="center"):
        if st.button("Start a new analysis", key="home-new", type="primary",
                     icon=":material/play_arrow:"):
            st.switch_page(pages["new"])
        if st.button("Ask Foresight", key="home-ask", icon=":material/forum:"):
            st.switch_page(pages["ask"])
    _running(settings, user, pages)
    if run_dir is not None:
        _glance(run_dir, latest=run_dir == next(iter(store.viewable_runs(settings, user)),
                                                None))
    finding = [("Top finding", lambda: _finding(run_dir, pages), "Top finding")] \
        if run_dir is not None else []
    recent = [[("Your recent analyses", lambda: _recent_analyses(settings, viewer), "Analyses")],
              [("Your recent questions", lambda: _recent_questions(settings, viewer),
                "Questions")]]
    if ui.phone():  # one screen: the top finding is the first tab of the card below
        ui.cards([finding, *recent] if finding else recent, "home")
        return
    if finding:
        _finding(run_dir, pages)
    ui.cards(recent, "home")


def _running(settings: Settings, user: str | None, pages: dict) -> None:
    """An analysis that is going: its name, step and a link to follow it."""
    active = store.active_run(settings)
    if active is None or (user is not None and not store.owns(active, user)):
        return
    folder = store.run_folder(settings, active.run_id)
    step = active.current.label if active.current else "starting"
    with st.container(key="home-running", horizontal=True, vertical_alignment="center"):
        st.info(f"**{analysis_name(folder)}** is running · now: {step}",
                icon=":material/progress_activity:", width="stretch")
        st.page_link(pages["new"], label="Follow it", icon=":material/arrow_forward:",
                     width="content")


def _glance(run_dir: Path, latest: bool) -> None:
    """The analysis shown: its headline numbers."""
    ui.label(f"{'Latest analysis' if latest else 'Analysis shown'} · {describe_run(run_dir)}")
    tiles = []
    risk = read_json(run_dir, "risk_summary.json")
    if risk:
        test = risk["test"][risk["recommended_ranking"]]
        if "fails_found" in test:
            tiles.append(("Failing runs caught", f"{test['fails_found']} of "
                          f"{test['fails_total']}", f"with {test['alarms']} alarms",
                          "Failing production runs in the test period that raised an alarm."))
        tiles.append(("Alarm precision", f"{test['precision_at_budget']:.1%}", "true alarms",
                      "Share of the alarms that were failing runs."))
    metrics = read_json(run_dir, "model_metrics.json")
    if metrics:
        tiles.append(("Model PR-AUC", f"{metrics['test_metrics']['pr_auc']:.3f}",
                      f"random {metrics['baseline_pr_auc']:.3f}",
                      "How well the model ranks failing runs above passing ones on the test "
                      "period (1 is perfect; random guessing scores the fail rate)."))
    eda = read_json(run_dir, "eda_summary.json")
    if eda:
        tiles.append(("Sensors that differ", str(eda["significant_features_q_below_0.05"]),
                      "failing vs passing", "Sensors whose values differ between failing and "
                      "passing runs (q < 0.05). An association, not a cause."))
    if tiles:
        ui.kpis(tiles)


def _finding(run_dir: Path, pages: dict) -> None:
    """The investigation's headline, and the way to the findings."""
    summary = store.investigation_summary(run_dir)
    with st.container(key="home-finding", horizontal=True, vertical_alignment="center"):
        if summary is not None:
            st.markdown(f"**Top finding.** {summary.headline}", help=run_help(run_dir))
        st.page_link(pages["findings"], label="Open the findings",
                     icon=":material/arrow_forward:", width="content")


def _recent_analyses(settings: Settings, viewer) -> None:
    runs = store.all_runs(settings) if viewer.developer else store.runs_of(settings,
                                                                          viewer.email)
    if not runs:
        st.caption("No analyses yet. The reference analysis, shown above, is a finished one: "
                   "start your own with Start a new analysis.")
        return
    for progress in runs[:4]:
        folder = store.run_folder(settings, progress.run_id)
        status = progress.effective_status()
        color = "green" if status == "success" else "blue" if status in ACTIVE else "orange"
        st.markdown(f"**{analysis_name(folder)}** · {progress.dataset} · "
                    f"{local_time(progress.started_at, '%d %b, %H:%M')} "
                    f":{color}-badge[{STATUS_WORDS.get(status, status)}]")


def _recent_questions(settings: Settings, viewer) -> None:
    questions = store.questions_by(settings, viewer.email)[:4] if viewer.email else []
    if not questions:
        st.caption("No questions yet. Ask Foresight answers from an analysis's reports, with "
                   "their sources.")
        return
    for q in questions:
        answer = ":gray-badge[not found]" if q.get("refused") else ":green-badge[answered]"
        when = local_time(q.get("time"), "%d %b, %H:%M") if q.get("time") else ""
        st.markdown(f"{q.get('question', '')} {answer} :gray[{when}]")
