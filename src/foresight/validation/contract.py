"""Data Contract for the cleaned SECOM dataset, plus raw and clean validation checks.

ERROR checks stop the Flow; WARNING checks let it continue but are reported.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from pandas.api import types as ptypes
from pydantic import BaseModel, Field

from foresight.data.cleaning import META_COLUMNS, CleaningReport, feature_columns
from foresight.data.secom import N_FEATURES, RAW_LABELS, SOURCE_PAGE, SOURCE_URL
from foresight.validation.gates import GateStatus

CONTRACT_VERSION = "1.0"


class Check(BaseModel):
    name: str
    status: GateStatus
    message: str


class ValidationSummary(BaseModel):
    status: GateStatus
    counts: dict[str, int]
    checks: list[Check]

    @classmethod
    def from_checks(cls, checks: list[Check]) -> ValidationSummary:
        counts = {s.value: sum(c.status == s for c in checks) for s in GateStatus}
        if counts["ERROR"]:
            status = GateStatus.ERROR
        elif counts["WARNING"]:
            status = GateStatus.WARNING
        else:
            status = GateStatus.PASS
        return cls(status=status, counts=counts, checks=checks)


class Target(BaseModel):
    name: str = "label"
    allowed_values: list[int] = [0, 1]
    mapping: dict[str, int] = {"-1": 0, "1": 1}
    positive_class: str = "fail (1)"
    expected_fail_rate: tuple[float, float] = (0.02, 0.2)


class Features(BaseModel):
    required: list[str]
    dtype: str = "float"
    max_missing_ratio: float
    ranges: dict[str, tuple[float, float]]


class DatasetContract(BaseModel):
    contract_version: str = CONTRACT_VERSION
    dataset: str = "SECOM"
    source: dict[str, object]
    min_rows: int
    id_column: str = "run_id"
    timestamp_column: str = "timestamp"
    target: Target = Field(default_factory=Target)
    features: Features
    dropped_columns: dict[str, list[str]]
    assumptions: list[str]
    constraints: list[str]

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.model_dump(mode="json"), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> DatasetContract:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def build_contract(
    cleaned: pd.DataFrame,
    report: CleaningReport,
    checksums: dict[str, str],
    min_rows: int,
    max_missing_ratio: float,
    expected_fail_rate: tuple[float, float] = (0.02, 0.2),
) -> DatasetContract:
    features = feature_columns(cleaned)
    stats = cleaned[features].agg(["min", "max"])
    return DatasetContract(
        source={"url": SOURCE_URL, "page": SOURCE_PAGE, "sha256": checksums},
        min_rows=min_rows,
        target=Target(expected_fail_rate=expected_fail_rate),
        features=Features(
            required=features,
            max_missing_ratio=max_missing_ratio,
            ranges={c: (float(stats.at["min", c]), float(stats.at["max", c])) for c in features},
        ),
        dropped_columns={
            "high_missing": report.dropped_high_missing,
            "constant": report.dropped_constant,
        },
        assumptions=[
            "Feature names are anonymized (f_000..f_589); they have no physical meaning.",
            "Missing values are kept in clean_data.csv; imputation is fitted on the training "
            "split inside the model pipeline.",
            "Value ranges are the observed min/max of the reference data; values outside them "
            "are reported as possible drift, not as errors.",
        ],
        constraints=[
            "run_id is unique.",
            "timestamp is never null and runs are sorted by time.",
            "label is 0 (pass) or 1 (fail); fails are rare (heavily imbalanced).",
        ],
    )


def _check(name: str, ok: bool, message_ok: str, message_bad: str,
           severity: GateStatus = GateStatus.ERROR) -> Check:
    return Check(name=name, status=GateStatus.PASS if ok else severity,
                 message=message_ok if ok else message_bad)


def _preview(items: list[str], limit: int = 5) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" (+{len(items) - limit} more)" if len(items) > limit else "")


def _plain(value: object) -> object:
    """numpy scalar -> plain Python value (2.0 -> 2) so messages read naturally."""
    value = value.item() if hasattr(value, "item") else value
    return int(value) if isinstance(value, float) and value.is_integer() else value


def validate_raw(raw: pd.DataFrame, min_rows: int) -> list[Check]:
    """Checks on the raw files before any cleaning."""
    features = feature_columns(raw)
    non_numeric = [c for c in features if not ptypes.is_numeric_dtype(raw[c])]
    bad_labels = sorted((_plain(v) for v in set(raw["label_raw"].dropna().unique())
                         - set(RAW_LABELS)), key=str)
    null_labels = int(raw["label_raw"].isna().sum())
    bad_timestamps = int(raw["timestamp"].isna().sum())
    return [
        _check("raw_feature_count", len(features) == N_FEATURES,
               f"{len(features)} feature columns",
               f"expected {N_FEATURES} feature columns, found {len(features)}"),
        _check("raw_feature_dtypes", not non_numeric, "all features are numeric",
               f"non-numeric feature columns: {_preview(non_numeric)}"),
        _check("raw_label_values", not bad_labels and not null_labels,
               "labels are -1 (pass) or 1 (fail)",
               f"unexpected label values {bad_labels}, missing or non-numeric labels: "
               f"{null_labels}"),
        _check("raw_timestamps", bad_timestamps == 0, "all timestamps parsed",
               f"{bad_timestamps} timestamps are missing or unparseable"),
        _check("raw_row_count", len(raw) >= min_rows, f"{len(raw)} rows",
               f"only {len(raw)} rows, contract needs at least {min_rows}"),
    ]


def validate_clean(
    cleaned: pd.DataFrame, contract: DatasetContract, checksums: dict[str, str] | None = None
) -> list[Check]:
    """Checks that the cleaned dataset matches the Data Contract."""
    required = META_COLUMNS + contract.features.required
    missing_cols = [c for c in required if c not in cleaned.columns]
    present = [c for c in contract.features.required if c in cleaned.columns]
    extra = [c for c in feature_columns(cleaned) if c not in contract.features.required]
    checks = [
        _check("required_columns", not missing_cols,
               f"all {len(required)} required columns present",
               f"missing required columns: {_preview(missing_cols)}"),
        _check("unexpected_columns", not extra, "no unexpected feature columns",
               f"feature columns not in the contract: {_preview(extra)}", GateStatus.WARNING),
    ]
    non_numeric = [c for c in present if not ptypes.is_numeric_dtype(cleaned[c])]
    checks.append(_check("feature_dtypes", not non_numeric, "all contract features are numeric",
                         f"non-numeric features: {_preview(non_numeric)}"))

    target = contract.target.name
    if target in cleaned.columns:
        values = set(cleaned[target].dropna().unique())
        bad = sorted(values - set(contract.target.allowed_values))
        nulls = int(cleaned[target].isna().sum())
        checks.append(_check("label_values", not bad and not nulls,
                             f"labels within {contract.target.allowed_values}",
                             f"unexpected label values {bad}, missing labels: {nulls}"))
        fail_rate = float((cleaned[target] == 1).mean())
        low, high = contract.target.expected_fail_rate
        checks.append(_check("fail_rate", low <= fail_rate <= high,
                             f"fail rate {fail_rate:.1%} within expected {low:.0%}-{high:.0%}",
                             f"fail rate {fail_rate:.1%} outside expected {low:.0%}-{high:.0%}",
                             GateStatus.WARNING))

    if contract.timestamp_column in cleaned.columns:
        nulls = int(cleaned[contract.timestamp_column].isna().sum())
        checks.append(_check("timestamps", nulls == 0, "no missing timestamps",
                             f"{nulls} missing timestamps"))
    if contract.id_column in cleaned.columns:
        dupes = int(cleaned[contract.id_column].duplicated().sum())
        checks.append(_check("unique_ids", dupes == 0, "run_id values are unique",
                             f"{dupes} duplicate run_id values"))
    checks.append(_check("row_count", len(cleaned) >= contract.min_rows,
                         f"{len(cleaned)} rows (minimum {contract.min_rows})",
                         f"only {len(cleaned)} rows, contract needs {contract.min_rows}"))

    numeric = [c for c in present if c not in non_numeric]
    if numeric:
        missing_ratio = cleaned[numeric].isna().mean()
        too_sparse = sorted(missing_ratio[missing_ratio > contract.features.max_missing_ratio]
                            .index)
        checks.append(_check(
            "feature_missing", not too_sparse,
            f"no feature above {contract.features.max_missing_ratio:.0%} missing",
            f"{len(too_sparse)} features above {contract.features.max_missing_ratio:.0%} "
            f"missing: {_preview(too_sparse)}", GateStatus.WARNING))

        lows = pd.Series({c: contract.features.ranges[c][0] for c in numeric})
        highs = pd.Series({c: contract.features.ranges[c][1] for c in numeric})
        values = cleaned[numeric]
        outside = ((values.lt(lows) | values.gt(highs)).sum())
        drifted = sorted(outside[outside > 0].index)
        checks.append(_check(
            "value_ranges", not drifted, "all values within contract ranges",
            f"{len(drifted)} features have values outside the contract range "
            f"(possible drift): {_preview(drifted)}", GateStatus.WARNING))

    if checksums is not None:
        expected = contract.source.get("sha256", {})
        checks.append(_check(
            "data_checksums", checksums == expected, "raw files match the contract checksums",
            "raw files differ from the files the contract was built from", GateStatus.WARNING))
    return checks
