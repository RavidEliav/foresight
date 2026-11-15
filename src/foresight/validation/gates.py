"""Generic validation gates used between Flow stages.

Each gate is a function ``(state) -> GateResult``. ERROR stops the Flow; WARNING lets it
continue but is reported. Each stage writes a
ValidationSummary to the Flow state; the gate after it reads that summary.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class GateStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class GateResult(BaseModel):
    gate: str
    status: GateStatus
    messages: list[str] = Field(default_factory=list)

    @property
    def blocks(self) -> bool:
        return self.status == GateStatus.ERROR


GateCheck = Callable[[Any], GateResult]


DATA_CONTRACT = "data_contract"
FEATURES_PRESENT = "features_present"
EVIDENCE_PRESENT = "evidence_present"

# Flow state attribute holding each gate's check summary (written by the stage before it).
GATE_SOURCES = {
    DATA_CONTRACT: "validation",
    FEATURES_PRESENT: "feature_checks",
    EVIDENCE_PRESENT: "evidence_checks",
}


def summary_check(gate: str) -> GateCheck:
    """Gate check that turns a stage's ValidationSummary (stored on the state) into a result."""

    def check(state: Any) -> GateResult:
        summary = getattr(state, GATE_SOURCES[gate], None)
        if not summary:
            return GateResult(gate=gate, status=GateStatus.ERROR,
                              messages=["no check results were produced"])
        status = GateStatus(summary["status"])
        wanted = {GateStatus.ERROR: "ERROR", GateStatus.WARNING: "WARNING"}.get(status)
        if wanted:
            messages = [f"{c['name']}: {c['message']}" for c in summary["checks"]
                        if c["status"] == wanted]
        else:
            messages = [f"all {len(summary['checks'])} checks passed"]
        return GateResult(gate=gate, status=status, messages=messages)

    return check


GATE_CHECKS: dict[str, GateCheck] = {name: summary_check(name) for name in GATE_SOURCES}


def run_gate(name: str, state: Any) -> GateResult:
    try:
        return GATE_CHECKS[name](state)
    except Exception as exc:  # a crashing check must stop the flow, not the app
        return GateResult(gate=name, status=GateStatus.ERROR, messages=[f"check crashed: {exc}"])
