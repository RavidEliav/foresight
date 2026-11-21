from pathlib import Path

import pytest

from foresight.llm import LLMConfigurationError, get_llm
from foresight.settings import PROJECT_ROOT, load_settings


def test_defaults_come_from_yaml():
    settings = load_settings()
    assert settings.seed == 42
    assert settings.llm.temperature == 0
    assert settings.environment == "local"


def test_environment_overrides(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gpt-test")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "dev")
    monkeypatch.setenv("MOCK_LLM", "false")
    settings = load_settings()
    assert settings.llm.model == "gpt-test"
    assert settings.environment == "dev"
    assert settings.mock_llm is False


def test_sign_in_settings_come_from_the_environment_and_never_print(monkeypatch):
    settings = load_settings()
    assert not settings.auth.google and settings.auth.public_url == "http://localhost:8501"
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("AUTH_COOKIE_SECRET", "cookie-secret")
    monkeypatch.setenv("FORESIGHT_DEVELOPERS", " Ada@Example.com, bob@example.com ")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "foresight-app-dev.up.railway.app")
    settings = load_settings()
    assert settings.auth.google
    assert settings.auth.developers == ["ada@example.com", "bob@example.com"]
    assert settings.auth.public_url == "https://foresight-app-dev.up.railway.app"
    dumped = settings.model_dump_json()  # cache keys and logs never carry the secrets
    assert "google-secret" not in dumped and "cookie-secret" not in dumped


def test_resolve_relative_and_absolute(tmp_path):
    settings = load_settings()
    assert settings.resolve(Path("runs")) == PROJECT_ROOT / "runs"
    assert settings.resolve(tmp_path) == tmp_path


def test_llm_is_none_in_mock_mode():
    assert get_llm(load_settings()) is None


def test_llm_requires_api_key_when_not_mocked(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "false")
    with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY"):
        get_llm(load_settings())
