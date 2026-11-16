"""Foresight CrewAI Flow.

Stage order: ingest -> [data contract gate] -> analyze -> [features gate] -> model
-> investigate -> [evidence gate] -> report. Any ERROR, or an exception inside a stage,
routes to handle_failure, which writes a failure report instead of crashing.

Deterministic Python tools compute every number; each stage then runs a CrewAI crew that
interprets them (analyze: Data Analyst, model: Data Scientist, investigate: Investigation,
report: Engineering Report). Crew outputs are checked deterministically (report_checks.json).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from crewai.flow.flow import Flow, listen, or_, router, start
from pydantic import BaseModel, Field

from foresight.analytics.stages import (
    StageResult,
    run_analyze,
    run_investigate,
    run_model,
    run_report,
)
from foresight.data.ingest import run_ingest
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

    def _stage(self, name: str, work: Callable[[], StageResult] | None = None,
               checks_attr: str | None = None) -> None:
        """Run one stage; an exception is recorded and routed to handle_failure."""
        if self.state.stage_error:
            return
        start_time = time.perf_counter()
        try:
            if work is None:
                Path(self.state.run_dir, f"{name}.json").write_text(
                    json.dumps({"stage": name, "placeholder": True}), encoding="utf-8")
            else:
                result = work()
                self.state.artifacts.update(result.artifacts)
                self.state.crew_usage.update(result.crew_usage)
                if checks_attr and result.checks is not None:
                    setattr(self.state, checks_attr, result.checks.model_dump(mode="json"))
        except Exception as exc:  # fail gracefully: report it, never crash the app
            log.exception("stage %s failed", name)
            self.state.stage_error = f"{name} stage error: {exc}"
            return
        self.state.stages_completed.append(name)
        self.state.durations[name] = round(time.perf_counter() - start_time, 4)
        log.info("stage %s completed in %.1fs", name, self.state.durations[name])

    def _gate(self, name: str) -> str:
        if self.state.stage_error:
            self.state.failure_reason = self.state.stage_error
            return FAILED
        result = run_gate(name, self.state)
        self.state.gates.append(result)
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
        result = run_ingest(self.settings, self._run_dir)
        self.state.data_checksums = result.checksums
        return StageResult(artifacts=result.artifacts, checks=result.validation)

    @start()
    def ingest(self):
        if not self.state.run_id:
            self.state.run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        run_dir = self.settings.resolve(self.settings.paths.runs_dir) / self.state.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self.state.run_dir = str(run_dir)
        self.state.status = "running"
        setup_logging(self.settings.resolve(self.settings.paths.logs_dir), self.state.run_id)
        set_seeds(self.settings.seed)
        log.info("run %s started (mock_llm=%s)", self.state.run_id, self.settings.mock_llm)
        self._stage("ingest", self._ingest, "validation")

    @router(ingest)
    def data_contract_gate(self):
        return "data_ok" if self._gate(DATA_CONTRACT) == OK else FAILED

    @listen("data_ok")
    def analyze(self):
        self._stage("analyze", lambda: run_analyze(self.settings, self._run_dir),
                    "feature_checks")

    @router(analyze)
    def features_gate(self):
        return "features_ok" if self._gate(FEATURES_PRESENT) == OK else FAILED

    @listen("features_ok")
    def model(self):
        self._stage("model", lambda: run_model(self.settings, self._run_dir))

    @listen(model)
    def investigate(self):
        self._stage("investigate", lambda: run_investigate(self.settings, self._run_dir),
                    "evidence_checks")

    @router(investigate)
    def evidence_gate(self):
        return "evidence_ok" if self._gate(EVIDENCE_PRESENT) == OK else FAILED

    @listen("evidence_ok")
    def report(self):
        self._stage("report", lambda: run_report(self.settings, self._run_dir), "report_checks")

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

    @listen(or_(FAILED))
    def handle_failure(self):
        self.state.status = "failed"
        report = (
            f"# Run {self.state.run_id} stopped\n\n"
            f"**Reason:** {self.state.failure_reason}\n\n"
            f"**Completed stages:** {', '.join(self.state.stages_completed) or 'none'}\n"
        )
        Path(self.state.run_dir, "failure_report.md").write_text(report, encoding="utf-8")
        log.error("run %s failed: %s", self.state.run_id, self.state.failure_reason)
        self._write_manifest()

    def _write_manifest(self) -> None:
        manifest = build_manifest(
            self.state.run_id,
            self.settings,
            status=self.state.status,
            stages_completed=self.state.stages_completed,
            gates=[g.model_dump() for g in self.state.gates],
            durations_s=self.state.durations,
            crew_usage=self.state.crew_usage,
            report_checks=(self.state.report_checks or {}).get("counts"),
            data_sha256=self.state.data_checksums,
            artifacts=sorted(Path(p).name for p in self.state.artifacts.values()),
        )
        write_manifest(manifest, Path(self.state.run_dir) / "run_manifest.json")


def run_pipeline(settings: Settings | None = None) -> ForesightState:
    flow = ForesightFlow(settings=settings or load_settings(), suppress_flow_events=True)
    flow.kickoff()
    return flow.state
