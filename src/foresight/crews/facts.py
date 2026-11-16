"""Fact sheets for the crews, and the set of numbers a report may quote.

Agents receive these facts in their task descriptions (plus read-only tools for details), so
every number they use was computed by Python and can be traced to a run file (ADR-005).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SOURCE_FILES = (
    "validation_summary.json", "cleaning_report.json", "data_profile.json", "feature_spec.json",
    "eda_summary.json", "model_metrics.json", "anomaly_summary.json", "risk_summary.json",
)


def read(run_dir: Path, name: str) -> dict:
    path = run_dir / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def data_facts(run_dir: Path) -> str:
    v, c, p = (read(run_dir, n) for n in ("validation_summary.json", "cleaning_report.json",
                                          "data_profile.json"))
    if not v:
        return "No data facts available."
    lines = [
        f"- Data Contract validation: {v['status']} ({v['counts']['PASS']} checks passed, "
        f"{v['counts']['WARNING']} warnings, {v['counts']['ERROR']} errors) "
        "[source: validation_summary.json]",
    ]
    if p:
        lines += [
            f"- {p['rows']} production runs from {p['time_range'][0]} to {p['time_range'][1]} "
            "[source: data_profile.json]",
            f"- {p['label_counts'].get('1', 0)} failing runs, fail rate {pct(p['fail_rate'])} "
            "[source: data_profile.json]",
            f"- Missing cells after cleaning: {pct(p['missing_cells_ratio'], 2)} "
            "[source: data_profile.json]",
        ]
    if c:
        lines += [
            f"- Features kept {c['features_out']} of {c['features_in']}: "
            f"{len(c['dropped_high_missing'])} dropped for more than 50% missing values, "
            f"{len(c['dropped_constant'])} dropped as constant [source: cleaning_report.json]",
        ]
    for check in v["checks"]:
        if check["status"] != "PASS":
            lines.append(f"- {check['status']} {check['name']}: {check['message']} "
                         "[source: validation_summary.json]")
    return "\n".join(lines)


def eda_facts(run_dir: Path, top: int = 8) -> str:
    e = read(run_dir, "eda_summary.json")
    if not e:
        return "No EDA facts available."
    months = ", ".join(f"{m}: {pct(r)}" for m, r in e["monthly_fail_rate"].items())
    m = e["missingness"]
    lines = [
        f"- Monthly fail rate: {months} [source: eda_summary.json]",
        f"- {e['significant_features_q_below_0.05']} sensors differ between failing and passing "
        "runs (Mann-Whitney U, Benjamini-Hochberg q < 0.05) [source: eda_summary.json]",
        f"- Missing values per run: failing {m['mean_missing_per_run_fail']}, passing "
        f"{m['mean_missing_per_run_pass']} [source: eda_summary.json]",
        f"- {e['redundant_feature_pairs_over_0.95']} sensor pairs are near duplicates "
        "(|r| > 0.95) [source: eda_summary.json]",
    ]
    for row in e["top_discriminating_features"][:top]:
        lines.append(
            f"- {row['feature']}: {row['direction']}, median pass {row['median_pass']:.4g} vs "
            f"fail {row['median_fail']:.4g}, effect {row['effect']:.2f}, "
            f"q = {row['q_value']:.2g} [source: eda_summary.json]")
    return "\n".join(lines)


def model_facts(run_dir: Path, top: int = 8) -> str:
    mm = read(run_dir, "model_metrics.json")
    if not mm:
        return "No model facts available."
    t, ci, cm, op = (mm["test_metrics"], mm["test_metrics_ci95"], mm["confusion_matrix"],
                     mm["operating_point"])
    fixed = mm["test_metrics_fixed_threshold"]
    s = mm["split"]
    lines = [
        f"- Time-ordered split: train {s['train']['runs']} runs ({s['train']['fails']} fails), "
        f"test {s['test']['runs']} runs ({s['test']['fails']} fails) from "
        f"{mm['test_start'][:10]} [source: model_metrics.json]",
        f"- Selected model: {mm['selected_model']} ({mm['selection_rule']}) "
        "[source: model_metrics.json]",
        f"- Operating point: {op['rule']}; {op['alarms_in_test']} alarms in the test period "
        "[source: model_metrics.json]",
        f"- Test PR-AUC {t['pr_auc']:.3f} (95% CI {ci['pr_auc'][0]:.3f}-{ci['pr_auc'][1]:.3f}) "
        f"vs random guessing {mm['baseline_pr_auc']:.3f} [source: model_metrics.json]",
        f"- Test ROC-AUC {t['roc_auc']:.3f} [source: model_metrics.json]",
        f"- At the alarm budget: recall {t['recall_fail']:.3f} (95% CI "
        f"{ci['recall_fail'][0]:.3f}-{ci['recall_fail'][1]:.3f}), precision "
        f"{t['precision_fail']:.3f}; {cm['tp']} fails caught, {cm['fn']} missed, {cm['fp']} "
        "false alarms [source: model_metrics.json]",
        f"- Fixed F2 threshold {mm['threshold']:.3f} tuned on older runs: recall "
        f"{fixed['recall_fail']:.3f} in the test period (drift) [source: model_metrics.json]",
    ]
    for name, c in mm["comparison"].items():
        lines.append(f"- {name}: time-CV PR-AUC {c['cv_pr_auc_mean']}, test PR-AUC "
                     f"{c['test_pr_auc']} [source: model_metrics.json]")
    names = ", ".join(r["feature"] for r in mm["top_features_permutation"][:top])
    if names:
        lines.append(f"- Most important sensors (permutation importance): {names} "
                     "[source: model_metrics.json]")
    return "\n".join(lines)


def anomaly_facts(run_dir: Path, top: int = 6) -> str:
    a, r = read(run_dir, "anomaly_summary.json"), read(run_dir, "risk_summary.json")
    if not a:
        return "No anomaly facts available."
    lines = [
        f"- {a['runs_flagged']} runs flagged as anomalous; flag rate {pct(a['flag_rate_fail'])} "
        f"for failing vs {pct(a['flag_rate_pass'])} for passing runs (lift {a['flag_lift']}) "
        "[source: anomaly_summary.json]",
        f"- Sensors out of control limits per run: failing {a['mean_out_of_limit_fail']}, "
        f"passing {a['mean_out_of_limit_pass']} [source: anomaly_summary.json]",
    ]
    for row in a["sensors_more_often_out_of_limit_in_fails"][:top]:
        lines.append(f"- {row['feature']} out of limits in {pct(row['out_of_limit_rate_fail'])} "
                     f"of failing vs {pct(row['out_of_limit_rate_pass'])} of passing runs "
                     "[source: anomaly_summary.json]")
    if r:
        chosen = r["recommended_ranking"]
        best = r["test"][chosen]
        lines.append(
            f"- Recommended risk ranking: {chosen} (chosen by time-ordered CV); flagging the "
            f"riskiest {pct(r['alarm_budget'], 0)} of test runs ({best['alarms']} alarms) finds "
            f"{best['fails_found']} of {best['fails_total']} failing runs, precision "
            f"{pct(best['precision_at_budget'])} [source: risk_summary.json]")
        for run in r["top_risk_runs"][:3]:
            lines.append(f"- Run {run['run_id']} ({run['timestamp'][:10]}, label "
                         f"{'fail' if run['label'] else 'pass'}): risk {run['risk_score']:.3f}, "
                         f"strongest signals {run['top_signals'] or 'none'} "
                         "[source: risk_summary.json]")
    return "\n".join(lines)


def all_facts(run_dir: Path) -> dict[str, str]:
    return {"data_facts": data_facts(run_dir), "eda_facts": eda_facts(run_dir),
            "model_facts": model_facts(run_dir), "anomaly_facts": anomaly_facts(run_dir)}


def _variants(value: float) -> set[str]:
    out = {f"{value:.{d}f}" for d in range(5)} | {f"{value:g}", f"{value:.2g}", f"{value:.3g}",
                                                  f"{value:.4g}"}
    if abs(value) <= 1:
        out |= {f"{value * 100:.{d}f}%" for d in range(3)}
        out |= {f"{value * 100:.{d}f}" for d in range(3)}
    out |= {f"{value:,.0f}", f"{abs(value):.{2}f}", f"{abs(value):g}"}
    return {o.lstrip("+") for o in out}


def allowed_numbers(run_dir: Path) -> set[str]:
    """Every number in the run's summary files, in common formatting variants."""
    allowed: set[str] = set()
    texts = [(run_dir / name).read_text(encoding="utf-8") for name in SOURCE_FILES
             if (run_dir / name).exists()]
    texts += list(all_facts(run_dir).values())
    for text in texts:
        for token in re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text):
            try:
                allowed |= _variants(float(token))
            except ValueError:
                continue
    return allowed
