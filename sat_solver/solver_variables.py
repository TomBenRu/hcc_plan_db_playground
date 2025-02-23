import dataclasses
from ortools.sat.python.cp_model import IntVar


@dataclasses.dataclass
class CastRules:
    applied_shifts_1: list[list[IntVar]] = dataclasses.field(default_factory=list)
    applied_shifts_2: list[list[IntVar]] = dataclasses.field(default_factory=list)
    is_equal_1: list[IntVar] = dataclasses.field(default_factory=list)
    is_equal_2: list[IntVar] = dataclasses.field(default_factory=list)
    is_equal: list[IntVar] = dataclasses.field(default_factory=list)
    is_unequal: list[IntVar] = dataclasses.field(default_factory=list)
    sum_of_applied_shifts: list[IntVar] = dataclasses.field(default_factory=list)

    def reset_fields(self):
        self.applied_shifts_1 = []
        self.applied_shifts_2 = []
        self.is_unequal = []
        self.sum_of_applied_shifts = []


cast_rules = CastRules()
