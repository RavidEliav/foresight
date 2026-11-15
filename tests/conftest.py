"""Shared fixtures. Must not import the foresight package at module level: the deployed
tests run with only the test tools installed."""

import os

import pytest

ENV_VARS = ("LLM_MODEL", "OPENAI_API_KEY", "RUN_PASSCODE", "RAILWAY_ENVIRONMENT_NAME",
            "RAILWAY_GIT_COMMIT_SHA")


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """No .env, no LLM, and run outputs in a temp folder for every test."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FORESIGHT_SKIP_DOTENV", "true")
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("FORESIGHT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")


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
