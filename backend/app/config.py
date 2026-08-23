import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))
ENV_FILE = ROOT_DIR / ".env" if (ROOT_DIR / ".env").exists() else BACKEND_DIR / ".env"

# Always load root .env into process env so SMTP works even if Settings cache was warm
load_dotenv(ENV_FILE, override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = f"sqlite:///{ROOT_DIR / 'edupath.db'}"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""
    secret_key: str = "dev-secret-change-me"
    demo_mode: bool = False
    discovery_schedule: str = "0 8 * * *"
    upload_dir: str = str(ROOT_DIR / "uploads")
    cors_origins: str = "http://localhost:3000"
    notify_match_threshold: float = 80.0

    ranking_weight_eligibility: float = 0.35
    ranking_weight_career: float = 0.25
    ranking_weight_interest: float = 0.15
    ranking_weight_academic: float = 0.10
    ranking_weight_readiness: float = 0.10
    ranking_weight_deadline: float = 0.05

    access_token_expire_minutes: int = 60 * 24 * 7
    algorithm: str = "HS256"

    # Optional SMTP for login confirmation codes. If unset, codes are returned in API (dev).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "EduPath AI <noreply@edupath.local>"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    resend_api_key: str = ""
    auth_code_ttl_minutes: int = 10

    # Gmail OAuth ("Connect Gmail" — Google login, no app password)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/email/gmail/callback"
    frontend_url: str = "http://localhost:3000"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def gmail_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def ranking_weights(self) -> dict[str, float]:
        return {
            "eligibility": self.ranking_weight_eligibility,
            "career": self.ranking_weight_career,
            "interest": self.ranking_weight_interest,
            "academic": self.ranking_weight_academic,
            "readiness": self.ranking_weight_readiness,
            "deadline": self.ranking_weight_deadline,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
