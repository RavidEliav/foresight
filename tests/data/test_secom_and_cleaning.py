import pandas as pd
import pytest

from foresight.data.cleaning import CleaningConfig, clean, profile
from foresight.data.secom import (
    LABELS_FILE,
    SecomDataError,
    checksums,
    ensure_secom,
    load_csv,
    load_raw,
    to_upload_csv,
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


def test_uploaded_csv_loads_like_the_secom_files(tmp_path, secom_factory):
    raw = load_raw(secom_factory(tmp_path))
    path = tmp_path / "upload.csv"
    path.write_bytes(to_upload_csv(raw))
    uploaded = load_csv(path)
    pd.testing.assert_frame_equal(uploaded, raw, check_dtype=False)


def test_uploaded_csv_accepts_iso_timestamps_and_any_sensor_names(tmp_path):
    path = tmp_path / "upload.csv"
    path.write_text("timestamp,label,temp,pressure\n2008-07-19T11:55:00,-1,1.5,2\n"
                    "2008-07-19T12:55:00,1,1.7,\n")
    uploaded = load_csv(path)
    assert list(uploaded.columns) == ["run_id", "timestamp", "label_raw", "f_000", "f_001"]
    assert uploaded["timestamp"].notna().all() and list(uploaded["label_raw"]) == [-1, 1]


def test_uploaded_csv_accepts_time_zones_fractions_and_mixed_formats(tmp_path):
    path = tmp_path / "upload.csv"
    path.write_text("timestamp,label,f_000\n2008-07-19T11:55:00Z,-1,1\n"
                    "2008-07-19T14:55:00.123+02:00,1,2\n"
                    "19/07/2008 13:00:00,-1,3\nnot a date,-1,4\n")
    stamps = load_csv(path)["timestamp"]
    assert [str(t) for t in stamps[:3]] == ["2008-07-19 11:55:00", "2008-07-19 12:55:00.123000",
                                            "2008-07-19 13:00:00"]
    assert stamps.isna().tolist() == [False, False, False, True]  # left to the raw checks


def test_uploaded_csv_without_a_label_column_is_rejected(tmp_path):
    path = tmp_path / "upload.csv"
    path.write_text("timestamp,f_000\n2008-07-19T11:55:00,1.5\n")
    with pytest.raises(SecomDataError, match="no label column"):
        load_csv(path)


def test_cleaning_with_a_contract_keeps_its_features_on_a_subset(tmp_path, secom_factory):
    raw = load_raw(secom_factory(tmp_path))
    _, reference = clean(raw)
    kept = [f"f_{i:03d}" for i in range(15, 590)]
    subset = raw.iloc[:40].copy()
    subset["f_300"] = 7.0  # constant in this subset, but part of the contract
    cleaned, report = clean(subset, CleaningConfig(
        contract_features=kept,
        contract_dropped={"high_missing": reference.dropped_high_missing,
                          "constant": reference.dropped_constant}))
    assert [c for c in cleaned.columns if c.startswith("f_")] == kept
    assert report.dropped_constant == reference.dropped_constant
    assert report.decisions[3] == "Applied the Data Contract: kept its 575 features."
