"""
ShiftsConstraint - Constraint für Schicht-Management

Dieser Constraint kombiniert verschiedene schicht-bezogene Constraints:
- add_constraints_unsigned_shifts()
- add_constraints_rel_shift_deviations()
- add_constraints_different_casts_on_shifts_with_different_locations_on_same_day()
"""

import itertools
import datetime
from typing import List, Dict, Tuple
from collections import defaultdict
from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from .base import AbstractConstraint


class ShiftsConstraint(AbstractConstraint):
    """
    Constraint für Schicht-Management und -Verteilung.
    
    Dieser Constraint behandelt:
    1. Unassigned Shifts (nicht zugewiesene Schichten)
    2. Relative Shift Deviations (Abweichungen von gewünschten Zuweisungen)
    3. Different Casts Constraints (verschiedene Besetzungen an verschiedenen Orten)
    
    Entspricht den ursprünglichen Funktionen:
    - add_constraints_unsigned_shifts()
    - add_constraints_rel_shift_deviations()  
    - add_constraints_different_casts_on_shifts_with_different_locations_on_same_day()
    """
    
    @property
    def constraint_name(self) -> str:
        """Name dieses Constraints."""
        return "shifts_management"
    
    def create_variables(self) -> List[IntVar]:
        """
        Erstellt alle Schicht-bezogenen Variablen.
        
        Returns:
            Liste aller erstellten Variablen
        """
        all_vars = []
        
        # 1. Unassigned Shifts Variablen
        unassigned_vars = self._create_unassigned_shifts_vars()
        all_vars.extend(unassigned_vars.values())
        
        # 2. Shift Deviation Variablen
        deviation_vars = self._create_shift_deviation_vars()
        all_vars.extend(deviation_vars['sum_assigned_shifts'].values())
        all_vars.extend(deviation_vars['relative_deviations'].values())
        all_vars.extend(deviation_vars['squared_deviations'].values())
        all_vars.append(deviation_vars['sum_squared_deviations'])
        
        return all_vars
    
    def add_constraints(self) -> None:
        """
        Fügt alle Schicht-Constraints hinzu.
        """
        self._add_unassigned_shifts_constraints()
        self._add_shift_deviation_constraints()
        self._add_different_casts_constraints()
    
    def _create_unassigned_shifts_vars(self) -> Dict[UUID, IntVar]:
        """
        Erstellt Variablen für unassigned shifts pro Event.
        
        Returns:
            Dictionary {event_group_id: unassigned_shifts_var}
        """
        unassigned_shifts_per_event = {}
        
        max_nr_actors = max(
            evg.event.cast_group.nr_actors
            for evg in self.entities.event_groups_with_event.values()
        ) if self.entities.event_groups_with_event else 0
        
        for event_group_id, event_group in self.entities.event_groups_with_event.items():
            var_name = f'unassigned_shifts_{event_group.event.date}'
            unassigned_var = self.model.NewIntVar(0, max_nr_actors, var_name)
            unassigned_shifts_per_event[event_group_id] = unassigned_var
        
        # Speichere für späteren Zugriff
        self.add_metadata('unassigned_shifts_vars', unassigned_shifts_per_event)
        return unassigned_shifts_per_event
    
    def _create_shift_deviation_vars(self) -> Dict[str, any]:
        """
        Erstellt Variablen für Schicht-Abweichungen.
        
        Returns:
            Dictionary mit verschiedenen Deviation-Variablen
        """
        # Sum Assigned Shifts pro Actor
        sum_assigned_shifts = {
            app.id: self.model.NewIntVar(
                lb=0, ub=1000, 
                name=f'sum_assigned_shifts_{app.person.f_name}'
            )
            for app in self.entities.actor_plan_periods.values()
        }
        
        # Relative Shift Deviations
        max_deviation = len(self.entities.event_groups_with_event) * 1_000_000
        relative_shift_deviations = {
            app.id: self.model.NewIntVar(
                lb=-max_deviation, ub=max_deviation,
                name=f'relative_shift_deviation_{app.person.f_name}'
            )
            for app in self.entities.actor_plan_periods.values()
        }
        
        # Squared Deviations
        squared_deviations = {
            app.id: self.model.NewIntVar(
                lb=0, ub=max_deviation ** 2,
                name=f'squared_deviation_{app.person.f_name}'
            )
            for app in self.entities.actor_plan_periods.values()
        }
        
        # Sum of Squared Deviations
        sum_squared_deviations = self.model.NewIntVar(
            lb=0, ub=1_000_000_000, name='sum_squared_deviations'
        )
        
        deviation_vars = {
            'sum_assigned_shifts': sum_assigned_shifts,
            'relative_deviations': relative_shift_deviations,
            'squared_deviations': squared_deviations,
            'sum_squared_deviations': sum_squared_deviations
        }
        
        # Speichere für späteren Zugriff
        for key, value in deviation_vars.items():
            self.add_metadata(f'{key}_vars', value)
        
        return deviation_vars
    
    def _add_unassigned_shifts_constraints(self) -> None:
        """
        Fügt Constraints für unassigned shifts hinzu.
        
        Entspricht add_constraints_unsigned_shifts().
        """
        unassigned_vars = self.get_metadata('unassigned_shifts_vars')
        constraints_added = 0
        
        for event_group_id, event_group in self.entities.event_groups_with_event.items():
            unassigned_var = unassigned_vars[event_group_id]
            
            # Summe aller zugewiesenen Mitarbeiter zum Event
            num_assigned_employees = sum(
                self.entities.shift_vars[(adg_id, event_group_id)]
                for adg_id in self.entities.avail_day_groups_with_avail_day
                if (adg_id, event_group_id) in self.entities.shift_vars
            )
            
            # Anzahl zugewiesener Mitarbeiter <= Anzahl benötigter Mitarbeiter (wenn Event stattfindet)
            self.model.Add(
                num_assigned_employees <= (
                    self.entities.event_group_vars[event_group.event_group_id] *
                    event_group.event.cast_group.nr_actors
                )
            )
            constraints_added += 1
            
            # Unassigned shifts = benötigte Mitarbeiter - zugewiesene Mitarbeiter
            self.model.Add(
                unassigned_var == (
                    self.entities.event_group_vars[event_group.event_group_id] *
                    event_group.event.cast_group.nr_actors - num_assigned_employees
                )
            )
            constraints_added += 1
        
        self.add_metadata('unassigned_shifts_constraints_added', constraints_added)
    
    def _add_shift_deviation_constraints(self) -> None:
        """
        Fügt Constraints für Schicht-Abweichungen hinzu.
        
        Entspricht add_constraints_rel_shift_deviations().
        """
        sum_assigned_shifts = self.get_metadata('sum_assigned_shifts_vars')
        relative_deviations = self.get_metadata('relative_deviations_vars')
        squared_deviations = self.get_metadata('squared_deviations_vars')
        sum_squared_deviations = self.get_metadata('sum_squared_deviations_vars')
        
        constraints_added = 0
        
        # Berechne Summe der gewünschten Zuweisungen
        sum_requested_assignments = sum(
            app.requested_assignments for app in self.entities.actor_plan_periods.values()
        ) or 0.1
        
        # Für jeden Actor Plan Period
        for app in self.entities.actor_plan_periods.values():
            app_id = app.id
            
            # Berechne tatsächlich zugewiesene Schichten
            assigned_shifts_of_app = sum(
                sum(
                    self.entities.shift_vars[(adg_id, evg_id)]
                    for evg_id in self.entities.event_groups_with_event
                    if (adg_id, evg_id) in self.entities.shift_vars
                )
                for adg_id, adg in self.entities.avail_day_groups_with_avail_day.items()
                if adg.avail_day.actor_plan_period.id == app_id
            )
            
            # Sum assigned shifts
            self.model.AddAbsEquality(sum_assigned_shifts[app_id], assigned_shifts_of_app)
            constraints_added += 1
            
            # Shift deviation
            shift_deviation = self.model.NewIntVar(-1000, 1000, f'shift_deviation_{app.person.f_name}')
            self.model.Add(shift_deviation == assigned_shifts_of_app - int(app.requested_assignments))
            constraints_added += 1
            
            # Relative shift deviation
            requested_assignments_scaled = int(app.requested_assignments * 10) if app.requested_assignments else 1
            self.model.AddDivisionEquality(
                relative_deviations[app_id],
                shift_deviation * 1_000,
                requested_assignments_scaled
            )
            constraints_added += 1
        
        # Durchschnittliche relative Abweichung berechnen
        sum_assigned_shifts_sum = self.model.NewIntVar(0, 10000, "sum_assigned_shifts_sum")
        self.model.Add(sum_assigned_shifts_sum == sum(sum_assigned_shifts.values()))
        constraints_added += 1
        
        diff = self.model.NewIntVar(-10000, 10000, "difference_term")
        self.model.Add(diff == sum_assigned_shifts_sum - int(sum_requested_assignments))
        constraints_added += 1
        
        scaled_diff = self.model.NewIntVar(-10_000_000, 10_000_000, "scaled_difference")
        self.model.AddMultiplicationEquality(scaled_diff, [diff, 1000])
        constraints_added += 1
        
        average_relative_shift_deviation = self.model.NewIntVar(
            -10_000_000, 10_000_000, "average_relative_shift_deviation"
        )
        self.model.AddDivisionEquality(
            average_relative_shift_deviation, scaled_diff, int(sum_requested_assignments) * 10
        )
        constraints_added += 1
        
        # Squared deviations
        for app in self.entities.actor_plan_periods.values():
            app_id = app.id
            
            diff_from_average = self.model.NewIntVar(
                0, 1_000_000, f'diff_from_average_{app_id}'
            )
            self.model.AddAbsEquality(
                diff_from_average,
                relative_deviations[app_id] - average_relative_shift_deviation
            )
            constraints_added += 1
            
            self.model.AddMultiplicationEquality(
                squared_deviations[app_id],
                [diff_from_average, diff_from_average]
            )
            constraints_added += 1
        
        # Sum of squared deviations
        self.model.AddAbsEquality(sum_squared_deviations, sum(squared_deviations.values()))
        constraints_added += 1
        
        self.add_metadata('shift_deviation_constraints_added', constraints_added)
    
    def _add_different_casts_constraints(self) -> None:
        """
        Fügt Constraints für verschiedene Besetzungen an verschiedenen Orten hinzu.
        
        Entspricht add_constraints_different_casts_on_shifts_with_different_locations_on_same_day().
        """
        constraints_added = 0
        
        # Erstelle Dictionary [date[actor_plan_period_id[location_id[list[shift_vars]]]]]
        dict_date_shift_var = self._create_date_shift_dict()
        
        # Erstelle Constraints
        for date, dict_actor_plan_period_id in dict_date_shift_var.items():
            for actor_plan_period_id, dict_location_id in dict_actor_plan_period_id.items():
                if len(dict_location_id) > 1:
                    # Mehrere Locations am selben Tag für denselben Actor
                    for loc_pair in itertools.combinations(list(dict_location_id.values()), 2):
                        for var_pair in itertools.product(*loc_pair):
                            # Prüfe ob Combination Locations möglich sind
                            if not self._combination_locations_possible(var_pair[0][0], var_pair[1][0]):
                                # Nicht möglich: Actor kann maximal an einer Location arbeiten
                                self.model.Add(sum(v[1] for v in var_pair) <= 1)
                                constraints_added += 1
        
        self.add_metadata('different_casts_constraints_added', constraints_added)
    
    def _create_date_shift_dict(self) -> dict:
        """
        Erstellt Dictionary zur Organisation der Shift-Variablen nach Datum, Actor und Location.
        """
        dict_date_shift_var = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        
        for (adg_id, eg_id), shift_var in self.entities.shift_vars.items():
            if not self.entities.shifts_exclusive.get((adg_id, eg_id), 1):
                continue
                
            date = self.entities.event_groups_with_event[eg_id].event.date
            actor_plan_period_id = self.entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.id
            location_id = self.entities.event_groups_with_event[eg_id].event.location_plan_period.location_of_work.id
            
            dict_date_shift_var[date][actor_plan_period_id][location_id].append(((adg_id, eg_id), shift_var))
        
        return dict_date_shift_var
    
    def _combination_locations_possible(self, key1: Tuple[UUID, UUID], key2: Tuple[UUID, UUID]) -> bool:
        """
        Prüft ob eine Kombination von Locations für einen Actor möglich ist.
        
        Args:
            key1: (adg_id_1, eg_id_1)
            key2: (adg_id_2, eg_id_2)
            
        Returns:
            True wenn Kombination möglich ist
        """
        adg_id_1, eg_id_1 = key1
        adg_id_2, eg_id_2 = key2
        
        avail_day_group_1 = self.entities.avail_day_groups_with_avail_day[adg_id_1]
        avail_day_group_2 = self.entities.avail_day_groups_with_avail_day[adg_id_2]
        event_1 = self.entities.event_groups_with_event[eg_id_1].event
        event_2 = self.entities.event_groups_with_event[eg_id_2].event
        
        # Berechne Zeitunterschiede
        start_1 = datetime.datetime.combine(event_1.date, event_1.time_of_day.start)
        end_1 = datetime.datetime.combine(event_1.date, event_1.time_of_day.end)
        start_2 = datetime.datetime.combine(event_2.date, event_2.time_of_day.start)
        end_2 = datetime.datetime.combine(event_2.date, event_2.time_of_day.end)
        
        time_diff = start_1 - end_2 if start_1 > end_2 else start_2 - end_1
        
        location_1_id = event_1.location_plan_period.location_of_work.id
        location_2_id = event_2.location_plan_period.location_of_work.id
        
        # Prüfe combination_locations_possibles
        for avail_day_group in [avail_day_group_1, avail_day_group_2]:
            clp = next(
                (clp for clp in avail_day_group.avail_day.combination_locations_possibles
                 if location_1_id in [loc.id for loc in clp.locations_of_work]
                 and location_2_id in [loc.id for loc in clp.locations_of_work]
                 and not clp.prep_delete), 
                None
            )
            
            if clp and time_diff >= clp.time_span_between:
                return True
        
        return False
    
    def validate_context(self) -> bool:
        """
        Validiert, ob der Kontext für diesen Constraint geeignet ist.
        """
        if not super().validate_context():
            return False
        
        required_attrs = [
            'event_groups_with_event',
            'avail_day_groups_with_avail_day', 
            'actor_plan_periods',
            'shift_vars',
            'event_group_vars',
            'shifts_exclusive'
        ]
        
        for attr in required_attrs:
            if not hasattr(self.entities, attr):
                self.add_metadata('validation_error', f"Missing entities.{attr}")
                return False
        
        return True
    
    def get_shifts_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung der Schicht-Daten zurück.
        """
        if not self.entities.shift_vars:
            return {}
        
        total_shifts = len(self.entities.shift_vars)
        available_shifts = sum(1 for val in self.entities.shifts_exclusive.values() if val == 1)
        total_events = len(self.entities.event_groups_with_event)
        total_actors = len(self.entities.actor_plan_periods)
        
        return {
            'total_shift_variables': total_shifts,
            'available_shift_combinations': available_shifts,
            'total_events': total_events,
            'total_actors': total_actors,
            'availability_ratio': available_shifts / total_shifts if total_shifts > 0 else 0
        }
    
    def get_summary(self) -> dict:
        """
        Erweiterte Zusammenfassung mit Schicht-Daten.
        """
        base_summary = super().get_summary()
        base_summary.update(self.get_shifts_summary())
        return base_summary
