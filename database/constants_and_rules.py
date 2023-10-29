# weights for sat-solver objective:
from uuid import UUID

WEIGHT_UNASSIGNED_SHIFTS = 100_000
WEIGHT_SUM_SQUARED_SHIFT_DEVIATIONS = 0.001
WEIGHT_CONSTRAINTS_WEIGHTS_IN_AVAIL_DAY_GROUPS = 1
WEIGHT_CONSTRAINTS_WEIGHTS_IN_EVENT_GROUPS = 1


# cast_rules
def same_cast(cast_1: set[UUID], cast_2: set[UUID]) -> bool:
    """Cast im direkt nachfolgenden Event der Gruppe (cast_2) muss (zu cast_1) gleich sein"""
    return cast_1 == cast_2


def different_cast(cast_1: set[UUID], cast_2: set[UUID]) -> bool:
    """Cast im direkt nachfolgenden Event der Gruppe (cast_2) muss (zu cast_1) unterschiedlich sein"""
    return not cast_1 | cast_2


def any_cast(cast_1: set[UUID], cast_2: set[UUID]) -> bool:
    """Cast im direkt nachfolgenden Event der Gruppe (cast_2) muss (zu cast_1) kann beliebig sein"""
    return True


CAST_RULES = {'~': same_cast, '-': different_cast, '*': any_cast}
