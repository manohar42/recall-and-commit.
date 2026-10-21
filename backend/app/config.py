"""Central settings. Every path and AI option is read from one place (environment or .env)."""
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'recall_commit.db').as_posix()}"
    sample_data_path: Path = BACKEND_DIR / "sample_data" / "conversations.json"
    auto_migrate: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    google_api_key: str = Field(default="", validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"))
    gemini_model: str = "gemini-3.8-flash"
    ai_enabled: bool = True
    ai_timeout_seconds: float = 45.0
    ai_max_retries: int = 2
    ai_temperature: float = 0.1
    analyze_batch_size: int = Field(default=10, ge=1, le=50)

    @property
    def ai_configured(self) -> bool:
        key = (self.google_api_key or "").strip()
        return bool(self.ai_enabled and key and not key.startswith("your_"))

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
