"""
RelShiftDeviationsConstraint - Soft Constraint für relative Schichtabweichungen.

Berechnet die Fairness der Schichtverteilung zwischen Mitarbeitern.
"""
from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase


class RelShiftDeviationsConstraint(ConstraintBase):
    """
    Soft Constraint für relative Schichtabweichungen (Fairness).
    
    Berechnet für jeden Mitarbeiter die Abweichung zwischen gewünschten
    und tatsächlich zugewiesenen Schichten und minimiert die Varianz
    dieser Abweichungen.
    
    Logik:
    - Für jeden ActorPlanPeriod wird die relative Abweichung berechnet:
      (zugewiesene Schichten - gewünschte Schichten) / gewünschte Schichten
    - Die quadrierten Abweichungen vom Durchschnitt werden summiert
    - Diese Summe wird als Penalty minimiert
    
    Attributes:
        sum_assigned_shifts: Dict mit Summe der zugewiesenen Schichten pro APP
        sum_squared_deviations: Variable für die Summe der quadrierten Abweichungen
    """
    
    name = "rel_shift_deviations"
    weight_attribute = "sum_deviations"
    
    def __init__(self):
        super().__init__()
        self.sum_assigned_shifts: dict[UUID, IntVar] = {}
        self.sum_squared_deviations: IntVar | None = None
    
    def apply(self) -> None:
        """
        Wendet das Relative Shift Deviations Constraint an.
        
        Berechnet die Fairness-Metrik und speichert die Penalty-Variable.
        """
        # Erstelle Variablen für zugewiesene Schichten pro ActorPlanPeriod
        self._create_sum_assigned_shifts_vars()
        
        # Erstelle Variablen für relative Abweichungen
        relative_shift_deviations = self._create_relative_shift_deviation_vars()
        
        # Berechne durchschnittliche relative Abweichung
        average_relative_shift_deviation = self._calculate_average_deviation()
        
        # Berechne quadrierte Abweichungen vom Durchschnitt
        squared_deviations = self._calculate_squared_deviations(
            relative_shift_deviations, 
            average_relative_shift_deviation
        )
        
        # Erstelle Summe der quadrierten Abweichungen als Penalty
        self.sum_squared_deviations = self.model.NewIntVar(
            lb=0, ub=1_000_000_000, name='sum_squared_deviations'
        )
        self.model.AddAbsEquality(
            self.sum_squared_deviations, 
            sum(squared_deviations.values())
        )
        
        # Penalty-Variable hinzufügen
        self.penalty_vars.append(self.sum_squared_deviations)
    
    def _create_sum_assigned_shifts_vars(self) -> None:
        """
        Erstellt IntVar für die Summe der zugewiesenen Schichten pro ActorPlanPeriod.
        """
        self.sum_assigned_shifts = {
            app.id: self.model.NewIntVar(
                lb=0, ub=1000, 
                name=f'sum_assigned_shifts {app.person.f_name}'
            )
            for app in self.entities.actor_plan_periods.values()
        }
    
    def _create_relative_shift_deviation_vars(self) -> dict[UUID, IntVar]:
        """
        Erstellt Variablen für relative Schichtabweichungen und fügt Constraints hinzu.
        
        Returns:
            Dict mit relativen Abweichungs-Variablen pro ActorPlanPeriod
        """
        relative_shift_deviations = {
            app.id: self.model.NewIntVar(
                lb=-len(self.entities.event_groups_with_event) * 1_000_000,
                ub=len(self.entities.event_groups_with_event) * 1_000_000,
                name=f'relative_shift_deviation_{app.person.f_name}'
            )
            for app in self.entities.actor_plan_periods.values()
        }
        
        # Constraints für jeden ActorPlanPeriod hinzufügen
        for app in self.entities.actor_plan_periods.values():
            assigned_shifts_of_app = sum(
                sum(
                    self.entities.shift_vars[(adg_id, evg_id)]
                    for evg_id in self.entities.event_groups_with_event
                )
                for adg_id, adg in self.entities.avail_day_groups_with_avail_day.items()
                if adg.avail_day.actor_plan_period.id == app.id
            )
            
            self.model.AddAbsEquality(
                self.sum_assigned_shifts[app.id], 
                assigned_shifts_of_app
            )
            
            shift_deviation = self.model.new_int_var(
                -1000, 1000, 
                f'abs_shirt_deviation_{app.person.f_name}'
            )
            self.model.Add(
                shift_deviation == assigned_shifts_of_app - int(app.requested_assignments)
            )
            
            if app.requested_assignments < 0:
                print(f'{app.requested_assignments=}')
            
            self.model.AddDivisionEquality(
                relative_shift_deviations[app.id],
                shift_deviation * 1_000,
                int(app.requested_assignments * 10) if app.requested_assignments else 1
            )
        
        return relative_shift_deviations
    
    def _calculate_average_deviation(self) -> IntVar:
        """
        Berechnet die durchschnittliche relative Abweichung.
        
        Returns:
            IntVar für die durchschnittliche relative Abweichung
        """
        sum_requested_assignments = (
            sum(app.requested_assignments for app in self.entities.actor_plan_periods.values()) 
            or 0.1
        )
        
        # Summe aller zugewiesenen Schichten
        sum_assigned_shifts_sum = self.model.NewIntVar(0, 10000, "sum_assigned_shifts_sum")
        self.model.Add(sum_assigned_shifts_sum == sum(self.sum_assigned_shifts.values()))
        
        # Differenz-Term
        diff = self.model.NewIntVar(-10000, 10000, "difference_term")
        self.model.Add(diff == sum_assigned_shifts_sum - int(sum_requested_assignments))
        
        # Skalierte Differenz
        scaled_diff = self.model.NewIntVar(-10_000_000, 10_000_000, "scaled_difference")
        self.model.AddMultiplicationEquality(scaled_diff, [diff, 1000])
        
        # Durchschnittliche relative Abweichung
        average_relative_shift_deviation = self.model.NewIntVar(
            -10_000_000, 10_000_000, 
            "average_relative_shift_deviation"
        )
        self.model.AddDivisionEquality(
            average_relative_shift_deviation, 
            scaled_diff, 
            int(sum_requested_assignments) * 10
        )
        
        return average_relative_shift_deviation
    
    def _calculate_squared_deviations(
        self, 
        relative_shift_deviations: dict[UUID, IntVar],
        average_relative_shift_deviation: IntVar
    ) -> dict[UUID, IntVar]:
        """
        Berechnet die quadrierten Abweichungen vom Durchschnitt.
        
        Args:
            relative_shift_deviations: Dict mit relativen Abweichungen pro APP
            average_relative_shift_deviation: Durchschnittliche Abweichung
            
        Returns:
            Dict mit quadrierten Abweichungen pro ActorPlanPeriod
        """
        squared_deviations = {
            app.id: self.model.NewIntVar(
                lb=0,
                ub=(len(self.entities.event_groups_with_event) * 1_000_000) ** 2,
                name=f'squared_deviation_{app.person.f_name}'
            )
            for app in self.entities.actor_plan_periods.values()
        }
        
        for app in self.entities.actor_plan_periods.values():
            dif_average = self.model.NewIntVar(
                lb=0, ub=1_000_000, 
                name=f'dif_average__relative_shift_deviation {app.id}'
            )
            self.model.AddAbsEquality(
                dif_average,
                relative_shift_deviations[app.id] - average_relative_shift_deviation
            )
            
            self.model.AddMultiplicationEquality(
                squared_deviations[app.id],
                [dif_average, dif_average]
            )
        
        return squared_deviations
    
    def get_results(self) -> tuple[dict[UUID, IntVar], IntVar]:
        """
        Gibt die Ergebnis-Variablen zurück (Kompatibilität mit alter API).
        
        Returns:
            Tuple von (sum_assigned_shifts dict, sum_squared_deviations var)
        """
        return self.sum_assigned_shifts, self.sum_squared_deviations
