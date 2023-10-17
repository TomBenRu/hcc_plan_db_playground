from collections import defaultdict
import dataclasses
import datetime
from typing import Optional
from uuid import UUID

from ortools.sat.cp_model_pb2 import CpSolverStatus
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

from database import db_services, schemas


def generate_adjusted_requested_assignments(events: list['Event'], employees: list['Employee'],
                                            assigned_shifts: int) -> dict[int, float]:
    requested_assignments_adjusted = defaultdict(int)

    for i, employee in enumerate(employees):
        employee: 'Employee'
        for event in events:
            if event.date in employee.available:
                requested_assignments_adjusted[i] += 1
        requested_assignments_adjusted[i] = min(requested_assignments_adjusted[i], employee.requested_shifts)

    requested_assignments_new: dict[int: int] = {}
    avail_assignments: int = assigned_shifts
    while True:
        mean_nr_assignments: float = avail_assignments / len(requested_assignments_adjusted)
        requested_greater_than_mean: dict[int: int] = {}
        requested_smaller_than_mean: dict[int: int] = {}
        for i, requested in requested_assignments_adjusted.items():
            if requested >= mean_nr_assignments:
                requested_greater_than_mean[i] = requested
            else:
                requested_smaller_than_mean[i] = requested

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
    return requested_assignments_new


class EmployeePartialSolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, shifts, unassigned_shifts_per_event, num_employees, num_days, sum_assigned_shifts, sum_squared_deviations, limit):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self._shifts = shifts
        self._unassigned_shifts_per_event = unassigned_shifts_per_event
        self._num_employees = num_employees
        self._num_days = num_days
        self._solution_count = 0
        self._sum_assigned_shifts = sum_assigned_shifts
        self._sum_squared_deviations = sum_squared_deviations
        self._solution_limit = limit

    def on_solution_callback(self):
        self._solution_count += 1
        print(f"Solution {self._solution_count}")
        for d in range(self._num_days):
            print(f"Day {d}")
            for n in range(self._num_employees):
                is_working = False
                if self.Value(self._shifts[(n, d)]):
                    is_working = True
                    print(f"  Employee {n} works day {d}")
                if not is_working:
                    print(f"  Employee {n} does not work")
        print('unassigned_shifts_per_event:', [self.Value(unassigned_shifts) for unassigned_shifts in self._unassigned_shifts_per_event])
        print(f'sum_assigned_shifts_of_employees: {[self.Value(s) for s in self._sum_assigned_shifts]}')
        print(f'sum_squared_deviations: {self.Value(self._sum_squared_deviations)}')
        if self._solution_count >= self._solution_limit:
            print(f"Stop search after {self._solution_limit} solutions")
            self.StopSearch()

    def solution_count(self):
        return self._solution_count


events: defaultdict[tuple[datetime.date, int], list[schemas.EventShow]] = defaultdict(list)

avail_days: defaultdict[tuple[datetime.date, int], list[schemas.AvailDayShow]] = defaultdict(list)

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

        self.find_event()
        self.fill_child_groups()

    def find_event(self):
        self.event_of_event_group = db_services.Event.get(self.event_group.event.id) if self.event_group.event else None
        if self.event_of_event_group:
            events[
                (
                    self.event_of_event_group.date, self.event_of_event_group.time_of_day.time_of_day_enum.time_index
                )
            ].append(self.event_of_event_group)

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

        self.find_avail_day()
        self.fill_child_groups()

    def find_avail_day(self):
        self.avail_day_of_avail_day_group = db_services.AvailDay.get_from__avail_day_group(self.avail_day_group.id)
        if self.avail_day_of_avail_day_group:
            avail_days[
                (self.avail_day_of_avail_day_group.date,
                 self.avail_day_of_avail_day_group.time_of_day.time_of_day_enum.time_index)
            ].append(self.avail_day_of_avail_day_group)

    def fill_child_groups(self):
        for avail_day_group in db_services.AvailDayGroup.get_child_groups_from__parent_group(self.avail_day_group.id):
            self.child_groups.append(AvailDayGroupCast(avail_day_group, self))


class Datastructures:
    def __init__(self, plan_period_id: UUID):
        self._plan_period_id = plan_period_id
        self._plan_period = db_services.PlanPeriod.get(plan_period_id)
        self._location_plan_periods = self._plan_period.location_plan_periods
        self.main_event_groups = [db_services.EventGroup.get_master_from__location_plan_period(lpp.id)
                                  for lpp in self._location_plan_periods]


class Employee:
    def __init__(self, name: str, available: list[int], requested_shifts):
        self.name = name
        self.available = available
        self.requested_shifts = requested_shifts
        self.adjusted_requested_shifts: float = requested_shifts

    def set_adjusted_requested_shifts(self, adjusted_requested_shifts: float):
        self.adjusted_requested_shifts = round(adjusted_requested_shifts, 2)


@dataclasses.dataclass
class Event:
    name: str
    date: int
    nr_employees: int
    staff: list[Employee] = dataclasses.field(default_factory=list)


employees = [Employee('Tom', [2, 3, 4, 5, 6], 6),
             Employee('Jan', [2, 3, 4, 5, 6], 3),
             Employee('Gabi', [2, 3, 4, 5, 6], 2),
             Employee('Suse', [2, 3, 4, 5, 6], 2)]

events = [Event('Event 1', 2, 2), Event('Event 2', 3, 2), Event('Event 3', 3, 2), Event('Event 4', 5, 2),
          Event('Event 5', 6, 1)]


def create_vars(model: cp_model.CpModel, employees: list[employees]) -> dict[tuple[int, int], IntVar]:
    shifts = {}
    for e in range(len(employees)):
        for d in range(len(events)):
            model.NewBoolVar('')
            shifts[(e, d)] = model.NewBoolVar(f'shift {e, d}')
    return shifts


def create_constraints(model: cp_model.CpModel,
                       shifts: dict[tuple[int, int], IntVar]) -> tuple[list[IntVar], list[IntVar], IntVar]:
    # Add constraints for employee availability.
    for e in range(len(employees)):
        for d in range(len(events)):
            if events[d].date not in employees[e].available:
                model.Add(shifts[(e, d)] == 0)

    # Create a list to represent the number of unassigned shifts for each event.
    unassigned_shifts_per_event = [
        model.NewIntVar(0, sum(e.nr_employees for e in events), f'unassigned_shifts_event_{d}')
        for d in range(len(events))]

    # Add a constraint for each event that the number of assigned employees is at most the number of needed employees,
    # and update the number of unassigned shifts for each event.
    for d in range(len(events)):
        num_assigned_employees = sum(shifts[(e, d)] for e in range(len(employees)))
        model.Add(num_assigned_employees <= events[d].nr_employees)
        model.Add(unassigned_shifts_per_event[d] == events[d].nr_employees - num_assigned_employees)

    # Create a lists to represent the sums of assigned shifts and the relative shift deviations for each employee.
    sum_assigned_shifts = [model.NewIntVar(0, 1000, f'sum_assigned_shifts {e}') for e in range(len(employees))]
    relative_shift_deviations = [model.NewIntVar(-len(events)*100_000_000, len(events)*100_000_000,
                                                 f'relative_shift_deviation_{e}') for e in range(len(employees))]

    # Add a constraint for each employee that the relative shift deviation is equal to (requested shifts - actual shifts) / requested shifts.
    for e in range(len(employees)):
        model.AddAbsEquality(sum_assigned_shifts[e], sum(list(shifts[(e, d)] for d in range(len(events)))))
        model.AddDivisionEquality(
            relative_shift_deviations[e],
            sum_assigned_shifts[e] * 100_000 - int(employees[e].adjusted_requested_shifts * 100_000),
            int(employees[e].adjusted_requested_shifts * 100) if employees[e].adjusted_requested_shifts else 1)

    # Calculate the average of the relative shift deviations.
    average_relative_shift_deviation = model.NewIntVar(-len(events)*100_000_000, len(events)*100_000_000,
                                                       'average_relative_shift_deviation')
    sum_relative_shift_deviations = model.NewIntVar(-100_000_000, 100_000_000, 'sum_x')
    model.AddAbsEquality(sum_relative_shift_deviations, sum(relative_shift_deviations))
    model.AddDivisionEquality(average_relative_shift_deviation, sum_relative_shift_deviations, len(employees))

    # Create a list to represent the squared deviations from the average for each employee.
    squared_deviations = [model.NewIntVar(0, len(events)**2*1_000_000**2,
                                          f'squared_deviation_{e}') for e in range(len(employees))]

    # Add a constraint for each employee that the squared deviation is equal to (relative shift deviation - average)^2.
    dif_average__relative_shift_deviations = []
    for e in range(len(employees)):
        dif_average__relative_shift_deviations.append(model.NewIntVar(-100_000_000, 100_000_000,
                                                                      f'dif_average__relative_shift_deviation {e}'))
        model.AddAbsEquality(dif_average__relative_shift_deviations[-1],
                             relative_shift_deviations[e] - average_relative_shift_deviation)

        model.AddMultiplicationEquality(
            squared_deviations[e],
            [dif_average__relative_shift_deviations[-1], dif_average__relative_shift_deviations[-1]])

    # Add a constraint that the sum_squared_deviations is equal to the sum(squared_deviations).
    sum_squared_deviations = model.NewIntVar(0, 10**16, 'sum_squared_deviations')
    model.AddAbsEquality(sum_squared_deviations, sum(squared_deviations))

    return unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations


def define_objective_minimize(model: cp_model.CpModel, unassigned_shifts_per_event: list[IntVar],
                              sum_squared_deviations: IntVar):
    """Change the objective to minimize a weighted sum of the number of unassigned shifts
    and the sum of the squared deviations."""
    weight_unassigned_shifts = 100_000
    weight_sum_squared_shift_deviations = 0.001 / len(employees)
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
                                                      len(employees),
                                                      len(events), sum_assigned_shifts,
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
                     unassigned_shifts_per_event: list[IntVar], sum_assigned_shifts: list[IntVar],
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
    print(f'{solver.Value(sum_squared_deviations)=}')
    print(f'{sum(solver.Value(a) for a in sum_assigned_shifts)=}')


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
    shifts = create_vars(model, employees)
    unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations = create_constraints(
        model, shifts)
    define_objective_minimize(model, unassigned_shifts_per_event, sum_squared_deviations)
    solver, solver_status = solve_model_to_optimum(model)
    print_statistics(solver, None, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations)
    print_solver_status(solver_status)
    return sum(solver.Value(a) for a in sum_assigned_shifts)


def call_solver_with_adjusted_requested_assignments(assigned_shifts: int) -> tuple[int, list[int]]:
    print('+++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
    print([e.adjusted_requested_shifts for e in employees])
    adjusted_requested_assignments = generate_adjusted_requested_assignments(
        events, employees, assigned_shifts)
    for i, adjusted_requested_assignment in adjusted_requested_assignments.items():
        employees[i].set_adjusted_requested_shifts(adjusted_requested_assignment)
    print([e.adjusted_requested_shifts for e in employees])

    # Create the CP-SAT model.
    model = cp_model.CpModel()
    shifts = create_vars(model, employees)
    unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations = create_constraints(
        model, shifts)
    define_objective_minimize(model, unassigned_shifts_per_event, sum_squared_deviations)
    solver, solver_status = solve_model_to_optimum(model)
    print_statistics(solver, None, unassigned_shifts_per_event,
                     sum_assigned_shifts, sum_squared_deviations)
    print_solver_status(solver_status)
    return solver.Value(sum_squared_deviations), [solver.Value(u) for u in unassigned_shifts_per_event]


def call_solver_with__fixed_unassigned_shifts_fixed_squared_deviation(unassigned_shifts_per_event_res: list[int],
                                                                      sum_squared_deviations_res: int):
    # Create the CP-SAT model.
    model = cp_model.CpModel()
    shifts = create_vars(model, employees)
    unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations = create_constraints(
        model, shifts)
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
    sum_squared_deviations_res, unassigned_shifts_per_event_res = call_solver_with_adjusted_requested_assignments(assigned_shifts)
    call_solver_with__fixed_unassigned_shifts_fixed_squared_deviation(
        unassigned_shifts_per_event_res, sum_squared_deviations_res)


if __name__ == '__main__':
    main()
