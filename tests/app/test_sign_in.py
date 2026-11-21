"""Sign-in for the whole app (Phase 8.6), with Google configured and st.user simulated."""

import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from foresight import access
from foresight.settings import load_settings

APP = str(Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py")
DEVELOPER = "dev@example.com"
USER_MENU = ["Run Pipeline", "Data Quality", "EDA & Insights", "Model", "Investigation & Report",
             "Line Replay", "Ask Foresight", "My activity"]


@pytest.fixture(autouse=True)
def google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("AUTH_COOKIE_SECRET", "cookie-secret")
    monkeypatch.setenv("FORESIGHT_DEVELOPERS", DEVELOPER)


def _app(email: str | None = None, name: str = "Ada Lovelace", issued: float | None = None):
    at = AppTest.from_file(APP, default_timeout=60)
    at.user = ({"is_logged_in": False} if email is None else
               {"is_logged_in": True, "email": email, "name": name, "email_verified": True,
                "iat": issued or time.time()})
    return at.run()


def _menu(at) -> list[str]:
    return [link.proto.label for link in at.sidebar.get("page_link")]


@pytest.mark.parametrize("user", [{"is_logged_in": False}, {}])
def test_visitors_only_see_the_sign_in_screen(user):
    """A visitor without a sign-in cookie may have an empty st.user (found in a browser)."""
    at = AppTest.from_file(APP, default_timeout=60)
    at.user = user
    at.run()
    assert not at.exception
    assert at.button(key="sign-in").label == "Sign in with Google"
    assert _menu(at) == [] and not at.get("popover")
    assert not any(t.value == "Run Pipeline" for t in at.title)
    links = [link.proto.label for link in at.get("page_link")]
    assert links == ["Privacy", "Terms"]  # public, as Google's consent screen requires


def test_railway_without_google_keys_lets_nobody_in(monkeypatch):
    for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "AUTH_COOKIE_SECRET"):
        monkeypatch.delenv(name)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "dev")
    at = _app("ada@example.com")
    assert any("Sign-in is not configured" in e.value for e in at.error)
    assert _menu(at) == []


def test_a_new_account_asks_for_access_and_waits():
    at = _app("ada@example.com")
    assert any("has no access to Foresight yet" in m.value for m in at.markdown)
    assert _menu(at) == []
    at.text_area(key="access-message").input("For the yield review")
    at.button(key="request-access").click().run()
    assert any("waiting for the developer's approval" in i.value for i in at.info)
    # no RESEND_API_KEY in tests: the request is saved and the page says it was not emailed
    assert any("could not be sent" in c.value for c in at.caption)
    stored = access.get_account(load_settings(), "ada@example.com")
    assert stored.status == "pending" and stored.message == "For the yield review"

    again = _app("ada@example.com")  # a later visit: still waiting, no second form
    assert any("waiting for the developer's approval" in i.value for i in again.info)
    assert not again.text_area


def test_an_approved_user_gets_the_user_view_and_a_greeting():
    settings = load_settings()
    access.add_account(settings, "ada@example.com", "user", DEVELOPER)
    at = _app("ada@example.com")
    assert not at.exception
    assert _menu(at) == USER_MENU  # no Trends, no Users & access
    assert at.get("popover")[0].proto.popover.label == "Hi, Ada"
    assert [t.value for t in at.toast] == ["Hi, Ada! You are signed in."]
    assert not any("Environment:" in m.value for m in at.sidebar.markdown)
    assert not at.text_input  # no passcode

    at.run()  # the greeting comes once per sign-in
    assert not at.toast


def test_a_developer_gets_the_developer_view():
    at = _app(DEVELOPER, "Ravid Eliav")
    assert _menu(at)[-1] == "Users & access" and "Trends" in _menu(at)
    assert any("Environment: local" in m.value for m in at.sidebar.markdown)
    assert at.get("popover")[0].proto.popover.label == "Hi, Ravid"


def test_an_hour_without_activity_signs_out(monkeypatch):
    settings = load_settings()
    access.add_account(settings, "ada@example.com", "user", DEVELOPER)
    long_ago = time.time() - 2 * 3600
    at = _app("ada@example.com", issued=long_ago)
    assert at.user == {"is_logged_in": False}  # st.logout ran
    assert at.button(key="sign-in")


def test_a_removed_account_loses_access(monkeypatch):
    from app import auth

    settings = load_settings()
    access.add_account(settings, "ada@example.com", "user", DEVELOPER)
    at = _app("ada@example.com")
    assert _menu(at) == USER_MENU
    access.remove_account(settings, "ada@example.com")
    monkeypatch.setattr(auth, "RECHECK_S", 0)  # the next check, without waiting a minute
    at.run()
    assert _menu(at) == []
    assert any("has no access" in m.value for m in at.markdown)


def _page(module: str, viewer_role: str | None, query: dict | None = None) -> AppTest:
    def page(module, role):
        import importlib

        import streamlit as st

        from app.auth import Viewer
        from foresight.settings import load_settings

        viewer = None if role is None else Viewer(email="dev@example.com", name="Ravid",
                                                  role=role)
        st.session_state["viewer"] = viewer
        importlib.import_module(module).render(load_settings(), viewer)

    at = AppTest.from_function(page, args=(module, viewer_role), default_timeout=60)
    for key, value in (query or {}).items():
        at.query_params[key] = value
    return at.run()


def test_the_emailed_link_approves_after_one_click_without_signing_in():
    settings = load_settings()
    request = access.request_access(settings, "ada@example.com", "Ada", "Thesis")
    token = access.review_token(settings, request)
    at = _page("app.review_page", None, {"token": token, "action": "approve"})
    assert any("Thesis" in m.value for m in at.markdown)
    assert access.get_account(settings, "ada@example.com").status == "pending"  # opening: no
    at.button(key="review-approve").click().run()
    assert any("Approved: ada@example.com" in s.value for s in at.success)
    decided = access.get_account(settings, "ada@example.com")
    assert decided.approved and decided.decided_by == "email link"

    again = _page("app.review_page", None, {"token": token, "action": "approve"})
    assert any("does not work any more" in w.value for w in again.warning)


def test_users_and_access_approves_requests_and_adds_people():
    settings = load_settings()
    access.request_access(settings, "ada@example.com", "Ada", "Thesis")
    at = _page("app.access_page", "developer")
    assert not at.exception
    at.button(key="approve-ada@example.com").click().run()
    assert access.get_account(settings, "ada@example.com").approved
    assert any("is approved" in s.value for s in at.success)

    at.text_input(key="add-email").input("Bob@Example.com")
    at.selectbox(key="add-role").set_value("developer")
    next(b for b in at.button if b.label == "Add").click().run()  # the form's button
    assert access.get_account(settings, "bob@example.com").developer

    table = at.dataframe[0].value
    assert set(table["email"]) == {DEVELOPER, "ada@example.com", "bob@example.com"}
    at.selectbox(key="manage-email").set_value("ada@example.com").run()
    at.button(key="remove-account").click().run()
    assert access.get_account(settings, "ada@example.com") is None


def test_my_activity_lists_only_the_persons_runs_and_questions():
    from foresight import jobs
    from foresight.progress import ProgressTracker
    from foresight.rag.chat import ChatAnswer, log_answer

    settings = load_settings()
    mine = jobs.runs_dir(settings) / "20260101T000000000000Z"
    ProgressTracker.create(mine, mine.name, "SECOM (UCI)", started_by=DEVELOPER).finish("success")
    other = jobs.runs_dir(settings) / "20260102T000000000000Z"
    ProgressTracker.create(other, other.name, started_by="ada@example.com").finish("success")
    log_answer(settings, mine, ChatAnswer(question="Mine?", answer="x", refused=False),
               DEVELOPER)
    log_answer(settings, mine, ChatAnswer(question="Not mine", answer="x", refused=False),
               "ada@example.com")

    at = _page("app.activity_page", "developer")
    assert not at.exception
    runs, questions = at.dataframe[0].value, at.dataframe[1].value
    assert len(runs) == 1 and runs.iloc[0]["you"] == "started"
    assert list(questions["question"]) == ["Mine?"]
