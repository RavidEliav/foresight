"""Deterministic checks on the crews' markdown outputs (engineering safety).

- required sections are present
- every sensor name mentioned exists in the cleaned dataset
- numbers can be traced to the run's summary files (or were derived from them)
- facts in the investigation cite a source file
- hypotheses follow the confidence rubric ("high" needs q < 0.001)
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from foresight.crews.facts import allowed_numbers
from foresight.validation.contract import Check, ValidationSummary
from foresight.validation.gates import GateStatus

REQUIRED_SECTIONS = {
    "insights.md": ["Summary", "Data quality", "What happened", "Notable sensors",
                    "Business implications"],
    "model_card.md": ["Model purpose", "Training data", "Metrics", "Limitations",
                      "Ethical considerations", "Intended use"],
    "investigation.md": ["Facts", "Assumptions", "Hypotheses", "Suggested verification"],
    "engineering_report.md": ["What was detected", "Supporting statistical evidence",
                              "Important abnormal parameters", "Hypotheses",
                              "Recommended next steps", "Data quality and model limitations"],
}
SENSOR = re.compile(r"\bf_\d{3}\b")
# A signed number (the sign only when it isn't a range dash), thousands separators allowed;
# possessive/atomic parts stop "12.5-14.25" from backtracking to "12".
NUMBER = re.compile(r"(?:(?<![\w.%])-)?(?<![\w.:/])(?>\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?+%?+"
                    r"(?![\w:/])")
TRACEABLE_SHARE = 0.9
CONFIDENCE = re.compile(r"confidence[\s*:=_-]*(?:level)?[\s*:=_-]*(high|medium|low)\b"
                        r"|\b(high|medium|low)[\s*_-]+confidence", re.IGNORECASE)
Q_VALUE = re.compile(r"\bq(?:[-_ ]?value)?\s*(?:of|=|:|<|≤|≈)?\s*(\d+(?:\.\d+)?(?:e[-+]?\d+)?)",
                     re.IGNORECASE)
HIGH_CONFIDENCE_Q = 0.001


def headings(text: str) -> list[str]:
    return [h.strip().lower() for h in re.findall(r"^#{1,3}\s+(.+)$", text, re.MULTILINE)]


def section(text: str, title: str) -> str:
    """Body of the first heading that starts with ``title``, up to the next heading of the same
    or a higher level (sub-headings stay inside)."""
    body: list[str] = []
    level = None
    for line in text.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading and level is not None and len(heading.group(1)) <= level:
            break
        if heading and level is None:
            if heading.group(2).strip().lower().startswith(title.lower()):
                level = len(heading.group(1))
            continue
        if level is not None:
            body.append(line)
    return "\n".join(body)


def checkable_numbers(text: str) -> list[str]:
    """Numbers worth checking: decimals, percentages and integers of 10 or more (not dates,
    sensor ids, run ids in 'run 123', or list numbering)."""
    text = SENSOR.sub("", text)
    text = re.sub(r"\b\d{4}-\d{2}(?:-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?)?\b", "", text)
    text = re.sub(r"\b[Rr]uns?\s+#?\d+", "", text)
    text = re.sub(r"\bADR-\d+", "", text)
    found = []
    for token in NUMBER.findall(text):
        bare = token.rstrip("%").replace(",", "")
        if "." in bare or token.endswith("%") or abs(float(bare)) >= 10:
            found.append(token)
    return found


def traced(token: str, allowed: set[str]) -> bool:
    bare = token.rstrip("%")
    return any(t in allowed for t in (token, bare, bare.replace(",", "")))


def numbered_items(text: str) -> list[str]:
    """Split a markdown section into its numbered list items or sub-headings (continuation
    lines included)."""
    items: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\s*\d+[.)]\s", line) or re.match(r"^#{2,6}\s", line):
            items.append(line)
        elif items and line.strip():
            items[-1] += " " + line.strip()
    return items


def confidence_problems(hypotheses: list[str]) -> list[str]:
    """Hypotheses that state no confidence level, or claim high confidence without citing
    q < 0.001 (the rubric in the investigation prompt)."""
    problems = []
    for i, item in enumerate(hypotheses, start=1):
        match = CONFIDENCE.search(item)
        if not match:
            problems.append(f"#{i} has no confidence level")
            continue
        if (match.group(1) or match.group(2)).lower() == "high":
            qs = [float(q) for q in Q_VALUE.findall(item)]
            if not any(q < HIGH_CONFIDENCE_Q for q in qs):
                problems.append(f"#{i} is 'high' without q < {HIGH_CONFIDENCE_Q}")
    return problems


def check_output(name: str, text: str, run_dir: Path, known_sensors: set[str],
                 allowed: set[str]) -> list[Check]:
    present = headings(text)
    missing = [s for s in REQUIRED_SECTIONS.get(name, [])
               if not any(h.startswith(s.lower()) for h in present)]
    checks = [Check(
        name=f"{name}: sections",
        status=GateStatus.WARNING if missing else GateStatus.PASS,
        message=f"missing sections: {', '.join(missing)}" if missing
        else f"all {len(REQUIRED_SECTIONS.get(name, []))} required sections present")]

    unknown = sorted(set(SENSOR.findall(text)) - known_sensors)
    checks.append(Check(
        name=f"{name}: sensor names",
        status=GateStatus.WARNING if unknown else GateStatus.PASS,
        message=f"unknown sensors mentioned: {', '.join(unknown[:5])}" if unknown
        else "every sensor mentioned exists in the data"))

    numbers = checkable_numbers(text)
    untraced = [n for n in numbers if not traced(n, allowed)]
    share = 1 - len(untraced) / len(numbers) if numbers else 1.0
    checks.append(Check(
        name=f"{name}: traceable numbers",
        status=GateStatus.PASS if share >= TRACEABLE_SHARE else GateStatus.WARNING,
        message=f"{share:.0%} of {len(numbers)} numbers found in the run files"
        + (f"; not found: {', '.join(untraced[:5])}" if untraced else "")))

    if name == "investigation.md":
        facts = [line for line in section(text, "Facts").splitlines()
                 if line.strip().startswith(("-", "*"))]
        cited = [line for line in facts if "[source:" in line.lower()]
        checks.append(Check(
            name=f"{name}: cited facts",
            status=GateStatus.PASS if facts and len(cited) == len(facts) else GateStatus.WARNING,
            message=f"{len(cited)} of {len(facts)} facts cite a source file"))

    if name in ("investigation.md", "engineering_report.md"):
        hypotheses = numbered_items(section(text, "Hypotheses"))
        problems = confidence_problems(hypotheses)
        checks.append(Check(
            name=f"{name}: confidence rubric",
            status=GateStatus.WARNING if problems or not hypotheses else GateStatus.PASS,
            message="no numbered hypotheses found" if not hypotheses
            else "; ".join(problems) if problems
            else f"all {len(hypotheses)} hypotheses follow the confidence rubric"))
    return checks


def known_sensor_names(run_dir: Path) -> set[str]:
    path = run_dir / "clean_data.csv"
    if not path.exists():
        return set()
    return {c for c in pd.read_csv(path, nrows=0).columns if c.startswith("f_")}


def check_outputs(run_dir: Path, names: list[str]) -> ValidationSummary:
    sensors = known_sensor_names(run_dir)
    allowed = allowed_numbers(run_dir)
    checks: list[Check] = []
    for name in names:
        path = run_dir / name
        if not path.exists():
            checks.append(Check(name=f"{name}: exists", status=GateStatus.ERROR,
                                message="output file was not written"))
            continue
        checks += check_output(name, path.read_text(encoding="utf-8"), run_dir, sensors, allowed)
    return ValidationSummary.from_checks(checks)
