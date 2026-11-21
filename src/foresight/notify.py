"""Email to the developers when someone asks for access (Phase 8.6).

Sent through Resend's HTTP API (Railway blocks outgoing SMTP). Without a domain of its own,
Resend only delivers to the Resend account's owner, which is the developer. A failed email
never blocks the request: it is stored either way and listed on the Users & access page.
"""

from __future__ import annotations

from html import escape
from urllib.parse import quote

from foresight.access import Account, review_token
from foresight.settings import Settings
from foresight.utils.logging import get_logger

RESEND_URL = "https://api.resend.com/emails"
log = get_logger("notify")


def review_links(settings: Settings, account: Account) -> dict[str, str]:
    """The approve and deny links of a request (they open the Review page, which asks for one
    more click, so a mail scanner that opens links decides nothing)."""
    token = quote(review_token(settings, account))
    base = f"{settings.auth.public_url}/review?token={token}"
    return {"approve": f"{base}&action=approve", "deny": f"{base}&action=deny",
            "users": f"{settings.auth.public_url}/users"}


def request_email(settings: Settings, account: Account) -> dict:
    links = review_links(settings, account)
    name = account.name or account.email
    rows = [("Name", account.name or "(not given)"), ("Email", account.email),
            ("Asked at", f"{account.requested_at} (UTC)"),
            ("Environment", settings.environment),
            ("Message", account.message or "(none)")]
    table = "".join(f"<tr><td style='padding:4px 12px 4px 0;color:#64748b'>{escape(k)}</td>"
                    f"<td style='padding:4px 0'>{escape(v)}</td></tr>" for k, v in rows)
    button = ("display:inline-block;padding:10px 18px;border-radius:999px;color:#fff;"
              "text-decoration:none;font-weight:600;margin-right:8px;background:")
    html = (f"<div style='font-family:Arial,sans-serif;font-size:15px;color:#0f172a'>"
            f"<p><b>{escape(name)}</b> asked for access to Foresight.</p>"
            f"<table style='border-collapse:collapse'>{table}</table>"
            f"<p style='margin-top:20px'>"
            f"<a href='{escape(links['approve'])}' style='{button}#059669'>Approve</a>"
            f"<a href='{escape(links['deny'])}' style='{button}#dc2626'>Deny</a></p>"
            f"<p style='color:#64748b;font-size:13px'>Each link opens Foresight and asks you to "
            f"confirm. The links work for {settings.auth.request_link_days} days; all requests "
            f"are also on the <a href='{escape(links['users'])}'>Users &amp; access</a> page."
            f"</p></div>")
    text = "\n".join([f"{name} asked for access to Foresight.", "",
                      *(f"{k}: {v}" for k, v in rows), "",
                      f"Approve: {links['approve']}", f"Deny: {links['deny']}",
                      f"All requests: {links['users']}"])
    return {"from": settings.auth.email_from, "to": settings.auth.developers,
            "subject": f"Foresight access request: {name}", "html": html, "text": text}


def send_access_request(settings: Settings, account: Account) -> bool:
    """Email the request to the developers; True when Resend accepted it."""
    key = settings.auth.resend_api_key.get_secret_value()
    if not key or not settings.auth.developers:
        log.warning("access request from %s not emailed: RESEND_API_KEY or "
                    "FORESIGHT_DEVELOPERS is not set", account.email)
        return False
    import requests

    try:
        response = requests.post(RESEND_URL, json=request_email(settings, account), timeout=10,
                                 headers={"Authorization": f"Bearer {key}",
                                          "User-Agent": "foresight-app"})
    except requests.RequestException as exc:
        log.warning("access request email failed: %s", type(exc).__name__)
        return False
    if response.status_code >= 300:
        log.warning("access request email refused: HTTP %s %s", response.status_code,
                    response.text[:200])
        return False
    return True
