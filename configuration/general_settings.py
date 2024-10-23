import os

import toml
from toml.decoder import TomlDecodeError

from pydantic import BaseModel

from configuration.api_remote_config import ConfigHandlerToml
from configuration.config_handler import ConfigHandler
from configuration.project_paths import curr_user_path_handler


class PlanSettings(BaseModel):
    """
    Plan settings for the application.
    """
    column_width: int = 120


class GeneralSettings(BaseModel):
    """
    General settings for the application.
    """
    plan_settings: PlanSettings = PlanSettings()


class GeneralSettingsHandler:
    """
    Handler for general settings.
    """
    def __init__(self):
        self._toml_dir = os.path.join(curr_user_path_handler.get_config().config_file_path, 'general_settings')
        self._toml_file = os.path.join(self._toml_dir, 'general_settings.toml')
        self._general_settings: GeneralSettings | None = None
        self.check_toml_dir()

    def check_toml_dir(self):
        if not os.path.exists(self._toml_dir):
            os.makedirs(self._toml_dir)

    def load_toml_file(self):
        try:
            with open(self._toml_file, 'r') as f:
                return GeneralSettings.model_validate(toml.load(f))
        except FileNotFoundError:
            return GeneralSettings()
        except TomlDecodeError:
            return GeneralSettings()

    def save_to_toml_file(self, general_settings: GeneralSettings):
        self._general_settings = general_settings
        with open(self._toml_file, 'w') as f:
            toml.dump(general_settings.model_dump(mode='json'), f)

    def get_general_settings(self) -> GeneralSettings:
        if self._general_settings is None:
            self._general_settings = self.load_toml_file()
        return self._general_settings


general_settings_handler = GeneralSettingsHandler()
