import dataclasses
from ortools.sat.python.cp_model import IntVar


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
