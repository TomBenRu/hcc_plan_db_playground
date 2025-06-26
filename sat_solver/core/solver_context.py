"""
SolverContext - Zentraler Kontext für alle Solver-Operationen

Diese Klasse kapselt alle geteilten Daten und Zustand des Solvers,
um Parameter-Weitergabe zu reduzieren und die Architektur zu verbessern.
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
from dataclasses import dataclass, field

from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

from .entities import Entities
from .solver_config import SolverConfig


@dataclass
class SolverContext:
    """
    Zentraler Kontext für alle Solver-Operationen.
    
    Diese Klasse ersetzt die vielen Parameter, die zwischen Funktionen
    weitergegeben wurden, und bietet eine einheitliche Schnittstelle
    für alle Solver-Komponenten.
    """
    
    # Kern-Komponenten
    entities: Entities
    model: cp_model.CpModel
    config: SolverConfig
    
    # Plan Period ID für Datenbankzugriffe
    plan_period_id: UUID
    
    # Constraint-Results: Speichert Variablen nach Constraint-Namen
    constraint_vars: Dict[str, List[IntVar]] = field(default_factory=dict)
    
    # Metadaten und Statistiken
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_constraint_vars(self, constraint_name: str, vars: List[IntVar]) -> None:
        """
        Fügt Constraint-Variablen zu einem benannten Constraint hinzu.
        
        Args:
            constraint_name: Name des Constraints (z.B. "location_prefs")
            vars: Liste der IntVar-Objekte für diesen Constraint
        """
        if constraint_name not in self.constraint_vars:
            self.constraint_vars[constraint_name] = []
        self.constraint_vars[constraint_name].extend(vars)
    
    def get_constraint_vars(self, constraint_name: str) -> List[IntVar]:
        """
        Holt alle Variablen für einen benannten Constraint.
        
        Args:
            constraint_name: Name des Constraints
            
        Returns:
            Liste der IntVar-Objekte für diesen Constraint
        """
        return self.constraint_vars.get(constraint_name, [])
    
    def has_constraint_vars(self, constraint_name: str) -> bool:
        """
        Prüft, ob Variablen für einen Constraint existieren.
        
        Args:
            constraint_name: Name des Constraints
            
        Returns:
            True wenn Variablen existieren, False sonst
        """
        return constraint_name in self.constraint_vars and bool(self.constraint_vars[constraint_name])
    
    def clear_constraint_vars(self, constraint_name: Optional[str] = None) -> None:
        """
        Löscht Constraint-Variablen.
        
        Args:
            constraint_name: Name des zu löschenden Constraints. 
                           Wenn None, werden alle gelöscht.
        """
        if constraint_name is None:
            self.constraint_vars.clear()
        elif constraint_name in self.constraint_vars:
            del self.constraint_vars[constraint_name]
    
    def get_all_constraint_names(self) -> List[str]:
        """
        Gibt alle Namen der registrierten Constraints zurück.
        
        Returns:
            Liste aller Constraint-Namen
        """
        return list(self.constraint_vars.keys())
    
    def add_metadata(self, key: str, value: Any) -> None:
        """
        Fügt Metadaten zum Kontext hinzu.
        
        Args:
            key: Metadaten-Schlüssel
            value: Metadaten-Wert
        """
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Holt Metadaten aus dem Kontext.
        
        Args:
            key: Metadaten-Schlüssel
            default: Rückgabewert wenn Schlüssel nicht existiert
            
        Returns:
            Metadaten-Wert oder default
        """
        return self.metadata.get(key, default)
    
    def is_valid(self) -> bool:
        """
        Prüft, ob der Kontext valide und einsatzbereit ist.
        
        Returns:
            True wenn der Kontext valide ist, False sonst
        """
        return (
            self.entities is not None and
            self.entities.is_initialized() and
            self.model is not None and
            self.config is not None and
            self.plan_period_id is not None
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Gibt eine Zusammenfassung des Kontext-Zustands zurück.
        
        Returns:
            Dictionary mit Zusammenfassungsdaten
        """
        return {
            'plan_period_id': str(self.plan_period_id),
            'entities_summary': self.entities.get_summary() if self.entities else {},
            'model_variables': self.model.NumVariables() if self.model else 0,
            'model_constraints': self.model.NumConstraints() if self.model else 0,
            'constraint_types': len(self.constraint_vars),
            'total_constraint_vars': sum(len(vars) for vars in self.constraint_vars.values()),
            'metadata_keys': list(self.metadata.keys()),
            'is_valid': self.is_valid()
        }
    
    def reset(self) -> None:
        """
        Setzt den Kontext zurück für eine neue Solver-Session.
        
        Behält Konfiguration und Plan Period ID bei, aber löscht
        alle dynamischen Daten.
        """
        if self.entities:
            self.entities.reset()
        self.constraint_vars.clear()
        self.metadata.clear()
        # model und config werden nicht zurückgesetzt
