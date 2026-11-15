"""Build the reference Data Contract (config/dataset_contract.json) from the real SECOM data.

Run once, review the diff, and commit it. Every pipeline run validates its cleaned data
against this committed contract.

Usage: python scripts/build_contract.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from foresight.data.cleaning import CleaningConfig, clean  # noqa: E402
from foresight.data.secom import ensure_secom, load_raw  # noqa: E402
from foresight.settings import load_settings  # noqa: E402
from foresight.validation.contract import build_contract, validate_raw  # noqa: E402
from foresight.validation.gates import GateStatus  # noqa: E402


def main() -> None:
    settings = load_settings()
    raw_dir = settings.resolve(settings.paths.data_raw_dir)
    checksums = ensure_secom(raw_dir)
    raw = load_raw(raw_dir)

    errors = [c for c in validate_raw(raw, settings.data.min_rows) if c.status == GateStatus.ERROR]
    if errors:
        sys.exit("raw data failed validation: " + "; ".join(c.message for c in errors))

    cleaned, report = clean(raw, CleaningConfig(max_missing_ratio=settings.data.max_missing_ratio))
    contract = build_contract(cleaned, report, checksums, settings.data.min_rows,
                              settings.data.max_missing_ratio, settings.data.expected_fail_rate)
    path = contract.save(settings.resolve(settings.paths.contract_path))
    print(f"wrote {path}: {len(contract.features.required)} required features, "
          f"{len(report.dropped_high_missing)} dropped (missing), "
          f"{len(report.dropped_constant)} dropped (constant)")


if __name__ == "__main__":
    main()
