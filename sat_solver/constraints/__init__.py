# sat_solver/constraints/__init__.py
"""
Constraint-Klassen für den SAT-Solver.

Dieses Modul enthält alle Constraint-Implementierungen als Klassen,
die über die ConstraintRegistry verwaltet werden.
"""

from sat_solver.constraints.base import ConstraintBase
from sat_solver.constraints.registry import ConstraintRegistry
from sat_solver.constraints.location_prefs import LocationPrefsConstraint
from sat_solver.constraints.employee_availability import EmployeeAvailabilityConstraint
from sat_solver.constraints.event_groups_activity import EventGroupsActivityConstraint
from sat_solver.constraints.avail_day_groups_activity import AvailDayGroupsActivityConstraint
from sat_solver.constraints.num_shifts_in_avail_day_groups import NumShiftsInAvailDayGroupsConstraint
from sat_solver.constraints.partner_location_prefs import PartnerLocationPrefsConstraint
from sat_solver.constraints.weights_in_avail_day_groups import WeightsInAvailDayGroupsConstraint
from sat_solver.constraints.weights_in_event_groups import WeightsInEventGroupsConstraint
from sat_solver.constraints.skills import SkillsConstraint
from sat_solver.constraints.unsigned_shifts import UnsignedShiftsConstraint
from sat_solver.constraints.required_avail_day_groups import RequiredAvailDayGroupsConstraint
from sat_solver.constraints.different_casts_same_day import DifferentCastsSameDayConstraint
from sat_solver.constraints.rel_shift_deviations import RelShiftDeviationsConstraint
from sat_solver.constraints.cast_rules import CastRulesConstraint
# Neue aufgeteilte Constraints
from sat_solver.constraints.fixed_cast_conflicts import FixedCastConflictsConstraint
from sat_solver.constraints.prefer_fixed_cast import PreferFixedCastConstraint
# Deprecated - für Rückwärtskompatibilität
from sat_solver.constraints.fixed_cast import FixedCastConstraint
from sat_solver.constraints.helpers import (
    check_actor_location_prefs_fits_event,
    check_time_span_avail_day_fits_event,
)

__all__ = [
    'ConstraintBase',
    'ConstraintRegistry',
    'LocationPrefsConstraint',
    'EmployeeAvailabilityConstraint',
    'EventGroupsActivityConstraint',
    'AvailDayGroupsActivityConstraint',
    'NumShiftsInAvailDayGroupsConstraint',
    'PartnerLocationPrefsConstraint',
    'WeightsInAvailDayGroupsConstraint',
    'WeightsInEventGroupsConstraint',
    'SkillsConstraint',
    'UnsignedShiftsConstraint',
    'RequiredAvailDayGroupsConstraint',
    'DifferentCastsSameDayConstraint',
    'RelShiftDeviationsConstraint',
    'CastRulesConstraint',
    # Neue aufgeteilte Constraints
    'FixedCastConflictsConstraint',
    'PreferFixedCastConstraint',
    # Deprecated
    'FixedCastConstraint',
    # Helper-Funktionen
    'check_actor_location_prefs_fits_event',
    'check_time_span_avail_day_fits_event',
]
