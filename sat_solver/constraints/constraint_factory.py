"""
ConstraintFactory - Factory für die Erstellung und Verwaltung aller Constraints

Diese Factory-Klasse orchestriert die Erstellung aller Constraint-Objekte
und bietet eine zentrale Schnittstelle für Constraint-Management.
"""

from typing import List, Dict, Type, Optional, Set
import logging

from sat_solver.core.solver_context import SolverContext
from .base import AbstractConstraint, ConstraintSetupError

# Import aller Constraint-Implementierungen
from .availability import EmployeeAvailabilityConstraint
from .event_groups import EventGroupsConstraint
from .avail_day_groups import AvailDayGroupsConstraint
from .location_prefs import LocationPrefsConstraint
from .shifts import ShiftsConstraint
from .weights import WeightsConstraint
from .partner_prefs import PartnerLocationPrefsConstraint
from .skills import SkillsConstraint
from .fixed_cast import FixedCastConstraint
from .cast_rules import CastRulesConstraint


logger = logging.getLogger(__name__)


class ConstraintFactory:
    """
    Factory für die Erstellung und Verwaltung aller Constraint-Implementierungen.
    
    Diese Klasse bietet eine zentrale Schnittstelle für:
    - Automatische Erkennung verfügbarer Constraints
    - Erstellung von Constraint-Instanzen
    - Batch-Setup aller Constraints
    - Dependency-Management zwischen Constraints
    """
    
    # Registry aller verfügbaren Constraint-Klassen
    # Diese Liste wird automatisch basierend auf verfügbaren Imports gefüllt
    AVAILABLE_CONSTRAINT_CLASSES: List[Type[AbstractConstraint]] = []
    
    @classmethod
    def _register_available_constraints(cls) -> None:
        """Registriert alle verfügbaren Constraint-Klassen."""
        cls.AVAILABLE_CONSTRAINT_CLASSES.clear()
        
        # Alle Constraint-Klassen registrieren
        # Reihenfolge ist wichtig: Basis-Constraints zuerst, dann abhängige
        constraint_classes = [
            EmployeeAvailabilityConstraint,  # ✅ Basis-Verfügbarkeit
            EventGroupsConstraint,           # ✅ Event-Group-Aktivität  
            AvailDayGroupsConstraint,        # ✅ AvailDay-Group-Management
            LocationPrefsConstraint,         # ✅ Standort-Präferenzen
            ShiftsConstraint,               # ✅ Schicht-Management
            WeightsConstraint,              # ✅ Gewichtungen (Event/AvailDay)
            PartnerLocationPrefsConstraint, # ✅ Partner-Standort-Präferenzen
            SkillsConstraint,               # ✅ Fertigkeiten-Matching
            FixedCastConstraint,            # ✅ Feste Besetzungen
            CastRulesConstraint,            # ✅ Besetzungsregeln
        ]
        
        for constraint_class in constraint_classes:
            if constraint_class is not None:
                cls.AVAILABLE_CONSTRAINT_CLASSES.append(constraint_class)
        
        logger.info(f"Registered {len(cls.AVAILABLE_CONSTRAINT_CLASSES)} constraint classes")
    
    @classmethod
    def get_available_constraint_names(cls) -> List[str]:
        """
        Gibt die Namen aller verfügbaren Constraints zurück.
        
        Returns:
            Liste der Constraint-Namen
        """
        if not cls.AVAILABLE_CONSTRAINT_CLASSES:
            cls._register_available_constraints()
        
        # Temporäre Instanzen erstellen um constraint_name zu bekommen
        # (Das ist nicht ideal, aber notwendig da constraint_name eine abstrakte Property ist)
        names = []
        for constraint_class in cls.AVAILABLE_CONSTRAINT_CLASSES:
            try:
                # Minimaler dummy context für Namen-Extraktion
                dummy_context = type('DummyContext', (), {
                    'model': None, 'entities': None, 'config': None
                })()
                temp_instance = constraint_class(dummy_context)
                names.append(temp_instance.constraint_name)
            except Exception as e:
                logger.warning(f"Could not get constraint name for {constraint_class.__name__}: {e}")
                names.append(constraint_class.__name__.lower())
        
        return names
    
    @classmethod
    def create_all_constraints(cls, context: SolverContext) -> List[AbstractConstraint]:
        """
        Erstellt Instanzen aller verfügbaren Constraints.
        
        Args:
            context: Der SolverContext für alle Constraints
            
        Returns:
            Liste aller erstellten Constraint-Instanzen
        """
        if not cls.AVAILABLE_CONSTRAINT_CLASSES:
            cls._register_available_constraints()
        
        constraints = []
        failed_constraints = []
        
        for constraint_class in cls.AVAILABLE_CONSTRAINT_CLASSES:
            try:
                constraint = constraint_class(context)
                if constraint.validate_context():
                    constraints.append(constraint)
                    logger.debug(f"Created constraint: {constraint.constraint_name}")
                else:
                    logger.warning(f"Context validation failed for {constraint_class.__name__}")
                    failed_constraints.append(constraint_class.__name__)
            except Exception as e:
                logger.error(f"Failed to create constraint {constraint_class.__name__}: {e}")
                failed_constraints.append(constraint_class.__name__)
        
        if failed_constraints:
            logger.warning(f"Failed to create {len(failed_constraints)} constraints: {failed_constraints}")
        
        logger.info(f"Successfully created {len(constraints)} constraints")
        return constraints
    
    @classmethod
    def create_specific_constraints(cls, context: SolverContext, 
                                  constraint_names: List[str]) -> List[AbstractConstraint]:
        """
        Erstellt nur spezifische Constraints basierend auf Namen.
        
        Args:
            context: Der SolverContext für die Constraints
            constraint_names: Liste der gewünschten Constraint-Namen
            
        Returns:
            Liste der erstellten Constraint-Instanzen
        """
        if not cls.AVAILABLE_CONSTRAINT_CLASSES:
            cls._register_available_constraints()
        
        constraints = []
        available_names = set(cls.get_available_constraint_names())
        requested_names = set(constraint_names)
        
        # Prüfe welche Namen nicht verfügbar sind
        unavailable = requested_names - available_names
        if unavailable:
            logger.warning(f"Requested constraints not available: {unavailable}")
        
        # Erstelle verfügbare Constraints
        for constraint_class in cls.AVAILABLE_CONSTRAINT_CLASSES:
            try:
                temp_constraint = constraint_class(context)
                if temp_constraint.constraint_name in requested_names:
                    if temp_constraint.validate_context():
                        constraints.append(temp_constraint)
                        logger.debug(f"Created specific constraint: {temp_constraint.constraint_name}")
                    else:
                        logger.warning(f"Context validation failed for {constraint_class.__name__}")
            except Exception as e:
                logger.error(f"Failed to create constraint {constraint_class.__name__}: {e}")
        
        logger.info(f"Created {len(constraints)} specific constraints")
        return constraints
    
    @classmethod
    def setup_all_constraints(cls, constraints: List[AbstractConstraint]) -> Dict[str, bool]:
        """
        Führt setup() für alle Constraints durch.
        
        Args:
            constraints: Liste der Constraint-Instanzen
            
        Returns:
            Dictionary mit Constraint-Namen und Setup-Status (True=Erfolg, False=Fehler)
        """
        setup_results = {}
        failed_setups = []
        
        for constraint in constraints:
            try:
                constraint.setup()
                setup_results[constraint.constraint_name] = True
                logger.debug(f"Successfully setup constraint: {constraint.constraint_name}")
            except Exception as e:
                setup_results[constraint.constraint_name] = False
                failed_setups.append((constraint.constraint_name, str(e)))
                logger.error(f"Failed to setup constraint {constraint.constraint_name}: {e}")
        
        success_count = sum(setup_results.values())
        total_count = len(constraints)
        
        if failed_setups:
            logger.warning(f"Failed to setup {len(failed_setups)} constraints: {[name for name, _ in failed_setups]}")
        
        logger.info(f"Successfully setup {success_count}/{total_count} constraints")
        return setup_results
    
    @classmethod
    def create_and_setup_all(cls, context: SolverContext) -> tuple[List[AbstractConstraint], Dict[str, bool]]:
        """
        Erstellt und richtet alle verfügbaren Constraints ein.
        
        Dies ist eine Convenience-Methode, die create_all_constraints()
        und setup_all_constraints() kombiniert.
        
        Args:
            context: Der SolverContext für alle Constraints
            
        Returns:
            Tupel aus (constraints_list, setup_results_dict)
        """
        logger.info("Starting creation and setup of all constraints")
        
        # Erstelle alle Constraints
        constraints = cls.create_all_constraints(context)
        
        # Setup alle Constraints
        setup_results = cls.setup_all_constraints(constraints)
        
        # Filtere erfolgreich eingerichtete Constraints
        successful_constraints = [
            c for c in constraints 
            if setup_results.get(c.constraint_name, False)
        ]
        
        logger.info(f"Completed constraint creation and setup: {len(successful_constraints)} ready")
        return successful_constraints, setup_results
    
    @classmethod
    def get_constraints_summary(cls, constraints: List[AbstractConstraint]) -> Dict[str, any]:
        """
        Erstellt eine Zusammenfassung aller Constraints.
        
        Args:
            constraints: Liste der Constraint-Instanzen
            
        Returns:
            Dictionary mit Zusammenfassungsdaten
        """
        summary = {
            'total_constraints': len(constraints),
            'setup_complete': sum(1 for c in constraints if c.is_setup_complete()),
            'total_variables': sum(len(c.get_constraint_variables()) for c in constraints),
            'constraint_details': []
        }
        
        for constraint in constraints:
            summary['constraint_details'].append(constraint.get_summary())
        
        return summary


# Automatische Registrierung beim Modul-Import
ConstraintFactory._register_available_constraints()
