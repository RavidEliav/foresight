import numpy as np
import pytest

from foresight.data.cleaning import clean
from foresight.data.secom import checksums, load_raw
from foresight.validation.contract import (
    DatasetContract,
    ValidationSummary,
    build_contract,
    validate_clean,
    validate_raw,
)
from foresight.validation.gates import GateStatus


@pytest.fixture
def dataset(tmp_path, secom_factory):
    raw_dir = secom_factory(tmp_path / "raw")
    raw = load_raw(raw_dir)
    cleaned, report = clean(raw)
    contract = build_contract(cleaned, report, checksums(raw_dir), min_rows=100,
                              max_missing_ratio=0.5)
    return raw, cleaned, contract, checksums(raw_dir)


def statuses(checks):
    return {c.name: c.status for c in checks}


def test_clean_data_matches_its_own_contract(dataset):
    _, cleaned, contract, sums = dataset
    summary = ValidationSummary.from_checks(validate_clean(cleaned, contract, sums))
    assert summary.status == GateStatus.PASS
    assert summary.counts["ERROR"] == summary.counts["WARNING"] == 0


def test_contract_records_schema_and_dropped_columns(dataset):
    _, cleaned, contract, _ = dataset
    assert contract.features.required == [c for c in cleaned.columns if c.startswith("f_")]
    assert contract.dropped_columns["constant"][0] == "f_000"
    assert contract.target.mapping == {"-1": 0, "1": 1}
    assert set(contract.features.ranges) == set(contract.features.required)


def test_contract_save_and_load_round_trip(dataset, tmp_path):
    contract = dataset[2]
    path = contract.save(tmp_path / "c" / "contract.json")
    assert DatasetContract.load(path) == contract


@pytest.mark.parametrize(
    ("mutate", "check", "expected"),
    [
        (lambda df: df.drop(columns=["f_020"]), "required_columns", GateStatus.ERROR),
        (lambda df: df.assign(label=df["label"].replace({1: 2})), "label_values",
         GateStatus.ERROR),
        (lambda df: df.assign(f_100=df["f_100"].astype(str)), "feature_dtypes", GateStatus.ERROR),
        (lambda df: df.assign(run_id=0), "unique_ids", GateStatus.ERROR),
        (lambda df: df.assign(timestamp=None), "timestamps", GateStatus.ERROR),
        (lambda df: df.head(50), "row_count", GateStatus.ERROR),
        (lambda df: df.assign(f_999=1.0), "unexpected_columns", GateStatus.WARNING),
        (lambda df: df.assign(f_020=df["f_020"] * 100), "value_ranges", GateStatus.WARNING),
        (lambda df: df.assign(f_030=np.nan), "feature_missing", GateStatus.WARNING),
        (lambda df: df.assign(label=0), "fail_rate", GateStatus.WARNING),
    ],
)
def test_contract_violations_are_reported(dataset, mutate, check, expected):
    _, cleaned, contract, _ = dataset
    result = statuses(validate_clean(mutate(cleaned.copy()), contract))
    assert result[check] == expected


def test_changed_raw_files_give_checksum_warning(dataset):
    _, cleaned, contract, sums = dataset
    changed = {**sums, "secom.data": "0" * 64}
    assert statuses(validate_clean(cleaned, contract, changed))["data_checksums"] == \
        GateStatus.WARNING


@pytest.mark.parametrize(
    ("mutate", "check"),
    [
        (lambda df: df.drop(columns=["f_589"]), "raw_feature_count"),
        (lambda df: df.assign(label_raw=df["label_raw"].replace({1: 2})), "raw_label_values"),
        (lambda df: df.assign(timestamp=None), "raw_timestamps"),
        (lambda df: df.head(10), "raw_row_count"),
    ],
)
def test_raw_problems_are_errors(dataset, mutate, check):
    raw = dataset[0]
    assert statuses(validate_raw(mutate(raw.copy()), min_rows=100))[check] == GateStatus.ERROR


def test_summary_status_is_worst_check(dataset):
    _, cleaned, contract, _ = dataset
    checks = validate_clean(cleaned.assign(f_999=1.0), contract)
    assert ValidationSummary.from_checks(checks).status == GateStatus.WARNING
    checks = validate_clean(cleaned.drop(columns=["f_020"]), contract)
    assert ValidationSummary.from_checks(checks).status == GateStatus.ERROR
