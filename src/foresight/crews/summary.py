"""The short, structured summary of an investigation (investigation_summary.json).

The Investigation crew writes it after investigation.md so the app can show a headline, a few
key findings and one card per hypothesis instead of the full text. Deterministic checks keep it
consistent with investigation.md: same hypotheses and confidence levels, real source files,
known sensors and traceable numbers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from foresight.validation.contract import Check
from foresight.validation.gates import GateStatus

SUMMARY_FILE = "investigation_summary.json"


class Finding(BaseModel):
    text: str = Field(min_length=10, max_length=220)
    source: str = Field(min_length=3, max_length=60)


class HypothesisCard(BaseModel):
    number: int = Field(ge=1)
    title: str = Field(min_length=10, max_length=120)
    confidence: Literal["high", "medium", "low"]
    evidence: str = Field(min_length=10, max_length=220)
    verify: str = Field(min_length=10, max_length=220)


class InvestigationSummary(BaseModel):
    headline: str = Field(min_length=20, max_length=300)
    key_findings: list[Finding] = Field(min_length=2, max_length=4)
    hypotheses: list[HypothesisCard] = Field(min_length=1, max_length=6)


def extract_json(text: str) -> str:
    """The JSON object inside an LLM answer (code fences or text around it are dropped);
    returned pretty-printed, or unchanged if there is no valid object."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return text.strip() + "\n"
    try:
        return json.dumps(json.loads(text[start:end + 1]), indent=2, ensure_ascii=False) + "\n"
    except json.JSONDecodeError:
        return text.strip() + "\n"


def load_summary(run_dir: Path) -> InvestigationSummary | None:
    """The run's summary if it exists and is valid (older runs have none)."""
    path = run_dir / SUMMARY_FILE
    if not path.exists():
        return None
    try:
        return InvestigationSummary.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError:
        return None


def summary_text(summary: InvestigationSummary) -> str:
    """All of the summary's prose, for the sensor and number checks."""
    parts = [summary.headline, *(f.text for f in summary.key_findings)]
    for h in summary.hypotheses:
        parts += [h.title, h.evidence, h.verify]
    return "\n".join(parts)


def check_summary(text: str, run_dir: Path, hypotheses: list[str]) -> list[Check]:
    """Schema, then consistency with investigation.md (``hypotheses`` are its numbered items)."""
    from foresight.crews.checks import CONFIDENCE

    name = SUMMARY_FILE
    try:
        summary = InvestigationSummary.model_validate_json(text)
    except ValidationError as exc:
        errors = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'json'}: {e['msg']}"
                           for e in exc.errors()[:3])
        return [Check(name=f"{name}: format", status=GateStatus.WARNING,
                      message=f"not a valid summary object ({errors})")]
    checks = [Check(name=f"{name}: format", status=GateStatus.PASS,
                    message=f"headline, {len(summary.key_findings)} key findings and "
                            f"{len(summary.hypotheses)} hypothesis cards")]

    problems = []
    if len(summary.hypotheses) != len(hypotheses):
        problems.append(f"{len(summary.hypotheses)} cards for {len(hypotheses)} hypotheses")
    for card, item in zip(summary.hypotheses, hypotheses, strict=False):
        match = CONFIDENCE.search(item)
        stated = (match.group(1) or match.group(2)).lower() if match else None
        if stated and card.confidence != stated:
            problems.append(f"card {card.number} says {card.confidence}, the investigation "
                            f"says {stated}")
    if [c.number for c in summary.hypotheses] != list(range(1, len(summary.hypotheses) + 1)):
        problems.append("cards must be numbered 1, 2, 3, ... in order")
    checks.append(Check(
        name=f"{name}: matches the investigation",
        status=GateStatus.WARNING if problems else GateStatus.PASS,
        message="; ".join(problems) if problems
        else "one card per hypothesis, with the same confidence levels"))

    bad = [f.source for f in summary.key_findings
           if not re.fullmatch(r"[\w.-]+\.(?:json|csv|md)", f.source)
           or not (run_dir / f.source).exists()]
    background = "background:" in summary_text(summary).lower()
    checks.append(Check(
        name=f"{name}: finding sources",
        status=GateStatus.WARNING if bad or background else GateStatus.PASS,
        message=(f"sources that are not files of this run: {', '.join(bad)}" if bad else "")
        + ("; " if bad and background else "")
        + ("background knowledge is never a finding" if background else "")
        or "every key finding cites a file of this run"))
    return checks
