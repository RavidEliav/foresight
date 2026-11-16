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
UNLOCKED = "chat_unlocked"


def render(run_dir: Path | None, settings: Settings) -> None:
    st.title("Ask Foresight")
    if run_dir is None:
        no_run("report to ask about")
        return
    st.caption(f"{run_label(run_dir)} · answers come only from this run's reports and cite "
               "them; anything else gets \"Not found in this run's artifacts.\"")

    if not st.session_state.get(UNLOCKED):
        _unlock(settings)
        return

    history: list[dict] = st.session_state.setdefault("chat", {}).setdefault(str(run_dir), [])
    for item in history:
        _show(item)

    picked = st.pills("Examples", EXAMPLES, key=f"examples-{len(history)}",
                      label_visibility="collapsed")
    question = st.chat_input("Ask about this run") or picked
    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"), st.spinner("Searching this run's reports..."):
            item = _ask(question, run_dir, settings)
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


def _ask(question: str, run_dir: Path, settings: Settings) -> dict | None:
    from foresight.rag.chat import ask, log_answer

    try:
        result = ask(question, run_dir, settings)
    except Exception as exc:  # friendly message, never a stack trace
        ui.friendly_error(f"The question could not be answered: {exc}")
        return None
    log_answer(settings, run_dir, result)
    return result.model_dump()


def _show(item: dict) -> None:
    with st.chat_message("user"):
        st.markdown(item["question"])
    with st.chat_message("assistant"):
        st.markdown(item["answer"])
        if item["refused"]:
            st.caption(f"Why: {item['reason']}")
        if item["sources"]:
            with st.expander(f"Sources ({len(item['sources'])})"):
                for s in item["sources"]:
                    st.markdown(f"**{s['file']} § {s['section']}** · similarity {s['score']:.2f}")
                    st.caption(s["text"])
