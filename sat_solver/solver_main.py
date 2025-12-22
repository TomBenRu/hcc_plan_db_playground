import dataclasses
import logging
import os
import sys
import time
from collections import defaultdict
import datetime
from datetime import date
from typing import Generator
from uuid import UUID


# Folgende Funktion wird nicht mehr gebraucht,
# durch direktes hinzufügen der DLLs (--add-data) in auto_py_to_exe_conf.json
def setup_ortools_dlls():
    """
    OR-Tools DLLs nur bei Bedarf laden (Performance-Optimierung).
    
    Lädt OR-Tools DLLs aus dem PyInstaller Bundle nur wenn der Solver
    tatsächlich verwendet wird, anstatt beim Anwendungsstart.
    Dies reduziert die Startup-Zeit erheblich.
    """
    if hasattr(sys, '_MEIPASS'):  # PyInstaller Bundle-Umgebung
        ortools_dir = os.path.join(sys._MEIPASS, '.ortools_libs')
        if os.path.exists(ortools_dir):
            try:
                # Windows-spezifisch: DLL-Verzeichnis zur Suche hinzufügen
                os.add_dll_directory(ortools_dir)
                logging.info(f"OR-Tools DLLs aus {ortools_dir} für Solver-Verwendung geladen")
            except (AttributeError, OSError) as e:
                # Fallback für ältere Python-Versionen oder andere OS
                logging.warning(f"Konnte OR-Tools DLL-Verzeichnis nicht hinzufügen: {e}")
    else:
        # Entwicklungsumgebung - keine spezielle DLL-Behandlung erforderlich
        pass

from ortools.sat.cp_model_pb2 import CpSolverStatus
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

from configuration.project_paths import curr_user_path_handler
from database import db_services, schemas
from configuration.solver import curr_config_handler
from database.schemas import AppointmentCreate
from gui.observer import signal_handling
from sat_solver import solver_variables
from sat_solver.avail_day_group_tree import (AvailDayGroup, get_avail_day_group_tree, AvailDayGroupTree,
                                                get_combined_avail_day_group_tree)
from sat_solver.cast_group_tree import get_cast_group_tree, CastGroupTree, CastGroup, get_combined_cast_group_tree
from sat_solver.event_group_tree import (get_event_group_tree, EventGroupTree, EventGroup,
                                         get_combined_event_group_tree)
from tools.helper_functions import generate_fixed_cast_clear_text, date_to_string

# Hilfsfunktionen aus constraints.helpers (ausgelagert zur Vermeidung von Circular Imports)
from sat_solver.constraints.helpers import (
    check_actor_location_prefs_fits_event,
    check_time_span_avail_day_fits_event,
)
# Constraint-Klassen für typsicheres get_constraint()
from sat_solver.constraints import (
    UnsignedShiftsConstraint,
    RelShiftDeviationsConstraint,
    WeightsInAvailDayGroupsConstraint,
    WeightsInEventGroupsConstraint,
    LocationPrefsConstraint,
    PartnerLocationPrefsConstraint,
    FixedCastConflictsConstraint,
    SkillsConstraint,
    CastRulesConstraint,
    PreferFixedCastConstraint, ConstraintRegistry,
)

cp_sat_logger = logging.getLogger(__name__)
handler = logging.FileHandler(os.path.join(curr_user_path_handler.get_config().log_file_path, 'cp-sat-solver.log'))
custom_format = logging.Formatter('')
handler.setFormatter(custom_format)
cp_sat_logger.addHandler(handler)
cp_sat_logger.propagate = False

def generate_adjusted_requested_assignments(assigned_shifts: int, possible_assignments: dict[UUID, int],
                                            entities: 'Entities') -> dict[UUID, float]:
    """
    Berechnet faire Einsätze für eine einzelne PlanPeriod auf ActorPlanPeriod-Ebene.

    Args:
        assigned_shifts: Gesamte Anzahl an zu verteilenden Einsätzen
        possible_assignments: Dict mit ActorPlanPeriod ID -> max. mögliche Einsätze
        entities: Entities-Objekt mit Solver-Daten

    Returns:
        Dict mit ActorPlanPeriod ID -> faire Anzahl Einsätze (float)
    """
    # fixme: unkorrekt mit avail_day_group Einschränkungen

    def adjust_requested_assignments(requested_assignments: dict[UUID, int],
                                     avail_assignments: float) -> dict[UUID, float]:
        requested_assignments_new: dict[UUID, float] = {}
        while True:
            mean_nr_assignments: float = avail_assignments / len(requested_assignments)
            requested_greater_than_mean: dict[UUID, int] = {}
            requested_smaller_than_mean: dict[UUID, int] = {}
            for app_id, requested in requested_assignments.items():
                if requested >= mean_nr_assignments:
                    requested_greater_than_mean[app_id] = requested
                else:
                    requested_smaller_than_mean[app_id] = requested

            if not requested_smaller_than_mean:
                requested_assignments_new.update({i: avail_assignments / len(requested_greater_than_mean)
                                                  for i in requested_greater_than_mean})
                break
            else:
                requested_assignments_new |= requested_smaller_than_mean
                avail_assignments -= sum(requested_smaller_than_mean.values())
                requested_assignments = requested_greater_than_mean.copy()
                if not requested_assignments:
                    break
        return requested_assignments_new

    # Dictionary mit ActorPlanPeriod ID -> requested_assignments welche nicht required sind
    requested_assignments: dict[UUID, int] = {
        app_id: min(entities.actor_plan_periods[app_id].requested_assignments, assignments)
        for app_id, assignments in possible_assignments.items()
        if not entities.actor_plan_periods[app_id].required_assignments
    }
    # Dictionary mit ActorPlanPeriod ID -> requested_assignments welche required sind
    required_assignments: dict[UUID, int] = {
        app_id: min(entities.actor_plan_periods[app_id].requested_assignments, assignments)
        for app_id, assignments in possible_assignments.items()
        if entities.actor_plan_periods[app_id].required_assignments
    }

    avail_assignments: int = assigned_shifts

    # 1. Verteile required_assignments faire auf ActorPlanPeriods, falls welche existieren
    if required_assignments:
        requested_assignments_new = adjust_requested_assignments(required_assignments, avail_assignments)
        avail_assignments -= sum(requested_assignments_new.values())
    # 2. Verteile requested_assignments faire auf ActorPlanPeriods, falls welche übrig sind
    else:
        requested_assignments_new = {}
    requested_assignments_new |= adjust_requested_assignments(requested_assignments, avail_assignments)

    # Setze die neuen requested_assignments in entities
    for app in entities.actor_plan_periods.values():
        app.requested_assignments = requested_assignments_new[app.id]

    return requested_assignments_new


def generate_adjusted_requested_assignments_multi_period(assigned_shifts_per_period: dict[UUID, int],
                                                         possible_assignments: dict[UUID, int],
                                                         entities: 'Entities') -> dict[UUID, float]:
    """
    Berechnet faire Einsätze über mehrere PlanPeriods hinweg auf Person-Ebene.

    Diese Funktion gruppiert ActorPlanPeriods nach Person und berechnet eine faire
    Verteilung der Gesamteinsätze über ALLE Perioden einer Person. Die Verteilung
    auf einzelne ActorPlanPeriods erfolgt proportional zum Minimum aus verfügbaren
    Tagen und requested_assignments.

    Args:
        assigned_shifts_per_period: Dict mit PlanPeriod ID -> Anzahl zu verteilender Einsätze
        possible_assignments: Dict mit ActorPlanPeriod ID -> max. mögliche Einsätze
        entities: Entities-Objekt mit Solver-Daten

    Returns:
        Dict mit ActorPlanPeriod ID -> faire Anzahl Einsätze (float)

    Beispiel:
        Person A hat 2 ActorPlanPeriods:
        - Januar: 5 verfügbare Tage, requested=5 → Basis: min(5,5) = 5
        - Februar: 20 verfügbare Tage, requested=20 → Basis: min(20,20) = 20

        Person A bekommt fair 15 Einsätze gesamt:
        - Januar:  15 * (5/25)  = 3.0 Einsätze
        - Februar: 15 * (20/25) = 12.0 Einsätze
    """

    def adjust_requested_assignments_for_persons(person_requested: dict[UUID, float],
                                                 avail_assignments: float) -> dict[UUID, float]:
        """
        Analog zur Original-Funktion, aber auf Person-Ebene.
        Verteilt Einsätze fair zwischen Personen basierend auf ihren Wünschen.
        """
        person_requested_new: dict[UUID, float] = {}

        print(
            f'DEBUG adjust_for_persons INPUT: person_requested={person_requested}, avail_assignments={avail_assignments}')

        while True:
            mean_nr_assignments = avail_assignments / len(person_requested)
            requested_greater_than_mean = {}
            requested_smaller_than_mean = {}

            for person_id, requested in person_requested.items():
                if requested >= mean_nr_assignments:
                    requested_greater_than_mean[person_id] = requested
                else:
                    requested_smaller_than_mean[person_id] = requested

            if not requested_smaller_than_mean:
                person_requested_new.update({
                    person_id: avail_assignments / len(requested_greater_than_mean)
                    for person_id in requested_greater_than_mean
                })
                break
            else:
                person_requested_new |= requested_smaller_than_mean
                avail_assignments -= sum(requested_smaller_than_mean.values())
                person_requested = requested_greater_than_mean.copy()
                if not person_requested:
                    break

        print(
            f'DEBUG adjust_for_persons OUTPUT: person_requested_new={person_requested_new}, sum={sum(person_requested_new.values())}')
        return person_requested_new

    def distribute_fair_requested_per_person_over_apps(app_requests: dict[UUID, float],
                                                       avail_assignments: float) -> dict[UUID, float]:
        """
        Verteilt die faire Anzahl an Einsätzen pro Person proportional über die ActorPlanPeriods der Person.
        Es kann dazu führen, dass die Gesamtzahl der ermittelten fairen Einsätze der Personen in einer Periode
        geringer oder höher ist als die Anzahl der verfügbaren Einsätze.
        Dieser Kompromiss bleibt mangels einer Idee zur besseren Lösung.
        """

        # TODO: Bessere Lösung finden (siehe Docstring)

        app_fair_assignments: dict[UUID, float] = {}
        while True:
            mean_nr_assignments = avail_assignments / len(app_requests)
            app_greater_than_mean = {}
            app_smaller_than_mean = {}

            for app_id, requested in app_requests.items():
                if requested >= mean_nr_assignments:
                    app_greater_than_mean[app_id] = requested
                else:
                    app_smaller_than_mean[app_id] = requested

            if not app_smaller_than_mean:
                app_fair_assignments.update({
                    app_id: avail_assignments / len(app_greater_than_mean)
                    for app_id in app_greater_than_mean
                })
                break
            else:
                app_fair_assignments |= app_smaller_than_mean
                avail_assignments -= sum(app_smaller_than_mean.values())
                app_requests = app_greater_than_mean.copy()
                if not app_requests:
                    break

        return app_fair_assignments

    person_to_requested: defaultdict[UUID, defaultdict[UUID, float]] = defaultdict(lambda: defaultdict(float))
    for app_id, max_assignments in possible_assignments.items():
        person_id = entities.actor_plan_periods[app_id].person.id
        requested = entities.actor_plan_periods[app_id].requested_assignments
        person_to_requested[person_id][app_id] = min(requested, max_assignments)

    fair_requested_per_person = adjust_requested_assignments_for_persons(
        {p_id: sum(app_requests.values()) for p_id, app_requests in person_to_requested.items()},
        sum(assigned_shifts_per_period.values())
    )
    distribution_per_person_over_apps: defaultdict[UUID, dict[UUID, float]] = defaultdict(lambda: defaultdict(float))
    for person_id, fair_requested in fair_requested_per_person.items():
        distribution_per_person_over_apps[person_id] = distribute_fair_requested_per_person_over_apps(
            person_to_requested[person_id],
            fair_requested
        )

    fair_assignments: dict[UUID, float] = {}
    for person_id, app_fair_assignments in distribution_per_person_over_apps.items():
        fair_assignments |= app_fair_assignments
        for app_id, fair in app_fair_assignments.items():
            entities.actor_plan_periods[app_id].requested_assignments = fair

    return fair_assignments




class PartialSolutionCallback(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, unassigned_shifts_per_event: list[IntVar],
                 sum_assigned_shifts: dict[UUID, IntVar], sum_squared_deviations: IntVar,
                 fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], IntVar], limit: int | None,
                 print_results: bool, entities: 'Entities', collect_schedule_versions=False):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self._unassigned_shifts_per_event = unassigned_shifts_per_event
        self._solution_count = 0
        self._sum_assigned_shifts = sum_assigned_shifts
        self._sum_squared_deviations = sum_squared_deviations
        self._fixed_cast_conflicts = fixed_cast_conflicts
        self._solution_limit = limit
        self._max_assigned_shifts: defaultdict[UUID, int] = defaultdict(int)
        self._sum_max_assigned = 0
        self._count_same_max_assigned = 0
        self._print_results = print_results
        self._entities = entities
        self._collect_schedule_versions = collect_schedule_versions
        self._curr_objective_value = float('inf')
        self._num_equal_objective_values = 0

        self._schedule_versions: list[list[schemas.AppointmentCreate]] = []

    def on_solution_callback(self):
        # print(f'{self.ObjectiveValue()=}')
        if abs(self._curr_objective_value - self.ObjectiveValue()) <= 50:
#             print('abs(self._curr_objective_value - self.ObjectiveValue()) <= 50')
            self._num_equal_objective_values += 1
        else:
            self._num_equal_objective_values = 0
        if self._num_equal_objective_values == 5:
            self.StopSearch()
        self._curr_objective_value = self.ObjectiveValue()
        self._solution_count += 1
        if self._print_results:
            self.print_results()
        if self._collect_schedule_versions:
            self.collect_schedule_versions()

        for app_id, s in self._sum_assigned_shifts.items():
            self._max_assigned_shifts[app_id] = max(self._max_assigned_shifts[app_id], self.Value(s))

        if self._solution_limit and self._solution_count >= self._solution_limit:
#             print(f"Stop search after {self._solution_count} solutions")
            self.StopSearch()


    def count_same_max_assigned_shifts(self):
        old_sum_max_assigned = self._sum_max_assigned
        if (new_sum_max_assigned := sum(self._max_assigned_shifts.values())) != old_sum_max_assigned:
            self._sum_max_assigned = new_sum_max_assigned
            self._count_same_max_assigned = 0
        else:
            self._count_same_max_assigned += 1

    def collect_schedule_versions(self):
        self._schedule_versions.append([])

        for event_group in sorted(list(self._entities.event_groups_with_event.values()),
                                  key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index)):
            if not self.Value(self._entities.event_group_vars[event_group.event_group_id]):
                continue
            scheduled_adg_ids = []
            for (adg_id, eg_id), var in self._entities.shift_vars.items():
                if eg_id == event_group.event_group_id and self.Value(var):
                    scheduled_adg_ids.append(adg_id)
            event = event_group.event
            avail_days = [self._entities.avail_day_groups_with_avail_day[agd_id].avail_day for agd_id in scheduled_adg_ids]
            self._schedule_versions[-1].append(schemas.AppointmentCreate(avail_days=avail_days, event=event))

    def print_results(self):
        return
        print(f"Solution {self._solution_count}")
        # self.print_shifts()
        print('unassigned_shifts_per_event:',
              [self.Value(unassigned_shifts) for unassigned_shifts in self._unassigned_shifts_per_event])
        sum_assigned_shifts_per_employee = {self._entities.actor_plan_periods[app_id].person.f_name: self.Value(s)
                                            for app_id, s in self._sum_assigned_shifts.items()}
        print(f'sum_assigned_shifts_of_employees: {sum_assigned_shifts_per_employee}')
        print(f'sum_squared_deviations: {self.Value(self._sum_squared_deviations)}')
        fixed_cast_conflicts = {f'{date:%d.%m.%y} ({time_of_day}) {cast_group_id}': self.Value(var)
                                for (date, time_of_day, cast_group_id), var in self._fixed_cast_conflicts.items()}
        print(f'fixed_cast_conflicts: {fixed_cast_conflicts}')
        print('-----------------------------------------------------------------------------------------------------')
        # for app_id, app in self._entities.actor_plan_periods.items():
        #     group_vars = {
        #         self._entities.avail_day_groups_with_avail_day[adg_id].avail_day.date: self.Value(var)
        #         for adg_id, var in self._entities.avail_day_group_vars.items()
        #         if (adg_id in self._entities.avail_day_groups_with_avail_day
        #             and self._entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.id == app_id)}
        #     print(f'active_avail_day_groups of {app.person.f_name}: {group_vars}')

    def print_shifts(self):
        return
        for event_group in sorted(list(self._entities.event_groups_with_event.values()),
                                  key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index)):
            if not self.Value(self._entities.event_group_vars[event_group.event_group_id]):
                continue
            print(f"Day {event_group.event.date: '%d.%m.%y'} ({event_group.event.time_of_day.name}) "
                  f"in {event_group.event.location_plan_period.location_of_work.name}")
            for actor_plan_period in self._entities.actor_plan_periods.values():
                if sum(self.Value(self._entities.shift_vars[(avd_id, event_group.event_group_id)])
                       for avd_id in actor_plan_period.avail_day_group_ids):
                    print(f"   {actor_plan_period.person.f_name} "
                          f"works in {event_group.event.location_plan_period.location_of_work.name:}")

    def get_max_assigned_shifts(self):
        return self._max_assigned_shifts

    def get_schedule_versions(self):
        return self._schedule_versions

    def solution_count(self):
        return self._solution_count


# Re-Export aus data_loading für Rückwärtskompatibilität
# WICHTIG: Diese Komponenten wurden nach data_loading.py ausgelagert,
# um OR-Tools Threading-Crash zu vermeiden (siehe HANDOVER_ortools_threading_crash_fix)
from sat_solver.data_loading import (
    Entities,
    create_data_models,
    create_data_models_multi_period,
    populate_shifts_exclusive,
)


def create_vars(model: cp_model.CpModel, event_group_tree: EventGroupTree, 
                avail_day_group_tree: AvailDayGroupTree, entities: Entities) -> None:
    """
    Erstellt alle Solver-Variablen und füllt entities damit.
    
    Args:
        model: Das CP-SAT Model
        event_group_tree: Baum der Event-Gruppen
        avail_day_group_tree: Baum der Verfügbarkeits-Tage-Gruppen
        entities: Entities-Objekt zum Befüllen mit Variablen
    """
    entities.event_group_vars = {
        event_group.event_group_id: model.NewBoolVar(f'')
        for event_group in event_group_tree.root.descendants
        if event_group.children or event_group.event
    }
    entities.avail_day_group_vars = {
        avail_day_group.avail_day_group_id: model.NewBoolVar(f'')
        for avail_day_group in avail_day_group_tree.root.descendants
        if avail_day_group.children or avail_day_group._avail_day_id
    }

    populate_shifts_exclusive(entities)
    
    # Erstelle shift_vars für den Solver
    for adg_id, adg in entities.avail_day_groups_with_avail_day.items():
        for event_group_id, event_group in entities.event_groups_with_event.items():
            entities.shift_vars[(adg_id, event_group_id)] = model.NewBoolVar(
                f'shift ({adg.avail_day.actor_plan_period.person.f_name},{adg.avail_day.date:%d.%m.%y}, {event_group_id})')
    # print(f'{len(entities.shift_vars)=}')
    # print(f'{sum(entities.shifts_exclusive.values())=}')



def add_constraint_requested_assignments_multi_period(model: cp_model.CpModel):
    """
    Wenn mehrere Planperioden gleichzeitig berechnet werden, wird die Anzahl der Leaves der einzelnen
    Master-AvailDayGroups genommen und die Summe der zugehörigen shift_vars
    mit den requested_assignments der ActorPlanPeriods verglichen und jeweils Strafpunkte vergeben.
    Bei required_assignments wird eine hard-constraint eingefügt.
    """
    pass


def constraint_max_shift_of_app(model: cp_model.CpModel, app_id: UUID, entities: 'Entities'):
    """
    Wird verwendet um die maximal möglichen Shifts eines Mitarbeiters zu bestimmen.
    """
    max_shifts_of_app = model.NewIntVar(0, 1000, 'max_sifts')
    model.Add(
        max_shifts_of_app == sum(
            shift_var for (adg, eg), shift_var in entities.shift_vars.items()
            if entities.avail_day_groups_with_avail_day[adg].avail_day.actor_plan_period.id == app_id
        )
    )
    return max_shifts_of_app



def create_constraints(model: cp_model.CpModel, entities: 'Entities', 
                       creating_test_constraints: bool = False) -> ConstraintRegistry:
    """
    Erstellt alle Solver-Constraints mit der Registry-Architektur.
    
    Args:
        model: Das CP-SAT Model
        entities: Entities-Objekt mit Solver-Daten
        creating_test_constraints: Wenn True, werden RequiredAvailDayGroups übersprungen
        
    Returns:
        ConstraintRegistry mit allen registrierten und angewendeten Constraints
    """
    # Imports für Constraint-Klassen
    from sat_solver.constraints import (
        LocationPrefsConstraint,
        EmployeeAvailabilityConstraint,
        EventGroupsActivityConstraint,
        AvailDayGroupsActivityConstraint,
        NumShiftsInAvailDayGroupsConstraint,
        PartnerLocationPrefsConstraint,
        WeightsInAvailDayGroupsConstraint,
        WeightsInEventGroupsConstraint,
        SkillsConstraint,
        UnsignedShiftsConstraint,
        RequiredAvailDayGroupsConstraint,
        DifferentCastsSameDayConstraint,
        RelShiftDeviationsConstraint,
        CastRulesConstraint,
        FixedCastConflictsConstraint,
        PreferFixedCastConstraint,
    )
    
    # Registry erstellen
    registry = ConstraintRegistry(entities, model)
    
    # Phase 2.1 - Hard Constraints
    registry.register(EmployeeAvailabilityConstraint)
    registry.register(EventGroupsActivityConstraint)
    registry.register(AvailDayGroupsActivityConstraint)
    
    # RequiredAvailDayGroups nur bei normalem Solving, nicht bei Test-Constraints
    if not creating_test_constraints:
        registry.register(RequiredAvailDayGroupsConstraint)
    
    registry.register(NumShiftsInAvailDayGroupsConstraint)
    
    # Phase 2.2 - Soft Constraints mit Penalties
    registry.register(WeightsInAvailDayGroupsConstraint)
    registry.register(LocationPrefsConstraint)
    registry.register(PartnerLocationPrefsConstraint)
    registry.register(UnsignedShiftsConstraint)
    registry.register(WeightsInEventGroupsConstraint)
    registry.register(CastRulesConstraint)
    registry.register(SkillsConstraint)
    registry.register(FixedCastConflictsConstraint)
    registry.register(PreferFixedCastConstraint)
    
    # Phase 2.3 - Komplexe Constraints
    registry.register(DifferentCastsSameDayConstraint)
    registry.register(RelShiftDeviationsConstraint)
    
    # Alle Constraints anwenden
    registry.apply_all()
    
    return registry


def create_constraint_max_shift_of_app(model: cp_model.CpModel, app_id: UUID, entities: 'Entities') -> IntVar:
    return constraint_max_shift_of_app(model, app_id, entities)


def define_objective_minimize(model: cp_model.CpModel, registry: 'ConstraintRegistry') -> None:
    """
    Definiert die Objective-Funktion als gewichtete Summe aller Constraint-Penalties.
    
    Args:
        model: Das CP-SAT Model
        registry: Die ConstraintRegistry mit allen registrierten Constraints
    """
    model.Minimize(registry.get_total_weighted_penalty())


def define_objective__max_shift_of_app(model: cp_model.CpModel,
                                       unassigned_shifts: int, sum_location_prefs: int, sum_partner_loc_prefs: int,
                                       sum_fixed_cast_conflicts: int, sum_cast_rules: int,
                                       unassigned_shifts_per_event: dict[UUID, IntVar],
                                       constraints_location_prefs: list[IntVar],
                                       constraints_partner_loc_prefs: list[IntVar],
                                       constraints_fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], IntVar],
                                       skill_conflict_vars: list[IntVar],
                                       max_shift_of_app: IntVar,
                                       constraints_prefer_fixed_cast: list[IntVar]
                                       ):
    # Mit den Constraints für location_prefs und partner_loc_prefs werden falsche max_shifts_per_app berechnet.
    model.Add(sum(constraints_location_prefs) == sum_location_prefs)
    # model.Add(sum(constraints_partner_loc_prefs) == sum_partner_loc_prefs)
    model.Add(sum(constraints_fixed_cast_conflicts.values()) == sum_fixed_cast_conflicts)
    model.Add(sum(skill_conflict_vars) == 0)
    model.Add(sum(list(unassigned_shifts_per_event.values())) == unassigned_shifts)
    # Preference-Constraints werden NICHT erzwungen bei max_shifts Berechnung
    # (nur die Obergrenze finden, Preferences sind für finale Plan-Erstellung relevant)
    model.Maximize(max_shift_of_app * 100)


def define_objective__fixed_unassigned(model: cp_model.CpModel,
                                       unassigned_shifts: int, sum_location_prefs: int, sum_partner_loc_prefs: int,
                                       sum_fixed_cast_conflicts: int, sum_cast_rules: int,
                                       unassigned_shifts_per_event: dict[UUID, IntVar],
                                       constraints_location_prefs: list[IntVar],
                                       constraints_partner_loc_prefs: list[IntVar],
                                       constraints_fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], IntVar],
                                       constraints_cast_rule: list[IntVar]):
    model.Add(sum(constraints_location_prefs) == sum_location_prefs)
    model.Add(sum(constraints_partner_loc_prefs) == sum_partner_loc_prefs)
    model.Add(sum(constraints_fixed_cast_conflicts.values()) == sum_fixed_cast_conflicts)
    model.Add(sum(list(unassigned_shifts_per_event.values())) == unassigned_shifts)


def define_objective__fixed_constraint_results(
        model: cp_model.CpModel, unassigned_shifts_per_event: list[IntVar], sum_squared_deviations: IntVar,
        constraints_weights_in_avail_day_groups: list[IntVar],
        constraints_weights_in_event_groups: list[IntVar],
        constraints_location_prefs: list[IntVar], constraints_partner_loc_prefs: list[IntVar],
        constraints_fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], IntVar],
        constraints_cast_rule: list[IntVar],
        constraints_prefer_fixed_cast: list[IntVar],
        unassigned_shifts_per_event_res: list[int], sum_squared_deviations_res: int,
        weights_shifts_in_avail_day_groups_res: int, weights_in_event_groups_res: int, sum_location_prefs_res: int,
        sum_partner_loc_prefs_res: int, sum_fixed_cast_conflicts_res: int, sum_cast_rules_res: int,
        sum_prefer_fixed_cast_res: int):
    model.Add(sum(unassigned_shifts_per_event) == sum(unassigned_shifts_per_event_res))
    model.Add(sum_squared_deviations == sum_squared_deviations_res)
    model.Add(sum(constraints_weights_in_avail_day_groups) == weights_shifts_in_avail_day_groups_res)
    model.Add(sum(constraints_weights_in_event_groups) == weights_in_event_groups_res)
    model.Add(sum(constraints_location_prefs) == sum_location_prefs_res)
    model.Add(sum(constraints_partner_loc_prefs) == sum_partner_loc_prefs_res)
    model.Add(sum(constraints_fixed_cast_conflicts.values()) == sum_fixed_cast_conflicts_res)
    model.Add(sum(constraints_cast_rule) == sum_cast_rules_res)
    model.Add(sum(constraints_prefer_fixed_cast) == sum_prefer_fixed_cast_res)


solver: cp_model.CpSolver | None = None


def solve_model_with_solver_solution_callback(
        model: cp_model.CpModel, unassigned_shifts_per_event: list[IntVar],
        sum_assigned_shifts: dict[UUID, IntVar],
        sum_squared_deviations: IntVar,
        constraints_fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], IntVar],
        print_solution_printer_results: bool,
        limit: int | None,
        log_search_process: bool,
        entities: 'Entities',
        collect_schedule_versions: bool) -> tuple[cp_model.CpSolver, PartialSolutionCallback, CpSolverStatus]:
    # Solve the model.
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = log_search_process
    solver.parameters.randomize_search = True
    solver.parameters.linearization_level = 0
    solver.parameters.enumerate_all_solutions = True
    solution_printer = PartialSolutionCallback(unassigned_shifts_per_event,
                                               sum_assigned_shifts,
                                               sum_squared_deviations,
                                               constraints_fixed_cast_conflicts,
                                               limit, print_solution_printer_results,
                                               entities,
                                               collect_schedule_versions)

    status = solver.Solve(model, solution_printer)

    return solver, solution_printer, status


def solve_model_to_optimum(model: cp_model.CpModel, max_search_time: int,
                           log_search_process: bool) -> tuple[cp_model.CpSolver, CpSolverStatus]:
    # Solve the model.
    solver = cp_model.CpSolver()
    solver.parameters.mip_max_activity_exponent = 62
    solver.parameters.log_search_progress = log_search_process
    solver.log_callback = cp_sat_logger.info
    # If using a custom log function, you can disable logging to stdout
    solver.parameters.log_to_stdout = False
    solver.parameters.linearization_level = 0
    solver.parameters.enumerate_all_solutions = False
    solver.parameters.max_time_in_seconds = max_search_time

    status = solver.Solve(model)

    return solver, status


def print_statistics(solver: cp_model.CpSolver, solution_printer: PartialSolutionCallback | None,
                     unassigned_shifts_per_event: dict[UUID, IntVar], sum_assigned_shifts: dict[UUID, IntVar],
                     sum_squared_deviations: IntVar, constraints_partner_loc_prefs: list[IntVar],
                     constraints_location_prefs: list[IntVar],
                     constraints_fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], IntVar],
                     constraints_weights_in_event_groups: list[IntVar],
                     constraints_weights_in_av_day_groups: list[IntVar], constraints_cast_rule: list[IntVar]):
    # Statistics.
    return
    print("\nStatistics")
    print(f"  - conflicts      : {solver.NumConflicts()}")
    print(f"  - branches       : {solver.NumBranches()}")
    print(f"  - wall time      : {solver.WallTime()} s")
    print(f'  - ObjectiveValue : {solver.ObjectiveValue()}')
    if solution_printer:
        print(f"  - solutions found: {solution_printer.solution_count()}")
    print(f'{sum(solver.Value(u) for u in unassigned_shifts_per_event.values())=}')
    print(f'{[solver.Value(u) for u in unassigned_shifts_per_event.values()]}')
    print(f'{solver.Value(sum_squared_deviations)=}')
    print(f'{sum(solver.Value(a) for a in sum_assigned_shifts.values())=}')
    print(f'location_prefs: {[(u.name ,solver.Value(u)) for u in constraints_location_prefs]}')
    print(f'sum_location_prefs: {solver.Value(sum(constraints_location_prefs))}')
    print(f'partner_loc_prefs: {[(u.name ,solver.Value(u)) for u in constraints_partner_loc_prefs]}')
    print(f'sum_partner_loc_prefs: {solver.Value(sum(constraints_partner_loc_prefs))}')
    print(f'fixed_cast_conflicts: {solver.Value(sum(constraints_fixed_cast_conflicts.values()))}')

    fixed_cast_conflicts = {f'{date:%d.%m.%y} ({time_of_day}), {cast_group_id}': solver.Value(var)
                            for (date, time_of_day, cast_group_id), var in constraints_fixed_cast_conflicts.items()}

    print(f'weights_in_event_groups: '
          f'{" | ".join([f"""{v.name}: {solver.Value(v)}""" for v in constraints_weights_in_event_groups])}')
    print(f'sum_weights_in_event_groups: {sum(solver.Value(w) for w in constraints_weights_in_event_groups)}')
    print(f'weights_in_av_day_groups: '
          f'{" | ".join([f"""{v.name}: {solver.Value(v)}""" for v in constraints_weights_in_av_day_groups])}')
    print(f'sum_weights_in_av_day_groups: {sum(solver.Value(w) for w in constraints_weights_in_av_day_groups)}')
    print(f'constraints_cast_rule: {" | ".join([f"""{v.name}: {solver.Value(v)}""" for v in constraints_cast_rule])}')
    print(f'sum_constraints_cast_rule: {sum(solver.Value(w) for w in constraints_cast_rule)}')


def print_solver_status(model: cp_model.CpModel, status: CpSolverStatus) -> tuple[bool, list[str]]:
    if status == cp_model.MODEL_INVALID:
        # print('########################### INVALID MODEL ######################################')
        return False, []
    elif status == cp_model.OPTIMAL:
#         print('########################### OPTIMAL ############################################')
        return True, []
    elif status == cp_model.FEASIBLE:
#         print('########################### FEASIBLE ############################################')
        return True, []
    elif status == cp_model.INFEASIBLE:
#         print('########################### INFEASIBLE ############################################')
#         for i in solver.SufficientAssumptionsForInfeasibility():
#             print(model.GetIntVarFromProtoIndex(i).name)
        return False, [model.GetIntVarFromProtoIndex(i).name for i in solver.SufficientAssumptionsForInfeasibility()]
    else:
#         print('########################### FAILED ############################################')
        return False, []


def call_solver_with_unadjusted_requested_assignments(
        event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree, 
        entities: 'Entities', max_search_time: int,
        log_search_process: bool) -> tuple[dict[UUID, int], int, int, int,
                                           dict[tuple[datetime.date, str, UUID], int], dict[str, int], int, bool]:
    """
    Ruft den Solver auf, um die maximale Anzahl an Einsätzen zu bestimmen, die in die verfügbaren Schichten passen.

    Es werden keine Fairness-Constraints berücksichtigt.

    Arguments:
        event_group_tree: Baum der Event-Gruppen
        avail_day_group_tree: Baum der Verfügbarkeits-Tage-Gruppen
        entities: Entities-Objekt mit Solver-Daten
        max_search_time: Maximale Suchzeit in Sekunden
        log_search_process: Ob Solver-Prozess geloggt werden soll

    Returns:
        Tuple mit (max_shifts_per_app, sum_location_prefs, sum_partner_loc_prefs, sum_fixed_cast_conflicts,
                   fixed_cast_conflicts, skill_conflicts, sum_cast_rules, success)
    """

    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree, entities)
    solver_variables.cast_rules.reset_fields()
    
    # Registry-basierte Constraints
    registry = create_constraints(model, entities)
    
    # Constraints aus Registry holen
    unsigned_shifts: UnsignedShiftsConstraint = registry.get_constraint(UnsignedShiftsConstraint)
    rel_shift_deviations: RelShiftDeviationsConstraint = registry.get_constraint(RelShiftDeviationsConstraint)
    weights_in_avail_day_groups: WeightsInAvailDayGroupsConstraint = (registry.
                                                                      get_constraint(WeightsInAvailDayGroupsConstraint))
    weights_in_event_groups: WeightsInEventGroupsConstraint = registry.get_constraint(WeightsInEventGroupsConstraint)
    location_prefs: LocationPrefsConstraint = registry.get_constraint(LocationPrefsConstraint)
    partner_location_prefs: PartnerLocationPrefsConstraint = registry.get_constraint(PartnerLocationPrefsConstraint)
    fixed_cast_conflicts: FixedCastConflictsConstraint = registry.get_constraint(FixedCastConflictsConstraint)
    skills: SkillsConstraint = registry.get_constraint(SkillsConstraint)
    cast_rules: CastRulesConstraint = registry.get_constraint(CastRulesConstraint)
    prefer_fixed_cast: PreferFixedCastConstraint = registry.get_constraint(PreferFixedCastConstraint)
    
    define_objective_minimize(model, registry)
    # print('\n\n++++++++++++++++++++++++++++++++++++++ New Solution +++++++++++++++++++++++++++++++++++++++++++++++++++')
    solver, solver_status = solve_model_to_optimum(model, max_search_time, log_search_process)

    success, problems = print_solver_status(model, solver_status)
    if not success:
        return 0, 0, 0, 0, {}, {}, 0, False

    print_statistics(solver, None, unsigned_shifts.unassigned_shifts_per_event,
                     rel_shift_deviations.sum_assigned_shifts, rel_shift_deviations.sum_squared_deviations,
                     partner_location_prefs.penalty_vars, location_prefs.penalty_vars,
                     fixed_cast_conflicts.fixed_cast_vars,
                     weights_in_event_groups.penalty_vars,
                     weights_in_avail_day_groups.penalty_vars, cast_rules.penalty_vars)
    unassigned_shifts = sum(solver.Value(u) for u in unsigned_shifts.unassigned_shifts_per_event.values())

    return ({app_id: solver.Value(a) for app_id, a in rel_shift_deviations.sum_assigned_shifts.items()},
            unassigned_shifts,
            solver.Value(sum(location_prefs.penalty_vars)),
            solver.Value(sum(partner_location_prefs.penalty_vars)),
            {key: solver.Value(int_var) for key, int_var in fixed_cast_conflicts.fixed_cast_vars.items()},
            {skill_var.name: solver.Value(skill_var) for skill_var in skills.penalty_vars},
            solver.Value(sum(cast_rules.penalty_vars)),
            success)


def extract_assignments_by_period(assigned_shifts: dict[UUID, int], plan_period_ids: list[UUID],
                                  entities: 'Entities') -> dict[UUID, int]:
    """
    Extrahiert die Anzahl der zugewiesenen Einsätze pro PlanPeriod aus dem Dictionary der ActorPlanPeriods.
    Args:
        assigned_shifts: Dictionary mit ActorPlanPeriod ID als Key und Anzahl der zugewiesenen Einsätze als Value
        plan_period_ids: Liste der PlanPeriod IDs
        entities: Entities-Objekt mit Solver-Daten

    Returns:
        Dictionary mit PlanPeriod ID als Key und Anzahl der zugewiesenen Einsätze als Value
    """
    plan_period_shifts = {pp_id: 0 for pp_id in plan_period_ids}
    for app_id, shifts in assigned_shifts.items():
        app = entities.actor_plan_periods[app_id]
        pp_id = app.plan_period.id
        plan_period_shifts[pp_id] += shifts
    return plan_period_shifts


def call_solver_to_get_max_shifts_per_app(
        event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree, 
        entities: 'Entities', unassigned_shifts: int,
        sum_location_prefs: int, sum_partner_loc_prefs: int, sum_fixed_cast_conflicts: int, sum_cast_rules: int,
        assigned_shifts: dict[UUID, int], max_search_time: int,
        log_search_process: bool) -> Generator[tuple[bool, UUID], None, tuple[bool, dict[UUID, int]]]:
    """
    Berechnet für jeden Mitarbeiter die maximal mögliche Anzahl von Einsätzen.
    
    Die faire Verteilung wird separat durch get_fair_distribution_multi_period() berechnet.
    """

    max_shifts_of_apps = {}
    for app_id in entities.actor_plan_periods.keys():
        model = cp_model.CpModel()
        create_vars(model, event_group_tree, avail_day_group_tree, entities)
        solver_variables.cast_rules.reset_fields()
        
        # Registry-basierte Constraints
        registry = create_constraints(model, entities)
        
        # Constraints aus Registry holen
        unsigned_shifts: UnsignedShiftsConstraint = registry.get_constraint(UnsignedShiftsConstraint)
        location_prefs: LocationPrefsConstraint = registry.get_constraint(LocationPrefsConstraint)
        partner_location_prefs: PartnerLocationPrefsConstraint = registry.get_constraint(PartnerLocationPrefsConstraint)
        fixed_cast_conflicts: FixedCastConflictsConstraint = registry.get_constraint(FixedCastConflictsConstraint)
        skills: SkillsConstraint = registry.get_constraint(SkillsConstraint)
        prefer_fixed_cast: PreferFixedCastConstraint = registry.get_constraint(PreferFixedCastConstraint)

        max_shifts_of_app = create_constraint_max_shift_of_app(model, app_id, entities)

        define_objective__max_shift_of_app(
            model,
            unassigned_shifts,
            sum_location_prefs,
            sum_partner_loc_prefs,
            sum_fixed_cast_conflicts,
            sum_cast_rules,
            unsigned_shifts.unassigned_shifts_per_event,
            location_prefs.penalty_vars,
            partner_location_prefs.penalty_vars,
            fixed_cast_conflicts.fixed_cast_vars,
            skills.penalty_vars,
            max_shifts_of_app,
            prefer_fixed_cast.penalty_vars
        )

        solver, status = solve_model_to_optimum(model, max_search_time, log_search_process)

        yield True, app_id

        if success_problems := print_solver_status(model, status):
            max_shifts_of_apps[app_id] = solver.value(max_shifts_of_app)

        else:
            return False, {}, {}

    # print(f'{sum(max_shifts_of_apps.values())=}')


    return True, max_shifts_of_apps


def get_fair_distribution_multi_period(
    plan_period_ids: list[UUID],
    max_shifts_per_app: dict[UUID, int],
    assigned_shifts_per_period: dict[UUID, int]
) -> tuple[EventGroupTree, AvailDayGroupTree, 'Entities', dict[UUID, float]]:
    """
    Berechnet faire Verteilung über alle PlanPeriods.
    
    Diese Funktion erstellt Combined Trees und Data Models, um die entities.actor_plan_periods
    korrekt mit allen ActorPlanPeriods zu füllen. Dann wird die faire Multi-Period Verteilung
    basierend auf den bereits berechneten max_shifts berechnet.
    
    Args:
        plan_period_ids: Liste aller PlanPeriod IDs
        max_shifts_per_app: Bereits berechnete maximale Shifts pro ActorPlanPeriod
        assigned_shifts_per_period: Dict mapping plan_period_id zu assigned_shifts dieser Periode
        
    Returns:
        Tuple mit (event_group_tree, avail_day_group_tree, entities, fair_assignments)
    """
    # Combined Trees für alle Perioden erstellen
    event_group_tree = get_combined_event_group_tree(plan_period_ids)
    avail_day_group_tree = get_combined_avail_day_group_tree(plan_period_ids)
    cast_group_tree = get_combined_cast_group_tree(plan_period_ids)
    
    # Data Models mit ALLEN ActorPlanPeriods erstellen
    entities = create_data_models_multi_period(
        event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_ids
    )
    
    # Multi-Period faire Verteilung berechnen
    fair_assignments = generate_adjusted_requested_assignments_multi_period(
        assigned_shifts_per_period,
        max_shifts_per_app,
        entities
    )
    
    return event_group_tree, avail_day_group_tree, entities, fair_assignments


def get_fair_distribution(
    max_shifts_per_app: dict[UUID, int],
    total_assigned_shifts: int,
    entities: 'Entities'
) -> dict[UUID, float]:
    """
    Berechnet faire Verteilung für Single-Period.
    
    Args:
        max_shifts_per_app: Bereits berechnete maximale Shifts pro ActorPlanPeriod
        total_assigned_shifts: Gesamtanzahl der zuzuweisenden Shifts
        entities: Entities-Objekt mit Solver-Daten
        
    Returns:
        Dictionary mit fairen Shifts pro ActorPlanPeriod
    """
    fair_assignments = generate_adjusted_requested_assignments(
        total_assigned_shifts,
        max_shifts_per_app,
        entities
    )
    return fair_assignments


def call_solver_with_adjusted_requested_assignments(
        event_group_tree: EventGroupTree,
        avail_day_group_tree: AvailDayGroupTree,
        entities: 'Entities',
        max_search_time: int,
        log_search_process: bool) -> tuple[int, list[int], int, int, int, int,
                                           dict[tuple[datetime.date, str, UUID], int], int,
                                           list[schemas.AppointmentCreate], bool]:

    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree, entities)
    solver_variables.cast_rules.reset_fields()
    
    # Registry-basierte Constraints
    registry = create_constraints(model, entities)
    
    # Constraints aus Registry holen
    unsigned_shifts: UnsignedShiftsConstraint = registry.get_constraint(UnsignedShiftsConstraint)
    rel_shift_deviations: RelShiftDeviationsConstraint = registry.get_constraint(RelShiftDeviationsConstraint)
    weights_in_avail_day_groups: WeightsInAvailDayGroupsConstraint = (registry.
                                                                      get_constraint(WeightsInAvailDayGroupsConstraint))
    weights_in_event_groups: WeightsInEventGroupsConstraint = registry.get_constraint(WeightsInEventGroupsConstraint)
    location_prefs: LocationPrefsConstraint = registry.get_constraint(LocationPrefsConstraint)
    partner_location_prefs: PartnerLocationPrefsConstraint = registry.get_constraint(PartnerLocationPrefsConstraint)
    fixed_cast_conflicts: FixedCastConflictsConstraint = registry.get_constraint(FixedCastConflictsConstraint)
    skills: SkillsConstraint = registry.get_constraint(SkillsConstraint)
    cast_rules: CastRulesConstraint = registry.get_constraint(CastRulesConstraint)
    prefer_fixed_cast: PreferFixedCastConstraint = registry.get_constraint(PreferFixedCastConstraint)
    
    define_objective_minimize(model, registry)
    solver, solver_status = solve_model_to_optimum(model, max_search_time, log_search_process)
    # print('\n\n++++++++++++++++++++++++++++++++++++++ New Solution +++++++++++++++++++++++++++++++++++++++++++++++++++')
    success, problems = print_solver_status(model, solver_status)
    if not success:
        return 0, [], 0, 0, 0, 0, {}, 0, [], False
    
    # DEBUG: Zeige tatsächliche Penalty-Werte
    if prefer_fixed_cast.penalty_vars:
        print("\n" + "="*80)
        print("DEBUG: prefer_fixed_cast_events - Tatsächliche Penalty-Werte")
        print("="*80)
        total_penalty = 0
        penalty_details = []
        for penalty_var in prefer_fixed_cast.penalty_vars:
            penalty_value = solver.Value(penalty_var)
            total_penalty += penalty_value
            if penalty_value > 0:
                # Nur Penalties > 0 anzeigen (interessante Fälle)
                penalty_details.append(f"  ⚠️  Penalty={penalty_value}: {penalty_var.name}")
        
        if penalty_details:
            print(f"  Penalties > 0 gefunden ({len(penalty_details)} von {len(prefer_fixed_cast.penalty_vars)}):")
            for detail in penalty_details:
                print(detail)
        else:
            print(f"  ✅ Alle Penalties = 0 (alle bevorzugten Mitarbeiter wurden zugewiesen)")
        
        print(f"\nGesamtsumme Penalties: {total_penalty}")
        print("="*80 + "\n")
    print_statistics(solver, None, unsigned_shifts.unassigned_shifts_per_event,
                     rel_shift_deviations.sum_assigned_shifts, rel_shift_deviations.sum_squared_deviations,
                     partner_location_prefs.penalty_vars, location_prefs.penalty_vars,
                     fixed_cast_conflicts.fixed_cast_vars,
                     weights_in_event_groups.penalty_vars,
                     weights_in_avail_day_groups.penalty_vars, cast_rules.penalty_vars)

    event_group_id_avail_day_group_ids: dict[UUID, list[UUID]] = {}
    for (adg_id, eg_id), var in entities.shift_vars.items():
        if solver.Value(entities.event_group_vars[eg_id]):
            if not event_group_id_avail_day_group_ids.get(eg_id):
                event_group_id_avail_day_group_ids[eg_id] = []
        if solver.Value(var):
            event_group_id_avail_day_group_ids[eg_id].append(adg_id)

    appointments = []
    for eg_id, adg_ids in event_group_id_avail_day_group_ids.items():
        appointments.append(
            schemas.AppointmentCreate(
                avail_days=[entities.avail_day_groups_with_avail_day[adg_id].avail_day for adg_id in adg_ids],
                event=entities.event_groups_with_event[eg_id].event
            )
        )

    # solver.parameters.log_search_progress = log_search_process
    # solver.parameters.randomize_search = True
    # solver.parameters.linearization_level = 0
    # solver.parameters.enumerate_all_solutions = True
    # solver.parameters.max_time_in_seconds = 100
    # status = solver.Solve(
    #     model, PartialSolutionCallback(
    #         list(unassigned_shifts_per_event.values()),
    #         sum_assigned_shifts,
    #         sum_squared_deviations,
    #         constraints_fixed_cast_conflicts,
    #         None,
    #         False)
    # )
    # print('OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE' if status == cp_model.FEASIBLE else 'FAILED')

    return (solver.Value(rel_shift_deviations.sum_squared_deviations), 
            [solver.Value(u) for u in unsigned_shifts.unassigned_shifts_per_event.values()],
            sum(solver.Value(w) for w in weights_in_avail_day_groups.penalty_vars),
            sum(solver.Value(v) for v in weights_in_event_groups.penalty_vars),
            sum(solver.Value(lp) for lp in location_prefs.penalty_vars),
            solver.Value(sum(partner_location_prefs.penalty_vars)),
            {key: solver.Value(int_var) for key, int_var in fixed_cast_conflicts.fixed_cast_vars.items()},
            solver.Value(sum(cast_rules.penalty_vars)), appointments, success)


def call_solver_with__fixed_constraint_results(
        event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree, cast_group_tree: CastGroupTree,
        entities: 'Entities',
        unassigned_shifts_per_event_res: list[int], sum_squared_deviations_res: int,
        weights_shifts_in_avail_day_groups_res: int, weights_in_event_groups_res: int, sum_location_prefs_res: int,
        sum_partner_loc_prefs_res: int, sum_fixed_cast_conflicts_res: int, sum_cast_rules: int,
        print_solution_printer_results: bool, log_search_process: bool, collect_schedule_versions: bool
) -> tuple[PartialSolutionCallback | None, dict[tuple[datetime.date, str, UUID], int], bool]:
    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree, entities)
    solver_variables.cast_rules.reset_fields()
    
    # Registry-basierte Constraints
    registry = create_constraints(model, entities)
    
    # Constraints aus Registry holen
    unsigned_shifts: UnsignedShiftsConstraint = registry.get_constraint(UnsignedShiftsConstraint)
    rel_shift_deviations: RelShiftDeviationsConstraint = registry.get_constraint(RelShiftDeviationsConstraint)
    weights_in_avail_day_groups: WeightsInAvailDayGroupsConstraint = (registry.
                                                                      get_constraint(WeightsInAvailDayGroupsConstraint))
    weights_in_event_groups: WeightsInEventGroupsConstraint = registry.get_constraint(WeightsInEventGroupsConstraint)
    location_prefs: LocationPrefsConstraint = registry.get_constraint(LocationPrefsConstraint)
    partner_location_prefs: PartnerLocationPrefsConstraint = registry.get_constraint(PartnerLocationPrefsConstraint)
    fixed_cast_conflicts: FixedCastConflictsConstraint = registry.get_constraint(FixedCastConflictsConstraint)
    cast_rules: CastRulesConstraint = registry.get_constraint(CastRulesConstraint)
    prefer_fixed_cast: PreferFixedCastConstraint = registry.get_constraint(PreferFixedCastConstraint)
    
    define_objective__fixed_constraint_results(
        model, list(unsigned_shifts.unassigned_shifts_per_event.values()), rel_shift_deviations.sum_squared_deviations,
        weights_in_avail_day_groups.penalty_vars, weights_in_event_groups.penalty_vars,
        location_prefs.penalty_vars, partner_location_prefs.penalty_vars,
        fixed_cast_conflicts.fixed_cast_vars, cast_rules.penalty_vars,
        prefer_fixed_cast.penalty_vars, unassigned_shifts_per_event_res,
        sum_squared_deviations_res, weights_shifts_in_avail_day_groups_res,
        weights_in_event_groups_res, sum_location_prefs_res,
        sum_partner_loc_prefs_res, sum_fixed_cast_conflicts_res, sum_cast_rules, 0)
    # print('\n\n++++++++++++++++++++++++++++++++++++++ New Solution +++++++++++++++++++++++++++++++++++++++++++++++++++')
    solver, solution_printer, solver_status = solve_model_with_solver_solution_callback(
        model, list(unsigned_shifts.unassigned_shifts_per_event.values()), rel_shift_deviations.sum_assigned_shifts,
        rel_shift_deviations.sum_squared_deviations, fixed_cast_conflicts.fixed_cast_vars,
        print_solution_printer_results, 100, log_search_process, entities, collect_schedule_versions)
    success, problems = print_solver_status(model, solver_status)
    if not success:
        return None, {}, False
    print_statistics(solver, solution_printer, unsigned_shifts.unassigned_shifts_per_event,
                     rel_shift_deviations.sum_assigned_shifts, rel_shift_deviations.sum_squared_deviations,
                     partner_location_prefs.penalty_vars, location_prefs.penalty_vars,
                     fixed_cast_conflicts.fixed_cast_vars,
                     weights_in_event_groups.penalty_vars,
                     weights_in_avail_day_groups.penalty_vars, cast_rules.penalty_vars)

    fixed_cast_conflicts_result = {key: solver.Value(val) for key, val in fixed_cast_conflicts.fixed_cast_vars.items()}
    return solution_printer, fixed_cast_conflicts_result, success


def set_test_plan_constraints(model: cp_model.CpModel, plan: schemas.PlanShow,
                              constraints_fixed_cast_conflicts:  dict[tuple[datetime.date, str, UUID], IntVar],
                              skill_conflict_vars: list[IntVar], entities: 'Entities'):
    indexes_shift_vars = set(entities.shift_vars.keys())
    for appointment in plan.appointments:
        event_group_id = db_services.Event.get(appointment.event.id).event_group.id
        for avd in appointment.avail_days:
            a = model.NewBoolVar(f'<p style="margin-bottom: 4px; margin-top: 8px;">Termin:</p>'
                                 f'<p style="margin-left: 20px; margin-bottom: 4px; margin-top: 4px;">'
                                 f'{avd.actor_plan_period.person.full_name}, '
                                 f'{appointment.event.date: %d.%m.%y}, '
                                 f'{appointment.event.time_of_day.name}, '
                                 f'{appointment.event.location_plan_period.location_of_work.name} '
                                 f'{appointment.event.location_plan_period.location_of_work.address.city}</p>')
            model.Add(entities.shift_vars[(avd.avail_day_group.id, event_group_id)] == True).OnlyEnforceIf(a)
            model.AddAssumption(a)
            indexes_shift_vars.remove((avd.avail_day_group.id, event_group_id))
    for idx in indexes_shift_vars:
        model.Add(entities.shift_vars[idx] == False)
    for int_var in constraints_fixed_cast_conflicts.values():
        a = model.NewBoolVar(f'<p style="margin-bottom: 4px; margin-top: 8px;">Feste Besetzung:</p>'
                             f'<p style="margin-left: 20px; margin-bottom: 4px; margin-top: 4px;">{int_var.name}</p>')
        model.Add(int_var == 0).OnlyEnforceIf(a)
        model.AddAssumption(a)
    for skill_var in skill_conflict_vars:
        a = model.NewBoolVar(f'<p style="margin-bottom: 4px; margin-top: 8px;">Fertigkeitskonflikt:</p>'
                             f'<p style="margin-left: 20px; margin-bottom: 4px; margin-top: 4px;">{skill_var.name}</p>')
        model.Add(skill_var == 0).OnlyEnforceIf(a)
        model.AddAssumption(a)

    avail_day_groups_with_required_shifts = [
        adg for adg in entities.avail_day_groups.values()
        if adg.required_avail_day_groups
    ]
    for adg in avail_day_groups_with_required_shifts:
        required = adg.required_avail_day_groups
        name_employee = adg.children[0].avail_day.actor_plan_period.person.full_name
        shift_dates = set(c.avail_day.date for c in adg.children)
        shift_dates_text = ', '.join(f'{d:%d.%m}' for d in sorted(shift_dates))
        shift_locations_text = ('in den Einrichtungen:<br>'
                                + ', '.join(sorted(l.name_an_city for l in required.locations_of_work))
                                + '<br>') if required.locations_of_work else ''
        a = model.NewBoolVar(f'<p style="margin-bottom: 4px; margin-top: 8px;">Mindesteinsätze:</p>'
                             f'<p style="margin-left: 20px; margin-bottom: 4px; margin-top: 4px;">Einsätze von {name_employee} an den Tagen:<br>'
                             f'{shift_dates_text}<br>{shift_locations_text}'
                             f'müssen {adg.required_avail_day_groups.num_avail_day_groups} oder 0 sein.</p>')
        y = model.NewBoolVar('Y')
        shift_sum = sum(
            shift_var
            for (adg_id, evg_id), shift_var in entities.shift_vars.items()
            if adg_id in [a.avail_day_group_id for a in adg.children]
            and (entities.event_groups_with_event[evg_id].event.location_plan_period.location_of_work.id
                 in {l.id for l in required.locations_of_work} if required.locations_of_work else True)
        )
        model.Add(shift_sum == adg.required_avail_day_groups.num_avail_day_groups * y).OnlyEnforceIf(a)
        model.AddAssumption(a)



def call_solver_to_test_plan(plan: schemas.PlanShow,
                             event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree,
                             entities: 'Entities', max_search_time: int, 
                             log_search_process: bool) -> tuple[bool, list[str]]:
    """
    DEPRECATED: Verwende stattdessen die neue validate_plan()-basierte Architektur.
    
    Diese Funktion startet einen vollständigen Solver-Lauf zur Plan-Validierung.
    Die neue Architektur nutzt direkte Python-Prüfungen ohne Solver.
    """
    import warnings
    warnings.warn(
        "call_solver_to_test_plan ist deprecated. "
        "Die neue test_plan() nutzt Registry.validate_plan() ohne Solver.",
        DeprecationWarning,
        stacklevel=2
    )
    
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree, entities)
    
    # Registry-basierte Constraints
    registry = create_constraints(model, entities, True)
    
    # Constraints aus Registry holen
    fixed_cast_conflicts: FixedCastConflictsConstraint = registry.get_constraint(FixedCastConflictsConstraint)
    skills: SkillsConstraint = registry.get_constraint(SkillsConstraint)
    
    set_test_plan_constraints(model, plan,
                              fixed_cast_conflicts.fixed_cast_vars, skills.penalty_vars, entities)
    solver, solver_status = solve_model_to_optimum(model, max_search_time, log_search_process)

    success, problems = print_solver_status(model, solver_status)
    return success, problems


def _get_max_fair_shifts_and_max_shifts_to_assign(
        plan_period_id: UUID, time_calc_max_shifts: int, time_calc_fair_distribution: int,
        log_search_process=False) -> tuple[EventGroupTree, AvailDayGroupTree, Entities, 
                                           dict[tuple[date, str, UUID], int],
                                           dict[str, int], dict[UUID, int], dict[UUID, float]] | None:
    """
    Berechnet maximale und faire Shifts für eine einzelne Planperiode.
    
    Returns:
        Tuple mit (event_group_tree, avail_day_group_tree, entities, 
                   fixed_cast_conflicts, skill_conflicts, max_shifts_per_app, fair_shifts_per_app)
        oder None bei Fehler
    """
    signal_handling.handler_solver.progress('Vorberechnungen...')

    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    entities = create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)

    (assigned_shifts, unassigned_shifts, sum_location_prefs, sum_partner_loc_prefs, fixed_cast_conflicts,
     skill_conflicts, sum_cast_rules, success) = call_solver_with_unadjusted_requested_assignments(
        event_group_tree,
        avail_day_group_tree,
        entities,
        time_calc_max_shifts,
        log_search_process)

    if sum(fixed_cast_conflicts.values()) or sum(skill_conflicts.values()):
        return event_group_tree, avail_day_group_tree, entities, fixed_cast_conflicts, skill_conflicts, {}, {}
    if not success:
        return

    get_max_shifts_per_app = call_solver_to_get_max_shifts_per_app(event_group_tree,
                                                                   avail_day_group_tree,
                                                                   entities,
                                                                   unassigned_shifts,
                                                                   sum_location_prefs,
                                                                   sum_partner_loc_prefs,
                                                                   sum(fixed_cast_conflicts.values()),
                                                                   sum_cast_rules,
                                                                   assigned_shifts,
                                                                   time_calc_fair_distribution,
                                                                   log_search_process)

    while True:
        try:
            signal_handling.handler_solver.progress('Bestimmung maximaler Einsätze...')
            next(get_max_shifts_per_app)
        except StopIteration as e:
            success, max_shifts_per_app = e.value
            break

    if not success:
        return None

    # Fair Distribution separat berechnen
    signal_handling.handler_solver.progress('Berechnung fairer Verteilung...')
    fair_shifts_per_app = get_fair_distribution(
        max_shifts_per_app,
        sum(assigned_shifts.values()),
        entities
    )

    time.sleep(0.1)  # notwendig, damit Signal-Handling Zeit für das Senden des neuen Signals hat.

    return ((event_group_tree, avail_day_group_tree, entities, fixed_cast_conflicts, skill_conflicts,
             max_shifts_per_app, fair_shifts_per_app) if success else None)


def _get_max_fair_shifts_and_max_shifts_to_assign_multi_period(
        plan_period_ids: list[UUID], time_calc_max_shifts: int, time_calc_fair_distribution: int,
        log_search_process=False) -> tuple[EventGroupTree, AvailDayGroupTree, dict[tuple[date, str, UUID], int],
                                           dict[str, int], dict[UUID, int], dict[UUID, float]] | None:
    """
    Multi-Period Version - Berechnet faire Einsätze über mehrere PlanPeriods.
    
    OPTIMIERT: Berechnet max_shifts periode-spezifisch für Performance.
    
    Args:
        plan_period_ids: Liste von PlanPeriod UUIDs
        time_calc_max_shifts: Zeitlimit für max shifts Berechnung
        time_calc_fair_distribution: Zeitlimit für faire Verteilung
        log_search_process: Ob Solver-Prozess geloggt werden soll
        
    Returns:
        Tuple mit Trees, Conflicts und Shifts oder None bei Fehler
    """
    signal_handling.handler_solver.progress('Vorberechnungen (Multi-Period)...')
    
    # ========== PHASE 1: Max Shifts pro Periode berechnen ==========
    max_shifts_per_app_total = {}
    assigned_shifts_per_period_total = {}
    all_fixed_cast_conflicts = {}
    all_skill_conflicts = {}
    
    for plan_period_id in plan_period_ids:
        # Single-Period Trees für diese Periode
        event_group_tree_period = get_event_group_tree(plan_period_id)
        avail_day_group_tree_period = get_avail_day_group_tree(plan_period_id)
        cast_group_tree_period = get_cast_group_tree(plan_period_id)
        
        # Neue entities für jede Periode (wichtig: jede Periode hat eigene Daten!)
        entities = create_data_models(
            event_group_tree_period, 
            avail_day_group_tree_period, 
            cast_group_tree_period, 
            plan_period_id
        )
        
        # Unadjusted berechnen mit periode-spezifischen Trees
        (assigned_shifts, unassigned_shifts, sum_location_prefs, sum_partner_loc_prefs,
         fixed_cast_conflicts, skill_conflicts, sum_cast_rules, success) = \
            call_solver_with_unadjusted_requested_assignments(
                event_group_tree_period,
                avail_day_group_tree_period,
                entities,
                time_calc_max_shifts,
                log_search_process
            )
        
        # Sammle Conflicts (können in verschiedenen Perioden auftreten)
        all_fixed_cast_conflicts.update(fixed_cast_conflicts)
        all_skill_conflicts.update(skill_conflicts)
        
        if not success:
            # Combined Trees für Rückgabe erstellen
            event_group_tree = get_combined_event_group_tree(plan_period_ids)
            avail_day_group_tree = get_combined_avail_day_group_tree(plan_period_ids)
            return event_group_tree, avail_day_group_tree, all_fixed_cast_conflicts, all_skill_conflicts, {}, {}
        
        # Max Shifts für diese Periode berechnen
        get_max_shifts_per_app = call_solver_to_get_max_shifts_per_app(
            event_group_tree_period,
            avail_day_group_tree_period,
            entities,
            unassigned_shifts,
            sum_location_prefs,
            sum_partner_loc_prefs,
            sum(fixed_cast_conflicts.values()),
            sum_cast_rules,
            assigned_shifts,
            time_calc_fair_distribution,
            log_search_process
        )
        
        # Generator abarbeiten
        while True:
            try:
                _, app_id = next(get_max_shifts_per_app)
                person_name = entities.actor_plan_periods[app_id].person.full_name
                period_name = (f'{date_to_string(entities.actor_plan_periods[app_id].plan_period.start)} '
                               f'- {date_to_string(entities.actor_plan_periods[app_id].plan_period.end)}')
                signal_handling.handler_solver.progress(
                    f'Max Shifts für {person_name} in {period_name}...'
                )
            except StopIteration as e:
                success, period_max_shifts = e.value
                break
        
        # Kurze Pause für Signal-Processing (verhindert Race-Condition)
        time.sleep(0.05)
        
        if not success:
            event_group_tree = get_combined_event_group_tree(plan_period_ids)
            avail_day_group_tree = get_combined_avail_day_group_tree(plan_period_ids)
            return event_group_tree, avail_day_group_tree, all_fixed_cast_conflicts, all_skill_conflicts, {}, {}
        
        # Sammle Ergebnisse
        max_shifts_per_app_total.update(period_max_shifts)
        assigned_shifts_per_period_total[plan_period_id] = sum(assigned_shifts.values())
    
    # Prüfe ob Conflicts aufgetreten sind
    if sum(all_fixed_cast_conflicts.values()) or sum(all_skill_conflicts.values()):
        event_group_tree = get_combined_event_group_tree(plan_period_ids)
        avail_day_group_tree = get_combined_avail_day_group_tree(plan_period_ids)
        return event_group_tree, avail_day_group_tree, all_fixed_cast_conflicts, all_skill_conflicts, {}, {}
    
    # ========== PHASE 2: Fair Distribution über alle Perioden ==========
    # Combined Trees werden in get_fair_distribution_multi_period() erstellt
    signal_handling.handler_solver.progress('Berechne faire Verteilung (Multi-Period)...')
    event_group_tree, avail_day_group_tree, fair_shifts_per_app = get_fair_distribution_multi_period(
        plan_period_ids,
        max_shifts_per_app_total,
        assigned_shifts_per_period_total
    )
    
    time.sleep(0.1)  # Signal-Handling Zeit geben
    
    # Returniere Combined Trees (werden für Plan-Berechnung benötigt!)
    return (event_group_tree, avail_day_group_tree,
            all_fixed_cast_conflicts, all_skill_conflicts,
            max_shifts_per_app_total, fair_shifts_per_app)


def solve(plan_period_id: UUID, num_plans: int, time_calc_max_shifts: int, time_calc_fair_distribution: int,
          time_calc_plan: int, log_search_process=False) -> tuple[list[list[AppointmentCreate]] | None,
                                                                  dict[tuple[date, str, UUID], int] | None,
                                                                  dict[str, int] | None,
                                                                  dict[UUID, int] | None,
                                                                  dict[UUID, float] | None]:

    result_shifts = _get_max_fair_shifts_and_max_shifts_to_assign(plan_period_id,
                                                                  time_calc_max_shifts,
                                                                  time_calc_fair_distribution,
                                                                  log_search_process)
    success = True
    if result_shifts is None:
        success = False

    if not success:
        return None, None, None, None, None

    (event_group_tree, avail_day_group_tree, entities,
     fixed_cast_conflicts, skill_conflicts, max_shifts_per_app, fair_shifts_per_app) = result_shifts

    if sum(fixed_cast_conflicts.values()) or skill_conflicts:
        return [], fixed_cast_conflicts, skill_conflicts, None, None

    plan_datas = []
    for n in range(1, num_plans + 1):
        signal_handling.handler_solver.progress(f'Pläne werden berechnet. ({n})')
        (sum_squared_deviations_res, unassigned_shifts_per_event_res, sum_weights_shifts_in_avail_day_groups,
         sum_weights_in_event_groups, sum_location_prefs_res, sum_partner_loc_prefs_res, fixed_cast_conflicts,
         sum_cast_rules, appointments,
         success) = call_solver_with_adjusted_requested_assignments(event_group_tree,
                                                                    avail_day_group_tree,
                                                                    entities,
                                                                    time_calc_plan,
                                                                    log_search_process)
        if not success:
            return None, None, None, None, None
        plan_datas.append(appointments)

    signal_handling.handler_solver.progress('Layouts der Pläne werden erstellt.')

    return plan_datas, fixed_cast_conflicts, skill_conflicts, max_shifts_per_app, fair_shifts_per_app


def solve_multi_period(plan_period_ids: list[UUID], num_plans: int, time_calc_max_shifts: int, 
                      time_calc_fair_distribution: int, time_calc_plan: int, 
                      log_search_process=False) -> tuple[list[list[list[AppointmentCreate]]] | None,
                                                         dict[tuple[date, str, UUID], int] | None,
                                                         dict[str, int] | None,
                                                         dict[UUID, int] | None,
                                                         dict[UUID, float] | None]:
    """
    Berechnet Pläne über mehrere PlanPeriods mit fairer Verteilung über alle Perioden.
    
    Diese Funktion ermöglicht die Multi-Period Kalkulation, wobei die faire Verteilung
    der Einsätze ALLE PlanPeriods berücksichtigt. Wenn ein Mitarbeiter in einer Periode
    weniger verfügbar ist, werden diese Ausfälle in anderen Perioden kompensiert.
    
    OPTIMIERT (Phase 2): Plan-Erstellung erfolgt pro Periode für bessere Performance.
    Die Fairness ist bereits durch generate_adjusted_requested_assignments_multi_period()
    garantiert, daher können Perioden unabhängig geplant werden.
    
    Workflow:
    1. Berechne Max Shifts pro Periode (Phase 1 - bereits optimiert)
    2. Berechne faire Verteilung über ALLE Perioden
    3. Erstelle Pläne PRO PERIODE (Phase 2 - NEU!)
    
    Args:
        plan_period_ids: Liste von PlanPeriod UUIDs (mindestens 2)
        num_plans: Anzahl der zu erstellenden Plan-Varianten
        time_calc_max_shifts: Zeitlimit für max shifts Berechnung (Sekunden)
        time_calc_fair_distribution: Zeitlimit für faire Verteilung (Sekunden)
        time_calc_plan: Zeitlimit pro Plan-Berechnung (Sekunden)
        log_search_process: Ob Solver-Prozess geloggt werden soll
        
    Returns:
        Tuple mit:
        - Liste von Plänen pro Periode: all_plans[period_idx][plan_idx]
          Jeder Plan enthält nur Events der jeweiligen Periode
        - Fixed cast conflicts
        - Skill conflicts  
        - Max shifts pro ActorPlanPeriod
        - Fair shifts pro ActorPlanPeriod
        
        Oder (None, None, None, None, None) bei Fehler
        
    Raises:
        ValueError: Wenn weniger als 2 PlanPeriods übergeben werden
    """
    if len(plan_period_ids) < 2:
        raise ValueError(f"Multi-Period calculation requires at least 2 periods, got {len(plan_period_ids)}")
    
    # ========== PHASE 1+2: Max Shifts + Fair Distribution ==========
    # Diese Phase arbeitet bereits optimiert (pro Periode für Max Shifts)
    result_shifts = _get_max_fair_shifts_and_max_shifts_to_assign_multi_period(
        plan_period_ids,
        time_calc_max_shifts,
        time_calc_fair_distribution,
        log_search_process
    )
    
    success = True
    if result_shifts is None:
        success = False

    if not success:
        return None, None, None, None, None

    (event_group_tree, avail_day_group_tree,
     fixed_cast_conflicts, skill_conflicts, max_shifts_per_app, fair_shifts_per_app) = result_shifts

    if sum(fixed_cast_conflicts.values()) or skill_conflicts:
        return [], fixed_cast_conflicts, skill_conflicts, None, None

    # ========== PHASE 3: Plan-Erstellung PRO PERIODE (OPTIMIERT!) ==========
    # Statt Combined Trees zu nutzen, erstellen wir Pläne pro Periode
    # Dies ist performanter, da der Solver nur relevante Events/AvailDays betrachtet
    all_plans = []
    
    for period_idx, plan_period_id in enumerate(plan_period_ids):
        signal_handling.handler_solver.progress(
            f'Erstelle Pläne für Periode {period_idx + 1}/{len(plan_period_ids)}...'
        )
        
        # Single-Period Trees für diese Periode
        event_group_tree_period = get_event_group_tree(plan_period_id)
        avail_day_group_tree_period = get_avail_day_group_tree(plan_period_id)
        cast_group_tree_period = get_cast_group_tree(plan_period_id)
        
        # entities mit nur dieser Periode füllen
        # WICHTIG: adjusted_assignments sind bereits fair durch Fair Distribution!
        entities = create_data_models(
            event_group_tree_period,
            avail_day_group_tree_period,
            cast_group_tree_period,
            plan_period_id
        )
        
        # KRITISCH: Übertrage die fairen adjusted_requested_assignments
        # Diese wurden in Phase 2 (Fair Distribution) für ALLE Perioden berechnet
        # und müssen nun an die neuen entities dieser Periode übergeben werden
        for actor_plan_period_id, fair_shifts in fair_shifts_per_app.items():
            if actor_plan_period_id in entities.actor_plan_periods:
                entities.actor_plan_periods[actor_plan_period_id].requested_assignments = fair_shifts
        
        # Erstelle num_plans für diese Periode
        period_plans = []
        for n in range(1, num_plans + 1):
            signal_handling.handler_solver.progress(
                f'Plan {n}/{num_plans} für Periode {period_idx + 1}/{len(plan_period_ids)}...'
            )
            
            (sum_squared_deviations_res, unassigned_shifts_per_event_res, 
             sum_weights_shifts_in_avail_day_groups, sum_weights_in_event_groups, 
             sum_location_prefs_res, sum_partner_loc_prefs_res, fixed_cast_conflicts,
             sum_cast_rules, appointments, success) = \
                call_solver_with_adjusted_requested_assignments(
                    event_group_tree_period,
                    avail_day_group_tree_period,
                    entities,
                    time_calc_plan,
                    log_search_process
                )
            
            if not success:
                return None, None, None, None, None
            
            period_plans.append(appointments)
        
        all_plans.append(period_plans)
    
    signal_handling.handler_solver.progress('Layouts der Multi-Period Pläne werden erstellt.')
    
    # Returniere Pläne pro Periode
    # Format: all_plans[period_idx][plan_idx] = appointments (nur Events dieser Periode)
    return all_plans, fixed_cast_conflicts, skill_conflicts, max_shifts_per_app, fair_shifts_per_app



def extract_appointments_by_period(
    appointments: list[AppointmentCreate],
    plan_period_ids: list[UUID]
) -> dict[UUID, list[AppointmentCreate]]:
    """
    Teilt einen Gesamtplan (über mehrere Perioden) in einzelne Perioden-Pläne auf.
    
    Diese Funktion nimmt einen Multi-Period Gesamtplan und gruppiert die Appointments
    nach ihren zugehörigen PlanPeriods. Jede PlanPeriod erhält eine separate Liste
    von Appointments, die nur Events aus dieser Periode enthält.
    
    Args:
        appointments: Liste von Appointments aus dem Gesamtplan (alle Perioden)
        plan_period_ids: Liste der PlanPeriod UUIDs zur Validierung
        
    Returns:
        Dictionary mit PlanPeriod ID als Key und Liste von Appointments als Value:
        {
            plan_period_id_1: [appointment1, appointment2, ...],
            plan_period_id_2: [appointment3, appointment4, ...],
            ...
        }
        
    Beispiel:
        >>> gesamtplan = solve_multi_period([pp1_id, pp2_id], ...)
        >>> perioden_plaene = extract_appointments_by_period(gesamtplan[0], [pp1_id, pp2_id])
        >>> plan_januar = perioden_plaene[pp1_id]  # Nur Appointments für Januar
        >>> plan_februar = perioden_plaene[pp2_id]  # Nur Appointments für Februar
    """
    # Initialisiere leere Listen für jede Periode
    period_appointments: dict[UUID, list[AppointmentCreate]] = {
        pp_id: [] for pp_id in plan_period_ids
    }
    
    # Gruppiere Appointments nach PlanPeriod
    for appointment in appointments:
        # Hole PlanPeriod ID aus dem Event
        pp_id = appointment.event.location_plan_period.plan_period.id
        
        # Validierung: Stelle sicher dass die PlanPeriod in der Liste ist
        if pp_id not in period_appointments:
            raise ValueError(
                f"Appointment gehört zu PlanPeriod {pp_id}, "
                f"die nicht in der übergebenen Liste enthalten ist!"
            )
        
        # Füge Appointment zur entsprechenden Periode hinzu
        period_appointments[pp_id].append(appointment)
    
    return period_appointments


def get_max_fair_shifts_per_app(plan_period_id: UUID, time_calc_max_shifts: int, time_calc_fair_distribution: int,
                                log_search_process=False) -> bool | tuple[dict[UUID, int], dict[UUID, float]]:
    result_shifts = _get_max_fair_shifts_and_max_shifts_to_assign(plan_period_id,
                                                                  time_calc_max_shifts,
                                                                  time_calc_fair_distribution,
                                                                  log_search_process)

    if result_shifts is None:
        return False
    _, _, _, fixed_cast_conflicts, skill_conflicts, max_shifts_per_app, fair_shifts_per_app = result_shifts

    return max_shifts_per_app, fair_shifts_per_app


def test_plan(plan_id: UUID, cached_entities: 'Entities | None' = None) -> tuple[bool, list[str], list[str]]:
    """
    Testet einen bestehenden Plan auf Regelverletzungen.
    
    Nutzt die neue Registry-basierte Validierung ohne Solver-Aufruf.
    Constraints die das Validatable-Protocol implementieren werden direkt
    in Python geprüft, was deutlich schneller ist als ein Solver-Durchlauf.
    
    Args:
        plan_id: UUID des zu testenden Plans
        cached_entities: Optional bereits geladene Entities für schnelle Validierung.
                        Wenn None, werden Entities neu geladen (langsamer).
        
    Returns:
        Tuple (success, problems, infos):
        - success: True wenn keine Fehler gefunden wurden
        - problems: Liste von HTML-formatierten Fehlermeldungen
        - infos: Liste von HTML-formatierten Hinweisen (keine Fehler)
    
    Note:
        Aktuell implementierte Validierungen:
        - EmployeeAvailability: Mitarbeiter-Verfügbarkeit
        - Skills: Fertigkeitsanforderungen
        - LocationPrefs: Standort-Präferenzen (nur Score=0)
        - FixedCastConflicts: Feste Besetzungen
        
        Für vollständige Validierung inkl. aller Constraints kann
        test_plan_with_solver() verwendet werden (deprecated).
    """
    from sat_solver.constraints import ConstraintRegistry
    
    # Plan laden (immer nötig, da Appointments aktuell sein müssen)
    plan = db_services.Plan.get(plan_id)
    
    if cached_entities is not None:
        # Schneller Pfad: Verwende gecachte Entities
        entities = cached_entities
    else:
        # Langsamer Pfad: Entities neu laden (Fallback)
        event_group_tree = get_event_group_tree(plan.plan_period.id)
        avail_day_group_tree = get_avail_day_group_tree(plan.plan_period.id)
        cast_group_tree = get_cast_group_tree(plan.plan_period.id)
        entities = create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan.plan_period.id)

        # Preload AvailDays und befülle shifts_exclusive für Verfügbarkeitsprüfungen
        preload_avail_days(entities)
        populate_shifts_exclusive(entities)

    registry = ConstraintRegistry(entities)
    registry.register_plan_test_constraints()

    # Validiere den Plan
    errors, validation_infos = registry.validate_plan(plan)
    
    # Konvertiere zu HTML-Strings
    problems = [error.to_html() for error in errors]
    infos = [info.to_html() for info in validation_infos]
    
    success = len(errors) == 0
    return success, problems, infos


def test_plan_with_solver(plan_id: UUID) -> tuple[bool, list[str]]:
    """
    DEPRECATED: Testet einen Plan mit vollständigem Solver-Durchlauf.
    
    Diese Funktion nutzt die alte Architektur mit Solver-Assumptions.
    Für die meisten Anwendungsfälle ist test_plan() schneller und ausreichend.
    
    Args:
        plan_id: UUID des zu testenden Plans
        
    Returns:
        Tuple (success, problems)
    """
    import warnings
    warnings.warn(
        "test_plan_with_solver ist deprecated. "
        "Verwende test_plan() für schnellere Validierung.",
        DeprecationWarning,
        stacklevel=2
    )
    
    plan = db_services.Plan.get(plan_id)
    event_group_tree = get_event_group_tree(plan.plan_period.id)
    avail_day_group_tree = get_avail_day_group_tree(plan.plan_period.id)
    cast_group_tree = get_cast_group_tree(plan.plan_period.id)
    entities = create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan.plan_period.id)
    success, problems = call_solver_to_test_plan(plan, event_group_tree, avail_day_group_tree, entities, 20, False)
    return success, problems


def solver_quit():
    if solver:
        solver.stop_search()


# todo: Eine Möglichkeit soll implementiert werden, um mehrere zusammenhängende AvailDays eines Mitarbeiters so
#  aufzuteilen, dass mehrere Events zugeordnet werden können, auch wenn die Start- und End-Zeiten nicht mit denen der
#  Events übereinstimmen. Auch ein AvailDay sollte auf mehrere Events aufgeteilt werden können.
#  Lösungsansatz:
#  - Zusammenhängende AvailDays sollten grundsätzlich zu einem AvailDay zusammengeführt werden.
#    Der Solver muss so modifiziert werden, dass nicht wie bisher nur genau 1 AvailDay mit genau 1 Event kombiniert
#    werden kann, sondern auch mehrere.
#    Siehe: add_constraints_unsigned_shift ->
#         # Summe aller zugewiesenen Freelancer zum Event:
#         num_assigned_employees = sum(
#             entities.shift_vars[(adg_id, event_group_id)] for adg_id in entities.avail_day_groups_with_avail_day
#         )
#         # Summe der zugewiesenen Freelancer muss kleiner oder gleich der einzusetzenden Mitarbeiter sein, falls
#         # wenn das Event stattfindet (über add_constraints_event_groups_activity wird das eingeschränkt):
#         model.Add(
#             num_assigned_employees <= (entities.event_group_vars[event_group.event_group_id]
#                                        * event_group.event.cast_group.nr_actors)
#    Das einschränkende Constraint würde dann wegfallen. Stattdessen müsste ein Constraint hinzugefügt werden welches
#    garantiert, dass sich die Zeiten (+ Zwischenzeiten, falls Events an verschiedenen Orten kombiniert werden) nicht
#    überlappen. Dafür gibt es bei ortools eine eingebaute Funktionalität.
# todo: claimed_assignments implementieren (auch im ActorPlanPeriod-Model). Hier eventuell über die Funktion
#  generate_adjusted_requested_assignments
# todo: Möglichkeit implementieren um die Anzahl der Einsätze eines Mitarbeiters an einer bestimmten Location zu
#  steuern. Einerseits die maximalen gewünschten Einsätze, alternativ die Anzahl der geforderten Einsätze.
