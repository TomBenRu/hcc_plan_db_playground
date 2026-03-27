"""
CastRulesConstraint - Soft/Hard Constraint für Besetzungsregeln.

Implementiert Regeln für Event-Besetzungen:
- Different Cast ("-"): Events müssen mit verschiedenen Mitarbeitern besetzt sein
- Same Cast ("~"): Events müssen mit den gleichen Mitarbeitern besetzt sein
- No Rule ("*"): Keine Besetzungsregel
"""
import collections
from typing import TYPE_CHECKING
from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from database import schemas
from sat_solver import solver_variables
from sat_solver.cast_group_tree import CastGroup
from sat_solver.constraints.base import ConstraintBase, Validatable

if TYPE_CHECKING:
    pass  # schemas bereits importiert


class CastRulesConstraint(ConstraintBase):
    """
    Constraint für Besetzungsregeln (Cast Rules).
    
    Implementiert Regeln für Event-Besetzungen basierend auf Cast Groups.
    Kann als Hard Constraint (strict_rule_pref=2) oder Soft Constraint 
    (strict_rule_pref=1) angewendet werden.
    
    Logik:
    - Cast Groups werden auf Level 1 gruppiert nach Parent
    - Regeln werden auf aufeinanderfolgende Cast Groups angewendet
    - "-" = Different Cast: Verschiedene Mitarbeiter
    - "~" = Same Cast: Gleiche Mitarbeiter
    - "*" = Keine Regel
    
    TODO: Anpassen für den Fall, dass nr_actors in Event Group < als len(children).
    TODO: Bisher nur Cast Groups auf Level 1 berücksichtigt
    """
    
    name = "cast_rules"
    weight_attribute = "constraints_cast_rule"
    
    def apply(self) -> None:
        """
        Wendet das Cast Rules Constraint an.
        
        Sammelt Cast Groups, sortiert sie chronologisch und wendet
        die entsprechenden Regeln an.
        """
        # Sammle alle Cast Groups auf Level 1, gruppiert nach Parent
        cast_groups_level_1 = collections.defaultdict(list)
        for cast_group in self.entities.cast_groups_with_event.values():
            cast_groups_level_1[cast_group.parent.cast_group_id].append(cast_group)
        
        # Sortiere Cast Groups chronologisch für konsistente Reihenfolge
        for cast_groups in cast_groups_level_1.values():
            cast_groups.sort(
                key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index)
            )
        
        # Verarbeite jede Cast Group Hierarchie
        for cg_id, cast_groups in cast_groups_level_1.items():
            cast_groups: list[CastGroup]
            parent = self.entities.cast_groups[cg_id]
            
            # Überspringe wenn keine Regel definiert oder inaktiv
            if not (rule := parent.cast_rule) or parent.strict_rule_pref == 0:
                continue
            
            # Wende Regeln auf aufeinanderfolgende Cast Groups an
            for idx in range(len(cast_groups) - 1):
                event_group_1 = self.entities.event_groups_with_event.get(
                    cast_groups[idx].event.event_group_id)
                event_group_2 = self.entities.event_groups_with_event.get(
                    cast_groups[idx + 1].event.event_group_id)
                if event_group_1 is None or event_group_2 is None:
                    continue

                # Regel-Symbol aus zyklischem Pattern ermitteln
                rule_symbol = rule[idx % len(rule)]

                if rule_symbol == '-':
                    # Different Cast Regel anwenden
                    self.penalty_vars.extend(
                        self._different_cast(event_group_1, event_group_2, parent.strict_rule_pref)
                    )
                elif rule_symbol == '~':
                    # Same Cast Regel anwenden
                    self.penalty_vars.extend(
                        self._same_cast(cast_groups[idx], cast_groups[idx + 1], parent.strict_rule_pref)
                    )
                elif rule_symbol == '*':
                    # Keine Regel - überspringen
                    continue
                else:
                    raise ValueError(f'unknown rule symbol: {rule}')
    
    def _different_cast(
        self, 
        event_group_1: schemas.EventGroup, 
        event_group_2: schemas.EventGroup,
        strict_rule_pref: int
    ) -> list[IntVar]:
        """
        Implementiert "Different Cast" Regel - Events müssen verschiedene Besetzung haben.
        
        Für jeden Mitarbeiter: Maximal eine Schicht in einer der beiden Event Groups.
        
        Args:
            event_group_1: Erste Event Group für Vergleich
            event_group_2: Zweite Event Group für Vergleich
            strict_rule_pref: Regel-Strenge (0=keine, 1=soft, 2=hart)
            
        Returns:
            Liste der Broken-Rule-Variablen (nur bei strict_rule_pref == 1)
        """
        broken_rules_vars: list[IntVar] = []
        
        for app_id, actor_plan_period in self.entities.actor_plan_periods.items():
            # Sammle alle relevanten Schicht-Variablen für beide Event Groups
            shift_vars = {
                (adg_id, eg_id): var 
                for (adg_id, eg_id), var in self.entities.shift_vars.items()
                if eg_id in {event_group_1.id, event_group_2.id}
                and self.entities.avail_day_groups[adg_id].avail_day.actor_plan_period.id == app_id
                and self.entities.avail_day_groups_with_avail_day[adg_id].avail_day.date
                    in {event_group_1.event.date, event_group_2.event.date}
                and self.entities.shifts_exclusive[(adg_id, eg_id)]
            }
            
            if strict_rule_pref == 2:
                # Harte Regel: Mitarbeiter kann maximal in einer Event Group arbeiten
                self.model.Add(sum(shift_vars.values()) <= 1)
            elif strict_rule_pref == 1:
                # Weiche Regel: Erstelle Variable für Regelverstoß
                name_var = (
                    f'{event_group_1.event.date:%d.%m.} + {event_group_2.event.date:%d.%m.}, '
                    f'{event_group_1.event.location_plan_period.location_of_work.name}, '
                    f'{actor_plan_period.person.f_name}'
                )
                equal_to_two = self.model.NewBoolVar(name_var)
                self.model.AddMaxEquality(equal_to_two, [sum(shift_vars.values()) - 1, 0])
                broken_rules_vars.append(equal_to_two)
        
        return broken_rules_vars
    
    def _same_cast(
        self, 
        cast_group_1: CastGroup, 
        cast_group_2: CastGroup, 
        strict_rule_pref: int
    ) -> list[IntVar]:
        """
        Implementiert "Same Cast" Regel - Events müssen mit gleichen Mitarbeitern besetzt sein.
        
        Falls die Events unterschiedliche Anzahl an Mitarbeitern haben, müssen alle
        Mitarbeiter des Events mit der kleineren Besetzung auch im Event mit der
        größeren Besetzung vorkommen.
        
        Args:
            cast_group_1: Erste Cast Group für Vergleich
            cast_group_2: Zweite Cast Group für Vergleich
            strict_rule_pref: Regel-Strenge (0=keine, 1=soft, 2=hart)
            
        Returns:
            Liste der Broken-Rule-Variablen (nur bei strict_rule_pref == 1)
        """
        broken_rules_vars: list[IntVar] = []
        
        event_group_1_id = cast_group_1.event.event_group_id
        event_group_2_id = cast_group_2.event.event_group_id
        
        # Erstelle Boolean-Arrays für tatsächliche Schicht-Zuweisungen
        applied_shifts_1: list[IntVar] = [
            self.model.NewBoolVar(f'{cast_group_1.event.date:%d.%m.}: {app.person.f_name}')
            for app in self.entities.actor_plan_periods.values()
        ]
        applied_shifts_2: list[IntVar] = [
            self.model.NewBoolVar(f'{cast_group_2.event.date:%d.%m.}: {app.person.f_name}')
            for app in self.entities.actor_plan_periods.values()
        ]
        
        # Speichere für Debug-Zwecke in solver_variables
        solver_variables.cast_rules.applied_shifts_1.append(applied_shifts_1)
        solver_variables.cast_rules.applied_shifts_2.append(applied_shifts_2)
        
        # Verknüpfe Boolean-Arrays mit tatsächlichen Schicht-Variablen
        for i, (app_id, app) in enumerate(self.entities.actor_plan_periods.items()):
            # Finde Schicht-Variable für Event 1
            shift_var_1 = next(
                (v for (adg_id, eg_id), v in self.entities.shift_vars.items()
                 if eg_id == event_group_1_id
                 and self.entities.avail_day_groups[adg_id].avail_day.actor_plan_period.id == app_id
                 and self.entities.shifts_exclusive[(adg_id, eg_id)]),
                0
            )
            # Finde Schicht-Variable für Event 2
            shift_var_2 = next(
                (v for (adg_id, eg_id), v in self.entities.shift_vars.items()
                 if eg_id == event_group_2_id
                 and self.entities.avail_day_groups[adg_id].avail_day.actor_plan_period.id == app_id
                 and self.entities.shifts_exclusive[(adg_id, eg_id)]),
                0
            )
            
            self.model.Add(applied_shifts_1[i] == shift_var_1)
            self.model.Add(applied_shifts_2[i] == shift_var_2)
        
        # Berechne Unterschiede zwischen den Besetzungen (XOR-Logic)
        curr_is_unequal: list[IntVar] = []
        
        for i, app in enumerate(self.entities.actor_plan_periods.values()):
            curr_is_unequal.append(
                self.model.NewBoolVar(f'{cast_group_1.event.date:%d.%m.}: {app.person.f_name}')
            )
            # Hilfsvariable für XOR-Implementierung
            factor = self.model.NewIntVar(0, 1, '')
            # XOR-Bedingung: unterschiedlich wenn genau einer der beiden true ist
            self.model.Add(
                applied_shifts_1[i] + applied_shifts_2[i] == curr_is_unequal[-1] + 2 * factor
            )
        
        solver_variables.cast_rules.is_unequal.extend(curr_is_unequal)
        
        if strict_rule_pref == 2:
            # Harte Regel: Anzahl Unterschiede <= erlaubte Differenz
            (self.model.Add(sum(curr_is_unequal) <= abs(cast_group_1.nr_actors - cast_group_2.nr_actors))
             .OnlyEnforceIf([self.entities.event_group_vars[event_group_1_id],
                             self.entities.event_group_vars[event_group_2_id]]))
            return broken_rules_vars
        elif strict_rule_pref == 1:
            # Weiche Regel: Erstelle Variable für Regelverstoß
            max_diff = cast_group_1.nr_actors + cast_group_2.nr_actors
            broken_rules_var = self.model.NewIntVar(
                0, max_diff,
                f'{cast_group_1.event.date:%d.%m.} + '
                f'{cast_group_2.event.date:%d.%m.}, '
                f'{cast_group_1.event.location_plan_period.location_of_work.name}'
            )
            # Zwischenvariable für Berechnung
            intermediate = self.model.NewIntVar(0, max_diff, '')
            (self.model.Add(intermediate == (sum(curr_is_unequal) -
                                             abs(cast_group_1.nr_actors - cast_group_2.nr_actors)))
             .OnlyEnforceIf([self.entities.event_group_vars[event_group_1_id],
                             self.entities.event_group_vars[event_group_2_id]]))
            self.model.AddDivisionEquality(broken_rules_var, intermediate, 2)
            broken_rules_vars.append(broken_rules_var)
            return broken_rules_vars
        elif strict_rule_pref == 0:
            # Keine Regel aktiv
            return broken_rules_vars
        else:
            raise ValueError(f'Unbekannte strict_rule_pref: {strict_rule_pref}')


    def validate_plan(self, plan: 'schemas.PlanShow') -> list['ValidationError']:
        """
        Prüft ob Cast Rules (bei strict_rule_pref=2) eingehalten werden.
        
        Regeln:
        - "-" = Different Cast: Keine Person darf in beiden aufeinanderfolgenden Events sein
        - "~" = Same Cast: Gleiche Personen müssen in beiden Events sein (mit erlaubter Differenz)
        """
        from sat_solver.constraints.base import ValidationError
        
        errors = []
        
        # Lookup: event_id -> {person_id: full_name} (für IDs und Fehlermeldungen)
        assigned_persons_by_event: dict[UUID, dict[UUID, str]] = {}
        for appointment in plan.appointments:
            event_id = appointment.event.id
            assigned_persons_by_event[event_id] = {
                avd.actor_plan_period.person.id: avd.actor_plan_period.person.full_name
                for avd in appointment.avail_days
            }
        
        # Sammle Cast Groups auf Level 1, gruppiert nach Parent (wie in apply())
        cast_groups_level_1 = collections.defaultdict(list)
        for cast_group in self.entities.cast_groups_with_event.values():
            cast_groups_level_1[cast_group.parent.cast_group_id].append(cast_group)
        
        # Sortiere chronologisch
        for cast_groups in cast_groups_level_1.values():
            cast_groups.sort(
                key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index)
            )
        
        # Prüfe jede Cast Group Hierarchie
        for cg_id, cast_groups in cast_groups_level_1.items():
            cast_groups: list[CastGroup]
            parent = self.entities.cast_groups[cg_id]
            
            # Nur Hard Constraints prüfen (strict_rule_pref == 2)
            if not (rule := parent.cast_rule) or parent.strict_rule_pref != 2:
                continue
            
            # Prüfe aufeinanderfolgende Cast Groups
            for idx in range(len(cast_groups) - 1):
                cg_1 = cast_groups[idx]
                cg_2 = cast_groups[idx + 1]
                
                event_1 = cg_1.event
                event_2 = cg_2.event
                
                # Prüfe ob beide Events im Plan sind
                if event_1.id not in assigned_persons_by_event or event_2.id not in assigned_persons_by_event:
                    continue
                
                persons_1 = assigned_persons_by_event[event_1.id]
                persons_2 = assigned_persons_by_event[event_2.id]
                ids_1 = persons_1.keys()
                ids_2 = persons_2.keys()

                # Regel-Symbol aus zyklischem Pattern
                rule_symbol = rule[idx % len(rule)]

                if rule_symbol == '-':
                    # Different Cast: Keine Person darf in beiden Events sein
                    overlap = ids_1 & ids_2
                    if overlap:
                        overlap_names = [persons_1[pid] for pid in overlap]
                        errors.append(ValidationError(
                            category="Different-Cast-Regel verletzt",
                            message=(
                                f'{event_1.location_plan_period.location_of_work.name}:<br>'
                                f'{event_1.date:%d.%m.%y} ({event_1.time_of_day.name}) und '
                                f'{event_2.date:%d.%m.%y} ({event_2.time_of_day.name})<br>'
                                f'Doppelt besetzt: {", ".join(overlap_names)}'
                            )
                        ))

                elif rule_symbol == '~':
                    # Same Cast: Gleiche Personen (mit erlaubter Differenz durch unterschiedliche nr_actors)
                    allowed_diff = abs(cg_1.nr_actors - cg_2.nr_actors)

                    # Symmetrische Differenz = Personen die nur in einem der beiden Events sind
                    sym_diff = ids_1 ^ ids_2
                    actual_diff = len(sym_diff)

                    if actual_diff > allowed_diff:
                        diff_in_1 = ids_1 - ids_2
                        diff_in_2 = ids_2 - ids_1

                        diff_names_1 = [persons_1[pid] for pid in diff_in_1]
                        diff_names_2 = [persons_2[pid] for pid in diff_in_2]

                        details = []
                        if diff_names_1:
                            details.append(f'Nur am {event_1.date:%d.%m.%y}: {", ".join(diff_names_1)}')
                        if diff_names_2:
                            details.append(f'Nur am {event_2.date:%d.%m.%y}: {", ".join(diff_names_2)}')
                        
                        errors.append(ValidationError(
                            category="Same-Cast-Regel verletzt",
                            message=(
                                f'{event_1.location_plan_period.location_of_work.name}:<br>'
                                f'{event_1.date:%d.%m.%y} ({event_1.time_of_day.name}) und '
                                f'{event_2.date:%d.%m.%y} ({event_2.time_of_day.name})<br>'
                                f'Erlaubte Abweichung: {allowed_diff}, Tatsächlich: {actual_diff}<br>'
                                f'{"; ".join(details)}'
                            )
                        ))
        
        return errors
