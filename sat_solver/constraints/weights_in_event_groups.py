"""
WeightsInEventGroupsConstraint - Soft Constraint für Gewichtungen in Event-Gruppen.

Bevorzugt Child-Event-Groups mit höherer Gewichtung.
"""
from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase


class WeightsInEventGroupsConstraint(ConstraintBase):
    """
    Soft Constraint für Gewichtungen in Event-Gruppen.
    
    Fügt Constraints hinzu, um sicherzustellen, dass die Child-Event-Groups 
    mit den höheren Gewichtungen bevorzugt werden. Die Werte von weight_vars 
    werden im Solver minimiert.
    
    Bei tiefer geschachtelten Event-Groups werden die Parent-Groups bevorzugt,
    deren ausgewählte Children ein insgesamt höheres weight haben, wenn die 
    Parent-Groups gleiches weight haben.
    """
    
    name = "weights_in_event_groups"
    weight_attribute = "constraints_weights_in_event_groups"
    
    def apply(self) -> None:
        """
        Wendet das WeightsInEventGroups Constraint an.
        """
        self._multiplier_level = (
            self.config.constraints_multipliers.group_depth_weights_event_groups
        )
        self._multiplier_weights = (
            self.config.constraints_multipliers.sliders_weights_event_groups
        )
        
        # Finde Root-Event-Group
        root_event_group = next(eg for eg in self.entities.event_groups.values() if not eg.parent)
        
        # Berechne Weight-Variablen rekursiv
        start_depth = 1 if root_event_group.root_is_location_plan_period_master_group else 0
        self.penalty_vars = self._calculate_weight_vars_recursive(root_event_group, start_depth)
    
    def _calculate_weight_vars_recursive(self, event_group, depth: int) -> list[IntVar]:
        """
        Rekursive Berechnung der Weight-Variablen für eine Event-Group und ihre Kinder.
        
        Args:
            event_group: Die zu verarbeitende EventGroup
            depth: Aktuelle Tiefe im Baum
        
        Returns:
            Liste der erstellten IntVar-Penalty-Variablen
        """
        weight_vars: list[IntVar] = []
        
        # Prüfe ob diese Gruppe eine Auswahl erfordert (nr_of_active_children < len(children))
        if event_group.nr_of_active_children is not None:
            children = event_group.children
            if children and (event_group.nr_of_active_children < len(children)):
                for c in children:
                    weight_var = self._create_weight_var_for_child(c, depth)
                    weight_vars.append(weight_var)
        
        # Rekursiv für alle Kinder
        for c in event_group.children:
            weight_vars.extend(self._calculate_weight_vars_recursive(c, depth + 1))
        
        return weight_vars
    
    def _create_weight_var_for_child(self, child, depth: int) -> IntVar:
        """
        Erstellt eine Weight-Variable für ein Child-EventGroup.
        
        Args:
            child: Child-EventGroup
            depth: Aktuelle Tiefe
        
        Returns:
            IntVar für die Gewichtung
        """
        # Berechne Wertebereich
        min_val = min(self._multiplier_weights.values()) * max(self._multiplier_level.values())
        max_val = max(self._multiplier_weights.values()) * max(self._multiplier_level.values())
        
        # Erstelle Variablen-Name
        if child.event is None:
            name = f'Depth {depth}, no Event'
        else:
            name = (
                f'Depth {depth}, Event: {child.event.date:%d.%m.%y}, '
                f'{child.event.time_of_day.name}, '
                f'{child.event.location_plan_period.location_of_work.name}'
            )
        
        # Erstelle Variable
        weight_var = self.model.NewIntVar(min_val, max_val, name)
        
        # Berechne angepasstes Weight
        adjusted_weight = self._multiplier_weights[child.weight]
        event_group_var = self.entities.event_group_vars[child.event_group_id]
        level_multiplier = self._multiplier_level.get(depth, 1)
        
        # Setze Constraint
        self.model.Add(weight_var == event_group_var * adjusted_weight * level_multiplier)
        
        return weight_var
