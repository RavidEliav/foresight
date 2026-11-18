"""Deterministic checks on the crews' markdown outputs (engineering safety).

- required sections are present
- every sensor name mentioned exists in the cleaned dataset
- numbers can be traced to the run's summary files (or were derived from them)
- facts in the investigation cite a source file
- hypotheses follow the confidence rubric ("high" needs q < 0.001 and a second signal)
- the investigation's structured summary matches it (same hypotheses and confidence levels)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from foresight.crews.facts import allowed_numbers
from foresight.crews.summary import SUMMARY_FILE
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
# Independent second signals the rubric accepts (effect size is part of the same test)
SECOND_SIGNAL = re.compile(r"out[- ]of[- ](?:control[- ])?limits?|importance|anomal",
                           re.IGNORECASE)
HIGH_CONFIDENCE_Q = 0.001
# Causal claims the rules forbid ("is associated with" is the allowed wording). Negations such
# as "not a proven cause" or "rather than causes", and "leads to verify" (leads as a noun), do
# not count.
CAUSAL_TERMS = (r"(?:contribut(?:es|ed|ing)\s+to|contributing\s+factor|caused\s+by|causes|"
                r"causing|leads?\s+to|leading\s+to|drives|driving)")
CAUSAL = re.compile(rf"\b{CAUSAL_TERMS}\b(?!\s+(?:verify|check|investigate|follow))",
                    re.IGNORECASE)
NEGATED_CAUSAL = re.compile(rf"\b(?:not|never|no|cannot|rather\s+than)\s+(?:[\w'-]+\s+){{0,3}}?"
                            rf"(?:{CAUSAL_TERMS}|causes?)\b|\broot\s+causes?\b", re.IGNORECASE)


def causal_problems(text: str) -> list[str]:
    """Causal wording outside Background sentences (those restate general knowledge) and
    outside negations."""
    claims = re.sub(r"Background:.*?\[background:[^\]]*\]", "", text,
                    flags=re.IGNORECASE | re.DOTALL)
    claims = NEGATED_CAUSAL.sub("", claims)
    return sorted({m.group(0).lower() for m in CAUSAL.finditer(claims)})


def causal_check(name: str, text: str) -> Check:
    found = causal_problems(text)
    return Check(name=f"{name}: no causal claims",
                 status=GateStatus.WARNING if found else GateStatus.PASS,
                 message=f"causal wording in hypotheses: {', '.join(found)} (write \"is "
                         "associated with\")" if found
                 else "hypotheses state associations, not causes")


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
    lines included). A list item ends at a blank line followed by unindented text, as in
    markdown; a sub-heading keeps its body."""
    items: list[str] = []
    heading = blank = False
    for line in text.splitlines():
        if re.match(r"^\s*\d+[.)]\s", line) or re.match(r"^#{2,6}\s", line):
            items.append(line)
            heading, blank = line.startswith("#"), False
        elif not line.strip():
            blank = True
        elif items and items[-1] and (heading or not blank or line[:1].isspace()):
            items[-1] += " " + line.strip()
            blank = False
        else:
            items.append("")  # text outside the list closes the current item
            blank = False
    return [item for item in items if item]


def confidence_problems(hypotheses: list[str]) -> list[str]:
    """Hypotheses that state no confidence level, or claim high confidence without citing
    q < 0.001 and naming a second, independent signal (the rubric in the investigation
    prompt)."""
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
            elif not SECOND_SIGNAL.search(item):
                problems.append(f"#{i} is 'high' without a second signal (out-of-limit "
                                "rate, model importance or anomaly flags)")
    return problems


def _sensor_check(name: str, text: str, known_sensors: set[str]) -> Check:
    unknown = sorted(set(SENSOR.findall(text)) - known_sensors)
    return Check(
        name=f"{name}: sensor names",
        status=GateStatus.WARNING if unknown else GateStatus.PASS,
        message=f"unknown sensors mentioned: {', '.join(unknown[:5])}" if unknown
        else "every sensor mentioned exists in the data")


def _number_check(name: str, text: str, allowed: set[str]) -> Check:
    numbers = checkable_numbers(text)
    untraced = [n for n in numbers if not traced(n, allowed)]
    share = 1 - len(untraced) / len(numbers) if numbers else 1.0
    return Check(
        name=f"{name}: traceable numbers",
        status=GateStatus.PASS if share >= TRACEABLE_SHARE else GateStatus.WARNING,
        message=f"{share:.0%} of {len(numbers)} numbers found in the run files"
        + (f"; not found: {', '.join(untraced[:5])}" if untraced else ""))


def check_summary_output(text: str, run_dir: Path, known_sensors: set[str],
                         allowed: set[str]) -> list[Check]:
    """investigation_summary.json: valid, consistent with investigation.md, known sensors and
    traceable numbers in its prose."""
    from foresight.crews.summary import InvestigationSummary, check_summary, summary_text

    path = run_dir / "investigation.md"
    hypotheses = (numbered_items(section(path.read_text(encoding="utf-8"), "Hypotheses"))
                  if path.exists() else [])
    checks = check_summary(text, run_dir, hypotheses)
    if checks[0].status == GateStatus.PASS:
        summary = InvestigationSummary.model_validate_json(text)
        prose = summary_text(summary)
        claims = "\n".join([summary.headline, *(f"{h.title} {h.evidence}"
                                                for h in summary.hypotheses)])
        checks += [_sensor_check(SUMMARY_FILE, prose, known_sensors),
                   _number_check(SUMMARY_FILE, prose, allowed),
                   causal_check(SUMMARY_FILE, claims)]
    return checks


def check_output(name: str, text: str, run_dir: Path, known_sensors: set[str],
                 allowed: set[str],
                 knowledge: dict[str, set[str]] | None = None) -> list[Check]:
    if name == SUMMARY_FILE:
        return check_summary_output(text, run_dir, known_sensors, allowed)
    present = headings(text)
    missing = [s for s in REQUIRED_SECTIONS.get(name, [])
               if not any(h.startswith(s.lower()) for h in present)]
    checks = [Check(
        name=f"{name}: sections",
        status=GateStatus.WARNING if missing else GateStatus.PASS,
        message=f"missing sections: {', '.join(missing)}" if missing
        else f"all {len(REQUIRED_SECTIONS.get(name, []))} required sections present")]
    checks.append(_sensor_check(name, text, known_sensors))
    checks.append(_number_check(name, text, allowed))

    if name == "investigation.md":
        facts_text = section(text, "Facts")
        facts = [line for line in facts_text.splitlines()
                 if line.strip().startswith(("-", "*"))]
        cited = [line for line in facts if "[source:" in line.lower()]
        checks.append(Check(
            name=f"{name}: cited facts",
            status=GateStatus.PASS if facts and len(cited) == len(facts) else GateStatus.WARNING,
            message=f"{len(cited)} of {len(facts)} facts cite a source file"))
        if (run_dir / "similar_runs.json").exists():
            problem = similar_evidence_problem(facts_text, run_dir)
            checks.append(Check(
                name=f"{name}: similar-run evidence",
                status=GateStatus.WARNING if problem else GateStatus.PASS,
                message=problem or "Facts report the overall similar-run comparison"))

    if name in ("investigation.md", "engineering_report.md"):
        hypotheses = numbered_items(section(text, "Hypotheses"))
        problems = confidence_problems(hypotheses)
        checks.append(Check(
            name=f"{name}: confidence rubric",
            status=GateStatus.WARNING if problems or not hypotheses else GateStatus.PASS,
            message="no numbered hypotheses found" if not hypotheses
            else "; ".join(problems) if problems
            else f"all {len(hypotheses)} hypotheses follow the confidence rubric"))
        checks.append(causal_check(name, section(text, "Hypotheses")))
        checks.append(background_check(name, text, knowledge))
    return checks


def similar_evidence_problem(facts_text: str, run_dir: Path) -> str | None:
    """The Facts must report the overall similar-run comparison (both neighbour fail shares),
    not only anecdotes about single runs."""
    summary = json.loads((run_dir / "similar_runs.json").read_text(encoding="utf-8"))
    shares = [summary.get("neighbour_fail_share_for_failing_test_runs"),
              summary.get("neighbour_fail_share_for_passing_test_runs")]
    if "similar_runs.json" not in facts_text:
        return "Facts do not report the similar-run evidence [source: similar_runs.json]"
    if None in shares:
        return None
    wanted = [{f"{v * 100:.{d}f}%" for d in (1, 2)} | {f"{v:.{d}f}" for d in (3, 4)}
              for v in shares]
    found = set(re.findall(r"(?<![\d.])\d+(?:\.\d+)?%?", facts_text))
    if not all(forms & found for forms in wanted):
        return ("Facts must report the overall similar-run comparison: neighbours of failing "
                f"test runs failed {shares[0]:.1%}, of passing test runs {shares[1]:.1%} "
                "[source: similar_runs.json]")
    rates = [*shares, summary.get("train_fail_rate") or 0, summary.get("explained_variance") or 0]
    allowed = {f"{v * 100:.{d}f}%" for v in rates for d in (0, 1, 2)}
    allowed |= set(re.findall(r"\d+(?:\.\d+)?%", summary.get("method", "")))
    for line in facts_text.splitlines():
        if "similar_runs.json" in line:
            invented = set(re.findall(r"(?<![\d.])\d+(?:\.\d+)?%", line)) - allowed
            if invented:
                return (f"a run's few similar past runs are not a failure rate "
                        f"({', '.join(sorted(invented))}); report counts such as '2 of 5'")
    return None


FAITHFUL_SIMILARITY = 0.45  # a Background sentence must be this close to the passage it cites


def background_sentence(text: str, start: int) -> str:
    """The claim a background citation starting at ``start`` supports: from the last
    "Background:" (or the previous sentence end) up to the citation."""
    before = text[:start].rstrip()
    begin = before.lower().rfind("background:")
    if begin < 0:
        stops = [m.end() for m in re.finditer(r"[.!?]\s|\n", before[:-1])]
        begin = stops[-1] if stops else 0
    else:
        begin += len("background:")
    return before[begin:].strip(" .*")


def unfaithful_backgrounds(text: str) -> list[str]:
    """Background sentences that do not match the passage they cite (embedding similarity
    below FAITHFUL_SIMILARITY; a heuristic, the same model as the knowledge search)."""
    from foresight.rag.index import _embedder, knowledge_index
    from foresight.rag.knowledge import BACKGROUND
    from foresight.settings import load_settings

    settings = load_settings()
    index = knowledge_index(settings)
    problems = []
    for match in BACKGROUND.finditer(text):
        file, sec = match.group(1).strip(), match.group(2).strip().lower()
        rows = [i for i, c in enumerate(index.chunks)
                if c.source == file and c.section.lower() == sec]
        claim = background_sentence(text, match.start())
        if not rows or not claim:
            continue
        vector = _embedder(settings).embed([claim])[0]
        score = max(float(index.vectors[i] @ vector) for i in rows)
        if score < FAITHFUL_SIMILARITY:
            problems.append(f"\"{claim[:60]}...\" does not match {file} § {match.group(2)} "
                            f"(similarity {score:.2f})")
    return problems


def background_check(name: str, text: str, knowledge: dict[str, set[str]] | None) -> Check:
    """Background citations point at a real knowledge section and stay out of Facts; the
    investigation must cite at least one (requirements §18.2)."""
    from foresight.rag.knowledge import background_citations, known_sections
    from foresight.settings import load_settings

    knowledge = known_sections(load_settings()) if knowledge is None else knowledge
    citations = background_citations(text)
    unknown = [f"{f} § {s}" for f, s in citations
               if s.lower() not in knowledge.get(f, set())]
    in_facts = background_citations(section(text, "Facts"))
    hypotheses = section(text, "Hypotheses")
    in_items = sum(len(background_citations(item)) for item in numbered_items(hypotheses))
    loose = len(background_citations(hypotheses)) - in_items
    problems = []
    if unknown:
        problems.append(f"unknown background sources: {', '.join(unknown[:3])}")
    if in_facts:
        problems.append("background cited in Facts (background is never evidence)")
    if loose > 0:
        problems.append("background must support a numbered hypothesis, not stand on its own")
    if not citations and name == "investigation.md":
        problems.append("no hypothesis cites a Background source "
                        "[background: <file> § <section>]")
    if citations and not unknown:
        problems += unfaithful_backgrounds(text)
    return Check(name=f"{name}: background sources",
                 status=GateStatus.WARNING if problems else GateStatus.PASS,
                 message="; ".join(problems) if problems
                 else f"{len(citations)} background citation(s), from the knowledge base and "
                      "consistent with their sources" if citations else "no background cited")


def known_sensor_names(run_dir: Path) -> set[str]:
    path = run_dir / "clean_data.csv"
    if not path.exists():
        return set()
    return {c for c in pd.read_csv(path, nrows=0).columns if c.startswith("f_")}


def check_outputs(run_dir: Path, names: list[str],
                  allowed: set[str] | None = None) -> ValidationSummary:
    """``allowed`` (numbers that count as traceable) can be given by a background crew, which
    takes it when it starts, so its checks match a sequential run."""
    from foresight.rag.knowledge import known_sections
    from foresight.settings import load_settings

    sensors = known_sensor_names(run_dir)
    allowed = allowed_numbers(run_dir) if allowed is None else allowed
    knowledge = known_sections(load_settings())
    checks: list[Check] = []
    for name in names:
        path = run_dir / name
        if not path.exists():
            checks.append(Check(name=f"{name}: exists", status=GateStatus.ERROR,
                                message="output file was not written"))
            continue
        checks += check_output(name, path.read_text(encoding="utf-8"), run_dir, sensors,
                               allowed, knowledge)
    return ValidationSummary.from_checks(checks)
