"""Interactive Plotly charts built from a run's files (the PNG figures stay in the run folder
for the reports). One template keeps every chart in the app's theme."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

CYAN, VIOLET, AMBER, GREEN, RED, SLATE = ("#22D3EE", "#A78BFA", "#FBBF24", "#34D399", "#F87171",
                                          "#64748B")
GRID = "rgba(148,163,184,0.10)"
# Charts that share a row have the same height, so their tops and bottoms line up.
ROW_HEIGHT, MODEL_HEIGHT, DETAIL_HEIGHT = 420, 360, 460

pio.templates["foresight"] = go.layout.Template(layout=go.Layout(
    font={"family": "Inter, sans-serif", "color": "#CBD5E1", "size": 13},
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    colorway=[CYAN, VIOLET, AMBER, GREEN, RED, "#60A5FA"],
    xaxis={"gridcolor": GRID, "zerolinecolor": GRID, "linecolor": GRID},
    yaxis={"gridcolor": GRID, "zerolinecolor": GRID, "linecolor": GRID},
    legend={"orientation": "h", "y": 1.08, "x": 0, "bgcolor": "rgba(0,0,0,0)"},
    hoverlabel={"bgcolor": "#0E1626", "bordercolor": CYAN, "font": {"color": "#E2E8F0"}},
    margin={"l": 10, "r": 10, "t": 40, "b": 10},
))


def show(fig: go.Figure, key: str, height: int = 380) -> None:
    fig.update_layout(template="foresight", height=height)
    st.plotly_chart(fig, key=key, config={"displaylogo": False,
                                          "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


@st.cache_data(show_spinner=False)
def _csv(path: str, mtime: float, columns: tuple[str, ...] | None = None) -> pd.DataFrame:
    return pd.read_csv(path, usecols=list(columns) if columns else None)


def read_csv(run_dir: Path, name: str,
             columns: tuple[str, ...] | None = None) -> pd.DataFrame | None:
    path = run_dir / name
    return _csv(str(path), path.stat().st_mtime, columns) if path.exists() else None


def _runs(frame: pd.DataFrame, mask, name: str, color: str, size: int, hover: str,
          custom: list[str], opacity: float = 0.9, **xy) -> go.Scattergl:
    part = frame[mask]
    return go.Scattergl(**{k: part[v] for k, v in xy.items()}, mode="markers", name=name,
                        marker={"color": color, "size": size, "opacity": opacity,
                                "line": {"width": 0}},
                        customdata=part[custom].to_numpy(), hovertemplate=hover)


def anomaly_timeline(run_dir: Path, score_limit: float) -> None:
    """Anomaly score of every run over time; failing runs stand out, the line is the flag
    limit (95% quantile of training scores)."""
    frame = read_csv(run_dir, "anomalies.csv", ("run_id", "timestamp", "label", "split",
                                                "anomaly_score", "n_out_of_limit",
                                                "top_signals"))
    if frame is None:
        return
    hover = ("Run %{customdata[0]}<br>%{x|%d %b %Y %H:%M}<br>Score %{y:.3f}"
             "<br>%{customdata[1]} sensors out of limits<br>%{customdata[2]}<extra></extra>")
    custom = ["run_id", "n_out_of_limit", "top_signals"]
    fig = go.Figure([
        _runs(frame, frame.label == 0, "passing runs", SLATE, 5, hover, custom, 0.55,
              x="timestamp", y="anomaly_score"),
        _runs(frame, frame.label == 1, "failing runs", AMBER, 8, hover, custom,
              x="timestamp", y="anomaly_score"),
    ])
    fig.add_hline(y=score_limit, line={"color": CYAN, "dash": "dot", "width": 1.5},
                  annotation_text="flag limit", annotation_font_color=CYAN)
    test = frame.loc[frame.split == "test", "timestamp"]
    if not test.empty:
        fig.add_vrect(x0=test.min(), x1=test.max(), fillcolor=VIOLET, opacity=0.06,
                      line_width=0, annotation_text="test period",
                      annotation_font_color=VIOLET, annotation_position="top left")
    fig.update_layout(yaxis_title="anomaly score", xaxis_title=None)
    show(fig, "anomaly-timeline")


def _focus(values: pd.Series) -> tuple[list[float], int]:
    """Axis range around the main cloud (1st-99th percentile, padded) and how many runs fall
    outside it; a few extreme runs would otherwise squash the rest into a corner."""
    low, high = values.quantile([0.01, 0.99])
    pad = (high - low) * 0.15
    return [low - pad, high + pad], int(((values < low - pad) | (values > high + pad)).sum())


def run_map(run_dir: Path, three_d: bool = False) -> None:
    """Runs placed by their first principal components of the sensor profile: training runs
    as faint dots, test-period runs coloured by outcome."""
    columns = ("run_id", "label", "split", "pc1", "pc2", "pc3")
    frame = read_csv(run_dir, "run_embeddings.csv", columns)
    if frame is None:
        return
    groups = [(frame.split == "train", "training runs", SLATE, 4, 0.35),
              ((frame.split == "test") & (frame.label == 0), "test: passing", CYAN, 5, 0.8),
              ((frame.split == "test") & (frame.label == 1), "test: failing", AMBER, 8, 1.0)]
    hover = "Run %{customdata[0]}<extra></extra>"
    ranges = {axis: _focus(frame[axis]) for axis in ("pc1", "pc2", "pc3")}
    shown = ("pc1", "pc2", "pc3") if three_d else ("pc1", "pc2")
    outside = int(sum(~frame[a].between(*ranges[a][0]) for a in shown).astype(bool).sum())
    if three_d:
        fig = go.Figure([go.Scatter3d(x=frame[m].pc1, y=frame[m].pc2, z=frame[m].pc3,
                                      mode="markers", name=name,
                                      marker={"color": color, "size": size / 2,
                                              "opacity": alpha},
                                      customdata=frame[m][["run_id"]].to_numpy(),
                                      hovertemplate=hover)
                         for m, name, color, size, alpha in groups])
        axis = {"backgroundcolor": "rgba(0,0,0,0)", "gridcolor": GRID, "showbackground": False}
        fig.update_layout(scene={f"{k}axis": {**axis, "title": pc.upper(),
                                              "range": ranges[pc][0]}
                                 for k, pc in zip("xyz", shown, strict=True)})
        show(fig, "run-map-3d")
    else:
        fig = go.Figure([_runs(frame, m, name, color, size, hover, ["run_id"], alpha,
                               x="pc1", y="pc2")
                         for m, name, color, size, alpha in groups])
        fig.update_layout(xaxis={"title": "PC1", "range": ranges["pc1"][0]},
                          yaxis={"title": "PC2", "range": ranges["pc2"][0]})
        show(fig, "run-map")
    if outside:
        st.caption(f"{outside} unusual runs lie outside this view; "
                   + ("zoom out to see them." if three_d
                      else "double-click the chart to zoom out to every run."))



def weekly_fail_rate(eda: dict) -> None:
    """Runs per week (bars) and the weekly fail rate (line)."""
    weeks = pd.DataFrame(eda.get("weekly_fail_rate", []))
    if weeks.empty:
        return
    fig = go.Figure([
        go.Bar(x=weeks.week, y=weeks.runs, name="runs per week", marker_color=SLATE,
               opacity=0.35, yaxis="y2",
               hovertemplate="Week of %{x}<br>%{y} runs<extra></extra>"),
        go.Scatter(x=weeks.week, y=weeks.fail_rate, name="fail rate", mode="lines+markers",
                   line={"color": AMBER, "width": 2.5},
                   marker={"size": 7}, customdata=weeks[["fails", "runs"]].to_numpy(),
                   hovertemplate="Week of %{x}<br>fail rate %{y:.1%}"
                                 "<br>%{customdata[0]} of %{customdata[1]} runs<extra></extra>"),
    ])
    fig.update_layout(yaxis={"title": "fail rate", "tickformat": ".0%"},
                      yaxis2={"overlaying": "y", "side": "right", "showgrid": False,
                              "title": "runs", "tickformat": ",d"})
    show(fig, "weekly-fail-rate", height=ROW_HEIGHT)


def sensor_differences(eda: dict, limit: int = 14) -> None:
    """Effect size of the sensors that differ most between failing and passing runs."""
    table = pd.DataFrame(eda.get("top_discriminating_features", [])).head(limit)
    if table.empty:
        return
    table = table.iloc[::-1]
    colors = [AMBER if d.startswith("higher") else VIOLET for d in table.direction]
    fig = go.Figure(go.Bar(
        x=table.effect.abs(), y=table.feature, orientation="h", marker_color=colors,
        customdata=table[["direction", "q_value", "median_fail", "median_pass"]].to_numpy(),
        hovertemplate="%{y}: %{customdata[0]}<br>effect %{x:.3f} · q = %{customdata[1]:.2g}"
                      "<br>median failing %{customdata[2]} vs passing %{customdata[3]}"
                      "<extra></extra>"))
    fig.update_layout(xaxis_title="effect size (amber: higher in failing runs, violet: lower)",
                      yaxis={"type": "category"}, showlegend=False)
    show(fig, "sensor-differences", height=ROW_HEIGHT)


def risk_over_time(run_dir: Path, cutoff: float | None, threshold: float | None) -> None:
    """Model risk score of every test-period run; the alarm cutoff flags the riskiest runs."""
    frame = read_csv(run_dir, "predictions.csv", ("run_id", "timestamp", "label",
                                                  "fail_probability"))
    if frame is None:
        return
    hover = ("Run %{customdata[0]}<br>%{x|%d %b %Y %H:%M}<br>risk %{y:.3f}<extra></extra>")
    fig = go.Figure([
        _runs(frame, frame.label == 0, "passing runs", SLATE, 6, hover, ["run_id"], 0.6,
              x="timestamp", y="fail_probability"),
        _runs(frame, frame.label == 1, "failing runs", AMBER, 9, hover, ["run_id"],
              x="timestamp", y="fail_probability"),
    ])
    if cutoff is not None:
        fig.add_hline(y=cutoff, line={"color": CYAN, "dash": "dot", "width": 1.5},
                      annotation_text="alarm cutoff", annotation_font_color=CYAN)
    if threshold is not None:
        fig.add_hline(y=threshold, line={"color": VIOLET, "dash": "dash", "width": 1},
                      annotation_text="fixed threshold", annotation_position="bottom right",
                      annotation_font_color=VIOLET)
    fig.update_layout(yaxis_title="risk score")
    show(fig, "risk-over-time", height=MODEL_HEIGHT)


def pr_curve(run_dir: Path, baseline: float) -> None:
    """Precision-recall curve on the test period against random guessing."""
    from sklearn.metrics import precision_recall_curve

    frame = read_csv(run_dir, "predictions.csv", ("label", "fail_probability"))
    if frame is None or frame.label.nunique() < 2:
        return
    precision, recall, _ = precision_recall_curve(frame.label, frame.fail_probability)
    fig = go.Figure([
        go.Scatter(x=recall, y=precision, mode="lines", name="selected model",
                   line={"color": CYAN, "width": 2.5, "shape": "hv"}, fill="tozeroy",
                   fillcolor="rgba(34,211,238,0.10)",
                   hovertemplate="recall %{x:.2f}<br>precision %{y:.2f}<extra></extra>"),
        go.Scatter(x=[0, 1], y=[baseline, baseline], mode="lines", name="random guessing",
                   line={"color": AMBER, "dash": "dot"}, hoverinfo="skip"),
    ])
    fig.update_layout(xaxis={"title": "recall (failing runs found)", "range": [0, 1]},
                      yaxis={"title": "precision", "range": [0, 1.02]})
    show(fig, "pr-curve", height=MODEL_HEIGHT)


def confusion(cm: dict) -> None:
    """Alarms against outcomes on the test period."""
    z = [[cm["tp"], cm["fn"]], [cm["fp"], cm["tn"]]]
    text = [[f"{cm['tp']}<br>caught", f"{cm['fn']}<br>missed"],
            [f"{cm['fp']}<br>false alarms", f"{cm['tn']}<br>correctly quiet"]]
    fig = go.Figure(go.Heatmap(
        z=z, x=["alarm", "no alarm"], y=["failing run", "passing run"], text=text,
        texttemplate="%{text}", textfont={"size": 15, "color": "#F1F5F9"}, showscale=False,
        hoverinfo="skip",
        colorscale=[[0, "rgba(34,211,238,0.06)"], [1, "rgba(34,211,238,0.55)"]]))
    fig.update_layout(yaxis={"autorange": "reversed"}, xaxis={"side": "top"})
    show(fig, "confusion", height=MODEL_HEIGHT)


def importance(metrics: dict, limit: int = 12) -> None:
    """Permutation importance of the most important sensors (with its spread)."""
    table = pd.DataFrame(metrics.get("top_features_permutation") or []).head(limit)
    if table.empty:
        return
    table = table.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=table.importance_mean, y=table.feature, orientation="h", marker_color=VIOLET,
        error_x={"type": "data", "array": table.importance_std, "color": "#CBD5E1",
                 "thickness": 1},
        hovertemplate="%{y}: %{x:.4f}<extra></extra>"))
    fig.update_layout(xaxis_title="drop in PR-AUC when the sensor is shuffled",
                      yaxis={"type": "category"}, showlegend=False)
    show(fig, "importance", height=MODEL_HEIGHT)


def missing_by_sensor(run_dir: Path, limit: int = 20) -> None:
    """Share of runs with a missing value, for the sensors with the most gaps."""
    frame = read_csv(run_dir, "clean_data.csv")
    if frame is None:
        return
    sensors = [c for c in frame.columns if c.startswith("f_")]
    share = frame[sensors].isna().mean()
    share = share[share > 0].sort_values(ascending=False).head(limit).iloc[::-1]
    if share.empty:
        st.caption("No sensor has missing values.")
        return
    fig = go.Figure(go.Bar(x=share.values, y=share.index, orientation="h", marker_color=VIOLET,
                           hovertemplate="%{y}: %{x:.1%} of runs missing<extra></extra>"))
    fig.update_layout(xaxis={"title": "share of runs with a missing value", "tickformat": ".0%"},
                      yaxis={"type": "category"}, showlegend=False)
    show(fig, "missing-by-sensor", height=DETAIL_HEIGHT)


def correlation(run_dir: Path, sensors: list[str], limit: int = 15) -> None:
    """Pearson correlation between the sensors that differ most (near duplicates stand out)."""
    names = tuple(sensors[:limit])
    frame = read_csv(run_dir, "clean_data.csv", names) if names else None
    if frame is None or frame.empty:
        return
    corr = frame[list(names)].corr()
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=list(names), y=list(names), zmin=-1, zmax=1, zmid=0,
        colorscale=[[0, VIOLET], [0.5, "#0E1626"], [1, CYAN]],
        colorbar={"thickness": 10, "outlinewidth": 0},
        hovertemplate="%{x} vs %{y}: r = %{z:.2f}<extra></extra>"))
    fig.update_layout(yaxis={"autorange": "reversed", "type": "category"},
                      xaxis={"type": "category", "tickangle": -45})
    show(fig, "correlation", height=DETAIL_HEIGHT)
