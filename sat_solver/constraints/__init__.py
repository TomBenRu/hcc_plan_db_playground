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

# Noch nicht implementierte Constraints (werden nach und nach hinzugefügt)
# from .weights import WeightsConstraint
# from .partner_prefs import PartnerLocationPrefsConstraint
# from .cast_rules import CastRulesConstraint
# from .fixed_cast import FixedCastConstraint
# from .skills import SkillsConstraint

__all__ = [
    'AbstractConstraint',
    'ConstraintFactory',
    'EmployeeAvailabilityConstraint',
    'EventGroupsConstraint',
    'AvailDayGroupsConstraint', 
    'LocationPrefsConstraint',
    'ShiftsConstraint',
    # Werden später hinzugefügt:
    # 'WeightsConstraint',
    # 'PartnerLocationPrefsConstraint',
    # 'CastRulesConstraint',
    # 'FixedCastConstraint',
    # 'SkillsConstraint'
]
