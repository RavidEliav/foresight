"""Deterministic cleaning. Every decision is recorded in a CleaningReport.

Missing values are intentionally kept: imputation is fitted on the training split
inside the model pipeline (Phase 2) so test data never leaks into it.
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field

META_COLUMNS = ["run_id", "timestamp", "label"]
LABEL_MAPPING = {-1: 0, 1: 1}  # 0 = pass, 1 = fail


class CleaningConfig(BaseModel):
    max_missing_ratio: float = 0.5
    # Set from the Data Contract: keep exactly its features instead of re-deciding per dataset
    contract_features: list[str] | None = None
    contract_dropped: dict[str, list[str]] = Field(default_factory=dict)


class CleaningReport(BaseModel):
    rows_in: int
    rows_out: int
    features_in: int
    features_out: int
    duplicate_rows_dropped: int
    dropped_high_missing: list[str] = Field(default_factory=list)
    dropped_constant: list[str] = Field(default_factory=list)
    label_mapping: dict[str, int] = Field(
        default_factory=lambda: {str(k): v for k, v in LABEL_MAPPING.items()}
    )
    remaining_missing_ratio: float
    decisions: list[str] = Field(default_factory=list)


def feature_columns(frame: pd.DataFrame) -> list[str]:
    return [c for c in frame.columns if c.startswith("f_")]


def clean(
    raw: pd.DataFrame, config: CleaningConfig | None = None
) -> tuple[pd.DataFrame, CleaningReport]:
    config = config or CleaningConfig()
    features = feature_columns(raw)

    frame = raw.drop_duplicates(subset=features + ["timestamp"]).copy()
    duplicates = len(raw) - len(frame)
    frame = frame.sort_values(["timestamp", "run_id"], kind="stable").reset_index(drop=True)
    frame["label"] = frame.pop("label_raw").map(LABEL_MAPPING)

    if config.contract_features is not None:
        # Same columns as the reference data, so a subset or a newer batch stays comparable
        keep = set(config.contract_features)
        dropped = config.contract_dropped
        high_missing = sorted(set(dropped.get("high_missing", [])) & set(features))
        constant = sorted(set(dropped.get("constant", [])) & set(features))
        kept = [c for c in features if c in keep]
        other = len(features) - len(kept) - len(high_missing) - len(constant)
        column_decisions = [
            f"Applied the Data Contract: kept its {len(kept)} features.",
            f"Dropped {len(high_missing)} features the contract marks as more than "
            f"{config.max_missing_ratio:.0%} missing and {len(constant)} it marks as constant"
            + (f", and {other} other features not in the contract." if other else "."),
        ]
    else:
        missing = frame[features].isna().mean()
        high_missing = sorted(missing[missing > config.max_missing_ratio].index)
        remaining = [c for c in features if c not in high_missing]
        unique_counts = frame[remaining].nunique(dropna=True)
        constant = sorted(unique_counts[unique_counts <= 1].index)
        kept = [c for c in remaining if c not in constant]
        column_decisions = [
            f"Dropped {len(high_missing)} features with more than "
            f"{config.max_missing_ratio:.0%} missing values.",
            f"Dropped {len(constant)} constant features (one unique value).",
        ]

    cleaned = frame[META_COLUMNS + kept]
    report = CleaningReport(
        rows_in=len(raw),
        rows_out=len(cleaned),
        features_in=len(features),
        features_out=len(kept),
        duplicate_rows_dropped=duplicates,
        dropped_high_missing=high_missing,
        dropped_constant=constant,
        remaining_missing_ratio=round(float(cleaned[kept].isna().mean().mean()), 6)
        if kept else 0.0,
        decisions=[
            "Dropped exact duplicate runs (same features and timestamp).",
            "Sorted runs by timestamp for time-aware splits.",
            "Mapped labels -1 -> 0 (pass) and 1 -> 1 (fail).",
            *column_decisions,
            "Kept remaining missing values; imputation is fitted on the training split "
            "inside the model pipeline.",
        ],
    )
    return cleaned, report


def profile(frame: pd.DataFrame, label_column: str = "label") -> dict:
    """Small descriptive profile used by the app and the Data Analyst crew."""
    features = feature_columns(frame)
    labels = frame[label_column].value_counts().sort_index()
    return {
        "rows": len(frame),
        "features": len(features),
        "label_counts": {str(k): int(v) for k, v in labels.items()},
        "fail_rate": round(float((frame[label_column] == 1).mean()), 6),
        "time_range": [str(frame["timestamp"].min()), str(frame["timestamp"].max())],
        "missing_cells_ratio": round(float(frame[features].isna().mean().mean()), 6)
        if features else 0.0,
        "features_with_missing": int(frame[features].isna().any().sum()),
    }
