"""Generic validation gates used between Flow stages.

Each gate is a function ``(state) -> GateResult``. ERROR stops the Flow; WARNING lets it
continue but is reported. The registry starts with placeholder checks; the real Data
Contract and feature checks replace them in later phases.
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


def _placeholder(gate: str) -> GateCheck:
    def check(_state: Any) -> GateResult:
        return GateResult(gate=gate, status=GateStatus.PASS, messages=["placeholder check"])

    return check


def data_contract_check(state: Any) -> GateResult:
    """Turns the ingest stage's validation summary into a gate result."""
    summary = getattr(state, "validation", None)
    if not summary:
        return GateResult(gate=DATA_CONTRACT, status=GateStatus.ERROR,
                          messages=["no validation results were produced"])
    status = GateStatus(summary["status"])
    wanted = {GateStatus.ERROR: "ERROR", GateStatus.WARNING: "WARNING"}.get(status)
    if wanted:
        messages = [f"{c['name']}: {c['message']}" for c in summary["checks"]
                    if c["status"] == wanted]
    else:
        messages = [f"all {len(summary['checks'])} checks passed"]
    return GateResult(gate=DATA_CONTRACT, status=status, messages=messages)


DATA_CONTRACT = "data_contract"
FEATURES_PRESENT = "features_present"
EVIDENCE_PRESENT = "evidence_present"

GATE_CHECKS: dict[str, GateCheck] = {
    DATA_CONTRACT: data_contract_check,
    FEATURES_PRESENT: _placeholder(FEATURES_PRESENT),
    EVIDENCE_PRESENT: _placeholder(EVIDENCE_PRESENT),
}


def run_gate(name: str, state: Any) -> GateResult:
    try:
        return GATE_CHECKS[name](state)
    except Exception as exc:  # a crashing check must stop the flow, not the app
        return GateResult(gate=name, status=GateStatus.ERROR, messages=[f"check crashed: {exc}"])
