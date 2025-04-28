"""
Konfigurationsmodul für E-Mail-Funktionalitäten.

Dieses Modul enthält alle relevanten Konfigurationen für den E-Mail-Versand,
einschließlich SMTP-Server-Einstellungen und Standard-Absender-Informationen.
"""

import os
from pydantic import BaseModel, Field, EmailStr
from typing import Optional

# Standardwerte für Umgebungsvariablen, falls nicht gesetzt
DEFAULT_SMTP_HOST = "smtp.example.com"
DEFAULT_SMTP_PORT = 587
DEFAULT_SMTP_USERNAME = ""
DEFAULT_SMTP_PASSWORD = ""
DEFAULT_SENDER_EMAIL = "noreply@hccplan.example.com"
DEFAULT_SENDER_NAME = "HCC Plan"


class EmailConfig(BaseModel):
    """Konfigurationsmodell für SMTP und E-Mail-Einstellungen."""
    
    # SMTP-Server-Einstellungen
    smtp_host: str = Field(
        default_factory=lambda: os.environ.get("SMTP_HOST", DEFAULT_SMTP_HOST)
    )
    smtp_port: int = Field(
        default_factory=lambda: int(os.environ.get("SMTP_PORT", DEFAULT_SMTP_PORT))
    )
    smtp_username: str = Field(
        default_factory=lambda: os.environ.get("SMTP_USERNAME", DEFAULT_SMTP_USERNAME)
    )
    smtp_password: str = Field(
        default_factory=lambda: os.environ.get("SMTP_PASSWORD", DEFAULT_SMTP_PASSWORD)
    )
    
    # TLS/SSL-Einstellungen
    use_tls: bool = Field(
        default_factory=lambda: os.environ.get("SMTP_USE_TLS", "True").lower() in ("true", "1", "yes")
    )
    use_ssl: bool = Field(
        default_factory=lambda: os.environ.get("SMTP_USE_SSL", "False").lower() in ("true", "1", "yes")
    )
    
    # Timeout-Einstellungen
    timeout: int = Field(
        default_factory=lambda: int(os.environ.get("SMTP_TIMEOUT", "30"))
    )
    
    # Absender-Einstellungen
    default_sender_email: EmailStr = Field(
        default_factory=lambda: os.environ.get("DEFAULT_SENDER_EMAIL", DEFAULT_SENDER_EMAIL)
    )
    default_sender_name: str = Field(
        default_factory=lambda: os.environ.get("DEFAULT_SENDER_NAME", DEFAULT_SENDER_NAME)
    )
    
    # Rate-Limiting-Einstellungen
    rate_limit_per_hour: int = Field(
        default_factory=lambda: int(os.environ.get("EMAIL_RATE_LIMIT", "100"))
    )
    
    # Debug-Modus (sendet E-Mails an die Konsole anstatt per SMTP im Debug-Modus)
    debug_mode: bool = Field(
        default_factory=lambda: os.environ.get("EMAIL_DEBUG_MODE", "False").lower() in ("true", "1", "yes")
    )
    
    # Optionale Debug-E-Mail-Adresse (alle E-Mails gehen an diese Adresse im Debug-Modus, wenn gesetzt)
    debug_email: Optional[EmailStr] = Field(
        default_factory=lambda: os.environ.get("EMAIL_DEBUG_ADDRESS", None)
    )

    @property
    def sender_formatted(self) -> str:
        """Formatierte Absender-Zeichenkette für E-Mail-Header."""
        return f"{self.default_sender_name} <{self.default_sender_email}>"


# Globale Konfigurationsinstanz
email_config = EmailConfig()


def load_config_from_file(file_path: str) -> None:
    """
    Lädt die Konfiguration aus einer Datei.
    
    Args:
        file_path: Pfad zur Konfigurationsdatei (TOML-Format)
    """
    import toml
    
    with open(file_path, "r", encoding="utf-8") as f:
        config_data = toml.load(f)
    
    if "email" in config_data:
        email_settings = config_data["email"]
        for key, value in email_settings.items():
            if hasattr(email_config, key):
                setattr(email_config, key, value)
