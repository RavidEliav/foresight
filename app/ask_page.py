"""Ask Foresight: questions about the selected run, answered only from its artifacts (§18.3)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app import ui
from app.runs import no_run, run_label
from foresight.settings import Settings

EXAMPLES = ["What is the model's test PR-AUC?", "Which sensors differ most between failing "
            "and passing runs?", "What are the hypotheses and how confident are they?",
            "Did the data pass the Data Contract validation?"]
EXAMPLES_ALL = ["How did the test PR-AUC differ between runs?", "Which sensors were among the "
                "most important in several runs?", "Which runs had warnings in their checks?"]
UNLOCKED = "chat_unlocked"
SCOPES = ["This run", "All runs"]


def render(run_dir: Path | None, settings: Settings) -> None:
    ui.page_header("Ask Foresight")
    if run_dir is None:
        no_run("report to ask about")
        return
    scope = st.segmented_control("Scope", SCOPES, default=SCOPES[0], key="chat_scope",
                                 label_visibility="collapsed") or SCOPES[0]
    every = scope == "All runs"
    if every:
        st.caption("All recorded runs · answers come only from the runs' reports, say which run "
                   "each statement is about and cite it; anything else gets \"Not found in the "
                   "recorded runs.\"")
    else:
        st.caption(f"{run_label(run_dir)} · answers come only from this run's reports and cite "
                   "them; anything else gets \"Not found in this run's artifacts.\"")

    if not st.session_state.get(UNLOCKED):
        _unlock(settings)
        return

    key = "all_runs" if every else str(run_dir)
    history: list[dict] = st.session_state.setdefault("chat", {}).setdefault(key, [])
    opened = st.session_state.pop("chat_open", None)  # picked in the sidebar's history
    if not every and opened and opened.get("run") == run_dir.name and (
            not history or history[-1]["question"] != opened["question"]):
        history.append({**opened, "from_history": True})
    for item in history:
        _show(item)

    turn = st.session_state.setdefault("example_turn", 0)
    picked = st.pills("Examples", EXAMPLES_ALL if every else EXAMPLES,
                      key=f"examples-{scope}-{turn}", label_visibility="collapsed")
    question = st.chat_input("Ask about all runs" if every else "Ask about this run") or picked
    if picked:
        st.session_state["example_turn"] = turn + 1  # use a picked example only once
    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant", avatar=ui.LOGO_IMAGE), \
                st.spinner("Searching all runs' reports..." if every
                           else "Searching this run's reports..."):
            item = _ask(question, None if every else run_dir, settings)
        if item:
            history.append(item)
            st.rerun()


def _unlock(settings: Settings) -> None:
    if not settings.run_passcode:
        st.info("The chat is disabled: RUN_PASSCODE is not configured.")
        return
    with st.form("unlock"):
        entered = st.text_input("Passcode", type="password", key="chat_passcode")
        if st.form_submit_button("Unlock the chat", type="primary"):
            if ui.passcode_ok(settings, entered):
                st.session_state[UNLOCKED] = True
                st.rerun()
            ui.friendly_error("Not authorized: wrong or missing passcode.")


def _ask(question: str, run_dir: Path | None, settings: Settings) -> dict | None:
    """``run_dir`` None: a question about all runs."""
    from app import store

    try:
        if run_dir is None:
            return store.ask_all(question, settings)
        return store.ask(question, run_dir, settings)
    except Exception as exc:  # friendly message, never a stack trace; the store logs it
        ui.friendly_error(f"The question could not be answered: {exc}")
        return None


def _show(item: dict) -> None:
    with st.chat_message("user"):
        st.markdown(item["question"])
    with st.chat_message("assistant", avatar=ui.LOGO_IMAGE):
        st.markdown(item["answer"])
        if item.get("from_history"):
            from app.runs import local_time

            st.caption(f"From the chat history, asked {local_time(item['time'])}")
        if item["refused"]:
            st.caption(f"Why: {item['reason']}")
        if item["sources"]:
            with st.expander(f"Sources ({len(item['sources'])})"):
                for s in item["sources"]:
                    if isinstance(s, str):  # logged answers keep "file § section (score)"
                        st.markdown(f"**{s}**")
                        continue
                    run = f"{s['run']} · " if s.get("run") else ""
                    st.markdown(f"**{run}{s['file']} § {s['section']}** · similarity "
                                f"{s['score']:.2f}")
                    st.caption(s["text"])
