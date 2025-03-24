from ortools.sat.python import cp_model


def simple_scheduling(min_makespan: bool = False, min_average_completion_time: bool = True):
    # Daten des Problems
    tasks = ['Task A', 'Task B', 'Task C', 'Task D', 'Task E']
    durations = [2, 3, 4, 1, 5]  # Stunden

    # Horizont berechnen
    horizon = 100
    max_sum_completion = horizon * len(tasks)

    # Modell erstellen
    model = cp_model.CpModel()

    # Variablen
    task_intervals = {
        task: model.NewIntervalVar(
            model.NewIntVar(0, horizon, f'start_{task}'),
            duration,
            model.NewIntVar(0, horizon, f'end_{task}'),
            f'task_interval_{task}')
        for task, duration in zip(tasks, durations)
    }

    # Keine Überlappung: Aufgaben müssen nacheinander ausgeführt werden
    model.AddNoOverlap(task_intervals.values())

    # Variablen für Ausgabe
    makespan = None
    average_completion_time = None

    if min_makespan:
        # Zielfunktion: Minimiere die Gesamtdauer (Makespan)
        makespan = model.NewIntVar(0, horizon, 'makespan')
        model.AddMaxEquality(makespan, [task_interval.EndExpr() for task_interval in task_intervals.values()])
        model.Minimize(makespan)

    if min_average_completion_time:
        # Zielfunktion: Minimiere die durchschnittliche Fertigstellungszeit
        sum_completion_time = model.NewIntVar(0, max_sum_completion, 'sum_completion_time')
        model.Add(sum_completion_time == sum(task_interval.EndExpr() for task_interval in task_intervals.values()))

        # Optional: Durchschnitt berechnen
        average_completion_time = model.NewIntVar(0, horizon, 'average_completion_time')
        model.AddDivisionEquality(average_completion_time, sum_completion_time, len(tasks))

        # Wir können direkt die Summe minimieren, das ergibt das gleiche Ergebnis
        model.Minimize(sum_completion_time)

    # Lösung finden
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print('Optimaler Zeitplan gefunden:')
        for task in tasks:
            start = solver.Value(task_intervals[task].StartExpr())
            end = solver.Value(task_intervals[task].EndExpr())
            print(f'{task}: Start = {start}, Ende = {end}')

        if min_makespan:
            print(f'Gesamtdauer (Makespan): {solver.Value(makespan)}')
        if min_average_completion_time:
            print(f'Durchschnittliche Fertigstellungszeit: {solver.Value(average_completion_time)}')
    else:
        print('Keine Lösung gefunden')


simple_scheduling(min_makespan=False, min_average_completion_time=True)