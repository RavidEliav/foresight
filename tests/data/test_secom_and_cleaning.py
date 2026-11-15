import pandas as pd
import pytest

from foresight.data.cleaning import clean, profile
from foresight.data.secom import (
    LABELS_FILE,
    SecomDataError,
    checksums,
    ensure_secom,
    load_raw,
)


def test_load_raw_has_ids_timestamps_and_590_features(tmp_path, secom_factory):
    raw = load_raw(secom_factory(tmp_path))
    assert raw.shape == (150, 3 + 590)
    assert list(raw.columns[:4]) == ["run_id", "timestamp", "label_raw", "f_000"]
    assert set(raw["label_raw"]) == {-1, 1}
    assert raw["timestamp"].notna().all()


def test_label_and_feature_row_mismatch_is_rejected(tmp_path, secom_factory):
    raw_dir = secom_factory(tmp_path)
    labels = raw_dir / LABELS_FILE
    labels.write_text("\n".join(labels.read_text().splitlines()[:-5]) + "\n")
    with pytest.raises(SecomDataError, match="row mismatch"):
        load_raw(raw_dir)


def test_missing_files_are_not_downloaded_when_offline(tmp_path):
    with pytest.raises(SecomDataError, match="downloads are disabled"):
        ensure_secom(tmp_path / "empty")


def test_existing_files_return_checksums_without_download(tmp_path, secom_factory):
    raw_dir = secom_factory(tmp_path)
    assert ensure_secom(raw_dir) == checksums(raw_dir)


def test_cleaning_drops_constant_and_sparse_features_and_keeps_nan(tmp_path, secom_factory):
    raw = load_raw(secom_factory(tmp_path))
    cleaned, report = clean(raw)

    assert report.dropped_constant == [f"f_{i:03d}" for i in range(10)]
    assert report.dropped_high_missing == [f"f_{i:03d}" for i in range(10, 15)]
    assert report.features_out == 590 - 15
    assert list(cleaned.columns[:3]) == ["run_id", "timestamp", "label"]
    assert set(cleaned["label"]) == {0, 1}
    assert cleaned["timestamp"].is_monotonic_increasing
    assert cleaned.drop(columns=["timestamp"]).isna().any().any()  # no imputation
    assert 0 < report.remaining_missing_ratio < 0.05


def test_cleaning_drops_exact_duplicate_runs(tmp_path, secom_factory):
    raw = load_raw(secom_factory(tmp_path))
    duplicated = pd.concat([raw, raw.iloc[[3]].assign(run_id=999)], ignore_index=True)
    _, report = clean(duplicated)
    assert report.duplicate_rows_dropped == 1


def test_profile_reports_imbalance(tmp_path, secom_factory):
    cleaned, _ = clean(load_raw(secom_factory(tmp_path)))
    stats = profile(cleaned)
    assert stats["rows"] == 150
    assert stats["label_counts"] == {"0": 135, "1": 15}
    assert stats["fail_rate"] == pytest.approx(0.1)
