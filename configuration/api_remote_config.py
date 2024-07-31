import os

import toml
from pydantic import BaseModel, EmailStr
from toml.decoder import TomlDecodeError


class Authentication(BaseModel):
    username: EmailStr
    password: str


class Endpoints(BaseModel):
    auth: str
    get_project: str
    get_persons: str
    get_teams: str
    get_plan_periods: str


class ApiRemote(BaseModel):
    host: str
    authentication: Authentication
    endpoints: Endpoints


class ConfigHandlerToml:
    _config_file_path = os.path.join(os.path.dirname(__file__), 'api_remote_config.toml')
    _api_remote: ApiRemote | None = None

    @staticmethod
    def load_config_from_file() -> ApiRemote:
        try:
            with open(ConfigHandlerToml._config_file_path, 'r') as f:
                return ApiRemote.model_validate(toml.load(f))
        except FileNotFoundError:
            raise FileNotFoundError('api_remote.toml not found')
        except TomlDecodeError:
            raise TomlDecodeError('api_remote.toml not valid')

    @staticmethod
    def save_config_to_file(config: ApiRemote):
        ConfigHandlerToml._api_remote = config
        with open(ConfigHandlerToml._config_file_path, 'w') as f:
            toml.dump(config.model_dump(mode='json'), f)

    @staticmethod
    def get_api_remote() -> ApiRemote:
        if ConfigHandlerToml._api_remote is None:
            ConfigHandlerToml._api_remote = ConfigHandlerToml.load_config_from_file()
        return ConfigHandlerToml._api_remote


current_config_handler = ConfigHandlerToml
