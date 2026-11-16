"""Investigation & Report page. Phase 2: anomaly detection results; Phase 3 adds the
investigation and the engineering report written by the crews."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app.runs import no_run, read_json, show_figure


def render(run_dir: Path | None) -> None:
    st.title("Investigation & Report")
    summary = read_json(run_dir, "anomaly_summary.json") if run_dir else None
    if not summary:
        no_run("investigation")
        return

    st.caption(f"Run `{run_dir.name}`")
    risk = read_json(run_dir, "risk_summary.json")
    if risk:
        _render_risk(risk)

    st.subheader("Anomalies")
    cols = st.columns(3)
    cols[0].metric("Runs flagged", summary["runs_flagged"])
    cols[1].metric("Flag rate: failing runs", f"{summary['flag_rate_fail']:.1%}")
    cols[2].metric("Flag rate: passing runs", f"{summary['flag_rate_pass']:.1%}",
                   help=f"Failing runs are flagged {summary['flag_lift']}x as often")
    show_figure(run_dir, summary["figures"].get("anomaly_scores"))

    sensors = pd.DataFrame(summary["sensors_more_often_out_of_limit_in_fails"])
    if not sensors.empty:
        st.markdown("**Sensors more often out of control limits in failing runs**")
        st.dataframe(sensors, hide_index=True, width="stretch")
    runs = pd.DataFrame(summary["most_anomalous_runs"])
    if not runs.empty:
        st.markdown("**Most anomalous runs**")
        st.dataframe(runs, hide_index=True, width="stretch")
    with st.expander("Method"):
        for name, text in summary["method"].items():
            st.markdown(f"- **{name}:** {text}")

    st.info("Hypotheses and the engineering report from the Investigation and Report crews "
            "are added in Phase 3.", icon=":material/construction:")


def _render_risk(risk: dict) -> None:
    st.subheader("Risk ranking")
    chosen = risk["recommended_ranking"]
    budget = risk["alarm_budget"]
    test = risk["test"][chosen]
    label = "model + anomaly score" if chosen == "combined" else "model alone"
    st.markdown(f"Recommended ranking: **{label}** (chosen by cross-validation on the training "
                f"period). Flagging the riskiest {budget:.0%} of test-period runs finds "
                f"**{test['recall_at_budget']:.0%}** of failing runs with **"
                f"{test['precision_at_budget']:.0%}** precision; random flagging would find "
                f"about {budget:.0%}.")
    comparison = pd.DataFrame([
        {"ranking": name, "CV PR-AUC": risk["cv_mean_per_fold"][name]["pr_auc"],
         "CV recall at budget": risk["cv_mean_per_fold"][name]["recall_at_budget"],
         "test PR-AUC": risk["test"][name]["pr_auc"],
         "test recall at budget": risk["test"][name]["recall_at_budget"],
         "test precision at budget": risk["test"][name]["precision_at_budget"]}
        for name in ("model", "anomaly", "combined")])
    st.dataframe(comparison, hide_index=True, width="stretch")
    top = pd.DataFrame(risk["top_risk_runs"])
    if not top.empty:
        st.markdown("**Riskiest test-period runs**")
        st.dataframe(top, hide_index=True, width="stretch")
