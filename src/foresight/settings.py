"""Project settings: config/settings.yaml with environment-variable overrides."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "settings.yaml"


class LLMSettings(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0


class PathSettings(BaseModel):
    runs_dir: Path = Path("runs")
    logs_dir: Path = Path("logs")
    reference_run_dir: Path = Path("artifacts/reference")


class Settings(BaseModel):
    seed: int = 42
    llm: LLMSettings = LLMSettings()
    paths: PathSettings = PathSettings()
    mock_llm: bool = False
    run_passcode: str = ""
    environment: str = "local"

    def resolve(self, path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path


def _as_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_settings(config_path: Path | None = None) -> Settings:
    if not _as_bool(os.getenv("FORESIGHT_SKIP_DOTENV")):
        load_dotenv(PROJECT_ROOT / ".env", override=False)
    path = config_path or DEFAULT_CONFIG
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    settings = Settings(**(data or {}))

    if model := os.getenv("LLM_MODEL"):
        settings.llm.model = model
    if runs_dir := os.getenv("FORESIGHT_RUNS_DIR"):
        settings.paths.runs_dir = Path(runs_dir)
    settings.mock_llm = _as_bool(os.getenv("MOCK_LLM"))
    settings.run_passcode = os.getenv("RUN_PASSCODE", "")
    settings.environment = os.getenv("RAILWAY_ENVIRONMENT_NAME", "local")
    return settings
