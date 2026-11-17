"""Deterministic drafts returned by the mock LLM (MOCK_LLM=true).

They are built only from the run's facts, follow the same required sections as the real crews,
and pass the same output checks. Every document is marked as a mock draft.
"""

from __future__ import annotations

import re
from pathlib import Path

from foresight.crews.facts import all_facts, pct, read

MOCK_NOTE = "_Draft generated in mock mode (no LLM). Numbers come from the run files._"


def _bullets(text: str, limit: int | None = None, start: int = 0) -> str:
    lines = [line for line in text.splitlines() if line.startswith("- ")]
    return "\n".join(lines[start:limit])


def _top_sensors(run_dir: Path, n: int = 3) -> list[dict]:
    return read(run_dir, "eda_summary.json").get("top_discriminating_features", [])[:n]


def insights(run_dir: Path) -> str:
    f = all_facts(run_dir)
    profile = read(run_dir, "data_profile.json")
    sensors = ", ".join(s["feature"] for s in _top_sensors(run_dir)) or "none"
    return f"""# Insights

{MOCK_NOTE}

## Summary
- {profile.get('rows', 'n/a')} production runs were analysed; the fail rate was \
{pct(profile.get('fail_rate', 0))} [source: data_profile.json]
- The sensors that differ most between failing and passing runs are {sensors} \
[source: eda_summary.json]

## Data quality
{_bullets(f['data_facts'])}

## What happened
{_bullets(f['eda_facts'], 4)}

## Notable sensors
{_bullets(f['eda_facts'], start=4) or '- none'}

## Business implications
- Failing runs are rare and the fail rate changes over time, so monitoring needs to adapt.
- The listed sensors are where an engineer should look first; they are associations, not
  proven causes.
"""


def model_card(run_dir: Path) -> str:
    f = all_facts(run_dir)
    mm = read(run_dir, "model_metrics.json")
    t, ci = mm.get("test_metrics", {}), mm.get("test_metrics_ci95", {})
    rows = "\n".join(
        f"| {label} | {t[key]:.3f} | {ci[key][0]:.3f}-{ci[key][1]:.3f} |"
        for key, label in (("pr_auc", "PR-AUC"), ("recall_fail", "Fail recall"),
                           ("precision_fail", "Precision"),
                           ("balanced_accuracy", "Balanced accuracy"))
        if key in t and key in ci)
    return f"""# Model card

{MOCK_NOTE}

## Model purpose
Rank production runs by their risk of failing, so engineers can review the riskiest runs first.
Selected model: {mm.get('selected_model', 'n/a')}.

## Training data
{_bullets(f['model_facts'], 1)}
{_bullets(f['data_facts'], 3)}

## Metrics
| Metric | Test value | 95% CI |
|---|---|---|
{rows}

{_bullets(f['model_facts'])}

## Limitations
- Few failing runs in the test period, so the confidence intervals are wide.
- The process drifts over time; a fixed threshold tuned on older runs stopped raising alarms.
- Sensor names are anonymized, so results point to where to look, not to physical causes.

## Ethical considerations
- Missed failures can reach customers; false alarms cost engineering time, scrap or rework.
- The model supports an engineer's judgement and must not make release decisions on its own.

## Intended use
Decision support for process engineers, with an alarm budget and regular retraining.
"""


def _background(query: str) -> str:
    """A cited Background sentence from the knowledge base (general knowledge, not evidence)."""
    from foresight.rag.knowledge import cite, search_knowledge
    from foresight.settings import load_settings

    hits = search_knowledge(query, load_settings(), k=1)
    if not hits:
        return ""
    first = re.split(r"(?<=[.!?])\s+", hits[0].chunk.text.strip())[0]
    return f" Background: {first} {cite(hits[0])}"


def investigation(run_dir: Path) -> str:
    f = all_facts(run_dir)
    sensors = _top_sensors(run_dir)
    anomalies = read(run_dir, "anomaly_summary.json")
    out_of_limit = anomalies.get("sensors_more_often_out_of_limit_in_fails", [])[:2]
    hypotheses = []
    for i, s in enumerate(sensors, 1):
        hypotheses.append(
            f"{i}. **Hypothesis (medium confidence):** process conditions measured by "
            f"{s['feature']} are associated with failing runs ({s['direction']}, q = "
            f"{s['q_value']:.2g}). This is a correlation, not a proven cause.")
    if out_of_limit:
        names = ", ".join(r["feature"] for r in out_of_limit)
        hypotheses.append(
            f"{len(hypotheses) + 1}. **Hypothesis (low confidence):** excursions outside control "
            f"limits on {names} accompany some failures.")
    hypotheses.append(
        f"{len(hypotheses) + 1}. **Hypothesis (medium confidence):** the change in fail rate "
        "between months reflects a process or product-mix change over time (drift)."
        + _background("process drift over time between maintenance events"))
    verification = "\n".join(
        f"- Hypothesis {i}: compare recent failing and passing runs on the named signal and "
        "check equipment and recipe logs for the same period."
        for i in range(1, len(hypotheses) + 1))
    return f"""# Investigation

{MOCK_NOTE}

## Facts
{_bullets(f['anomaly_facts'])}
{_bullets(f['eda_facts'], 2)}

## Assumptions
- Labels (pass/fail) are correct and timestamps reflect production order.
- Sensors are comparable across the whole period after cleaning.
- Missing values are not themselves a signal, except through the missing_count feature.

## Hypotheses
{chr(10).join(hypotheses)}

## Suggested verification
{verification}
"""


def investigation_summary(run_dir: Path) -> str:
    """The structured summary of the mock investigation (investigation_summary.json)."""
    import json
    import textwrap

    from foresight.crews.checks import CONFIDENCE, numbered_items, section

    def short(text: str, width: int) -> str:
        text = textwrap.shorten(text, width=width, placeholder="...")
        return text[:1].upper() + text[1:]

    text = investigation(run_dir)
    findings = []
    for line in section(text, "Facts").splitlines():
        source = re.search(r"\[source:\s*([^\]]+)\]", line)
        body = re.sub(r"\s*\[source:[^\]]*\]", "", line[2:]).strip()
        if line.startswith("- ") and source and 10 <= len(body) <= 220:
            findings.append({"text": body, "source": source.group(1).strip()})
    checks = [line[2:].split(": ", 1)[-1] for line in
              section(text, "Suggested verification").splitlines() if line.startswith("- ")]
    cards = []
    for i, item in enumerate(numbered_items(section(text, "Hypotheses")), start=1):
        level = CONFIDENCE.search(item)
        body = re.sub(r"^\s*\d+[.)]\s*(\*\*[^*]+\*\*\s*)?", "", item).split(" Background:")[0]
        cards.append({"number": i, "title": short(body.split(". ")[0], 120),
                      "confidence": (level.group(1) or level.group(2)).lower(),
                      "evidence": short(body, 220),
                      "verify": short(checks[i - 1] if i <= len(checks) else body, 220)})
    return json.dumps({
        "headline": "Mock draft (no LLM): a few sensors differ between failing and passing runs "
                    "and anomaly flags add a second, weaker signal. The hypotheses are leads "
                    "for an engineer, not proven causes.",
        "key_findings": findings[:3], "hypotheses": cards}, indent=2)


def engineering_report(run_dir: Path, investigation_text: str | None = None) -> str:
    f = all_facts(run_dir)
    risk = read(run_dir, "risk_summary.json")
    chosen = risk.get("recommended_ranking", "model")
    best = risk.get("test", {}).get(chosen, {})
    detected = (f"- The recommended risk ranking ({chosen}) flags {best.get('alarms', 'n/a')} "
                f"test-period runs and finds {best.get('fails_found', 'n/a')} of "
                f"{best.get('fails_total', 'n/a')} failing runs [source: risk_summary.json]")
    sensors = "\n".join(
        f"- {s['feature']}: {s['direction']} (q = {s['q_value']:.2g}) [source: eda_summary.json]"
        for s in _top_sensors(run_dir))
    investigation_text = investigation_text or investigation(run_dir)
    hypotheses = investigation_text.split("## Hypotheses", 1)[-1].split("##", 1)[0].strip()
    return f"""# Engineering report

{MOCK_NOTE}

## What was detected
{detected}
{_bullets(f['anomaly_facts'], 1)}

## Supporting statistical evidence
{_bullets(f['model_facts'], 6)}
{_bullets(f['eda_facts'], 2)}

## Important abnormal parameters
{sensors or '- none'}

## Hypotheses
{hypotheses}

## Recommended next steps
- Review the flagged runs with the process team, starting with the highest risk scores.
- Check equipment and recipe logs around the named sensors for the flagged periods.
- Retrain the model on recent runs at a regular interval because the process drifts.

## Data quality and model limitations
{_bullets(f['data_facts'], 2)}
- Few failing runs in the test period; confidence intervals are wide.
- Sensor names are anonymized; findings are associations, not confirmed root causes.
"""


def intermediate(facts: str) -> str:
    return _bullets(facts) or "- No facts available."


def draft_for(task_name: str, run_dir: Path, inputs: dict[str, str]) -> str:
    f = all_facts(run_dir)
    final = {
        "insights": lambda: insights(run_dir),
        "model_card": lambda: model_card(run_dir),
        "investigation": lambda: investigation(run_dir),
        "investigation_summary": lambda: investigation_summary(run_dir),
        "engineering_report": lambda: engineering_report(run_dir, inputs.get("investigation")),
        "report_draft": lambda: engineering_report(run_dir, inputs.get("investigation")),
    }
    if task_name in final:
        return final[task_name]()
    source = {"data_quality_review": "data_facts", "eda_findings": "eda_facts",
              "evaluation_review": "model_facts", "limitations_ethics": "model_facts",
              "anomaly_review": "anomaly_facts", "signal_review": "eda_facts"}
    return intermediate(f[source.get(task_name, "data_facts")])
