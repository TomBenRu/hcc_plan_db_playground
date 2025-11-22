import collections
import dataclasses
import itertools
import logging
import os
import pprint
import sys
import time
from ast import literal_eval
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

cp_sat_logger = logging.getLogger(__name__)
handler = logging.FileHandler(os.path.join(curr_user_path_handler.get_config().log_file_path, 'cp-sat-solver.log'))
custom_format = logging.Formatter('')
handler.setFormatter(custom_format)
cp_sat_logger.addHandler(handler)
cp_sat_logger.propagate = False

def generate_adjusted_requested_assignments(assigned_shifts: int, possible_assignments: dict[UUID, int]):
    """
    Berechnet faire Einsätze für eine einzelne PlanPeriod auf ActorPlanPeriod-Ebene.

    Args:
        assigned_shifts: Gesamte Anzahl an zu verteilenden Einsätzen
        possible_assignments: Dict mit ActorPlanPeriod ID -> max. mögliche Einsätze

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
                                                         possible_assignments: dict[UUID, int]) -> dict[UUID, float]:
    """
    Berechnet faire Einsätze über mehrere PlanPeriods hinweg auf Person-Ebene.

    Diese Funktion gruppiert ActorPlanPeriods nach Person und berechnet eine faire
    Verteilung der Gesamteinsätze über ALLE Perioden einer Person. Die Verteilung
    auf einzelne ActorPlanPeriods erfolgt proportional zum Minimum aus verfügbaren
    Tagen und requested_assignments.

    Args:
        assigned_shifts_per_period: Dict mit PlanPeriod ID -> Anzahl zu verteilender Einsätze
        possible_assignments: Dict mit ActorPlanPeriod ID -> max. mögliche Einsätze

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


def check_actor_location_prefs_fits_event(avail_day: schemas.AvailDayShow,
                                          location_of_work: schemas.LocationOfWork) -> bool:
    """Prüft, ob die actor_location_prefs des avail_days die location_of_work des Events zulassen."""
    if found_alf := next((alf for alf in avail_day.actor_location_prefs_defaults
                          if alf.location_of_work.id == location_of_work.id), None):
        if found_alf.score == 0:
            return False
    return True


def check_time_span_avail_day_fits_event(
        event: schemas.Event, avail_day: schemas.AvailDay, only_time_index: bool = True) -> bool:
    """Prüft, ob der Zeitraum des avail_days den Zeitraum des Events enthält."""
    if only_time_index:
        return (
            avail_day.date == event.date
            and avail_day.time_of_day.time_of_day_enum.time_index
            == event.time_of_day.time_of_day_enum.time_index
        )
    else:
        return (
            avail_day.date == event.date
            and avail_day.time_of_day.start <= event.time_of_day.start
            and avail_day.time_of_day.end >= event.time_of_day.end
        )


class PartialSolutionCallback(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, unassigned_shifts_per_event: list[IntVar],
                 sum_assigned_shifts: dict[UUID, IntVar], sum_squared_deviations: IntVar,
                 fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], IntVar], limit: int | None,
                 print_results: bool, collect_schedule_versions=False):
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

        for event_group in sorted(list(entities.event_groups_with_event.values()),
                                  key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index)):
            if not self.Value(entities.event_group_vars[event_group.event_group_id]):
                continue
            scheduled_adg_ids = []
            for (adg_id, eg_id), var in entities.shift_vars.items():
                if eg_id == event_group.event_group_id and self.Value(var):
                    scheduled_adg_ids.append(adg_id)
            event = event_group.event
            avail_days = [entities.avail_day_groups_with_avail_day[agd_id].avail_day for agd_id in scheduled_adg_ids]
            self._schedule_versions[-1].append(schemas.AppointmentCreate(avail_days=avail_days, event=event))

    def print_results(self):
        return
        print(f"Solution {self._solution_count}")
        # self.print_shifts()
        print('unassigned_shifts_per_event:',
              [self.Value(unassigned_shifts) for unassigned_shifts in self._unassigned_shifts_per_event])
        sum_assigned_shifts_per_employee = {entities.actor_plan_periods[app_id].person.f_name: self.Value(s)
                                            for app_id, s in self._sum_assigned_shifts.items()}
        print(f'sum_assigned_shifts_of_employees: {sum_assigned_shifts_per_employee}')
        print(f'sum_squared_deviations: {self.Value(self._sum_squared_deviations)}')
        fixed_cast_conflicts = {f'{date:%d.%m.%y} ({time_of_day}) {cast_group_id}': self.Value(var)
                                for (date, time_of_day, cast_group_id), var in self._fixed_cast_conflicts.items()}
        print(f'fixed_cast_conflicts: {fixed_cast_conflicts}')
        print('-----------------------------------------------------------------------------------------------------')
        # for app_id, app in entities.actor_plan_periods.items():
        #     group_vars = {
        #         entities.avail_day_groups_with_avail_day[adg_id].avail_day.date: self.Value(var)
        #         for adg_id, var in entities.avail_day_group_vars.items()
        #         if (adg_id in entities.avail_day_groups_with_avail_day
        #             and entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.id == app_id)}
        #     print(f'active_avail_day_groups of {app.person.f_name}: {group_vars}')

    def print_shifts(self):
        return
        for event_group in sorted(list(entities.event_groups_with_event.values()),
                                  key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index)):
            if not self.Value(entities.event_group_vars[event_group.event_group_id]):
                continue
            print(f"Day {event_group.event.date: '%d.%m.%y'} ({event_group.event.time_of_day.name}) "
                  f"in {event_group.event.location_plan_period.location_of_work.name}")
            for actor_plan_period in entities.actor_plan_periods.values():
                if sum(self.Value(entities.shift_vars[(avd_id, event_group.event_group_id)])
                       for avd_id in (avd.avail_day_group.id for avd in actor_plan_period.avail_days)):
                    print(f"   {actor_plan_period.person.f_name} "
                          f"works in {event_group.event.location_plan_period.location_of_work.name:}")

    def get_max_assigned_shifts(self):
        return self._max_assigned_shifts

    def get_schedule_versions(self):
        return self._schedule_versions

    def solution_count(self):
        return self._solution_count


@dataclasses.dataclass
class Entities:
    actor_plan_periods: dict[UUID, schemas.ActorPlanPeriodShow] = dataclasses.field(default_factory=dict)
    avail_day_groups: dict[UUID, AvailDayGroup] = dataclasses.field(default_factory=dict)
    avail_day_groups_with_avail_day: dict[UUID, AvailDayGroup] = dataclasses.field(default_factory=dict)
    avail_day_group_vars: dict[UUID, IntVar] = dataclasses.field(default_factory=dict)
    event_groups: dict[UUID, EventGroup] = dataclasses.field(default_factory=dict)
    event_groups_with_event: dict[UUID, EventGroup] = dataclasses.field(default_factory=dict)
    event_group_vars: dict[UUID, IntVar] = dataclasses.field(default_factory=dict)
    cast_groups: dict[UUID, CastGroup] = dataclasses.field(default_factory=dict)
    cast_groups_with_event: dict[UUID, CastGroup] = dataclasses.field(default_factory=dict)
    shift_vars: dict[tuple[UUID, UUID], IntVar] = dataclasses.field(default_factory=dict)
    shifts_exclusive: dict[tuple[UUID, UUID], int] = dataclasses.field(default_factory=dict)
    # wenn value==0, kann shift mit key (adg_id, eg_id) nicht gesetzt werden


entities: Entities | None = None


def create_data_models(event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree,
                       cast_group_tree: CastGroupTree, plan_period_id: UUID):
    plan_period = db_services.PlanPeriod.get(plan_period_id)
    entities.actor_plan_periods = {app.id: db_services.ActorPlanPeriod.get(app.id)
                                   for app in plan_period.actor_plan_periods}
    entities.event_groups = {
        event_group.event_group_id: event_group for event_group in event_group_tree.root.descendants
        if event_group.children or event_group.event
    }
    entities.event_groups = {event_group_tree.root.event_group_id: event_group_tree.root} | entities.event_groups

    entities.event_groups_with_event = {leave.event_group_id: leave for leave in event_group_tree.root.leaves
                                        if leave.event}

    entities.avail_day_groups = {
        avail_day_group.avail_day_group_id: avail_day_group for avail_day_group in avail_day_group_tree.root.descendants
        if avail_day_group.children or avail_day_group.avail_day
    }
    entities.avail_day_groups = ({avail_day_group_tree.root.avail_day_group_id: avail_day_group_tree.root}
                                 | entities.avail_day_groups)
    entities.avail_day_groups_with_avail_day = {
        leave.avail_day_group_id: leave for leave in avail_day_group_tree.root.leaves if leave.avail_day
    }

    entities.cast_groups = {cast_group_tree.root.cast_group_id: cast_group_tree.root} | {
        cast_group.cast_group_id: cast_group
        for cast_group in cast_group_tree.root.descendants
    }
    entities.cast_groups_with_event = {cast_group.cast_group_id: cast_group
                                       for cast_group in cast_group_tree.root.leaves if cast_group.event}


def create_data_models_multi_period(event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree,
                                   cast_group_tree: CastGroupTree, plan_period_ids: list[UUID]):
    """
    Erstellt die Data Models für Multi-Period Kalkulation.
    
    Im Gegensatz zu create_data_models() werden hier ActorPlanPeriods, Events und CastGroups
    von ALLEN übergebenen PlanPeriods gesammelt.
    
    Args:
        event_group_tree: Combined EventGroupTree über alle Perioden
        avail_day_group_tree: Combined AvailDayGroupTree über alle Perioden
        cast_group_tree: Combined CastGroupTree über alle Perioden
        plan_period_ids: Liste aller PlanPeriod UUIDs
    """
    # Sammle ActorPlanPeriods von ALLEN PlanPeriods
    entities.actor_plan_periods = {}
    for pp_id in plan_period_ids:
        plan_period = db_services.PlanPeriod.get(pp_id)
        for app in plan_period.actor_plan_periods:
            # ActorPlanPeriod ID ist unique, daher keine Duplikate möglich
            entities.actor_plan_periods[app.id] = db_services.ActorPlanPeriod.get(app.id)
    
    # Rest analog zu create_data_models() - Tree-Struktur ist bereits kombiniert
    entities.event_groups = {
        event_group.event_group_id: event_group for event_group in event_group_tree.root.descendants
        if event_group.children or event_group.event
    }
    entities.event_groups = {event_group_tree.root.event_group_id: event_group_tree.root} | entities.event_groups

    entities.event_groups_with_event = {leave.event_group_id: leave for leave in event_group_tree.root.leaves
                                        if leave.event}

    entities.avail_day_groups = {
        avail_day_group.avail_day_group_id: avail_day_group for avail_day_group in avail_day_group_tree.root.descendants
        if avail_day_group.children or avail_day_group.avail_day
    }
    entities.avail_day_groups = ({avail_day_group_tree.root.avail_day_group_id: avail_day_group_tree.root}
                                 | entities.avail_day_groups)

    entities.avail_day_groups_with_avail_day = {
        leave.avail_day_group_id: leave for leave in avail_day_group_tree.root.leaves if leave.avail_day
    }

    entities.cast_groups = {cast_group_tree.root.cast_group_id: cast_group_tree.root} | {
        cast_group.cast_group_id: cast_group
        for cast_group in cast_group_tree.root.descendants
    }
    entities.cast_groups_with_event = {cast_group.cast_group_id: cast_group
                                       for cast_group in cast_group_tree.root.leaves if cast_group.event}


def create_vars(model: cp_model.CpModel, event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree):

    entities.event_group_vars = {
        event_group.event_group_id: model.NewBoolVar(f'')
        for event_group in event_group_tree.root.descendants
        if event_group.children or event_group.event
    }
    entities.avail_day_group_vars = {
        avail_day_group.avail_day_group_id: model.NewBoolVar(f'')
        for avail_day_group in avail_day_group_tree.root.descendants
        if avail_day_group.children or avail_day_group.avail_day
    }

    for adg_id, adg in entities.avail_day_groups_with_avail_day.items():
        for event_group_id, event_group in entities.event_groups_with_event.items():
            location_of_work = event_group.event.location_plan_period.location_of_work
            #######################################################################################################
            # todo: später implementieren, um die shift_vars zu minimieren und die Effektivität zu verbessern
            # shift_vars werden nicht gesetzt, wenn das zur location_of_work zugehörige actor_location_pref
            # des avail_day einen Score von 0 besitzt:
            entities.shifts_exclusive[adg_id, event_group_id] = 1
            if not check_actor_location_prefs_fits_event(adg.avail_day, location_of_work):
                entities.shifts_exclusive[adg_id, event_group_id] = 0
            # shift_vars werden nicht gesetzt, wenn Zeitfenster und Datum nicht zu denen des avail_day passen:
            if not check_time_span_avail_day_fits_event(event_group.event, adg.avail_day):
                entities.shifts_exclusive[adg_id, event_group_id] = 0
            #########################################################################################################
            entities.shift_vars[(adg_id, event_group_id)] = model.NewBoolVar(
                f'shift ({adg.avail_day.actor_plan_period.person.f_name},{adg.avail_day.date:%d.%m.%y}, {event_group_id})')
    # print(f'{len(entities.shift_vars)=}')
    # print(f'{sum(entities.shifts_exclusive.values())=}')


def add_constraints_employee_availability(model: cp_model.CpModel):
    # todo: shift_vars können schon bei der Variablenerstellung ausgeschlossen werden, falls die unten angegebene
    #  Bedingung nicht erfüllt ist.

    for key, val in entities.shifts_exclusive.items():
        if not val:
            model.Add(entities.shift_vars[key] == 0)
    return


def add_constraints_event_groups_activity(model: cp_model.CpModel):
    """
    Fügt Constraints hinzu, um sicherzustellen, dass nur so viele Child-Event-Groups aktiv sind,
    wie in der Parent-Event-Group mit dem Parameter 'nr_of_active_children' angegeben ist.
    """
    for event_group_id, event_group in entities.event_groups.items():
        if not event_group.children:
            continue
        nr_of_active_children = (event_group.nr_of_active_children
                                 or len([c for c in event_group.children if c.children or c.event]))
        child_vars = [entities.event_group_vars[c.event_group_id] for c in event_group.children if
                      c.children or c.event]
        # Wenn es sich bei der Event-Group um eine Root-Event-Group handelt, ist diese garantiert aktiv.
        if event_group.is_root:
            model.Add(sum(child_vars) == nr_of_active_children)
        # Wenn es sich um eine Child-Event-Group handelt, ist diese eventuell nicht aktiv.
        # In diesem Fall sollen keine aktiven existieren.
        else:
            model.Add(sum(child_vars) == nr_of_active_children * entities.event_group_vars[event_group_id])


def add_constraints_weights_in_event_groups(model: cp_model.CpModel) -> list[IntVar]:
    """
    Fügt Constraints hinzu, um sicherzustellen, dass die Child-Event-Groups mit den höheren Gewichtungen
    bevorzugt werden. Die Werte von weight_vars werden im Solver minimiert.
    Bei tiefer geschachtelten Event-Groups werden die Parent-Groups bevorzugt deren ausgewählte Children
    ein insgesamt höheres weight haben, wenn die Parent-Groups gleiches weight haben.
    not_sure: Überlegenswert ist eine alternative Implementierung wie bei 'add_constraints_weights_in_avail_day_groups'.
      Dies entspräche allerdings nicht der Nutzerlogik. Der Nutzer geht vermutlich davon aus, dass übergeordnete Gruppen
      eine höhere Relevanz haben.
    """

    multiplier_level = (curr_config_handler.get_solver_config()
                        .constraints_multipliers.group_depth_weights_event_groups)
    multiplier_weights = (curr_config_handler.get_solver_config()
                          .constraints_multipliers.sliders_weights_event_groups)

    def calculate_weight_vars_of_children_recursive(event_group: EventGroup, depth: int) -> list[IntVar]:
        weight_vars: list[IntVar] = []
        if event_group.nr_of_active_children is not None:
            if (children := event_group.children) and (event_group.nr_of_active_children < len(event_group.children)):
                children: list[EventGroup]
                for c in children:
                    # Das angepasste weight der Child-Event-Group wird berechnet:
                    adjusted_weight = multiplier_weights[c.weight]

                    event_group_var = entities.event_group_vars[c.event_group_id]
                    weight_vars.append(
                        model.NewIntVar(min(multiplier_weights.values()) * max(multiplier_level.values()),
                                        max(multiplier_weights.values()) * max(multiplier_level.values()),
                                        f'Depth {depth}, no Event' if c.event is None
                                        else f'Depth {depth}, Event: {c.event.date:%d.%m.%y}, '
                                             f'{c.event.time_of_day.name}, '
                                             f'{c.event.location_plan_period.location_of_work.name}')
                    )
                    model.Add(weight_vars[-1] == (event_group_var * adjusted_weight * multiplier_level.get(depth, 1)))
        for c in event_group.children:
            weight_vars.extend(calculate_weight_vars_of_children_recursive(c, depth + 1))

        return weight_vars

    root_event_group = next(eg for eg in entities.event_groups.values() if not eg.parent)

    return calculate_weight_vars_of_children_recursive(
        root_event_group, 1 if root_event_group.root_is_location_plan_period_master_group else 0)


def add_constraints_weights_in_event_groups_alternative_implementation(model: cp_model.CpModel) -> list[IntVar]:
    multiplier_weights = (curr_config_handler.get_solver_config()
                          .constraints_multipliers.sliders_weights_event_groups)

    def calculate_weight_vars_of_children_recursive(group: EventGroup,
                                                    cumulative_adjusted_weight: int = 0) -> list[IntVar]:
        weight_vars: list[IntVar] = []
        for c in group.children:
            c: EventGroup
            if c.event:
                # Es wird kein IntVar erstellt, wenn kein Einsatz dieses Events möglich ist:
                if not sum(val for (adg_id, evg_id), val in entities.shifts_exclusive.items()
                           if evg_id == c.event_group_id
                              and check_time_span_avail_day_fits_event(
                    entities.event_groups_with_event[evg_id].event,
                    entities.avail_day_groups_with_avail_day[adg_id].avail_day)):
                    continue
                # für die fehlenden Level wird jew. die Gewichtung 1 (default: 0) gesetzt:
                adjusted_weight = (max_depth - c.depth) * multiplier_weights[1] + multiplier_weights[c.weight]
                weight_vars.append(
                    model.NewIntVar(-100, 100000,
                                    f'Depth {group.depth}, Event: {c.event.date:%d.%m.%y}, '
                                    f'{c.event.time_of_day.name}, '
                                    f'{c.event.location_plan_period.location_of_work.name_an_city}')
                )
                # stelle fest, ob doe zugehörige Event-Group aktiv ist:
                model.Add(weight_vars[-1] == ((cumulative_adjusted_weight + adjusted_weight)
                                              * entities.event_group_vars[c.event_group_id]))
            else:
                adjusted_weight = multiplier_weights[c.weight]
                weight_vars.extend(
                    calculate_weight_vars_of_children_recursive(c,
                                                                cumulative_adjusted_weight + adjusted_weight))
        return weight_vars

    root_group = next(eg for eg in entities.event_groups.values() if not eg.parent)
    max_depth = (max(node.depth for node in entities.event_groups.values())
                 - (1 if root_group.root_is_location_plan_period_master_group else 0))

    if root_group.root_is_location_plan_period_master_group:
        all_weight_vars = calculate_weight_vars_of_children_recursive(root_group)
    else:
        all_weight_vars = sum((calculate_weight_vars_of_children_recursive(lpp_master_group)
                               for lpp_master_group in root_group.children), [])

    return all_weight_vars


def add_constraints_avail_day_groups_activity(model: cp_model.CpModel):
    """
    Fügt Constraints hinzu, um sicherzustellen, dass nur so viele Child-Event-Groups aktiv sind,
    wie in der Parent-Avail-Day-Group mit dem Parameter 'nr_of_active_children' angegeben ist.
    """

    for avail_day_group_id, avail_day_group in entities.avail_day_groups.items():
        if not avail_day_group.children:
            continue
        nr_of_active_children = (avail_day_group.nr_of_active_children
                                 or len([c for c in avail_day_group.children if c.children or c.avail_day]))
        child_vars = (entities.avail_day_group_vars[c.avail_day_group_id] for c in avail_day_group.children
                      if c.children or c.avail_day)
        # Wenn es sich bei der Avail-Day-Group um eine Root-Avail-Day-Group handelt, ist diese garantiert aktiv.
        if avail_day_group.is_root:
            model.Add(sum(child_vars) == nr_of_active_children)
        # Wenn es sich um eine Child-Avail-Day-Group handelt, ist diese eventuell nicht aktiv.
        # In diesem Fall sollen keine aktiven existieren.
        else:
            model.Add(sum(child_vars) == nr_of_active_children * entities.avail_day_group_vars[avail_day_group_id])


def add_constraints_required_avail_day_groups(model: cp_model.CpModel):
    """
    Falls die Parent-Avail-Day-Group eine Required-Avail-Day-Group hat, wird eine
    zusätzliche Bedingung hinzugefügt, dass mindestens so viele Schichten wie in required_avail_day_groups
    geplant werden oder gar keine Schichten geplant werden.
    """

    for avail_day_group_id, avail_day_group in entities.avail_day_groups.items():
        if required := avail_day_group.required_avail_day_groups:
            # Erstelle die Binärvariable y über NewBoolVar.
            y = model.NewBoolVar("y")

            # Definiere die Summe der Schichtvariablen.
            shift_sum = sum(
                shift_var
                for (adg_id, evg_id), shift_var in entities.shift_vars.items()
                if adg_id in [a.avail_day_group_id for a in avail_day_group.children]
                and (entities.event_groups_with_event[evg_id].event.location_plan_period.location_of_work.id
                in {l.id for l in required.locations_of_work} if required.locations_of_work else True)
            )

            # Füge eine Nebenbedingung hinzu, die sicherstellt,
            # dass shift_sum entweder 0 oder required.num_avail_day_groups ist.
            # Wenn y = 0 => shift_sum = 0, wenn y = 1 => shift_sum = required.
            model.Add(shift_sum == required.num_avail_day_groups * y)


def add_constraints_num_shifts_in_avail_day_groups(model: cp_model.CpModel):
    """
        Wenn die BoolVar einer avail_day_group mit avail_day wegen Einschränkungen durch nr_avail_day_groups
        auf False gesetzt ist (siehe Funktion add_constraints_avail_day_groups_activity()), müssen auch die zugehörigen
        BoolVars der shifts auf False gesetzt sein.
        Der Unterschied zu nr_event_groups ist, dass nr_event_groups angibt wie viele Event-Groups innerhalb einer
        Event-Group stattfinden müssen, während nr_avail_day_groups angibt, wie viele Avail-Day-Groups innerhalb einer
        Avail-Day-Group maximal stattfinden können.
        Daher diese Constraints.
    """
    for (adg_id, event_group_id), shift_var in entities.shift_vars.items():
        model.AddMultiplicationEquality(0, [shift_var, entities.avail_day_group_vars[adg_id].Not()])


def add_constraints_weights_in_avail_day_groups(model: cp_model.CpModel) -> list[IntVar]:
    """
        Fügt Constraints hinzu, um sicherzustellen, dass Child-Avail-Day-Groups mit höherer Gewichtung bevorzugt werden.
        Die justierten Gewichtungen werden jeweils zu den nächsten Child-Groups durchgereicht, wo sie zu den
        Gewichtungen dieser Child-Groups addiert werden. Falls eine Child-Avail-Day-Group ein Avail-Day besitzt, wird
        diese kumulierte Gewichtung als Constraint hinzugefügt.
        Um Verfälschungen durch Level-Verstärkungen zu vermeiden, wenn die Zweige des Gruppenbaums
        unterschiedliche Tiefen haben, werden die Constraints stets so berechnet, als befänden sich die
        Avail-Day-Groups mit Avail-Days auf der untersten Stufe.
        Falls nr_of_active_children < len(children), wird ebenso die kumulierte Gewichtung der Avail-Day-Group mit
        Avail-Day gesetzt, falls der dazugehörige Event stattfindet.
        not_sure: Überlegen, ob es sinnvoll ist, eine alternative Implementierung wie bei
          'add_constraints_weights_in_event_groups' zu verwenden. Dies entspräche unter Umständen eher der Nutzerlogik.
          Der Nutzer geht vermutlich davon aus, dass übergeordnete Gruppen
          eine höhere Relevanz haben.
    """

    multiplier_weights = (curr_config_handler.get_solver_config()
                              .constraints_multipliers.sliders_weights_avail_day_groups)
    shift_vars_of_adg_ids: defaultdict[UUID, list] = defaultdict(list)

    def calculate_weight_vars_of_children_recursive(group: AvailDayGroup,
                                                    cumulative_adjusted_weight: int = 0) -> list[IntVar]:
        weight_vars: list[IntVar] = []
        for c in group.children:
            if c.avail_day:
                # Es wird kein IntVar erstellt, wenn kein Einsatz dieses AvalDays möglich ist:
                if not sum(val for (adg_id, evg_id), val in entities.shifts_exclusive.items()
                           if adg_id == c.avail_day_group_id
                           and check_time_span_avail_day_fits_event(
                               entities.event_groups_with_event[evg_id].event,
                               entities.avail_day_groups_with_avail_day[adg_id].avail_day)):
                    continue
                # für die fehlenden Level wird jew. die Gewichtung 1 (default: 0) gesetzt:
                adjusted_weight = (max_depth - c.depth) * multiplier_weights[1] + multiplier_weights[c.weight]
                weight_vars.append(
                    model.NewIntVar(-100, 100000,
                                    f'Depth {group.depth}, AvailDay: {c.avail_day.date:%d.%m.%y}, '
                                    f'{c.avail_day.time_of_day.name}, '
                                    f'{c.avail_day.actor_plan_period.person.f_name}')
                )
                # stelle fest, ob ein zugehöriges Event stattfindet:
                adg_has_shifts = model.NewBoolVar('')
                model.Add(adg_has_shifts == sum(shift_vars_of_adg_ids[c.avail_day_group_id]))
                model.Add(weight_vars[-1] == ((cumulative_adjusted_weight + adjusted_weight) * adg_has_shifts))
            else:
                adjusted_weight = multiplier_weights[c.weight]
                weight_vars.extend(
                    calculate_weight_vars_of_children_recursive(c,
                                                                cumulative_adjusted_weight + adjusted_weight))
        return weight_vars

    root_group = next(eg for eg in entities.avail_day_groups.values() if not eg.parent)
    max_depth = (max(node.depth for node in entities.avail_day_groups.values())
                 - (1 if root_group.group_is_actor_plan_period_master_group else 0))

    for (adg_id, _), bool_var in entities.shift_vars.items():
        shift_vars_of_adg_ids[adg_id].append(bool_var)

    if root_group.group_is_actor_plan_period_master_group:
        all_weight_vars = calculate_weight_vars_of_children_recursive(root_group)
    else:
        all_weight_vars = sum((calculate_weight_vars_of_children_recursive(app_master_group)
                               for app_master_group in root_group.children), [])

    return all_weight_vars


def add_constraints_location_prefs(model: cp_model.CpModel) -> list[IntVar]:
    # todo: Schleifen können vermutlich vereinfacht werden, indem zuerst über entities.shift_vars iteriert wird.
    loc_pref_vars = []

    multiplier_slider = curr_config_handler.get_solver_config().constraints_multipliers.sliders_location_prefs

    event_data = {
        (
            event_group.event.date,
            event_group.event.time_of_day.time_of_day_enum.time_index,
            event_group.event.location_plan_period.location_of_work.id
        ): (eg_id, event_group)
        for eg_id, event_group in entities.event_groups_with_event.items()
    }

    for avail_day_group_id, avail_day_group in entities.avail_day_groups_with_avail_day.items():
        avail_day = avail_day_group.avail_day
        for loc_pref in [alp for alp in avail_day_group.avail_day.actor_location_prefs_defaults if not alp.prep_delete]:
            eg_id__event_group = event_data.get(
                (avail_day.date, avail_day.time_of_day.time_of_day_enum.time_index, loc_pref.location_of_work.id))
            if not eg_id__event_group:
                continue
            eg_id, event_group = eg_id__event_group
            shift_var = entities.shift_vars[(avail_day_group_id, eg_id)]
            event = event_group.event

            if loc_pref.score == 0:
                model.add(shift_var == 0)
                continue
            loc_pref_vars.append(
                model.NewIntVar(
                    multiplier_slider[2],
                    multiplier_slider[0.5],
                    f'{event.date:%d.%m.%Y} ({event.time_of_day.name}), '
                    f'{event.location_plan_period.location_of_work.name}: '
                    f'{avail_day.actor_plan_period.person.f_name}'))

            model.AddMultiplicationEquality(
                loc_pref_vars[-1],
                [
                    shift_var,
                    entities.event_group_vars[eg_id],
                    multiplier_slider[loc_pref.score]
                ]
            )

    return loc_pref_vars


def add_constraints_partner_location_prefs(model: cp_model.CpModel) -> list[IntVar]:
    plp_constr_multipliers = curr_config_handler.get_solver_config().constraints_multipliers.sliders_partner_loc_prefs

    partner_loc_pref_vars: list[IntVar] = []

    for eg_id, event_group in entities.event_groups_with_event.items():
        if event_group.event.cast_group.nr_actors < 2:
            continue
        # Get all AvailDayGroups with the same date and time of day
        avail_day_groups = (adg for adg_id, adg in entities.avail_day_groups_with_avail_day.items()
                            if entities.shifts_exclusive[adg_id, eg_id])
        # Get all combinations of possible AvailDayGroups for this event
        duo_combs = itertools.combinations(avail_day_groups, 2)
        for combo in duo_combs:
            combo: tuple[AvailDayGroup, AvailDayGroup]
            # Only add constraint if there is at least one partner with partner_location_preference...
            if not any(len(adg.avail_day.actor_partner_location_prefs_defaults) for adg in combo):
                continue
            # ...and if the partners are not the same...
            if combo[0].avail_day.actor_plan_period.id == combo[1].avail_day.actor_plan_period.id:
                continue
            partner_loc_pref_vars.append(
                model.NewIntVar(
                    plp_constr_multipliers[2] * 2, plp_constr_multipliers[0] * 2,
                    f'{event_group.event.date:%d.%m.%y} ({event_group.event.time_of_day.name}), '
                    f'{event_group.event.location_plan_period.location_of_work.name} '
                    f'{combo[0].avail_day.actor_plan_period.person.f_name} + '
                    f'{combo[1].avail_day.actor_plan_period.person.f_name}')
            )

            # Kalkuliere die Scores der Partner-Location-Pref-Variablen. Falls keine Variable mit dem Partner und der
            # entsprechenden Location existiert, ist der Score 1.
            score_0 = next((plp.score for plp in combo[0].avail_day.actor_partner_location_prefs_defaults
                            if plp.partner.id == combo[1].avail_day.actor_plan_period.person.id
                            and plp.location_of_work.id == event_group.event.location_plan_period.location_of_work.id),
                           1)
            score_1 = next((plp.score for plp in combo[1].avail_day.actor_partner_location_prefs_defaults
                            if plp.partner.id == combo[0].avail_day.actor_plan_period.person.id
                            and plp.location_of_work.id == event_group.event.location_plan_period.location_of_work.id),
                           1)

            # Intermediate variables that allow the calculation of the Partner-Location-Pref variable based on the
            # Shift variables and Event-Group variable:
            plp_weight_var = model.NewIntVar(plp_constr_multipliers[2] * 2, plp_constr_multipliers[0] * 2, '')
            shift_active_var = model.NewBoolVar('')  # 1, wenn alle Personen der Combo besetzt sind, sonst 0
            all_active_var = model.NewBoolVar('')  # 1, wenn zudem das Event stattfindet, sonst 0

            # not_sure: plp_weight_var wird hier mit der anvisierten Besetzungsstärke ermittelt,
            #  sollte aber vielleicht mit der tatsächlichen Besetzungsstärke ermittelt werden...
            #  Nachteil davon: Mitarbeiter werden nicht besetzt, wenn bei einem Mitarbeiter die Partner-Location-Pref 0
            #  ist und die aktuelle Besetzungsstärke 2 ist, obwohl durch nachträgliche Bearbeitung des Plans die
            #  Besetzungsstärke größer als 2 sein könnte.
            model.Add(plp_weight_var == round(
                (plp_constr_multipliers[score_0] + plp_constr_multipliers[score_1]) /
                (event_group.event.cast_group.nr_actors - 1))
                      )

            model.AddMultiplicationEquality(shift_active_var,
                                            [entities.shift_vars[(combo[0].avail_day_group_id, eg_id)],
                                             entities.shift_vars[(combo[1].avail_day_group_id, eg_id)]])
            model.AddMultiplicationEquality(all_active_var, [shift_active_var, entities.event_group_vars[eg_id]])
            model.AddMultiplicationEquality(partner_loc_pref_vars[-1], [plp_weight_var, all_active_var])

            # Falls eine der Personen absolut nicht mit der anderen Person besetzt werden soll
            # und die Besetzungsstärke 2 ist, wird nur 1 dieser Personen besetzt:
            exclusive = 0 if (score_0 and score_1) or event_group.event.cast_group.nr_actors >= 3 else 1
            model.Add(entities.shift_vars[(combo[0].avail_day_group_id, eg_id)]
                      + entities.shift_vars[(combo[1].avail_day_group_id, eg_id)] < 2).OnlyEnforceIf(exclusive)

    return partner_loc_pref_vars


def add_constraints_cast_rules(model: cp_model.CpModel) -> list[IntVar]:
    """
    Erstellt Cast-Regel-Constraints für den SAT-Solver.

    Implementiert Regeln für Event-Besetzungen:
    - Different Cast ("-"): Events müssen mit verschiedenen Mitarbeitern besetzt sein
    - Same Cast ("~"): Events müssen mit den gleichen Mitarbeitern besetzt sein
    - No Rule ("*"): Keine Besetzungsregel

    Args:
        model: Das CP-SAT Model für Constraint-Erstellung

    Returns:
        Liste der Constraint-Variablen für gebrochene Regeln (bei strict_rule_pref == 1)

    TODO: Anpassen für den Fall, dass nr_actors in Event Group < als len(children).
          Könnte man lösen, indem der Index der 1. aktiven Gruppe in einer Variablen
          abgelegt wird und die Besetzung dieser Gruppe als Referenz genommen wird.
    TODO: Bisher nur Cast Groups auf Level 1 berücksichtigt
    """

    def different_cast(event_group_1: schemas.EventGroup, event_group_2: schemas.EventGroup,
                       strict_rule_pref: int) -> list[IntVar]:
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

        for app_id, actor_plan_period in entities.actor_plan_periods.items():
            # Sammle alle relevanten Schicht-Variablen für beide Event Groups
            shift_vars = {(adg_id, eg_id): var for (adg_id, eg_id), var in entities.shift_vars.items()
                          if eg_id in {event_group_1.id, event_group_2.id}
                          and entities.avail_day_groups[adg_id].avail_day.actor_plan_period.id == app_id
                          and entities.avail_day_groups_with_avail_day[adg_id].avail_day.date
                          in {event_group_1.event.date, event_group_2.event.date}
                          and entities.shifts_exclusive[(adg_id, eg_id)]}

            if strict_rule_pref == 2:
                # Harte Regel: Mitarbeiter kann maximal in einer Event Group arbeiten
                model.Add(sum(shift_vars.values()) <= 1)
            elif strict_rule_pref == 1:
                # Weiche Regel: Erstelle Variable für Regelverstoß
                name_var = (f'{event_group_1.event.date:%d.%m.} + {event_group_2.event.date:%d.%m.}, '
                            f'{event_group_1.event.location_plan_period.location_of_work.name}, '
                            f'{actor_plan_period.person.f_name}')
                equal_to_two = model.NewBoolVar(name_var)
                model.AddMaxEquality(equal_to_two, [sum(shift_vars.values()) - 1, 0])
                broken_rules_vars.append(equal_to_two)

        return broken_rules_vars

    def same_cast(cast_group_1: CastGroup, cast_group_2: CastGroup, strict_rule_pref: int) -> list[IntVar]:
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

        event_group_1_id = cast_group_1.event.event_group.id
        event_group_2_id = cast_group_2.event.event_group.id

        # Erstelle Boolean-Arrays für tatsächliche Schicht-Zuweisungen
        applied_shifts_1: list[IntVar] = [
            model.NewBoolVar(f'{cast_group_1.event.date:%d.%m.}: {app.person.f_name}')
            for app in entities.actor_plan_periods.values()
        ]
        applied_shifts_2: list[IntVar] = [
            model.NewBoolVar(f'{cast_group_2.event.date:%d.%m.}: {app.person.f_name}')
            for app in entities.actor_plan_periods.values()
        ]

        # Speichere für Debug-Zwecke in solver_variables
        solver_variables.cast_rules.applied_shifts_1.append(applied_shifts_1)
        solver_variables.cast_rules.applied_shifts_2.append(applied_shifts_2)

        # Verknüpfe Boolean-Arrays mit tatsächlichen Schicht-Variablen
        for i, (app_id, app) in enumerate(entities.actor_plan_periods.items()):
            # Finde Schicht-Variable für Event 1
            shift_var_1 = next((v for (adg_id, eg_id), v in entities.shift_vars.items()
                                if eg_id == event_group_1_id
                                and entities.avail_day_groups[adg_id].avail_day.actor_plan_period.id == app_id
                                and entities.shifts_exclusive[(adg_id, eg_id)]), 0)
            # Finde Schicht-Variable für Event 2
            shift_var_2 = next((v for (adg_id, eg_id), v in entities.shift_vars.items()
                                if eg_id == event_group_2_id
                                and entities.avail_day_groups[adg_id].avail_day.actor_plan_period.id == app_id
                                and entities.shifts_exclusive[(adg_id, eg_id)]), 0)

            model.Add(applied_shifts_1[i] == shift_var_1)
            model.Add(applied_shifts_2[i] == shift_var_2)

        # Berechne Unterschiede zwischen den Besetzungen (XOR-Logic)
        curr_is_unequal: list[IntVar] = []

        for i, app in enumerate(entities.actor_plan_periods.values()):
            curr_is_unequal.append(
                model.NewBoolVar(f'{cast_group_1.event.date:%d.%m.}: {app.person.f_name}')
            )
            # Hilfsvariable für XOR-Implementierung
            factor = model.NewIntVar(0, 1, '')
            # XOR-Bedingung: unterschiedlich wenn genau einer der beiden true ist
            model.Add(applied_shifts_1[i] + applied_shifts_2[i] == curr_is_unequal[-1] + 2 * factor)

        solver_variables.cast_rules.is_unequal.extend(curr_is_unequal)

        if strict_rule_pref == 2:
            # Harte Regel: Anzahl Unterschiede <= erlaubte Differenz
            (model.Add(sum(curr_is_unequal) <= abs(cast_group_1.nr_actors - cast_group_2.nr_actors))
             .OnlyEnforceIf([entities.event_group_vars[event_group_1_id],
                             entities.event_group_vars[event_group_2_id]]))
            return broken_rules_vars
        elif strict_rule_pref == 1:
            # Weiche Regel: Erstelle Variable für Regelverstoß
            max_diff = cast_group_1.nr_actors + cast_group_2.nr_actors
            broken_rules_var = model.NewIntVar(0, max_diff,
                                               f'{cast_group_1.event.date:%d.%m.} + '
                                               f'{cast_group_2.event.date:%d.%m.}, '
                                               f'{cast_group_1.event.location_plan_period.location_of_work.name}')
            # Zwischenvariable für Berechnung
            intermediate = model.NewIntVar(0, max_diff, '')
            (model.Add(intermediate == (sum(curr_is_unequal) -
                                        abs(cast_group_1.nr_actors - cast_group_2.nr_actors)))
             .OnlyEnforceIf([entities.event_group_vars[event_group_1_id],
                             entities.event_group_vars[event_group_2_id]]))
            model.AddDivisionEquality(broken_rules_var, intermediate, 2)
            broken_rules_vars.append(broken_rules_var)
            return broken_rules_vars
        elif strict_rule_pref == 0:
            # Keine Regel aktiv
            return broken_rules_vars
        else:
            raise ValueError(f'Unbekannte strict_rule_pref: {strict_rule_pref}')

    # Hauptlogik der Funktion
    constraints_cast_rule: list[IntVar] = []

    # Sammle alle Cast Groups auf Level 1, gruppiert nach Parent
    cast_groups_level_1 = collections.defaultdict(list)
    for cast_group in entities.cast_groups_with_event.values():
        cast_groups_level_1[cast_group.parent.cast_group_id].append(cast_group)

    # Sortiere Cast Groups chronologisch für konsistente Reihenfolge
    for cast_groups in cast_groups_level_1.values():
        cast_groups.sort(key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index))

    # Verarbeite jede Cast Group Hierarchie
    for cg_id, cast_groups in cast_groups_level_1.items():
        cast_groups: list[CastGroup]
        parent = entities.cast_groups[cg_id]

        # Überspringe wenn keine Regel definiert oder inaktiv
        if not (rule := parent.cast_rule) or parent.strict_rule_pref == 0:
            continue

        # Wende Regeln auf aufeinanderfolgende Cast Groups an
        for idx in range(len(cast_groups) - 1):
            event_group_1 = cast_groups[idx].event.event_group
            event_group_2 = cast_groups[idx + 1].event.event_group

            # Regel-Symbol aus zyklischem Pattern ermitteln
            if rule[idx % len(rule)] == '-':
                # Different Cast Regel anwenden
                constraints_cast_rule.extend(different_cast(event_group_1, event_group_2,
                                                            parent.strict_rule_pref))
            elif rule[idx % len(rule)] == '~':
                # Same Cast Regel anwenden
                constraints_cast_rule.extend(same_cast(cast_groups[idx], cast_groups[idx + 1],
                                                       parent.strict_rule_pref))
            elif rule[idx % len(rule)] == '*':
                # Keine Regel - überspringen
                continue
            else:
                raise ValueError(f'unknown rule symbol: {rule}')

    return constraints_cast_rule


def filter_unavailable_persons(
    fixed_cast_list: tuple | str, 
    cast_group: CastGroup
) -> tuple | str | None:
    """
    Entfernt nicht verfügbare Personen aus der fixed_cast Liste.
    
    Args:
        fixed_cast_list: Die geparste fixed_cast Liste (verschachtelte Struktur)
        cast_group: Die CastGroup mit Event-Informationen
    
    Returns:
        Gefilterte Liste oder None wenn keine Person verfügbar ist
    """
    if isinstance(fixed_cast_list, str):
        # Einzelne Person - prüfe Verfügbarkeit
        person_id = UUID(fixed_cast_list)
        if is_person_available_for_event(person_id, cast_group):
            return fixed_cast_list
        else:
            return None
    
    # Liste mit Operatoren - rekursiv filtern
    result = []
    for i, element in enumerate(fixed_cast_list):
        if i % 2 == 0:  # Person oder verschachtelte Liste
            filtered = filter_unavailable_persons(element, cast_group)
            if filtered is not None:
                result.append(filtered)
        else:  # Operator
            # Operator nur hinzufügen wenn vorher und nachher Elemente existieren
            if result and i + 1 < len(fixed_cast_list):
                result.append(element)
    
    # Bereinige: Entferne trailing Operatoren
    while result and isinstance(result[-1], str) and result[-1] in ('and', 'or'):
        result.pop()
    
    # Bereinige: Entferne leading Operatoren  
    while result and isinstance(result[0], str) and result[0] in ('and', 'or'):
        result.pop(0)

    return tuple(result) if len(result) > 1 else result[0] if result else None


def is_person_available_for_event(person_id: UUID, cast_group: CastGroup) -> bool:
    """
    Prüft, ob eine Person für ein spezifisches Event verfügbar ist.
    
    Args:
        person_id: UUID der Person
        cast_group: CastGroup mit Event-Informationen
    
    Returns:
        True, wenn Person verfügbar ist, sonst False
    """
    if cast_group.nr_actors == 0:
        return False
    event = cast_group.event
    event_group_id = event.event_group.id

    available = next(
        (bool(val) for (adg_id, eg_id), val in entities.shifts_exclusive.items()
         if eg_id == event_group_id
         and entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.person.id == person_id
         and entities.avail_day_groups_with_avail_day[adg_id].avail_day.date == event.date
         and entities.avail_day_groups_with_avail_day[adg_id].avail_day.time_of_day.time_of_day_enum.time_index
         == event.time_of_day.time_of_day_enum.time_index),
        False
    )

    return available

    pass

    # der folgende Code ist deprecated, da im Ergebnis äquivalent zu dem Code oben
    if cast_group.nr_actors == 0:
        return False
    event = cast_group.event
    event_group_id = event.event_group.id
    
    # Prüfe ob es shift_vars gibt für diese Person an diesem Tag/Event
    for (adg_id, eg_id), shift_var in entities.shift_vars.items():
        if eg_id != event_group_id:
            continue
        
        avail_day_group = entities.avail_day_groups_with_avail_day.get(adg_id)
        if not avail_day_group:
            continue
            
        # Prüfe Person, Datum und ob die Kombination möglich ist (shifts_exclusive)
        if (avail_day_group.avail_day.actor_plan_period.person.id == person_id
            and avail_day_group.avail_day.date == event.date
            and entities.shifts_exclusive.get((adg_id, eg_id), 0) == 1):
            return True
    
    return False


def is_empty_list(fixed_cast_list: tuple | str | None) -> bool:
    """
    Prüft ob eine fixed_cast Liste leer ist (rekursiv).
    """
    if fixed_cast_list is None:
        return True
    if isinstance(fixed_cast_list, str):
        return False
    if not fixed_cast_list:
        return True
    
    # Prüfe ob alle Elemente leer sind
    for element in fixed_cast_list:
        if isinstance(element, str) and element in ('and', 'or'):
            continue  # Operatoren überspringen
        if not is_empty_list(element):
            return False
    
    return True


def add_constraints_fixed_cast(model: cp_model.CpModel) -> tuple[
    dict[tuple[datetime.date, str, UUID], IntVar],
    list[IntVar]
]:
    # todo: funktioniert bislang nur für CastGroups mit Event
    
    def check_pers_id_in_shift_vars(pers_id: UUID, cast_group: CastGroup) -> IntVar:
        var = model.NewBoolVar('')
        model.Add(var == sum(shift_var for (adg_id, eg_id), shift_var in entities.shift_vars.items()
                             if eg_id == cast_group.event.event_group.id
                             and entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.person.id
                             == pers_id))
        return var

    def create_var_and(var_list: list[IntVar]) -> IntVar:
        var = model.NewBoolVar('')
        model.AddMultiplicationEquality(var, var_list)
        return var

    def create_var_or(var_list: list[IntVar]) -> IntVar:
        var = model.NewBoolVar('')
        model.Add(var == sum(var_list))
        return var

    def proof_recursive(fixed_cast_list: tuple | str, cast_group: CastGroup) -> IntVar:
        if isinstance(fixed_cast_list, str):
            return check_pers_id_in_shift_vars(UUID(fixed_cast_list), cast_group)
        pers_ids = [v for i, v in enumerate(fixed_cast_list) if not i % 2]
        operators = [v for i, v in enumerate(fixed_cast_list) if i % 2]
        if any(o != operators[0] for o in operators):
            raise Exception('Alle Operatoren müssen gleich sein!')  # sourcery skip: raise-specific-error
        else:
            operator = operators[0]

        if operator == 'and':
            return create_var_and([proof_recursive(p_id, cast_group) for p_id in pers_ids])
        else:
            return create_var_or([proof_recursive(p_id, cast_group) for p_id in pers_ids])

    def parse_and_filter_fixed_cast(cast_group: CastGroup) -> tuple | str | None:
        """
        Parsed fixed_cast String und filtert optional nicht verfügbare Personen.
        
        Args:
            cast_group: CastGroup mit fixed_cast String
        
        Returns:
            - Parsed fixed_cast_as_list wenn verfügbare Personen vorhanden
            - None wenn keine Personen übrig bleiben (bei only_if_available)
        """
        # String wird zu Python-Objekt umgewandelt
        fixed_cast_as_list = literal_eval(cast_group.fixed_cast
                              .replace('and', ',"and",')
                              .replace('or', ',"or",')
                              .replace('in team', '')
                              .replace('UUID', ''))
        
        # Wenn only_if_available aktiviert ist, filtere nicht verfügbare Personen
        if cast_group.fixed_cast_only_if_available:
            fixed_cast_as_list = filter_unavailable_persons(
                fixed_cast_as_list, 
                cast_group
            )
            
            # Falls nach dem Filtern keine Personen übrig sind
            if not fixed_cast_as_list or is_empty_list(fixed_cast_as_list):
                return None
        
        return fixed_cast_as_list

    fixed_cast_vars = {(datetime.date(1999, 1, 1), 'dummy', UUID('00000000-0000-0000-0000-000000000000')): model.NewBoolVar('')}
    for cast_group in entities.cast_groups_with_event.values():
        if not cast_group.fixed_cast:
            continue

        # Parsed fixed_cast und filtere optional nicht verfügbare Personen
        fixed_cast_as_list = parse_and_filter_fixed_cast(cast_group)
        if fixed_cast_as_list is None:
            continue

        text_fixed_cast_persons = generate_fixed_cast_clear_text(cast_group.fixed_cast,
                                                                 cast_group.fixed_cast_only_if_available,
                                                                 cast_group.prefer_fixed_cast_events)
        text_fixed_cast_var = (f'Datum: {cast_group.event.date: %d.%m.%y} ({cast_group.event.time_of_day.name})\n'
                               f'Ort: {cast_group.event.location_plan_period.location_of_work.name_an_city}\n'
                               f'Besetzung: {text_fixed_cast_persons}')

        fixed_cast_vars[key := (cast_group.event.date, cast_group.event.time_of_day.name, cast_group.event.id)] = (
            model.NewBoolVar(text_fixed_cast_var)
        )

        (model.Add(fixed_cast_vars[key] == proof_recursive(fixed_cast_as_list, cast_group).Not())
         .OnlyEnforceIf(entities.event_group_vars[cast_group.event.event_group.id]))

    # ============================================================================
    # NEU: Tracking für prefer_fixed_cast_events
    # ============================================================================
    
    def extract_person_uuids(fixed_cast_list: tuple | str) -> list[UUID]:
        """
        Extrahiert alle Person-UUIDs aus der verschachtelten fixed_cast Struktur.
        
        Args:
            fixed_cast_list: Parsed fixed_cast_as_list (kann verschachtelt sein)
        
        Returns:
            Liste aller Person-UUIDs (ohne Operatoren wie 'and', 'or')
        """
        if isinstance(fixed_cast_list, str):
            # Einzelne UUID
            return [UUID(fixed_cast_list)]
        
        # Tuple mit mehreren Elementen - sammle rekursiv alle UUIDs
        result = []
        for element in fixed_cast_list:
            if isinstance(element, str):
                # Überspringe Operatoren
                if element not in ('and', 'or'):
                    result.append(UUID(element))
            else:
                # Rekursiver Aufruf für verschachtelte Strukturen
                result.extend(extract_person_uuids(element))
        
        return result
    
    def has_only_and_operators(fixed_cast_list: tuple | str) -> bool:
        """
        Prüft ob die fixed_cast Struktur ausschließlich AND-Operatoren enthält.
        
        Wenn nur AND-Operatoren vorhanden sind, können wir pro Person eine Penalty-Variable
        erstellen. Bei OR-Operatoren ist die Semantik anders (mindestens einer muss besetzt sein),
        daher verwenden wir in dem Fall die alte Event-basierte Logik.
        
        Args:
            fixed_cast_list: Parsed fixed_cast_as_list (kann verschachtelt sein)
        
        Returns:
            True wenn nur AND-Operatoren (oder keine Operatoren), False bei OR-Operatoren
        """
        if isinstance(fixed_cast_list, str):
            # Einzelne UUID - kein Operator
            return True
        
        # Prüfe alle Operatoren in der Struktur
        for element in fixed_cast_list:
            if isinstance(element, str):
                if element == 'or':
                    return False  # OR gefunden!
                # 'and' ist ok, andere Strings sind UUIDs (ok)
            else:
                # Rekursiv in verschachtelte Strukturen
                if not has_only_and_operators(element):
                    return False
        
        return True
    
    preference_vars = []
    
    for cast_group in entities.cast_groups_with_event.values():
        # 1. Grundvoraussetzungen prüfen
        if not (cast_group.fixed_cast and cast_group.prefer_fixed_cast_events):
            continue
        
        # 2. Relevanz-Prüfung: Ist Preference überhaupt relevant?
        parent_cast_group = cast_group.parent
        if not parent_cast_group:
            continue  # Keine Parent-Group → keine Auswahl → Preference irrelevant
        
        # Hole die zugehörige EventGroup
        event_group_id = cast_group.event.event_group.id
        event_group = entities.event_groups_with_event.get(event_group_id)
        if not event_group or not event_group.parent:
            continue  # Keine Parent EventGroup → Preference irrelevant
        
        parent_event_group = event_group.parent
        
        # Prüfe ob Parent überhaupt eine Auswahl trifft
        nr_of_active_children = parent_event_group.nr_of_active_children
        if nr_of_active_children is None:
            continue  # Alle Children werden ausgewählt → Preference irrelevant
        
        # Zähle die Children der Parent-Group die Events haben
        children_with_event = [c for c in parent_event_group.children if c.event]
        if nr_of_active_children >= len(children_with_event):
            continue  # Alle Events werden ausgewählt → Preference irrelevant
        
        # 3. Verfügbarkeits-Prüfung (bei fixed_cast_only_if_available)
        fixed_cast_as_list = parse_and_filter_fixed_cast(cast_group)
        if fixed_cast_as_list is None:
            continue  # Keine Preference wenn Event nicht besetzbar
        
        # 4. NEU: Erstelle Preference-Variable basierend auf Operator-Typ
        # TODO: Verbesserungspotential für komplexe OR-Logik
        #
        # AKTUELLES VERHALTEN:
        # - Bei reinem AND (z.B. "uuid1 AND uuid2"): Pro Mitarbeiter 1 Penalty
        #   → 2 Mitarbeiter nicht besetzt = 2 Penalties ✓
        #
        # - Bei OR-Operatoren (z.B. "uuid1 OR uuid2"): 1 Penalty pro Event
        #   → Semantisch: "Mindestens einer muss besetzt sein"
        #   → Aktuell: Event-basierte Penalty (entweder 0 oder 1)
        #
        # PROBLEM:
        # - Komplexe Strukturen wie "((uuid1 AND uuid2) OR uuid3)" werden nicht optimal behandelt
        # - Bei reinem OR: Unterscheidung nicht möglich zwischen "1 von 2 besetzt" vs "0 von 2 besetzt"
        #
        # MÖGLICHE VERBESSERUNG:
        # - Rekursive Operator-Logik analog zu proof_recursive()
        # - Zähle "erforderliche Mindestbesetzung" statt binär Event ja/nein
        # - Beispiel: "(uuid1 AND uuid2) OR uuid3" → Min 1 Slot erforderlich, nicht 3 Personen
        #
        # AUFWAND: Hoch (komplexe rekursive Logik)
        # NUTZEN: Gering (die meisten fixed_casts sind einfache ANDs)
        # ENTSCHEIDUNG: Aktuell "gut genug" - bei Bedarf später erweitern
        
        if has_only_and_operators(fixed_cast_as_list):
            # Strategie A: Pro-Person Penalties (bei reinem AND)
            # Extrahiere alle Person-UUIDs aus der verschachtelten Struktur
            person_uuids = extract_person_uuids(fixed_cast_as_list)
            
            for person_uuid in person_uuids:
                # Prüfe ob diese Person dem Event zugewiesen ist
                is_assigned_var = check_pers_id_in_shift_vars(person_uuid, cast_group)
                
                # Erstelle Penalty-Variable: 1 wenn Mitarbeiter NICHT zugewiesen
                person = next(
                    (app.person for app in entities.actor_plan_periods.values() 
                     if app.person.id == person_uuid),
                    None
                )
                person_name = person.f_name if person else str(person_uuid)[:8]
                
                penalty_var = model.NewIntVar(0, 1, 
                    f'Prefer: {cast_group.event.date:%d.%m.%y} '
                    f'({cast_group.event.time_of_day.name}), '
                    f'{cast_group.event.location_plan_period.location_of_work.name_an_city}, '
                    f'{person_name}'
                )
                
                # penalty_var = 1 wenn Mitarbeiter NICHT zugewiesen
                # penalty_var = 0 wenn Mitarbeiter zugewiesen
                model.Add(penalty_var == 1 - is_assigned_var)
                
                preference_vars.append(penalty_var)
        else:
            # Strategie B: Event-basierte Penalty (bei OR-Operatoren)
            # Fallback auf alte Logik: 1 Penalty wenn Event nicht gewählt
            penalty_var = model.NewIntVar(0, 1, 
                f'Prefer: {cast_group.event.date:%d.%m.%y} '
                f'({cast_group.event.time_of_day.name}), '
                f'{cast_group.event.location_plan_period.location_of_work.name_an_city}'
            )
            
            # penalty_var = 1 wenn Event NICHT ausgewählt (entities.event_group_vars[...] == 0)
            # penalty_var = 0 wenn Event ausgewählt (entities.event_group_vars[...] == 1)
            model.Add(penalty_var == 1 - entities.event_group_vars[event_group_id])
            
            preference_vars.append(penalty_var)
    
    # ============================================================================

    return fixed_cast_vars, preference_vars


def add_constraints_skills(model: cp_model.CpModel) -> list[IntVar]:
    skill_conflict_vars = []

    for eg_id, event_group in entities.event_groups_with_event.items():
        if not event_group.event.skill_groups:
            continue

        for skill_group in event_group.event.skill_groups:
            skill = skill_group.skill
            #  Summe aller zugewiesenen avail_day_groups mit dem skill muss
            #  >= min(geforderten Anzahl der Mitarbeiter mit Skill, Besetzungsstärke)
            num_employees_with_skill = min(skill_group.nr_actors, event_group.event.cast_group.nr_actors)
            skill_conflict_vars.append(
                model.NewIntVar(
                    -10, 10,
                    f'Datum: {event_group.event.date:%d.%m.%y} ({event_group.event.time_of_day.name})\n'
                    f'Ort: {event_group.event.location_plan_period.location_of_work.name_an_city}\n'
                    f'benötigt: {num_employees_with_skill} Mitarbeiter mit Fertigkeit "{skill.name}"')
            )
            num_fulfilled_cond = (sum(entities.shift_vars[(adg_id, eg_id)]
                                       for adg_id, adg in entities.avail_day_groups_with_avail_day.items()
                                       if skill in adg.avail_day.skills))

            # Differenz der Anzahl der Mitarbeiter mit Skill und der geforderten Anzahl
            # wird der Variablen zugewiesen:
            model.AddMaxEquality(
                skill_conflict_vars[-1], [0, num_employees_with_skill - num_fulfilled_cond]
            )

    return skill_conflict_vars


def add_constraints_unsigned_shifts(model: cp_model.CpModel) -> dict[UUID, IntVar]:
    unassigned_shifts_per_event = {
        event_group_id: model.NewIntVar(
            0, max(evg.event.cast_group.nr_actors
                   for evg in entities.event_groups_with_event.values()), f'unassigned {event_group.event.date}'
        )
        for event_group_id, event_group in entities.event_groups_with_event.items()}

    for event_group_id, event_group in entities.event_groups_with_event.items():
        # Summe aller zugewiesenen Freelancer zum Event:
        num_assigned_employees = sum(
            entities.shift_vars[(adg_id, event_group_id)] for adg_id in entities.avail_day_groups_with_avail_day
        )
        # Summe der zugewiesenen Freelancer muss kleiner oder gleich der einzusetzenden Mitarbeiter sein, falls
        # wenn das Event stattfindet (über add_constraints_event_groups_activity wird das eingeschränkt):
        model.Add(
            num_assigned_employees <= (entities.event_group_vars[event_group.event_group_id]
                                       * event_group.event.cast_group.nr_actors)
        )
        # Variablen für unsigned shifts werden erstellt. Wenn die zum Event zugehörige EventGroup nicht stattfindet,
        # werden die unassigned_shifts_per_event durch Multiplikation mit der EventGroup-Variablen 0.:
        model.Add(unassigned_shifts_per_event[event_group_id] == (
                entities.event_group_vars[event_group.event_group_id] * event_group.event.cast_group.nr_actors
                - num_assigned_employees))
    return unassigned_shifts_per_event


def add_constraints_different_casts_on_shifts_with_different_locations_on_same_day(model: cp_model.CpModel):
    """Besetzungen von Events an unterschiedlichen Locations welche am gleichen Tag stattfinden müssen unterschiedlich
       sein.
       Ausnahme, wenn CombinationLocationsPossible für die jeweiligen Events festgelegt wurden.
       todo: Diese Funktionalität soll deaktiviert werden können: Entweder über Configuration oder durch zusätzliche
        Felder in Projekt und Team.
    """

    def comb_locations_possible(adg_id_1: UUID, eg_id_1: UUID, adg_id_2: UUID, eg_id_2: UUID) -> bool:
        """
            Stellt fest, ob combination_locations_possibles bei den AvailDays existieren und diese zu den Locations der
            Events passen.
        """
        avail_day_group_1 = entities.avail_day_groups_with_avail_day[adg_id_1]
        avail_day_group_2 = entities.avail_day_groups_with_avail_day[adg_id_2]
        event_1 = entities.event_groups_with_event[eg_id_1].event
        event_2 = entities.event_groups_with_event[eg_id_2].event
        start_1 = datetime.datetime.combine(event_1.date, event_1.time_of_day.start)
        end_1 = datetime.datetime.combine(event_1.date, event_1.time_of_day.end)
        start_2 = datetime.datetime.combine(event_2.date, event_2.time_of_day.start)
        end_2 = datetime.datetime.combine(event_2.date, event_2.time_of_day.end)
        time_diff = start_1 - end_2 if start_1 > end_2 else start_2 - end_1
        location_1_id = entities.event_groups_with_event[eg_id_1].event.location_plan_period.location_of_work.id
        location_2_id = entities.event_groups_with_event[eg_id_2].event.location_plan_period.location_of_work.id

        clp_1 = next((clp for clp in avail_day_group_1.avail_day.combination_locations_possibles
                      if location_1_id in [loc.id for loc in clp.locations_of_work]
                      and location_2_id in [loc.id for loc in clp.locations_of_work]
                      and not clp.prep_delete), None)

        clp_2 = next((clp for clp in avail_day_group_2.avail_day.combination_locations_possibles
                      if location_1_id in [loc.id for loc in clp.locations_of_work]
                      and location_2_id in [loc.id for loc in clp.locations_of_work]
                      and not clp.prep_delete), None)

        return clp_1 and clp_2 and time_diff >= max(clp_1.time_span_between, clp_2.time_span_between)

    # erstellt ein defaultdict [date[actor_plan_period_id[location_id[list[tuple[tuple[adg_id, eg_id], shift_var]]]]]
    dict_date_shift_var: defaultdict[datetime.date, defaultdict[UUID, defaultdict[UUID, list[tuple[tuple[UUID, UUID], IntVar]]]]] = (
        defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    for (adg_id, eg_id), shift_var in entities.shift_vars.items():
        if not entities.shifts_exclusive[(adg_id, eg_id)]:
            continue
        date = entities.event_groups_with_event[eg_id].event.date
        # if ((date := entities.event_groups_with_event[eg_id].event.date)
        #         != entities.avail_day_groups_with_avail_day[adg_id].avail_day.date):
        #     continue
        actor_plan_period_id = entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.id
        location_id = entities.event_groups_with_event[eg_id].event.location_plan_period.location_of_work.id
        dict_date_shift_var[date][actor_plan_period_id][location_id].append(((adg_id, eg_id), shift_var))

    # erstellt Constraints
    for date, dict_actor_plan_period_id in dict_date_shift_var.items():
        for actor_plan_period_id, dict_location_id in dict_actor_plan_period_id.items():
            if len(dict_location_id) > 1:
                for loc_pair in itertools.combinations(list(dict_location_id.values()), 2):
                    for var_pair in itertools.product(*loc_pair):
                        if not comb_locations_possible(var_pair[0][0][0], var_pair[0][0][1],
                                                       var_pair[1][0][0], var_pair[1][0][1]):
                            model.Add(sum(v[1] for v in var_pair) <= 1)


def add_constraints_rel_shift_deviations(model: cp_model.CpModel) -> tuple[dict[UUID, IntVar], IntVar]:
    # Create a lists to represent the sums of assigned shifts and the relative shift deviations for each actor_plan_period.
    sum_assigned_shifts = {
        app.id: model.NewIntVar(lb=0, ub=1000, name=f'sum_assigned_shifts {app.person.f_name}')
        for app in entities.actor_plan_periods.values()
    }
    relative_shift_deviations = {
        app.id: model.NewIntVar(
            lb=-len(entities.event_groups_with_event) * 1_000_000,
            ub=len(entities.event_groups_with_event) * 1_000_000,
            name=f'relative_shift_deviation_{app.person.f_name}'
        )
        for app in entities.actor_plan_periods.values()
    }

    # Add a constraint for each actor_plan_period,
    # that the relative shift deviation is equal to (requested shifts - actual shifts) / requested shifts.
    for app in entities.actor_plan_periods.values():
        assigned_shifts_of_app = sum(
            sum(
                entities.shift_vars[(adg_id, evg_id)]
                for evg_id in entities.event_groups_with_event
            )
            for adg_id, adg in entities.avail_day_groups_with_avail_day.items()
            if adg.avail_day.actor_plan_period.id == app.id
        )
        model.AddAbsEquality(
            sum_assigned_shifts[app.id], assigned_shifts_of_app
        )
        shift_deviation = model.new_int_var(-1000, 1000, f'abs_shirt_deviation_{app.person.f_name}')
        model.Add(shift_deviation == assigned_shifts_of_app - int(app.requested_assignments))
        if app.requested_assignments < 0:
            print(f'{app.requested_assignments=}')
        model.AddDivisionEquality(
            relative_shift_deviations[app.id],
            shift_deviation * 1_000,
            int(app.requested_assignments * 10) if app.requested_assignments else 1)

    sum_requested_assignments = sum(app.requested_assignments for app in entities.actor_plan_periods.values()) or 0.1
    # Calculate the sum of all assigned shifts
    sum_assigned_shifts_sum = model.NewIntVar(0, 10000, "sum_assigned_shifts_sum")
    model.Add(sum_assigned_shifts_sum == sum(sum_assigned_shifts.values()))

    # Compute the difference term
    diff = model.NewIntVar(-10000, 10000, "difference_term")
    model.Add(diff == sum_assigned_shifts_sum - int(sum_requested_assignments))

    # Scale the difference by 1000
    scaled_diff = model.NewIntVar(-10_000_000, 10_000_000, "scaled_difference")
    model.AddMultiplicationEquality(scaled_diff, [diff, 1000])

    # Define the division term
    average_relative_shift_deviation = model.NewIntVar(-10_000_000, 10_000_000, "average_relative_shift_deviation")
    model.AddDivisionEquality(average_relative_shift_deviation, scaled_diff, int(sum_requested_assignments) * 10)

    # Create a list to represent the squared deviations from the average for each actor_plan_period.
    squared_deviations = {
        app.id: model.NewIntVar(lb=0,
                                ub=(len(entities.event_groups_with_event) * 1_000_000) ** 2,
                                name=f'squared_deviation_{app.person.f_name}')
        for app in entities.actor_plan_periods.values()
    }

    # Add a constraint for each actor_plan_period,
    # that the squared deviation is equal to (relative shift deviation - average)^2.
    dif_average__relative_shift_deviations = {}
    for app in entities.actor_plan_periods.values():
        dif_average__relative_shift_deviations[app.id] = model.NewIntVar(
            lb=0, ub=1_000_000, name=f'dif_average__relative_shift_deviation {app.id}')
        model.AddAbsEquality(dif_average__relative_shift_deviations[app.id],
                             relative_shift_deviations[app.id] - average_relative_shift_deviation)

        model.AddMultiplicationEquality(
            squared_deviations[app.id],
            [dif_average__relative_shift_deviations[app.id], dif_average__relative_shift_deviations[app.id]])

    # Add a constraint that the sum_squared_deviations is equal to the sum(squared_deviations).
    sum_squared_deviations = model.NewIntVar(lb=0, ub=1_000_000_000, name='sum_squared_deviations')
    model.AddAbsEquality(sum_squared_deviations, sum(squared_deviations.values()))

    return sum_assigned_shifts, sum_squared_deviations


def add_constraint_requested_assignments_multi_period(model: cp_model.CpModel):
    """
    Wenn mehrere Planperioden gleichzeitig berechnet werden, wird die Anzahl der Leaves der einzelnen
    Master-AvailDayGroups genommen und die Summe der zugehörigen shift_vars
    mit den requested_assignments der ActorPlanPeriods verglichen und jeweils Strafpunkte vergeben.
    Bei required_assignments wird eine hard-constraint eingefügt.
    """
    pass


def constraint_max_shift_of_app(model: cp_model.CpModel, app_id: UUID):
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


def create_constraints(model: cp_model.CpModel, creating_test_constraints: bool = False) -> tuple[dict[UUID, IntVar],
                                                         dict[UUID, IntVar], IntVar, list[IntVar],
                                                         list[IntVar], list[IntVar], list[IntVar],
                                                         dict[tuple[datetime.date, str, UUID], IntVar], list[IntVar],
                                                         list[IntVar], list[IntVar]]:
    # Add constraints for employee availability.
    add_constraints_employee_availability(model)

    # Add constraints for activity of event groups:
    add_constraints_event_groups_activity(model)

    # Add constraints for activity of avail_day groups:
    add_constraints_avail_day_groups_activity(model)

    # Add constraints for required_avail_day_groups:
    if not creating_test_constraints:
        add_constraints_required_avail_day_groups(model)

    # Add constraints for shifts in inactive avail_day_groups:
    add_constraints_num_shifts_in_avail_day_groups(model)

    # Add constraints for weights in avail_day_groups:
    constraints_weights_in_avail_day_groups = add_constraints_weights_in_avail_day_groups(model)

    # Add constraints for location prefs in avail.days:
    constraints_location_prefs = add_constraints_location_prefs(model)

    # Add constraints for partner-location prefs in avail.days:
    constraints_partner_loc_prefs = add_constraints_partner_location_prefs(model)

    # Add constraints for unsigned shifts:
    unassigned_shifts_per_event = add_constraints_unsigned_shifts(model)

    # Add constraints for weights in event_groups:
    constraints_weights_in_event_groups = add_constraints_weights_in_event_groups(model)

    # Add constraints for cast_rules:
    constraints_cast_rule = add_constraints_cast_rules(model)

    # Add constraints for skills:
    skill_conflict_vars = add_constraints_skills(model)

    # Add constraints for fixed_cast:
    constraints_fixed_cast_conflicts, constraints_prefer_fixed_cast = add_constraints_fixed_cast(model)

    # Add constraints for different casts on shifts with different locations on same day:
    add_constraints_different_casts_on_shifts_with_different_locations_on_same_day(model)

    # Add constraints for relative shift deviations:
    sum_assigned_shifts, sum_squared_deviations = add_constraints_rel_shift_deviations(model)

    return (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
            constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups, constraints_location_prefs,
            constraints_partner_loc_prefs, constraints_fixed_cast_conflicts, skill_conflict_vars, constraints_cast_rule,
            constraints_prefer_fixed_cast)


def create_constraint_max_shift_of_app(model: cp_model.CpModel, app_id: UUID) -> IntVar:
    return constraint_max_shift_of_app(model, app_id)


def define_objective_minimize(model: cp_model.CpModel, unassigned_shifts_per_event: dict[UUID, IntVar],
                              sum_squared_deviations: IntVar, constraints_weights_in_avail_day_groups: list[IntVar],
                              constraints_weights_in_event_groups: list[IntVar],
                              constraints_location_prefs: list[IntVar],
                              constraints_partner_loc_prefs: list[IntVar],
                              constraints_fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], IntVar],
                              skill_conflict_vars: list[IntVar],
                              constraints_cast_rule: list[IntVar],
                              constraints_prefer_fixed_cast: list[IntVar]) -> None:
    """Change the objective to minimize a weighted sum of the number of unassigned shifts
    and the sum of the squared deviations."""

    weights = curr_config_handler.get_solver_config().minimization_weights

    weight_unassigned_shifts = weights.unassigned_shifts
    weight_sum_squared_shift_deviations = weights.sum_squared_deviations / len(entities.actor_plan_periods)
    weight_constraints_weights_in_avail_day_groups = weights.constraints_weights_in_avail_day_groups
    weight_constraints_weights_in_event_groups = weights.constraints_weights_in_event_groups
    weight_constraints_location_prefs = weights.constraints_location_prefs
    weight_constraints_fixed_cast_conflicts = weights.constraints_fixed_casts_conflicts
    weight_constraints_partner_loc_prefs = weights.constraints_partner_loc_prefs
    weight_constraints_skills = weights.constraints_skills_match
    weight_constraints_cast_rule = weights.constraints_cast_rule
    weight_prefer_fixed_cast = weights.prefer_fixed_cast_events

    model.Minimize(weight_unassigned_shifts * sum(unassigned_shifts_per_event.values())
                   + weight_sum_squared_shift_deviations * sum_squared_deviations
                   + weight_constraints_weights_in_avail_day_groups * sum(constraints_weights_in_avail_day_groups)
                   + weight_constraints_weights_in_event_groups * sum(constraints_weights_in_event_groups)
                   + weight_constraints_location_prefs * sum(constraints_location_prefs)
                   + weight_constraints_partner_loc_prefs * sum(constraints_partner_loc_prefs)
                   + weight_constraints_fixed_cast_conflicts * sum(constraints_fixed_cast_conflicts.values())
                   + weight_constraints_skills * sum(skill_conflict_vars)
                   + weight_constraints_cast_rule * sum(constraints_cast_rule)
                   + weight_prefer_fixed_cast * sum(constraints_prefer_fixed_cast)
                   )


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
        collect_schedule_versions: bool) -> tuple[cp_model.CpSolver, PartialSolutionCallback, CpSolverStatus]:
    # Solve the model.
    global solver
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
                                               collect_schedule_versions)

    status = solver.Solve(model, solution_printer)

    return solver, solution_printer, status


def solve_model_to_optimum(model: cp_model.CpModel, max_search_time: int,
                           log_search_process: bool) -> tuple[cp_model.CpSolver, CpSolverStatus]:
    # Solve the model.
    global solver
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
        event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree, max_search_time: int,
        log_search_process: bool) -> tuple[dict[UUID, int], int, int, int,
                                           dict[tuple[datetime.date, str, UUID], int], dict[str, int], int, bool]:
    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree)
    solver_variables.cast_rules.reset_fields()
    (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
     constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
     constraints_location_prefs, constraints_partner_loc_prefs,
     constraints_fixed_cast_conflicts, skill_conflict_vars, constraints_cast_rule,
     constraints_prefer_fixed_cast) = create_constraints(model)
    define_objective_minimize(model, unassigned_shifts_per_event, sum_squared_deviations,
                              constraints_weights_in_avail_day_groups,
                              constraints_weights_in_event_groups,
                              constraints_location_prefs, constraints_partner_loc_prefs,
                              constraints_fixed_cast_conflicts,
                              skill_conflict_vars,
                              constraints_cast_rule,
                              constraints_prefer_fixed_cast)
    # print('\n\n++++++++++++++++++++++++++++++++++++++ New Solution +++++++++++++++++++++++++++++++++++++++++++++++++++')
    solver, solver_status = solve_model_to_optimum(model, max_search_time, log_search_process)

    success, problems = print_solver_status(model, solver_status)
    if not success:
        return 0, 0, 0, 0, {}, {}, 0, False
    print_statistics(solver, None, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations,
                     constraints_partner_loc_prefs, constraints_location_prefs,
                     constraints_fixed_cast_conflicts,
                     constraints_weights_in_event_groups,
                     constraints_weights_in_avail_day_groups, constraints_cast_rule)
    unassigned_shifts = sum(solver.Value(u) for u in unassigned_shifts_per_event.values())

    return ({app_id: solver.Value(a) for app_id, a in sum_assigned_shifts.items()},
            unassigned_shifts,
            solver.Value(sum(constraints_location_prefs)),
            solver.Value(sum(constraints_partner_loc_prefs)),
            {key: solver.Value(int_var) for key, int_var in constraints_fixed_cast_conflicts.items()},
            {skill_var.name: solver.Value(skill_var) for skill_var in skill_conflict_vars},
            solver.Value(sum(constraints_cast_rule)),
            success)


def extract_assignments_by_period(assigned_shifts: dict[UUID, int], plan_period_ids: list[UUID]) -> dict[UUID, int]:
    """
    Extrahiert die Anzahl der zugewiesenen Einsätze pro PlanPeriod aus dem Dictionary der ActorPlanPeriods.
    Args:
        assigned_shifts: Dictionary mit ActorPlanPeriod ID als Key und Anzahl der zugewiesenen Einsätze als Value
        plan_period_ids: Liste der PlanPeriod IDs

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
        event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree, unassigned_shifts: int,
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
        create_vars(model, event_group_tree, avail_day_group_tree)
        solver_variables.cast_rules.reset_fields()
        (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
         constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
         constraints_location_prefs, constraints_partner_loc_prefs,
         constraints_fixed_cast_conflicts, skill_conflict_vars, constraints_cast_rule,
         constraints_prefer_fixed_cast) = create_constraints(model)

        max_shifts_of_app = create_constraint_max_shift_of_app(model, app_id)

        define_objective__max_shift_of_app(
            model,
            unassigned_shifts,
            sum_location_prefs,
            sum_partner_loc_prefs,
            sum_fixed_cast_conflicts,
            sum_cast_rules,
            unassigned_shifts_per_event,
            constraints_location_prefs,
            constraints_partner_loc_prefs,
            constraints_fixed_cast_conflicts,
            skill_conflict_vars,
            max_shifts_of_app,
            constraints_prefer_fixed_cast
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
) -> tuple[EventGroupTree, AvailDayGroupTree, dict[UUID, float]]:
    """
    Berechnet faire Verteilung über alle PlanPeriods und schreibt in entities.
    
    Diese Funktion erstellt Combined Trees und Data Models, um die entities.actor_plan_periods
    korrekt mit allen ActorPlanPeriods zu füllen. Dann wird die faire Multi-Period Verteilung
    basierend auf den bereits berechneten max_shifts berechnet.
    
    Args:
        plan_period_ids: Liste aller PlanPeriod IDs
        max_shifts_per_app: Bereits berechnete maximale Shifts pro ActorPlanPeriod
        assigned_shifts_per_period: Dict mapping plan_period_id zu assigned_shifts dieser Periode
        
    Returns:
        Tuple mit (event_group_tree, avail_day_group_tree, fair_assignments)
    """
    # Combined Trees für alle Perioden erstellen
    event_group_tree = get_combined_event_group_tree(plan_period_ids)
    avail_day_group_tree = get_combined_avail_day_group_tree(plan_period_ids)
    cast_group_tree = get_combined_cast_group_tree(plan_period_ids)
    
    # Data Models mit ALLEN ActorPlanPeriods erstellen
    # Dies füllt entities.actor_plan_periods korrekt
    create_data_models_multi_period(
        event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_ids
    )
    
    # Multi-Period faire Verteilung berechnen
    fair_assignments = generate_adjusted_requested_assignments_multi_period(
        assigned_shifts_per_period,
        max_shifts_per_app
    )
    
    return event_group_tree, avail_day_group_tree, fair_assignments


def get_fair_distribution(
    max_shifts_per_app: dict[UUID, int],
    total_assigned_shifts: int
) -> dict[UUID, float]:
    """
    Berechnet faire Verteilung für Single-Period.
    
    entities.actor_plan_periods müssen bereits durch create_data_models() gefüllt sein.
    
    Args:
        max_shifts_per_app: Bereits berechnete maximale Shifts pro ActorPlanPeriod
        total_assigned_shifts: Gesamtanzahl der zuzuweisenden Shifts
        
    Returns:
        Dictionary mit fairen Shifts pro ActorPlanPeriod
    """
    fair_assignments = generate_adjusted_requested_assignments(
        total_assigned_shifts,
        max_shifts_per_app
    )
    return fair_assignments


def call_solver_with_adjusted_requested_assignments(
        event_group_tree: EventGroupTree,
        avail_day_group_tree: AvailDayGroupTree,
        max_search_time: int,
        log_search_process: bool) -> tuple[int, list[int], int, int, int, int,
                                           dict[tuple[datetime.date, str, UUID], int], int,
                                           list[schemas.AppointmentCreate], bool]:

    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree)
    solver_variables.cast_rules.reset_fields()
    (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
     constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
     constraints_location_prefs, constraints_partner_loc_prefs,
     constraints_fixed_cast_conflicts, skill_conflict_vars, constraints_cast_rule,
     constraints_prefer_fixed_cast) = create_constraints(model)
    define_objective_minimize(model, unassigned_shifts_per_event, sum_squared_deviations,
                              constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
                              constraints_location_prefs, constraints_partner_loc_prefs,
                              constraints_fixed_cast_conflicts, skill_conflict_vars, constraints_cast_rule,
                              constraints_prefer_fixed_cast)
    solver, solver_status = solve_model_to_optimum(model, max_search_time, log_search_process)
    # print('\n\n++++++++++++++++++++++++++++++++++++++ New Solution +++++++++++++++++++++++++++++++++++++++++++++++++++')
    success, problems = print_solver_status(model, solver_status)
    if not success:
        return 0, [], 0, 0, 0, 0, {}, 0, [], False
    print_statistics(solver, None, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations,
                     constraints_partner_loc_prefs, constraints_location_prefs,
                     constraints_fixed_cast_conflicts,
                     constraints_weights_in_event_groups,
                     constraints_weights_in_avail_day_groups, constraints_cast_rule)

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

    return (solver.Value(sum_squared_deviations), [solver.Value(u) for u in unassigned_shifts_per_event.values()],
            sum(solver.Value(w) for w in constraints_weights_in_avail_day_groups),
            sum(solver.Value(v) for v in constraints_weights_in_event_groups),
            sum(solver.Value(lp) for lp in constraints_location_prefs),
            solver.Value(sum(constraints_partner_loc_prefs)),
            {key: solver.Value(int_var) for key, int_var in constraints_fixed_cast_conflicts.items()},
            solver.Value(sum(constraints_cast_rule)), appointments, success)


def call_solver_with__fixed_constraint_results(
        event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree, cast_group_tree: CastGroupTree,
        unassigned_shifts_per_event_res: list[int], sum_squared_deviations_res: int,
        weights_shifts_in_avail_day_groups_res: int, weights_in_event_groups_res: int, sum_location_prefs_res: int,
        sum_partner_loc_prefs_res: int, sum_fixed_cast_conflicts_res: int, sum_cast_rules: int,
        print_solution_printer_results: bool, log_search_process: bool, collect_schedule_versions: bool
) -> tuple[PartialSolutionCallback | None, dict[tuple[datetime.date, str, UUID], int], bool]:
    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree)
    solver_variables.cast_rules.reset_fields()
    (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
     constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
     constraints_location_prefs, constraints_partner_loc_prefs,
     constraints_fixed_cast_conflicts, skill_conflict_vars, constraints_cast_rule,
     constraints_prefer_fixed_cast) = create_constraints(model)
    define_objective__fixed_constraint_results(
        model, list(unassigned_shifts_per_event.values()), sum_squared_deviations,
        constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
        constraints_location_prefs, constraints_partner_loc_prefs,
        constraints_fixed_cast_conflicts, constraints_cast_rule,
        constraints_prefer_fixed_cast, unassigned_shifts_per_event_res,
        sum_squared_deviations_res, weights_shifts_in_avail_day_groups_res,
        weights_in_event_groups_res, sum_location_prefs_res,
        sum_partner_loc_prefs_res, sum_fixed_cast_conflicts_res, sum_cast_rules, 0)
    # print('\n\n++++++++++++++++++++++++++++++++++++++ New Solution +++++++++++++++++++++++++++++++++++++++++++++++++++')
    solver, solution_printer, solver_status = solve_model_with_solver_solution_callback(
        model, list(unassigned_shifts_per_event.values()), sum_assigned_shifts,
        sum_squared_deviations, constraints_fixed_cast_conflicts,
        print_solution_printer_results, 100, log_search_process, collect_schedule_versions)
    success, problems = print_solver_status(model, solver_status)
    if not success:
        return None, {}, False
    print_statistics(solver, solution_printer, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations,
                     constraints_partner_loc_prefs, constraints_location_prefs,
                     constraints_fixed_cast_conflicts,
                     constraints_weights_in_event_groups,
                     constraints_weights_in_avail_day_groups, constraints_cast_rule)

    constraints_fixed_cast_conflicts = {key: solver.Value(val) for key, val in constraints_fixed_cast_conflicts.items()}
    return solution_printer, constraints_fixed_cast_conflicts, success


def set_test_plan_constraints(model: cp_model.CpModel, plan: schemas.PlanShow,
                              constraints_fixed_cast_conflicts:  dict[tuple[datetime.date, str, UUID], IntVar],
                              skill_conflict_vars: list[IntVar]):
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
                             max_search_time: int, log_search_process: bool) -> tuple[bool, list[str]]:
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree)
    (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
     constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
     constraints_location_prefs, constraints_partner_loc_prefs,
     constraints_fixed_cast_conflicts, skill_conflict_vars, constraints_cast_rule) = create_constraints(model, True)
    set_test_plan_constraints(model, plan,
                              constraints_fixed_cast_conflicts, skill_conflict_vars)
    solver, solver_status = solve_model_to_optimum(model, max_search_time, log_search_process)

    success, problems = print_solver_status(model, solver_status)
    return success, problems


def _get_max_fair_shifts_and_max_shifts_to_assign(
        plan_period_id: UUID, time_calc_max_shifts: int, time_calc_fair_distribution: int,
        log_search_process=False) -> tuple[EventGroupTree, AvailDayGroupTree, dict[tuple[date, str, UUID], int],
                                           dict[str, int], dict[UUID, int], dict[UUID, float]] | None:
    signal_handling.handler_solver.progress('Vorberechnungen...')
    global entities
    entities = Entities()

    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)

    (assigned_shifts, unassigned_shifts, sum_location_prefs, sum_partner_loc_prefs, fixed_cast_conflicts,
     skill_conflicts, sum_cast_rules, success) = call_solver_with_unadjusted_requested_assignments(
        event_group_tree,
        avail_day_group_tree,
        time_calc_max_shifts,
        log_search_process)

    if sum(fixed_cast_conflicts.values()) or sum(skill_conflicts.values()):
        return event_group_tree, avail_day_group_tree, fixed_cast_conflicts, skill_conflicts, {}, {}
    if not success:
        return

    get_max_shifts_per_app = call_solver_to_get_max_shifts_per_app(event_group_tree,
                                                                   avail_day_group_tree,
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
        sum(assigned_shifts.values())
    )

    time.sleep(0.1)  # notwendig, damit Signal-Handling Zeit für das Senden des neuen Signals hat.

    return ((event_group_tree, avail_day_group_tree, fixed_cast_conflicts, skill_conflicts,
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
        # Neue entities für jede Periode (wichtig: jede Periode hat eigene Daten!)
        global entities
        entities = Entities()
        
        # Single-Period Trees für diese Periode
        event_group_tree_period = get_event_group_tree(plan_period_id)
        avail_day_group_tree_period = get_avail_day_group_tree(plan_period_id)
        cast_group_tree_period = get_cast_group_tree(plan_period_id)
        
        # Data Models für diese Periode
        create_data_models(
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

    (event_group_tree, avail_day_group_tree,
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
        global entities
        entities = Entities()
        
        create_data_models(
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
    _, _, fixed_cast_conflicts, skill_conflicts, max_shifts_per_app, fair_shifts_per_app = result_shifts

    return max_shifts_per_app, fair_shifts_per_app


def test_plan(plan_id: UUID) -> tuple[bool, list[str]]:
    # todo: Möglichkeit hinzufügen, um die Besetzung von Gästen auf CastRules zu überprüfen.
    #  Statistiken von möglichen und gerechten Einsätzen zurückgeben.
    plan = db_services.Plan.get(plan_id)
    global entities
    entities = Entities()
    event_group_tree = get_event_group_tree(plan.plan_period.id)
    avail_day_group_tree = get_avail_day_group_tree(plan.plan_period.id)
    cast_group_tree = get_cast_group_tree(plan.plan_period.id)
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan.plan_period.id)
    success, problems = call_solver_to_test_plan(plan, event_group_tree, avail_day_group_tree, 20, False)
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
