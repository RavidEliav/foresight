"""EDA & Insights page: descriptive statistics and charts of a run."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app import charts, store, ui
from app.runs import no_run, read_json, run_label, show_markdown_file


def render(run_dir: Path | None) -> None:
    ui.page_header("EDA & Insights")
    eda = read_json(run_dir, "eda_summary.json") if run_dir else None
    if not eda:
        no_run("analysis")
        return

    st.caption(f"{run_label(run_dir)} · descriptive statistics over the whole dataset")
    overview = eda["overview"]
    ui.kpis([
        ("Runs", f"{overview['rows']:,}", None, None),
        ("Sensors", str(overview["features"]), None, None),
        ("Fail rate", f"{overview['fail_rate']:.1%}", None, "Over the whole dataset"),
        ("Sensors differ (q<0.05)", str(eda["significant_features_q_below_0.05"]), None,
         "Mann-Whitney U test, failing vs passing runs, Benjamini-Hochberg corrected"),
    ])
    # Phase 8.7: the crew's insights beside one chart card with tabs, so the page fits a screen
    insights = store.exists(run_dir, "insights.md")
    left, right = st.columns([2, 3], gap="medium") if insights else (None, st.container())
    if insights:
        with left, st.container(key="card-insights", height="stretch"):
            ui.label("Insights from the Data Analyst crew")
            _summary_section(run_dir)
    with right, st.container(key="card-tabs-eda", height="stretch"):
        rate, sensors = st.tabs(["Fail rate over time", "Sensors that differ"])
        with rate:
            charts.weekly_fail_rate(eda)
            months = ", ".join(f"{m}: {r:.1%}" for m, r in eda["monthly_fail_rate"].items())
            st.caption(f"By month: {months}")
        with sensors:
            charts.sensor_differences(eda)
            st.caption("Sensors that differ between failing and passing runs. A difference is "
                       "a correlation, not a cause. Sensor names are anonymized.")

    if not ui.developer():  # Extended data is part of the developer view (Phase 8.6)
        return
    ui.section_label("Extended data")
    sensors, missing, insights = st.tabs(["Sensor statistics", "Missing data and redundancy",
                                          "Full insights"])
    with sensors:
        table = pd.DataFrame(eda["top_discriminating_features"])
        if not table.empty:
            ui.table(table[["feature", "direction", "effect", "q_value", "median_pass",
                            "median_fail"]],
                     {"effect": st.column_config.NumberColumn(format="%.3f"),
                      "q_value": st.column_config.NumberColumn(format="%.2e")})
    with missing:
        m = eda["missingness"]
        st.markdown(f"- {m['features_with_missing']} sensors have gaps\n"
                    f"- Missing values per run: failing {m['mean_missing_per_run_fail']}, "
                    f"passing {m['mean_missing_per_run_pass']}\n"
                    f"- {eda['redundant_feature_pairs_over_0.95']} sensor pairs are near "
                    "duplicates (|r| > 0.95)")
        top = [f["feature"] for f in eda["top_discriminating_features"]]
        left, right = st.columns(2, gap="medium")
        with left, st.container(key="card-chart-missing", height="stretch"):
            ui.label("Sensors with the most missing values")
            charts.missing_by_sensor(run_dir)
        with right, st.container(key="card-chart-correlation", height="stretch"):
            ui.label("Correlation between the sensors that differ most")
            charts.correlation(run_dir, top)
    with insights:
        show_markdown_file(run_dir, "insights.md", "Download insights.md")
        report = store.read_bytes(run_dir, "eda_report.html")
        if report is not None:
            st.download_button("Download eda_report.html", report,
                               file_name="eda_report.html", mime="text/html")


def _summary_section(run_dir: Path) -> None:
    """The crew's Summary section; the full document is under Extended data."""
    from foresight.crews.checks import section

    text = store.read_text(run_dir, "insights.md") or ""
    body = section(text, "Summary").strip()
    st.markdown(ui.md(body or text))
