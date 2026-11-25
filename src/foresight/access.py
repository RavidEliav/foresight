"""Who may use Foresight (Phase 8.6): accounts, access requests, roles and sign-in activity.

People sign in with Google. A new account asks for access; the developers get an email with
the requester's details and a link to approve or deny it. Approved accounts only click "Sign in
with Google" from then on. The developers (``FORESIGHT_DEVELOPERS``) are always approved and
see the developer view; on the Users & access page they approve requests and add accounts.

Accounts live in Supabase (``foresight.accounts``) when ``SUPABASE_DB_URL`` is set, else in
``.access/accounts.json`` in the runs folder (the Railway volume; tests and local checkouts).
Each environment has its own database, so dev and main approve separately.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

from foresight.settings import Settings

ROLES = ("user", "developer")
STATUSES = ("pending", "approved", "denied")
ACCESS_DIR = ".access"
_LOCK = threading.Lock()


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def normalize(email: str) -> str:
    return (email or "").strip().lower()


class Account(BaseModel):
    email: str
    name: str = ""
    role: str = "user"          # user or developer
    status: str = "pending"     # pending, approved or denied
    message: str = ""           # what the requester wrote
    requested_at: str | None = None
    decided_at: str | None = None
    decided_by: str | None = None

    @property
    def approved(self) -> bool:
        return self.status == "approved"

    @property
    def developer(self) -> bool:
        return self.approved and self.role == "developer"


# --- storage ---------------------------------------------------------------------------------

def _folder(settings: Settings) -> Path:
    return settings.resolve(settings.paths.runs_dir) / ACCESS_DIR


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class _Files:
    def __init__(self, settings: Settings):
        self.path = _folder(settings) / "accounts.json"

    def all(self) -> list[Account]:
        return [Account(**a) for a in _read_json(self.path).values()]

    def get(self, email: str) -> Account | None:
        found = _read_json(self.path).get(email)
        return Account(**found) if found else None

    def put(self, account: Account) -> None:
        with _LOCK:
            data = _read_json(self.path)
            data[account.email] = account.model_dump()
            _write_json(self.path, data)

    def delete(self, email: str) -> None:
        with _LOCK:
            data = _read_json(self.path)
            data.pop(email, None)
            _write_json(self.path, data)


COLUMNS = ("email", "name", "role", "status", "message", "requested_at", "decided_at",
           "decided_by")


class _Database:
    def __init__(self, settings: Settings):
        self.url = settings.database_url

    @staticmethod
    def _account(row: dict) -> Account:
        for key in ("requested_at", "decided_at"):
            if row[key] is not None:
                row[key] = row[key].isoformat()
        return Account(**row)

    def all(self) -> list[Account]:
        from psycopg.rows import dict_row

        from foresight.registry.db import connect

        with connect(self.url) as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"select {', '.join(COLUMNS)} from foresight.accounts")
            return [self._account(r) for r in cur.fetchall()]

    def get(self, email: str) -> Account | None:
        from psycopg.rows import dict_row

        from foresight.registry.db import connect

        with connect(self.url) as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"select {', '.join(COLUMNS)} from foresight.accounts where email = %s",
                        [email])
            row = cur.fetchone()
        return self._account(row) if row else None

    def put(self, account: Account) -> None:
        from foresight.registry.db import connect

        values = account.model_dump()
        updates = ", ".join(f"{c} = excluded.{c}" for c in COLUMNS if c != "email")
        with connect(self.url) as conn:
            conn.execute(f"insert into foresight.accounts ({', '.join(COLUMNS)}) values "
                         f"({', '.join(['%s'] * len(COLUMNS))}) on conflict (email) do update "
                         f"set {updates}", [values[c] for c in COLUMNS])

    def delete(self, email: str) -> None:
        from foresight.registry.db import connect

        with connect(self.url) as conn:
            conn.execute("delete from foresight.accounts where email = %s", [email])


def _store(settings: Settings):
    return _Database(settings) if settings.database_url else _Files(settings)


def backend(settings: Settings) -> str:
    return "supabase" if settings.database_url else "files"


# --- accounts --------------------------------------------------------------------------------

def is_developer_email(settings: Settings, email: str) -> bool:
    return normalize(email) in settings.auth.developers


def get_account(settings: Settings, email: str, name: str = "") -> Account | None:
    """The account of a signed-in email. The developers are always approved, without a
    database lookup, so they can sign in even when the database does not answer."""
    email = normalize(email)
    if is_developer_email(settings, email):
        return Account(email=email, name=name, role="developer", status="approved")
    return _store(settings).get(email)


def accounts(settings: Settings) -> list[Account]:
    """Every account, waiting requests first, then by email."""
    order = {"pending": 0, "approved": 1, "denied": 2}
    return sorted(_store(settings).all(), key=lambda a: (order.get(a.status, 3), a.email))


def request_access(settings: Settings, email: str, name: str, message: str = "") -> Account:
    """Record (or renew) a request. A renewed request gets a new time, so links in older
    emails stop working."""
    account = Account(email=normalize(email), name=name.strip(), status="pending",
                      message=message.strip()[:500], requested_at=now())
    _store(settings).put(account)
    return account


def decide(settings: Settings, email: str, approve: bool, by: str) -> Account | None:
    """Approve or deny a waiting request (None if there is none)."""
    account = _store(settings).get(normalize(email))
    if account is None or account.status != "pending":
        return None
    account.status = "approved" if approve else "denied"
    account.decided_at, account.decided_by = now(), normalize(by)
    _store(settings).put(account)
    return account


def add_account(settings: Settings, email: str, role: str, by: str, name: str = "") -> Account:
    """A developer adds (or re-approves) an account directly."""
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}")
    email = normalize(email)
    if "@" not in email or " " in email:
        raise ValueError("enter a valid email address")
    existing = _store(settings).get(email)
    account = Account(email=email, name=name.strip() or (existing.name if existing else ""),
                      role=role, status="approved",
                      message=existing.message if existing else "",
                      requested_at=existing.requested_at if existing else None,
                      decided_at=now(), decided_by=normalize(by))
    _store(settings).put(account)
    return account


def set_role(settings: Settings, email: str, role: str, by: str) -> Account | None:
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}")
    account = _store(settings).get(normalize(email))
    if account is None:
        return None
    account.role, account.decided_at, account.decided_by = role, now(), normalize(by)
    _store(settings).put(account)
    return account


def remove_account(settings: Settings, email: str) -> None:
    """Remove access. The person can ask again by signing in."""
    _store(settings).delete(normalize(email))


# --- Google sign-in settings for Streamlit ---------------------------------------------------

GOOGLE_METADATA = "https://accounts.google.com/.well-known/openid-configuration"


def streamlit_secrets(settings: Settings) -> str:
    """The ``[auth]`` section ``st.login`` reads. ``prompt = "select_account"`` lets a person
    with several Google accounts choose which one to use."""
    auth = settings.auth
    values = {"redirect_uri": f"{auth.public_url}/oauth2callback",
              "cookie_secret": auth.cookie_secret.get_secret_value(),
              "client_id": auth.google_client_id,
              "client_secret": auth.google_client_secret.get_secret_value(),
              "server_metadata_url": GOOGLE_METADATA}
    lines = ["# Written by the app from environment variables (app/auth.py). Not committed.",
             "[auth]", *(f"{k} = {json.dumps(v)}" for k, v in values.items()),
             'client_kwargs = { prompt = "select_account" }', ""]
    return "\n".join(lines)


def write_streamlit_secrets(settings: Settings, path: Path) -> bool:
    """Write the sign-in settings where Streamlit reads them; True if the file changed.
    Streamlit reads the file again on every sign-in until it exists, so writing it at the
    first page load is enough."""
    text = streamlit_secrets(settings)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


# --- links in the request email -------------------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(settings: Settings, payload: str) -> str:
    key = settings.auth.cookie_secret.get_secret_value().encode()
    return _b64(hmac.new(key, payload.encode(), hashlib.sha256).digest())


def review_token(settings: Settings, account: Account) -> str:
    """A signed link token for one request: it names the request (email and time) and
    expires after ``auth.request_link_days``."""
    expires = int(time.time() + settings.auth.request_link_days * 86400)
    payload = json.dumps([account.email, account.requested_at, expires], separators=(",", ":"))
    return f"{_b64(payload.encode())}.{_sign(settings, payload)}"


def read_token(settings: Settings, token: str) -> Account | None:
    """The waiting request a link token names; None if the token is forged, expired, or the
    request was decided or renewed since."""
    if not settings.auth.cookie_secret.get_secret_value() or "." not in (token or ""):
        return None
    body, signature = token.rsplit(".", 1)
    try:
        payload = _unb64(body).decode()
        email, requested_at, expires = json.loads(payload)
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(signature, _sign(settings, payload)) or time.time() > expires:
        return None
    account = _store(settings).get(normalize(email))
    if account is None or account.status != "pending" or account.requested_at != requested_at:
        return None
    return account


# --- sign-in activity (signed out after an hour without activity) ----------------------------

class Activity:
    """Last activity per sign-in (email and the time Google issued the sign-in), kept in
    memory and saved to the runs folder at most once a minute, so a restart does not reset
    the idle clock."""

    SAVE_EVERY_S = 60

    def __init__(self, settings: Settings):
        self.path = _folder(settings) / "activity.json"
        self.idle = timedelta(minutes=settings.auth.idle_minutes)
        self._seen: dict[str, float] = {k: float(v) for k, v in _read_json(self.path).items()}
        self._saved = time.time()
        self._lock = threading.Lock()

    @staticmethod
    def key(email: str, issued_at) -> str:
        return f"{normalize(email)}|{int(issued_at or 0)}"

    def last(self, email: str, issued_at) -> float:
        """Last activity of this sign-in: its start if nothing was recorded (a sign-in
        without an issue time counts from now, so it is never signed out at once)."""
        return self._seen.get(self.key(email, issued_at), float(issued_at or time.time()))

    def expired(self, email: str, issued_at, at: float | None = None) -> bool:
        at = time.time() if at is None else at
        return at - self.last(email, issued_at) > self.idle.total_seconds()

    def is_new(self, email: str, issued_at) -> bool:
        """True the first time this sign-in is seen (to greet the person once)."""
        return self.key(email, issued_at) not in self._seen

    def touch(self, email: str, issued_at, at: float | None = None) -> None:
        at = time.time() if at is None else at
        key = self.key(email, issued_at)
        with self._lock:
            new = key not in self._seen
            self._seen[key] = at
            if new or at - self._saved >= self.SAVE_EVERY_S:  # a new sign-in is saved at once
                self._save(at)

    def forget(self, email: str, issued_at) -> None:
        with self._lock:
            self._seen.pop(self.key(email, issued_at), None)
            self._save(time.time())

    def _save(self, at: float) -> None:
        horizon = at - self.idle.total_seconds() * 2  # older sign-ins can only be expired
        self._seen = {k: v for k, v in self._seen.items() if v >= horizon}
        with contextlib.suppress(OSError):  # the clock still works in memory
            _write_json(self.path, self._seen)
        self._saved = at
