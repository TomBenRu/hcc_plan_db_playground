"""
CastRulesConstraint - Constraint für Cast-Regeln

Dieser Constraint entspricht der Funktion add_constraints_cast_rules()
und behandelt Regeln für unterschiedliche oder gleiche Besetzungen
zwischen aufeinanderfolgenden Events.
"""

import collections
from typing import List, Dict
from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from .base import AbstractConstraint
from sat_solver import solver_variables
from sat_solver.cast_group_tree import CastGroup


class CastRulesConstraint(AbstractConstraint):
    """
    Constraint für Cast-Regeln zwischen Events.
    
    Dieser Constraint behandelt Regeln wie:
    - '-': Verschiedene Besetzungen zwischen Events
    - '~': Gleiche Besetzungen zwischen Events  
    - '*': Keine Regel (ignoriert)
    
    Die Regeln werden als String-Pattern definiert und auf aufeinanderfolgende
    Events in Cast-Groups angewendet.
    
    Entspricht der ursprünglichen Funktion add_constraints_cast_rules().
    """
    
    @property
    def constraint_name(self) -> str:
        """Name dieses Constraints."""
        return "cast_rules"
    
    def create_variables(self) -> List[IntVar]:
        """
        Erstellt Cast-Rule-Conflict-Variablen.
        
        Für jede Cast-Regel-Verletzung wird eine Variable erstellt,
        die in der Zielfunktion minimiert wird.
        
        Returns:
            Liste der erstellten Cast-Rule-Conflict-Variablen
        """
        cast_rule_vars = []
        
        # Organisiere Cast Groups nach Parent (Level 1)
        cast_groups_level_1 = self._organize_cast_groups_by_parent()
        
        # Sortiere Cast Groups nach Datum und Zeit
        for cast_groups in cast_groups_level_1.values():
            cast_groups.sort(key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index))
        
        # Erstelle Constraints für jede Parent-Cast-Group
        for cg_id, cast_groups in cast_groups_level_1.items():
            cast_groups: List[CastGroup]
            parent = self.entities.cast_groups[cg_id]
            
            # Überspringe wenn keine Regel oder kein Enforcement
            if not (rule := parent.cast_rule) or parent.strict_rule_pref == 0:
                continue
            
            # Verarbeite aufeinanderfolgende Cast Groups
            for idx in range(len(cast_groups) - 1):
                current_cast_group = cast_groups[idx]
                next_cast_group = cast_groups[idx + 1]
                
                # Bestimme die anzuwendende Regel (mit Modulo für wiederholende Pattern)
                rule_symbol = rule[idx % len(rule)]
                
                if rule_symbol == '-':
                    # Verschiedene Besetzungen erforderlich
                    conflict_vars = self._create_different_cast_constraints(
                        current_cast_group, next_cast_group, parent.strict_rule_pref
                    )
                    cast_rule_vars.extend(conflict_vars)
                    
                elif rule_symbol == '~':
                    # Gleiche Besetzungen erforderlich
                    conflict_vars = self._create_same_cast_constraints(
                        current_cast_group, next_cast_group, parent.strict_rule_pref
                    )
                    cast_rule_vars.extend(conflict_vars)
                    
                elif rule_symbol == '*':
                    # Keine Regel - ignorieren
                    continue
                    
                else:
                    # Unbekanntes Regel-Symbol
                    self.add_metadata(f'unknown_rule_symbol_{idx}', {
                        'symbol': rule_symbol,
                        'parent_id': str(cg_id),
                        'position': idx
                    })
                    raise ValueError(f'Unknown rule symbol: {rule_symbol}')
        
        self.add_metadata('total_cast_rule_conflicts', len(cast_rule_vars))
        return cast_rule_vars
    
    def add_constraints(self) -> None:
        """
        Fügt zusätzliche Cast-Rule-Constraints hinzu.
        
        Die Hauptlogik ist bereits in create_variables() implementiert.
        """
        constraints_added = 0
        
        # Reset Solver Variables für Cast Rules (falls verwendet)
        if hasattr(solver_variables, 'cast_rules'):
            solver_variables.cast_rules.reset_fields()
        
        self.add_metadata('additional_cast_rule_constraints', constraints_added)
    
    def _organize_cast_groups_by_parent(self) -> Dict[UUID, List[CastGroup]]:
        """
        Organisiert Cast Groups nach ihren Parent-IDs (Level 1).
        
        Returns:
            Dictionary {parent_id: [cast_groups]}
        """
        cast_groups_level_1 = collections.defaultdict(list)
        
        for cast_group in self.entities.cast_groups_with_event.values():
            if cast_group.parent:
                cast_groups_level_1[cast_group.parent.cast_group_id].append(cast_group)
        
        return cast_groups_level_1
    
    def _create_different_cast_constraints(self, cast_group_1: CastGroup, cast_group_2: CastGroup,
                                         strict_rule_pref: int) -> List[IntVar]:
        """
        Erstellt Constraints für verschiedene Besetzungen.
        
        Args:
            cast_group_1: Erste Cast Group
            cast_group_2: Zweite Cast Group  
            strict_rule_pref: Enforcement-Level (1=soft, 2=hard)
            
        Returns:
            Liste der Conflict-Variablen
        """
        broken_rules_vars = []
        
        event_group_1 = cast_group_1.event.event_group
        event_group_2 = cast_group_2.event.event_group
        
        for app_id, actor_plan_period in self.entities.actor_plan_periods.items():
            # Sammle Shift-Variablen für diesen Actor bei beiden Events
            shift_vars_1 = self._get_shift_vars_for_actor_and_event(app_id, event_group_1)
            shift_vars_2 = self._get_shift_vars_for_actor_and_event(app_id, event_group_2)
            
            if not shift_vars_1 or not shift_vars_2:
                continue
            
            if strict_rule_pref == 2:
                # Hard Constraint: Actor kann maximal in einem der beiden Events sein
                self.model.Add(sum(shift_vars_1) + sum(shift_vars_2) <= 1)
                
            elif strict_rule_pref == 1:
                # Soft Constraint: Erstelle Penalty-Variable
                name_var = (f'{event_group_1.event.date:%d.%m.} + {event_group_2.event.date:%d.%m.}, '
                           f'{event_group_1.event.location_plan_period.location_of_work.name}, '
                           f'{actor_plan_period.person.f_name}')
                
                penalty_var = self.model.NewBoolVar(name_var)
                
                # Penalty = 1 wenn Actor in beiden Events ist, sonst 0
                both_events_sum = sum(shift_vars_1) + sum(shift_vars_2)
                self.model.AddMaxEquality(penalty_var, [both_events_sum - 1, 0])
                
                broken_rules_vars.append(penalty_var)
        
        return broken_rules_vars
    
    def _create_same_cast_constraints(self, cast_group_1: CastGroup, cast_group_2: CastGroup,
                                    strict_rule_pref: int) -> List[IntVar]:
        """
        Erstellt Constraints für gleiche Besetzungen.
        
        Args:
            cast_group_1: Erste Cast Group
            cast_group_2: Zweite Cast Group
            strict_rule_pref: Enforcement-Level (1=soft, 2=hard)
            
        Returns:
            Liste der Conflict-Variablen
        """
        broken_rules_vars = []
        
        event_group_1 = cast_group_1.event.event_group
        event_group_2 = cast_group_2.event.event_group
        
        # Erstelle Applied-Shifts-Variablen für beide Events
        applied_shifts_1, applied_shifts_2 = self._create_applied_shifts_variables(
            event_group_1, event_group_2
        )
        
        # Erstelle Unequal-Variablen (XOR-Logik)
        curr_is_unequal = self._create_unequal_variables(applied_shifts_1, applied_shifts_2)
        
        if strict_rule_pref == 2:
            # Hard Constraint: Unterschiede dürfen nur Cast-Größen-Differenz betragen
            max_allowed_diff = abs(cast_group_1.nr_actors - cast_group_2.nr_actors)
            
            constraint = self.model.Add(sum(curr_is_unequal) <= max_allowed_diff)
            
            # Nur enforced wenn beide Events stattfinden
            self.model.AddImplication(
                self.entities.event_group_vars[event_group_1.event_group_id] *
                self.entities.event_group_vars[event_group_2.event_group_id],
                constraint
            )
            
        elif strict_rule_pref == 1:
            # Soft Constraint: Penalty für Abweichungen
            max_diff = cast_group_1.nr_actors + cast_group_2.nr_actors
            allowed_diff = abs(cast_group_1.nr_actors - cast_group_2.nr_actors)
            
            penalty_var = self.model.NewIntVar(
                0, max_diff,
                f'{event_group_1.event.date:%d.%m.} + {event_group_2.event.date:%d.%m.}, '
                f'{event_group_1.event.location_plan_period.location_of_work.name}'
            )
            
            # Penalty = (actual_differences - allowed_differences) / 2
            intermediate = self.model.NewIntVar(0, max_diff, 'intermediate_diff')
            
            both_events_active = self.model.NewBoolVar('both_events_active')
            self.model.AddMultiplicationEquality(
                both_events_active,
                [self.entities.event_group_vars[event_group_1.event_group_id],
                 self.entities.event_group_vars[event_group_2.event_group_id]]
            )
            
            self.model.Add(
                intermediate == ((sum(curr_is_unequal) - allowed_diff) * both_events_active)
            )
            
            self.model.AddDivisionEquality(penalty_var, intermediate, 2)
            broken_rules_vars.append(penalty_var)
        
        return broken_rules_vars
    
    def _get_shift_vars_for_actor_and_event(self, app_id: UUID, event_group) -> List[IntVar]:
        """
        Holt alle Shift-Variablen für einen Actor bei einem Event.
        
        Args:
            app_id: Actor Plan Period ID
            event_group: Event Group Objekt
            
        Returns:
            Liste der Shift-Variablen
        """
        shift_vars = []
        
        for (adg_id, eg_id), var in self.entities.shift_vars.items():
            if (eg_id == event_group.id and
                adg_id in self.entities.avail_day_groups_with_avail_day and
                self.entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.id == app_id and
                self.entities.shifts_exclusive.get((adg_id, eg_id), 0)):
                
                shift_vars.append(var)
        
        return shift_vars
    
    def _create_applied_shifts_variables(self, event_group_1, event_group_2) -> tuple[List[IntVar], List[IntVar]]:
        """
        Erstellt Applied-Shifts-Variablen für beide Events.
        
        Args:
            event_group_1: Erste Event Group
            event_group_2: Zweite Event Group
            
        Returns:
            Tupel aus (applied_shifts_1, applied_shifts_2)
        """
        applied_shifts_1 = []
        applied_shifts_2 = []
        
        for app_id, app in self.entities.actor_plan_periods.items():
            # Variable für Event 1
            shift_var_1_sum = sum(self._get_shift_vars_for_actor_and_event(app_id, event_group_1))
            applied_1 = self.model.NewBoolVar(f'{event_group_1.event.date:%d.%m.}: {app.person.f_name}')
            self.model.Add(applied_1 == shift_var_1_sum)
            applied_shifts_1.append(applied_1)
            
            # Variable für Event 2
            shift_var_2_sum = sum(self._get_shift_vars_for_actor_and_event(app_id, event_group_2))
            applied_2 = self.model.NewBoolVar(f'{event_group_2.event.date:%d.%m.}: {app.person.f_name}')
            self.model.Add(applied_2 == shift_var_2_sum)
            applied_shifts_2.append(applied_2)
        
        # Speichere in solver_variables falls verwendet
        if hasattr(solver_variables, 'cast_rules'):
            solver_variables.cast_rules.applied_shifts_1.append(applied_shifts_1)
            solver_variables.cast_rules.applied_shifts_2.append(applied_shifts_2)
        
        return applied_shifts_1, applied_shifts_2
    
    def _create_unequal_variables(self, applied_shifts_1: List[IntVar], 
                                 applied_shifts_2: List[IntVar]) -> List[IntVar]:
        """
        Erstellt Unequal-Variablen (XOR-Logik) für Applied-Shifts.
        
        Args:
            applied_shifts_1: Applied-Shifts für Event 1
            applied_shifts_2: Applied-Shifts für Event 2
            
        Returns:
            Liste der Unequal-Variablen
        """
        curr_is_unequal = []
        
        for i, (shift_1, shift_2) in enumerate(zip(applied_shifts_1, applied_shifts_2)):
            app = list(self.entities.actor_plan_periods.values())[i]
            
            unequal_var = self.model.NewBoolVar(f'unequal_{app.person.f_name}')
            factor = self.model.NewIntVar(0, 1, f'factor_{i}')
            
            # XOR-Bedingung: applied_1 + applied_2 == unequal + 2 * factor
            self.model.Add(shift_1 + shift_2 == unequal_var + 2 * factor)
            
            curr_is_unequal.append(unequal_var)
        
        # Speichere in solver_variables falls verwendet
        if hasattr(solver_variables, 'cast_rules'):
            solver_variables.cast_rules.is_unequal.extend(curr_is_unequal)
        
        return curr_is_unequal
    
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
            'cast_groups',
            'cast_groups_with_event',
            'actor_plan_periods',
            'shift_vars',
            'event_group_vars',
            'shifts_exclusive',
            'avail_day_groups_with_avail_day'
        ]
        
        for attr in required_attrs:
            if not hasattr(self.entities, attr):
                self.add_metadata('validation_error', f"Missing entities.{attr}")
                return False
        
        # Prüfe ob Cast Groups existieren
        if not self.entities.cast_groups_with_event:
            self.add_metadata('validation_error', "No cast groups with events found")
            return False
        
        return True
    
    def get_cast_rules_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung der Cast Rules Daten zurück.
        
        Returns:
            Dictionary mit Cast Rules Statistiken
        """
        if not self.entities.cast_groups:
            return {}
        
        # Analysiere Cast Groups und ihre Regeln
        total_cast_groups = len(self.entities.cast_groups)
        cast_groups_with_rules = 0
        rule_patterns = []
        enforcement_levels = []
        
        cast_groups_level_1 = self._organize_cast_groups_by_parent()
        
        for cg_id, cast_groups in cast_groups_level_1.items():
            parent = self.entities.cast_groups[cg_id]
            
            if parent.cast_rule:
                cast_groups_with_rules += 1
                rule_patterns.append(parent.cast_rule)
                enforcement_levels.append(parent.strict_rule_pref)
        
        # Pattern-Analyse
        unique_patterns = list(set(rule_patterns))
        pattern_counts = {pattern: rule_patterns.count(pattern) for pattern in unique_patterns}
        
        # Enforcement-Analyse
        enforcement_counts = {level: enforcement_levels.count(level) for level in set(enforcement_levels)}
        
        return {
            'total_cast_groups': total_cast_groups,
            'cast_groups_with_rules': cast_groups_with_rules,
            'unique_rule_patterns': len(unique_patterns),
            'rule_pattern_counts': pattern_counts,
            'enforcement_level_counts': enforcement_counts,
            'cast_rule_conflict_variables': self.get_metadata('total_cast_rule_conflicts', 0),
            'cast_rule_coverage': (
                cast_groups_with_rules / len(cast_groups_level_1) 
                if cast_groups_level_1 else 0.0
            )
        }
    
    def get_cast_rules_details(self) -> List[dict]:
        """
        Gibt detaillierte Informationen über Cast Rules zurück.
        
        Returns:
            Liste mit Details zu jeder Cast Rule
        """
        details = []
        
        cast_groups_level_1 = self._organize_cast_groups_by_parent()
        
        for cg_id, cast_groups in cast_groups_level_1.items():
            parent = self.entities.cast_groups[cg_id]
            
            if not parent.cast_rule:
                continue
            
            # Sortiere Cast Groups
            cast_groups.sort(key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index))
            
            for idx in range(len(cast_groups) - 1):
                rule_symbol = parent.cast_rule[idx % len(parent.cast_rule)]
                
                details.append({
                    'parent_cast_group_id': str(cg_id),
                    'rule_pattern': parent.cast_rule,
                    'rule_position': idx,
                    'rule_symbol': rule_symbol,
                    'enforcement_level': parent.strict_rule_pref,
                    'enforcement_description': {
                        0: 'No enforcement',
                        1: 'Soft constraint (penalty)',
                        2: 'Hard constraint (must satisfy)'
                    }.get(parent.strict_rule_pref, 'Unknown'),
                    'event_1_date': cast_groups[idx].event.date.strftime('%Y-%m-%d'),
                    'event_1_time': cast_groups[idx].event.time_of_day.name,
                    'event_1_location': cast_groups[idx].event.location_plan_period.location_of_work.name,
                    'event_2_date': cast_groups[idx + 1].event.date.strftime('%Y-%m-%d'),
                    'event_2_time': cast_groups[idx + 1].event.time_of_day.name,
                    'event_2_location': cast_groups[idx + 1].event.location_plan_period.location_of_work.name,
                    'rule_description': {
                        '-': 'Different cast required',
                        '~': 'Same cast required',
                        '*': 'No rule (ignore)'
                    }.get(rule_symbol, 'Unknown rule')
                })
        
        return details
    
    def get_summary(self) -> dict:
        """
        Erweiterte Zusammenfassung mit Cast Rules Daten.
        
        Returns:
            Dictionary mit Constraint- und Cast Rules Daten
        """
        base_summary = super().get_summary()
        base_summary.update(self.get_cast_rules_summary())
        return base_summary
