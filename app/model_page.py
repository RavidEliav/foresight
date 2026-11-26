"""Model page: model comparison, test metrics with confidence intervals, important sensors."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app import charts, store, ui
from app.runs import download, no_run, read_json, run_line, show_markdown_file

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
    run_line(run_dir, f"Trained on {split['train']['runs']} production runs "
                      f"({split['train']['fails']} failing), tested on the next "
                      f"{split['test']['runs']} ({split['test']['fails']} failing) from "
                      f"{metrics['test_start'][:10]}.")
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
    def summary() -> None:
        st.markdown(f"**`{metrics['selected_model']}`** · {op['rule']}.")
        st.markdown(f"On the test period it raised **{op['alarms_in_test']}** alarms: "
                    f"**{cm['tp']}** failing runs caught, **{cm['fn']}** missed, "
                    f"**{cm['fp']}** false alarms.")
        st.markdown(f"The fixed threshold ({metrics['threshold']:.3f}, tuned on older runs) "
                    f"caught {fixed['recall_fail']:.0%} of failing runs.")
        st.caption("Drift moves the scores; the alarm budget adapts, a fixed threshold does "
                   "not.")

    # Phase 8.7: the selected model beside one chart card with tabs (on a phone, all tabs)
    ui.cards([[("Selected model", summary)],
              [("Risk scores", lambda: charts.risk_over_time(
                  run_dir, op.get("cutoff_probability_in_test"), metrics.get("threshold"))),
               ("Important sensors", lambda: charts.importance(metrics)),
               ("Alarms vs outcomes", lambda: charts.confusion(cm)),
               ("Precision-recall", lambda: charts.pr_curve(run_dir,
                                                            metrics["baseline_pr_auc"]))]],
             "model", widths=[2, 3])

    if not ui.developer():  # Extended data is part of the developer view (Phase 8.6)
        return
    shown = ui.extended(["Model comparison", "Evaluation report", "Model card"], "model")
    if shown == "Model comparison":
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
    elif shown == "Evaluation report":
        report = store.read_text(run_dir, "evaluation_report.md")
        if report is not None:
            st.markdown(report)
            download(run_dir, "evaluation_report.md", report.encode("utf-8"))
    elif shown == "Model card" and not show_markdown_file(run_dir, "model_card.md",
                                                          downloadable=True):
        st.info("No model card in this run.")
