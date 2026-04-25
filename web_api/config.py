from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — required, kein SQLite-Fallback für Web-API
    DATABASE_URL: str

    # JWT (wird ab Phase 3 verwendet, hier schon definiert)
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # App
    DEBUG: bool = False
    APP_TITLE: str = "hcc_plan Web-API"
    BASE_URL: str = "http://localhost:8000"  # Basis für absolute Links (Reset-Mails etc.)

    # E-Mail
    EMAIL_BACKEND: str = "console"  # "smtp" | "console"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@hccplan.local"


def get_settings() -> Settings:
    """Factory — kann in Tests via dependency_overrides ersetzt werden."""
    return Settings()
