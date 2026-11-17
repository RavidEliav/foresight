"""Similar-run search (numeric run embeddings, requirements §18.1).

Each run is embedded with median imputation + standard scaling + PCA, all fitted on the
training runs only. For the riskiest and the failing test runs, the k nearest *training* runs
(all earlier in time, so no look-ahead) are retrieved with their labels and distances. The
evidence is honest about its strength: it compares how often the neighbours of failing vs
passing test runs failed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from foresight.analytics import figures
from foresight.analytics.features import SPLIT, FeatureSpec
from foresight.settings import AnalyticsSettings

EMBEDDINGS_FILE = "run_embeddings.csv"
SIMILAR_CSV = "similar_runs.csv"
SIMILAR_JSON = "similar_runs.json"


def embed_runs(frame: pd.DataFrame, spec: FeatureSpec, components: int,
               seed: int) -> tuple[pd.DataFrame, float]:
    """Run embeddings (PC1..PCn) for every run, and the explained variance ratio."""
    sensors = [f for f in spec.features if f not in spec.engineered]
    train = frame[SPLIT] == "train"
    n = max(2, min(components, int(train.sum()) - 1, len(sensors)))
    pipeline = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             PCA(n_components=n, random_state=seed))
    pipeline.fit(frame.loc[train, sensors])
    vectors = pipeline.transform(frame[sensors])
    embedded = pd.DataFrame(np.round(vectors, 5), columns=[f"pc{i + 1}" for i in range(n)])
    embedded.insert(0, "run_id", frame["run_id"].to_numpy())
    embedded.insert(1, "timestamp", frame["timestamp"].to_numpy())
    embedded.insert(2, "label", frame["label"].to_numpy())
    embedded.insert(3, SPLIT, frame[SPLIT].to_numpy())
    variance = float(pipeline.named_steps["pca"].explained_variance_ratio_.sum())
    return embedded, variance


def neighbours(embedded: pd.DataFrame, run_ids: list[int], k: int) -> pd.DataFrame:
    """The k nearest training runs of each query run (a training query excludes itself)."""
    pcs = [c for c in embedded.columns if c.startswith("pc")]
    history = embedded[embedded[SPLIT] == "train"].reset_index(drop=True)
    queries = embedded[embedded["run_id"].isin(run_ids)].drop_duplicates("run_id")
    if queries.empty:
        return pd.DataFrame()
    index = NearestNeighbors(n_neighbors=min(k + 1, len(history))).fit(history[pcs])
    distances, positions = index.kneighbors(queries[pcs])
    hist_ids = history["run_id"].to_numpy()
    rows = []
    for (_, query), dist, pos in zip(queries.iterrows(), distances, positions, strict=True):
        found = [(d, p) for d, p in zip(dist, pos, strict=True)
                 if hist_ids[p] != query["run_id"]][:k]
        for rank, (distance, p) in enumerate(found, start=1):
            rows.append({"query_run_id": int(query["run_id"]),
                         "query_label": int(query["label"]), "rank": rank,
                         "neighbour_run_id": int(hist_ids[p]),
                         "neighbour_timestamp": str(history.at[p, "timestamp"])[:19],
                         "neighbour_label": int(history.at[p, "label"]),
                         "distance": round(float(distance), 3)})
    return pd.DataFrame(rows)


def find_similar(frame: pd.DataFrame, spec: FeatureSpec, cfg: AnalyticsSettings, seed: int,
                 out_dir: Path) -> dict:
    embedded, variance = embed_runs(frame, spec, cfg.similar_components, seed)
    embedded.to_csv(out_dir / EMBEDDINGS_FILE, index=False, date_format="%Y-%m-%dT%H:%M:%S")
    k = cfg.similar_k
    test = embedded[embedded[SPLIT] == "test"]
    train_rate = float(embedded.loc[embedded[SPLIT] == "train", "label"].mean())

    # Does similarity carry signal? Neighbour fail share for every test run, by its label.
    every = neighbours(embedded, test["run_id"].tolist(), k)
    share = every.groupby("query_run_id")["neighbour_label"].mean()
    labels = test.set_index("run_id")["label"]
    fail_share = float(share[labels[labels == 1].index].mean()) if (labels == 1).any() else None
    pass_share = float(share[labels[labels == 0].index].mean()) if (labels == 0).any() else None

    risk = json.loads((out_dir / "risk_summary.json").read_text(encoding="utf-8")) \
        if (out_dir / "risk_summary.json").exists() else {}
    queries = [(int(r["run_id"]), "high risk") for r in risk.get("top_risk_runs", [])[:5]]
    queries += [(int(r), "failed") for r in labels[labels == 1].index
                if int(r) not in {q for q, _ in queries}]
    reason = dict(queries)
    table = every[every["query_run_id"].isin(reason)].copy()
    table.insert(1, "query_reason", table["query_run_id"].map(reason))
    table.to_csv(out_dir / SIMILAR_CSV, index=False)

    variance = round(variance, 3)  # one rounded value for the method text and the summary
    summary = {
        "method": f"median imputation + standard scaling + PCA ({embedded.shape[1] - 4} "
                  f"components, {variance:.0%} of variance), fitted on training runs; "
                  f"{k} nearest training runs (Euclidean), all earlier in time than the test "
                  "runs",
        "k": k,
        "explained_variance": variance,
        "train_fail_rate": round(train_rate, 4),
        "neighbour_fail_share_for_failing_test_runs": _round(fail_share),
        "neighbour_fail_share_for_passing_test_runs": _round(pass_share),
        "lift": round(fail_share / pass_share, 3) if fail_share and pass_share else None,
        "queries": [_query_summary(table, run_id, why) for run_id, why in queries
                    if run_id in set(table["query_run_id"])],
        "figures": {"run_map": _plot(embedded, out_dir / "figures" / "run_map.png")
                    .relative_to(out_dir).as_posix()},
    }
    (out_dir / SIMILAR_JSON).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _round(value: float | None) -> float | None:
    return None if value is None or np.isnan(value) else round(value, 4)


def _query_summary(table: pd.DataFrame, run_id: int, why: str) -> dict:
    rows = table[table["query_run_id"] == run_id]
    return {"run_id": run_id, "reason": why, "label": int(rows.iloc[0]["query_label"]),
            "neighbours_failed": int(rows["neighbour_label"].sum()), "k": len(rows),
            "nearest_distance": float(rows["distance"].min()),
            "neighbours": [{"run_id": int(r.neighbour_run_id), "label": int(r.neighbour_label),
                            "timestamp": r.neighbour_timestamp, "distance": float(r.distance)}
                           for r in rows.itertuples()]}


def _plot(embedded: pd.DataFrame, path: Path) -> Path:
    fig, ax = figures.new_figure(7, 5)
    for split, marker in (("train", "o"), ("test", "^")):
        for label, color, name in ((0, figures.PASS_COLOR, "pass"),
                                   (1, figures.FAIL_COLOR, "fail")):
            rows = embedded[(embedded[SPLIT] == split) & (embedded["label"] == label)]
            ax.scatter(rows["pc1"], rows["pc2"], s=10 if label == 0 else 26, marker=marker,
                       color=color, alpha=0.35 if label == 0 else 0.9, label=f"{split} {name}")
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title("Run map: each run's sensor profile in 2-D (PCA fitted on training runs)")
    ax.legend(fontsize=8)
    return figures.save(fig, path)
