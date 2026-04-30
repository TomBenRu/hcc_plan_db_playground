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

    # E-Mail-Verschlüsselung: Master-Key für SMTP-Passwörter in der DB.
    # Pflicht für jede Umgebung, in der E-Mails versendet werden — fehlende Werte
    # werden erst beim ersten Versand erkannt (EmailEncryptionKeyMissingError).
    # Generierung: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    EMAIL_ENCRYPTION_KEY: str = ""


def get_settings() -> Settings:
    """Factory — kann in Tests via dependency_overrides ersetzt werden."""
    return Settings()
