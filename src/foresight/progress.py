"""Live progress of a run, saved as progress.json in the run folder.

The Flow updates it at every stage and gate; the background runner adds a heartbeat. The app
reads it to show live progress, so a run survives a browser refresh. A run whose heartbeat
stopped (for example after a container restart) is reported as interrupted.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, PrivateAttr

PROGRESS_FILE = "progress.json"
ACTIVE = ("queued", "running")
FINISHED = ("success", "failed", "timeout", "interrupted")
STALE_AFTER_S = 90

# (stage, what the deterministic part does, the crew that interprets it)
STAGES: list[tuple[str, str, str | None]] = [
    ("ingest", "Load the data and check the Data Contract", None),
    ("analyze", "EDA and features", "Data Analyst crew"),
    ("model", "Train and evaluate models", "Data Scientist crew"),
    ("investigate", "Anomalies and risk ranking", "Investigation crew"),
    ("report", "Engineering report and output checks", "Engineering Report crew"),
]


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_run_id() -> str:
    """Run ids sort by time (the app relies on that). Defined here, not in flow.py, so the app
    can create runs without importing the Flow (CrewAI and the analytics stack, about 270 MB)."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


# Stage of each crew (the crew runs after its stage's deterministic work)
CREW_STAGES = {"analyst": "analyze", "scientist": "model", "investigation": "investigate",
               "report": "report"}


class StageProgress(BaseModel):
    name: str
    label: str
    crew: str | None = None
    status: str = "pending"  # pending, running, done, failed, skipped
    crew_status: str | None = None  # running, done, skipped, failed
    seconds: float | None = None
    crew_seconds: float | None = None  # a background crew's time, after `seconds`
    # Kept so that a resumed run can reuse a finished stage instead of redoing it
    artifacts: dict[str, str] = Field(default_factory=dict)
    checks: dict | None = None
    crew_usage: dict[str, dict] = Field(default_factory=dict)

    @property
    def reusable(self) -> bool:
        """A resumed run can take this stage over: it finished, recorded its files (runs from
        before Phase 6.1 did not) and the files are still there. Ingest is always redone."""
        return (self.name != "ingest" and self.status == "done" and bool(self.artifacts)
                and (self.crew is None or self.crew_status in ("done", "skipped"))
                and all(Path(p).exists() for p in self.artifacts.values()))

class RunProgress(BaseModel):
    run_id: str
    status: str = "queued"
    dataset: str = "SECOM (UCI)"
    started_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    finished_at: str | None = None
    stages: list[StageProgress] = Field(default_factory=lambda: [
        StageProgress(name=n, label=label, crew=crew) for n, label, crew in STAGES])
    gates: list[dict] = Field(default_factory=list)
    failure_reason: str | None = None
    resumed_at: list[str] = Field(default_factory=list)

    def effective_status(self, stale_after_s: int = STALE_AFTER_S) -> str:
        """``interrupted`` when an active run stopped sending heartbeats."""
        if self.status in ACTIVE:
            age = datetime.now(UTC) - datetime.fromisoformat(self.updated_at)
            if age.total_seconds() > stale_after_s:
                return "interrupted"
        return self.status

    @property
    def current(self) -> StageProgress | None:
        return next((s for s in self.stages if s.status == "running"), None)

    @property
    def can_continue(self) -> bool:
        """An interrupted, timed-out or crashed run can continue where it stopped; a run that a
        gate stopped would stop again on the same data."""
        status = self.effective_status()
        crashed = status == "failed" and any(
            marker in (self.failure_reason or "") for marker in ("stage error", "crew error"))
        return status in ("interrupted", "timeout") or crashed


def load_progress(run_dir: Path) -> RunProgress | None:
    path = run_dir / PROGRESS_FILE
    try:
        return RunProgress.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class ProgressTracker(BaseModel):
    """Thread-safe writer for one run's progress.json."""

    run_dir: Path
    progress: RunProgress
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    @classmethod
    def create(cls, run_dir: Path, run_id: str, dataset: str | None = None) -> ProgressTracker:
        """Continue an existing progress.json (the app writes it first), else start one."""
        progress = load_progress(run_dir)
        if progress is None:
            progress = RunProgress(run_id=run_id)
            if dataset:
                progress.dataset = dataset
        tracker = cls(run_dir=run_dir, progress=progress)
        tracker.save()
        return tracker

    def save(self) -> None:
        with self._lock:
            self.progress.updated_at = now()
            self.run_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.run_dir / f".{PROGRESS_FILE}.{os.getpid()}.{threading.get_ident()}"
            tmp.write_text(json.dumps(self.progress.model_dump(mode="json"), indent=2),
                           encoding="utf-8")
            for attempt in range(40):  # Windows refuses while a reader has the file open
                try:
                    os.replace(tmp, self.run_dir / PROGRESS_FILE)
                    break
                except PermissionError:
                    if attempt == 39:
                        raise
                    time.sleep(0.05)

    def _stage(self, name: str) -> StageProgress | None:
        return next((s for s in self.progress.stages if s.name == name), None)

    def running(self) -> None:
        self.progress.status = "running"
        self.save()

    def stage_started(self, name: str) -> None:
        if stage := self._stage(name):
            stage.status = "running"
        self.save()

    def stage_finished(self, name: str, seconds: float | None, ok: bool = True,
                       artifacts: dict[str, str] | None = None, checks: dict | None = None,
                       crew_usage: dict[str, dict] | None = None) -> None:
        if stage := self._stage(name):
            stage.status = "done" if ok else "failed"
            stage.seconds = None if seconds is None else round(seconds, 1)
            # merged, not replaced: a fast background crew may already have recorded its part
            stage.artifacts = {**stage.artifacts, **(artifacts or {})}
            stage.checks = checks
            stage.crew_usage = {**stage.crew_usage, **(crew_usage or {})}
            if not ok and stage.crew_status == "running":
                stage.crew_status = "failed"
        self.save()

    def crew(self, crew: str, status: str) -> None:
        if stage := self._stage(CREW_STAGES.get(crew, "")):
            stage.crew_status = status
        self.save()

    def crew_finished(self, stage_name: str, artifacts: dict[str, str],
                      crew_usage: dict[str, dict]) -> None:
        """A background crew's outputs and usage join its stage's record (for Continue)."""
        if stage := self._stage(stage_name):
            stage.artifacts = {**stage.artifacts, **artifacts}
            stage.crew_usage = {**stage.crew_usage, **crew_usage}
            stage.crew_status = "done"
            stage.crew_seconds = round(sum(u.get("seconds") or 0 for u in crew_usage.values()), 1)
        self.save()

    def finished_stage(self, name: str) -> StageProgress | None:
        """The stage if it finished before (a resumed run reuses it) and its files are still
        there."""
        stage = self._stage(name)
        return stage if stage is not None and stage.reusable else None

    def prepare_resume(self) -> None:
        """Reset what did not finish, so the run can continue from there."""
        progress = self.progress
        progress.status, progress.failure_reason, progress.finished_at = "queued", None, None
        progress.gates = []
        progress.resumed_at.append(now())
        for stage in progress.stages:
            if stage.status != "done" or not stage.reusable:
                stage.status, stage.crew_status, stage.seconds = "pending", None, None
                stage.crew_seconds = None
                stage.artifacts, stage.checks, stage.crew_usage = {}, None, {}
        self.save()

    def gate(self, name: str, status: str, messages: list[str]) -> None:
        self.progress.gates.append({"gate": name, "status": status, "messages": messages})
        self.save()

    def finish(self, status: str, reason: str | None = None) -> None:
        self.progress.status = status
        self.progress.failure_reason = reason
        self.progress.finished_at = now()
        for stage in self.progress.stages:
            if stage.status == "running":
                stage.status = "failed"
                if stage.crew_status == "running":
                    stage.crew_status = "failed"
            elif stage.status == "pending" and status != "success":
                stage.status = "skipped"
        self.save()
