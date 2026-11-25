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


def test_a_byte_order_mark_in_the_environment_is_dropped(monkeypatch):
    """Windows PowerShell can prepend U+FEFF when piping a value to a CLI (2026-11-21)."""
    import os

    monkeypatch.setenv("SUPABASE_DB_URL", "﻿postgresql://u:p@db.example:5432/postgres ")
    monkeypatch.setenv("OPENAI_API_KEY", "﻿sk-test")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "﻿id.apps.googleusercontent.com")
    settings = load_settings()
    assert settings.database_url == "postgresql://u:p@db.example:5432/postgres"
    assert settings.auth.google_client_id == "id.apps.googleusercontent.com"
    assert os.environ["OPENAI_API_KEY"] == "sk-test"  # read by the OpenAI SDK itself


def test_passwords_in_urls_are_redacted():
    from foresight.utils.logging import redact

    message = ('missing "=" after "﻿postgresql://postgres.ref:s3cr3t!@pooler.example:5432'
               '/postgres" in connection info string')
    assert "s3cr3t" not in redact(message)
    assert "postgresql://postgres.ref:***@pooler.example:5432" in redact(message)
    assert redact("no url here") == "no url here"
    assert redact("https://example.com/path") == "https://example.com/path"


def test_a_failing_migration_never_prints_the_database_password(monkeypatch, capsys):
    from foresight.registry import migrate

    monkeypatch.setenv("SUPABASE_DB_URL", "not-a-url postgresql://u:s3cr3t@host:5432/db")
    assert migrate.main() == 1
    output = capsys.readouterr().out
    assert "migration failed" in output and "s3cr3t" not in output


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
