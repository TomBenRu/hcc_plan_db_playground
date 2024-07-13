import json
import os
from typing import Protocol

import toml

from pydantic import BaseModel


class MinimizationWeights(BaseModel):
    unassigned_shifts: float = 100_000
    sum_squared_deviations: float = 0.005
    constraints_weights_in_avail_day_groups: float = 1
    constraints_weights_in_event_groups: float = 1
    constraints_location_prefs: float = 0.001  # bei Faktor 0.0001 hat location prefs keinen Einfluss, komisch!
    constraints_partner_loc_prefs: float = 0.0001
    constraints_fixed_casts_conflicts: float = 1_000_000_000


class ConstraintsMultipliers(BaseModel):
    sliders_location_prefs: dict[float, int]  # WEIGHT_VARS_LOCATION_PREFS
    sliders_partner_loc_prefs: dict[float, int]  # WEIGHT_VARS_PARTNER_LOC_PREFS
    partner_loc_prefs: dict[float, int] = {}
    # todo: bei mehr als 2 Mitarbeitern werden die Weight-Vars angepasst. Derzeit funktional implementiert


class SolverConfig(BaseModel):
    minimization_weights: MinimizationWeights
    constraints_multipliers: ConstraintsMultipliers


class ConfigHandler(Protocol):
    _config_file_path: str

    @staticmethod
    def load_config_from_file(self) -> SolverConfig:
        ...

    @staticmethod
    def save_config_to_file(self, config: SolverConfig):
        ...

    @staticmethod
    def get_solver_config(self) -> SolverConfig:
        ...


class ConfigHandlerJson:
    _config_file_path = os.path.join(os.path.dirname(__file__), 'solver_config.json')
    _solver_config: SolverConfig | None = None

    @staticmethod
    def load_config_from_file() -> SolverConfig:
        with open(ConfigHandlerJson._config_file_path, 'r') as f:
            return SolverConfig.model_validate(json.load(f))

    @staticmethod
    def save_config_to_file(config: SolverConfig):
        ConfigHandlerJson._solver_config = config
        with open(ConfigHandlerJson._config_file_path, 'w') as f:
            json.dump(config.model_dump(), f)

    @staticmethod
    def get_solver_config() -> SolverConfig:
        if ConfigHandlerJson._solver_config is None:
            ConfigHandlerJson._solver_config = ConfigHandlerJson.load_config_from_file()
        return ConfigHandlerJson._solver_config


class ConfigHandlerToml:
    _config_file_path = os.path.join(os.path.dirname(__file__), 'solver_config.toml')
    _solver_config: SolverConfig | None = None

    @staticmethod
    def load_config_from_file() -> SolverConfig:
        with open(ConfigHandlerToml._config_file_path, 'r') as f:
            return SolverConfig.model_validate(toml.load(f))

    @staticmethod
    def save_config_to_file(config: SolverConfig):
        ConfigHandlerToml._solver_config = config
        with open(ConfigHandlerToml._config_file_path, 'w') as f:
            toml.dump(config.model_dump(mode='json'), f)

    @staticmethod
    def get_solver_config() -> SolverConfig:
        if ConfigHandlerToml._solver_config is None:
            ConfigHandlerToml._solver_config = ConfigHandlerToml.load_config_from_file()
        return ConfigHandlerToml._solver_config


curr_config_handler = ConfigHandlerToml
