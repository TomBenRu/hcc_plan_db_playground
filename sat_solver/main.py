from collections import defaultdict
import datetime
from typing import Optional
from uuid import UUID

from ortools.sat.cp_model_pb2 import CpSolverStatus
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

from database import db_services, schemas


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


actor_plan_periods: list[schemas.ActorPlanPeriodShow] = []

events: list[schemas.EventShow] = []

avail_days: list[schemas.AvailDayShow] = []

appointments: defaultdict[tuple[datetime.date, int], list['AppointmentCast']] = defaultdict(list)


class AppointmentCast:
    def __init__(self, event: schemas.EventShow):
        self.event = event
        self.avail_days: list[schemas.AvailDayShow] = []

    def add_avail_day(self, avail_day: schemas.AvailDayShow | None):
        self.avail_days.append(avail_day)


class EventGroupCast:
    def __init__(self, event_group: schemas.EventGroupShow, parent_group: Optional['EventGroupCast']):
        self.event_group: schemas.EventGroupShow = event_group
        self.event_of_event_group = db_services.Event.get(event_group.event.id) if event_group.event else None
        self.parent_group: 'EventGroupCast' = parent_group
        self.child_groups: list['EventGroupCast'] = []
        self.nr_child_groups_to_activate: int | None = event_group.nr_event_groups

        self.find_event()
        self.fill_child_groups()

    def find_event(self):
        self.event_of_event_group = db_services.Event.get(self.event_group.event.id) if self.event_group.event else None
        if self.event_of_event_group:
            events.append(self.event_of_event_group)

    def fill_child_groups(self):
        for event_group in self.event_group.event_groups:
            event_group = db_services.EventGroup.get(event_group.id)
            self.child_groups.append(EventGroupCast(event_group, self))


class AvailDayGroupCast:
    def __init__(self, avail_day_group: schemas.AvailDayGroupShow, parent_group: Optional['AvailDayGroupCast']):
        self.avail_day_group = avail_day_group
        self.avail_day_of_avail_day_group: schemas.AvailDayShow | None = None
        self.parent_group = parent_group
        self.child_groups: list['AvailDayGroupCast'] = []
        self.nr_child_groups_to_activate: int | None = avail_day_group.nr_avail_day_groups

        self.find_avail_day()
        self.fill_child_groups()

    def find_avail_day(self):
        self.avail_day_of_avail_day_group = db_services.AvailDay.get_from__avail_day_group(self.avail_day_group.id)
        if self.avail_day_of_avail_day_group:
            avail_days.append(self.avail_day_of_avail_day_group)

    def fill_child_groups(self):
        for avail_day_group in db_services.AvailDayGroup.get_child_groups_from__parent_group(self.avail_day_group.id):
            self.child_groups.append(AvailDayGroupCast(avail_day_group, self))


def create_vars(model: cp_model.CpModel, events: list[schemas.EventShow],
                avail_days: list[schemas.AvailDayShow]) -> dict[tuple[int, int], IntVar]:
    shifts = {}
    for a in range(len(avail_days)):
        for e in range(len(events)):
            shifts[(a, e)] = model.NewBoolVar(f'shift {a, e}')
    return shifts


def create_constraints(
        model: cp_model.CpModel, shifts: dict[tuple[int, int], IntVar],
        actor_plan_periods: list[schemas.ActorPlanPeriodShow]) -> tuple[list[IntVar], dict[UUID, IntVar], IntVar]:
    # Add constraints for employee availability.
    for a in range(len(avail_days)):
        for e in range(len(events)):
            if (events[e].date != avail_days[a].date
                    or (events[e].time_of_day.start < avail_days[a].time_of_day.start)
                    or (events[e].time_of_day.end > avail_days[a].time_of_day.end)):
                model.Add(shifts[(a, e)] == 0)

    # Create a list to represent the number of unassigned shifts for each event.
    unassigned_shifts_per_event = [
        model.NewIntVar(0, sum(e.cast_group.nr_actors for e in events), f'unassigned_shifts_event_{e}')
        for e in range(len(events))]

    # Add a constraint for each event that the number of assigned employees is at most the number of needed employees,
    # and update the number of unassigned shifts for each event.
    for e in range(len(events)):
        num_assigned_employees = sum(shifts[(a, e)] for a in range(len(avail_days)))
        model.Add(num_assigned_employees <= events[e].cast_group.nr_actors)
        model.Add(unassigned_shifts_per_event[e] == events[e].cast_group.nr_actors - num_assigned_employees)

    # Create a lists to represent the sums of assigned shifts and the relative shift deviations for each employee.
    sum_assigned_shifts = {
        app.id: model.NewIntVar(0, 1000, f'sum_assigned_shifts {app.person.f_name}')
        for app in actor_plan_periods
    }
    relative_shift_deviations = {
        app.id: model.NewIntVar(
            -len(events) * 100_000_000, len(events) * 100_000_000, f'relative_shift_deviation_{app.person.f_name}'
        )
        for app in actor_plan_periods
    }

    # Add a constraint for each actor_plan_period,
    # that the relative shift deviation is equal to (requested shifts - actual shifts) / requested shifts.
    for app in actor_plan_periods:
        assigned_shifts_of_app = 0
        for a in range(len(avail_days)):
            if avail_days[a].actor_plan_period.id == app.id:
                assigned_shifts_of_app += sum(shifts[(a, e)] for e in range(len(events)))
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
    sum_relative_shift_deviations = model.NewIntVar(-len(events)*100_000_000, len(events)*100_000_000,
                                                    'sum_relative_shift_deviations')
    model.AddAbsEquality(sum_relative_shift_deviations, sum(relative_shift_deviations.values()))
    model.AddDivisionEquality(average_relative_shift_deviation, sum_relative_shift_deviations, len(actor_plan_periods))

    # Create a list to represent the squared deviations from the average for each actor_plan_period.
    squared_deviations = {
        app.id: model.NewIntVar(0, (len(events) * 10_000_000) ** 2, f'squared_deviation_{app.person.f_name}')
        for app in actor_plan_periods
    }

    # Add a constraint for each actor_plan_period,
    # that the squared deviation is equal to (relative shift deviation - average)^2.
    dif_average__relative_shift_deviations = {}
    for app in actor_plan_periods:
        dif_average__relative_shift_deviations[app.id] = model.NewIntVar(
            -100_000_000, 100_000_000, f'dif_average__relative_shift_deviation {app.id}')
        model.AddAbsEquality(dif_average__relative_shift_deviations[app.id],
                             relative_shift_deviations[app.id] - average_relative_shift_deviation)

        model.AddMultiplicationEquality(
            squared_deviations[app.id],
            [dif_average__relative_shift_deviations[app.id], dif_average__relative_shift_deviations[app.id]])

    # Add a constraint that the sum_squared_deviations is equal to the sum(squared_deviations).
    sum_squared_deviations = model.NewIntVar(0, 10**16, 'sum_squared_deviations')
    model.AddAbsEquality(sum_squared_deviations, sum(squared_deviations.values()))

    return unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations


def define_objective_minimize(model: cp_model.CpModel, unassigned_shifts_per_event: list[IntVar],
                              sum_squared_deviations: IntVar):
    """Change the objective to minimize a weighted sum of the number of unassigned shifts
    and the sum of the squared deviations."""
    weight_unassigned_shifts = 100_000
    weight_sum_squared_shift_deviations = 0.001 / len(actor_plan_periods)
    model.Minimize(weight_unassigned_shifts*sum(unassigned_shifts_per_event)
                   + weight_sum_squared_shift_deviations*sum_squared_deviations)


def define_objective__fixed_unsigned_squared_deviation(
        model: cp_model.CpModel, unassigned_shifts_per_event: list[IntVar], sum_squared_deviations: IntVar,
        unassigned_shifts_per_event_res: list[int], sum_squared_deviations_res: int):
    model.Add(sum(unassigned_shifts_per_event) == sum(unassigned_shifts_per_event_res))
    model.Add(sum_squared_deviations == sum_squared_deviations_res)


def solve_model_with_solver_solution_callback(
        model: cp_model.CpModel, shifts: dict[tuple[int, int], IntVar], unassigned_shifts_per_event: list[IntVar],
        sum_assigned_shifts: list[IntVar],
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
    solver.parameters.log_search_progress = False
    solver.parameters.linearization_level = 0
    solver.parameters.enumerate_all_solutions = False

    status = solver.Solve(model)

    return solver, status


def print_statistics(solver: cp_model.CpSolver, solution_printer: EmployeePartialSolutionPrinter | None,
                     unassigned_shifts_per_event: list[IntVar], sum_assigned_shifts: dict[UUID, IntVar],
                     sum_squared_deviations: IntVar):
    # Statistics.
    print("\nStatistics")
    print(f"  - conflicts      : {solver.NumConflicts()}")
    print(f"  - branches       : {solver.NumBranches()}")
    print(f"  - wall time      : {solver.WallTime()} s")
    print(f'  - ObjectiveValue : {solver.ObjectiveValue()}')
    if solution_printer:
        print(f"  - solutions found: {solution_printer.solution_count()}")
    print(f'{sum(solver.Value(u) for u in unassigned_shifts_per_event)=}')
    print(f'{[solver.Value(u) for u in unassigned_shifts_per_event]}')
    print(f'{solver.Value(sum_squared_deviations)=}')
    print(f'{sum(solver.Value(a) for a in sum_assigned_shifts.values())=}')


def print_solver_status(status: CpSolverStatus):
    if status == cp_model.OPTIMAL:
        print('########################### OPTIMAL ############################################')
    elif status == cp_model.FEASIBLE:
        print('########################### FEASIBLE ############################################')
    else:
        print('########################### FAILED ############################################')


def call_solver_with_unadjusted_requested_assignments() -> int:
    # Create the CP-SAT model.
    model = cp_model.CpModel()
    shifts = create_vars(model, events, avail_days)
    unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations = create_constraints(
        model, shifts, actor_plan_periods)
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


def main():
    assigned_shifts = call_solver_with_unadjusted_requested_assignments()
    sum_squared_deviations_res, unassigned_shifts_per_event_res, actor_plan_periods_adjusted = call_solver_with_adjusted_requested_assignments(assigned_shifts)
    call_solver_with__fixed_unassigned_shifts_fixed_squared_deviation(
        unassigned_shifts_per_event_res, sum_squared_deviations_res, actor_plan_periods_adjusted)


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    plan_period = db_services.PlanPeriod.get(PLAN_PERIOD_ID)
    actor_plan_periods = [db_services.ActorPlanPeriod.get(app.id) for app in plan_period.actor_plan_periods]
    avail_days = db_services.AvailDay.get_all_from__plan_period(PLAN_PERIOD_ID)
    events = db_services.Event.get_all_from__plan_period(PLAN_PERIOD_ID)
    main()
