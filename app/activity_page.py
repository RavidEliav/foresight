"""My activity (Phase 8.6): the signed-in person's own runs and chat questions. A developer can
choose another person and see theirs (Phase 8.10)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import store, ui
from app.runs import local_time
from foresight.settings import Settings


def render(settings: Settings, viewer) -> None:
    ui.page_header("My activity")
    email, name, role = _person(settings, viewer)
    mine = email == viewer.email
    st.caption((name or email) + (f" · {email}" if email and name else "") + f" · {role}"
               + (" · local checkout: everything run here counts as yours"
                  if viewer.local and mine else ""))
    runs = _runs(settings, email)
    questions = store.questions_by(settings, email)
    finished = [r for r in runs if r["status"] == "success"]
    whose = "Your" if mine else "Their"
    ui.kpis([
        ("Analyses started", str(sum("started" in r["by"] for r in runs)), None,
         "Analyses started from the New analysis page"),
        ("Completed", str(len(finished)), None,
         "Of the analyses started, resumed or stopped"),
        ("Questions asked", str(len(questions)), None, "Questions to Ask Foresight"),
    ])

    # Phase 8.7: runs and questions in tabs, so the page fits one screen
    runs_tab, questions_tab = st.tabs([f"{whose} analyses ({len(runs)})",
                                       f"{whose} questions ({len(questions)})"])
    with runs_tab, st.container(key="card-my-runs"):
        if runs:
            ui.table(pd.DataFrame(runs).rename(columns={"by": "you" if mine else "they"}),
                     max_rows=10)
            st.caption("Open a successful analysis's results by choosing it under \"Analysis "
                       "shown\" in the sidebar.")
        else:
            st.caption("No analyses yet." + (" Start one on the New analysis page."
                                             if mine else ""))

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
            st.caption("No questions yet." + (" Ask one on the Ask Foresight page."
                                              if mine else ""))


def _person(settings: Settings, viewer) -> tuple[str, str, str]:
    """Whose activity to show (email, name, role): the viewer's own, or for a developer the
    person chosen from the accounts."""
    own = (viewer.email, viewer.name, "developer" if viewer.developer else "user")
    if not viewer.developer:
        return own
    try:
        others = {a.email: a for a in store.accounts(settings) if a.email != viewer.email}
    except Exception:  # the accounts could not be read: the viewer's own activity
        return own
    if not others:
        return own
    choices = [viewer.email, *sorted(others)]
    chosen = st.selectbox(
        "Activity of", choices, key="activity-person", filter_mode=ui.search(), width=360,
        format_func=lambda e: "You" if e == viewer.email else
        (f"{others[e].name} · {e}" if others[e].name else e),
        help="As a developer you can see anyone's analyses and questions.")
    if chosen == viewer.email:
        return own
    account = others[chosen]
    return account.email, account.name, account.role


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
                                 "status": r["status"], "by": ["started"]}
    for p in store.runs_of(settings, email):
        row = rows.setdefault(p.run_id, {"started": p.started_at, "dataset": p.dataset,
                                         "status": p.effective_status(), "by": []})
        row["status"] = p.effective_status()  # the run folder is the live state
        for did, yes in (("started", p.started_by == email), ("resumed", email in p.resumed_by),
                         ("stopped", p.stopped_by == email)):
            if yes and did not in row["by"]:
                row["by"].append(did)
    ordered = sorted(rows.items(), key=lambda kv: kv[1]["started"] or "", reverse=True)
    return [{"analysis": _name(run_id), "started": local_time(r["started"], "%d %b, %H:%M")
             if r["started"] else "", "dataset": r["dataset"], "status": r["status"],
             "by": ", ".join(r["by"])}
            for run_id, r in ordered]


def _name(run_id: str | None) -> str:
    """Phase 8.10: "Analysis 12", not the run id (the reference run's id included)."""
    numbers = store.analysis_numbers()
    if run_id in numbers:
        return f"Analysis {numbers[run_id]}"
    return "Reference analysis" if run_id else ""
