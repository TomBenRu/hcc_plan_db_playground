import dataclasses
import os

import toml
from pydantic import BaseModel
from toml.decoder import TomlDecodeError


@dataclasses.dataclass
class Paths:
    root_path: str


class UserPaths(BaseModel):
    excel_output_path: str = ''


class UserPathHandlerToml:
    _config_file_path = os.path.join(os.path.dirname(__file__), 'user_paths.toml')
    _config: UserPaths | None = None

    @staticmethod
    def load_config_from_file() -> UserPaths:
        try:
            with open(UserPathHandlerToml._config_file_path, 'r') as f:
                return UserPaths.model_validate(toml.load(f))
        except FileNotFoundError:
            return UserPaths()
        except TomlDecodeError:
            return UserPaths()

    @staticmethod
    def save_config_to_file(config: UserPaths):
        UserPathHandlerToml._start_config = config
        with open(UserPathHandlerToml._config_file_path, 'w') as f:
            toml.dump(config.model_dump(mode='json'), f)

    @staticmethod
    def get_config() -> UserPaths:
        if UserPathHandlerToml._config is None:
            UserPathHandlerToml._config = UserPathHandlerToml.load_config_from_file()
        return UserPathHandlerToml._config


curr_user_path_handler = UserPathHandlerToml
paths = Paths()
