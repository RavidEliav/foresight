"""Sign-in for the whole app (Phase 8.6): Google sign-in through ``st.login``, access requests,
roles, and the Foresight session rules.

- A session ends on Sign out, when the browser closes (the sign-in cookie is a session cookie)
  and after ``auth.idle_minutes`` without activity.
- Approved accounts use the app; the developers also see the developer view (technical
  details, Extended data, Trends, Users & access). Anyone else can ask for access.
- Without Google keys, a local checkout (and CI) opens as a local developer. On Railway the
  keys are required: without them nobody gets in.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from app import store, ui
from foresight.settings import Settings

VIEWER = "viewer"            # session key of the signed-in person (read by ui.developer)
CHECKED = "account_checked"  # (email, time, account): the access check, redone every minute
RECHECK_S = 60
SECRETS_ENV = "FORESIGHT_SECRETS_FILE"  # tests write the generated secrets here
REQUEST_SENT = "access_request_sent"


@dataclass(frozen=True)
class Viewer:
    email: str
    name: str
    role: str                # user or developer
    picture: str = ""
    issued_at: float = 0.0   # when Google issued the sign-in (the idle clock's key)
    local: bool = False      # no sign-in configured: a local checkout or CI

    @property
    def developer(self) -> bool:
        return self.role == "developer"

    @property
    def first_name(self) -> str:
        return (self.name or self.email.split("@")[0] or "there").split()[0]


@dataclass(frozen=True)
class Session:
    status: str              # ok, signed_out, no_access, unavailable, not_configured
    viewer: Viewer | None = None
    account: object = None   # the stored account of a person without access (or None)


def viewer() -> Viewer | None:
    return st.session_state.get(VIEWER)


def required(settings: Settings) -> bool:
    """Sign-in is on when Google is configured, and always outside a local checkout."""
    return settings.auth.google or settings.environment != "local"


# --- set-up, once per server process -----------------------------------------------------------

def secrets_path() -> Path:
    """Where Streamlit looks for secrets (the project's .streamlit/secrets.toml)."""
    if override := os.getenv(SECRETS_ENV):
        return Path(override)
    return Path(st.get_option("secrets.files")[-1])


def use_session_cookie() -> bool:
    """Make the sign-in cookie end with the browser session. Streamlit 1.67 sets it for 30
    days through a module constant read at every sign-in; None leaves out Max-Age (checked by
    tests/unit/test_access.py, so an upgrade that changes this fails the tests)."""
    try:
        from streamlit.web.server.starlette import starlette_auth_routes as routes
    except ImportError:
        return False
    routes.AUTH_COOKIE_MAX_AGE_SECONDS = None
    return True


@st.cache_resource(show_spinner=False)
def _configure(key: str, _settings: Settings) -> bool:
    if _settings.auth.google:
        from foresight.access import write_streamlit_secrets

        write_streamlit_secrets(_settings, secrets_path())
        use_session_cookie()
    return True


def configure(settings: Settings) -> None:
    _configure(f"{settings.auth.public_url}|{settings.auth.google_client_id}", settings)


# --- who is here -------------------------------------------------------------------------------

def session(settings: Settings) -> Session:
    """Check the visitor: signed in, approved, not idle for too long."""
    configure(settings)
    if not required(settings):
        local = Viewer(email="", name="Local developer", role="developer", local=True)
        st.session_state[VIEWER] = local
        return Session("ok", local)
    st.session_state.pop(VIEWER, None)
    if not settings.auth.google:
        return Session("not_configured")
    # a visitor without a sign-in cookie can have an empty st.user (no is_logged_in at all)
    if not st.user.get("is_logged_in", False):
        return Session("signed_out")

    email = str(st.user.get("email") or "").strip().lower()
    name = str(st.user.get("name") or "")
    issued = float(st.user.get("iat") or 0)
    if not email or st.user.get("email_verified") is False:
        return Session("no_access")
    clock = store.activity(settings)
    if clock.expired(email, issued):
        clock.forget(email, issued)
        st.logout()  # clears st.user and sends the browser to sign out; the page meanwhile
        return Session("signed_out")  # shows the sign-in card

    try:
        account = _account(settings, email, name)
    except Exception as exc:  # the database did not answer
        from foresight.utils.logging import get_logger

        get_logger("auth").warning("access check failed: %s", type(exc).__name__)
        return Session("unavailable")
    if account is None or not account.approved:
        return Session("no_access", account=account)

    if clock.is_new(email, issued):
        st.toast(f"Hi, {(name or email).split()[0]}! You are signed in.",
                 icon=":material/waving_hand:")
    clock.touch(email, issued)
    person = Viewer(email=email, name=account.name or name, role=account.role,
                    picture=str(st.user.get("picture") or ""), issued_at=issued)
    st.session_state[VIEWER] = person
    return Session("ok", person, account)


def _account(settings: Settings, email: str, name: str):
    """The stored account, rechecked at most once a minute per browser session (a removed
    account loses access within a minute)."""
    checked = st.session_state.get(CHECKED)
    if checked and checked[0] == email and time.time() - checked[1] < RECHECK_S:
        return checked[2]
    account = store.account(settings, email, name)
    st.session_state[CHECKED] = (email, time.time(), account)
    return account


@st.fragment(run_every=60)
def idle_watch(settings: Settings) -> None:
    """Signs out an open page after the idle time, without waiting for the next click (this
    check is not activity)."""
    person = viewer()
    if person is None or person.local:
        return
    if store.activity(settings).expired(person.email, person.issued_at):
        store.activity(settings).forget(person.email, person.issued_at)
        st.logout()


# --- what a visitor without access sees --------------------------------------------------------

def gate_page(settings: Settings, state: Session, privacy, terms) -> None:
    """The page in place of the app: sign in, ask for access, or wait for approval."""
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        ui.page_header("Foresight")
        st.markdown("Semiconductor yield intelligence on the SECOM manufacturing data: data "
                    "validation, failure prediction, investigation reports and a cited chat.")
        if state.status == "not_configured":
            ui.friendly_error("Sign-in is not configured on this server, so nobody can sign "
                              "in. The developer needs to set GOOGLE_CLIENT_ID, "
                              "GOOGLE_CLIENT_SECRET and AUTH_COOKIE_SECRET.")
        elif state.status == "unavailable":
            st.warning("Your access could not be checked right now: the database did not "
                       "answer. Please try again in a minute.", icon=":material/cloud_off:")
            st.button("Try again", key="retry", type="primary")
        elif state.status == "signed_out":
            _sign_in(settings)
        else:
            _no_access(settings, state.account)
        st.html('<div class="fs-gap"></div>')
        left, right, _ = st.columns([1, 1, 3])
        left.page_link(privacy, label="Privacy", icon=":material/shield:")
        right.page_link(terms, label="Terms", icon=":material/gavel:")


def _sign_in(settings: Settings) -> None:
    with st.container(key="card-sign-in"):
        ui.label("Sign in")
        st.markdown("Sign in with your Google account. The session ends when you sign out, "
                    f"close the browser, or after {settings.auth.idle_minutes} minutes "
                    "without activity.")
        st.button("Sign in with Google", key="sign-in", type="primary",
                  icon=":material/login:", on_click=st.login)
        st.caption("New here? Sign in with Google first, then ask for access: the developer "
                   "approves it by email, and from then on one click signs you in.")


def _no_access(settings: Settings, account) -> None:
    email = str(st.user.get("email") or "")
    name = str(st.user.get("name") or "")
    status = getattr(account, "status", None)
    with st.container(key="card-access"):
        if status == "pending" or st.session_state.get(REQUEST_SENT):
            ui.label("Request sent")
            st.info(f"Your request for **{email}** is waiting for the developer's approval. "
                    "Once it is approved, Sign in with Google takes you straight in.",
                    icon=":material/hourglass_top:")
            if st.session_state.get(REQUEST_SENT) == "not emailed":
                st.caption("The email to the developer could not be sent; the request is saved "
                           "and shows up on their Users & access page.")
        elif status == "denied":
            ui.label("Access not granted")
            st.warning(f"The developer did not grant access to **{email}**. If you think this "
                       "is a mistake, contact the developer.", icon=":material/block:")
        else:
            ui.label("Ask for access")
            st.markdown(f"You are signed in as **{name or email}** ({email}), but this account "
                        "has no access to Foresight yet.")
            message = st.text_area("Why do you need access? (optional)", key="access-message",
                                   max_chars=500, height=90)
            if st.button("Request access", key="request-access", type="primary",
                         icon=":material/send:"):
                emailed = store.request_access(settings, email, name, message)
                st.session_state[REQUEST_SENT] = "emailed" if emailed else "not emailed"
                st.session_state.pop(CHECKED, None)
                st.rerun()
        st.button("Sign out (or use another Google account)", key="sign-out-gate",
                  type="tertiary", icon=":material/logout:", on_click=st.logout)


# --- the signed-in person, top right -----------------------------------------------------------

def top_bar(person: Viewer, activity_page, privacy, terms) -> None:
    """ "Hi, <name>" at the top of every page, with the account menu."""
    with st.container(key="topbar", horizontal=True, horizontal_alignment="right"), \
            st.popover(f"Hi, {person.first_name}", icon=":material/account_circle:",
                       type="tertiary"):
        if person.picture:
            st.image(person.picture, width=48)
        st.markdown(f"**{person.name or person.email}**" +
                    (f"  \n:gray[{person.email}]" if person.email else ""))
        st.markdown(":violet-badge[Developer]" if person.developer else ":blue-badge[User]")
        st.page_link(activity_page, label="My activity", icon=":material/history:")
        st.page_link(privacy, label="Privacy", icon=":material/shield:")
        st.page_link(terms, label="Terms", icon=":material/gavel:")
        if not person.local:
            st.button("Sign out", key="sign-out", icon=":material/logout:", on_click=st.logout)
