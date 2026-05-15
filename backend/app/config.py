"""Application settings loaded from environment variables / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    secret_key: str
    environment: str = "development"
    debug: bool = False
    allowed_origins: list[str] = ["http://localhost:3000"]

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str
    database_pool_size: int = 20

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str

    # ── Auth ──────────────────────────────────────────────────────────────────
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    credential_encryption_key: str  # 32-byte URL-safe base64 for Fernet

    # ── Initial admin ─────────────────────────────────────────────────────────
    initial_admin_email: str = "admin@example.com"
    initial_admin_password: str

    # ── Email (SMTP) ──────────────────────────────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.com"

    # ── Security ──────────────────────────────────────────────────────────────
    max_pii_risk_score: float = 0.8
    max_injection_risk_score: float = 0.7
    audit_retention_days: int = 90

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
