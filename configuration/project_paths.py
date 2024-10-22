import dataclasses
import os
import platform

import toml
from pydantic import BaseModel
from toml.decoder import TomlDecodeError


@dataclasses.dataclass
class Paths:
    root_path: str = ''

if platform.system() == 'Windows':
    app_is_installed = os.path.dirname(__file__).split(os.sep)[1].startswith('Program Files')
    prog_name = 'hcc_plan' if app_is_installed else 'hcc_plan_dev'
    excel_output_root = os.path.join(os.path.expanduser('~'), 'Documents')
    config_file_root = os.getenv('APPDATA')
    db_file_root = os.getenv('LOCALAPPDATA')
    log_file_root = os.getenv('LOCALAPPDATA')
elif platform.system() == 'Linux':
    prog_name = 'hcc_plan'
    excel_output_root = os.path.join(os.path.expanduser('~'), 'Documents')
    config_file_root = os.path.join(os.path.expanduser('~'), '.config')
    db_file_root = os.path.join(os.path.expanduser('~'), '.local', 'share')
    log_file_root = os.path.join(os.path.expanduser('~'), '.local', 'state')
elif platform.system() == 'Darwin':
    prog_name = 'hcc_plan'
    excel_output_root = os.path.join(os.path.expanduser('~'), 'Documents')
    config_file_root = os.path.join(os.path.expanduser('~'), 'Library', 'Preferences')
    db_file_root = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
    log_file_root = os.path.join(os.path.expanduser('~'), 'Library', 'Logs')
else:
    raise NotImplementedError(f'Unsupported platform: {platform.system()}')


class UserPaths(BaseModel):
    excel_output_path: str = os.path.join(
        excel_output_root, 'happy_code_company', prog_name, 'excel_output')  # User's documents folder
    config_file_path: str = os.path.join(
        config_file_root, 'happy_code_company', prog_name, 'config')  # User's config folder
    db_file_path: str = os.path.join(
        db_file_root, 'happy_code_company', prog_name, 'database')  # User's database folder
    log_file_path: str = os.path.join(
        log_file_root, 'happy_code_company', prog_name, 'logs')  # User's logs folder


class UserPathHandlerToml:
    def __init__(self):
        self._toml_dir = os.path.join(UserPaths().config_file_path, 'paths')
        self._config_file_path = os.path.join(self._toml_dir, 'user_paths.toml')
        self._user_paths: UserPaths | None = None
        self._check_toml_dir()

    def _check_toml_dir(self):
        if not os.path.exists(self._toml_dir):
            os.makedirs(self._toml_dir)

    def load_config_from_file(self) -> UserPaths:
        try:
            with open(self._config_file_path, 'r') as f:
                return UserPaths.model_validate(toml.load(f))
        except FileNotFoundError:
            return UserPaths()
        except TomlDecodeError:
            return UserPaths()

    def save_config_to_file(self, user_paths: UserPaths):
        self._user_paths = user_paths
        with open(self._config_file_path, 'w') as f:
            toml.dump(user_paths.model_dump(mode='json'), f)

    def get_config(self) -> UserPaths:
        if self._user_paths is None:
            self._user_paths = self.load_config_from_file()
        return self._user_paths


curr_user_path_handler = UserPathHandlerToml()
paths = Paths()
