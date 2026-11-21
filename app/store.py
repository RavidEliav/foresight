"""All of the app's access to run data, in one module (ADR-020).

Pages never touch the filesystem or the pipeline's modules directly: they read a run's files,
list runs, follow progress, start or continue runs and ask the chat through these functions.
This implementation works on the local runs folder (the Railway volume). A later split into a
UI service and an API service would only replace this module; a run folder's name is its run
id.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from foresight import jobs
from foresight.progress import RunProgress, load_progress
from foresight.settings import Settings

RunLimitError = jobs.RunLimitError
MANIFEST = "run_manifest.json"


# --- files of one run -------------------------------------------------------------------------

def exists(run_dir: Path, name: str) -> bool:
    return (run_dir / name).exists()


def read_text(run_dir: Path, name: str) -> str | None:
    path = run_dir / name
    return path.read_text(encoding="utf-8") if path.exists() else None


def read_bytes(run_dir: Path, name: str) -> bytes | None:
    path = run_dir / name
    return path.read_bytes() if path.exists() else None


def read_json(run_dir: Path, name: str) -> dict | None:
    text = read_text(run_dir, name)
    return json.loads(text) if text is not None else None


@st.cache_data(show_spinner=False, max_entries=32)
def _csv(path: str, mtime: float, columns: tuple[str, ...] | None) -> pd.DataFrame:
    return pd.read_csv(path, usecols=list(columns) if columns else None)


def read_csv(run_dir: Path, name: str,
             columns: tuple[str, ...] | None = None) -> pd.DataFrame | None:
    """A run's table, cached per file version (charts redraw on every rerun)."""
    path = run_dir / name
    return _csv(str(path), path.stat().st_mtime, columns) if path.exists() else None


def figure(run_dir: Path, relative: str | None) -> Path | None:
    """A figure of the run. Runs made on Windows store "figures\\x.png"; both separators
    work."""
    if not relative:
        return None
    path = run_dir.joinpath(*relative.replace("\\", "/").split("/"))
    return path if path.exists() else None


def investigation_summary(run_dir: Path):
    from foresight.crews.summary import load_summary

    return load_summary(run_dir)


# --- runs ------------------------------------------------------------------------------------

def runs_folder(settings: Settings) -> Path:
    return jobs.runs_dir(settings)


def run_folder(settings: Settings, run_id: str) -> Path:
    return jobs.runs_dir(settings) / run_id


def viewable_runs(settings: Settings) -> list[Path]:
    """Successful runs, newest first, then the committed reference run."""
    folder = runs_folder(settings)
    found = []
    if folder.exists():
        for path in sorted(folder.iterdir(), reverse=True):
            manifest = read_json(path, MANIFEST) if path.is_dir() else None
            if manifest and manifest.get("status") == "success":
                found.append(path)
    reference = settings.resolve(settings.paths.reference_run_dir)
    if exists(reference, MANIFEST):
        found.append(reference)
    return found


def all_runs(settings: Settings) -> list[RunProgress]:
    """Runs started from the app or the CLI (with their progress), newest first."""
    return jobs.list_runs(settings)


def progress(run_dir: Path) -> RunProgress | None:
    return load_progress(run_dir)


def active_run(settings: Settings) -> RunProgress | None:
    return jobs.active_run(settings)


def start_run(settings: Settings, upload: bytes | None, upload_name: str | None,
              scenario: dict | None = None, user: str = "") -> str:
    return jobs.start_run(settings, upload, upload_name, scenario, user=user)


def scenario_kinds() -> dict[str, tuple[str, str, float, int]]:
    """Scenario Lab kinds: title, description, default intensity, sensors changed."""
    from foresight.data.scenarios import KINDS

    return KINDS


def resume_run(settings: Settings, run_id: str, user: str = "") -> str:
    return jobs.resume_run(settings, run_id, user=user)


def stop_run(settings: Settings, run_id: str, user: str = "") -> None:
    jobs.stop_run(settings, run_id, user=user)


def stop_requested(run_dir: Path) -> bool:
    return jobs.stop_requested(run_dir)


@st.cache_data(show_spinner=False)
def _template(raw_dir: str) -> bytes:
    from foresight.data.secom import load_raw, to_upload_csv

    return to_upload_csv(load_raw(Path(raw_dir)))


def upload_template(settings: Settings) -> bytes | None:
    """The built-in SECOM data in the upload format (None if the raw files are missing)."""
    from foresight.data.secom import DATA_FILE, LABELS_FILE

    raw_dir = settings.resolve(settings.paths.data_raw_dir)
    if not all((raw_dir / name).exists() for name in (DATA_FILE, LABELS_FILE)):
        return None
    return _template(str(raw_dir))


# --- run registry (Trends) --------------------------------------------------------------------

@st.cache_data(ttl=20, show_spinner=False)
def _history(key: str, _settings: Settings) -> tuple[list[dict], str | None]:
    from foresight import registry

    try:
        return registry.history(_settings), None
    except Exception as exc:  # database unreachable: the run folders still work
        from foresight.utils.logging import get_logger

        get_logger("registry").warning("registry read failed: %s", exc)
        files = _settings.model_copy(update={"database_url": ""})
        return registry.history(files), f"{type(exc).__name__}"


def run_history(settings: Settings) -> tuple[pd.DataFrame, str, str | None]:
    """Recorded runs (newest first), where they came from, and an error if the database could
    not be read (then the run folders are used)."""
    from foresight import registry

    rows, error = _history(settings.model_dump_json(), settings)
    source = "files" if error else registry.backend(settings)
    return pd.DataFrame(rows), source, error


@st.cache_data(ttl=20, show_spinner=False)
def _stages(key: str, run_ids: tuple[str, ...], _settings: Settings) -> list[dict]:
    from foresight import registry

    try:
        return registry.stage_history(_settings, list(run_ids))
    except Exception:
        return registry.stage_history(_settings.model_copy(update={"database_url": ""}),
                                      list(run_ids))


def stage_history(settings: Settings, run_ids: list[str], source: str) -> pd.DataFrame:
    """Stage rows from the same source as the history (no second wait on an unreachable
    database)."""
    if source != "supabase":
        settings = settings.model_copy(update={"database_url": ""})
    return pd.DataFrame(_stages(settings.model_dump_json(), tuple(run_ids), settings))


def sync_registry_in_background(settings: Settings) -> None:
    """Record the runs on this server in Supabase (runs from before it was connected, runs a
    restart interrupted); a background thread, so the page never waits for it."""
    if not settings.database_url:
        return
    import threading

    def work() -> None:
        from foresight import registry
        from foresight.registry import db
        from foresight.utils.logging import get_logger

        log = get_logger("registry")
        try:
            db.ping(settings.database_url)
            log.info("registry sync: %d runs recorded", registry.sync(settings))
        except Exception as exc:
            log.warning("registry sync skipped: %s", type(exc).__name__)

    threading.Thread(target=work, name="registry-sync", daemon=True).start()


# --- chat ------------------------------------------------------------------------------------

def ask(question: str, run_dir: Path, settings: Settings, user: str = "") -> dict:
    """Answer and log a question about the run; a failure is logged too, then raised."""
    from foresight.rag.chat import ChatAnswer, log_answer
    from foresight.rag.chat import ask as rag_ask
    from foresight.utils.logging import get_logger

    try:
        result = rag_ask(question, run_dir, settings)
    except Exception as exc:
        get_logger("chat").exception("question failed for run %s", run_dir.name)
        log_answer(settings, run_dir, ChatAnswer(question=question, answer="", refused=True,
                                                 reason=f"error: {exc}"), user)
        raise
    log_answer(settings, run_dir, result, user)
    return result.model_dump()


def ask_all(question: str, settings: Settings, user: str = "") -> dict:
    """Answer and log a question about all recorded runs (logged as "all_runs")."""
    from foresight.rag.chat import ChatAnswer, log_answer
    from foresight.rag.chat import ask_all as rag_ask_all
    from foresight.utils.logging import get_logger

    try:
        result = rag_ask_all(question, settings)
    except Exception as exc:
        get_logger("chat").exception("question about all runs failed")
        log_answer(settings, Path(ALL_RUNS), ChatAnswer(question=question, answer="",
                                                        refused=True, reason=f"error: {exc}"),
                   user)
        raise
    log_answer(settings, Path(ALL_RUNS), result, user)
    return result.model_dump()


ALL_RUNS = "all_runs"  # chat log name of questions about all runs


def recent_questions(settings: Settings, run_dir: Path, user: str | None = None) -> list[dict]:
    from foresight.rag.chat import recent_questions as recent

    return recent(settings, run_dir, user=user)


def questions_by(settings: Settings, user: str) -> list[dict]:
    from foresight.rag.chat import questions_by as asked

    return asked(settings, user)


# --- accounts and sign-in (Phase 8.6) ----------------------------------------------------------

def account(settings: Settings, email: str, name: str = ""):
    from foresight import access

    return access.get_account(settings, email, name)


def accounts(settings: Settings) -> list:
    from foresight import access

    return access.accounts(settings)


def request_access(settings: Settings, email: str, name: str, message: str) -> bool:
    """Record the request and email the developers; True when the email went out."""
    from foresight import access, notify

    return notify.send_access_request(settings, access.request_access(settings, email, name,
                                                                       message))


def decide(settings: Settings, email: str, approve: bool, by: str):
    from foresight import access

    return access.decide(settings, email, approve, by)


def add_account(settings: Settings, email: str, role: str, by: str):
    from foresight import access

    return access.add_account(settings, email, role, by)


def set_role(settings: Settings, email: str, role: str, by: str):
    from foresight import access

    return access.set_role(settings, email, role, by)


def remove_account(settings: Settings, email: str) -> None:
    from foresight import access

    access.remove_account(settings, email)


def review_request(settings: Settings, token: str):
    """The waiting request an emailed link names (None if the link is not valid)."""
    from foresight import access

    return access.read_token(settings, token)


def accounts_backend(settings: Settings) -> str:
    from foresight import access

    return access.backend(settings)


@st.cache_resource(show_spinner=False)
def _activity(runs_dir: str, idle_minutes: int, _settings: Settings):
    from foresight.access import Activity

    return Activity(_settings)


def activity(settings: Settings):
    """The sign-in activity clock, one per server process."""
    return _activity(str(runs_folder(settings)), settings.auth.idle_minutes, settings)


def runs_of(settings: Settings, user: str) -> list[RunProgress]:
    """Runs on this server that ``user`` started, resumed or stopped, newest first."""
    return [p for p in all_runs(settings)
            if user and (p.started_by == user or user in p.resumed_by or p.stopped_by == user)]


def warm_up_chat(settings: Settings) -> None:
    """Get the chat's embedding model ready in the background (once per server process)."""
    from foresight.rag.embedding import warm_up

    warm_up(str(settings.resolve(settings.paths.models_dir)))
