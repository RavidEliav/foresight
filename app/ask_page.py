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
                "most important in several runs?", "Did the data pass the Data Contract in "
                "every run?"]
SCOPES = ["This run", "All runs"]


def render(run_dir: Path | None, settings: Settings) -> None:
    ui.page_header("Ask Foresight")
    if run_dir is None:
        no_run("report to ask about")
        return
    from app.store import ALL_RUNS

    if opened := st.session_state.get("chat_open"):  # a question from the sidebar: its scope
        st.session_state["chat_scope"] = SCOPES[1] if opened.get("run") == ALL_RUNS \
            else SCOPES[0]
    st.session_state.setdefault("chat_scope", SCOPES[0])
    scope = st.segmented_control("Scope", SCOPES, key="chat_scope",
                                 label_visibility="collapsed") or SCOPES[0]
    every = scope == "All runs"
    if every:
        runs = "All recorded runs" if ui.developer() else "Your runs and the reference run"
        st.caption(f"{runs} · answers come only from the runs' reports, say which run "
                   "each statement is about and cite it; anything else gets \"Not found in the "
                   "recorded runs.\"")
    else:
        st.caption(f"{run_label(run_dir)} · answers come only from this run's reports and cite "
                   "them; anything else gets \"Not found in this run's artifacts.\"")

    key = "all_runs" if every else str(run_dir)
    history: list[dict] = st.session_state.setdefault("chat", {}).setdefault(key, [])
    opened = st.session_state.pop("chat_open", None)  # picked in the sidebar's history
    if opened and opened.get("run") == (ALL_RUNS if every else run_dir.name) and (
            not history or history[-1]["question"] != opened["question"]):
        history.append({**opened, "from_history": True})
    # the conversation scrolls in its own box (its height follows the window, ui.CSS), so the
    # title, the scope and the question bar stay in place
    log = st.container(height=400, key="chat-log", border=False)
    with log:
        for item in history:
            _show(item)
        if not history:
            st.caption("Ask a question below, or pick an example.")

    turn = st.session_state.setdefault("example_turn", 0)
    # the examples sit right above the question bar: on a computer both in one box under the
    # conversation (a chat input inside a container is not pinned to the window's bottom); on
    # a phone both pinned to the bottom of the screen (Streamlit's bottom area, st.bottom)
    with st.bottom if ui.phone() else st.container(), \
            st.container(key="ask-bottom", gap="small"):
        picked = st.pills("Examples", EXAMPLES_ALL if every else EXAMPLES,
                          key=f"examples-{scope}-{turn}", label_visibility="collapsed")
        prompt = "Ask about all runs" if every else "Ask about this run"
        question = st.chat_input(prompt) or picked
    if picked:
        st.session_state["example_turn"] = turn + 1  # use a picked example only once
    if question:
        with log, st.chat_message("user"):
            st.markdown(question)
        with log, st.chat_message("assistant", avatar=ui.LOGO_IMAGE), \
                st.spinner("Searching all runs' reports..." if every
                           else "Searching this run's reports..."):
            item = _ask(question, None if every else run_dir, settings)
        if item:
            history.append(item)
            st.rerun()


def _ask(question: str, run_dir: Path | None, settings: Settings) -> dict | None:
    """``run_dir`` None: a question about all runs. Logged with who asked (Phase 8.6)."""
    from app import store

    try:
        if run_dir is None:  # a user's question covers their own runs and the reference run
            return store.ask_all(question, settings, ui.user_email(), store.visible_run_ids(
                settings, None if ui.developer() else ui.user_email()))
        return store.ask(question, run_dir, settings, ui.user_email())
    except Exception as exc:  # friendly message, never a stack trace; the store logs it
        from foresight.utils.logging import redact

        ui.friendly_error(f"The question could not be answered: {redact(exc)}")
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
        if item["sources"] and ui.developer():  # technical details (Phase 8.6)
            with st.expander(f"Sources ({len(item['sources'])})"):
                for s in item["sources"]:
                    if isinstance(s, str):  # logged answers keep "file § section (score)"
                        st.markdown(f"**{s}**")
                        continue
                    run = f"{s['run']} · " if s.get("run") else ""
                    st.markdown(f"**{run}{s['file']} § {s['section']}** · similarity "
                                f"{s['score']:.2f}")
                    st.caption(s["text"])
