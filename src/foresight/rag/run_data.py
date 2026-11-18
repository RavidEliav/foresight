"""run_data.md: the run's tables as text, so "Ask Foresight" can answer about them.

The reports describe the run in prose; questions about the numbers behind the app's tables
(a run's risk score, its similar past runs, why its nearest distance is large) need the data
itself. This file is written from the run's JSON and CSV files only (numbers copied, nothing
computed by an LLM), one section per topic and one section per run that appears in a table, so
a question naming a run finds its section. It is indexed with the reports.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median

import pandas as pd

RUN_DATA_FILE = "run_data.md"
TABLE_FILES = ("model_metrics.json", "risk_summary.json", "anomaly_summary.json",
               "similar_runs.json")
FAR = 10  # a nearest distance this many times the typical one means no similar past run


def _json(run_dir: Path, name: str) -> dict:
    path = run_dir / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _csv(run_dir: Path, name: str) -> pd.DataFrame:
    path = run_dir / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _label(value) -> str:
    return "failed" if int(value) == 1 else "passed"


def _model(metrics: dict) -> list[str]:
    if not metrics:
        return []
    t, ci, cm = metrics["test_metrics"], metrics["test_metrics_ci95"], metrics["confusion_matrix"]
    lines = [f"Selected model: {metrics['selected_model']}. Random-guessing PR-AUC: "
             f"{metrics['baseline_pr_auc']}."]
    for key, name in (("pr_auc", "PR-AUC"), ("recall_fail", "fail recall"),
                      ("precision_fail", "precision"), ("balanced_accuracy", "balanced accuracy")):
        if key in t:
            low, high = ci.get(key, [None, None])
            lines.append(f"Test {name}: {t[key]} (95% CI {low} to {high}).")
    lines.append(f"Test period: {cm['tp']} failing runs caught, {cm['fn']} missed, {cm['fp']} "
                 f"false alarms, {cm['tn']} passing runs correctly not flagged.")
    return ["## Model test metrics", *lines]


def _risk(risk: dict) -> list[str]:
    if not risk:
        return []
    chosen = risk["recommended_ranking"]
    test = risk["test"][chosen]
    lines = [f"Recommended ranking: {chosen}. Alarm budget: the riskiest "
             f"{risk['alarm_budget']:.0%} of test-period runs."]
    if "fails_found" in test:
        lines.append(f"It finds {test['fails_found']} of {test['fails_total']} failing runs with "
                     f"{test['alarms']} alarms (recall {test['recall_at_budget']}, precision "
                     f"{test['precision_at_budget']}).")
    return ["## Risk ranking", *lines]


def _anomalies(summary: dict) -> list[str]:
    if not summary:
        return []
    lines = [f"Runs flagged as anomalous: {summary['runs_flagged']} (flag limit "
             f"{summary['score_limit']}). Flag rate: failing runs {summary['flag_rate_fail']}, "
             f"passing runs {summary['flag_rate_pass']} (lift {summary['flag_lift']})."]
    if "mean_out_of_limit_fail" in summary:
        lines.append(f"Sensors out of control limits per run: failing runs "
                     f"{summary['mean_out_of_limit_fail']}, passing runs "
                     f"{summary['mean_out_of_limit_pass']}.")
    return ["## Anomaly detection", *lines]


def _similar(similar: dict, typical: float | None) -> list[str]:
    if not similar:
        return []
    lines = [f"Method: {similar['method']}.",
             f"For each high-risk or failing test run, the {similar['k']} most similar past runs "
             "were found. Distance is the Euclidean distance between sensor profiles after "
             "scaling and PCA: small means similar."]
    fail, ok = (similar.get("neighbour_fail_share_for_failing_test_runs"),
                similar.get("neighbour_fail_share_for_passing_test_runs"))
    if fail is not None and ok is not None:
        lines.append(f"Share of similar past runs that failed: {fail} for failing test runs, "
                     f"{ok} for passing test runs (training fail rate "
                     f"{similar['train_fail_rate']}).")
    if typical is not None:
        lines.append(f"Typical (median) nearest distance: {typical}.")
    return ["## Similar past runs: method and overall result", *lines]


def _run_sections(run_dir: Path, risk: dict, anomalies: dict, similar: dict,
                  typical: float | None) -> list[str]:
    scores = _csv(run_dir, "risk_scores.csv").set_index("run_id", drop=False) \
        if (run_dir / "risk_scores.csv").exists() else pd.DataFrame()
    queries = {q["run_id"]: q for q in similar.get("queries", [])}
    risky = {r["run_id"]: r for r in risk.get("top_risk_runs", [])}
    odd = {r["run_id"]: r for r in anomalies.get("most_anomalous_runs", [])}
    out: list[str] = []
    for run_id in sorted({*queries, *risky, *odd}):
        lines = []
        row = risky.get(run_id) or odd.get(run_id)
        if run_id in scores.index:
            row = {**scores.loc[run_id].to_dict(), **(row or {})}
        if row:
            when = row.get("timestamp", "time unknown")
            parts = [f"Run {run_id} ({when}) {_label(row['label'])}."]
            if "risk_score" in row:
                parts.append(f"Risk score {row['risk_score']}, model fail probability "
                             f"{row.get('fail_probability')}.")
            if "anomaly_score" in row:
                parts.append(f"Anomaly score {row['anomaly_score']}.")
            if row.get("n_out_of_limit") is not None and str(row.get("n_out_of_limit")) != "nan":
                parts.append(f"Sensors out of control limits: {row['n_out_of_limit']}.")
            if row.get("top_signals"):
                parts.append(f"Top signals (sensor: robust z-score): {row['top_signals']}.")
            lines.append(" ".join(parts))
        if run_id in risky:
            lines.append(f"Run {run_id} is among the riskiest test-period runs.")
        if run_id in odd:
            lines.append(f"Run {run_id} is among the most anomalous runs.")
        if q := queries.get(run_id):
            neighbours = ", ".join(f"{n['run_id']} ({_label(n['label'])}, distance "
                                   f"{n['distance']})" for n in q["neighbours"])
            lines.append(f"Similar past runs of run {run_id} (selected because: {q['reason']}): "
                         f"{q['neighbours_failed']} of {q['k']} failed; nearest distance "
                         f"{q['nearest_distance']}; most similar runs: {neighbours}.")
            if typical and q["nearest_distance"] > FAR * typical:
                lines.append(f"Run {run_id}'s nearest distance ({q['nearest_distance']}) is far "
                             f"above the typical {typical}: no past run has a similar sensor "
                             "profile, so its similar past runs say little about it. Its top "
                             "signals show the sensors with the most extreme values.")
        out += [f"## Run {run_id}", *lines, ""]
    return out


def _ranked(risk: dict, anomalies: dict) -> list[str]:
    """The app's two ranked tables, in their order."""
    out = []
    if top := risk.get("top_risk_runs"):
        out += ["## Riskiest test-period runs", "Ordered from the highest risk score down:"]
        out += [f"{i}. Run {r['run_id']} ({_label(r['label'])}): risk score {r['risk_score']}, "
                f"model fail probability {r['fail_probability']}, anomaly score "
                f"{r['anomaly_score']}." for i, r in enumerate(top, start=1)]
        out.append("")
    if odd := anomalies.get("most_anomalous_runs"):
        out += ["## Most anomalous runs", "Ordered from the highest anomaly score down:"]
        out += [f"{i}. Run {r['run_id']} ({_label(r['label'])}): anomaly score "
                f"{r['anomaly_score']}, {r['n_out_of_limit']} sensors out of control limits."
                for i, r in enumerate(odd, start=1)]
        out.append("")
    return out


def write_run_data(run_dir: Path) -> Path | None:
    """Write run_data.md from the run's files; None when the run has no tables yet."""
    metrics, risk = _json(run_dir, "model_metrics.json"), _json(run_dir, "risk_summary.json")
    anomalies, similar = _json(run_dir, "anomaly_summary.json"), _json(run_dir, "similar_runs.json")
    if not (metrics or risk or anomalies or similar):
        return None
    distances = [q["nearest_distance"] for q in similar.get("queries", [])]
    typical = round(median(distances), 3) if distances else None
    lines = ["# Run data", "Numbers copied from this run's files (model_metrics.json, "
             "risk_summary.json, risk_scores.csv, anomaly_summary.json, similar_runs.json).", ""]
    for block in (_model(metrics), _risk(risk), _anomalies(anomalies), _similar(similar, typical)):
        lines += [*block, ""] if block else []
    lines += _ranked(risk, anomalies)
    lines += _run_sections(run_dir, risk, anomalies, similar, typical)
    path = run_dir / RUN_DATA_FILE
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path
