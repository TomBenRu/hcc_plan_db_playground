"""Persistente Konfiguration der Web-API-URL fuer den Desktop-Client.

Speichert die vom User im Login-Dialog gewaehlte Server-URL in einer
TOML-Datei im User-Config-Verzeichnis. Wird vom DesktopApiClient als
Fallback genutzt, wenn keine `DESKTOP_API_URL`-Env-Var gesetzt ist.

Aufloesungsreihenfolge im Client (siehe `gui/api_client/client.py`):
    1. os.environ["DESKTOP_API_URL"]   — Dev-/CI-Override
    2. diese TOML (User-Wahl im Login-Dialog)
    3. Default: http://127.0.0.1:8000
"""
import os

import toml
from pydantic import BaseModel
from toml.decoder import TomlDecodeError

from configuration.project_paths import curr_user_path_handler


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


class DesktopApiSettings(BaseModel):
    base_url: str = DEFAULT_BASE_URL


class DesktopApiConfigHandler:
    def __init__(self):
        self._toml_dir = os.path.join(
            curr_user_path_handler.get_config().config_file_path, 'desktop_api'
        )
        self._config_file_path = os.path.join(self._toml_dir, 'desktop_api.toml')
        self._settings: DesktopApiSettings | None = None
        self._check_config_dir()

    def _check_config_dir(self):
        if not os.path.exists(self._toml_dir):
            os.makedirs(self._toml_dir)

    def _load_from_file(self) -> DesktopApiSettings:
        try:
            with open(self._config_file_path, 'r', encoding='utf-8') as f:
                return DesktopApiSettings.model_validate(toml.load(f))
        except FileNotFoundError:
            return DesktopApiSettings()
        except TomlDecodeError:
            return DesktopApiSettings()

    def get_settings(self) -> DesktopApiSettings:
        if self._settings is None:
            self._settings = self._load_from_file()
        return self._settings

    def save_settings(self, settings: DesktopApiSettings) -> None:
        self._settings = settings
        with open(self._config_file_path, 'w', encoding='utf-8') as f:
            toml.dump(settings.model_dump(mode='json'), f)


curr_desktop_api_config_handler = DesktopApiConfigHandler()