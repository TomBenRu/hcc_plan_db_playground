# sat_solver/constraints/registry.py
"""
Registry zur Verwaltung aller Solver-Constraints.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Type

from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

from configuration.solver import SolverConfig, curr_config_handler

if TYPE_CHECKING:
    from sat_solver.constraints.base import ConstraintBase

logger = logging.getLogger(__name__)


class Entities:
    """
    Container für alle Solver-Entitäten.
    
    HINWEIS: Diese Klasse ist ein Platzhalter für die Typ-Annotationen.
    In der Integration wird die echte Entities-Klasse aus solver_main.py verwendet.
    
    Hält alle Datenstrukturen, die von den Constraints benötigt werden:
    - actor_plan_periods: Mitarbeiter-Perioden-Zuordnungen
    - avail_day_groups: Verfügbarkeits-Gruppen
    - event_groups: Event-Gruppen
    - cast_groups: Besetzungs-Gruppen
    - shift_vars: Schicht-Variablen (BoolVars für jede mögliche Zuweisung)
    - shifts_exclusive: Dict das angibt, ob eine Schicht möglich ist (0/1)
    - etc.
    """
    pass  # Die echte Implementierung kommt aus solver_main.py


class ConstraintRegistry:
    """
    Registry zur Verwaltung und Ausführung aller Solver-Constraints.
    
    Die Registry ist der zentrale Punkt für:
    - Registrierung von Constraint-Klassen
    - Ausführung aller Constraints
    - Berechnung der gewichteten Objective-Funktion
    - Logging und Debugging
    
    Attributes:
        model: Das OR-Tools CP-SAT Model
        entities: Container mit allen Solver-Entitäten
        config: Solver-Konfiguration (Weights, Multipliers)
        constraints: Liste aller registrierten Constraints
    
    Example:
        >>> model = cp_model.CpModel()
        >>> entities = Entities()
        >>> registry = ConstraintRegistry(model, entities)
        >>> 
        >>> # Constraints registrieren
        >>> registry.register(LocationPrefsConstraint)
        >>> registry.register(FixedCastConflictsConstraint)
        >>> 
        >>> # Alle Constraints anwenden
        >>> registry.apply_all()
        >>> 
        >>> # Objective-Funktion definieren
        >>> model.Minimize(registry.get_total_weighted_penalty())
    """
    
    def __init__(
        self,
        model: cp_model.CpModel,
        entities: Entities,
        config: SolverConfig | None = None
    ):
        """
        Initialisiert die Registry.
        
        Args:
            model: Das CP-SAT Model für Constraint-Erstellung
            entities: Container mit allen Solver-Entitäten
            config: Solver-Konfiguration (optional, nutzt sonst curr_config_handler)
        """
        self.model = model
        self.entities = entities
        self.config = config or curr_config_handler.get_solver_config()
        self._constraints: list[ConstraintBase] = []
    
    @property
    def constraints(self) -> list['ConstraintBase']:
        """Gibt alle registrierten Constraints zurück."""
        return self._constraints.copy()
    
    def register(self, constraint_class: type['ConstraintBase']) -> 'ConstraintBase':
        """
        Registriert eine Constraint-Klasse.
        
        Erstellt eine Instanz der Constraint-Klasse und fügt sie zur Registry hinzu.
        Das Constraint wird noch NICHT angewendet - dafür muss apply_all() 
        oder apply() auf dem Constraint aufgerufen werden.
        
        Args:
            constraint_class: Die Constraint-Klasse (nicht Instanz!)
        
        Returns:
            Die erstellte Constraint-Instanz
        
        Example:
            >>> constraint = registry.register(LocationPrefsConstraint)
            >>> print(constraint.name)  # "location_prefs"
        """
        constraint = constraint_class()
        constraint.registry = self
        self._constraints.append(constraint)
        logger.debug(f"Constraint registriert: {constraint.name}")
        return constraint
    
    def register_instance(self, constraint: 'ConstraintBase') -> 'ConstraintBase':
        """
        Registriert eine bereits erstellte Constraint-Instanz.
        
        Nützlich wenn ein Constraint mit speziellen Parametern erstellt wurde.
        
        Args:
            constraint: Die Constraint-Instanz
        
        Returns:
            Die registrierte Constraint-Instanz
        """
        constraint.registry = self
        self._constraints.append(constraint)
        logger.debug(f"Constraint-Instanz registriert: {constraint.name}")
        return constraint
    
    def apply_all(self) -> None:
        """
        Wendet alle registrierten Constraints an.
        
        Ruft apply() auf jedem registrierten Constraint auf.
        Die Reihenfolge entspricht der Registrierungsreihenfolge.
        
        Raises:
            RuntimeError: Wenn ein Constraint fehlschlägt
        """
        logger.info(f"Wende {len(self._constraints)} Constraints an...")
        
        for constraint in self._constraints:
            try:
                logger.debug(f"Wende Constraint an: {constraint.name}")
                constraint.apply()
                logger.debug(
                    f"Constraint '{constraint.name}' angewendet: "
                    f"{len(constraint.penalty_vars)} Penalty-Variablen"
                )
            except Exception as e:
                logger.error(f"Fehler bei Constraint '{constraint.name}': {e}")
                raise RuntimeError(
                    f"Constraint '{constraint.name}' fehlgeschlagen: {e}"
                ) from e
        
        logger.info(f"Alle {len(self._constraints)} Constraints angewendet")
    
    def get_constraint(self, constraint_class: Type[ConstraintBase]) -> ConstraintBase | None:
        """
        Gibt ein Constraint anhand seiner Klasse zurück.
        
        Args:
            constraint_class: Die Klasse des Constraints
        
        Returns:
            Das Constraint oder None wenn nicht gefunden
        """
        return next((c for c in self._constraints if isinstance(c, constraint_class)), None)
    
    def get_all_penalty_vars(self) -> dict[str, list[IntVar]]:
        """
        Gibt alle Penalty-Variablen gruppiert nach Constraint-Name zurück.
        
        Returns:
            Dict mit Constraint-Name als Key und Liste von Penalty-Vars als Value
        """
        return {
            constraint.name: constraint.penalty_vars
            for constraint in self._constraints
        }
    
    def get_total_weighted_penalty(self) -> IntVar | int:
        """
        Berechnet die gewichtete Summe aller Penalties.
        
        Diese Methode erstellt den Ausdruck für die Objective-Funktion,
        indem sie jede Constraint-Penalty mit ihrem konfigurierten Weight multipliziert.
        
        Returns:
            Die gewichtete Summe aller Penalties (für model.Minimize())
        """
        total = 0
        
        for constraint in self._constraints:
            weight = constraint.get_weight()
            penalty_vars = constraint.penalty_vars
            
            # Nur hinzufügen wenn es Penalty-Variablen gibt und Weight != 0
            if penalty_vars and weight != 0:
                weighted_sum = weight * sum(penalty_vars)
                total += weighted_sum
                logger.debug(
                    f"Constraint '{constraint.name}': "
                    f"weight={weight}, "
                    f"penalties={len(penalty_vars)}"
                )
        
        return total
    
    def get_penalty_summary(self, solver: cp_model.CpSolver) -> dict[str, dict]:
        """
        Erstellt eine Zusammenfassung aller Penalty-Werte nach dem Solving.
        
        Args:
            solver: Der Solver nach dem Lösen des Models
        
        Returns:
            Dict mit Statistiken pro Constraint:
            {
                "constraint_name": {
                    "weight": 1000,
                    "num_penalties": 5,
                    "penalty_sum": 3,
                    "weighted_sum": 3000,
                    "details": [...]  # Einzelne Penalty-Werte
                }
            }
        """
        summary = {}
        
        for constraint in self._constraints:
            penalty_values = [
                solver.Value(var) if hasattr(var, 'Index') else var
                for var in constraint.penalty_vars
            ]
            penalty_sum = sum(penalty_values)
            
            summary[constraint.name] = {
                "weight": constraint.get_weight(),
                "num_penalties": len(constraint.penalty_vars),
                "penalty_sum": penalty_sum,
                "weighted_sum": constraint.get_weight() * penalty_sum,
                "details": penalty_values
            }
        
        return summary
    
    def log_penalty_summary(self, solver: cp_model.CpSolver) -> None:
        """
        Loggt eine Zusammenfassung aller Penalty-Werte.
        
        Args:
            solver: Der Solver nach dem Lösen des Models
        """
        summary = self.get_penalty_summary(solver)
        
        logger.info("=" * 60)
        logger.info("Penalty-Zusammenfassung:")
        logger.info("=" * 60)
        
        total_weighted = 0
        for name, data in summary.items():
            if data["penalty_sum"] > 0:
                logger.info(
                    f"  {name}: "
                    f"sum={data['penalty_sum']}, "
                    f"weighted={data['weighted_sum']:.2f}"
                )
                total_weighted += data["weighted_sum"]
        
        logger.info("-" * 60)
        logger.info(f"  GESAMT (gewichtet): {total_weighted:.2f}")
        logger.info("=" * 60)
    
    def __repr__(self) -> str:
        constraint_names = [c.name for c in self._constraints]
        return f"ConstraintRegistry(constraints={constraint_names})"
