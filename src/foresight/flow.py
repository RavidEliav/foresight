"""Foresight CrewAI Flow.

Stage order: ingest -> [data contract gate] -> analyze -> [features gate]
-> investigate -> [evidence gate] -> report -> finalize. Any ERROR routes to
handle_failure, which writes a failure report instead of crashing.

ingest is real (Phase 1: SECOM + Data Contract); the later stages are placeholders
until Phases 2-3.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from crewai.flow.flow import Flow, listen, or_, router, start
from pydantic import BaseModel, Field

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
    artifacts: dict[str, str] = Field(default_factory=dict)
    data_checksums: dict[str, str] = Field(default_factory=dict)


class ForesightFlow(Flow[ForesightState]):
    settings: Settings = Field(default_factory=load_settings)

    def _stage(self, name: str) -> None:
        start_time = time.perf_counter()
        run_dir = Path(self.state.run_dir)
        (run_dir / f"{name}.json").write_text(
            json.dumps({"stage": name, "placeholder": True}), encoding="utf-8"
        )
        self.state.stages_completed.append(name)
        self.state.durations[name] = round(time.perf_counter() - start_time, 4)
        log.info("stage %s completed", name)

    def _gate(self, name: str) -> str:
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
        start_time = time.perf_counter()
        result = run_ingest(self.settings, run_dir)
        self.state.validation = result.validation.model_dump(mode="json")
        self.state.artifacts.update(result.artifacts)
        self.state.data_checksums = result.checksums
        self.state.stages_completed.append("ingest")
        self.state.durations["ingest"] = round(time.perf_counter() - start_time, 4)
        log.info("stage ingest completed")

    @router(ingest)
    def data_contract_gate(self):
        return "data_ok" if self._gate(DATA_CONTRACT) == OK else FAILED

    @listen("data_ok")
    def analyze(self):
        self._stage("analyze")

    @router(analyze)
    def features_gate(self):
        return "features_ok" if self._gate(FEATURES_PRESENT) == OK else FAILED

    @listen("features_ok")
    def investigate(self):
        self._stage("investigate")

    @router(investigate)
    def evidence_gate(self):
        return "evidence_ok" if self._gate(EVIDENCE_PRESENT) == OK else FAILED

    @listen("evidence_ok")
    def report(self):
        self._stage("report")
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
            data_sha256=self.state.data_checksums,
            artifacts=sorted(Path(p).name for p in self.state.artifacts.values()),
        )
        write_manifest(manifest, Path(self.state.run_dir) / "run_manifest.json")


def run_pipeline(settings: Settings | None = None) -> ForesightState:
    flow = ForesightFlow(settings=settings or load_settings(), suppress_flow_events=True)
    flow.kickoff()
    return flow.state
