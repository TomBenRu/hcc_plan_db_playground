from dataclasses import dataclass

from ortools.sat.python import cp_model


@dataclass
class Task1:
    name: str
    duration: int
    resource: str

@dataclass
class Task2:
    name: str
    durations: list[int]


"""
Scheduling mit mehreren Ressourcen
In realen Szenarien haben wir oft begrenzte Ressourcen (z.B. Maschinen, Arbeiter), 
die für verschiedene Aufgaben benötigt werden. Hier ist ein Beispiel:

In diesem Beispiel haben wir:

Zwei Maschinen (Machine 1 und Machine 2)
Fünf Aufgaben mit festen Zuordnungen zu Maschinen
Ein Constraint, dass keine Maschine zwei Aufgaben gleichzeitig bearbeiten kann
Eine einfache ASCII-Visualisierung hinzugefügt

Die wichtigste Neuerung ist die Organisation der Constraints nach Ressourcen: 
Wir erstellen für jede Ressource eine Liste von Intervallen 
und fügen dann einen NoOverlap-Constraint für jede dieser Listen hinzu.
"""


def multi_resource_scheduling_1():
    # Daten des Problems
    tasks = [
        Task1('Task A', 2, 'Machine 1'),
        Task1('Task B', 3, 'Machine 1'),
        Task1('Task C', 4, 'Machine 2'),
        Task1('Task D', 1, 'Machine 2'),
        Task1('Task E', 5, 'Machine 1'),
    ]

    # Modell erstellen
    model = cp_model.CpModel()
    horizon = sum(task.duration for task in tasks)

    # Variablen für Aufgaben
    task_intervals = {task.name: model.NewIntervalVar(
        model.NewIntVar(0, horizon, f'start_{task.name}'),
        task.duration,
        model.NewIntVar(0, horizon, f'end_{task.name}'),
        f'task_interval_{task.name}') for task in tasks}

    machine_to_intervals = {machine: [] for machine in set(task.resource for task in tasks)}
    for task in tasks:
        machine_to_intervals[task.resource].append(task_intervals[task.name])

    # Keine Überlappung auf derselben Maschine
    for intervals in machine_to_intervals.values():
        model.AddNoOverlap(intervals)

    # Zielfunktion: Minimiere die Gesamtdauer (Makespan)
    makespan = model.NewIntVar(0, horizon, 'makespan')
    model.AddMaxEquality(makespan, [task_intervals[task.name].EndExpr() for task in tasks])
    model.Minimize(makespan)

    # Lösung finden
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print('Optimaler Zeitplan gefunden:')
        for task in tasks:
            start = solver.Value(task_intervals[task.name].StartExpr())
            end = solver.Value(task_intervals[task.name].EndExpr())
            print(f'{task.name}: Start = {start}, Ende = {end}, Ressource = {task.resource}')
        print(f'Gesamtdauer (Makespan): {solver.Value(makespan)}')

        # Visualisierung als ASCII-Diagramm
        print("\nZeitplan-Visualisierung:")
        for machine, intervals in machine_to_intervals.items():
            print(f"{machine}: ", end="")
            timeline = ['.'] * (solver.Value(makespan) + 1)
            for interval in intervals:
                for t in range(solver.Value(interval.StartExpr()), solver.Value(interval.EndExpr())):
                    timeline[t] = interval.Name()[-1]  # Verwende letzten Buchstaben des Tasks als Marker
            print(''.join(timeline))
    else:
        print('Keine Lösung gefunden')


"""
Aufgabe 2
Erweitere das obige Beispiel:

Erlaube flexible Ressourcenzuordnung - jede Aufgabe kann auf beiden Maschinen ausgeführt werden
Füge unterschiedliche Bearbeitungszeiten für jede Aufgabe je nach Maschine hinzu
Minimiere weiterhin den Makespan

Deine Lösung sollte die Maschine für jede Aufgabe automatisch auswählen, um die Gesamtzeit zu minimieren.
"""


def multi_resource_scheduling_2():
    # Daten des Problems
    tasks = [
        Task2('Task A', [1, 4]),
        Task2('Task B', [2, 3]),
        Task2('Task C', [4, 6]),
        Task2('Task D', [3, 5]),
        Task2('Task E', [5, 2]),
    ]
    num_machines = len(tasks[0].durations)

    # Modell erstellen
    model = cp_model.CpModel()
    horizon = sum(max(task.durations) for task in tasks)

    # Variablen für Aufgaben
    task_intervals = {}
    for task in tasks:
        machine_vars = [model.NewBoolVar(f'machine_{machine}') for machine in range(1,num_machines + 1)]
        model.Add(sum(machine_vars) == 1)
        for machine_nr, duration in enumerate(task.durations, start=1):
            task_intervals[(task.name, f'Machine {machine_nr}')] = model.NewIntervalVar(
                model.NewIntVar(0, horizon, f'start_{task.name}_{machine_nr}'),
                duration * machine_vars[machine_nr - 1],
                model.NewIntVar(0, horizon, f'end_{task.name}_{machine_nr}'),
                f'task_interval_{task.name}_{machine_nr}')

    machine_to_intervals: dict[str, list[cp_model.IntervalVar]] = {f'Machine {machine}': []
                                                                   for machine in range(1, len(tasks[0].durations) + 1)}
    for (_, machine), task_interval in task_intervals.items():
        machine_to_intervals[machine].append(task_interval)

    # Keine Überlappung auf derselben Maschine
    for intervals in machine_to_intervals.values():
        model.AddNoOverlap(intervals)

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

        # Visualisierung als ASCII-Diagramm
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


# Ausführen des Beispiels
multi_resource_scheduling_2()