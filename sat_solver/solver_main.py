import collections
import dataclasses
import itertools
import pprint
import sys
from collections import defaultdict
import datetime
from uuid import UUID

import anytree
from ortools.sat.cp_model_pb2 import CpSolverStatus
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

from database import db_services, schemas
from configuration.solver import curr_config_handler
from sat_solver.avail_day_group_tree import AvailDayGroup, get_avail_day_group_tree, AvailDayGroupTree
from sat_solver.cast_group_tree import get_cast_group_tree, CastGroupTree, CastGroup
from sat_solver.event_group_tree import get_event_group_tree, EventGroupTree, EventGroup


def generate_adjusted_requested_assignments(assigned_shifts: int, possible_assignments: dict[UUID, int]):
    # fixme: unkorrekt mit avail_day_group Einschränkungen
    requested_assignments_adjusted: dict[UUID, int] = {
        app_id: min(entities.actor_plan_periods[app_id].requested_assignments, assignments)
        for app_id, assignments in possible_assignments.items()
    }

    requested_assignments_new: dict[UUID, float] = {}
    avail_assignments: int = assigned_shifts
    while True:
        mean_nr_assignments: float = avail_assignments / len(requested_assignments_adjusted)
        requested_greater_than_mean: dict[UUID, int] = {}
        requested_smaller_than_mean: dict[UUID, int] = {}
        for app_id, requested in requested_assignments_adjusted.items():
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
            requested_assignments_adjusted = requested_greater_than_mean.copy()
            if not requested_assignments_adjusted:
                break
    for app in entities.actor_plan_periods.values():
        app.requested_assignments = requested_assignments_new[app.id]


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

        self._schedule_versions: list[list[schemas.AppointmentCreate]] = []

    def on_solution_callback(self):
        self._solution_count += 1
        if self._print_results:
            self.print_results()
        if self._collect_schedule_versions:
            self.collect_schedule_versions()

        for app_id, s in self._sum_assigned_shifts.items():
            self._max_assigned_shifts[app_id] = max(self._max_assigned_shifts[app_id], self.Value(s))

        if self._solution_limit and self._solution_count >= self._solution_limit:
            print(f"Stop search after {self._solution_count} solutions")
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


entities: Entities | None = None


def create_vars(model: cp_model.CpModel, event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree,
                cast_group_tree: CastGroupTree):

    entities.event_groups = {
        event_group.event_group_id: event_group for event_group in event_group_tree.root.descendants
        if event_group.children or event_group.event
    }
    entities.event_groups = {event_group_tree.root.event_group_id: event_group_tree.root} | entities.event_groups
    entities.event_group_vars = {
        event_group.event_group_id: model.NewBoolVar(f'') for event_group in event_group_tree.root.descendants
        if event_group.children or event_group.event
    }

    entities.event_groups_with_event = {leave.event_group_id: leave for leave in event_group_tree.root.leaves
                                        if leave.event}

    entities.avail_day_groups = {
        avail_day_group.avail_day_group_id: avail_day_group for avail_day_group in avail_day_group_tree.root.descendants
        if avail_day_group.children or avail_day_group.avail_day
    }
    entities.avail_day_groups = ({avail_day_group_tree.root.avail_day_group_id: avail_day_group_tree.root}
                                 | entities.avail_day_groups)
    entities.avail_day_group_vars = {
        avail_day_group.avail_day_group_id: model.NewBoolVar(f'')
        for avail_day_group in avail_day_group_tree.root.descendants
        if avail_day_group.children or avail_day_group.avail_day
    }
    entities.avail_day_groups_with_avail_day = {
        leave.avail_day_group_id: leave for leave in avail_day_group_tree.root.leaves if leave.avail_day
    }

    entities.cast_groups = {cast_group_tree.root.cast_group_id: cast_group_tree.root} | {
        cast_group.cast_group_id: cast_group
        for cast_group in cast_group_tree.root.descendants
    }
    entities.cast_groups_with_event = {cast_group.cast_group_id: cast_group
                                       for cast_group in cast_group_tree.root.leaves if cast_group.event}

    for adg_id, adg in entities.avail_day_groups_with_avail_day.items():
        for event_group_id, event_group in entities.event_groups_with_event.items():
            location_of_work = event_group.event.location_plan_period.location_of_work
            #######################################################################################################
            # todo: später implementieren, um die shift_vars zu minimieren und die Effektivität zu verbessern
            # # shift_vars werden nicht gesetzt, wenn das zur location_of_work zugehörige actor_location_pref
            # # des avail_day einen Score von 0 besitzt:
            # if found_alf := next((alf for alf in adg.avail_day.actor_location_prefs_defaults
            #                      if alf.location_of_work.id == location_of_work.id), None):
            #     if found_alf.score == 0:
            #         continue
            # # shift_vars werden nicht gesetzt, wenn Zeitfenster und Datum nicht zu denen des avail_day passen:
            # if not (adg.avail_day.date == event_group.event.date
            #         and adg.avail_day.time_of_day.start <= event_group.event.time_of_day.start
            #         and adg.avail_day.time_of_day.end >= event_group.event.time_of_day.end):
            #     continue
            #########################################################################################################
            entities.shift_vars[(adg_id, event_group_id)] = model.NewBoolVar(f'shift ({adg_id}, {event_group_id})')
    print(f'{len(entities.shift_vars)=}')


def add_constraints_employee_availability(model: cp_model.CpModel):
    # for adg in entities.avail_day_groups_with_avail_day.values():
    #     for event_group in entities.event_groups_with_event.values():
    #         if (event_group.event.date != adg.avail_day.date
    #                 or (event_group.event.time_of_day.start < adg.avail_day.time_of_day.start)
    #                 or (event_group.event.time_of_day.end > adg.avail_day.time_of_day.end)):
    #             model.Add(entities.shift_vars[(adg.avail_day_group_id, event_group.event_group_id)] == 0)

    # todo: shift_vars können schon bei der Variablenerstellung ausgeschlossen werden, falls die unten angegebene
    #  Bedingung nicht erfüllt ist.
    for (adg_id, eg_id), var in entities.shift_vars.items():
        avail_day_group = entities.avail_day_groups[adg_id]
        event_group = entities.event_groups[eg_id]
        if (event_group.event.date != avail_day_group.avail_day.date
                or (event_group.event.time_of_day.start < avail_day_group.avail_day.time_of_day.start)
                or (event_group.event.time_of_day.end > avail_day_group.avail_day.time_of_day.end)):
            model.Add(var == 0)


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
    Bei tiefer geschachtelten Event-Groups kann werden die Parent-Groups bevorzugt deren ausgewählte Children
    ein insgesamt höheres weight haben, wenn die Parent-Groups gleiches weight haben.
    todo: Überlegenswert ist eine alternative Implementierung wie bei 'add_constraints_weights_in_avail_day_groups'.
    """

    multiplier_level = (curr_config_handler.get_solver_config()
                        .constraints_multipliers.sliders_levels_weights_event_groups)

    def calculate_weight_vars_of_children_recursive(event_group: EventGroup, depth: int) -> list[IntVar]:
        weight_vars: list[IntVar] = []
        if event_group.nr_of_active_children is not None:
            if (children := event_group.children) and (event_group.nr_of_active_children < len(event_group.children)):
                children: list[EventGroup]
                for c in children:
                    # Das angepasste weight der Child-Event-Group wird berechnet:
                    adjusted_weight = 1 - c.weight

                    event_group_var = entities.event_group_vars[c.event_group_id]
                    weight_vars.append(
                        model.NewIntVar(-1000, 1000,
                                        f'Depth {depth}, no Event' if c.event is None
                                        else f'Depth {depth}, Event: {c.event.date:%d.%m.%y}, '
                                             f'{c.event.time_of_day.name}, '
                                             f'{c.event.location_plan_period.location_of_work.name}')
                    )
                    model.Add(weight_vars[-1] == (event_group_var * adjusted_weight * multiplier_level[depth]))
        for c in event_group.children:
            weight_vars.extend(calculate_weight_vars_of_children_recursive(c, depth + 1))

        return weight_vars

    root_event_group = next(eg for eg in entities.event_groups.values() if not eg.parent)

    return calculate_weight_vars_of_children_recursive(
        root_event_group, 1 if root_event_group.root_is_location_plan_period_master_group else 0)


def add_constraints_avail_day_groups_activity(model: cp_model):
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
        Die multiplier_level können benutzt werden, um den weights der Groups je nach Tiefe eine zusätzliche
        Verstärkung zu geben. Um Verfälschungen durch Level-Verstärkungen zu vermeiden, wenn die Zweige des Gruppenbaums
        unterschiedliche Tiefen haben, werden die Constraints stets so berechnet, als befänden sich die
        Avail-Day-Groups mit Avail-Days auf der untersten Stufe.
        Falls nr_of_active_children < len(children), wird ebenso die kumulierte Gewichtung der Avail-Day-Group mit
        Avail-Day gesetzt, falls der dazugehörige Event stattfindet.
    """

    multiplier_constraints = (curr_config_handler.get_solver_config()
                              .constraints_multipliers.sliders_weights_avail_day_groups)
    multiplier_level = (curr_config_handler.get_solver_config()
                        .constraints_multipliers.sliders_levels_weights_av_day_groups)

    def calculate_weight_vars_of_children_recursive(group: AvailDayGroup,
                                                    cumulative_adjusted_weight: int = 0) -> list[IntVar]:
        weight_vars: list[IntVar] = []
        for c in group.children:
            if c.avail_day:
                adjusted_weight = multiplier_constraints[c.weight] * multiplier_level[group.depth]
                weight_vars.append(
                    model.NewIntVar(-1000000, 100000000,
                                    f'Depth {group.depth}, AvailDay: {c.avail_day.date:%d.%m.%y}, '
                                    f'{c.avail_day.time_of_day.name}, '
                                    f'{c.avail_day.actor_plan_period.person.f_name}')
                )
                # stelle fest, ob der zugehörige Event stattfindet:
                shift_with_this_avd = model.NewBoolVar('')
                model.Add(shift_with_this_avd == sum(var for (avg_id, _), var in entities.shift_vars.items()
                                                     if avg_id == c.avail_day_group_id))
                model.Add(weight_vars[-1] == ((cumulative_adjusted_weight + adjusted_weight) * shift_with_this_avd))
            else:
                adjusted_weight = multiplier_constraints[c.weight] * multiplier_level[max_depth - 1]
                weight_vars.extend(
                    calculate_weight_vars_of_children_recursive(c,
                                                                cumulative_adjusted_weight + adjusted_weight))
        return weight_vars

    root_group = next(eg for eg in entities.avail_day_groups.values() if not eg.parent)
    max_depth = (max(node.depth for node in entities.avail_day_groups.values())
                 - (1 if root_group.group_is_actor_plan_period_master_group else 0))

    if root_group.group_is_actor_plan_period_master_group:
        all_weight_vars = calculate_weight_vars_of_children_recursive(root_group)
    else:
        all_weight_vars = sum((calculate_weight_vars_of_children_recursive(app_master_group)
                               for app_master_group in root_group.children), [])

    return all_weight_vars


def add_constraints_location_prefs(model: cp_model.CpModel) -> list[IntVar]:
    # todo: Schleifen können vermutlich vereinfacht werden, indem zuerst über entities.shift_vars iteriert wird.
    loc_pref_vars = []
    for avail_day_group_id, avail_day_group in entities.avail_day_groups_with_avail_day.items():
        avail_day = avail_day_group.avail_day
        for loc_pref in [alp for alp in avail_day_group.avail_day.actor_location_prefs_defaults if not alp.prep_delete]:
            for (adg_id, eg_id), shift_var in entities.shift_vars.items():
                event = entities.event_groups[eg_id].event
                event_time_of_day_index = event.time_of_day.time_of_day_enum.time_index
                event_location_id = event.location_plan_period.location_of_work.id
                if (adg_id == avail_day_group_id and event.date == avail_day.date
                        and event_time_of_day_index == avail_day.time_of_day.time_of_day_enum.time_index
                        and event_location_id == loc_pref.location_of_work.id):
                    loc_pref_vars.append(
                        model.NewIntVar(
                            curr_config_handler.get_solver_config().constraints_multipliers.sliders_location_prefs[2],
                            curr_config_handler.get_solver_config().constraints_multipliers.sliders_location_prefs[0],
                            f'{event.date:%d.%m.%Y} ({event.time_of_day.name}), '
                            f'{event.location_plan_period.location_of_work.name}: '
                            f'{avail_day.actor_plan_period.person.f_name}'))
                    # Intermediate variable that allows the calculation of the Location-Pref variable based on the
                    # Shift variable and Event-Group variable:
                    all_active_var = model.NewBoolVar('')

                    model.AddMultiplicationEquality(
                        all_active_var, [shift_var, entities.event_group_vars[eg_id]])
                    model.Add(loc_pref_vars[-1] == all_active_var * curr_config_handler.get_solver_config()
                              .constraints_multipliers.sliders_location_prefs[loc_pref.score])

    return loc_pref_vars


def add_constraints_partner_location_prefs(model: cp_model.CpModel) -> list[IntVar]:
    plp_constr_multipliers = curr_config_handler.get_solver_config().constraints_multipliers.sliders_partner_loc_prefs

    partner_loc_pref_vars: list[IntVar] = []

    for eg_id, event_group in entities.event_groups_with_event.items():
        if event_group.event.cast_group.nr_actors < 2:
            continue
        # Get all AvailDayGroups with the same date and time of day
        avail_day_groups = (adg for adg in entities.avail_day_groups_with_avail_day.values()
                            if adg.avail_day.date == event_group.event.date
                            and adg.avail_day.time_of_day.time_of_day_enum.time_index
                            == event_group.event.time_of_day.time_of_day_enum.time_index)
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

            # todo: plp_weight_var wird hier mit der anvisierten Besetzungsstärke ermittelt,
            #  sollte aber mit der tatsächlichen Besetzungsstärke ermittelt werden...
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


def add_constraints_cast_rules(model: cp_model.CpModel):
    # todo: Anpassen für den Fall, dass nr_actors in Event Group < als len(children). Könnte man lösen, indem der Index
    #       der 1. aktiven Gruppe in einer Variablen abgelegt wird und die Besetzung dieser Gruppe als Referenz genommen
    #       wird.
    # done: Bei same_cast funktioniert es nur, wenn nr_actors bei allen gleich sind.
    # todo: Bisher nur Cast Groups auf Level 1 berücksichtigt
    # todo: strict_cast_pref kann noch implementiert werden.
    def different_cast(event_group_1_id: UUID, event_group_2_id: UUID):
        for app_id in entities.actor_plan_periods:
            shift_vars = {(adg_id, eg_id): var for (adg_id, eg_id), var in entities.shift_vars.items()
                          if eg_id in {event_group_1_id, event_group_2_id}
                          and entities.avail_day_groups[adg_id].avail_day.actor_plan_period.id == app_id}
            (model.Add(sum(shift_vars.values()) <= 1)
             .OnlyEnforceIf(entities.event_group_vars[event_group_1_id])
             .OnlyEnforceIf(entities.event_group_vars[event_group_2_id]))

    def same_cast(cast_group_1: CastGroup, cast_group_2: CastGroup):
        """Alle Actors des Events mit der kleineren Besetzung müssen auch im Event mit der größeren Besetzung
        vorkommen. Die überschüssige Position des Events mit der größeren Besetzung kann beliebig besetzt sein."""
        event_group_1_id = cast_group_1.event.event_group.id
        event_group_2_id = cast_group_2.event.event_group.id
        applied_shifts_1: list[IntVar] = [model.NewIntVar(0, 2, '')
                                          for _ in entities.actor_plan_periods]
        applied_shifts_2: list[IntVar] = [model.NewIntVar(0, 2, '')
                                          for _ in entities.actor_plan_periods]
        for i, app_id in enumerate(entities.actor_plan_periods):
            shift_vars_1 = {(adg_id, eg_id): var for (adg_id, eg_id), var in entities.shift_vars.items()
                            if eg_id == event_group_1_id
                            and entities.avail_day_groups[adg_id].avail_day.actor_plan_period.id == app_id}
            shift_vars_2 = {(adg_id, eg_id): var for (adg_id, eg_id), var in entities.shift_vars.items()
                            if eg_id == event_group_2_id
                            and entities.avail_day_groups[adg_id].avail_day.actor_plan_period.id == app_id}
            model.Add(applied_shifts_1[i] == sum(shift_vars_1.values()))
            model.Add(applied_shifts_2[i] == sum(shift_vars_2.values()))

        # works probably also with different nr_actors
        ################################################################################################################

        # equal Nones, equal Trues, equal Nones and Trues, unequal Nones and Trues:
        is_equal_1, is_equal_2, is_equal, is_unequal = [], [], [], []

        for i in range(len(entities.actor_plan_periods)):
            is_equal_1.append(model.NewBoolVar(''))
            is_equal_2.append(model.NewBoolVar(''))
            is_equal.append(model.NewBoolVar(''))
            is_unequal.append(model.NewBoolVar(''))

            model.AddMultiplicationEquality(is_equal_1[-1], [applied_shifts_1[i] - 1, applied_shifts_2[i] - 1])
            model.AddMultiplicationEquality(is_equal_2[-1], [applied_shifts_1[i], applied_shifts_2[i]])
            model.Add(is_equal[-1] == is_equal_1[-1] + is_equal_2[-1])
            model.AddAbsEquality(is_unequal[-1], is_equal[-1].Not())

        (model.Add(sum(is_unequal) == abs(cast_group_1.nr_actors - cast_group_2.nr_actors))
         .OnlyEnforceIf(entities.event_group_vars[event_group_1_id])
         .OnlyEnforceIf(entities.event_group_vars[event_group_2_id]))

        ################################################################################################################

        # works only with same nr_actors
        ################################################################################################################
        # for var_1, var_2 in zip(applied_shifts_1, applied_shifts_2):
        #     (model.Add(var_1 == var_2)
        #      .OnlyEnforceIf(entities.event_group_vars[event_group_1_id])
        #      .OnlyEnforceIf(entities.event_group_vars[event_group_2_id]))
        ################################################################################################################

    cast_groups_level_1 = collections.defaultdict(list)
    for cast_group in entities.cast_groups_with_event.values():
        cast_groups_level_1[cast_group.parent.cast_group_id].append(cast_group)

    for cast_groups in cast_groups_level_1.values():
        cast_groups.sort(key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index))

    for cg_id, cast_groups in cast_groups_level_1.items():
        cast_groups: list[CastGroup]
        parent = entities.cast_groups[cg_id]
        if not (rule := parent.cast_rule):
            continue

        for idx in range(len(cast_groups) - 1):
            event_group_1 = cast_groups[idx].event.event_group
            event_group_2 = cast_groups[idx + 1].event.event_group
            if rule[idx % len(rule)] == '-':
                different_cast(event_group_1.id, event_group_2.id)
            elif rule[idx % len(rule)] == '~':
                same_cast(cast_groups[idx], cast_groups[idx + 1])
            elif rule[idx % len(rule)] == '*':
                continue
            else:
                raise ValueError(f'unknown rule symbol: {rule}')


def add_constraints_fixed_cast(model: cp_model.CpModel) -> dict[tuple[datetime.date, str, UUID], IntVar]:
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

    def proof_recursive(fixed_cast_list: tuple | UUID, cast_group: CastGroup) -> IntVar:
        if isinstance(fixed_cast_list, UUID):
            return check_pers_id_in_shift_vars(fixed_cast_list, cast_group)
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

    fixed_cast_vars = {(datetime.date(1999, 1, 1), 'dummy', UUID('00000000-0000-0000-0000-000000000000')): model.NewBoolVar('')}
    for cast_group in entities.cast_groups_with_event.values():
        if not cast_group.fixed_cast:
            continue

        fixed_cast_vars[key := (cast_group.event.date, cast_group.event.time_of_day.name, cast_group.event.id)] = model.NewBoolVar('')

        # String wird zu Python-Objekt umgewandelt:
        fixed_cast_as_list = eval(cast_group.fixed_cast
                                  .replace('and', ',"and",')
                                  .replace('or', ',"or",')
                                  .replace('in team', ''))

        (model.Add(fixed_cast_vars[key] == proof_recursive(fixed_cast_as_list, cast_group).Not())
         .OnlyEnforceIf(entities.event_group_vars[cast_group.event.event_group.id]))

    return fixed_cast_vars


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


def add_constraints_different_casts_on_shifts_with_different_locations_on_same_day(model: cp_model.CpModel) -> dict[UUID, IntVar]:
    """Besetzungen von Events an unterschiedlichen Locations welche am gleichen stattfinden müssen unterschiedlich sein.
       Ausnahme, wenn CombinationLocationsPossible für die jeweiligen Events festgelegt wurden.
       todo: Implementieren
    """


def add_constraints_rel_shift_deviations(model: cp_model.CpModel) -> tuple[dict[UUID, IntVar], IntVar]:
    # Create a lists to represent the sums of assigned shifts and the relative shift deviations for each actor_plan_period.
    sum_assigned_shifts = {
        app.id: model.NewIntVar(lb=0, ub=1000, name=f'sum_assigned_shifts {app.person.f_name}')
        for app in entities.actor_plan_periods.values()
    }
    relative_shift_deviations = {
        app.id: model.NewIntVar(
            lb=-len(entities.event_groups_with_event) * 100_000_000,
            ub=len(entities.event_groups_with_event) * 100_000_000,
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
        model.AddDivisionEquality(
            relative_shift_deviations[app.id],
            sum_assigned_shifts[app.id] * 100_000 - int(app.requested_assignments * 100_000),
            int(app.requested_assignments * 100) if app.requested_assignments else 1)

    # Calculate the average of the relative shift deviations.
    average_relative_shift_deviation = model.NewIntVar(lb=-100_000_000, ub=100_000_000,
                                                       name='average_relative_shift_deviation')
    sum_relative_shift_deviations = model.NewIntVar(lb=-len(entities.event_groups_with_event) * 100_000_000,
                                                    ub=len(entities.event_groups_with_event) * 100_000_000,
                                                    name='sum_relative_shift_deviations')
    model.AddAbsEquality(sum_relative_shift_deviations, sum(relative_shift_deviations.values()))
    model.AddDivisionEquality(average_relative_shift_deviation,
                              sum_relative_shift_deviations,
                              len(entities.actor_plan_periods))

    # Create a list to represent the squared deviations from the average for each actor_plan_period.
    squared_deviations = {
        app.id: model.NewIntVar(lb=0,
                                ub=(len(entities.event_groups_with_event) * 10_000_000) ** 2,
                                name=f'squared_deviation_{app.person.f_name}')
        for app in entities.actor_plan_periods.values()
    }

    # Add a constraint for each actor_plan_period,
    # that the squared deviation is equal to (relative shift deviation - average)^2.
    dif_average__relative_shift_deviations = {}
    for app in entities.actor_plan_periods.values():
        dif_average__relative_shift_deviations[app.id] = model.NewIntVar(
            lb=-100_000_000, ub=100_000_000, name=f'dif_average__relative_shift_deviation {app.id}')
        model.AddAbsEquality(dif_average__relative_shift_deviations[app.id],
                             relative_shift_deviations[app.id] - average_relative_shift_deviation)

        model.AddMultiplicationEquality(
            squared_deviations[app.id],
            [dif_average__relative_shift_deviations[app.id], dif_average__relative_shift_deviations[app.id]])

    # Add a constraint that the sum_squared_deviations is equal to the sum(squared_deviations).
    sum_squared_deviations = model.NewIntVar(lb=0, ub=10 ** 16, name='sum_squared_deviations')
    model.AddAbsEquality(sum_squared_deviations, sum(squared_deviations.values()))

    return sum_assigned_shifts, sum_squared_deviations


def create_constraints(model: cp_model.CpModel) -> tuple[dict[UUID, IntVar], dict[UUID, IntVar], IntVar, list[IntVar],
                                                         list[IntVar], list[IntVar], list[IntVar],
                                                         dict[tuple[datetime.date, str, UUID], IntVar]]:
    # Add constraints for employee availability.
    add_constraints_employee_availability(model)

    # Add constraints for activity of event groups:
    add_constraints_event_groups_activity(model)

    # Add constraints for activity of avail_day groups:
    add_constraints_avail_day_groups_activity(model)

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
    add_constraints_cast_rules(model)

    # Add constraints for fixed_cast:
    constraints_fixed_cast_conflicts = add_constraints_fixed_cast(model)

    # Add constraints for relative shift deviations:
    sum_assigned_shifts, sum_squared_deviations = add_constraints_rel_shift_deviations(model)

    return (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
            constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups, constraints_location_prefs,
            constraints_partner_loc_prefs, constraints_fixed_cast_conflicts)


def define_objective_minimize(model: cp_model.CpModel, unassigned_shifts_per_event: dict[UUID, IntVar],
                              sum_squared_deviations: IntVar, constraints_weights_in_avail_day_groups: list[IntVar],
                              constraints_weights_in_event_groups: list[IntVar],
                              constraints_location_prefs: list[IntVar],
                              constraints_partner_loc_prefs: list[IntVar],
                              constraints_fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], IntVar]):
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

    model.Minimize(weight_unassigned_shifts * sum(unassigned_shifts_per_event.values())
                   + weight_sum_squared_shift_deviations * sum_squared_deviations
                   + weight_constraints_weights_in_avail_day_groups * sum(constraints_weights_in_avail_day_groups)
                   + weight_constraints_weights_in_event_groups * sum(constraints_weights_in_event_groups)
                   + weight_constraints_location_prefs * sum(constraints_location_prefs)
                   + weight_constraints_partner_loc_prefs * sum(constraints_partner_loc_prefs)
                   + weight_constraints_fixed_cast_conflicts * sum(constraints_fixed_cast_conflicts.values()))


def define_objective__fixed_unassigned(model: cp_model.CpModel,
                                       unassigned_shifts: int, sum_location_prefs: int, sum_partner_loc_prefs: int,
                                       sum_fixed_cast_conflicts: int, unassigned_shifts_per_event: dict[UUID, IntVar],
                                       constraints_location_prefs: list[IntVar],
                                       constraints_partner_loc_prefs: list[IntVar],
                                       constraints_fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], IntVar]):
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
        unassigned_shifts_per_event_res: list[int],
        sum_squared_deviations_res: int, weights_shifts_in_avail_day_groups_res: int, weights_in_event_groups_res: int,
        sum_location_prefs_res: int, sum_partner_loc_prefs_res: int, sum_fixed_cast_conflicts_res: int):
    model.Add(sum(unassigned_shifts_per_event) == sum(unassigned_shifts_per_event_res))
    model.Add(sum_squared_deviations == sum_squared_deviations_res)
    model.Add(sum(constraints_weights_in_avail_day_groups) == weights_shifts_in_avail_day_groups_res)
    model.Add(sum(constraints_weights_in_event_groups) == weights_in_event_groups_res)
    model.Add(sum(constraints_location_prefs) == sum_location_prefs_res)
    model.Add(sum(constraints_partner_loc_prefs) == sum_partner_loc_prefs_res)
    model.Add(sum(constraints_fixed_cast_conflicts.values()) == sum_fixed_cast_conflicts_res)


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


def solve_model_to_optimum(model: cp_model.CpModel,
                           log_search_process: bool) -> tuple[cp_model.CpSolver, CpSolverStatus]:
    # Solve the model.
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = log_search_process
    solver.parameters.linearization_level = 0
    solver.parameters.enumerate_all_solutions = False

    status = solver.Solve(model)

    return solver, status


def print_statistics(solver: cp_model.CpSolver, solution_printer: PartialSolutionCallback | None,
                     unassigned_shifts_per_event: dict[UUID, IntVar], sum_assigned_shifts: dict[UUID, IntVar],
                     sum_squared_deviations: IntVar, constraints_partner_loc_prefs: list[IntVar],
                     constraints_location_prefs: list[IntVar],
                     constraints_fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], IntVar],
                     constraints_weights_in_event_groups: list[IntVar],
                     constraints_weights_in_av_day_groups: list[IntVar]):
    # Statistics.
    print("\nStatistics")
    print(f"  - conflicts      : {solver.NumConflicts()}")
    print(f"  - branches       : {solver.NumBranches()}")
    print(f"  - wall time      : {solver.WallTime()} s")
    print(f'  - ObjectiveValue : {solver.ObjectiveValue()}')
    if solution_printer:
        print(f"  - solutions found: {solution_printer.solution_count()}")
    print(f'{unassigned_shifts_per_event=}')
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
    print(f'fixed_cast_conflicts: {fixed_cast_conflicts}')

    print(f'weights_in_event_groups: '
          f'{" | ".join([f"""{v.name}: {solver.Value(v)}""" for v in constraints_weights_in_event_groups])}')
    print(f'sum_weights_in_event_groups: {sum(solver.Value(w) for w in constraints_weights_in_event_groups)}')
    print(f'weights_in_av_day_groups: '
          f'{" | ".join([f"""{v.name}: {solver.Value(v)}""" for v in constraints_weights_in_av_day_groups])}')
    print(f'sum_weights_in_av_day_groups: {sum(solver.Value(w) for w in constraints_weights_in_av_day_groups)}')


def print_solver_status(status: CpSolverStatus):
    if status == cp_model.MODEL_INVALID:
        print('########################### INVALID MODEL ######################################')
        sys.exit()
    elif status == cp_model.OPTIMAL:
        print('########################### OPTIMAL ############################################')
    elif status == cp_model.FEASIBLE:
        print('########################### FEASIBLE ############################################')
    else:
        print('########################### FAILED ############################################')


def call_solver_with_unadjusted_requested_assignments(
        event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree,
        cast_group_tree: CastGroupTree, log_search_process: bool) -> tuple[int, int, int, int, int]:
    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree, cast_group_tree)
    (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
     constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
     constraints_location_prefs, constraints_partner_loc_prefs,
     constraints_fixed_cast_conflicts) = create_constraints(model)
    define_objective_minimize(model, unassigned_shifts_per_event, sum_squared_deviations,
                              constraints_weights_in_avail_day_groups,
                              constraints_weights_in_event_groups,
                              constraints_location_prefs, constraints_partner_loc_prefs,
                              constraints_fixed_cast_conflicts)
    print('\n\n++++++++++++++++++++++++++++++++++++++ New Solution +++++++++++++++++++++++++++++++++++++++++++++++++++')
    solver, solver_status = solve_model_to_optimum(model, log_search_process)

    print_solver_status(solver_status)
    print_statistics(solver, None, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations,
                     constraints_partner_loc_prefs, constraints_location_prefs,
                     constraints_fixed_cast_conflicts,
                     constraints_weights_in_event_groups,
                     constraints_weights_in_avail_day_groups)
    unassigned_shifts = sum(solver.Value(u) for u in unassigned_shifts_per_event.values())

    print('partner_loc_prefs_res:', {p.Name(): solver.Value(p) for p in constraints_partner_loc_prefs})
    return (sum(solver.Value(a) for a in sum_assigned_shifts.values()),
            unassigned_shifts,
            solver.Value(sum(constraints_location_prefs)),
            solver.Value(sum(constraints_partner_loc_prefs)),
            solver.Value(sum(constraints_fixed_cast_conflicts.values())))


def call_solver_with_fixed_unassigned_shifts(
        event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree, cast_group_tree: CastGroupTree,
        unassigned_shifts: int, sum_location_prefs: int, sum_partner_loc_prefs: int, sum_fixed_cast_conflicts: int,
        print_solution_printer_results: bool, log_search_process: bool, collect_schedule_versions: bool):
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree, cast_group_tree)
    (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
     constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
     constraints_location_prefs, constraints_partner_loc_prefs,
     constraints_fixed_cast_conflicts) = create_constraints(model)
    define_objective__fixed_unassigned(model,
                                       unassigned_shifts,
                                       sum_location_prefs,
                                       sum_partner_loc_prefs,
                                       sum_fixed_cast_conflicts,
                                       unassigned_shifts_per_event,
                                       constraints_location_prefs,
                                       constraints_partner_loc_prefs,
                                       constraints_fixed_cast_conflicts)
    print('\n\n++++++++++++++++++++++++++++++++++++++ New Solution +++++++++++++++++++++++++++++++++++++++++++++++++++')
    solver, solution_printer, solver_status = solve_model_with_solver_solution_callback(
        model, list(unassigned_shifts_per_event.values()), sum_assigned_shifts,
        sum_squared_deviations, constraints_fixed_cast_conflicts,
        print_solution_printer_results, 1000, log_search_process, collect_schedule_versions)
    print_solver_status(solver_status)
    print_statistics(solver, solution_printer, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations,
                     constraints_partner_loc_prefs, constraints_location_prefs,
                     constraints_fixed_cast_conflicts,
                     constraints_weights_in_event_groups,
                     constraints_weights_in_avail_day_groups)

    return solution_printer.get_max_assigned_shifts()


def call_solver_with_adjusted_requested_assignments(
        event_group_tree: EventGroupTree,
        avail_day_group_tree: AvailDayGroupTree,
        cast_group_tree: CastGroupTree,
        assigned_shifts: int,
        possible_assignment_per_app: dict[UUID, int],
        log_search_process: bool) -> tuple[int, list[int], int, int, int, int, int]:
    print('++++++++++++++++++++++++ Requested Assignments +++++++++++++++++++++++++++++++++')
    print([f'{app.person.f_name}: {app.requested_assignments}' for app in entities.actor_plan_periods.values()])
    generate_adjusted_requested_assignments(assigned_shifts, possible_assignment_per_app)
    print('------------------------ Adjusted Assignments ----------------------------------')
    print([f'{app.person.f_name}: {app.requested_assignments}' for app in entities.actor_plan_periods.values()])

    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree, cast_group_tree)
    (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
     constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
     constraints_location_prefs, constraints_partner_loc_prefs,
     constraints_fixed_cast_conflicts) = create_constraints(model)
    define_objective_minimize(model, unassigned_shifts_per_event, sum_squared_deviations,
                              constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
                              constraints_location_prefs, constraints_partner_loc_prefs,
                              constraints_fixed_cast_conflicts)
    solver, solver_status = solve_model_to_optimum(model, log_search_process)
    print('\n\n++++++++++++++++++++++++++++++++++++++ New Solution +++++++++++++++++++++++++++++++++++++++++++++++++++')
    print_solver_status(solver_status)
    print_statistics(solver, None, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations,
                     constraints_partner_loc_prefs, constraints_location_prefs,
                     constraints_fixed_cast_conflicts,
                     constraints_weights_in_event_groups,
                     constraints_weights_in_avail_day_groups)
    return (solver.Value(sum_squared_deviations), [solver.Value(u) for u in unassigned_shifts_per_event.values()],
            sum(solver.Value(w) for w in constraints_weights_in_avail_day_groups),
            sum(solver.Value(v) for v in constraints_weights_in_event_groups),
            sum(solver.Value(lp) for lp in constraints_location_prefs),
            solver.Value(sum(constraints_partner_loc_prefs)),
            solver.Value(sum(constraints_fixed_cast_conflicts.values())))


def call_solver_with__fixed_constraint_results(
        event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree, cast_group_tree: CastGroupTree,
        unassigned_shifts_per_event_res: list[int], sum_squared_deviations_res: int,
        weights_shifts_in_avail_day_groups_res: int, weights_in_event_groups_res: int, sum_location_prefs_res: int,
        sum_partner_loc_prefs_res: int, sum_fixed_cast_conflicts_res: int, print_solution_printer_results: bool,
        log_search_process: bool, collect_schedule_versions: bool
) -> tuple[PartialSolutionCallback, dict[tuple[datetime.date, str, UUID], int]]:
    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree, cast_group_tree)
    (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
     constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
     constraints_location_prefs, constraints_partner_loc_prefs,
     constraints_fixed_cast_conflicts) = create_constraints(model)
    define_objective__fixed_constraint_results(
        model, list(unassigned_shifts_per_event.values()), sum_squared_deviations,
        constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
        constraints_location_prefs, constraints_partner_loc_prefs,
        constraints_fixed_cast_conflicts, unassigned_shifts_per_event_res,
        sum_squared_deviations_res, weights_shifts_in_avail_day_groups_res,
        weights_in_event_groups_res, sum_location_prefs_res,
        sum_partner_loc_prefs_res, sum_fixed_cast_conflicts_res)
    print('\n\n++++++++++++++++++++++++++++++++++++++ New Solution +++++++++++++++++++++++++++++++++++++++++++++++++++')
    solver, solution_printer, solver_status = solve_model_with_solver_solution_callback(
        model, list(unassigned_shifts_per_event.values()), sum_assigned_shifts,
        sum_squared_deviations, constraints_fixed_cast_conflicts,
        print_solution_printer_results, 100, log_search_process, collect_schedule_versions)
    print_solver_status(solver_status)
    print_statistics(solver, solution_printer, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations,
                     constraints_partner_loc_prefs, constraints_location_prefs,
                     constraints_fixed_cast_conflicts,
                     constraints_weights_in_event_groups,
                     constraints_weights_in_avail_day_groups)

    constraints_fixed_cast_conflicts = {key: solver.Value(val) for key, val in constraints_fixed_cast_conflicts.items()}
    return solution_printer, constraints_fixed_cast_conflicts


def solve(plan_period_id: UUID, log_search_process=False) -> tuple[list[list[schemas.AppointmentCreate]],
                                                                   dict[tuple[datetime.date, str, UUID], int]]:
    global entities
    entities = Entities()

    plan_period = db_services.PlanPeriod.get(plan_period_id)
    entities.actor_plan_periods = {app.id: db_services.ActorPlanPeriod.get(app.id)
                                   for app in plan_period.actor_plan_periods}
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)

    (assigned_shifts, unassigned_shifts, sum_location_prefs, sum_partner_loc_prefs,
     sum_fixed_cast_conflicts) = call_solver_with_unadjusted_requested_assignments(event_group_tree,
                                                                                   avail_day_group_tree,
                                                                                   cast_group_tree,
                                                                                   log_search_process)
    max_shifts_per_app = call_solver_with_fixed_unassigned_shifts(event_group_tree,
                                                                  avail_day_group_tree,
                                                                  cast_group_tree,
                                                                  unassigned_shifts,
                                                                  sum_location_prefs,
                                                                  sum_partner_loc_prefs,
                                                                  sum_fixed_cast_conflicts,
                                                                  False,
                                                                  log_search_process,
                                                                  False)
    (sum_squared_deviations_res, unassigned_shifts_per_event_res, sum_weights_shifts_in_avail_day_groups,
     sum_weights_in_event_groups, sum_location_prefs_res, sum_partner_loc_prefs_res,
     sum_fixed_cast_conflicts_res) = call_solver_with_adjusted_requested_assignments(event_group_tree,
                                                                                     avail_day_group_tree,
                                                                                     cast_group_tree,
                                                                                     assigned_shifts,
                                                                                     max_shifts_per_app,
                                                                                     log_search_process)
    solution_printer, fixed_cast_conflicts = call_solver_with__fixed_constraint_results(
        event_group_tree,
        avail_day_group_tree,
        cast_group_tree,
        unassigned_shifts_per_event_res,
        sum_squared_deviations_res,
        sum_weights_shifts_in_avail_day_groups,
        sum_weights_in_event_groups,
        sum_location_prefs_res,
        sum_partner_loc_prefs_res,
        sum_fixed_cast_conflicts_res,
        True,
        log_search_process,
        True)
    return solution_printer.get_schedule_versions(), fixed_cast_conflicts


if __name__ == '__main__':
    LOG_SEARCH_PROCESS = False
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    solve(PLAN_PERIOD_ID, LOG_SEARCH_PROCESS)
