import json
import os
from typing import Protocol

import toml

from pydantic import BaseModel
from toml import TomlDecodeError

from configuration.project_paths import curr_user_path_handler


class MinimizationWeights(BaseModel):
    unassigned_shifts: float = 100_000
    sum_squared_deviations: float = 0.5
    constraints_weights_in_avail_day_groups: float = 1
    constraints_weights_in_event_groups: float = 1
    constraints_location_prefs: float = 0.001  # bei Faktor 0.0001 hat location prefs keinen Einfluss, komisch!
    constraints_partner_loc_prefs: float = 0.1
    constraints_fixed_casts_conflicts: float = 1_000_000_000
    constraints_cast_rule: float = 1000


class ConstraintsMultipliers(BaseModel):
    sliders_location_prefs: dict[float, int] = {0: 100_000_000_000_000, 0.5: 10, 1: 0, 1.5: -10, 2: -20} # WEIGHT_VARS_LOCATION_PREFS
    sliders_partner_loc_prefs: dict[float, int] = {0: 20, 0.5: 10, 1: 0, 1.5: -10, 2: -20}  # WEIGHT_VARS_PARTNER_LOC_PREFS
    sliders_levels_weights_event_groups: dict[float, int] = {1: 100, 2: 10, 3: 1}
    sliders_weights_avail_day_groups: dict[float, int] = {1: 1000, 2: 0, 3: -1}
    sliders_levels_weights_av_day_groups: dict[float, int] = {1: 1, 2: 1, 3: 1}
    partner_loc_prefs_levels: dict[float, int] = {}
    # todo: bei mehr als 2 Mitarbeitern werden die Weight-Vars angepasst. Derzeit funktional implementiert


class SolverConfig(BaseModel):
    minimization_weights: MinimizationWeights = MinimizationWeights()
    constraints_multipliers: ConstraintsMultipliers = ConstraintsMultipliers()


class ConfigHandlerJson:
    def __init__(self):
        self._json_dir = os.path.join(curr_user_path_handler.get_config().config_file_path, 'solver')
        self._config_file_path = os.path.join(self._json_dir, 'solver_config.json')
        self._solver_config: SolverConfig | None = None
        self._check_json_dir()

    def _check_json_dir(self):
        if not os.path.exists(self._json_dir):
            os.makedirs(self._json_dir)

    def load_config_from_file(self) -> SolverConfig:
        try:
            with open(self._config_file_path, 'r') as f:
                return SolverConfig.model_validate(json.load(f))
        except FileNotFoundError:
            return SolverConfig()
        except json.JSONDecodeError:
            return SolverConfig()

    def save_config_to_file(self, config: SolverConfig):
        self._solver_config = config
        with open(self._config_file_path, 'w') as f:
            json.dump(config.model_dump(), f)

    def get_solver_config(self) -> SolverConfig:
        if self._solver_config is None:
            self._solver_config = self.load_config_from_file()
        return self._solver_config


class ConfigHandlerToml:
    def __init__(self):
        self._toml_dir = os.path.join(curr_user_path_handler.get_config().config_file_path, 'solver')
        self._config_file_path = os.path.join(self._toml_dir, 'solver_config.toml')
        self._solver_config: SolverConfig | None = None
        self._check_toml_dir()

    def _check_toml_dir(self):
        if not os.path.exists(self._toml_dir):
            os.makedirs(self._toml_dir)

    def load_config_from_file(self) -> SolverConfig:
        try:
            with open(self._config_file_path, 'r') as f:
                return SolverConfig.model_validate(toml.load(f))
        except FileNotFoundError:
            return SolverConfig()
        except TomlDecodeError:
            return SolverConfig()

    def save_config_to_file(self, config: SolverConfig):
        self._solver_config = config
        with open(self._config_file_path, 'w') as f:
            toml.dump(config.model_dump(mode='json'), f)

    def get_solver_config(self) -> SolverConfig:
        if self._solver_config is None:
            self._solver_config = self.load_config_from_file()
        return self._solver_config


curr_config_handler = ConfigHandlerToml()
