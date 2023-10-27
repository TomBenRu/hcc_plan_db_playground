import dataclasses
from collections import defaultdict
import datetime
from typing import Optional
from uuid import UUID

from ortools.sat.cp_model_pb2 import CpSolverStatus
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

from database import db_services, schemas
from sat_solver.avail_day_group_tree import AvailDayGroup, get_avail_day_group_tree, AvailDayGroupTree
from sat_solver.event_group_tree import get_event_group_tree, EventGroupTree, EventGroup


def generate_adjusted_requested_assignments(assigned_shifts: int, possible_assignments: dict[UUID, int]):
    # fixme: unkorrekt mit avail_day_group Einschränkungen
    requested_assignments_adjusted: dict[UUID, int] = {
        app_id: min(entities.actor_plan_periods[app_id].requested_assignments, assignments)
        for app_id, assignments in possible_assignments.items()
    }

    requested_assignments_new: dict[UUID, int] = {}
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


class EmployeePartialSolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, unassigned_shifts_per_event: list[IntVar],
                 sum_assigned_shifts: dict[UUID, IntVar], sum_squared_deviations: IntVar, limit: int | None,
                 print_results: bool):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self._unassigned_shifts_per_event = unassigned_shifts_per_event
        self._solution_count = 0
        self._sum_assigned_shifts = sum_assigned_shifts
        self._sum_squared_deviations = sum_squared_deviations
        self._solution_limit = limit
        self._max_assigned_shifts: defaultdict[UUID, int] = defaultdict(int)
        self._print_results = print_results

    def on_solution_callback(self):
        self._solution_count += 1
        if self._print_results:
            self.print_results()
        for app_id, s in self._sum_assigned_shifts.items():
            self._max_assigned_shifts[app_id] = max(self._max_assigned_shifts[app_id], self.Value(s))

        if self._solution_limit and self._solution_count >= self._solution_limit:
            print(f"Stop search after {self._solution_limit} solutions")
            self.StopSearch()

    def print_results(self):
        print(f"Solution {self._solution_count}")
        for event_group in entities.event_groups_with_event.values():
            if not self.Value(entities.event_group_vars[event_group.event_group_id]):
                continue
            print(f"Day {event_group.event.date: '%d.%m.%y'} ({event_group.event.time_of_day.name})")
            for actor_plan_period in entities.actor_plan_periods.values():
                is_working = False
                if sum(self.Value(entities.shift_vars[(avd_id, event_group.event_group_id)])
                       for avd_id in (avd.avail_day_group.id for avd in actor_plan_period.avail_days)):
                    is_working = True
                    print(f"  Employee {actor_plan_period.person.f_name} "
                          f"works in {event_group.event.location_plan_period.location_of_work.name:}")
                else:
                    print(f"  Employee {actor_plan_period.person.f_name} does not work")
        print('unassigned_shifts_per_event:',
              [self.Value(unassigned_shifts) for unassigned_shifts in self._unassigned_shifts_per_event])
        sum_assigned_shifts_per_employee = {entities.actor_plan_periods[app_id].person.f_name: self.Value(s)
                                            for app_id, s in self._sum_assigned_shifts.items()}
        print(f'sum_assigned_shifts_of_employees: {sum_assigned_shifts_per_employee}')
        print(f'sum_squared_deviations: {self.Value(self._sum_squared_deviations)}')
        for app_id, app in entities.actor_plan_periods.items():
            group_vars = {
                entities.avail_day_groups_with_avail_day[adg_id].avail_day.date: self.Value(var)
                for adg_id, var in entities.avail_day_group_vars.items()
                if (adg_id in entities.avail_day_groups_with_avail_day
                    and entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.id == app_id)}
            print(f'active_avail_day_groups of {app.person.f_name}: {group_vars}')

    def get_max_assigned_shifts(self):
        return self._max_assigned_shifts

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
    shift_vars: dict[tuple[UUID, UUID], IntVar] = dataclasses.field(default_factory=dict)


entities = Entities()

appointments: defaultdict[tuple[datetime.date, int], list['AppointmentCast']] = defaultdict(list)


class AppointmentCast:
    def __init__(self, event: schemas.EventShow):
        self.event = event
        self.avail_days: list[schemas.AvailDayShow] = []

    def add_avail_day(self, avail_day: schemas.AvailDayShow | None):
        self.avail_days.append(avail_day)


def create_vars(model: cp_model.CpModel, event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree):
    """
    Create variables for the constraint programming model.

    Args:
        model: The constraint programming model.
        event_group_tree: The tree structure representing event groups.
        avail_days: The list of available days.

    Returns: A tuple containing two dictionaries:
            - The dictionary of shift variables, where the keys are tuples of (avail_day_id, event_id) and the values are IntVars.
            - The dictionary of event group variables, where the keys are event group IDs and the values are IntVars.
    """

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

    entities.shift_vars = {}
    for adg_id in entities.avail_day_groups_with_avail_day:
        for event_group_id in entities.event_groups_with_event:
            entities.shift_vars[(adg_id, event_group_id)] = model.NewBoolVar(f'shift ({adg_id}, {event_group_id})')


def add_constraints_employee_availability(model: cp_model.CpModel):
    for adg in entities.avail_day_groups_with_avail_day.values():
        for event_group in entities.event_groups_with_event.values():
            if (event_group.event.date != adg.avail_day.date
                    or (event_group.event.time_of_day.start < adg.avail_day.time_of_day.start)
                    or (event_group.event.time_of_day.end > adg.avail_day.time_of_day.end)):
                model.Add(entities.shift_vars[(adg.avail_day_group_id, event_group.event_group_id)] == 0)


def add_constraints_event_groups_activity(model: cp_model.CpModel):
    for event_group_id, event_group in entities.event_groups.items():
        if event_group.children:
            nr_of_active_children = (event_group.nr_of_active_children
                                     or len([c for c in event_group.children if c.children or c.event]))
            if event_group.is_root:
                model.Add(
                    sum(
                        entities.event_group_vars[c.event_group_id] for c in event_group.children
                        if c.children or c.event
                    ) == nr_of_active_children
                )
            else:
                model.Add(
                    sum(entities.event_group_vars[c.event_group_id] for c in event_group.children
                        if c.children or c.event
                        ) == nr_of_active_children * entities.event_group_vars[event_group_id]
                )


def add_constraints_avail_day_groups_activity(model: cp_model):
    for avail_day_group_id, avail_day_group in entities.avail_day_groups.items():
        if avail_day_group.children:
            nr_of_active_children = (avail_day_group.nr_of_active_children
                                     or len([c for c in avail_day_group.children if c.children or c.avail_day]))
            if avail_day_group.is_root:
                model.Add(
                    sum(
                        entities.avail_day_group_vars[c.avail_day_group_id] for c in avail_day_group.children
                        if c.children or c.avail_day
                    ) == nr_of_active_children
                )
            else:
                model.Add(
                    sum(entities.avail_day_group_vars[c.avail_day_group_id] for c in avail_day_group.children
                        if c.children or c.avail_day
                        ) == nr_of_active_children * entities.avail_day_group_vars[avail_day_group_id]
                )


def add_constraints_shifts_in_avail_day_groups(model: cp_model.CpModel):
    rating_signed_shifts: list[IntVar] = []
    for (adg_id, event_group_id), shift_var in entities.shift_vars.items():
        rating_var = model.NewBoolVar('')
        model.AddMultiplicationEquality(rating_var, [shift_var, 1 - entities.avail_day_group_vars[adg_id]])
        rating_signed_shifts.append(rating_var)
    model.Add(sum(rating_signed_shifts) == 0)


def add_constraints_unsigned_shifts(model: cp_model.CpModel) -> dict[UUID, IntVar]:
    unassigned_shifts_per_event = {
        event_group_id: model.NewIntVar(
            0, sum(evg.event.cast_group.nr_actors
                   for evg in entities.event_groups_with_event.values()), f'unassigned {event_group.event.date}'
        )
        for event_group_id, event_group in entities.event_groups_with_event.items()}

    for event_group_id, event_group in entities.event_groups_with_event.items():
        num_assigned_employees = sum(
            entities.shift_vars[(adg_id, event_group_id)] for adg_id in (entities.avail_day_groups_with_avail_day)
        )
        model.Add(
            num_assigned_employees <= (entities.event_group_vars[event_group.event_group_id]
                                       * event_group.event.cast_group.nr_actors)
        )
        model.Add(unassigned_shifts_per_event[event_group_id] == (
                entities.event_group_vars[event_group.event_group_id] * event_group.event.cast_group.nr_actors
                - num_assigned_employees))
    return unassigned_shifts_per_event


def add_constraints_rel_shift_deviations(model) -> tuple[dict[UUID, IntVar], IntVar]:
    # Create a lists to represent the sums of assigned shifts and the relative shift deviations for each actor_plan_period.
    sum_assigned_shifts = {
        app.id: model.NewIntVar(0, 1000, f'sum_assigned_shifts {app.person.f_name}')
        for app in entities.actor_plan_periods.values()
    }
    relative_shift_deviations = {
        app.id: model.NewIntVar(
            -len(entities.event_groups_with_event) * 100_000_000,
            len(entities.event_groups_with_event) * 100_000_000,
            f'relative_shift_deviation_{app.person.f_name}'
        )
        for app in entities.actor_plan_periods.values()
    }

    # Add a constraint for each actor_plan_period,
    # that the relative shift deviation is equal to (requested shifts - actual shifts) / requested shifts.
    for app in entities.actor_plan_periods.values():
        assigned_shifts_of_app = 0
        for adg_id, adg in entities.avail_day_groups_with_avail_day.items():
            if adg.avail_day.actor_plan_period.id == app.id:
                assigned_shifts_of_app += sum(entities.shift_vars[(adg_id, evg_id)]
                                              for evg_id in entities.event_groups_with_event)
        model.AddAbsEquality(
            sum_assigned_shifts[app.id], assigned_shifts_of_app
        )
        model.AddDivisionEquality(
            relative_shift_deviations[app.id],
            sum_assigned_shifts[app.id] * 100_000 - int(app.requested_assignments * 100_000),
            int(app.requested_assignments * 100) if app.requested_assignments else 1)

    # Calculate the average of the relative shift deviations.
    average_relative_shift_deviation = model.NewIntVar(-100_000_000, 100_000_000,
                                                       'average_relative_shift_deviation')
    sum_relative_shift_deviations = model.NewIntVar(-len(entities.event_groups_with_event) * 100_000_000,
                                                    len(entities.event_groups_with_event) * 100_000_000,
                                                    'sum_relative_shift_deviations')
    model.AddAbsEquality(sum_relative_shift_deviations, sum(relative_shift_deviations.values()))
    model.AddDivisionEquality(average_relative_shift_deviation,
                              sum_relative_shift_deviations,
                              len(entities.actor_plan_periods))

    # Create a list to represent the squared deviations from the average for each actor_plan_period.
    squared_deviations = {
        app.id: model.NewIntVar(0,
                                (len(entities.event_groups_with_event) * 10_000_000) ** 2,
                                f'squared_deviation_{app.person.f_name}')
        for app in entities.actor_plan_periods.values()
    }

    # Add a constraint for each actor_plan_period,
    # that the squared deviation is equal to (relative shift deviation - average)^2.
    dif_average__relative_shift_deviations = {}
    for app in entities.actor_plan_periods.values():
        dif_average__relative_shift_deviations[app.id] = model.NewIntVar(
            -100_000_000, 100_000_000, f'dif_average__relative_shift_deviation {app.id}')
        model.AddAbsEquality(dif_average__relative_shift_deviations[app.id],
                             relative_shift_deviations[app.id] - average_relative_shift_deviation)

        model.AddMultiplicationEquality(
            squared_deviations[app.id],
            [dif_average__relative_shift_deviations[app.id], dif_average__relative_shift_deviations[app.id]])

    # Add a constraint that the sum_squared_deviations is equal to the sum(squared_deviations).
    sum_squared_deviations = model.NewIntVar(0, 10 ** 16, 'sum_squared_deviations')
    model.AddAbsEquality(sum_squared_deviations, sum(squared_deviations.values()))

    return sum_assigned_shifts, sum_squared_deviations


def create_constraints(model: cp_model.CpModel) -> tuple[dict[UUID, IntVar], dict[UUID, IntVar], IntVar]:
    # Add constraints for employee availability.
    add_constraints_employee_availability(model)

    # Add constraints for activity of event groups:
    add_constraints_event_groups_activity(model)

    # Add constraints for activity of avail_day groups:
    add_constraints_avail_day_groups_activity(model)

    # Add constaints for shifts in inactive avail_day_groups:
    add_constraints_shifts_in_avail_day_groups(model)

    # Add constraints for unsigned shifts:
    unassigned_shifts_per_event = add_constraints_unsigned_shifts(model)

    # Add constraints for relative shift deviations:
    sum_assigned_shifts, sum_squared_deviations = add_constraints_rel_shift_deviations(model)

    return unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations


def define_objective_minimize(model: cp_model.CpModel, unassigned_shifts_per_event: dict[UUID, IntVar],
                              sum_squared_deviations: IntVar):
    """Change the objective to minimize a weighted sum of the number of unassigned shifts
    and the sum of the squared deviations."""
    weight_unassigned_shifts = 100_000
    weight_sum_squared_shift_deviations = 0.001 / len(entities.actor_plan_periods)
    model.Minimize(weight_unassigned_shifts*sum(unassigned_shifts_per_event.values())
                   + weight_sum_squared_shift_deviations*sum_squared_deviations)


def define_objective__fixed_unassigned(model: cp_model.CpModel,
                                       unassigned_shifts: int,
                                       unassigned_shifts_per_event: dict[UUID, IntVar]):
    model.Add(sum(list(unassigned_shifts_per_event.values())) == unassigned_shifts)


def define_objective__fixed_unsigned_squared_deviation(
        model: cp_model.CpModel, unassigned_shifts_per_event: list[IntVar], sum_squared_deviations: IntVar,
        unassigned_shifts_per_event_res: list[int], sum_squared_deviations_res: int):
    model.Add(sum(unassigned_shifts_per_event) == sum(unassigned_shifts_per_event_res))
    model.Add(sum_squared_deviations == sum_squared_deviations_res)


def solve_model_with_solver_solution_callback(
        model: cp_model.CpModel, unassigned_shifts_per_event: list[IntVar],
        sum_assigned_shifts: dict[UUID, IntVar],
        sum_squared_deviations: IntVar,
        print_solution_printer_results: bool,
        limit: int | None) -> tuple[cp_model.CpSolver, EmployeePartialSolutionPrinter,
                                                       CpSolverStatus]:
    # Solve the model.
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = LOG_SEARCH_PROCESS
    solver.parameters.randomize_search = True
    solver.parameters.linearization_level = 0
    solver.parameters.enumerate_all_solutions = True
    solution_printer = EmployeePartialSolutionPrinter(unassigned_shifts_per_event,
                                                      sum_assigned_shifts,
                                                      sum_squared_deviations, limit,
                                                      print_solution_printer_results)

    status = solver.Solve(model, solution_printer)

    return solver, solution_printer, status


def solve_model_to_optimum(model: cp_model.CpModel) -> tuple[cp_model.CpSolver, CpSolverStatus]:
    # Solve the model.
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = LOG_SEARCH_PROCESS
    solver.parameters.linearization_level = 0
    solver.parameters.enumerate_all_solutions = False

    status = solver.Solve(model)

    return solver, status


def print_statistics(solver: cp_model.CpSolver, solution_printer: EmployeePartialSolutionPrinter | None,
                     unassigned_shifts_per_event: dict[UUID, IntVar], sum_assigned_shifts: dict[UUID, IntVar],
                     sum_squared_deviations: IntVar):
    # Statistics.
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


def print_solver_status(status: CpSolverStatus):
    if status == cp_model.OPTIMAL:
        print('########################### OPTIMAL ############################################')
    elif status == cp_model.FEASIBLE:
        print('########################### FEASIBLE ############################################')
    else:
        print('########################### FAILED ############################################')


def call_solver_with_unadjusted_requested_assignments(
        event_group_tree: EventGroupTree, avail_day_group_tree) -> tuple[int, int]:
    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree)
    unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations = create_constraints(model)
    define_objective_minimize(model, unassigned_shifts_per_event, sum_squared_deviations)
    solver, solver_status = solve_model_to_optimum(model)
    print_statistics(solver, None, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations)
    print_solver_status(solver_status)
    unassigned_shifts = sum(solver.Value(u) for u in unassigned_shifts_per_event.values())

    return sum(solver.Value(a) for a in sum_assigned_shifts.values()), unassigned_shifts


def call_solver_with_fixed_unassigned_shifts(
        event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree, unassigned_shifts: int,
        print_solution_printer_results: bool):
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree)
    unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations = create_constraints(model)
    define_objective__fixed_unassigned(model, unassigned_shifts, unassigned_shifts_per_event)
    solver, solution_printer, solver_status = solve_model_with_solver_solution_callback(
        model, list(unassigned_shifts_per_event.values()), sum_assigned_shifts,
        sum_squared_deviations, print_solution_printer_results, None)
    print_statistics(solver, solution_printer, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations)

    return solution_printer.get_max_assigned_shifts()


def call_solver_with_adjusted_requested_assignments(
        event_group_tree: EventGroupTree,
        avail_day_group_tree: AvailDayGroupTree,
        assigned_shifts: int,
        possible_assignment_per_app: dict[UUID, int]) -> tuple[int, list[int]]:
    print('+++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
    print([app.requested_assignments for app in entities.actor_plan_periods.values()])
    generate_adjusted_requested_assignments(assigned_shifts, possible_assignment_per_app)
    print([app.requested_assignments for app in entities.actor_plan_periods.values()])

    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree)
    unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations = create_constraints(model)
    define_objective_minimize(model, unassigned_shifts_per_event, sum_squared_deviations)
    solver, solver_status = solve_model_to_optimum(model)
    print_statistics(solver, None, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations)
    print_solver_status(solver_status)
    return solver.Value(sum_squared_deviations), [solver.Value(u) for u in unassigned_shifts_per_event.values()]


def call_solver_with__fixed_unassigned_shifts_fixed_squared_deviation(
        event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree,
        unassigned_shifts_per_event_res: list[int], sum_squared_deviations_res: int,
        print_solution_printer_results: bool):
    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree)
    unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations = create_constraints(model)
    define_objective__fixed_unsigned_squared_deviation(
        model, list(unassigned_shifts_per_event.values()), sum_squared_deviations,
        unassigned_shifts_per_event_res, sum_squared_deviations_res)
    solver, solution_printer, solver_status = solve_model_with_solver_solution_callback(
        model, list(unassigned_shifts_per_event.values()), sum_assigned_shifts,
        sum_squared_deviations, print_solution_printer_results, None)
    print_solver_status(solver_status)
    print_statistics(solver, solution_printer, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations)


def main(plan_period_id: UUID):
    plan_period = db_services.PlanPeriod.get(plan_period_id)
    entities.actor_plan_periods = {app.id: db_services.ActorPlanPeriod.get(app.id)
                                   for app in plan_period.actor_plan_periods}
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)

    assigned_shifts, unassigned_shifts = call_solver_with_unadjusted_requested_assignments(
        event_group_tree, avail_day_group_tree)
    max_shifts_per_app = call_solver_with_fixed_unassigned_shifts(
        event_group_tree, avail_day_group_tree, unassigned_shifts, False)
    (sum_squared_deviations_res, unassigned_shifts_per_event_res) = call_solver_with_adjusted_requested_assignments(
        event_group_tree, avail_day_group_tree, assigned_shifts, max_shifts_per_app)
    call_solver_with__fixed_unassigned_shifts_fixed_squared_deviation(event_group_tree,
                                                                      avail_day_group_tree,
                                                                      unassigned_shifts_per_event_res,
                                                                      sum_squared_deviations_res,
                                                                      True)


if __name__ == '__main__':
    LOG_SEARCH_PROCESS = False
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    main(PLAN_PERIOD_ID)
