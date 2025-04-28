"""
Konfigurationsmodul für E-Mail-Funktionalitäten.

Dieses Modul lädt die E-Mail-Konfiguration aus der zentralen Konfiguration
und stellt sie für das E-Mail-Modul bereit.
"""

import os
from typing import Optional, Dict, Any

try:
    # Importiere die zentrale Konfiguration
    from configuration.email_config import get_email_config, EmailSettings
    use_central_config = True
except ImportError:
    # Fallback auf lokale Konfiguration, wenn die zentrale nicht verfügbar ist
    use_central_config = False
    from pydantic import BaseModel, Field, EmailStr


# Fallback-Konfigurationsklasse für den Fall, dass die zentrale Konfiguration nicht verfügbar ist
if not use_central_config:
    class EmailConfig(BaseModel):
        """Lokales Konfigurationsmodell für SMTP und E-Mail-Einstellungen."""
        
        # SMTP-Server-Einstellungen
        smtp_host: str = Field(
            default_factory=lambda: os.environ.get("SMTP_HOST", "smtp.example.com")
        )
        smtp_port: int = Field(
            default_factory=lambda: int(os.environ.get("SMTP_PORT", "587"))
        )
        smtp_username: str = Field(
            default_factory=lambda: os.environ.get("SMTP_USERNAME", "")
        )
        smtp_password: str = Field(
            default_factory=lambda: os.environ.get("SMTP_PASSWORD", "")
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
            default_factory=lambda: os.environ.get("DEFAULT_SENDER_EMAIL", "noreply@hccplan.example.com")
        )
        default_sender_name: str = Field(
            default_factory=lambda: os.environ.get("DEFAULT_SENDER_NAME", "HCC Plan")
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
else:
    # Adapter-Klasse für die zentrale Konfiguration
    class EmailConfig:
        """Adapter-Klasse für die zentrale E-Mail-Konfiguration."""
        
        def __init__(self):
            self._config = get_email_config()
            self._settings = self._config.get_settings()
            self._credentials = self._config.get_smtp_credentials()
            
        @property
        def smtp_host(self) -> str:
            return self._credentials.get("smtp_host", "")
            
        @property
        def smtp_port(self) -> int:
            return self._credentials.get("smtp_port", 587)
            
        @property
        def smtp_username(self) -> str:
            return self._credentials.get("smtp_username", "")
            
        @property
        def smtp_password(self) -> str:
            return self._credentials.get("smtp_password", "")
            
        @property
        def use_tls(self) -> bool:
            return self._settings.use_tls
            
        @property
        def use_ssl(self) -> bool:
            return self._settings.use_ssl
            
        @property
        def timeout(self) -> int:
            return self._settings.timeout
            
        @property
        def default_sender_email(self) -> str:
            return self._settings.default_sender_email
            
        @property
        def default_sender_name(self) -> str:
            return self._settings.default_sender_name
            
        @property
        def rate_limit_per_hour(self) -> int:
            return self._settings.rate_limit_per_hour
            
        @property
        def debug_mode(self) -> bool:
            return self._settings.debug_mode
            
        @property
        def debug_email(self) -> Optional[str]:
            return self._settings.debug_email
            
        @property
        def sender_formatted(self) -> str:
            """Formatierte Absender-Zeichenkette für E-Mail-Header."""
            return f"{self.default_sender_name} <{self.default_sender_email}>"
            
        def refresh(self):
            """Aktualisiert die Konfiguration aus der zentralen Konfiguration."""
            self._settings = self._config.get_settings()
            self._credentials = self._config.get_smtp_credentials()
            
        def save_settings(self, settings: Dict[str, Any]):
            """
            Speichert die Einstellungen in der zentralen Konfiguration.
            
            Args:
                settings: Dictionary mit den zu speichernden Einstellungen
            """
            # Extrahiere die sensitiven Daten
            host = settings.get("smtp_host", "")
            port = settings.get("smtp_port", 587)
            username = settings.get("smtp_username", "")
            password = settings.get("smtp_password", "")
            
            # Speichere die sensitiven Daten in der Keychain
            self._config.save_smtp_credentials(host, port, username, password)
            
            # Extrahiere die nicht-sensitiven Daten
            email_settings = EmailSettings(
                default_sender_email=settings.get("default_sender_email", self._settings.default_sender_email),
                default_sender_name=settings.get("default_sender_name", self._settings.default_sender_name),
                use_tls=settings.get("use_tls", self._settings.use_tls),
                use_ssl=settings.get("use_ssl", self._settings.use_ssl),
                timeout=settings.get("timeout", self._settings.timeout),
                rate_limit_per_hour=settings.get("rate_limit_per_hour", self._settings.rate_limit_per_hour),
                debug_mode=settings.get("debug_mode", self._settings.debug_mode),
                debug_email=settings.get("debug_email", self._settings.debug_email)
            )
            
            # Speichere die nicht-sensitiven Daten in der TOML-Datei
            self._config.save_settings(email_settings)
            
            # Aktualisiere die lokalen Kopien
            self.refresh()


# Globale Konfigurationsinstanz
email_config = EmailConfig()


def load_config_from_file(file_path: str) -> None:
    """
    Lädt die Konfiguration aus einer Datei.
    
    Diese Funktion wird aus Kompatibilitätsgründen beibehalten, ist aber bei 
    Verwendung der zentralen Konfiguration nicht mehr erforderlich.
    
    Args:
        file_path: Pfad zur Konfigurationsdatei (TOML-Format)
    """
    import toml
    
    with open(file_path, "r", encoding="utf-8") as f:
        config_data = toml.load(f)
    
    if "email" in config_data and use_central_config:
        email_settings = config_data["email"]
        email_config.save_settings(email_settings)
    elif not use_central_config:
        # Im Fallback-Modus: Setze Umgebungsvariablen
        if "email" in config_data:
            email_settings = config_data["email"]
            for key, value in email_settings.items():
                env_key = key.upper()
                if key.startswith("smtp_"):
                    env_key = "SMTP_" + key[5:].upper()
                elif key.startswith("default_sender_"):
                    env_key = "DEFAULT_SENDER_" + key[15:].upper()
                os.environ[env_key] = str(value)
