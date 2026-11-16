"""Anomaly detection: IsolationForest scores and SPC-style robust z-scores per sensor.

Both are fitted on the training split only and applied to every run.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer

from foresight.analytics import figures
from foresight.analytics.features import SPLIT, FeatureSpec
from foresight.settings import AnalyticsSettings


def robust_z(frame: pd.DataFrame, train: pd.DataFrame) -> pd.DataFrame:
    """(x - median) / (1.4826 * MAD) with training statistics; sensors with MAD 0 use the std."""
    median = train.median()
    scale = 1.4826 * (train - median).abs().median()
    scale = scale.where(scale > 0, train.std())
    scale = scale.where(scale > 0)
    return (frame - median) / scale


def detect(frame: pd.DataFrame, spec: FeatureSpec, cfg: AnalyticsSettings, seed: int,
           out_dir: Path) -> dict:
    sensors = [f for f in spec.features if f not in spec.engineered]
    train_mask = frame[SPLIT] == "train"

    imputer = SimpleImputer(strategy="median").fit(frame.loc[train_mask, sensors])
    filled = pd.DataFrame(imputer.transform(frame[sensors]), columns=sensors, index=frame.index)
    forest = IsolationForest(n_estimators=200, random_state=seed).fit(filled[train_mask])
    score = -forest.score_samples(filled)
    limit = float(np.quantile(score[train_mask.to_numpy()], cfg.anomaly_quantile))

    z = robust_z(frame[sensors], frame.loc[train_mask, sensors])
    beyond = z.abs() > cfg.z_limit
    top_signals = []
    for _, row in z.abs().iterrows():
        strongest = row.dropna().nlargest(3)
        top_signals.append("; ".join(
            f"{name}:{z.at[row.name, name]:+.1f}" for name in strongest.index
            if strongest[name] > cfg.z_limit))

    result = frame[["run_id", "timestamp", "label", SPLIT]].copy()
    result["anomaly_score"] = np.round(score, 5)
    result["is_anomaly"] = score > limit
    result["n_out_of_limit"] = beyond.sum(axis=1)
    result["top_signals"] = top_signals
    result.to_csv(out_dir / "anomalies.csv", index=False, date_format="%Y-%m-%dT%H:%M:%S")

    summary = _summarize(result, beyond, frame["label"], limit, cfg)
    summary["figures"] = {"anomaly_scores": str(_plot(result, limit, out_dir / "figures" /
                                                      "anomaly_scores.png").relative_to(out_dir).as_posix())}
    (out_dir / "anomaly_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _rate(series: pd.Series) -> float:
    return round(float(series.mean()), 4) if len(series) else 0.0


def _summarize(result: pd.DataFrame, beyond: pd.DataFrame, labels: pd.Series, limit: float,
               cfg: AnalyticsSettings) -> dict:
    fails, passes = labels == 1, labels == 0
    fail_rate_flagged = _rate(result.loc[fails, "is_anomaly"])
    pass_rate_flagged = _rate(result.loc[passes, "is_anomaly"])
    fail_share = beyond[fails].mean()
    pass_share = beyond[passes].mean()
    sensors = pd.DataFrame({
        "out_of_limit_rate_fail": fail_share,
        "out_of_limit_rate_pass": pass_share,
        "difference": fail_share - pass_share,
    }).sort_values(["difference"], ascending=False)
    flagged = result[result["is_anomaly"]].sort_values("anomaly_score", ascending=False)
    return {
        "method": {
            "isolation_forest": f"200 trees, fitted on training runs; flag = score above the "
                                f"{cfg.anomaly_quantile:.0%} quantile of training scores",
            "spc": f"robust z-score per sensor (training median and MAD); out of limit = "
                   f"|z| > {cfg.z_limit}",
        },
        "score_limit": round(limit, 5),
        "runs_flagged": int(result["is_anomaly"].sum()),
        "flag_rate_fail": fail_rate_flagged,
        "flag_rate_pass": pass_rate_flagged,
        "flag_lift": round(fail_rate_flagged / pass_rate_flagged, 3) if pass_rate_flagged else None,
        "flag_rate_test_fail": _rate(result.loc[fails & (result[SPLIT] == "test"), "is_anomaly"]),
        "mean_out_of_limit_fail": round(float(result.loc[fails, "n_out_of_limit"].mean()), 3),
        "mean_out_of_limit_pass": round(float(result.loc[passes, "n_out_of_limit"].mean()), 3),
        "sensors_more_often_out_of_limit_in_fails": [
            {"feature": name, **{k: round(float(v), 4) for k, v in row.items()}}
            for name, row in sensors.head(cfg.top_features).iterrows() if row["difference"] > 0
        ],
        "most_anomalous_runs": [
            {"run_id": int(r.run_id), "timestamp": str(r.timestamp), "label": int(r.label),
             "anomaly_score": float(r.anomaly_score), "n_out_of_limit": int(r.n_out_of_limit),
             "top_signals": r.top_signals}
            for r in flagged.head(cfg.top_features).itertuples()
        ],
    }


def _plot(result: pd.DataFrame, limit: float, path: Path) -> Path:
    fig, ax = figures.new_figure(9, 4.5)
    for label, color, name in ((0, figures.PASS_COLOR, "pass"), (1, figures.FAIL_COLOR, "fail")):
        rows = result[result["label"] == label]
        ax.scatter(rows["timestamp"], rows["anomaly_score"], s=10 if label == 0 else 24,
                   color=color, alpha=0.5 if label == 0 else 0.9, label=name)
    ax.axhline(limit, color="black", ls="--", lw=1, label="anomaly limit")
    test_start = result.loc[result[SPLIT] == "test", "timestamp"].min()
    if pd.notna(test_start):
        ax.axvline(test_start, color="gray", ls=":", label="test period starts")
    ax.set_ylabel("Anomaly score (higher = more unusual)")
    ax.set_title("IsolationForest anomaly score over time")
    ax.legend(fontsize=8)
    fig.autofmt_xdate()
    return figures.save(fig, path)
