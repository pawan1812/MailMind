"""MailMind configuration via pydantic-settings."""

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App
    app_name: str = "MailMind OpenEnv"
    app_version: str = "2.0.0"
    debug: bool = False
    log_level: str = "info"

    # Firebase (optional — falls back to in-memory if not set)
    firebase_project_id: Optional[str] = None
    firebase_service_account_json: Optional[str] = None
    google_application_credentials: Optional[str] = None
    firestore_emulator_host: Optional[str] = None

    # OpenAI (baseline script only)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # Server
    host: str = "0.0.0.0"
    port: int = 7860

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
