"""Trends page: every recorded run over time (the run registry, ADR-027): model quality, where
the run time goes, and LLM tokens. Reads Supabase when it is connected, else the run folders."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import charts, store, ui
from app.runs import local_zone
from foresight.settings import Settings

SOURCES = {"secom": "SECOM", "upload": "Upload", "scenario": "Synthetic",
           "reference": "Reference"}


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    """Local start time and a short label for every run."""
    started = pd.to_datetime(frame.started_at, utc=True, format="ISO8601")
    zone = local_zone()
    frame = frame.assign(when=started.dt.tz_convert(zone).dt.tz_localize(None))
    frame["label"] = frame.when.dt.strftime("%d %b %H:%M")
    repeated = frame.label.duplicated(keep=False)
    frame.loc[repeated, "label"] = frame.when[repeated].dt.strftime("%d %b %H:%M:%S")
    frame["source_name"] = frame.source.map(SOURCES).fillna(frame.source)
    return frame


def _median(series: pd.Series) -> float | None:
    series = series.dropna()
    return float(series.median()) if not series.empty else None


def _kpis(frame: pd.DataFrame) -> None:
    ok = frame[frame.status.eq("success")]
    real = ok[~ok.llm_mock.astype("boolean").fillna(False) & ok.source.ne("reference")]
    minutes = _median(real.duration_s)
    tokens = _median(real.total_tokens)
    latest = ok.sort_values("when").iloc[-1] if not ok.empty else None
    ui.kpis([
        ("Runs recorded", f"{len(frame)}", f"{len(ok)} successful", None),
        ("Median run time", "n/a" if minutes is None else f"{minutes / 60:.1f} min",
         "real runs", "Successful runs with real LLM crews, start to finish."),
        ("Median tokens", "n/a" if tokens is None else f"{tokens:,.0f}", "per real run", None),
        ("Latest PR-AUC", "n/a" if latest is None or pd.isna(latest.pr_auc)
         else f"{latest.pr_auc:.3f}",
         None if latest is None or pd.isna(latest.baseline_pr_auc)
         else f"random {latest.baseline_pr_auc:.3f}", "Test PR-AUC of the newest successful run."),
    ])


def _table(frame: pd.DataFrame) -> None:
    checks = frame[["report_pass", "report_warning", "report_error"]].astype("Int64")
    table = pd.DataFrame({
        "started": frame.when.dt.strftime("%d %b %Y %H:%M"),
        "source": frame.source_name,
        "status": frame.status,
        "model": frame.selected_model,
        "PR-AUC": frame.pr_auc,
        "fail recall": frame.recall,
        "rows": frame.rows.astype("Int64"),
        "fail rate": frame.fail_rate,
        "run time (min)": frame.duration_s / 60,
        "tokens": frame.total_tokens.astype("Int64"),
        "report checks": [f"{p} / {w} / {e}" if pd.notna(p) else ""
                          for p, w, e in checks.itertuples(index=False)],
        "run id": frame.run_id,
    })
    number = st.column_config.NumberColumn
    ui.table(table, {"PR-AUC": number(format="%.3f"), "fail recall": number(format="%.3f"),
                     "fail rate": number(format="percent"),
                     "run time (min)": number(format="%.1f"),
                     "report checks": st.column_config.TextColumn(
                         help="PASS / WARNING / ERROR of the report's automatic checks")},
             max_rows=15)


def render(settings: Settings) -> None:
    ui.page_header("Trends")
    frame, source, error = store.run_history(settings)
    where = ("Supabase run registry" if source == "supabase"
             else "the run folders on this server (Supabase is not connected)")
    if error:
        st.warning(f"The Supabase run registry could not be read ({error}); showing the run "
                   "folders on this server instead.", icon=":material/cloud_off:")
    if frame.empty:
        st.info("No runs recorded yet. Start one on Run Pipeline.", icon=":material/insights:")
        return
    frame = _prepare(frame)
    names = list(dict.fromkeys(frame.source_name))
    chosen = st.pills("Data", names, default=names, selection_mode="multi", key="trend-sources",
                      label_visibility="collapsed")
    frame = frame[frame.source_name.isin(chosen or names)]
    st.caption(f"{len(frame)} runs from {where}.",
               help="Runs on the built-in SECOM data give the same model numbers every time "
                    "(fixed seed); the lines move when the data changes.")
    _kpis(frame)

    def run_time() -> None:
        recent = frame.sort_values("when").tail(15)
        charts.run_time_trend(recent, store.stage_history(settings, list(recent.run_id), source))

    # Phase 8.7: two cards with two tabs each (on a phone, one card with four tabs)
    ui.cards([[("Model quality over runs", lambda: charts.quality_trend(frame), "Model quality"),
               ("LLM tokens per run", lambda: charts.tokens_trend(frame), "Tokens")],
              [("Run outcomes", lambda: _outcomes(frame, settings.analytics.test_fraction),
                "Outcomes"),
               ("Where the run time goes", run_time, "Run time")]], "trends")

    if ui.extended(["Run table"], "trends") == "Run table":
        _table(frame.sort_values("when", ascending=False))


STATUS_COLORS = {"success": "green", "failed": "red", "timeout": "orange",
                 "interrupted": "orange", "stopped": "orange"}


def _outcomes(frame: pd.DataFrame, test_fraction: float, limit: int = 6) -> None:
    """How many runs ended how, then a list of the runs that stopped, newest first, each with
    its reason in plain words (the technical reason is in the run table)."""
    from app.messages import explain_reason

    counts = frame.status.value_counts()
    st.markdown(" ".join(f":{STATUS_COLORS.get(status, 'gray')}-badge[{n} {status}]"
                         for status, n in counts.items()))
    stopped = frame[frame.status.ne("success")].sort_values("when", ascending=False)
    if stopped.empty:
        st.caption("Every recorded run completed.")
        return
    items = []
    for row in stopped.head(limit).itertuples():
        reason = explain_reason(row.status, row.failure_reason, test_fraction)
        items.append(f"- :{STATUS_COLORS.get(row.status, 'gray')}-badge[{row.status}] "
                     f"**{row.label}** · {row.source_name}  \n  {ui.md(reason)}")
    st.markdown("\n".join(items))
    if len(stopped) > limit:
        st.caption(f"{len(stopped) - limit} more in the run table under Extended data.")
