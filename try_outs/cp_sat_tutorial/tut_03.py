from dataclasses import dataclass

from ortools.sat.python import cp_model

@dataclass
class Task:
    name: str
    durations_with_machine: list[int]
    start_between: tuple[int, int | None]
    end_between: tuple[int, int | None]


def multi_resource_scheduling():
    # Daten des Problems
    tasks = [
        Task('Task A', [2, 4], (0, None), (0, None)),
        Task('Task B', [3, 5], (10, 15), (15, None)),
        Task('Task C', [4, 6], (0, None), (5, 7)),
        Task('Task D', [1, 3], (0, None), (0, None)),
        Task('Task E', [5, 2], (0, None), (0, 12)),
    ]
    num_machines = len(tasks[0].durations_with_machine)

    starts_after_completion = {
        'Task B': ['Task A', 'Task C', 'Task D', 'Task E'],
        'Task D': ['Task C'],
        'Task E': ['Task D'],
    }

    # Modell erstellen
    model = cp_model.CpModel()
    horizon = sum(task.end_between[0] + max(task.durations_with_machine) for task in tasks)

    # Variablen für Aufgaben
    task_intervals = {}
    for task in tasks:
        machine_vars = [model.NewBoolVar(f'machine_{machine}') for machine in range(1,num_machines + 1)]
        model.Add(sum(machine_vars) == 1)
        for machine_nr, duration in enumerate(task.durations_with_machine, start=1):
            task_intervals[(task.name, f'Machine {machine_nr}')] = model.NewIntervalVar(
                model.NewIntVar(
                    task.start_between[0], task.start_between[1] if task.start_between[1] else horizon,
                    f'start_{task.name}_{machine_nr}'
                ),
                duration * machine_vars[machine_nr - 1],
                model.NewIntVar(
                    task.end_between[0], task.end_between[1] if task.end_between[1] else horizon,
                    f'end_{task.name}_{machine_nr}'
                ),
                f'task_interval_{task.name}_{machine_nr}')

    machine_to_intervals: dict[str, list[cp_model.IntervalVar]] = {
        f'Machine {machine}': [] for machine in range(1, len(tasks[0].durations_with_machine) + 1)
    }
    for (_, machine), task_interval in task_intervals.items():
        machine_to_intervals[machine].append(task_interval)

    # Keine Überlappung auf derselben Maschine
    for intervals in machine_to_intervals.values():
        model.AddNoOverlap(intervals)

    # Tasks müssen nacheinander ausgeführt werden
    for task_after, tasks_before in starts_after_completion.items():
        for task_before in tasks_before:
            # Für task_before: Finde die tatsächliche End-Zeit über alle möglichen Maschinen
            task_before_end_times = []
            for machine in range(1, num_machines + 1):
                interval = task_intervals[(task_before, f'Machine {machine}')]
                is_active = model.NewBoolVar(f'{task_before}_{machine}_is_active')
                model.Add(interval.SizeExpr() > 0).OnlyEnforceIf(is_active)
                model.Add(interval.SizeExpr() == 0).OnlyEnforceIf(is_active.Not())
                task_before_end_times.append(model.NewIntVar(0, horizon, 'end_time'))
                model.Add(task_before_end_times[-1] == interval.EndExpr()).OnlyEnforceIf(is_active)
                model.Add(task_before_end_times[-1] == 0).OnlyEnforceIf(is_active.Not())
            
            actual_end = model.NewIntVar(0, horizon, f'{task_before}_actual_end')
            model.AddMaxEquality(actual_end, task_before_end_times)

            # Für task_after: Finde die tatsächliche Start-Zeit über alle möglichen Maschinen
            task_after_start_times = []
            for machine in range(1, num_machines + 1):
                interval = task_intervals[(task_after, f'Machine {machine}')]
                is_active = model.NewBoolVar(f'{task_after}_{machine}_is_active')
                model.Add(interval.SizeExpr() > 0).OnlyEnforceIf(is_active)
                model.Add(interval.SizeExpr() == 0).OnlyEnforceIf(is_active.Not())
                task_after_start_times.append(model.NewIntVar(0, horizon, 'start_time'))
                model.Add(task_after_start_times[-1] == interval.StartExpr()).OnlyEnforceIf(is_active)
                model.Add(task_after_start_times[-1] == horizon).OnlyEnforceIf(is_active.Not())

            actual_start = model.NewIntVar(0, horizon, f'{task_after}_actual_start')
            model.AddMinEquality(actual_start, task_after_start_times)

            # Erzwinge die Reihenfolge
            model.Add(actual_end <= actual_start)

    # Zielfunktion: Minimiere die Gesamtdauer (Makespan)
    makespan = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(makespan, [task_interval.EndExpr() for task_interval in task_intervals.values()])
    model.Minimize(makespan)

    # Lösung finden
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print('Optimaler Zeitplan gefunden:')
        for task_interval in task_intervals.values():
            if not solver.Value(task_interval.SizeExpr()):
                continue
            start = solver.Value(task_interval.StartExpr())
            end = solver.Value(task_interval.EndExpr())
            print(f'{task_interval.name}: Start = {start}, Ende = {end}')
        print(f'Gesamtdauer (Makespan): {solver.Value(makespan)}')
        print("\nZeitplan-Visualisierung:")

        for machine, intervals in machine_to_intervals.items():
            print(f"{machine}: ", end="")
            timeline = ['.'] * (solver.Value(makespan) + 1)
            for interval in intervals:
                for t in range(solver.Value(interval.StartExpr()), solver.Value(interval.EndExpr())):
                    timeline[t] = interval.Name()[-3]  # Verwende letzten Buchstaben des Tasks als Marker
            print(''.join(timeline))
    else:
        print('Keine Lösung gefunden')

multi_resource_scheduling()
