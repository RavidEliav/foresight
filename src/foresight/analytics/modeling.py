"""Model training and evaluation for pass/fail prediction (ADR-010).

- Time-ordered split: models learn from the training split only; the test split is the
  last runs in time and is scored once.
- Model selection and the decision threshold use TimeSeriesSplit inside the training data.
- Test metrics come with bootstrap 95% confidence intervals.
- Stratified random CV is reported as an optimistic reference only.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit
from sklearn.pipeline import Pipeline

from foresight.analytics import figures
from foresight.analytics.features import FeatureSpec, xy
from foresight.settings import AnalyticsSettings

BASELINE = "baseline_always_pass"


class ModelVariant(BaseModel):
    name: str
    description: str


def _f_test(X, y):
    """ANOVA F-test that scores constant columns (in a fold) as 0 instead of warning."""
    with np.errstate(divide="ignore", invalid="ignore"):
        scores, p_values = f_classif(X, y)
    return np.nan_to_num(scores), np.nan_to_num(p_values, nan=1.0)


def build_models(cfg: AnalyticsSettings, seed: int) -> dict[str, tuple[str, Pipeline]]:
    def imputer():
        return SimpleImputer(strategy="median")

    def forest():
        return RandomForestClassifier(n_estimators=cfg.rf_trees, min_samples_leaf=3,
                                      class_weight="balanced_subsample", n_jobs=-1,
                                      random_state=seed)

    from sklearn.preprocessing import StandardScaler

    return {
        "logreg_l1": (
            "L1 logistic regression (balanced classes, sparse and interpretable)",
            Pipeline([("impute", imputer()), ("scale", StandardScaler()),
                      ("model", LogisticRegression(C=0.05, l1_ratio=1.0, solver="liblinear",
                                                   class_weight="balanced", max_iter=5000))]),
        ),
        "random_forest": (
            "Random forest on all features (balanced subsamples)",
            Pipeline([("impute", imputer()), ("model", forest())]),
        ),
        "rf_select_k": (
            f"Random forest on the top {cfg.select_k} features (ANOVA F-test, chosen inside "
            "each training fold)",
            Pipeline([("impute", imputer()),
                      ("select", SelectKBest(_f_test, k=cfg.select_k)),
                      ("model", forest())]),
        ),
        BASELINE: (
            "Always predicts pass (reference)",
            Pipeline([("model", DummyClassifier(strategy="most_frequent"))]),
        ),
    }


def _has_both_classes(y: pd.Series) -> bool:
    return y.nunique() == 2


def time_cv(model: Pipeline, X: pd.DataFrame, y: pd.Series, folds: int):
    """PR-AUC per usable fold and out-of-fold probabilities (NaN where not predicted)."""
    scores: list[float] = []
    oof = np.full(len(y), np.nan)
    for train_idx, val_idx in TimeSeriesSplit(n_splits=folds).split(X):
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        if not (_has_both_classes(y_train) and y_val.sum() > 0):
            continue
        fitted = clone(model).fit(X.iloc[train_idx], y_train)
        proba = fitted.predict_proba(X.iloc[val_idx])[:, 1]
        oof[val_idx] = proba
        scores.append(float(average_precision_score(y_val, proba)))
    return scores, oof


def stratified_cv(model: Pipeline, X: pd.DataFrame, y: pd.Series, folds: int, seed: int):
    folds = min(folds, int(y.sum()))
    if folds < 2:
        return []
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    scores = []
    for train_idx, val_idx in splitter.split(X, y):
        fitted = clone(model).fit(X.iloc[train_idx], y.iloc[train_idx])
        scores.append(float(average_precision_score(
            y.iloc[val_idx], fitted.predict_proba(X.iloc[val_idx])[:, 1])))
    return scores


def choose_threshold(y: np.ndarray, proba: np.ndarray, beta: float = 2.0) -> float:
    """Threshold maximizing F-beta (beta=2 weights recall of failing runs higher)."""
    mask = ~np.isnan(proba)
    if mask.sum() == 0 or y[mask].sum() == 0:
        return 0.5
    precision, recall, thresholds = precision_recall_curve(y[mask], proba[mask])
    precision, recall = precision[:-1], recall[:-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        score = (1 + beta**2) * precision * recall / (beta**2 * precision + recall)
    score = np.nan_to_num(score)
    return float(thresholds[int(np.argmax(score))])


def classification_metrics(y: np.ndarray, proba: np.ndarray, threshold: float) -> dict:
    pred = (proba >= threshold).astype(int)
    both = len(np.unique(y)) == 2
    return {
        "pr_auc": float(average_precision_score(y, proba)) if y.sum() else float("nan"),
        "roc_auc": float(roc_auc_score(y, proba)) if both else float("nan"),
        "recall_fail": float(recall_score(y, pred, zero_division=0)),
        "precision_fail": float(precision_score(y, pred, zero_division=0)),
        "f1_fail": float(f1_score(y, pred, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
    }


def bootstrap_ci(y: np.ndarray, proba: np.ndarray, threshold: float, samples: int,
                 seed: int) -> dict[str, list[float]]:
    rng = np.random.default_rng(seed)
    collected: dict[str, list[float]] = {}
    for _ in range(samples):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:
            continue
        for key, value in classification_metrics(y[idx], proba[idx], threshold).items():
            collected.setdefault(key, []).append(value)
    return {k: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
            for k, v in collected.items()}


def native_importance(model: Pipeline, features: list[str]) -> pd.Series:
    names = np.array(features)
    if "select" in model.named_steps:
        names = names[model.named_steps["select"].get_support()]
    estimator = model.named_steps["model"]
    if hasattr(estimator, "feature_importances_"):
        values = estimator.feature_importances_
    elif hasattr(estimator, "coef_"):
        values = np.abs(estimator.coef_[0])
    else:
        return pd.Series(dtype=float)
    return pd.Series(values, index=names).sort_values(ascending=False)


def permutation_importance_top(model: Pipeline, X: pd.DataFrame, y: pd.Series,
                               candidates: list[str], repeats: int, seed: int) -> pd.DataFrame:
    """Drop in test PR-AUC when one feature is shuffled (only for the candidate features)."""
    rng = np.random.default_rng(seed)
    base = average_precision_score(y, model.predict_proba(X)[:, 1])
    rows = []
    for feature in candidates:
        drops = []
        for _ in range(repeats):
            shuffled = X.copy()
            shuffled[feature] = rng.permutation(shuffled[feature].to_numpy())
            drops.append(base - average_precision_score(y, model.predict_proba(shuffled)[:, 1]))
        rows.append({"feature": feature, "importance_mean": float(np.mean(drops)),
                     "importance_std": float(np.std(drops))})
    return pd.DataFrame(rows).sort_values(["importance_mean", "feature"],
                                          ascending=[False, True]).reset_index(drop=True)


def train_and_evaluate(frame: pd.DataFrame, spec: FeatureSpec, cfg: AnalyticsSettings,
                       seed: int, out_dir: Path) -> dict:
    """Writes model.joblib, model_metrics.json, evaluation_report.md and figures."""
    X_train, y_train = xy(frame, spec, "train")
    X_test, y_test = xy(frame, spec, "test")
    models = build_models(cfg, seed)

    comparison: dict[str, dict] = {}
    oof_by_model: dict[str, np.ndarray] = {}
    test_proba: dict[str, np.ndarray] = {}
    fitted_models: dict[str, Pipeline] = {}
    for name, (description, model) in models.items():
        scores, oof = time_cv(model, X_train, y_train, cfg.cv_folds)
        fitted = clone(model).fit(X_train, y_train)
        proba = fitted.predict_proba(X_test)[:, 1]
        fitted_models[name], oof_by_model[name], test_proba[name] = fitted, oof, proba
        comparison[name] = {
            "description": description,
            "cv_pr_auc_mean": round(float(np.mean(scores)), 4) if scores else None,
            "cv_pr_auc_std": round(float(np.std(scores)), 4) if scores else None,
            "cv_folds_used": len(scores),
            "stratified_cv_pr_auc_mean": None,
            "test_pr_auc": round(float(average_precision_score(y_test, proba)), 4)
            if y_test.sum() else None,
            "test_roc_auc": round(float(roc_auc_score(y_test, proba)), 4)
            if y_test.nunique() == 2 else None,
        }

    candidates = {n: c for n, c in comparison.items()
                  if n != BASELINE and c["cv_pr_auc_mean"] is not None}
    best = max(candidates, key=lambda n: (candidates[n]["cv_pr_auc_mean"], n)) if candidates \
        else "logreg_l1"
    threshold = choose_threshold(y_train.to_numpy(), oof_by_model[best])

    X_all, y_all = xy(frame, spec)
    for name, (_, model) in models.items():
        if name != BASELINE:
            scores = stratified_cv(model, X_all, y_all, cfg.cv_folds, seed)
            comparison[name]["stratified_cv_pr_auc_mean"] = \
                round(float(np.mean(scores)), 4) if scores else None

    y_true, proba = y_test.to_numpy(), test_proba[best]
    test_metrics = {k: round(v, 4) for k, v in
                    classification_metrics(y_true, proba, threshold).items()}
    tn, fp, fn, tp = confusion_matrix(y_true, (proba >= threshold).astype(int),
                                      labels=[0, 1]).ravel()
    native = native_importance(fitted_models[best], spec.features)
    importance = permutation_importance_top(
        fitted_models[best], X_test, y_test, list(native.index[:cfg.permutation_top_n]),
        cfg.permutation_repeats, seed) if y_test.sum() and len(native) else pd.DataFrame()

    metrics = {
        "selected_model": best,
        "selection_rule": "highest mean PR-AUC in time-ordered CV on the training split",
        "threshold": round(threshold, 4),
        "threshold_rule": "maximizes F2 (recall weighted 2x) on out-of-fold CV predictions",
        "split": spec.split_counts,
        "test_start": spec.test_start,
        "baseline_pr_auc": round(float(y_test.mean()), 4),
        "test_metrics": test_metrics,
        "test_metrics_ci95": bootstrap_ci(y_true, proba, threshold, cfg.bootstrap_samples, seed),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "comparison": comparison,
        "top_features_native": [{"feature": f, "importance": round(float(v), 6)}
                                for f, v in native.head(cfg.top_features).items()],
        "top_features_permutation": [
            {k: (round(v, 6) if isinstance(v, float) else v) for k, v in row.items()}
            for row in importance.head(cfg.top_features).to_dict(orient="records")
        ],
    }

    fig_paths = _plot_evaluation(y_true, test_proba, best, threshold, metrics, importance,
                                 out_dir / "figures")
    metrics["figures"] = {k: str(v.relative_to(out_dir)) for k, v in fig_paths.items()}
    joblib.dump({"model": fitted_models[best], "name": best, "threshold": threshold,
                 "features": spec.features, "trained_on": "train split",
                 "test_start": spec.test_start}, out_dir / "model.joblib")
    test_rows = frame[frame["split"] == "test"]
    pd.DataFrame({
        "run_id": test_rows["run_id"].to_numpy(),
        "label": y_true,
        "fail_probability": np.round(proba, 5),
        "predicted_fail": (proba >= threshold).astype(int),
    }).to_csv(out_dir / "predictions.csv", index=False)
    (out_dir / "model_metrics.json").write_text(json.dumps(metrics, indent=2, default=str),
                                                encoding="utf-8")
    (out_dir / "evaluation_report.md").write_text(render_report(metrics), encoding="utf-8")
    return metrics


def _plot_evaluation(y_true, probas, best, threshold, metrics, importance, fig_dir: Path):
    paths = {}
    fig, ax = figures.new_figure(7, 5)
    for name, proba in probas.items():
        if name == BASELINE or not y_true.sum():
            continue
        precision, recall, _ = precision_recall_curve(y_true, proba)
        width = 2.5 if name == best else 1.2
        ax.plot(recall, precision, lw=width,
                label=f"{name} (AP {average_precision_score(y_true, proba):.3f})")
    ax.axhline(y_true.mean(), color="gray", ls="--", label=f"random ({y_true.mean():.3f})")
    ax.set_xlabel("Recall (failing runs found)")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-recall on the test period")
    ax.legend(fontsize=8)
    paths["pr_curve"] = figures.save(fig, fig_dir / "pr_curve.png")

    cm = metrics["confusion_matrix"]
    fig, ax = figures.new_figure(4.5, 4)
    grid = np.array([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]])
    ax.imshow(grid, cmap="Blues")
    for (i, j), value in np.ndenumerate(grid):
        ax.text(j, i, str(value), ha="center", va="center", fontsize=14)
    ax.set_xticks([0, 1], ["pred pass", "pred fail"])
    ax.set_yticks([0, 1], ["actual pass", "actual fail"])
    ax.set_title(f"{best} @ threshold {threshold:.3f}")
    paths["confusion_matrix"] = figures.save(fig, fig_dir / "confusion_matrix.png")

    if not importance.empty:
        top = importance.head(15).iloc[::-1]
        fig, ax = figures.new_figure(7, 5)
        ax.barh(top["feature"], top["importance_mean"], xerr=top["importance_std"],
                color=figures.FAIL_COLOR, alpha=0.8)
        ax.set_xlabel("Drop in test PR-AUC when shuffled")
        ax.set_title("Permutation importance (selected model)")
        paths["feature_importance"] = figures.save(fig, fig_dir / "feature_importance.png")
    return paths


def _fmt(value) -> str:
    return "n/a" if value is None or (isinstance(value, float) and np.isnan(value)) \
        else f"{value:.3f}"


def render_report(metrics: dict) -> str:
    """Numbers-first evaluation report. All values come from model_metrics.json."""
    t, ci, cm = metrics["test_metrics"], metrics["test_metrics_ci95"], metrics["confusion_matrix"]
    split = metrics["split"]
    rows = "\n".join(
        f"| {name} | {_fmt(c['cv_pr_auc_mean'])} ± {_fmt(c['cv_pr_auc_std'])} | "
        f"{_fmt(c['stratified_cv_pr_auc_mean'])} | {_fmt(c['test_pr_auc'])} | "
        f"{_fmt(c['test_roc_auc'])} | {c['description']} |"
        for name, c in metrics["comparison"].items()
    )
    metric_rows = "\n".join(
        f"| {name} | {_fmt(t[name])} | {_fmt(ci.get(name, [None])[0])} – "
        f"{_fmt(ci.get(name, [None, None])[1])} |"
        for name in ("pr_auc", "roc_auc", "recall_fail", "precision_fail", "f1_fail",
                     "balanced_accuracy")
    )
    top = "\n".join(f"| {r['feature']} | {r['importance_mean']:.4f} ± {r['importance_std']:.4f} |"
                    for r in metrics["top_features_permutation"]) or "| n/a | n/a |"
    return f"""# Evaluation report

## Setup
- **Split:** time-ordered. Train: {split['train']['runs']} runs ({split['train']['fails']} fails).
  Test: {split['test']['runs']} runs ({split['test']['fails']} fails), from {metrics['test_start']}.
- **Model selection:** {metrics['selection_rule']}.
- **Selected model:** `{metrics['selected_model']}`
- **Decision threshold:** {metrics['threshold']:.4f} ({metrics['threshold_rule']}).

## Model comparison (PR-AUC; random guessing = fail rate)
| Model | Time CV (train) | Stratified CV (optimistic) | Test PR-AUC | Test ROC-AUC | Description |
|---|---|---|---|---|---|
{rows}

Random-guessing PR-AUC on the test period: **{metrics['baseline_pr_auc']:.3f}**.

## Selected model on the test period
| Metric | Value | 95% bootstrap CI |
|---|---|---|
{metric_rows}

Confusion matrix at the threshold: {cm['tp']} failing runs caught, {cm['fn']} missed,
{cm['fp']} false alarms, {cm['tn']} passing runs correctly passed.

## Most important sensors (permutation importance on the test period)
| Sensor | Drop in PR-AUC when shuffled |
|---|---|
{top}

## Caveats
- The test period has only {split['test']['fails']} failing runs, so the confidence intervals
  are wide.
- Stratified CV mixes future runs into training and is shown only as an optimistic reference.
- Sensor names are anonymized; important sensors point to where to look, not to a cause.
"""
