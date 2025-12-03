# sat_solver/constraints/base.py
"""
Abstrakte Basisklasse für alle Solver-Constraints.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

from dataclasses import dataclass

from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

if TYPE_CHECKING:
    from sat_solver.constraints.registry import ConstraintRegistry
    from database import schemas


@dataclass
class ValidationError:
    """
    Repräsentiert einen Validierungsfehler bei der Plan-Prüfung.
    
    Wird von Constraints zurückgegeben, die das Validatable-Protokoll implementieren.
    
    Attributes:
        category: Kategorie des Fehlers (z.B. "Feste Besetzung", "Fertigkeitskonflikt")
        message: Detaillierte Fehlerbeschreibung
    """
    category: str
    message: str
    
    def to_html(self) -> str:
        """Formatiert den Fehler als HTML für die UI-Anzeige."""
        return (f'<p style="margin-bottom: 4px; margin-top: 8px;">{self.category}:</p>'
                f'<p style="margin-left: 20px; margin-bottom: 4px; margin-top: 4px;">'
                f'{self.message}</p>')


@runtime_checkable
class Validatable(Protocol):
    """
    Protocol für Constraints, die Plan-Validierung unterstützen.
    
    Constraints die dieses Protocol implementieren, können einen bestehenden Plan
    ohne Solver auf Regelverletzungen prüfen. Dies ermöglicht schnelle Validierung
    mit klaren Fehlermeldungen.
    
    Die Registry nutzt isinstance(constraint, Validatable) um zu prüfen,
    ob ein Constraint Validierung unterstützt.
    
    Example:
        >>> class MyConstraint(ConstraintBase, Validatable):
        ...     def validate_plan(self, plan) -> list[ValidationError]:
        ...         errors = []
        ...         # Prüflogik hier
        ...         return errors
    """
    name: str
    
    def validate_plan(self, plan: 'schemas.PlanShow') -> list[ValidationError]:
        """
        Validiert einen bestehenden Plan gegen dieses Constraint.
        
        Args:
            plan: Der zu prüfende Plan
        
        Returns:
            Liste von ValidationError-Objekten für gefundene Verstöße.
            Leere Liste wenn keine Verstöße gefunden wurden.
        """
        ...


class ConstraintBase(ABC):
    """
    Abstrakte Basisklasse für alle Solver-Constraints.
    
    Jedes Constraint muss:
    - einen eindeutigen Namen haben (name)
    - einen Weight-Attribut-Namen für die Objective-Funktion definieren (weight_attribute)
    - die apply()-Methode implementieren
    
    Die apply()-Methode fügt Constraints zum Model hinzu und speichert
    erzeugte Penalty-Variablen in self.penalty_vars.
    
    Attributes:
        name: Eindeutiger Name des Constraints (für Logging/Debugging)
        weight_attribute: Name des Attributs in MinimizationWeights für dieses Constraint
        penalty_vars: Liste der erzeugten Penalty-Variablen für die Objective-Funktion
        registry: Referenz zur ConstraintRegistry (wird bei Registrierung gesetzt)
    
    Example:
        >>> class MyConstraint(ConstraintBase):
        ...     name = "my_constraint"
        ...     weight_attribute = "constraints_my_feature"
        ...     
        ...     def apply(self) -> None:
        ...         # Constraint-Logik hier
        ...         penalty_var = self.model.NewIntVar(0, 100, "penalty")
        ...         self.penalty_vars.append(penalty_var)
    """
    
    # Muss von Subklassen überschrieben werden
    name: str = ""
    weight_attribute: str = ""
    
    def __init__(self):
        """Initialisiert das Constraint mit leerer Penalty-Liste."""
        self.penalty_vars: list[IntVar] = []
        self._registry: 'ConstraintRegistry | None' = None
    
    @property
    def registry(self) -> 'ConstraintRegistry':
        """Gibt die zugehörige Registry zurück."""
        if self._registry is None:
            raise RuntimeError(
                f"Constraint '{self.name}' wurde nicht bei einer Registry registriert. "
                f"Verwende registry.register() bevor apply() aufgerufen wird."
            )
        return self._registry
    
    @registry.setter
    def registry(self, value: 'ConstraintRegistry') -> None:
        """Setzt die Registry-Referenz."""
        self._registry = value
    
    @property
    def model(self) -> cp_model.CpModel:
        """Shortcut für Zugriff auf das CP-Model."""
        return self.registry.model
    
    @property
    def entities(self):
        """Shortcut für Zugriff auf die Entities."""
        return self.registry.entities
    
    @property
    def config(self):
        """Shortcut für Zugriff auf die Solver-Konfiguration."""
        return self.registry.config
    
    @abstractmethod
    def apply(self) -> None:
        """
        Wendet das Constraint auf das Model an.
        
        Diese Methode muss von Subklassen implementiert werden.
        Sie sollte:
        1. Constraints zum self.model hinzufügen
        2. Penalty-Variablen zu self.penalty_vars hinzufügen (bei Soft Constraints)
        
        Raises:
            NotImplementedError: Wenn nicht von Subklasse implementiert
        """
        raise NotImplementedError(
            f"Constraint '{self.name}' muss die apply()-Methode implementieren"
        )
    
    def get_weight(self) -> float:
        """
        Gibt das konfigurierte Weight für dieses Constraint zurück.
        
        Returns:
            Das Weight aus der Solver-Konfiguration, oder 0 wenn nicht definiert
        """
        if not self.weight_attribute:
            return 0.0
        return getattr(self.config.minimization_weights, self.weight_attribute, 0.0)
    
    def get_penalty_sum(self) -> int | IntVar:
        """
        Berechnet die Summe aller Penalty-Variablen.
        
        Returns:
            Summe der Penalties (0 wenn keine vorhanden)
        """
        if not self.penalty_vars:
            return 0
        return sum(self.penalty_vars)
    
    def get_weighted_penalty_sum(self) -> float | IntVar:
        """
        Berechnet die gewichtete Summe aller Penalty-Variablen.
        
        Returns:
            Weight * Summe der Penalties
        """
        return self.get_weight() * self.get_penalty_sum()
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', penalties={len(self.penalty_vars)})"
