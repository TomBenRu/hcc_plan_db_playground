"""
AbstractConstraint - Basisklasse für alle SAT-Solver Constraints

Diese abstrakte Klasse definiert die einheitliche Schnittstelle
für alle Constraint-Implementierungen im refactored Solver.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from ortools.sat.python.cp_model import IntVar

from sat_solver.core.solver_context import SolverContext


class AbstractConstraint(ABC):
    """
    Abstrakte Basisklasse für alle Constraint-Implementierungen.
    
    Diese Klasse definiert die einheitliche Schnittstelle, die alle
    Constraint-Klassen implementieren müssen. Sie bietet Zugriff auf
    den gemeinsamen SolverContext und standardisiert den Workflow.
    """
    
    def __init__(self, context: SolverContext):
        """
        Initialisiert den Constraint mit dem Solver-Kontext.
        
        Args:
            context: Der gemeinsame SolverContext
        """
        self.context = context
        self.model = context.model
        self.entities = context.entities
        self.config = context.config
        self._constraint_vars: List[IntVar] = []
        self._is_created = False
        self._metadata: Dict[str, Any] = {}
    
    @property
    @abstractmethod
    def constraint_name(self) -> str:
        """
        Eindeutiger Name des Constraints für Referenzierung.
        
        Returns:
            String-Identifier für diesen Constraint-Typ
        """
        pass
    
    @abstractmethod
    def create_variables(self) -> List[IntVar]:
        """
        Erstellt die für diesen Constraint nötigen Variablen.
        
        Diese Methode sollte alle IntVar-Objekte erstellen, die
        für die Constraint-Implementierung benötigt werden.
        
        Returns:
            Liste der erstellten IntVar-Objekte
        """
        pass
    
    @abstractmethod
    def add_constraints(self) -> None:
        """
        Fügt die eigentlichen Constraints zum CP-Model hinzu.
        
        Diese Methode implementiert die spezifische Constraint-Logik
        und fügt alle notwendigen Bedingungen zum model hinzu.
        """
        pass
    
    def setup(self) -> None:
        """
        Führt die vollständige Constraint-Einrichtung durch.
        
        Diese Methode orchestriert den gesamten Setup-Prozess:
        1. Variablen erstellen
        2. Constraints hinzufügen  
        3. Variablen im Kontext registrieren
        """
        if self._is_created:
            return
        
        # 1. Variablen erstellen
        self._constraint_vars = self.create_variables()
        
        # 2. Constraints hinzufügen
        self.add_constraints()
        
        # 3. Variablen im Kontext registrieren
        if self._constraint_vars:
            self.context.add_constraint_vars(self.constraint_name, self._constraint_vars)
        
        # 4. Als erstellt markieren
        self._is_created = True
        
        # 5. Setup-spezifische Metadaten hinzufügen
        self._add_setup_metadata()
    
    def get_constraint_variables(self) -> List[IntVar]:
        """
        Gibt die von diesem Constraint erstellten Variablen zurück.
        
        Returns:
            Liste der IntVar-Objekte dieses Constraints
        """
        return self._constraint_vars.copy()
    
    def is_setup_complete(self) -> bool:
        """
        Prüft, ob der Constraint vollständig eingerichtet wurde.
        
        Returns:
            True wenn setup() erfolgreich ausgeführt wurde
        """
        return self._is_created
    
    def add_metadata(self, key: str, value: Any) -> None:
        """
        Fügt Metadaten zu diesem Constraint hinzu.
        
        Args:
            key: Metadaten-Schlüssel
            value: Metadaten-Wert
        """
        self._metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Holt Metadaten dieses Constraints.
        
        Args:
            key: Metadaten-Schlüssel
            default: Rückgabewert wenn Schlüssel nicht existiert
            
        Returns:
            Metadaten-Wert oder default
        """
        return self._metadata.get(key, default)
    
    def get_all_metadata(self) -> Dict[str, Any]:
        """
        Gibt alle Metadaten dieses Constraints zurück.
        
        Returns:
            Dictionary mit allen Metadaten
        """
        return self._metadata.copy()
    
    def validate_context(self) -> bool:
        """
        Validiert, ob der Kontext für diesen Constraint geeignet ist.
        
        Subklassen können diese Methode überschreiben, um spezifische
        Validierungen durchzuführen.
        
        Returns:
            True wenn der Kontext valide ist
        """
        return (
            self.context is not None and
            self.context.is_valid() and
            self.model is not None and
            self.entities is not None and
            self.config is not None
        )
    
    def _add_setup_metadata(self) -> None:
        """
        Fügt automatische Setup-Metadaten hinzu.
        
        Diese Metadaten werden automatisch nach dem Setup hinzugefügt
        und enthalten grundlegende Informationen über den Constraint.
        """
        self.add_metadata('constraint_name', self.constraint_name)
        self.add_metadata('variables_count', len(self._constraint_vars))
        self.add_metadata('is_setup_complete', True)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Gibt eine Zusammenfassung dieses Constraints zurück.
        
        Returns:
            Dictionary mit Constraint-Informationen
        """
        return {
            'constraint_name': self.constraint_name,
            'is_setup_complete': self.is_setup_complete(),
            'variables_count': len(self._constraint_vars),
            'context_valid': self.validate_context(),
            'metadata': self.get_all_metadata()
        }
    
    def __str__(self) -> str:
        """String-Repräsentation des Constraints."""
        return f"{self.__class__.__name__}(name='{self.constraint_name}', vars={len(self._constraint_vars)})"
    
    def __repr__(self) -> str:
        """Debug-Repräsentation des Constraints."""
        return (f"{self.__class__.__name__}("
                f"constraint_name='{self.constraint_name}', "
                f"variables={len(self._constraint_vars)}, "
                f"setup_complete={self.is_setup_complete()})")


class ConstraintValidationError(Exception):
    """Exception für Constraint-Validierungsfehler."""
    
    def __init__(self, constraint_name: str, message: str):
        self.constraint_name = constraint_name
        self.message = message
        super().__init__(f"Constraint '{constraint_name}': {message}")


class ConstraintSetupError(Exception):
    """Exception für Constraint-Setup-Fehler."""
    
    def __init__(self, constraint_name: str, message: str, cause: Optional[Exception] = None):
        self.constraint_name = constraint_name
        self.message = message
        self.cause = cause
        super().__init__(f"Failed to setup constraint '{constraint_name}': {message}")
