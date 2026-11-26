"""My activity (Phase 8.6): the signed-in person's own runs and chat questions."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import store, ui
from app.runs import local_time
from foresight.settings import Settings


def render(settings: Settings, viewer) -> None:
    ui.page_header("My activity")
    who = viewer.name or viewer.email
    st.caption(f"{who}" + (f" · {viewer.email}" if viewer.email and viewer.name else "") +
               f" · {'developer' if viewer.developer else 'user'}"
               + (" · local checkout: everything run here counts as yours" if viewer.local
                  else ""))
    runs = _runs(settings, viewer.email)
    questions = store.questions_by(settings, viewer.email)
    finished = [r for r in runs if r["status"] == "success"]
    ui.kpis([
        ("Analyses started", str(sum("started" in r["you"] for r in runs)), None,
         "Analyses you started from the New analysis page"),
        ("Completed", str(len(finished)), None,
         "Of the analyses you started, resumed or stopped"),
        ("Questions asked", str(len(questions)), None, "Questions to Ask Foresight"),
    ])

    # Phase 8.7: runs and questions in tabs, so the page fits one screen
    runs_tab, questions_tab = st.tabs([f"Your analyses ({len(runs)})",
                                       f"Your questions ({len(questions)})"])
    with runs_tab, st.container(key="card-my-runs"):
        if runs:
            ui.table(pd.DataFrame(runs), max_rows=10)
            st.caption("Open a successful analysis's results by choosing it under \"Analysis "
                       "shown\" "
                       "in the sidebar.")
        else:
            st.caption("No analyses yet. Start one on the New analysis page.")

    with questions_tab, st.container(key="card-my-questions"):
        if questions:
            ui.table(pd.DataFrame([{
                "asked": local_time(q.get("time"), "%d %b, %H:%M"),
                "about": "all analyses" if q.get("run") == store.ALL_RUNS
                else _name(q.get("run")),
                "question": q.get("question", ""),
                "answer": "not found" if q.get("refused") else "answered",
            } for q in questions]), max_rows=10)
        else:
            st.caption("No questions yet. Ask one on the Ask Foresight page.")


def _runs(settings: Settings, email: str) -> list[dict]:
    """Runs the person started (the registry keeps them after the run folder is pruned) and
    the runs on this server they resumed or stopped."""
    rows: dict[str, dict] = {}
    history, _, _ = store.run_history(settings)
    if not history.empty and "started_by" in history:
        mine = history[(history["started_by"].fillna("") == email)
                       & (history["source"] != "reference")]
        for r in mine.to_dict("records"):
            rows[r["run_id"]] = {"started": r["started_at"], "dataset": r["dataset"],
                                 "status": r["status"], "you": ["started"]}
    for p in store.runs_of(settings, email):
        row = rows.setdefault(p.run_id, {"started": p.started_at, "dataset": p.dataset,
                                         "status": p.effective_status(), "you": []})
        row["status"] = p.effective_status()  # the run folder is the live state
        for did, yes in (("started", p.started_by == email), ("resumed", email in p.resumed_by),
                         ("stopped", p.stopped_by == email)):
            if yes and did not in row["you"]:
                row["you"].append(did)
    ordered = sorted(rows.items(), key=lambda kv: kv[1]["started"] or "", reverse=True)
    return [{"analysis": _name(run_id), "started": local_time(r["started"], "%d %b, %H:%M")
             if r["started"] else "", "dataset": r["dataset"], "status": r["status"],
             "you": ", ".join(r["you"])}
            for run_id, r in ordered]


def _name(run_id: str | None) -> str:
    """Phase 8.10: "Analysis 12", not the run id (the reference run's id included)."""
    numbers = store.analysis_numbers()
    if run_id in numbers:
        return f"Analysis {numbers[run_id]}"
    return "Reference analysis" if run_id else ""
