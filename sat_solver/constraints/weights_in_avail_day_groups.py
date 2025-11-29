"""
WeightsInAvailDayGroupsConstraint - Soft Constraint für Gewichtungen in Verfügbarkeitstag-Gruppen.

Bevorzugt Child-Avail-Day-Groups mit höherer Gewichtung.
"""
from collections import defaultdict
from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase
from sat_solver.constraints.helpers import check_time_span_avail_day_fits_event


class WeightsInAvailDayGroupsConstraint(ConstraintBase):
    """
    Soft Constraint für Gewichtungen in Verfügbarkeitstag-Gruppen.
    
    Fügt Constraints hinzu, um sicherzustellen, dass Child-Avail-Day-Groups 
    mit höherer Gewichtung bevorzugt werden.
    
    Die justierten Gewichtungen werden jeweils zu den nächsten Child-Groups 
    durchgereicht, wo sie zu den Gewichtungen dieser Child-Groups addiert werden.
    Falls eine Child-Avail-Day-Group ein Avail-Day besitzt, wird diese kumulierte 
    Gewichtung als Constraint hinzugefügt.
    
    Um Verfälschungen durch Level-Verstärkungen zu vermeiden, wenn die Zweige 
    des Gruppenbaums unterschiedliche Tiefen haben, werden die Constraints stets 
    so berechnet, als befänden sich die Avail-Day-Groups mit Avail-Days auf der 
    untersten Stufe.
    """
    
    name = "weights_in_avail_day_groups"
    weight_attribute = "constraints_weights_in_avail_day_groups"
    
    def apply(self) -> None:
        """
        Wendet das WeightsInAvailDayGroups Constraint an.
        """
        self._multiplier_weights = (
            self.config.constraints_multipliers.sliders_weights_avail_day_groups
        )
        
        # Sammle shift_vars pro avail_day_group_id
        self._shift_vars_of_adg_ids: defaultdict[UUID, list] = defaultdict(list)
        for (adg_id, _), bool_var in self.entities.shift_vars.items():
            self._shift_vars_of_adg_ids[adg_id].append(bool_var)
        
        # Finde Root-Group und berechne max_depth
        root_group = next(eg for eg in self.entities.avail_day_groups.values() if not eg.parent)
        self._max_depth = (
            max(node.depth for node in self.entities.avail_day_groups.values())
            - (1 if root_group.group_is_actor_plan_period_master_group else 0)
        )
        
        # Berechne Weight-Variablen
        if root_group.group_is_actor_plan_period_master_group:
            self.penalty_vars = self._calculate_weight_vars_recursive(root_group)
        else:
            all_weight_vars = []
            for app_master_group in root_group.children:
                all_weight_vars.extend(self._calculate_weight_vars_recursive(app_master_group))
            self.penalty_vars = all_weight_vars
    
    def _calculate_weight_vars_recursive(self, group, cumulative_adjusted_weight: int = 0) -> list[IntVar]:
        """
        Rekursive Berechnung der Weight-Variablen für eine Gruppe und ihre Kinder.
        
        Args:
            group: Die zu verarbeitende AvailDayGroup
            cumulative_adjusted_weight: Kumulierte Gewichtung von übergeordneten Gruppen
        
        Returns:
            Liste der erstellten IntVar-Penalty-Variablen
        """
        weight_vars: list[IntVar] = []
        
        for c in group.children:
            if c.avail_day:
                # Prüfe ob ein Einsatz dieses AvailDays möglich ist
                if not self._has_possible_shifts(c):
                    continue
                
                # Erstelle Weight-Variable
                weight_var = self._create_weight_var_for_avail_day(c, group, cumulative_adjusted_weight)
                weight_vars.append(weight_var)
            else:
                # Rekursiv für Kinder ohne avail_day
                adjusted_weight = self._multiplier_weights[c.weight]
                weight_vars.extend(
                    self._calculate_weight_vars_recursive(
                        c, 
                        cumulative_adjusted_weight + adjusted_weight
                    )
                )
        
        return weight_vars
    
    def _has_possible_shifts(self, avail_day_group) -> bool:
        """
        Prüft ob ein AvailDay mögliche Shifts hat.
        
        Returns:
            True wenn mindestens ein Shift möglich ist
        """
        for (adg_id, evg_id), val in self.entities.shifts_exclusive.items():
            if adg_id != avail_day_group.avail_day_group_id:
                continue
            if not val:
                continue
            
            event = self.entities.event_groups_with_event[evg_id].event
            avail_day = self.entities.avail_day_groups_with_avail_day[adg_id].avail_day
            
            if check_time_span_avail_day_fits_event(event, avail_day):
                return True
        
        return False
    
    def _create_weight_var_for_avail_day(self, c, parent_group, cumulative_adjusted_weight: int) -> IntVar:
        """
        Erstellt eine Weight-Variable für einen AvailDay.
        
        Args:
            c: Child-AvailDayGroup mit avail_day
            parent_group: Übergeordnete Gruppe
            cumulative_adjusted_weight: Kumulierte Gewichtung
        
        Returns:
            IntVar für die Gewichtung
        """
        # Für fehlende Level wird jeweils die Gewichtung 1 (default: 0) gesetzt
        adjusted_weight = (
            (self._max_depth - c.depth) * self._multiplier_weights[1] 
            + self._multiplier_weights[c.weight]
        )
        
        # Erstelle Variable
        name = (
            f'Depth {parent_group.depth}, AvailDay: {c.avail_day.date:%d.%m.%y}, '
            f'{c.avail_day.time_of_day.name}, '
            f'{c.avail_day.actor_plan_period.person.f_name}'
        )
        weight_var = self.model.NewIntVar(-100, 100000, name)
        
        # Stelle fest, ob ein zugehöriges Event stattfindet
        adg_has_shifts = self.model.NewBoolVar('')
        self.model.Add(
            adg_has_shifts == sum(self._shift_vars_of_adg_ids[c.avail_day_group_id])
        )
        
        # Setze Constraint für weight_var
        self.model.Add(
            weight_var == (cumulative_adjusted_weight + adjusted_weight) * adg_has_shifts
        )
        
        return weight_var
