import os

from pydantic import BaseModel
import toml
from toml.decoder import TomlDecodeError

from configuration.project_paths import curr_user_path_handler


class MainGeometry(BaseModel):
    width: int | None = None
    height: int | None = None
    x: int | None = None
    y: int | None = None
    maximized: bool | None = None


class GeometryManager:
    def __init__(self):
        self._toml_dir = os.path.join(curr_user_path_handler.get_config().config_file_path, 'main_geometry')
        self._main_geometry_file_path = os.path.join(self._toml_dir, 'main_geometry.toml')
        self._main_geometry: MainGeometry | None = None
        self._check_toml_dir()

    def _check_toml_dir(self):
        if not os.path.exists(self._toml_dir):
            os.makedirs(self._toml_dir)

    def _load_geometry_from_file(self) -> MainGeometry:
        try:
            with open(self._main_geometry_file_path, 'r') as f:
                return MainGeometry.model_validate(toml.load(f))
        except FileNotFoundError:
            return MainGeometry()
        except TomlDecodeError:
            return MainGeometry()

    def save_geometry_to_file(self, geometry: MainGeometry):
        self._main_geometry = geometry
        with open(self._main_geometry_file_path, 'w') as f:
            toml.dump(geometry.model_dump(mode='json'), f)

    def get_geometry(self) -> MainGeometry:
        if self._main_geometry is None:
            self._main_geometry = self._load_geometry_from_file()
        return self._main_geometry


geometry_manager = GeometryManager()
