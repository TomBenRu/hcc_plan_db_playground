import dataclasses
from typing import TYPE_CHECKING

# OR-Tools lazy import für Performance-Optimierung
# IntVar wird nur für Type Hints verwendet, daher conditional import
if TYPE_CHECKING:
    from ortools.sat.python.cp_model import IntVar
else:
    IntVar = "IntVar"  # String für Runtime, da nur für Type Hints benötigt


@dataclasses.dataclass
class CastRules:
    applied_shifts_1: list[list[IntVar]] = dataclasses.field(default_factory=list)
    applied_shifts_2: list[list[IntVar]] = dataclasses.field(default_factory=list)
    is_unequal: list[IntVar] = dataclasses.field(default_factory=list)

    def reset_fields(self):
        self.applied_shifts_1 = []
        self.applied_shifts_2 = []
        self.is_unequal = []


cast_rules = CastRules()
