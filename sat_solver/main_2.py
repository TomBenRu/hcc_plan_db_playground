import dataclasses
from collections import defaultdict
import datetime
from typing import Optional
from uuid import UUID

from ortools.sat.cp_model_pb2 import CpSolverStatus
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

from database import db_services, schemas
from sat_solver.event_group_tree import get_event_group_tree, EventGroupTree, EventGroup


def generate_adjusted_requested_assignments(events: list[schemas.EventShow],
                                            actor_plan_periods: list[schemas.ActorPlanPeriodShow],
                                            assigned_shifts: int) -> list[schemas.ActorPlanPeriodShow]:
    requested_assignments_adjusted: dict[UUID, int] = {app.id: 0 for app in actor_plan_periods}

    for app in actor_plan_periods:
        for event in events:
            if event.date in {avd.date for avd in app.avail_days}:
                requested_assignments_adjusted[app.id] += 1
        requested_assignments_adjusted[app.id] = min(requested_assignments_adjusted[app.id], app.requested_assignments)

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
    for app in actor_plan_periods:
        app.requested_assignments = requested_assignments_new[app.id]
    return actor_plan_periods


class EmployeePartialSolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, shifts: dict[tuple[int, int], IntVar], unassigned_shifts_per_event: list[IntVar],
                 avail_days: list[schemas.AvailDayShow], events: list[schemas.EventShow],
                 sum_assigned_shifts: dict[UUID, IntVar], sum_squared_deviations: IntVar, limit: int):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self._shifts = shifts
        self._unassigned_shifts_per_event = unassigned_shifts_per_event
        self._avail_days = avail_days
        self._events = events
        self._solution_count = 0
        self._sum_assigned_shifts = sum_assigned_shifts
        self._sum_squared_deviations = sum_squared_deviations
        self._solution_limit = limit

    def on_solution_callback(self):
        self._solution_count += 1
        print(f"Solution {self._solution_count}")
        for event_idx, event in enumerate(self._events):
            event: schemas.EventShow
            print(f"Day {event.date: '%d.%m.%y'}")
            for avd_idx, avd in enumerate(self._avail_days):
                avd: schemas.AvailDayShow
                is_working = False
                if self.Value(self._shifts[(avd_idx, event_idx)]):
                    is_working = True
                    print(f"  Employee {avd.actor_plan_period.person.f_name} "
                          f"works in {event.location_plan_period.location_of_work.name:}")
                if not is_working and avd.date == event.date:
                    print(f"  Employee {avd.actor_plan_period.person.f_name} does not work")
        print('unassigned_shifts_per_event:',
              [self.Value(unassigned_shifts) for unassigned_shifts in self._unassigned_shifts_per_event])
        print(f'sum_assigned_shifts_of_employees: {[self.Value(s) for s in self._sum_assigned_shifts.values()]}')
        print(f'sum_squared_deviations: {self.Value(self._sum_squared_deviations)}')
        if self._solution_count >= self._solution_limit:
            print(f"Stop search after {self._solution_limit} solutions")
            self.StopSearch()

    def solution_count(self):
        return self._solution_count


@dataclasses.dataclass
class Entities:
    actor_plan_periods: list[schemas.ActorPlanPeriodShow] = dataclasses.field(default_factory=list)
    avail_days: dict[UUID, schemas.AvailDayShow] = dataclasses.field(default_factory=dict)
    event_groups: dict[UUID, EventGroup] = dataclasses.field(default_factory=dict)
    event_groups_with_event: dict[UUID, EventGroup] = dataclasses.field(default_factory=dict)
    shift_vars: dict[tuple[UUID, UUID], IntVar] = dataclasses.field(default_factory=dict)
    event_group_vars: dict[UUID, IntVar] = dataclasses.field(default_factory=dict)


entities = Entities()

appointments: defaultdict[tuple[datetime.date, int], list['AppointmentCast']] = defaultdict(list)


class AppointmentCast:
    def __init__(self, event: schemas.EventShow):
        self.event = event
        self.avail_days: list[schemas.AvailDayShow] = []

    def add_avail_day(self, avail_day: schemas.AvailDayShow | None):
        self.avail_days.append(avail_day)


def create_vars(model: cp_model.CpModel, event_group_tree: EventGroupTree) -> tuple[dict[tuple[UUID, UUID], IntVar], [dict[UUID, IntVar]]]:
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

    entities.event_groups_with_event = {leave.event_group_id: leave for leave in event_group_tree.root.leaves if leave.event}

    entities.shift_vars = {}
    for avd_id in entities.avail_days:
        for event_group_id in entities.event_groups_with_event:
            entities.shift_vars[(avd_id, event_group_id)] = model.NewBoolVar(f'shift ({avd_id}, {event_group_id})')


def add_constraints_employee_availability(model: cp_model.CpModel):
    for avd in entities.avail_days.values():
        for event_group in entities.event_groups_with_event.values():
            if (event_group.event.date != avd.date
                    or (event_group.event.time_of_day.start < avd.time_of_day.start)
                    or (event_group.event.time_of_day.end > avd.time_of_day.end)):
                model.Add(entities.shift_vars[(avd.id, event_group.event_group_id)] == 0)


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


def add_constraints_unsigned_shifts(model: cp_model.CpModel) -> dict[UUID, IntVar]:
    unassigned_shifts_per_event = {
        event_group_id: model.NewIntVar(
            0, sum(evg.event.cast_group.nr_actors
                   for evg in entities.event_groups_with_event.values()), f'unassigned {event_group.event.date}'
        )
        for event_group_id, event_group in entities.event_groups_with_event.items()}

    for event_group_id, event_group in entities.event_groups_with_event.items():
        num_assigned_employees = sum(entities.shift_vars[(avd_id, event_group_id)] for avd_id in entities.avail_days)
        model.Add(
            num_assigned_employees <= (entities.event_group_vars[event_group.event_group_id]
                                       * event_group.event.cast_group.nr_actors)
        )
        model.Add(unassigned_shifts_per_event[event_group_id] == (
                entities.event_group_vars[event_group.event_group_id] * event_group.event.cast_group.nr_actors
                - num_assigned_employees))
    return unassigned_shifts_per_event


def add_constraints_rel_shift_deviations(model) -> tuple[dict[UUID, IntVar], IntVar]:
    # Create a lists to represent the sums of assigned shifts and the relative shift deviations for each employee.
    sum_assigned_shifts = {
        app.id: model.NewIntVar(0, 1000, f'sum_assigned_shifts {app.person.f_name}')
        for app in entities.actor_plan_periods
    }
    relative_shift_deviations = {
        app.id: model.NewIntVar(
            -len(entities.event_groups_with_event) * 100_000_000,
            len(entities.event_groups_with_event) * 100_000_000,
            f'relative_shift_deviation_{app.person.f_name}'
        )
        for app in entities.actor_plan_periods
    }

    # Add a constraint for each actor_plan_period,
    # that the relative shift deviation is equal to (requested shifts - actual shifts) / requested shifts.
    for app in entities.actor_plan_periods:
        assigned_shifts_of_app = 0
        for avd_id, avd in entities.avail_days.items():
            if avd.actor_plan_period.id == app.id:
                assigned_shifts_of_app += sum(entities.shift_vars[(avd_id, evg_id)]
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
        for app in entities.actor_plan_periods
    }

    # Add a constraint for each actor_plan_period,
    # that the squared deviation is equal to (relative shift deviation - average)^2.
    dif_average__relative_shift_deviations = {}
    for app in entities.actor_plan_periods:
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


def define_objective__fixed_unsigned_squared_deviation(
        model: cp_model.CpModel, unassigned_shifts_per_event: list[IntVar], sum_squared_deviations: IntVar,
        unassigned_shifts_per_event_res: list[int], sum_squared_deviations_res: int):
    model.Add(sum(unassigned_shifts_per_event) == sum(unassigned_shifts_per_event_res))
    model.Add(sum_squared_deviations == sum_squared_deviations_res)


def solve_model_with_solver_solution_callback(
        model: cp_model.CpModel, shifts: dict[tuple[int, int], IntVar], unassigned_shifts_per_event: list[IntVar],
        sum_assigned_shifts: dict[UUID, IntVar],
        sum_squared_deviations: IntVar) -> tuple[cp_model.CpSolver, EmployeePartialSolutionPrinter, CpSolverStatus]:
    # Solve the model.
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = False
    solver.parameters.randomize_search = True
    solver.parameters.linearization_level = 0
    solver.parameters.enumerate_all_solutions = True
    solution_printer = EmployeePartialSolutionPrinter(shifts,
                                                      unassigned_shifts_per_event,
                                                      avail_days,
                                                      events, sum_assigned_shifts,
                                                      sum_squared_deviations, 20)

    status = solver.Solve(model, solution_printer)

    return solver, solution_printer, status


def solve_model_to_optimum(model: cp_model.CpModel) -> tuple[cp_model.CpSolver, CpSolverStatus]:
    # Solve the model.
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
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
    for app_id, var in sum_assigned_shifts.items():
        print(app_id, solver.Value(var))

    for evg_id, evg in entities.event_groups_with_event.items():
        nr_shifts = sum(solver.Value(entities.shift_vars[avd_id, evg_id]) for avd_id in entities.avail_days)
        print(evg.event.date, nr_shifts)

    for evg_id, var in entities.event_group_vars.items():
        print(evg_id, solver.Value(var))


def print_solver_status(status: CpSolverStatus):
    if status == cp_model.OPTIMAL:
        print('########################### OPTIMAL ############################################')
    elif status == cp_model.FEASIBLE:
        print('########################### FEASIBLE ############################################')
    else:
        print('########################### FAILED ############################################')


def call_solver_with_unadjusted_requested_assignments(event_group_tree: EventGroupTree) -> int:
    # Create the CP-SAT model.
    model = cp_model.CpModel()
    create_vars(model, event_group_tree)
    unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations = create_constraints(model)
    define_objective_minimize(model, unassigned_shifts_per_event, sum_squared_deviations)
    solver, solver_status = solve_model_to_optimum(model)
    print_statistics(solver, None, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations)
    print_solver_status(solver_status)
    return sum(solver.Value(a) for a in sum_assigned_shifts.values())


def call_solver_with_adjusted_requested_assignments(
        assigned_shifts: int) -> tuple[int, list[int], list[schemas.ActorPlanPeriodShow]]:
    print('+++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
    print([app.requested_assignments for app in actor_plan_periods])
    actor_plan_periods_adjusted = generate_adjusted_requested_assignments(
        events, actor_plan_periods, assigned_shifts)
    print([app.requested_assignments for app in actor_plan_periods_adjusted])

    # Create the CP-SAT model.
    model = cp_model.CpModel()
    shifts = create_vars(model, events, avail_days)
    unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations = create_constraints(
        model, shifts, actor_plan_periods_adjusted)
    define_objective_minimize(model, unassigned_shifts_per_event, sum_squared_deviations)
    solver, solver_status = solve_model_to_optimum(model)
    print_statistics(solver, None, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations)
    print_solver_status(solver_status)
    return (solver.Value(sum_squared_deviations),
            [solver.Value(u) for u in unassigned_shifts_per_event],
            actor_plan_periods_adjusted)


def call_solver_with__fixed_unassigned_shifts_fixed_squared_deviation(
        unassigned_shifts_per_event_res: list[int], sum_squared_deviations_res: int,
        actor_plan_periods: list[schemas.ActorPlanPeriodShow]):
    # Create the CP-SAT model.
    model = cp_model.CpModel()
    shifts = create_vars(model, events, avail_days)
    unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations = create_constraints(
        model, shifts, actor_plan_periods)
    define_objective__fixed_unsigned_squared_deviation(
        model, unassigned_shifts_per_event, sum_squared_deviations,
        unassigned_shifts_per_event_res, sum_squared_deviations_res
    )
    solver, solution_printer, solver_status = solve_model_with_solver_solution_callback(
        model, shifts, unassigned_shifts_per_event, sum_assigned_shifts,
        sum_squared_deviations)
    print_solver_status(solver_status)
    print_statistics(solver, solution_printer, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations)


def main(plan_period_id: UUID):
    plan_period = db_services.PlanPeriod.get(plan_period_id)
    entities.avail_days = {avd.id: avd for avd in db_services.AvailDay.get_all_from__plan_period(plan_period_id)}
    entities.actor_plan_periods = [db_services.ActorPlanPeriod.get(app.id) for app in plan_period.actor_plan_periods]
    event_group_tree = get_event_group_tree(plan_period_id)

    assigned_shifts = call_solver_with_unadjusted_requested_assignments(event_group_tree)
    # sum_squared_deviations_res, unassigned_shifts_per_event_res, actor_plan_periods_adjusted = call_solver_with_adjusted_requested_assignments(assigned_shifts)
    # call_solver_with__fixed_unassigned_shifts_fixed_squared_deviation(
    #     unassigned_shifts_per_event_res, sum_squared_deviations_res, actor_plan_periods_adjusted)


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    main(PLAN_PERIOD_ID)
