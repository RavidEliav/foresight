"""Project settings: config/settings.yaml with environment-variable overrides."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "settings.yaml"


class LLMSettings(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    crew_revisions: int = 1


class PathSettings(BaseModel):
    runs_dir: Path = Path("runs")
    logs_dir: Path = Path("logs")
    reference_run_dir: Path = Path("artifacts/reference")
    data_raw_dir: Path = Path("data/raw")
    contract_path: Path = Path("config/dataset_contract.json")
    knowledge_dir: Path = Path("knowledge")
    models_dir: Path = Path("runs/.models")  # embedding model + knowledge index cache (volume)


class RagSettings(BaseModel):
    embedding_model: str = "all-MiniLM-L6-v2"  # local ONNX model, 384 dimensions, no API cost
    chunk_chars: int = 800
    overlap_chars: int = 120
    top_k: int = 4
    min_similarity: float = 0.25     # below this the chat refuses without calling the LLM
    knowledge_k: int = 3
    all_runs_k: int = 6              # excerpts for a question about all runs (Phase 8.2)


class DataSettings(BaseModel):
    max_missing_ratio: float = 0.5
    min_rows: int = 100
    expected_fail_rate: tuple[float, float] = (0.02, 0.2)


class AnalyticsSettings(BaseModel):
    test_fraction: float = 0.25
    cv_folds: int = 5
    corr_threshold: float = 0.98
    select_k: int = 40
    rf_trees: int = 300
    bootstrap_samples: int = 1000
    permutation_top_n: int = 20
    permutation_repeats: int = 5
    min_fails_train: int = 10
    min_fails_test: int = 5
    alarm_budget: float = 0.10
    anomaly_quantile: float = 0.95
    z_limit: float = 3.0
    top_features: int = 15
    similar_components: int = 30     # PCA run embedding (fitted on training runs)
    similar_k: int = 5               # nearest past runs per query run


class AppSettings(BaseModel):
    run_timeout_s: int = 1200        # timeout guard for one pipeline run
    max_runs_per_hour: int = 6       # cost and abuse control (one run at a time as well)
    heartbeat_s: int = 15            # a run without a heartbeat for 90 s counts as interrupted
    keep_runs: int = 20              # older finished runs are deleted (the volume is 500 MB)


class AuthSettings(BaseModel):
    """Google sign-in and access requests (Phase 8.6). Secrets come from the environment only."""
    idle_minutes: int = 60           # signed out after this long without activity
    request_link_days: int = 7       # an emailed approve/deny link works this long
    email_from: str = "Foresight <onboarding@resend.dev>"
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    cookie_secret: SecretStr = SecretStr("")  # signs the sign-in cookie and the emailed links
    resend_api_key: SecretStr = SecretStr("")
    developers: list[str] = []       # always approved, with the developer view
    public_url: str = "http://localhost:8501"

    @property
    def google(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret.get_secret_value()
                    and self.cookie_secret.get_secret_value())


class Settings(BaseModel):
    seed: int = 42
    llm: LLMSettings = LLMSettings()
    paths: PathSettings = PathSettings()
    data: DataSettings = DataSettings()
    analytics: AnalyticsSettings = AnalyticsSettings()
    app: AppSettings = AppSettings()
    rag: RagSettings = RagSettings()
    auth: AuthSettings = AuthSettings()
    mock_llm: bool = False
    environment: str = "local"
    database_url: str = ""  # Supabase Postgres (Session pooler); empty = run folders only

    def resolve(self, path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path


def _as_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_settings(config_path: Path | None = None) -> Settings:
    if not _as_bool(os.getenv("FORESIGHT_SKIP_DOTENV")):
        load_dotenv(PROJECT_ROOT / ".env", override=False)
    path = config_path or Path(os.getenv("FORESIGHT_CONFIG", DEFAULT_CONFIG))
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    settings = Settings(**(data or {}))

    if model := os.getenv("LLM_MODEL"):
        settings.llm.model = model
    path_overrides = {
        "FORESIGHT_RUNS_DIR": "runs_dir",
        "FORESIGHT_LOGS_DIR": "logs_dir",
        "FORESIGHT_DATA_DIR": "data_raw_dir",
        "FORESIGHT_CONTRACT_PATH": "contract_path",
        "FORESIGHT_MODELS_DIR": "models_dir",
    }
    for env_name, field in path_overrides.items():
        if value := os.getenv(env_name):
            setattr(settings.paths, field, Path(value))
    settings.mock_llm = _as_bool(os.getenv("MOCK_LLM"))
    settings.environment = os.getenv("RAILWAY_ENVIRONMENT_NAME", "local")
    auth = settings.auth
    auth.google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    auth.google_client_secret = SecretStr(os.getenv("GOOGLE_CLIENT_SECRET", "").strip())
    auth.cookie_secret = SecretStr(os.getenv("AUTH_COOKIE_SECRET", "").strip())
    auth.resend_api_key = SecretStr(os.getenv("RESEND_API_KEY", "").strip())
    if developers := os.getenv("FORESIGHT_DEVELOPERS"):
        auth.developers = [e.strip().lower() for e in developers.split(",") if e.strip()]
    if url := os.getenv("FORESIGHT_PUBLIC_URL"):
        auth.public_url = url.rstrip("/")
    elif domain := os.getenv("RAILWAY_PUBLIC_DOMAIN"):
        auth.public_url = f"https://{domain}"
    # Railway sets SUPABASE_DB_URL per environment (ADR-026); empty = the run folders only
    settings.database_url = os.getenv("SUPABASE_DB_URL", "")
    return settings
