import json
import os

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


class ConfigHandler:
    _config_file_path = os.path.join(os.path.dirname(__file__), 'solver_config.json')

    @staticmethod
    def load_config_from_file() -> SolverConfig:
        with open(ConfigHandler._config_file_path, 'r') as f:
            return SolverConfig.model_validate(json.load(f))

    @staticmethod
    def save_config_to_file(config: SolverConfig):
        with open(ConfigHandler._config_file_path, 'w') as f:
            json.dump(config.model_dump(), f)


solver_configs = ConfigHandler.load_config_from_file()
