"""Users & access (developer only, Phase 8.6): waiting requests, adding people, roles."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import store, ui
from app.runs import local_time
from foresight.settings import Settings

ROLE_LABELS = {"user": "User", "developer": "Developer"}
NOTICE = "access_notice"


def render(settings: Settings, viewer) -> None:
    ui.page_header("Users & access")
    st.caption("Who may sign in to this environment"
               f" ({settings.environment}). Each environment keeps its own list; the "
               "developers set in FORESIGHT_DEVELOPERS are always approved.")
    if notice := st.session_state.pop(NOTICE, None):
        st.success(notice, icon=":material/check_circle:")
    try:
        everyone = store.accounts(settings)
    except Exception as exc:  # the database did not answer
        ui.friendly_error(f"The account list could not be read: {type(exc).__name__}. "
                          "Try again in a minute.")
        return

    waiting = [a for a in everyone if a.status == "pending"]
    # Phase 8.7: requests and the add form side by side, so the page fits one screen
    left, right = st.columns(2, gap="medium")
    with left, st.container(key="card-requests", height="stretch"):
        ui.label(f"Waiting requests ({len(waiting)})")
        if not waiting:
            st.caption("No one is waiting. New requests also arrive by email.")
        for account in waiting:
            _request(settings, viewer, account)

    with right, st.container(key="card-add-user", height="stretch"):
        ui.label("Add a person")
        st.caption("They get access at once: they only need to sign in with this Google "
                   "account.")
        with st.form("add-user", clear_on_submit=True, border=False):
            left, right = st.columns([3, 1])
            email = left.text_input("Google account email", key="add-email",
                                    placeholder="name@gmail.com")
            role = right.selectbox("Role", list(ROLE_LABELS), format_func=ROLE_LABELS.get,
                                   key="add-role")
            if st.form_submit_button("Add", type="primary", icon=":material/person_add:"):
                try:
                    added = store.add_account(settings, email, role, viewer.email)
                except ValueError as exc:
                    ui.friendly_error(str(exc).capitalize() + ".")
                else:
                    st.session_state[NOTICE] = f"{added.email} can now sign in as a " \
                                               f"{ROLE_LABELS[added.role].lower()}."
                    st.rerun()

    _accounts(settings, viewer, everyone)


def _request(settings: Settings, viewer, account) -> None:
    with st.container(border=True):
        st.markdown(f"**{account.name or account.email}** · {account.email}  \n"
                    f":gray[asked {local_time(account.requested_at)}]")
        if account.message:
            st.markdown(f"> {account.message}")
        approve, deny, _ = st.columns([1, 1, 4])
        if approve.button("Approve", key=f"approve-{account.email}", type="primary",
                          icon=":material/check:"):
            store.decide(settings, account.email, True, viewer.email)
            st.session_state[NOTICE] = f"{account.email} is approved and can sign in now."
            st.rerun()
        if deny.button("Deny", key=f"deny-{account.email}", icon=":material/close:"):
            store.decide(settings, account.email, False, viewer.email)
            st.session_state[NOTICE] = f"The request of {account.email} is denied."
            st.rerun()


def _accounts(settings: Settings, viewer, everyone: list) -> None:
    developers = [{"email": e, "name": "", "role": "developer", "status": "always approved",
                   "decided": "", "by": "FORESIGHT_DEVELOPERS"} for e in settings.auth.developers]
    stored = [{"email": a.email, "name": a.name, "role": a.role, "status": a.status,
               "decided": local_time(a.decided_at, "%d %b, %H:%M") if a.decided_at else "",
               "by": a.decided_by or ""}
              for a in everyone if a.status != "pending"
              and a.email not in settings.auth.developers]
    with st.container(key="card-accounts"):
        ui.label(f"Accounts ({len(developers) + len(stored)})")
        ui.table(pd.DataFrame(developers + stored), max_rows=30)
        where = "Supabase" if store.accounts_backend(settings) == "supabase" else \
            "the runs folder"
        st.caption(f"Stored in {where}.")
        if not stored:
            return
        emails = [row["email"] for row in stored]
        left, middle, right = st.columns([3, 1, 2], vertical_alignment="bottom")
        chosen = left.selectbox("Change an account", emails, key="manage-email")
        current = next(a for a in everyone if a.email == chosen)
        role = middle.selectbox("Role", list(ROLE_LABELS), format_func=ROLE_LABELS.get,
                                index=list(ROLE_LABELS).index(current.role),
                                key=f"manage-role-{chosen}")
        with right:
            save, remove = st.columns(2)
            if save.button("Save role", key="save-role", disabled=role == current.role
                           and current.status == "approved"):
                if current.status == "approved":
                    store.set_role(settings, chosen, role, viewer.email)
                else:  # a denied account: saving approves it with this role
                    store.add_account(settings, chosen, role, viewer.email)
                st.session_state[NOTICE] = f"{chosen} is now a {ROLE_LABELS[role].lower()}."
                st.rerun()
            if remove.button("Remove", key="remove-account", icon=":material/person_remove:"):
                store.remove_account(settings, chosen)
                st.session_state[NOTICE] = (f"{chosen} no longer has access (within a "
                                            "minute for an open session).")
                st.rerun()
