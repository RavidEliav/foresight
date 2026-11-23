"""Run files in Supabase Storage (ADR-033).

A finished run is packed into one ``<run id>.tar.gz`` in the private bucket ``runs``, and its
registry row gets the whole progress. The Railway volume then keeps the newest runs whole and
only a stub of the others (``progress.json``, ``run_manifest.json`` and ``archived.json``, a
few KB): every list, label and history works from the stubs, and a page that needs a run's
files downloads them again. On an empty volume the stubs are rebuilt from the registry.

A Storage or database problem is logged and never fails a run or a page: a run folder stays
whole until its files are safely archived.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tarfile
import threading
from datetime import UTC, datetime
from pathlib import Path

import requests

from foresight.progress import ACTIVE, PROGRESS_FILE, STOP_FILE, ProgressTracker, load_progress
from foresight.settings import Settings
from foresight.utils.logging import get_logger, redact

log = get_logger("archive")
BUCKET = "runs"
MARKER = "archived.json"
MANIFEST = "run_manifest.json"
STUB = {PROGRESS_FILE, MANIFEST, MARKER}
TIMEOUT_S = 120
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock(run_id: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(run_id, threading.Lock())


def _request(method: str, url: str, **kwargs) -> requests.Response:
    return requests.request(method, url, timeout=TIMEOUT_S, **kwargs)


def _object_url(settings: Settings, run_id: str) -> str:
    return f"{settings.storage_url}/storage/v1/object/{BUCKET}/{run_id}.tar.gz"


def _headers(settings: Settings) -> dict[str, str]:
    return {"apikey": settings.storage_key.get_secret_value()}


# --- the marker: is the run archived, and is the folder only a stub? ---------------------------

def marker(run_dir: Path) -> dict | None:
    try:
        return json.loads((run_dir / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_marker(run_dir: Path, values: dict) -> None:
    (run_dir / MARKER).write_text(json.dumps(values), encoding="utf-8")


def is_stub(run_dir: Path) -> bool:
    """Only the run's progress and manifest are on the volume; its files are in Storage."""
    return bool((marker(run_dir) or {}).get("stub"))


def _archived(run_dir: Path, updated_at: str) -> bool:
    """Archived, and not changed since (a resumed run is archived again)."""
    return (marker(run_dir) or {}).get("updated_at") == updated_at


# --- Storage ---------------------------------------------------------------------------------

def pack(run_dir: Path) -> bytes:
    """The run's files as one .tar.gz (not the marker, a stop request or temporary files)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", compresslevel=6) as tar:
        for path in sorted(run_dir.rglob("*")):
            if path.is_file() and path.name not in (MARKER, STOP_FILE) \
                    and not path.name.startswith("."):
                tar.add(path, arcname=path.relative_to(run_dir).as_posix())
    return buffer.getvalue()


def upload(settings: Settings, run_dir: Path) -> int:
    """Pack the run into Storage (replacing an older archive); returns its size in bytes."""
    data = pack(run_dir)
    response = _request("POST", _object_url(settings, run_dir.name), data=data,
                        headers={**_headers(settings), "Content-Type": "application/gzip",
                                 "x-upsert": "true"})
    if response.status_code >= 300:
        raise RuntimeError(f"Storage upload: HTTP {response.status_code} {response.text[:200]}")
    return len(data)


def download(settings: Settings, run_dir: Path) -> bool:
    """Unpack the run's archive into its folder; False if Storage has none."""
    response = _request("GET", _object_url(settings, run_dir.name), headers=_headers(settings))
    if response.status_code in (400, 404):  # Storage answers 400 "Object not found"
        return False
    if response.status_code >= 300:
        raise RuntimeError(f"Storage download: HTTP {response.status_code}")
    staging = run_dir.parent / f".download-{run_dir.name}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
            tar.extractall(staging, filter="data")  # no paths outside the folder
        for path in staging.rglob("*"):
            if path.is_file():
                target = run_dir / path.relative_to(staging)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(path, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return True


# --- the run lifecycle -----------------------------------------------------------------------

def archive_run(run_dir: Path, settings: Settings) -> bool:
    """Put a finished run's files in Storage and its row (with the progress) in the registry;
    True when its files are safely archived, now or before."""
    if is_stub(run_dir):
        return True
    if not settings.archive:
        return False
    progress = load_progress(run_dir)
    if progress is None or progress.effective_status() in ACTIVE:
        return False
    if _archived(run_dir, progress.updated_at):
        return True
    with _lock(run_dir.name):
        try:
            if progress.status in ACTIVE:  # it went quiet: record why before it is archived
                from foresight.jobs import interruption_cause

                tracker = ProgressTracker(run_dir=run_dir, progress=progress)
                tracker.finish("interrupted", interruption_cause(settings, run_dir, progress)[0])
                progress = tracker.progress
            size = upload(settings, run_dir)
            from foresight.registry import db, record_run

            if not record_run(run_dir, settings):
                raise RuntimeError("the registry row was not written")
            db.mark_archived(settings.database_url, progress.run_id, size)
            _write_marker(run_dir, {"updated_at": progress.updated_at, "bytes": size,
                                    "archived_at": datetime.now(UTC).isoformat(timespec="seconds"),
                                    "stub": False})
            log.info("run %s archived in Supabase Storage (%.1f MB)", run_dir.name, size / 1e6)
            return True
        except Exception as exc:  # the folder stays whole; the next start tries again
            log.warning("run %s not archived: %s", run_dir.name, redact(exc))
            return False


def make_stub(run_dir: Path) -> None:
    """Keep only the run's progress, manifest and marker on the volume (it is archived)."""
    with _lock(run_dir.name):
        for path in list(run_dir.iterdir()):
            if path.name not in STUB:
                shutil.rmtree(path) if path.is_dir() else path.unlink()
        _write_marker(run_dir, {**(marker(run_dir) or {}), "stub": True})


def ensure_full(settings: Settings, run_dir: Path) -> bool:
    """True when the run's files are on the volume; a stub's are downloaded again."""
    if not is_stub(run_dir):
        return run_dir.exists()
    if not settings.archive:
        return False
    with _lock(run_dir.name):
        if not is_stub(run_dir):  # another page loaded it meanwhile
            return True
        try:
            if not download(settings, run_dir):
                log.warning("run %s has no archive in Supabase Storage", run_dir.name)
                return False
        except Exception as exc:
            log.warning("run %s not loaded from Supabase Storage: %s", run_dir.name, redact(exc))
            return False
        _write_marker(run_dir, {**(marker(run_dir) or {}), "stub": False})
        return True


def restore_stubs(settings: Settings) -> int:
    """Rebuild the stub of every archived run missing from the volume (a new or wiped volume),
    from its registry row; returns how many."""
    if not settings.archive:
        return 0
    from foresight.registry import db

    runs = settings.resolve(settings.paths.runs_dir)
    made = 0
    for row in db.fetch_archived(settings.database_url):
        folder = runs / row["run_id"]
        if (folder / PROGRESS_FILE).exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        (folder / PROGRESS_FILE).write_text(json.dumps(row["progress"]), encoding="utf-8")
        if row.get("manifest"):
            (folder / MANIFEST).write_text(json.dumps(row["manifest"]), encoding="utf-8")
        _write_marker(folder, {"updated_at": row["progress"].get("updated_at"), "stub": True})
        made += 1
    return made
