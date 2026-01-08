import json
import os

import toml

from pydantic import BaseModel
from toml import TomlDecodeError

from configuration.project_paths import curr_user_path_handler


class MinimizationWeights(BaseModel):
    """
    Gewichte für die Solver-Objective-Funktion.

    Alle Gewichte sind Integer-basiert für konsistente CP-SAT-Verarbeitung.
    Die Prioritätshierarchie (höher = wichtiger):

    1. Pseudo-Hard-Constraints: 1.000.000+ (quasi unverhandelbar)
    2. Kernfunktion (Schichten besetzen): 10.000
    3. Wichtige Regeln (Skills, Cast-Rules): 1.000
    4. Fairness (Schichtverteilung): 100
    5. Gruppen-Gewichtungen: 10
    6. Präferenzen (nice-to-have): 1
    """
    # Priorität 1: Pseudo-Hard-Constraints
    constraints_fixed_casts_conflicts: int = 10_000_000

    # Priorität 2: Kernfunktion
    unassigned_shifts: int = 100_000

    # Priorität 3: Wichtige Regeln
    prefer_fixed_cast_events: int = 10_000
    constraints_cast_rule: int = 10_000
    constraints_skills_match: int = 10_000

    # Priorität 4: Fairness (wird durch num_apps normalisiert)
    sum_squared_deviations: int = 100

    # Priorität 5: Gruppen-Gewichtungen
    constraints_weights_in_avail_day_groups: int = 10
    constraints_weights_in_event_groups: int = 10

    # Priorität 6: Präferenzen
    constraints_partner_loc_prefs: int = 1
    constraints_location_prefs: int = 1


class ConstraintsMultipliers(BaseModel):
    """
    Multiplikatoren für Slider-basierte Constraints.

    Alle Slider verwenden eine konsistente Skala von -100 bis +100:
    - Positive Werte = Penalty (zu vermeiden)
    - Negative Werte = Bonus (zu bevorzugen)
    - 0 = Neutral

    Bei Score 0 wird in LocationPrefs ein Hard-Constraint gesetzt (keine Penalty-Variable).
    """
    # Location-Präferenzen: Score 0 = Hard-Constraint (separat behandelt)
    sliders_location_prefs: dict[float, int] = {
        0: 0,       # Wird als Hard-Constraint behandelt, nicht als Penalty
        0.5: 100,   # Ungern: hohe Penalty
        1: 0,       # Neutral
        1.5: -50,   # Gern: Bonus
        2: -100     # Sehr gern: hoher Bonus
    }

    # Partner-Location-Präferenzen
    sliders_partner_loc_prefs: dict[float, int] = {
        0: 200,     # Nicht zusammen: sehr hohe Penalty
        0.5: 100,   # Ungern zusammen
        1: 0,       # Neutral
        1.5: -50,   # Gern zusammen
        2: -100     # Sehr gern zusammen
    }

    # Event-Gruppen Gewichtungen
    group_depth_weights_event_groups: dict[int, int] = {1: 10, 2: 5, 3: 1}
    sliders_weights_event_groups: dict[float, int] = {
        0: 100,     # Bevorzugt
        1: 0,       # Neutral
        2: -100     # Nicht bevorzugt
    }

    # AvailDay-Gruppen Gewichtungen
    sliders_weights_avail_day_groups: dict[float, int] = {
        0: 100,     # Bevorzugt
        1: 0,       # Neutral
        2: -100     # Nicht bevorzugt
    }

    partner_loc_prefs_levels: dict[float, int] = {}
    # TODO: Bei mehr als 2 Mitarbeitern werden die Weight-Vars angepasst


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
