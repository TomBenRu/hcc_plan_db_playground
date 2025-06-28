"""
WeightsConstraint - Constraint für Gewichtungen in Event- und AvailDay-Groups

Dieser Constraint entspricht den Funktionen:
- add_constraints_weights_in_event_groups()
- add_constraints_weights_in_avail_day_groups()

Dies ist einer der komplexesten Constraints mit verschachtelter Gewichtungslogik.
"""

from typing import List, Dict
from collections import defaultdict

from ortools.sat.python.cp_model import IntVar

from .base import AbstractConstraint


class WeightsConstraint(AbstractConstraint):
    """
    Constraint für Gewichtungen in Event- und AvailDay-Groups.
    
    Dieser Constraint behandelt die komplexe Logik für:
    1. Gewichtungen in Event-Groups (mit Tiefe-Multiplikatoren)
    2. Gewichtungen in AvailDay-Groups (kumulative Gewichtung)
    
    Die Gewichtungen werden in der Zielfunktion minimiert, um bevorzugte
    Groups/Events zu favorisieren.
    
    Entspricht den ursprünglichen Funktionen:
    - add_constraints_weights_in_event_groups()
    - add_constraints_weights_in_avail_day_groups()
    """
    
    @property
    def constraint_name(self) -> str:
        """Name dieses Constraints."""
        return "weights"
    
    def create_variables(self) -> List[IntVar]:
        """
        Erstellt Gewichtungs-Variablen für Event- und AvailDay-Groups.
        
        Returns:
            Liste aller erstellten Gewichtungs-Variablen
        """
        all_weight_vars = []
        
        # 1. Event-Group Gewichtungs-Variablen
        event_weight_vars = self._create_event_group_weight_vars()
        all_weight_vars.extend(event_weight_vars)
        
        # 2. AvailDay-Group Gewichtungs-Variablen  
        avail_day_weight_vars = self._create_avail_day_group_weight_vars()
        all_weight_vars.extend(avail_day_weight_vars)
        
        # Speichere für späteren Zugriff
        self.add_metadata('event_weight_vars', event_weight_vars)
        self.add_metadata('avail_day_weight_vars', avail_day_weight_vars)
        self.add_metadata('total_weight_vars', len(all_weight_vars))
        
        return all_weight_vars
    
    def add_constraints(self) -> None:
        """
        Fügt Gewichtungs-Constraints hinzu.
        
        Die Hauptlogik ist bereits in create_variables() implementiert.
        Hier werden zusätzliche Validierungs-Constraints hinzugefügt.
        """
        constraints_added = 0
        
        # Zusätzliche Gewichtungs-Constraints können hier hinzugefügt werden
        # Zum Beispiel: Konsistenz-Checks, Boundaries, etc.
        
        self.add_metadata('additional_weight_constraints', constraints_added)
    
    def _create_event_group_weight_vars(self) -> List[IntVar]:
        """
        Erstellt Gewichtungs-Variablen für Event-Groups.
        
        Entspricht add_constraints_weights_in_event_groups().
        
        Returns:
            Liste der Event-Group Gewichtungs-Variablen
        """
        multiplier_level = self.config.constraint_multipliers.group_depth_weights_event_groups
        multiplier_weights = self.config.constraint_multipliers.sliders_weights_event_groups
        
        # Finde Root Event Group
        root_event_group = next(
            (eg for eg in self.entities.event_groups.values() if not eg.parent), 
            None
        )
        
        if not root_event_group:
            self.add_metadata('event_groups_error', 'No root event group found')
            return []
        
        # Bestimme Start-Tiefe basierend auf Root-Type
        start_depth = 1 if root_event_group.root_is_location_plan_period_master_group else 0
        
        return self._calculate_event_weight_vars_recursive(root_event_group, start_depth)
    
    def _calculate_event_weight_vars_recursive(self, event_group, depth: int) -> List[IntVar]:
        """
        Berechnet Event-Group Gewichtungs-Variablen rekursiv.
        
        Args:
            event_group: Die Event-Group
            depth: Aktuelle Tiefe in der Hierarchie
            
        Returns:
            Liste der Gewichtungs-Variablen
        """
        weight_vars = []
        multiplier_level = self.config.constraint_multipliers.group_depth_weights_event_groups
        multiplier_weights = self.config.constraint_multipliers.sliders_weights_event_groups
        
        if event_group.nr_of_active_children is not None:
            if (children := event_group.children) and (event_group.nr_of_active_children < len(children)):
                
                for child in children:
                    # Berechne angepasstes Gewicht
                    adjusted_weight = multiplier_weights[child.weight]
                    
                    # Erstelle Gewichtungs-Variable
                    if child.event is None:
                        var_name = f'Depth {depth}, no Event'
                    else:
                        var_name = (f'Depth {depth}, Event: {child.event.date:%d.%m.%y}, '
                                   f'{child.event.time_of_day.name}, '
                                   f'{child.event.location_plan_period.location_of_work.name}')
                    
                    weight_var = self.model.NewIntVar(
                        min(multiplier_weights.values()) * max(multiplier_level.values()),
                        max(multiplier_weights.values()) * max(multiplier_level.values()),
                        var_name
                    )
                    
                    weight_vars.append(weight_var)
                    
                    # Constraint für Gewichtungs-Variable
                    if child.event_group_id in self.entities.event_group_vars:
                        event_group_var = self.entities.event_group_vars[child.event_group_id]
                        level_multiplier = multiplier_level.get(depth, 1)
                        
                        self.model.Add(
                            weight_var == (event_group_var * adjusted_weight * level_multiplier)
                        )
        
        # Rekursive Bearbeitung der Children
        for child in event_group.children:
            weight_vars.extend(self._calculate_event_weight_vars_recursive(child, depth + 1))
        
        return weight_vars
    
    def _create_avail_day_group_weight_vars(self) -> List[IntVar]:
        """
        Erstellt Gewichtungs-Variablen für AvailDay-Groups.
        
        Entspricht add_constraints_weights_in_avail_day_groups().
        
        Returns:
            Liste der AvailDay-Group Gewichtungs-Variablen
        """
        multiplier_weights = self.config.constraint_multipliers.sliders_weights_avail_day_groups
        
        # Erstelle Shift-Variables-Mapping für AvailDay-Groups
        shift_vars_of_adg_ids = self._create_shift_vars_mapping()
        
        # Finde Root AvailDay Group
        root_group = next(
            (adg for adg in self.entities.avail_day_groups.values() if not adg.parent), 
            None
        )
        
        if not root_group:
            self.add_metadata('avail_day_groups_error', 'No root avail day group found')
            return []
        
        # Berechne maximale Tiefe für Gewichtungsausgleich
        max_depth = (
            max(node.depth for node in self.entities.avail_day_groups.values()) -
            (1 if root_group.group_is_actor_plan_period_master_group else 0)
        )
        
        self.add_metadata('max_avail_day_depth', max_depth)
        
        # Berechne Gewichtungs-Variablen
        if root_group.group_is_actor_plan_period_master_group:
            all_weight_vars = self._calculate_avail_day_weight_vars_recursive(
                root_group, max_depth, shift_vars_of_adg_ids
            )
        else:
            all_weight_vars = []
            for app_master_group in root_group.children:
                all_weight_vars.extend(
                    self._calculate_avail_day_weight_vars_recursive(
                        app_master_group, max_depth, shift_vars_of_adg_ids
                    )
                )
        
        return all_weight_vars
    
    def _calculate_avail_day_weight_vars_recursive(self, group, max_depth: int, 
                                                  shift_vars_mapping: Dict, 
                                                  cumulative_adjusted_weight: int = 0) -> List[IntVar]:
        """
        Berechnet AvailDay-Group Gewichtungs-Variablen rekursiv.
        
        Args:
            group: Die AvailDay-Group
            max_depth: Maximale Tiefe für Gewichtungsausgleich
            shift_vars_mapping: Mapping von AvailDay-Group-IDs zu Shift-Variablen
            cumulative_adjusted_weight: Kumulatives Gewicht von Parent-Groups
            
        Returns:
            Liste der Gewichtungs-Variablen
        """
        weight_vars = []
        multiplier_weights = self.config.constraint_multipliers.sliders_weights_avail_day_groups
        
        for child in group.children:
            if child.avail_day:
                # Prüfe ob Einsätze für dieses AvailDay möglich sind
                if not self._avail_day_has_possible_shifts(child.avail_day_group_id):
                    continue
                
                # Berechne angepasstes Gewicht (mit Level-Ausgleich)
                level_weight = (max_depth - child.depth) * multiplier_weights[1]
                child_weight = multiplier_weights[child.weight]
                adjusted_weight = level_weight + child_weight
                
                # Erstelle Gewichtungs-Variable
                var_name = (f'Depth {group.depth}, AvailDay: {child.avail_day.date:%d.%m.%y}, '
                           f'{child.avail_day.time_of_day.name}, '
                           f'{child.avail_day.actor_plan_period.person.f_name}')
                
                weight_var = self.model.NewIntVar(-100, 100000, var_name)
                weight_vars.append(weight_var)
                
                # Prüfe ob zugehörige Events stattfinden
                adg_has_shifts = self.model.NewBoolVar(f'adg_has_shifts_{child.avail_day_group_id}')
                
                if child.avail_day_group_id in shift_vars_mapping:
                    shift_vars = shift_vars_mapping[child.avail_day_group_id]
                    self.model.Add(adg_has_shifts == sum(shift_vars))
                else:
                    self.model.Add(adg_has_shifts == 0)
                
                # Constraint für Gewichtungs-Variable
                total_weight = cumulative_adjusted_weight + adjusted_weight
                self.model.Add(weight_var == (total_weight * adg_has_shifts))
                
            else:
                # Rekursive Bearbeitung für Groups ohne AvailDay
                child_adjusted_weight = multiplier_weights[child.weight]
                weight_vars.extend(
                    self._calculate_avail_day_weight_vars_recursive(
                        child, max_depth, shift_vars_mapping,
                        cumulative_adjusted_weight + child_adjusted_weight
                    )
                )
        
        return weight_vars
    
    def _create_shift_vars_mapping(self) -> Dict:
        """
        Erstellt Mapping von AvailDay-Group-IDs zu Shift-Variablen.
        
        Returns:
            Dictionary {adg_id: [shift_vars]}
        """
        shift_vars_of_adg_ids = defaultdict(list)
        
        for (adg_id, _), shift_var in self.entities.shift_vars.items():
            shift_vars_of_adg_ids[adg_id].append(shift_var)
        
        return shift_vars_of_adg_ids
    
    def _avail_day_has_possible_shifts(self, adg_id) -> bool:
        """
        Prüft ob für eine AvailDay-Group Einsätze möglich sind.
        
        Args:
            adg_id: AvailDay-Group ID
            
        Returns:
            True wenn Einsätze möglich sind
        """
        if adg_id not in self.entities.avail_day_groups_with_avail_day:
            return False
        
        adg = self.entities.avail_day_groups_with_avail_day[adg_id]
        
        # Prüfe ob es Shift-Variablen gibt, die nicht ausgeschlossen sind
        for (adg_check_id, evg_id), val in self.entities.shifts_exclusive.items():
            if adg_check_id == adg_id and val:
                # Prüfe zusätzlich Zeit- und Event-Kompatibilität
                if evg_id in self.entities.event_groups_with_event:
                    event = self.entities.event_groups_with_event[evg_id].event
                    if self._check_time_span_avail_day_fits_event(event, adg.avail_day):
                        return True
        
        return False
    
    def _check_time_span_avail_day_fits_event(self, event, avail_day, only_time_index: bool = True) -> bool:
        """
        Prüft ob AvailDay zeitlich zum Event passt.
        
        Entspricht check_time_span_avail_day_fits_event() aus solver_main.py.
        """
        if only_time_index:
            return (
                avail_day.date == event.date and
                avail_day.time_of_day.time_of_day_enum.time_index == 
                event.time_of_day.time_of_day_enum.time_index
            )
        else:
            return (
                avail_day.date == event.date and
                avail_day.time_of_day.start <= event.time_of_day.start and
                avail_day.time_of_day.end >= event.time_of_day.end
            )
    
    def validate_context(self) -> bool:
        """
        Validiert, ob der Kontext für diesen Constraint geeignet ist.
        
        Returns:
            True wenn alle notwendigen Datenstrukturen verfügbar sind
        """
        if not super().validate_context():
            return False
        
        # Prüfe notwendige Datenstrukturen
        required_attrs = [
            'event_groups',
            'event_group_vars',
            'avail_day_groups',
            'avail_day_groups_with_avail_day',
            'shift_vars',
            'shifts_exclusive',
            'event_groups_with_event'
        ]
        
        for attr in required_attrs:
            if not hasattr(self.entities, attr):
                self.add_metadata('validation_error', f"Missing entities.{attr}")
                return False
        
        # Prüfe Konfiguration
        if not hasattr(self.config, 'constraint_multipliers'):
            self.add_metadata('validation_error', "Missing config.constraint_multipliers")
            return False
        
        required_multipliers = [
            'group_depth_weights_event_groups',
            'sliders_weights_event_groups', 
            'sliders_weights_avail_day_groups'
        ]
        
        for multiplier in required_multipliers:
            if not hasattr(self.config.constraint_multipliers, multiplier):
                self.add_metadata('validation_error', f"Missing config multiplier: {multiplier}")
                return False
        
        return True
    
    def get_weights_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung der Gewichtungs-Daten zurück.
        
        Returns:
            Dictionary mit Gewichtungs-Statistiken
        """
        summary = {
            'total_event_groups': len(self.entities.event_groups),
            'total_avail_day_groups': len(self.entities.avail_day_groups),
            'event_weight_vars': len(self.get_metadata('event_weight_vars', [])),
            'avail_day_weight_vars': len(self.get_metadata('avail_day_weight_vars', [])),
            'total_weight_vars': self.get_metadata('total_weight_vars', 0)
        }
        
        # Gewichtungsverteilung analysieren
        if self.entities.event_groups:
            event_weights = [eg.weight for eg in self.entities.event_groups.values() if hasattr(eg, 'weight')]
            summary['event_weights_distribution'] = {
                weight: event_weights.count(weight) for weight in set(event_weights)
            }
        
        if self.entities.avail_day_groups:
            avail_weights = [adg.weight for adg in self.entities.avail_day_groups.values() if hasattr(adg, 'weight')]
            summary['avail_day_weights_distribution'] = {
                weight: avail_weights.count(weight) for weight in set(avail_weights)
            }
        
        return summary
    
    def get_summary(self) -> dict:
        """
        Erweiterte Zusammenfassung mit Gewichtungs-Daten.
        
        Returns:
            Dictionary mit Constraint- und Gewichtungs-Daten
        """
        base_summary = super().get_summary()
        base_summary.update(self.get_weights_summary())
        return base_summary
