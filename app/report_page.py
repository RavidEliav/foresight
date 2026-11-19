"""Investigation & Report page: a short, checked summary (key findings and one card per
hypothesis) on top; the engineering report, the full investigation, the risk ranking, similar
past runs, anomalies and the safety checks in tabs below."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app import charts, store, ui
from app.runs import no_run, read_json, run_label, show_markdown_file
from foresight.crews.summary import SUMMARY_FILE, InvestigationSummary

STATUS_ICON = {"PASS": ":material/check_circle:", "WARNING": ":material/warning:",
               "ERROR": ":material/cancel:"}
TABS = ["Engineering report", "Full investigation", "Risk ranking", "Similar past runs",
        "Anomalies", "Safety checks"]


def render(run_dir: Path | None) -> None:
    ui.page_header("Investigation & Report")
    summary = read_json(run_dir, "anomaly_summary.json") if run_dir else None
    if not summary:
        no_run("investigation")
        return

    st.caption(run_label(run_dir))
    checks = read_json(run_dir, "report_checks.json")
    risk = read_json(run_dir, "risk_summary.json")
    similar = read_json(run_dir, "similar_runs.json")
    _status_line(checks)
    ui.kpis(_headline_numbers(summary, risk, similar))
    scenario = read_json(run_dir, "scenario_check.json")
    if scenario:
        _render_scenario(scenario)
    overview = store.investigation_summary(run_dir)
    if overview:
        _render_overview(overview)
    elif store.exists(run_dir, SUMMARY_FILE):
        st.warning("The short summary of this run did not pass its format check, so there are "
                   "no hypothesis cards. The full investigation is under Extended data below; "
                   "the Safety checks tab says what was wrong.", icon=":material/warning:")
    else:
        st.info("This run was made before Foresight wrote a short summary, so there are no "
                "hypothesis cards. The full investigation is under Extended data below.",
                icon=":material/history:")

    left, right = st.columns(2, gap="medium")
    with left, st.container(key="card-chart-anomalies", height="stretch"):
        ui.label("Anomaly score over time")
        charts.anomaly_timeline(run_dir, summary["score_limit"])
        st.caption("Dotted line: the flag limit (95% of training-run scores). Shaded: the test "
                   "period.")
    with right, st.container(key="card-chart-runmap", height="stretch"):
        ui.label("Run map: similar sensor profiles sit close together")
        if similar:
            three_d = st.session_state.get("run-map-3d-toggle", False)
            charts.run_map(run_dir, three_d)
            st.toggle("3D view", key="run-map-3d-toggle")
        else:
            _older_run("Similar-run search")

    ui.section_label("Extended data")
    report, investigation, risk_tab, similar_tab, anomalies, safety = st.tabs(TABS)
    with report:
        _render_report(run_dir)
    with investigation:
        _render_investigation(run_dir)
    with risk_tab:
        if risk:
            _render_risk(risk)
        else:
            _older_run("The risk ranking")
    with similar_tab:
        if similar:
            _render_similar(similar)
        else:
            _older_run("Similar-run search")
    with anomalies:
        _render_anomalies(summary)
    with safety:
        _render_checks(checks)


def _headline_numbers(summary: dict, risk: dict | None,
                      similar: dict | None) -> list[tuple[str, str, str | None, str | None]]:
    """The numbers an engineer looks for first: (label, value, comparison, help)."""
    items = []
    if risk:
        chosen = risk["recommended_ranking"]
        test, budget = risk["test"][chosen], risk["alarm_budget"]
        name = "model + anomaly score" if chosen == "combined" else "model alone"
        if "fails_found" in test:
            items.append(("Failing runs caught", f"{test['fails_found']} of {test['fails_total']}",
                          f"with {test['alarms']} alarms",
                          f"Flagging the riskiest {budget:.0%} of test-period runs (ranking: "
                          f"{name}); random flagging finds about {budget:.0%} of failing runs"))
        items.append(("Alarm precision", f"{test['precision_at_budget']:.1%}",
                      "true alarms", "Share of the alarms that were failing runs"))
    items.append(("Anomaly flag lift", f"{summary['flag_lift']}x",
                  f"{summary['flag_rate_fail']:.1%} vs {summary['flag_rate_pass']:.1%} flagged",
                  f"Failing runs are flagged {summary['flag_lift']}x as often as passing runs "
                  f"({summary['runs_flagged']} runs flagged in total)"))
    if "mean_out_of_limit_fail" in summary:
        items.append(("Sensors out of limits", str(summary["mean_out_of_limit_fail"]),
                      f"{summary['mean_out_of_limit_pass']} in passing runs",
                      "Average number of sensors outside their control limits (|z| > 3) per "
                      "failing run, and per passing run"))
    if similar and similar["neighbour_fail_share_for_failing_test_runs"] is not None:
        items.append(("Similar runs that failed",
                      f"{similar['neighbour_fail_share_for_failing_test_runs']:.1%}",
                      f"{similar['neighbour_fail_share_for_passing_test_runs']:.1%} for passing "
                      "runs",
                      f"Share of the {similar['k']} most similar past runs that failed, for "
                      f"failing and for passing test runs (training fail rate "
                      f"{similar['train_fail_rate']:.1%}). Close values mean weak evidence."))
    return items


def _older_run(feature: str) -> None:
    st.info(f"{feature} was added after this run was made. Choose the reference run in the "
            "sidebar, or start a new run.", icon=":material/history:")


def _status_line(checks: dict | None) -> None:
    if not checks:
        return
    status, counts = checks["status"], checks["counts"]
    total = sum(counts.values())
    color = ui.STATUS_COLORS[status]
    st.markdown(f":{color}-badge[{STATUS_ICON[status]} Report safety checks: {status}] "
                f":gray[{counts['PASS']} of {total} passed · details in the Safety checks "
                "tab]")


def _render_overview(overview: InvestigationSummary) -> None:
    with st.container(key="card-summary"):
        ui.label("Key findings")
        st.html(f'<div class="fs-headline">{_escape(overview.headline)}</div>')
        st.markdown("\n".join(f"- {ui.md(f.text)} :gray-badge[{f.source}]"
                              for f in overview.key_findings))

    st.markdown("**Hypotheses** :gray[AI-generated leads for an engineer to verify, not proven "
                "causes]")
    per_row = 3
    cards = overview.hypotheses
    for start in range(0, len(cards), per_row):
        columns = st.columns(per_row)
        for offset, (column, card) in enumerate(zip(columns, cards[start:start + per_row],
                                                    strict=False)):
            # keyed by position: an LLM may repeat a card number
            with column, st.container(key=f"card-hyp-{start + offset}", height="stretch"):
                color = ui.CONFIDENCE_COLORS[card.confidence]
                st.markdown(f"**H{card.number}** :{color}-badge[{card.confidence} confidence]")
                st.markdown(f"**{ui.md(card.title)}**")
                st.markdown(f":gray[Evidence:] {ui.md(card.evidence)}")
                st.markdown(f":blue[Verify:] {ui.md(card.verify)}")


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_scenario(scenario: dict) -> None:
    """Scenario Lab: what was changed (ground truth) and what the analysis found."""
    with st.container(key="card-scenario"):
        ui.label("Synthetic scenario: ground truth")
        found = len(scenario["found"])
        total = len(scenario["sensors"])
        period = scenario.get("training_runs")  # runs recorded before 8.3's fix lack it
        changed = (f"{scenario['training_runs_changed']} of {period} training runs changed"
                   if period else "training period changed")
        st.markdown(f":orange-badge[SYNTHETIC] **{scenario['title']}** · strength "
                    f"{scenario['intensity']:g} · seed {scenario['seed']} · {changed}, "
                    f"{scenario['test_runs_untouched']} test runs untouched")
        if total:
            st.markdown(f"The analysis named **{found} of {total}** changed "
                        f"sensor{'s' if total != 1 else ''}.")
            rows = [{"sensor": r["sensor"],
                     "EDA rank": (f"{r['eda_rank']} of {r['eda_listed']}" if r["eda_rank"]
                                  else f"not in the top {r['eda_listed']}"),
                     "model importance rank": r["model_rank"] or "not listed",
                     "named in the reports": "yes" if r["in_reports"] else "no"}
                    for r in scenario["sensors_checked"]]
            ui.table(pd.DataFrame(rows))
        st.caption("The model is evaluated on the original SECOM test period, where the "
                   "synthetic change does not exist: every metric on these pages is computed "
                   "on real runs only.")


def _render_report(run_dir: Path) -> None:
    if not store.exists(run_dir, "engineering_report.md"):
        st.info("No engineering report in this run.")
        return
    with st.container(border=True):
        show_markdown_file(run_dir, "engineering_report.md", "Download engineering_report.md")


INVESTIGATION_SECTIONS = [
    ("Facts", "green", "measured results, each with its source file"),
    ("Assumptions", "gray", "what the analysis takes for granted"),
    ("Hypotheses", "orange", "AI-generated, to be verified by an engineer"),
    ("Suggested verification", "blue", "how to test each hypothesis"),
]


def _render_investigation(run_dir: Path) -> None:
    """Facts, assumptions and hypotheses in separate, colour-labelled blocks."""
    from foresight.crews.checks import section

    text = store.read_text(run_dir, "investigation.md")
    if text is None:
        st.info("No investigation in this run.")
        return
    for title, color, meaning in INVESTIGATION_SECTIONS:
        body = section(text, title).strip()
        if not body:
            continue
        with st.container(border=True):
            st.markdown(f":{color}-badge[{title}] :gray[{meaning}]")
            st.markdown(body)
    st.download_button("Download investigation.md", text.encode("utf-8"),
                       file_name="investigation.md", mime="text/markdown",
                       key="download-investigation.md")


def _render_checks(checks: dict | None) -> None:
    if not checks:
        st.info("No safety checks in this run.")
        return
    status, counts = checks["status"], checks["counts"]
    message = (f"Report safety checks: **{status}** · {counts['PASS']} passed, "
               f"{counts['WARNING']} warnings, {counts['ERROR']} errors")
    {"PASS": st.success, "WARNING": st.warning, "ERROR": st.error}[status](
        message, icon=STATUS_ICON[status])
    st.markdown("Required sections are present, every sensor mentioned exists in the data, "
                "numbers can be traced to the run files, every fact in the investigation cites "
                "its source file, every hypothesis follows the confidence rubric (\"high\" "
                "needs q < 0.001 and a second, independent signal) and the summary above "
                "matches the investigation. A crew whose output fails a check revises it once; "
                "revisions are listed below.")
    ui.table(pd.DataFrame(checks["checks"])[["status", "name", "message"]], max_rows=30)


def _render_anomalies(summary: dict) -> None:
    st.markdown(f"**{summary['runs_flagged']}** runs flagged as anomalous: "
                f"**{summary['flag_rate_fail']:.1%}** of failing runs and "
                f"**{summary['flag_rate_pass']:.1%}** of passing runs (failing runs "
                f"{summary['flag_lift']}x as often).")
    sensors = pd.DataFrame(summary["sensors_more_often_out_of_limit_in_fails"])
    runs = pd.DataFrame(summary["most_anomalous_runs"])
    left, right = st.columns([2, 3], gap="medium")
    with left:
        if not sensors.empty:
            st.markdown("**Sensors more often out of limits in failing runs**")
            rates = sensors.rename(columns={"out_of_limit_rate_fail": "failing",
                                            "out_of_limit_rate_pass": "passing"})
            rates[["failing", "passing", "difference"]] *= 100
            ui.table(rates, {c: st.column_config.NumberColumn(format="%.1f%%")
                             for c in ("failing", "passing", "difference")})
    with right:
        if not runs.empty:
            st.markdown("**Most anomalous runs**")
            ui.table(runs, {"anomaly_score": st.column_config.NumberColumn(format="%.3f")})
    with st.expander("Method"):
        for name, text in summary["method"].items():
            st.markdown(f"- **{name}:** {text}")


def _render_similar(similar: dict) -> None:
    fail, ok = (similar["neighbour_fail_share_for_failing_test_runs"],
                similar["neighbour_fail_share_for_passing_test_runs"])
    if fail is not None and ok is not None:
        st.markdown(f"Among the {similar['k']} most similar past runs, **{fail:.1%}** failed for "
                    f"failing test runs and **{ok:.1%}** for passing ones (training fail rate "
                    f"{similar['train_fail_rate']:.1%}). The closer these are, the less a run's "
                    "overall sensor profile says about failure.")
    rows = [{"run": q["run_id"], "why": q["reason"], "label": "fail" if q["label"] else "pass",
             "similar past runs that failed": f"{q['neighbours_failed']} of {q['k']}",
             "nearest distance": q["nearest_distance"],
             "most similar runs": ", ".join(str(n["run_id"]) for n in q["neighbours"])}
            for q in similar["queries"]]
    if rows:
        ui.table(pd.DataFrame(rows), {"nearest distance": st.column_config.NumberColumn(
            format="%.2f")})
    with st.expander("Method"):
        st.caption(similar["method"])


def _render_risk(risk: dict) -> None:
    chosen = risk["recommended_ranking"]
    budget = risk["alarm_budget"]
    test = risk["test"][chosen]
    label = "model + anomaly score" if chosen == "combined" else "model alone"
    found = (f" ({test['fails_found']} of {test['fails_total']}, {test['alarms']} alarms)"
             if "fails_found" in test else "")
    st.markdown(f"Recommended ranking: **{label}** (chosen by cross-validation on the training "
                f"period). Flagging the riskiest {budget:.0%} of test-period runs finds "
                f"**{test['recall_at_budget']:.0%}** of failing runs{found} with **"
                f"{test['precision_at_budget']:.1%}** precision; random flagging would find "
                f"about {budget:.0%}.")
    comparison = pd.DataFrame([
        {"ranking": name, "CV PR-AUC": risk["cv_mean_per_fold"][name]["pr_auc"],
         "CV recall at budget": risk["cv_mean_per_fold"][name]["recall_at_budget"],
         "test PR-AUC": risk["test"][name]["pr_auc"],
         "test recall at budget": risk["test"][name]["recall_at_budget"],
         "test precision at budget": risk["test"][name]["precision_at_budget"]}
        for name in ("model", "anomaly", "combined")])
    ui.table(comparison, {c: st.column_config.NumberColumn(format="%.3f")
                          for c in comparison.columns if c != "ranking"})
    top = pd.DataFrame(risk["top_risk_runs"])
    if not top.empty:
        st.markdown("**Riskiest test-period runs**")
        ui.table(top, {c: st.column_config.NumberColumn(format="%.3f")
                       for c in ("risk_score", "fail_probability", "anomaly_score")})
