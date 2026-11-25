"""Sign-in (Phase 8.6): accounts, access requests, emailed review links, the idle clock and
the request email."""

import time

import pytest

from foresight import access, notify
from foresight.settings import load_settings


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("FORESIGHT_DEVELOPERS", "dev@example.com")
    monkeypatch.setenv("AUTH_COOKIE_SECRET", "test-cookie-secret")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("FORESIGHT_PUBLIC_URL", "https://foresight.example")
    return load_settings()


def test_a_request_waits_until_a_developer_approves_it(settings):
    assert access.get_account(settings, "ada@example.com") is None
    request = access.request_access(settings, " Ada@Example.com ", "Ada Lovelace", "For my thesis")
    assert request.email == "ada@example.com" and request.status == "pending"
    assert not access.get_account(settings, "ada@example.com").approved

    decided = access.decide(settings, "ada@example.com", True, "Dev@Example.com")
    assert decided.approved and decided.decided_by == "dev@example.com"
    assert access.get_account(settings, "ADA@example.com").approved
    assert access.decide(settings, "ada@example.com", False, "dev@example.com") is None  # done

    access.request_access(settings, "eve@example.com", "Eve", "")
    access.decide(settings, "eve@example.com", False, "dev@example.com")
    assert access.get_account(settings, "eve@example.com").status == "denied"
    assert [a.status for a in access.accounts(settings)] == ["approved", "denied"]


def test_developers_are_always_approved_and_can_add_and_remove_people(settings):
    developer = access.get_account(settings, "DEV@example.com", "Ravid")
    assert developer.developer and developer.name == "Ravid"

    added = access.add_account(settings, "bob@example.com", "user", "dev@example.com")
    assert added.approved and not added.developer
    assert access.set_role(settings, "bob@example.com", "developer", "dev@example.com").developer
    with pytest.raises(ValueError):
        access.add_account(settings, "not an email", "user", "dev@example.com")
    with pytest.raises(ValueError):
        access.set_role(settings, "bob@example.com", "admin", "dev@example.com")
    access.remove_account(settings, "bob@example.com")
    assert access.get_account(settings, "bob@example.com") is None


def test_a_review_link_names_one_waiting_request(settings, monkeypatch):
    request = access.request_access(settings, "ada@example.com", "Ada", "")
    token = access.review_token(settings, request)
    assert access.read_token(settings, token).email == "ada@example.com"

    body, signature = token.rsplit(".", 1)
    assert access.read_token(settings, f"{body}.{signature[:-2]}xx") is None  # forged
    assert access.read_token(settings, "garbage") is None
    other = settings.model_copy(deep=True)
    other.auth.cookie_secret = type(other.auth.cookie_secret)("another-secret")
    assert access.read_token(other, token) is None  # signed with another key

    later = time.time() + settings.auth.request_link_days * 86400 + 60
    monkeypatch.setattr(access.time, "time", lambda: later)
    assert access.read_token(settings, token) is None  # expired
    monkeypatch.undo()

    time.sleep(1.1)  # a renewed request has a new time: older links stop working
    access.request_access(settings, "ada@example.com", "Ada", "again")
    assert access.read_token(settings, token) is None
    fresh = access.review_token(settings, access.get_account(settings, "ada@example.com"))
    access.decide(settings, "ada@example.com", True, "dev@example.com")
    assert access.read_token(settings, fresh) is None  # decided


def test_the_idle_clock_signs_out_after_an_hour_and_survives_a_restart(settings, monkeypatch):
    monkeypatch.setattr(access.Activity, "SAVE_EVERY_S", 0)  # save every touch
    clock = access.Activity(settings)
    signed_in = 1_000_000.0
    assert clock.is_new("ada@example.com", signed_in)
    assert not clock.expired("ada@example.com", signed_in, at=signed_in + 59 * 60)
    assert clock.expired("ada@example.com", signed_in, at=signed_in + 61 * 60)

    clock.touch("ada@example.com", signed_in, at=signed_in + 50 * 60)
    assert not clock.is_new("ada@example.com", signed_in)
    assert not clock.expired("ada@example.com", signed_in, at=signed_in + 100 * 60)
    assert clock.expired("ada@example.com", signed_in, at=signed_in + 111 * 60)

    clock.touch("ada@example.com", signed_in, at=time.time())
    restarted = access.Activity(settings)
    assert not restarted.is_new("ada@example.com", signed_in)
    assert not restarted.expired("ada@example.com", signed_in)
    assert not restarted.expired("ada@example.com", 0)  # no issue time: counts from now


def test_the_request_email_has_the_details_and_both_links(settings, monkeypatch):
    request = access.request_access(settings, "ada@example.com", "Ada <Lovelace>", "Thesis")
    email = notify.request_email(settings, request)
    assert email["to"] == ["dev@example.com"]
    assert email["subject"] == "Foresight access request: Ada <Lovelace>"
    assert "Ada &lt;Lovelace&gt;" in email["html"] and "<Lovelace>" not in email["html"]
    for action in ("approve", "deny"):
        assert "https://foresight.example/review?token=" in email["text"]
        assert f"&action={action}" in email["text"]
    token = email["text"].split("token=")[1].split("&")[0]
    from urllib.parse import unquote

    assert access.read_token(settings, unquote(token)).email == "ada@example.com"

    sent = []

    class Response:
        status_code = 200
        text = ""

    import requests

    monkeypatch.setattr(requests, "post", lambda url, **kw: sent.append((url, kw)) or Response())
    assert notify.send_access_request(settings, request)
    url, kw = sent[0]
    assert url == notify.RESEND_URL and kw["headers"]["Authorization"] == "Bearer re_test"

    Response.status_code = 403
    assert not notify.send_access_request(settings, request)  # logged, never raised


def test_sign_in_settings_are_written_where_streamlit_reads_them(settings, tmp_path, monkeypatch):
    import tomllib

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", 'se"cret')
    configured = load_settings()
    path = tmp_path / ".streamlit" / "secrets.toml"
    assert access.write_streamlit_secrets(configured, path)
    assert not access.write_streamlit_secrets(configured, path)  # unchanged: not rewritten
    section = tomllib.loads(path.read_text(encoding="utf-8"))["auth"]
    assert section["client_secret"] == 'se"cret'
    assert section["redirect_uri"] == "https://foresight.example/oauth2callback"
    assert section["client_kwargs"] == {"prompt": "select_account"}  # choose a Google account


def test_the_sign_in_cookie_ends_with_the_browser_session():
    """Streamlit sets a 30-day cookie through a module constant; Foresight makes it a session
    cookie. Fails if a Streamlit upgrade changes how the cookie is set."""
    import inspect

    from streamlit.web.server.starlette import starlette_auth_routes as routes

    from app import auth

    assert "max_age=AUTH_COOKIE_MAX_AGE_SECONDS" in inspect.getsource(routes._set_single_cookie)
    assert auth.use_session_cookie() and routes.AUTH_COOKIE_MAX_AGE_SECONDS is None

    from starlette.responses import Response

    response = Response()
    routes._set_single_cookie(response, "_streamlit_user", "{}")
    cookie = response.headers["set-cookie"].lower()
    assert "max-age" not in cookie and "expires" not in cookie and "httponly" in cookie
