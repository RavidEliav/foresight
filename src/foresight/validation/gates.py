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


DATA_CONTRACT = "data_contract"
FEATURES_PRESENT = "features_present"
EVIDENCE_PRESENT = "evidence_present"

GATE_CHECKS: dict[str, GateCheck] = {
    DATA_CONTRACT: _placeholder(DATA_CONTRACT),
    FEATURES_PRESENT: _placeholder(FEATURES_PRESENT),
    EVIDENCE_PRESENT: _placeholder(EVIDENCE_PRESENT),
}


def run_gate(name: str, state: Any) -> GateResult:
    try:
        return GATE_CHECKS[name](state)
    except Exception as exc:  # a crashing check must stop the flow, not the app
        return GateResult(gate=name, status=GateStatus.ERROR, messages=[f"check crashed: {exc}"])
