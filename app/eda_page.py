"""EDA & Insights page: descriptive statistics and charts of a run."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app import charts, ui
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
    if (run_dir / "insights.md").exists():
        with st.container(key="card-insights"):
            ui.label("Insights from the Data Analyst crew")
            _summary_section(run_dir / "insights.md")

    left, right = st.columns(2, gap="medium")
    with left, st.container(key="card-chart-failrate", height="stretch"):
        ui.label("Fail rate over time")
        charts.weekly_fail_rate(eda)
        months = ", ".join(f"{m}: {r:.1%}" for m, r in eda["monthly_fail_rate"].items())
        st.caption(f"By month: {months}")
    with right, st.container(key="card-chart-sensors", height="stretch"):
        ui.label("Sensors that differ between failing and passing runs")
        charts.sensor_differences(eda)
        st.caption("A difference between failing and passing runs is a correlation, not a "
                   "cause. Sensor names are anonymized.")

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
        report = run_dir / "eda_report.html"
        if report.exists():
            st.download_button("Download eda_report.html", report.read_bytes(),
                               file_name="eda_report.html", mime="text/html")


def _summary_section(path: Path) -> None:
    """The crew's Summary section; the full document is under Extended data."""
    from foresight.crews.checks import section

    text = path.read_text(encoding="utf-8")
    body = section(text, "Summary").strip()
    st.markdown(ui.md(body or text))
