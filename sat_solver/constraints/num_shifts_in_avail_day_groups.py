"""
NumShiftsInAvailDayGroupsConstraint - Hard Constraint für Schicht-Verfügbarkeitsgruppen-Verknüpfung.

Stellt sicher, dass Schichten nur aktiv sein können, wenn ihre zugehörige
Verfügbarkeitstag-Gruppe aktiv ist.
"""
from sat_solver.constraints.base import ConstraintBase


class NumShiftsInAvailDayGroupsConstraint(ConstraintBase):
    """
    Hard Constraint: Verknüpfung von Schichten mit Verfügbarkeitstag-Gruppen.
    
    Wenn die BoolVar einer avail_day_group aufgrund von Einschränkungen durch
    nr_avail_day_groups auf False gesetzt ist (durch AvailDayGroupsActivityConstraint),
    müssen auch die zugehörigen BoolVars der shifts auf False gesetzt sein.
    
    Technische Umsetzung:
    - Für jede shift_var wird geprüft: shift_var * NOT(avail_day_group_var) == 0
    - Das bedeutet: Wenn avail_day_group_var == 0, dann muss shift_var == 0
    - AddMultiplicationEquality(0, [shift_var, adg_var.Not()]) erzwingt dies
    
    Dies ist ein **Hard Constraint** ohne Penalty-Variablen.
    """
    
    name = "num_shifts_in_avail_day_groups"
    weight_attribute = ""  # Hard Constraint, kein Weight benötigt
    
    def apply(self) -> None:
        """
        Wendet das NumShiftsInAvailDayGroups Constraint an.
        
        Für jede Schicht-Variable wird ein Constraint hinzugefügt, das
        sicherstellt, dass die Schicht nur aktiv sein kann, wenn die
        zugehörige Avail-Day-Group aktiv ist.
        """
        for (adg_id, event_group_id), shift_var in self.entities.shift_vars.items():
            # shift_var * NOT(adg_var) == 0
            # => Wenn adg_var == 0, dann muss shift_var == 0
            self.model.AddMultiplicationEquality(
                0, 
                [shift_var, self.entities.avail_day_group_vars[adg_id].Not()]
            )
