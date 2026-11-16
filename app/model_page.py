"""Model page: model comparison, test metrics with confidence intervals, important sensors."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app.runs import no_run, read_json, run_label, show_figure, show_markdown_file

METRICS = [("pr_auc", "PR-AUC"), ("recall_fail", "Fail recall"),
           ("precision_fail", "Precision"), ("balanced_accuracy", "Balanced accuracy")]


def _fmt(value) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def render(run_dir: Path | None) -> None:
    st.title("Model")
    metrics = read_json(run_dir, "model_metrics.json") if run_dir else None
    if not metrics:
        no_run("model results")
        return

    split = metrics["split"]
    st.caption(f"{run_label(run_dir)} · trained on {split['train']['runs']} runs "
               f"({split['train']['fails']} fails), tested on the next {split['test']['runs']} "
               f"runs ({split['test']['fails']} fails) from {metrics['test_start'][:10]}")
    op = metrics["operating_point"]
    st.markdown(f"**Selected model:** `{metrics['selected_model']}` · operating point: "
                f"{op['rule']} · random-guessing PR-AUC {metrics['baseline_pr_auc']:.3f}")

    cols = st.columns(len(METRICS))
    for col, (key, label) in zip(cols, METRICS, strict=True):
        low, high = metrics["test_metrics_ci95"].get(key, [None, None])
        col.metric(label, _fmt(metrics["test_metrics"][key]),
                   help=f"95% bootstrap CI: {_fmt(low)} – {_fmt(high)}")
    cm = metrics["confusion_matrix"]
    fixed = metrics["test_metrics_fixed_threshold"]
    st.markdown(f"On the test period the alarm budget raised **{op['alarms_in_test']}** alarms: "
                f"**{cm['tp']}** failing runs caught, **{cm['fn']}** missed, **{cm['fp']}** false "
                f"alarms. For comparison, the fixed threshold ({metrics['threshold']:.3f}, tuned "
                f"on older runs) caught {fixed['recall_fail']:.0%} of failing runs.")
    show_figure(run_dir, metrics["figures"].get("scores_over_time"),
                "Risk scores over the test period: drift moves scores, the alarm budget adapts")

    st.subheader("Model comparison")
    rows = [{"model": name, "time CV PR-AUC": c["cv_pr_auc_mean"],
             "stratified CV (optimistic)": c["stratified_cv_pr_auc_mean"],
             "test PR-AUC": c["test_pr_auc"], "test ROC-AUC": c["test_roc_auc"],
             "description": c["description"]} for name, c in metrics["comparison"].items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    rules = (metrics["selection_rule"], op["rule"])
    st.caption(" ".join(f"{rule[:1].upper()}{rule[1:]}." for rule in rules))

    left, right = st.columns(2)
    with left:
        show_figure(run_dir, metrics["figures"].get("pr_curve"))
    with right:
        show_figure(run_dir, metrics["figures"].get("confusion_matrix"))

    st.subheader("Most important sensors")
    show_figure(run_dir, metrics["figures"].get("feature_importance"))

    report = run_dir / "evaluation_report.md"
    if report.exists():
        with st.expander("Evaluation report"):
            st.markdown(report.read_text(encoding="utf-8"))
        st.download_button("Download evaluation_report.md", report.read_bytes(),
                           file_name="evaluation_report.md", mime="text/markdown")
    if (run_dir / "model_card.md").exists():
        with st.expander("Model card (Data Scientist crew)"):
            show_markdown_file(run_dir, "model_card.md", "Download model_card.md")
