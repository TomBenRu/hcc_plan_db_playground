"""
E-Mail-Konfigurationsmodul für die Einsatzplan-Software.

Dieses Modul verwaltet die E-Mail-Konfiguration, wobei sensitive Daten (wie SMTP-Passwörter) 
in der Systemkeychain und nicht-sensitive Daten in einer TOML-Datei gespeichert werden.
"""

import os
import keyring
import toml
from pydantic import BaseModel, EmailStr, Field
from toml.decoder import TomlDecodeError

from configuration.project_paths import curr_user_path_handler

# Keyring Service-Namen
KEYRING_SERVICE = "hcc_plan_email"
KEYRING_SMTP_HOST = "smtp_host"
KEYRING_SMTP_PORT = "smtp_port"
KEYRING_SMTP_USERNAME = "smtp_username"
KEYRING_SMTP_PASSWORD = "smtp_password"


class EmailSettings(BaseModel):
    """Basismodell für E-Mail-Einstellungen (nicht-sensitive Daten)."""
    
    default_sender_email: EmailStr = Field(default="noreply@hccplan.example.com")
    default_sender_name: str = Field(default="HCC Plan")
    use_tls: bool = Field(default=True)
    use_ssl: bool = Field(default=False)
    timeout: int = Field(default=30)
    rate_limit_per_hour: int = Field(default=100)
    debug_mode: bool = Field(default=False)
    debug_email: EmailStr | None = Field(default=None)


class EmailConfig:
    """
    Hauptklasse für E-Mail-Konfiguration, die beide Speichertypen verwendet:
    - Sensitive Daten werden in der Systemkeychain gespeichert
    - Nicht-sensitive Daten werden in einer TOML-Datei gespeichert
    """
    
    def __init__(self):
        self.toml_dir = os.path.join(curr_user_path_handler.get_config().config_file_path, 'email')
        self._config_file_path = os.path.join(self.toml_dir, 'email_settings.toml')
        self._settings = None
        self._check_toml_dir()
        
    def _check_toml_dir(self):
        """Stellt sicher, dass das Konfigurationsverzeichnis existiert."""
        if not os.path.exists(self.toml_dir):
            os.makedirs(self.toml_dir)
            
    def _load_settings_from_file(self) -> EmailSettings:
        """Lädt nicht-sensitive Einstellungen aus der TOML-Datei."""
        try:
            with open(self._config_file_path, 'r', encoding='utf-8') as f:
                data = toml.load(f)
                return EmailSettings.model_validate(data)
        except FileNotFoundError:
            # Wenn die Datei nicht existiert, Standardeinstellungen zurückgeben
            return EmailSettings()
        except TomlDecodeError:
            # Bei fehlerhafter TOML-Datei, Standardeinstellungen zurückgeben
            return EmailSettings()
            
    def get_settings(self) -> EmailSettings:
        """Gibt die aktuellen Einstellungen zurück."""
        if self._settings is None:
            self._settings = self._load_settings_from_file()
        return self._settings
        
    def save_settings(self, settings: EmailSettings):
        """Speichert nicht-sensitive Einstellungen in der TOML-Datei."""
        self._settings = settings
        with open(self._config_file_path, 'w', encoding='utf-8') as f:
            toml.dump(settings.model_dump(mode='json'), f)
            
    def get_smtp_credentials(self):
        """Holt die SMTP-Anmeldeinformationen.

        Reihenfolge:
        1. Env-Vars (Server-Deploys: Render, Docker, CI) — höchste Priorität.
        2. Systemkeychain (Desktop-Client) — Fallback.
        Auf Headless-Servern ohne Keyring-Backend werden Env-Vars genutzt; fehlen sie,
        liefert die Methode leere Strings statt zu crashen.
        """
        if env_host := os.environ.get("SMTP_HOST"):
            try:
                env_port = int(os.environ.get("SMTP_PORT", "587"))
            except ValueError:
                env_port = 587
            return {
                "smtp_host": env_host,
                "smtp_port": env_port,
                "smtp_username": os.environ.get("SMTP_USERNAME", ""),
                "smtp_password": os.environ.get("SMTP_PASSWORD", ""),
            }

        try:
            host = keyring.get_password(KEYRING_SERVICE, KEYRING_SMTP_HOST) or ""
            port_str = keyring.get_password(KEYRING_SERVICE, KEYRING_SMTP_PORT) or "587"
            username = keyring.get_password(KEYRING_SERVICE, KEYRING_SMTP_USERNAME) or ""
            password = keyring.get_password(KEYRING_SERVICE, KEYRING_SMTP_PASSWORD) or ""
        except keyring.errors.KeyringError:
            return {"smtp_host": "", "smtp_port": 587, "smtp_username": "", "smtp_password": ""}

        try:
            port = int(port_str)
        except ValueError:
            port = 587

        return {
            "smtp_host": host,
            "smtp_port": port,
            "smtp_username": username,
            "smtp_password": password
        }
        
    def save_smtp_credentials(self, host: str, port: int, username: str, password: str):
        """Speichert die SMTP-Anmeldeinformationen in der Systemkeychain."""
        keyring.set_password(KEYRING_SERVICE, KEYRING_SMTP_HOST, host)
        keyring.set_password(KEYRING_SERVICE, KEYRING_SMTP_PORT, str(port))
        keyring.set_password(KEYRING_SERVICE, KEYRING_SMTP_USERNAME, username)
        keyring.set_password(KEYRING_SERVICE, KEYRING_SMTP_PASSWORD, password)
        
    def get_full_config(self):
        """
        Gibt eine vollständige Konfiguration zurück, die sowohl sensitive als auch 
        nicht-sensitive Daten enthält.
        """
        settings = self.get_settings()
        credentials = self.get_smtp_credentials()
        
        config = settings.model_dump()
        config.update(credentials)
        
        return config


# Globale Instanz
curr_email_config = EmailConfig()


def get_email_config():
    """Hilfsfunktion, um die aktuelle E-Mail-Konfiguration zu erhalten."""
    return curr_email_config
