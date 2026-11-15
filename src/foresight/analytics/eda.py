"""Descriptive analytics (EDA) on the cleaned dataset: statistics, charts and eda_report.html.

The EDA describes the whole dataset ("what happened"); models only learn from the training
split.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from foresight.analytics import figures
from foresight.data.cleaning import feature_columns, profile


def _bh(p_values: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (false discovery rate)."""
    n = len(p_values)
    order = np.argsort(p_values)
    ranked = p_values[order] * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(adjusted, 1.0)
    return out


def discriminating_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Mann-Whitney U test per feature, failing vs passing runs, with BH correction.

    effect = rank-biserial correlation in [-1, 1]; positive means higher values in fails.
    """
    fails = frame["label"] == 1
    rows = []
    for column in feature_columns(frame):
        fail_values = frame.loc[fails, column].dropna()
        pass_values = frame.loc[~fails, column].dropna()
        if len(fail_values) < 3 or len(pass_values) < 3:
            continue
        result = stats.mannwhitneyu(fail_values, pass_values, alternative="two-sided")
        effect = 2 * result.statistic / (len(fail_values) * len(pass_values)) - 1
        rows.append({
            "feature": column,
            "p_value": float(result.pvalue),
            "effect": float(effect),
            "median_fail": float(fail_values.median()),
            "median_pass": float(pass_values.median()),
            "direction": "higher in fails" if effect > 0 else "lower in fails",
        })
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    table["q_value"] = _bh(table["p_value"].to_numpy())
    return table.sort_values(["p_value", "feature"]).reset_index(drop=True)


def weekly_fail_rate(frame: pd.DataFrame) -> pd.DataFrame:
    weekly = frame.set_index("timestamp")["label"].resample("W").agg(["count", "sum"])
    weekly = weekly[weekly["count"] > 0]
    weekly["fail_rate"] = weekly["sum"] / weekly["count"]
    return weekly.rename(columns={"count": "runs", "sum": "fails"})


def _plot_fail_rate(weekly: pd.DataFrame, path: Path) -> Path:
    fig, ax = figures.new_figure()
    ax.bar(weekly.index, weekly["fail_rate"] * 100, width=5, color=figures.FAIL_COLOR, alpha=0.8)
    ax.set_ylabel("Fail rate (%)")
    ax.set_title("Weekly fail rate")
    twin = ax.twinx()
    twin.plot(weekly.index, weekly["runs"], color=figures.PASS_COLOR, marker="o")
    twin.set_ylabel("Runs per week", color=figures.PASS_COLOR)
    fig.autofmt_xdate()
    return figures.save(fig, path)


def _plot_missingness(frame: pd.DataFrame, path: Path) -> Path:
    ratios = frame[feature_columns(frame)].isna().mean()
    fig, ax = figures.new_figure()
    ax.hist(ratios[ratios > 0] * 100, bins=30, color=figures.PASS_COLOR)
    ax.set_xlabel("Missing values per feature (%)")
    ax.set_ylabel("Features")
    ax.set_title(f"Missingness ({int((ratios > 0).sum())} of {len(ratios)} features have gaps)")
    return figures.save(fig, path)


def _plot_top_features(frame: pd.DataFrame, top: list[str], path: Path) -> Path:
    fig, axes = figures.plt.subplots(2, 3, figsize=(10, 6), dpi=110)
    for ax, column in zip(axes.flat, top, strict=False):
        data = [frame.loc[frame["label"] == 0, column].dropna(),
                frame.loc[frame["label"] == 1, column].dropna()]
        parts = ax.boxplot(data, tick_labels=["pass", "fail"], patch_artist=True, showfliers=False)
        for patch, color in zip(parts["boxes"], (figures.PASS_COLOR, figures.FAIL_COLOR),
                                strict=True):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
        ax.set_title(column)
    for ax in list(axes.flat)[len(top):]:
        ax.axis("off")
    fig.suptitle("Sensors that differ most between failing and passing runs")
    return figures.save(fig, path)


def _plot_correlation(frame: pd.DataFrame, top: list[str], path: Path) -> Path:
    corr = frame[top].corr()
    fig, ax = figures.new_figure(7, 6)
    image = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(top)), top, rotation=90, fontsize=7)
    ax.set_yticks(range(len(top)), top, fontsize=7)
    fig.colorbar(image, ax=ax, shrink=0.8)
    ax.set_title("Correlation between the top discriminating sensors")
    return figures.save(fig, path)


def build_eda(cleaned: pd.DataFrame, out_dir: Path, top_n: int = 15) -> dict:
    """Write figures/, eda_summary.json and eda_report.html. Returns the summary."""
    fig_dir = out_dir / "figures"
    weekly = weekly_fail_rate(cleaned)
    tests = discriminating_features(cleaned)
    top = tests.head(top_n)
    features = feature_columns(cleaned)
    corr = cleaned[features].corr().abs().to_numpy()
    redundant_pairs = int((np.triu(corr, 1) > 0.95).sum())
    missing_per_run = cleaned[features].isna().sum(axis=1)

    fails = cleaned["label"] == 1
    summary = {
        "overview": profile(cleaned),
        "weekly_fail_rate": [
            {"week": f"{idx:%Y-%m-%d}", "runs": int(r.runs), "fails": int(r.fails),
             "fail_rate": round(float(r.fail_rate), 4)} for idx, r in weekly.iterrows()
        ],
        "monthly_fail_rate": {
            str(k): round(float(v), 4)
            for k, v in cleaned.groupby(cleaned["timestamp"].dt.to_period("M"))["label"]
            .mean().items()
        },
        "missingness": {
            "features_with_missing": int((cleaned[features].isna().any()).sum()),
            "mean_missing_per_run": round(float(missing_per_run.mean()), 3),
            "mean_missing_per_run_fail": round(float(missing_per_run[fails].mean()), 3),
            "mean_missing_per_run_pass": round(float(missing_per_run[~fails].mean()), 3),
        },
        "redundant_feature_pairs_over_0.95": redundant_pairs,
        "significant_features_q_below_0.05": int((tests["q_value"] < 0.05).sum())
        if not tests.empty else 0,
        "top_discriminating_features": [
            {k: (round(v, 6) if isinstance(v, float) else v) for k, v in row.items()}
            for row in top.to_dict(orient="records")
        ],
        "method_notes": [
            "Descriptive statistics over the whole dataset; models learn from the training "
            "split only.",
            "Pass vs fail per sensor: Mann-Whitney U test, Benjamini-Hochberg correction "
            "(q-value); effect is the rank-biserial correlation.",
            "A difference between failing and passing runs is a correlation, not a cause.",
        ],
    }

    paths = {
        "fail_rate_over_time": _plot_fail_rate(weekly, fig_dir / "fail_rate_over_time.png"),
        "missingness": _plot_missingness(cleaned, fig_dir / "missingness.png"),
    }
    if len(top):
        names = top["feature"].tolist()
        paths["top_features"] = _plot_top_features(cleaned, names[:6], fig_dir / "top_features.png")
        if len(names) > 1:
            paths["correlation"] = _plot_correlation(cleaned, names, fig_dir / "correlation.png")
    summary["figures"] = {k: str(v.relative_to(out_dir)) for k, v in paths.items()}

    (out_dir / "eda_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "eda_report.html").write_text(_render_html(summary, top, paths), encoding="utf-8")
    return summary


def _render_html(summary: dict, top: pd.DataFrame, paths: dict[str, Path]) -> str:
    o = summary["overview"]
    m = summary["missingness"]
    table = top[["feature", "direction", "effect", "p_value", "q_value", "median_pass",
                 "median_fail"]].to_html(index=False, float_format=lambda v: f"{v:.4g}",
                                         border=0) if len(top) else "<p>No features tested.</p>"
    months = "".join(f"<li>{html.escape(k)}: {v:.1%}</li>"
                     for k, v in summary["monthly_fail_rate"].items())
    images = "".join(f"<figure>{figures.embed(p)}</figure>" for p in paths.values())
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in summary["method_notes"])
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Foresight EDA report</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;max-width:1000px;margin:24px auto;color:#1f2937;
padding:0 16px}}
h1{{margin-bottom:4px}} .kpis{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}}
.kpi{{border:1px solid #e5e7eb;border-radius:10px;padding:10px 16px}}
.kpi b{{display:block;font-size:22px}} table{{border-collapse:collapse;font-size:13px}}
th,td{{padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:left}}
img{{max-width:100%}} figure{{margin:16px 0}}
</style></head><body>
<h1>SECOM exploratory data analysis</h1>
<p>Generated by Foresight from the cleaned dataset ({html.escape(o['time_range'][0])} to
{html.escape(o['time_range'][1])}).</p>
<div class="kpis">
<div class="kpi"><b>{o['rows']:,}</b>runs</div>
<div class="kpi"><b>{o['features']}</b>sensors</div>
<div class="kpi"><b>{o['fail_rate']:.1%}</b>fail rate</div>
<div class="kpi"><b>{o['missing_cells_ratio']:.2%}</b>missing cells</div>
<div class="kpi"><b>{summary['significant_features_q_below_0.05']}</b>sensors differ
(q&lt;0.05)</div>
</div>
<h2>Fail rate by month</h2><ul>{months}</ul>
<h2>Missing data</h2>
<p>{m['features_with_missing']} sensors have gaps. Failing runs miss on average
{m['mean_missing_per_run_fail']} values, passing runs {m['mean_missing_per_run_pass']}.</p>
<h2>Sensors that differ most between failing and passing runs</h2>{table}
<p>{summary['redundant_feature_pairs_over_0.95']} sensor pairs are almost duplicates
(|r| &gt; 0.95).</p>
<h2>Charts</h2>{images}
<h2>Method notes</h2><ul>{notes}</ul>
</body></html>
"""
