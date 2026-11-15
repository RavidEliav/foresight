"""Time split and feature engineering (fitted on the training split only)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel

from foresight.data.cleaning import META_COLUMNS, feature_columns

SPLIT = "split"
ENGINEERED = ["missing_count"]


class FeatureSpec(BaseModel):
    features: list[str]
    engineered: list[str]
    dropped_correlated: list[str]
    corr_threshold: float
    test_fraction: float
    split_counts: dict[str, dict[str, int]]
    test_start: str


def time_split(frame: pd.DataFrame, test_fraction: float) -> pd.Series:
    """'train' for the earliest runs, 'test' for the last ``test_fraction`` (time-sorted)."""
    n_train = int(len(frame) * (1 - test_fraction))
    return pd.Series(np.where(np.arange(len(frame)) < n_train, "train", "test"),
                     index=frame.index, name=SPLIT)


def _correlated_to_drop(train: pd.DataFrame, threshold: float) -> list[str]:
    corr = train.corr().abs().to_numpy()
    columns = list(train.columns)
    dropped: set[int] = set()
    for i in range(len(columns)):
        if i in dropped:
            continue
        for j in np.nonzero(corr[i, i + 1:] > threshold)[0] + i + 1:
            dropped.add(int(j))
    return [columns[j] for j in sorted(dropped)]


def engineer(cleaned: pd.DataFrame, test_fraction: float,
             corr_threshold: float) -> tuple[pd.DataFrame, FeatureSpec]:
    split = time_split(cleaned, test_fraction)
    base = feature_columns(cleaned)
    dropped = _correlated_to_drop(cleaned.loc[split == "train", base], corr_threshold)
    kept = [c for c in base if c not in dropped]

    frame = cleaned[META_COLUMNS].copy()
    frame[SPLIT] = split
    frame = pd.concat(
        [frame, cleaned[kept], cleaned[base].isna().sum(axis=1).rename("missing_count")], axis=1)

    counts = {
        name: {"runs": int((split == name).sum()),
               "fails": int(cleaned.loc[split == name, "label"].sum())}
        for name in ("train", "test")
    }
    test_rows = cleaned.loc[split == "test", "timestamp"]
    spec = FeatureSpec(
        features=kept + ENGINEERED,
        engineered=ENGINEERED,
        dropped_correlated=dropped,
        corr_threshold=corr_threshold,
        test_fraction=test_fraction,
        split_counts=counts,
        test_start=str(test_rows.iloc[0]) if len(test_rows) else "",
    )
    return frame, spec


def xy(frame: pd.DataFrame, spec: FeatureSpec, split: str | None = None):
    rows = frame if split is None else frame[frame[SPLIT] == split]
    return rows[spec.features], rows["label"].astype(int)
