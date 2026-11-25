"""Ingest stage: load SECOM, validate raw data, clean, apply the Data Contract.

Writes to the run folder: clean_data.csv, cleaning_report.json, data_profile.json,
dataset_contract.json and validation_summary.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from foresight.data.cleaning import CleaningConfig, clean, profile
from foresight.data.scenarios import DATA_FILE as SCENARIO_DATA_FILE
from foresight.data.scenarios import SCENARIO_FILE, Scenario, check_test_period, generate
from foresight.data.secom import (
    SecomDataError,
    ensure_secom,
    load_csv,
    load_raw,
    sha256,
    to_upload_csv,
)
from foresight.settings import Settings
from foresight.utils.logging import get_logger
from foresight.validation.contract import (
    Check,
    DatasetContract,
    ValidationSummary,
    build_contract,
    validate_clean,
    validate_raw,
)
from foresight.validation.gates import GateStatus

log = get_logger("ingest")


class IngestResult(BaseModel):
    validation: ValidationSummary
    artifacts: dict[str, str] = Field(default_factory=dict)
    checksums: dict[str, str] = Field(default_factory=dict)


def _write_json(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(path)


def run_ingest(settings: Settings, run_dir: Path, dataset: Path | None = None,
               scenario: Scenario | None = None) -> IngestResult:
    """Ingest the built-in SECOM files, ``dataset`` (an uploaded CSV) when given, or a
    synthetic ``scenario`` built from SECOM (training period only, Phase 8.3)."""
    raw_dir = settings.resolve(settings.paths.data_raw_dir)
    artifacts: dict[str, str] = {}
    contract_path = settings.resolve(settings.paths.contract_path)
    contract = DatasetContract.load(contract_path) if contract_path.exists() else None
    config = CleaningConfig(max_missing_ratio=settings.data.max_missing_ratio)
    if contract is not None:
        config.contract_features = contract.features.required
        config.contract_dropped = contract.dropped_columns
    original = None
    try:
        if dataset is not None:
            checksums = {dataset.name: sha256(dataset)}
            raw = load_csv(dataset)
        elif scenario is not None:
            ensure_secom(raw_dir)
            original = load_raw(raw_dir)
            raw, artifacts, checksums = _scenario_data(original, scenario, config, settings,
                                                       run_dir)
        else:
            checksums = ensure_secom(raw_dir)
            raw = load_raw(raw_dir)
    except (SecomDataError, OSError) as exc:
        checks = [Check(name="load_raw", status=GateStatus.ERROR, message=str(exc))]
        return _finish(run_dir, checks, artifacts, {})

    checks = validate_raw(raw, settings.data.min_rows)
    if original is not None:
        checks.append(check_test_period(original, raw, config, settings.analytics.test_fraction))
    if any(c.status == GateStatus.ERROR for c in checks):
        return _finish(run_dir, checks, artifacts, checksums)

    cleaned, report = clean(raw, config)
    clean_path = run_dir / "clean_data.csv"
    cleaned.to_csv(clean_path, index=False, date_format="%Y-%m-%dT%H:%M:%S")
    artifacts["clean_data"] = str(clean_path)
    artifacts["cleaning_report"] = _write_json(run_dir / "cleaning_report.json",
                                               report.model_dump())
    artifacts["data_profile"] = _write_json(run_dir / "data_profile.json", profile(cleaned))

    if contract is None:
        contract = build_contract(cleaned, report, checksums, settings.data.min_rows,
                                  settings.data.max_missing_ratio,
                                  settings.data.expected_fail_rate)
        checks.append(Check(
            name="contract_bootstrap", status=GateStatus.WARNING,
            message=f"no contract at {contract_path}; built one from this run's data "
                    "(run scripts/build_contract.py to commit a reference contract)"))
    artifacts["dataset_contract"] = str(contract.save(run_dir / "dataset_contract.json"))

    checks += validate_clean(cleaned, contract, checksums)
    log.info("cleaned %d rows x %d features", report.rows_out, report.features_out)
    return _finish(run_dir, checks, artifacts, checksums)


def _scenario_data(original, scenario: Scenario, config: CleaningConfig, settings: Settings,
                   run_dir: Path) -> tuple:
    """Generate the scenario's data from SECOM and save it apart from the original files:
    scenario_data.csv (upload format) and scenario.json (recipe and ground truth)."""
    raw, resolved, truth = generate(original, scenario, config, settings.analytics.test_fraction)
    data_path = run_dir / SCENARIO_DATA_FILE
    data_path.write_bytes(to_upload_csv(raw))
    recipe = {"scenario": resolved.model_dump(), "label": resolved.label(), "ground_truth": truth}
    artifacts = {"scenario": _write_json(run_dir / SCENARIO_FILE, recipe),
                 "scenario_data": str(data_path)}
    log.info("scenario %s: %s", resolved.kind, resolved.label())
    return raw, artifacts, {SCENARIO_DATA_FILE: sha256(data_path)}


def _finish(run_dir: Path, checks: list[Check], artifacts: dict[str, str],
            checksums: dict[str, str]) -> IngestResult:
    summary = ValidationSummary.from_checks(checks)
    artifacts["validation_summary"] = _write_json(run_dir / "validation_summary.json",
                                                  summary.model_dump(mode="json"))
    log.info("validation %s %s", summary.status.value, summary.counts)
    return IngestResult(validation=summary, artifacts=artifacts, checksums=checksums)
