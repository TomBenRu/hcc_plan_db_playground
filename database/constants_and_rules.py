# weights for sat-solver objective:
from typing import Callable
from uuid import UUID

WEIGHT_UNASSIGNED_SHIFTS = 100_000
WEIGHT_SUM_SQUARED_SHIFT_DEVIATIONS = 0.005
WEIGHT_CONSTRAINTS_WEIGHTS_IN_AVAIL_DAY_GROUPS = 1
WEIGHT_CONSTRAINTS_WEIGHTS_IN_EVENT_GROUPS = 1
WEIGHT_VARS_LOCATION_PREFS = {0: 100_000_000_000_000, 0.5: 10, 1: 0, 1.5: -10, 2: -20}
WEIGHT_CONSTRAINTS_LOCATION_PREFS = 0.001
WEIGHT_VARS_PARTNER_LOC_PREFS = {0: 100_000_000_000_000, 0.5: 10, 1: 0, 1.5: -10, 2: -20}
TRANSPOSE_FACTORS_PARTNER_LOC_PREFS = {}  # todo: bei mehr als 2 Mitarbeitern werden die Weight-Vars angepasst.
WEIGHT_CONSTRAINTS_PARTNER_LOC_PREFS = 0.001
WEIGHT_CONSTRAINTS_FIXED_CASTS_CONFLICTS = 1_000_000_000


# cast_rules
def same_cast(cast_1: set[UUID], cast_2: set[UUID]) -> bool:
    """Cast im direkt nachfolgenden Event der Gruppe (cast_2) muss (zu cast_1) gleich sein"""
    return cast_1 == cast_2


def different_cast(cast_1: set[UUID], cast_2: set[UUID]) -> bool:
    """Cast im direkt nachfolgenden Event der Gruppe (cast_2) muss (zu cast_1) unterschiedlich sein"""
    return not cast_1 & cast_2


def any_cast(cast_1: set[UUID], cast_2: set[UUID]) -> bool:
    """Cast im direkt nachfolgenden Event der Gruppe (cast_2) muss (zu cast_1) kann beliebig sein"""
    return True


CAST_RULES: dict[str, Callable[[set[UUID], set[UUID]], bool]] = {'~': same_cast, '-': different_cast, '*': any_cast}
