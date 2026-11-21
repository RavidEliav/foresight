"""Review an access request from the email's Approve / Deny link (Phase 8.6).

The link carries a signed token that names one waiting request, so it works without signing
in. Opening it decides nothing: the page asks for one click, so a mail scanner that opens
links cannot approve anyone.
"""

from __future__ import annotations

import streamlit as st

from app import store, ui
from app.runs import local_time
from foresight.settings import Settings

DONE = "review_done"


def render(settings: Settings, viewer) -> None:
    ui.page_header("Access request")
    if done := st.session_state.get(DONE):
        st.success(done, icon=":material/check_circle:")
        return
    request = store.review_request(settings, str(st.query_params.get("token", "")))
    if request is None:
        st.warning("This link does not work any more: the request was already decided, the "
                   "person asked again (a newer email has the current link), or the link "
                   "expired. Every request is on the Users & access page.",
                   icon=":material/link_off:")
        return
    wanted = str(st.query_params.get("action", "approve"))
    with st.container(key="card-review"):
        ui.label("Waiting for your decision")
        st.markdown(f"**{request.name or request.email}** · {request.email}  \n"
                    f":gray[asked {local_time(request.requested_at)} · environment "
                    f"{settings.environment}]")
        if request.message:
            st.markdown(f"> {request.message}")
        approve, deny, _ = st.columns([1, 1, 3])
        by = viewer.email if viewer is not None and viewer.email else "email link"
        if approve.button("Approve", key="review-approve", icon=":material/check:",
                          type="primary" if wanted == "approve" else "secondary"):
            store.decide(settings, request.email, True, by)
            st.session_state[DONE] = (f"Approved: {request.email} can now sign in with "
                                      "Google.")
            st.rerun()
        if deny.button("Deny", key="review-deny", icon=":material/close:",
                       type="primary" if wanted == "deny" else "secondary"):
            store.decide(settings, request.email, False, by)
            st.session_state[DONE] = f"Denied: {request.email} has no access."
            st.rerun()
