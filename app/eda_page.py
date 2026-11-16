"""EDA & Insights page: descriptive statistics and charts of a run."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app.runs import no_run, read_json, run_label, show_figure, show_markdown_file


def render(run_dir: Path | None) -> None:
    st.title("EDA & Insights")
    eda = read_json(run_dir, "eda_summary.json") if run_dir else None
    if not eda:
        no_run("analysis")
        return

    st.caption(f"{run_label(run_dir)} · descriptive statistics over the whole "
               "dataset")
    overview = eda["overview"]
    cols = st.columns(4)
    cols[0].metric("Runs", f"{overview['rows']:,}")
    cols[1].metric("Sensors", overview["features"])
    cols[2].metric("Fail rate", f"{overview['fail_rate']:.1%}")
    cols[3].metric("Sensors differ (q<0.05)", eda["significant_features_q_below_0.05"],
                   help="Mann-Whitney U test, failing vs passing runs, "
                        "Benjamini-Hochberg corrected")

    if (run_dir / "insights.md").exists():
        with st.expander("Insights from the Data Analyst crew", expanded=True):
            show_markdown_file(run_dir, "insights.md", "Download insights.md")

    st.subheader("Fail rate over time")
    months = ", ".join(f"{m}: {r:.1%}" for m, r in eda["monthly_fail_rate"].items())
    st.markdown(f"By month: {months}")
    show_figure(run_dir, eda["figures"].get("fail_rate_over_time"))

    st.subheader("Sensors that differ between failing and passing runs")
    table = pd.DataFrame(eda["top_discriminating_features"])
    if not table.empty:
        st.dataframe(table[["feature", "direction", "effect", "q_value", "median_pass",
                            "median_fail"]], hide_index=True, width="stretch")
    show_figure(run_dir, eda["figures"].get("top_features"))
    st.caption("A difference between failing and passing runs is a correlation, not a cause. "
               "Sensor names are anonymized.")

    with st.expander("Missing data and sensor redundancy"):
        m = eda["missingness"]
        st.markdown(f"- {m['features_with_missing']} sensors have gaps\n"
                    f"- Missing values per run: failing {m['mean_missing_per_run_fail']}, "
                    f"passing {m['mean_missing_per_run_pass']}\n"
                    f"- {eda['redundant_feature_pairs_over_0.95']} sensor pairs are near "
                    "duplicates (|r| > 0.95)")
        show_figure(run_dir, eda["figures"].get("missingness"))
        show_figure(run_dir, eda["figures"].get("correlation"))

    report = run_dir / "eda_report.html"
    if report.exists():
        st.download_button("Download eda_report.html", report.read_bytes(),
                           file_name="eda_report.html", mime="text/html")
