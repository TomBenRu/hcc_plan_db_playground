"""
SolverConfig - Konfigurationsklassen für den SAT-Solver

Diese Datei enthält alle Konfigurationsstrukturen für den Solver,
basierend auf der bestehenden Configuration aus curr_config_handler.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

from configuration.solver import curr_config_handler


@dataclass
class MinimizationWeights:
    """Gewichtungen für die Zielfunktions-Minimierung."""
    
    unassigned_shifts: float = 1000.0
    sum_squared_deviations: float = 1.0
    constraints_weights_in_avail_day_groups: float = 1.0
    constraints_weights_in_event_groups: float = 1.0
    constraints_location_prefs: float = 1.0
    constraints_partner_loc_prefs: float = 1.0
    constraints_fixed_casts_conflicts: float = 1000.0
    constraints_skills_match: float = 1000.0
    constraints_cast_rule: float = 100.0


@dataclass
class ConstraintMultipliers:
    """Multiplikatoren für verschiedene Constraint-Typen."""
    
    sliders_weights_event_groups: Dict[int, int]
    sliders_weights_avail_day_groups: Dict[int, int]
    group_depth_weights_event_groups: Dict[int, int]
    sliders_location_prefs: Dict[float, int]
    sliders_partner_loc_prefs: Dict[float, int]


@dataclass
class SolverParameters:
    """Parameter für den CP-SAT Solver."""
    
    max_time_in_seconds: int = 60
    log_search_progress: bool = False
    randomize_search: bool = True
    linearization_level: int = 0
    enumerate_all_solutions: bool = False
    solution_limit: Optional[int] = None


@dataclass
class SolverConfig:
    """
    Zentrale Konfiguration für den SAT-Solver.
    
    Diese Klasse kapselt alle Konfigurationsparameter und bietet
    eine einheitliche Schnittstelle für Solver-Einstellungen.
    """
    
    minimization_weights: MinimizationWeights
    constraint_multipliers: ConstraintMultipliers
    solver_parameters: SolverParameters
    
    def __init__(self, 
                 minimization_weights: Optional[MinimizationWeights] = None,
                 constraint_multipliers: Optional[ConstraintMultipliers] = None,
                 solver_parameters: Optional[SolverParameters] = None):
        """
        Initialisiert die Solver-Konfiguration.
        
        Args:
            minimization_weights: Gewichtungen für Zielfunktion
            constraint_multipliers: Multiplikatoren für Constraints
            solver_parameters: Parameter für den Solver
        """
        
        self.minimization_weights = minimization_weights or self._load_default_weights()
        self.constraint_multipliers = constraint_multipliers or self._load_default_multipliers()
        self.solver_parameters = solver_parameters or SolverParameters()
    
    @classmethod
    def from_current_config(cls) -> 'SolverConfig':
        """
        Erstellt eine SolverConfig aus der aktuellen Konfiguration.
        
        Returns:
            SolverConfig basierend auf curr_config_handler
        """
        current_config = curr_config_handler.get_solver_config()
        
        # Lade Minimization Weights
        weights = MinimizationWeights(
            unassigned_shifts=current_config.minimization_weights.unassigned_shifts,
            sum_squared_deviations=current_config.minimization_weights.sum_squared_deviations,
            constraints_weights_in_avail_day_groups=current_config.minimization_weights.constraints_weights_in_avail_day_groups,
            constraints_weights_in_event_groups=current_config.minimization_weights.constraints_weights_in_event_groups,
            constraints_location_prefs=current_config.minimization_weights.constraints_location_prefs,
            constraints_partner_loc_prefs=current_config.minimization_weights.constraints_partner_loc_prefs,
            constraints_fixed_casts_conflicts=current_config.minimization_weights.constraints_fixed_casts_conflicts,
            constraints_skills_match=current_config.minimization_weights.constraints_skills_match,
            constraints_cast_rule=current_config.minimization_weights.constraints_cast_rule
        )
        
        # Lade Constraint Multipliers
        multipliers = ConstraintMultipliers(
            sliders_weights_event_groups=current_config.constraints_multipliers.sliders_weights_event_groups,
            sliders_weights_avail_day_groups=current_config.constraints_multipliers.sliders_weights_avail_day_groups,
            group_depth_weights_event_groups=current_config.constraints_multipliers.group_depth_weights_event_groups,
            sliders_location_prefs=current_config.constraints_multipliers.sliders_location_prefs,
            sliders_partner_loc_prefs=current_config.constraints_multipliers.sliders_partner_loc_prefs
        )
        
        return cls(
            minimization_weights=weights,
            constraint_multipliers=multipliers,
            solver_parameters=SolverParameters()
        )
    
    def _load_default_weights(self) -> MinimizationWeights:
        """Lädt Standard-Gewichtungen."""
        return MinimizationWeights()
    
    def _load_default_multipliers(self) -> ConstraintMultipliers:
        """Lädt Standard-Multiplikatoren."""
        return ConstraintMultipliers(
            sliders_weights_event_groups={0: 0, 1: 5, 2: 20, 3: 50, 4: 100, 5: 200},
            sliders_weights_avail_day_groups={0: 0, 1: 5, 2: 20, 3: 50, 4: 100, 5: 200},
            group_depth_weights_event_groups={0: 1, 1: 2, 2: 4, 3: 8, 4: 16, 5: 32},
            sliders_location_prefs={0: 0, 0.5: 10, 1: 5, 1.5: 3, 2: 1},
            sliders_partner_loc_prefs={0: 1000, 0.5: 100, 1: 5, 1.5: 3, 2: 1}
        )
    
    def update_solver_time(self, seconds: int) -> None:
        """
        Aktualisiert die maximale Solver-Zeit.
        
        Args:
            seconds: Maximale Zeit in Sekunden
        """
        self.solver_parameters.max_time_in_seconds = seconds
    
    def enable_logging(self, enabled: bool = True) -> None:
        """
        Aktiviert/deaktiviert Solver-Logging.
        
        Args:
            enabled: True um Logging zu aktivieren
        """
        self.solver_parameters.log_search_progress = enabled
    
    def set_solution_limit(self, limit: Optional[int]) -> None:
        """
        Setzt ein Limit für die Anzahl der Lösungen.
        
        Args:
            limit: Maximale Anzahl Lösungen, None für unbegrenzt
        """
        self.solver_parameters.solution_limit = limit
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Konvertiert die Konfiguration zu einem Dictionary.
        
        Returns:
            Dictionary-Repräsentation der Konfiguration
        """
        return {
            'minimization_weights': self.minimization_weights.__dict__,
            'constraint_multipliers': self.constraint_multipliers.__dict__,
            'solver_parameters': self.solver_parameters.__dict__
        }
    
    def copy(self) -> 'SolverConfig':
        """
        Erstellt eine Kopie der Konfiguration.
        
        Returns:
            Neue SolverConfig-Instanz mit gleichen Werten
        """
        return SolverConfig(
            minimization_weights=MinimizationWeights(**self.minimization_weights.__dict__),
            constraint_multipliers=ConstraintMultipliers(**self.constraint_multipliers.__dict__),
            solver_parameters=SolverParameters(**self.solver_parameters.__dict__)
        )
