"""Foresight CrewAI Flow.

Stage order: ingest -> [data contract gate] -> analyze -> [features gate] -> model
-> investigate -> [evidence gate] -> report. Any ERROR, or an exception inside a stage,
routes to handle_failure, which writes a failure report instead of crashing.

The Data Analyst and Data Scientist crews run in the background while the next stages compute
(they only read files that already exist); the Flow waits for them before the report, which
needs their documents.

Deterministic Python tools compute every number; each stage then runs a CrewAI crew that
interprets them (analyze: Data Analyst, model: Data Scientist, investigate: Investigation,
report: Engineering Report). Crew outputs are checked deterministically (report_checks.json).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from crewai.flow.flow import Flow, listen, or_, router, start
from pydantic import BaseModel, Field, PrivateAttr

from foresight.analytics.stages import (
    StageResult,
    run_analyze,
    run_investigate,
    run_model,
    run_report,
)
from foresight.data.ingest import run_ingest
from foresight.progress import ProgressTracker, new_run_id
from foresight.rag.index import CHUNKS_FILE
from foresight.registry import record_run
from foresight.settings import Settings, load_settings
from foresight.utils.logging import get_logger, setup_logging
from foresight.utils.manifest import build_manifest, write_manifest
from foresight.utils.seeds import set_seeds
from foresight.validation.gates import (
    DATA_CONTRACT,
    EVIDENCE_PRESENT,
    FEATURES_PRESENT,
    GateResult,
    GateStatus,
    run_gate,
)

log = get_logger("flow")

OK = "ok"
FAILED = "failed"


class ForesightState(BaseModel):
    run_id: str = ""
    run_dir: str = ""
    status: str = "pending"
    stages_completed: list[str] = Field(default_factory=list)
    gates: list[GateResult] = Field(default_factory=list)
    failure_reason: str | None = None
    durations: dict[str, float] = Field(default_factory=dict)
    validation: dict | None = None
    feature_checks: dict | None = None
    evidence_checks: dict | None = None
    report_checks: dict | None = None
    crew_usage: dict[str, dict] = Field(default_factory=dict)
    stage_error: str | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    data_checksums: dict[str, str] = Field(default_factory=dict)


class ForesightFlow(Flow[ForesightState]):
    settings: Settings = Field(default_factory=load_settings)
    dataset: Path | None = None
    tracker: ProgressTracker | None = None
    continue_run: bool = False  # `resume` is taken by CrewAI's Flow
    background_crews: bool = True
    _pending: dict[str, Future] = PrivateAttr(default_factory=dict)
    _executor: ThreadPoolExecutor | None = PrivateAttr(default=None)

    @property
    def executor(self) -> ThreadPoolExecutor | None:
        if not self.background_crews:
            return None
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="crew")
        return self._executor

    def _join_crews(self) -> None:
        """Wait for the crews running in the background and take over their outputs; a crew
        that failed fails its stage."""
        for name, future in list(self._pending.items()):
            try:
                crew = future.result()  # its stage record was updated when it finished
                self.state.artifacts.update(crew.artifacts)
                self.state.crew_usage.update(crew.crew_usage)
            except Exception as exc:  # reported like a stage error, never a crash
                log.exception("crew of stage %s failed", name)
                self.state.stage_error = self.state.stage_error or f"{name} crew error: {exc}"
                stage = next((s for s in self.tracker.progress.stages if s.name == name), None)
                if stage is not None:
                    stage.crew_status = "failed"
                    self.tracker.save()
            del self._pending[name]
        if self._executor is not None:  # no crew starts after this point
            self._executor.shutdown(wait=False)
            self._executor = None
    def _reuse(self, name: str, checks_attr: str | None) -> bool:
        """A resumed run takes over a stage that finished before the interruption (its files,
        checks and crew usage); ingest is always redone (about a second, and it re-reads the
        data checksums)."""
        resumable = self.continue_run and name != "ingest"
        stage = self.tracker.finished_stage(name) if resumable else None
        if stage is None:
            return False
        self.state.artifacts.update(stage.artifacts)
        self.state.crew_usage.update(stage.crew_usage)
        if checks_attr and stage.checks is not None:
            setattr(self.state, checks_attr, stage.checks)
        self.state.stages_completed.append(name)
        self.state.durations[name] = stage.seconds or 0.0
        log.info("stage %s reused from before the interruption", name)
        return True

    def _stage(self, name: str, work: Callable[[], StageResult] | None = None,
               checks_attr: str | None = None) -> None:
        """Run one stage; an exception is recorded and routed to handle_failure."""
        if self.state.stage_error or self._reuse(name, checks_attr):
            return
        start_time = time.perf_counter()
        result = None
        self.tracker.stage_started(name)
        try:
            if work is None:
                Path(self.state.run_dir, f"{name}.json").write_text(
                    json.dumps({"stage": name, "placeholder": True}), encoding="utf-8")
            else:
                result = work()
                if result.pending is not None:
                    self._pending[name] = result.pending
                self.state.artifacts.update(result.artifacts)
                self.state.crew_usage.update(result.crew_usage)
                if checks_attr and result.checks is not None:
                    setattr(self.state, checks_attr, result.checks.model_dump(mode="json"))
        except Exception as exc:  # fail gracefully: report it, never crash the app
            log.exception("stage %s failed", name)
            self.state.stage_error = f"{name} stage error: {exc}"
            self.tracker.stage_finished(name, time.perf_counter() - start_time, ok=False)
            return
        self.state.stages_completed.append(name)
        self.state.durations[name] = round(time.perf_counter() - start_time, 4)
        self.tracker.stage_finished(
            name, self.state.durations[name], artifacts=result.artifacts if result else None,
            checks=getattr(self.state, checks_attr) if checks_attr else None,
            crew_usage=result.crew_usage if result else None)
        log.info("stage %s completed in %.1fs", name, self.state.durations[name])

    def _gate(self, name: str) -> str:
        if self.state.stage_error:
            self.state.failure_reason = self.state.stage_error
            return FAILED
        result = run_gate(name, self.state)
        self.state.gates.append(result)
        self.tracker.gate(name, result.status.value, result.messages)
        log.log(
            40 if result.blocks else 30 if result.status == GateStatus.WARNING else 20,
            "gate %s: %s %s",
            name,
            result.status,
            "; ".join(result.messages),
        )
        if result.blocks:
            self.state.failure_reason = f"{name}: " + "; ".join(result.messages)
            return FAILED
        return OK

    @property
    def _run_dir(self) -> Path:
        return Path(self.state.run_dir)

    def _ingest(self) -> StageResult:
        result = run_ingest(self.settings, self._run_dir, self.dataset)
        self.state.data_checksums = result.checksums
        return StageResult(artifacts=result.artifacts, checks=result.validation)

    @start()
    def ingest(self):
        if not self.state.run_id:
            self.state.run_id = new_run_id()
        run_dir = self.settings.resolve(self.settings.paths.runs_dir) / self.state.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self.state.run_dir = str(run_dir)
        self.state.status = "running"
        if self.tracker is None:
            self.tracker = ProgressTracker.create(
                run_dir, self.state.run_id, "Uploaded CSV" if self.dataset else None)
        self.tracker.running()
        setup_logging(self.settings.resolve(self.settings.paths.logs_dir), self.state.run_id)
        set_seeds(self.settings.seed)
        log.info("run %s started (mock_llm=%s)", self.state.run_id, self.settings.mock_llm)
        self._stage("ingest", self._ingest, "validation")

    @router(ingest)
    def data_contract_gate(self):
        return "data_ok" if self._gate(DATA_CONTRACT) == OK else FAILED

    @listen("data_ok")
    def analyze(self):
        self._stage("analyze", lambda: run_analyze(self.settings, self._run_dir, self.tracker,
                                                   self.executor), "feature_checks")

    @router(analyze)
    def features_gate(self):
        return "features_ok" if self._gate(FEATURES_PRESENT) == OK else FAILED

    @listen("features_ok")
    def model(self):
        self._stage("model", lambda: run_model(self.settings, self._run_dir, self.tracker,
                                               self.executor))

    @listen(model)
    def investigate(self):
        self._stage("investigate",
                    lambda: run_investigate(self.settings, self._run_dir, self.tracker),
                    "evidence_checks")

    @router(investigate)
    def evidence_gate(self):
        return "evidence_ok" if self._gate(EVIDENCE_PRESENT) == OK else FAILED

    @listen("evidence_ok")
    def report(self):
        self._join_crews()  # the report needs the insights and the model card
        self._stage("report", lambda: run_report(self.settings, self._run_dir, self.tracker),
                    "report_checks")

    @router(report)
    def report_done(self):
        if self.state.stage_error:
            self.state.failure_reason = self.state.stage_error
            return FAILED
        return "reported"

    @listen("reported")
    def finalize(self):
        self.state.status = "success"
        self._write_manifest()
        self.tracker.finish("success")
        record_run(Path(self.state.run_dir), self.settings)

    @listen(or_(FAILED))
    def handle_failure(self):
        self._join_crews()  # no crew may still write files after the failure report
        if self.state.stage_error and not self.state.failure_reason:
            self.state.failure_reason = self.state.stage_error
        self.state.status = "failed"
        report = (
            f"# Run {self.state.run_id} stopped\n\n"
            f"**Reason:** {self.state.failure_reason}\n\n"
            f"**Completed stages:** {', '.join(self.state.stages_completed) or 'none'}\n"
        )
        Path(self.state.run_dir, "failure_report.md").write_text(report, encoding="utf-8")
        log.error("run %s failed: %s", self.state.run_id, self.state.failure_reason)
        self._write_manifest()
        self.tracker.finish("failed", self.state.failure_reason)
        record_run(Path(self.state.run_dir), self.settings)

    def _write_manifest(self) -> None:
        chunks = Path(self.state.run_dir) / CHUNKS_FILE
        rag = json.loads(chunks.read_text(encoding="utf-8"))["params"] if chunks.exists() \
            else None
        manifest = build_manifest(
            self.state.run_id,
            self.settings,
            status=self.state.status,
            stages_completed=self.state.stages_completed,
            gates=[g.model_dump() for g in self.state.gates],
            durations_s=self.state.durations,
            crew_usage=self.state.crew_usage,
            report_checks=(self.state.report_checks or {}).get("counts"),
            rag_index=rag,
            data_sha256=self.state.data_checksums,
            artifacts=sorted(Path(p).name for p in self.state.artifacts.values()),
        )
        write_manifest(manifest, Path(self.state.run_dir) / "run_manifest.json")



def run_pipeline(settings: Settings | None = None, run_id: str | None = None,
                 dataset: Path | None = None, tracker: ProgressTracker | None = None,
                 resume: bool = False) -> ForesightState:
    """Run the whole Flow. ``dataset`` is an uploaded CSV (default: the built-in SECOM files);
    ``tracker`` lets the background runner share progress.json (and add a heartbeat);
    ``resume`` continues an interrupted run, reusing the stages it had finished."""
    flow = ForesightFlow(settings=settings or load_settings(), dataset=dataset, tracker=tracker,
                         continue_run=resume, suppress_flow_events=True)
    flow.kickoff(inputs={"run_id": run_id} if run_id else None)
    return flow.state
