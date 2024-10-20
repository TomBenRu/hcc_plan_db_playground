import os

import toml
from pydantic import BaseModel, EmailStr
from toml.decoder import TomlDecodeError

from configuration.project_paths import curr_user_path_handler


class Authentication(BaseModel):
    username: EmailStr = 'example@mail.com'
    password: str = ''


class Endpoints(BaseModel):
    auth: str = ''
    get_project: str = ''
    get_persons: str = ''
    get_teams: str = ''
    get_plan_periods: str = ''
    post_plan_period: str = ''
    fetch_avail_days: str = ''


class ApiRemote(BaseModel):
    host: str = ''
    authentication: Authentication = Authentication()
    endpoints: Endpoints = Endpoints()


class ConfigHandlerToml:
    def __init__(self):
        self._toml_dir = os.path.join(curr_user_path_handler.get_config().config_file_path, 'api_remote')
        self._config_file_path = os.path.join(self._toml_dir, 'api_remote_config.toml')
        self._api_remote: ApiRemote | None = None
        self._check_config_dir()

    def _check_config_dir(self):
        if not os.path.exists(self._toml_dir):
            os.makedirs(self._toml_dir)

    def load_config_from_file(self) -> ApiRemote:
        if not os.path.exists(self._config_file_path):
            return ApiRemote()
        else:
            try:
                with open(self._config_file_path, 'r') as f:
                    return ApiRemote.model_validate(toml.load(f))
            except FileNotFoundError:
                raise FileNotFoundError('api_remote.toml not found')
            except TomlDecodeError as e:
                raise Exception(f'Fehler beim laden der "api_remote_config.toml": {e}')

    def save_config_to_file(self, config: ApiRemote):
        self._api_remote = config
        with open(self._config_file_path, 'w') as f:
            toml.dump(config.model_dump(mode='json'), f)

    def get_api_remote(self) -> ApiRemote:
        if self._api_remote is None:
            self._api_remote = self.load_config_from_file()
        return self._api_remote


current_config_handler = ConfigHandlerToml()
