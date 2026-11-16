"""Risk ranking: combine the model's fail probability with the anomaly score.

Both signals are turned into percentile ranks within the batch being scored (a CV fold, or the
test period) and averaged. The combined ranking is only recommended if it beats the model alone
in time-ordered CV on the training split, so the test period is never used to decide.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_score, recall_score

from foresight.analytics.modeling import BASELINE, bootstrap_ci, budget_flags
from foresight.settings import AnalyticsSettings

SIGNALS = ("model", "anomaly", "combined")


def _scores(group: pd.DataFrame) -> dict[str, np.ndarray]:
    model = group["fail_probability"].rank(pct=True).to_numpy()
    anomaly = group["anomaly_score"].rank(pct=True).to_numpy()
    return {"model": model, "anomaly": anomaly, "combined": (model + anomaly) / 2}


def _metrics(y: np.ndarray, score: np.ndarray, budget: float) -> dict[str, float]:
    flags = budget_flags(score, budget)
    return {
        "pr_auc": float(average_precision_score(y, score)) if y.sum() else float("nan"),
        "recall_at_budget": float(recall_score(y, flags, zero_division=0)),
        "precision_at_budget": float(precision_score(y, flags, zero_division=0)),
    }


def _mean(values: list[dict], key: str) -> float | None:
    usable = [v[key] for v in values if not np.isnan(v[key])]
    return round(float(np.mean(usable)), 4) if usable else None


def rank_risk(run_dir: Path, cfg: AnalyticsSettings, seed: int) -> dict:
    anomalies = pd.read_csv(run_dir / "anomalies.csv")[["run_id", "anomaly_score",
                                                          "n_out_of_limit", "top_signals"]]
    oof = pd.read_csv(run_dir / "oof_predictions.csv").merge(anomalies, on="run_id")
    test = pd.read_csv(run_dir / "predictions.csv").merge(anomalies, on="run_id")
    budget = cfg.alarm_budget

    per_fold: dict[str, list[dict]] = {s: [] for s in SIGNALS}
    for _, group in oof.groupby("fold"):
        y = group["label"].to_numpy()
        if not y.sum():
            continue
        for name, score in _scores(group).items():
            per_fold[name].append(_metrics(y, score, budget))
    cv = {name: {key: _mean(values, key) for key in ("pr_auc", "recall_at_budget",
                                                       "precision_at_budget")}
          for name, values in per_fold.items()}
    combined_wins = (cv["combined"]["pr_auc"] or 0) > (cv["model"]["pr_auc"] or 0)
    recommended = "combined" if combined_wins else "model"

    y_test = test["label"].to_numpy()
    test_scores = _scores(test)
    test_metrics = {name: {k: round(v, 4) for k, v in _metrics(y_test, s, budget).items()}
                    for name, s in test_scores.items()}
    chosen = test_scores[recommended]
    ci = bootstrap_ci(y_test, chosen, {"type": "budget", "value": budget},
                      cfg.bootstrap_samples, seed)

    test = test.assign(model_rank=test_scores["model"], anomaly_rank=test_scores["anomaly"],
                       combined_score=test_scores["combined"], risk_score=chosen,
                       flagged=budget_flags(chosen, budget))
    columns = ["run_id", "timestamp", "label", "fail_probability", "anomaly_score",
               "n_out_of_limit", "top_signals", "model_rank", "anomaly_rank", "combined_score",
               "risk_score", "flagged"]
    ranked = test[columns].sort_values(["risk_score", "run_id"], ascending=[False, True])
    ranked.round(5).to_csv(run_dir / "risk_scores.csv", index=False)

    summary = {
        "method": "percentile rank of model fail probability and anomaly score within the "
                  "scored batch, averaged; recommended only if it beats the model alone in "
                  "time-ordered CV on the training split",
        "alarm_budget": budget,
        "random_recall_at_budget": budget,
        "cv_mean_per_fold": cv,
        "recommended_ranking": recommended,
        "test": test_metrics,
        "test_recommended_ci95": {k: ci[k] for k in ("pr_auc", "recall_fail", "precision_fail")
                                  if k in ci},
        "top_risk_runs": [
            {"run_id": int(r.run_id), "timestamp": str(r.timestamp), "label": int(r.label),
             "risk_score": round(float(r.risk_score), 4),
             "fail_probability": float(r.fail_probability),
             "anomaly_score": float(r.anomaly_score), "top_signals": r.top_signals
             if isinstance(r.top_signals, str) else ""}
            for r in ranked.head(cfg.top_features).itertuples()
        ],
        "note": f"Random flagging of {budget:.0%} of runs finds about {budget:.0%} of failing "
                "runs; recall at budget above that means the ranking adds value.",
        "excluded_models": [BASELINE],
    }
    (run_dir / "risk_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
