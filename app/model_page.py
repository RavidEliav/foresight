"""Model page: model comparison, test metrics with confidence intervals, important sensors."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app import charts, store, ui
from app.runs import no_run, read_json, run_label, show_markdown_file

METRICS = [("pr_auc", "PR-AUC"), ("recall_fail", "Fail recall"),
           ("precision_fail", "Precision"), ("balanced_accuracy", "Balanced accuracy")]


def _fmt(value) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def render(run_dir: Path | None) -> None:
    ui.page_header("Model")
    metrics = read_json(run_dir, "model_metrics.json") if run_dir else None
    if not metrics:
        no_run("model results")
        return

    split = metrics["split"]
    st.caption(f"{run_label(run_dir)} · trained on {split['train']['runs']} runs "
               f"({split['train']['fails']} fails), tested on the next {split['test']['runs']} "
               f"runs ({split['test']['fails']} fails) from {metrics['test_start'][:10]}")
    op = metrics["operating_point"]
    tiles = []
    for key, label in METRICS:
        low, high = metrics["test_metrics_ci95"].get(key, [None, None])
        comparison = (f"random {metrics['baseline_pr_auc']:.3f}" if key == "pr_auc"
                      else f"95% CI {_fmt(low)}–{_fmt(high)}")
        tiles.append((label, _fmt(metrics["test_metrics"][key]), comparison,
                      f"95% bootstrap CI: {_fmt(low)} – {_fmt(high)}"))
    ui.kpis(tiles)

    cm = metrics["confusion_matrix"]
    fixed = metrics["test_metrics_fixed_threshold"]
    with st.container(key="card-model-summary"):
        ui.label("Selected model")
        st.markdown(f"**`{metrics['selected_model']}`** · operating point: {op['rule']}")
        st.markdown(f"On the test period the alarm budget raised **{op['alarms_in_test']}** "
                    f"alarms: **{cm['tp']}** failing runs caught, **{cm['fn']}** missed, "
                    f"**{cm['fp']}** false alarms. For comparison, the fixed threshold "
                    f"({metrics['threshold']:.3f}, tuned on older runs) caught "
                    f"{fixed['recall_fail']:.0%} of failing runs.")

    left, right = st.columns(2, gap="medium")
    with left, st.container(key="card-chart-risk", height="stretch"):
        ui.label("Risk scores over the test period")
        charts.risk_over_time(run_dir, op.get("cutoff_probability_in_test"),
                              metrics.get("threshold"))
        st.caption("Drift moves the scores; the alarm budget adapts, a fixed threshold does not.")
    with right, st.container(key="card-chart-pr", height="stretch"):
        ui.label("Precision-recall curve")
        charts.pr_curve(run_dir, metrics["baseline_pr_auc"])
    left, right = st.columns(2, gap="medium")
    with left, st.container(key="card-chart-confusion", height="stretch"):
        ui.label("Alarms vs outcomes (test period)")
        charts.confusion(cm)
    with right, st.container(key="card-chart-importance", height="stretch"):
        ui.label("Most important sensors")
        charts.importance(metrics)

    if not ui.developer():  # Extended data is part of the developer view (Phase 8.6)
        return
    ui.section_label("Extended data")
    comparison, evaluation, card = st.tabs(["Model comparison", "Evaluation report",
                                            "Model card"])
    with comparison:
        st.subheader("Model comparison")
        rows = [{"model": name, "time CV PR-AUC": c["cv_pr_auc_mean"],
                 "stratified CV (optimistic)": c["stratified_cv_pr_auc_mean"],
                 "test PR-AUC": c["test_pr_auc"], "test ROC-AUC": c["test_roc_auc"],
                 "description": c["description"]} for name, c in metrics["comparison"].items()]
        frame = pd.DataFrame(rows)
        ui.table(frame, {c: st.column_config.NumberColumn(format="%.3f")
                         for c in frame.columns if c not in ("model", "description")})
        rules = (metrics["selection_rule"], op["rule"])
        st.caption(" ".join(f"{rule[:1].upper()}{rule[1:]}." for rule in rules))
    with evaluation:
        report = store.read_text(run_dir, "evaluation_report.md")
        if report is not None:
            st.markdown(report)
            st.download_button("Download evaluation_report.md", report.encode("utf-8"),
                               file_name="evaluation_report.md", mime="text/markdown")
    with card:
        if not show_markdown_file(run_dir, "model_card.md", "Download model_card.md"):
            st.info("No model card in this run.")
