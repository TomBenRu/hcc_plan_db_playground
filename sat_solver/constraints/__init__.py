"""
SAT-Solver Constraints Module

Dieses Modul enthält alle Constraint-Implementierungen:
- AbstractConstraint: Basisklasse für alle Constraints
- Spezifische Constraint-Klassen für verschiedene Problemaspekte
- ConstraintFactory: Factory für Constraint-Erstellung
"""

from .base import AbstractConstraint
from .constraint_factory import ConstraintFactory

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

__all__ = [
    'AbstractConstraint',
    'ConstraintFactory',
    'EmployeeAvailabilityConstraint',
    'EventGroupsConstraint',
    'AvailDayGroupsConstraint', 
    'LocationPrefsConstraint',
    'ShiftsConstraint',
    'WeightsConstraint',
    'PartnerLocationPrefsConstraint',
    'SkillsConstraint',
    'FixedCastConstraint',
    'CastRulesConstraint'
]
