"""Shared fixtures. Must not import the foresight package or pandas at module level: the
deployed tests run with only pytest, pytest-playwright and requests installed."""

import os
from pathlib import Path

import pytest

ENV_VARS = ("LLM_MODEL", "OPENAI_API_KEY", "RUN_PASSCODE", "RAILWAY_ENVIRONMENT_NAME",
            "RAILWAY_GIT_COMMIT_SHA")
# Read before isolated_env removes RUN_PASSCODE: E5/E6 type it into the app under test
E2E_PASSCODE = os.getenv("E2E_PASSCODE") or os.getenv("RUN_PASSCODE")


@pytest.fixture(scope="session", autouse=True)
def no_paid_calls():
    """Session-wide guard (also covers module-scoped fixtures): no LLM calls, no downloads,
    no .env secrets."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("MOCK_LLM", "true")
        patch.setenv("FORESIGHT_SKIP_DOTENV", "true")
        patch.setenv("FORESIGHT_OFFLINE", "true")
        patch.setenv("CREWAI_TRACING_ENABLED", "false")
        patch.delenv("OPENAI_API_KEY", raising=False)
        yield


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """No .env, no LLM, no downloads; runs, logs, data and contract live in a temp folder."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FORESIGHT_SKIP_DOTENV", "true")
    monkeypatch.setenv("FORESIGHT_CONFIG", str(Path(__file__).parent / "fast_settings.yaml"))
    monkeypatch.setenv("FORESIGHT_OFFLINE", "true")
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("FORESIGHT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("FORESIGHT_LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("FORESIGHT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FORESIGHT_CONTRACT_PATH", str(tmp_path / "dataset_contract.json"))
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")
    monkeypatch.setenv("CREWAI_TRACING_ENABLED", "false")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")


def write_synthetic_secom(raw_dir: Path, n_rows: int = 150, fail_rate: float = 0.1,
                          seed: int = 0) -> Path:
    """Write SECOM-format files: 590 features, f_000-f_009 constant, f_010-f_014 70% missing,
    2% missing elsewhere, f_020 shifted for failing runs, hourly timestamps."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    values = rng.normal(100, 10, size=(n_rows, 590))
    values[:, :10] = 1.0
    values[rng.random((n_rows, 590)) < 0.02] = np.nan
    values[:, 10:15][rng.random((n_rows, 5)) < 0.7] = np.nan
    values[:, :10] = 1.0
    labels = np.full(n_rows, -1)
    labels[rng.choice(n_rows, size=round(n_rows * fail_rate), replace=False)] = 1
    values[labels == 1, 20] += 50

    raw_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(values).to_csv(raw_dir / "secom.data", sep=" ", header=False, index=False,
                                na_rep="NaN")
    stamps = pd.date_range("2008-07-19 11:00", periods=n_rows, freq="h")
    lines = [f'{label} "{ts:%d/%m/%Y %H:%M:%S}"' for label, ts in zip(labels, stamps, strict=True)]
    (raw_dir / "secom_labels.data").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return raw_dir


@pytest.fixture
def secom_factory():
    return write_synthetic_secom


@pytest.fixture
def secom_env(tmp_path):
    """Synthetic SECOM files in the data dir and a reference contract built from them."""
    from foresight.data.cleaning import CleaningConfig, clean
    from foresight.data.secom import checksums, load_raw
    from foresight.settings import load_settings
    from foresight.validation.contract import build_contract

    settings = load_settings()
    raw_dir = write_synthetic_secom(settings.paths.data_raw_dir)
    cleaned, report = clean(load_raw(raw_dir), CleaningConfig())
    contract = build_contract(cleaned, report, checksums(raw_dir), settings.data.min_rows,
                              settings.data.max_missing_ratio)
    contract.save(settings.paths.contract_path)
    return settings


@pytest.fixture
def analytics_run(secom_env, tmp_path):
    """A run folder with clean_data.csv from the synthetic data, ready for analytics stages."""
    from foresight.data.ingest import run_ingest

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    run_ingest(secom_env, run_dir)
    return secom_env, run_dir


@pytest.fixture
def gate_checks():
    """The gate registry, restored after the test so replaced checks don't leak."""
    from foresight.validation import gates

    original = dict(gates.GATE_CHECKS)
    yield gates.GATE_CHECKS
    gates.GATE_CHECKS.clear()
    gates.GATE_CHECKS.update(original)


@pytest.fixture(scope="session")
def app_url() -> str:
    """Running app under test: local in CI, or the Railway dev/main URL."""
    return os.getenv("BASE_URL", "http://localhost:8501").rstrip("/")


@pytest.fixture(scope="session")
def expected_env() -> str | None:
    """Environment the deployed app should report (dev/main); None skips the check."""
    return os.getenv("EXPECTED_ENV") or None


@pytest.fixture(scope="session")
def e2e_passcode() -> str:
    """Passcode of the app under test (E5/E6 start runs, so only against a local mock app)."""
    if not E2E_PASSCODE:
        pytest.skip("set RUN_PASSCODE (or E2E_PASSCODE) to the passcode of the app under test")
    return E2E_PASSCODE
