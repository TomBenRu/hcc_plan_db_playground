from ortools.sat.python import cp_model
from datetime import time

def time_to_minutes(t): return t.hour * 60 + t.minute
def minutes_to_time(m): return time(hour=m // 60, minute=m % 60)

# Mitarbeiter mit ihren Arbeitszeiten
# employees = {
#     'Anna': {'start': time(9, 0), 'end': time(13, 0)},
#     'Bob': {'start': time(14, 0), 'end': time(16, 0)},
#     'Charlie': {'start': time(8, 0), 'end': time(13, 0)},
#     'David': {'start': time(11, 0), 'end': time(17, 0)}
# }
employees = {
    'Anna': {'start': time(10, 0), 'end': time(12, 0)},
    'Bob': {'start': time(10, 0), 'end': time(12, 0)},
    'Charlie': {'start': time(10, 0), 'end': time(15, 0)},
    'David': {'start': time(10, 0), 'end': time(15, 0)}
}

events = [
    {'name': "Meeting 1", 'duration': 60, 'earliest_start': time(9, 30), 'latest_end': time(13, 30)},
    {'name': "Workshop", 'duration': 120, 'earliest_start': time(10, 0), 'latest_end': time(15, 0)},
    {'name': "Präsentation", 'duration': 30, 'earliest_start': time(13, 0), 'latest_end': time(16, 0)},
    {'name': "Review", 'duration': 60, 'earliest_start': time(14, 0), 'latest_end': time(17, 0)}
]

model = cp_model.CpModel()

# Variablen für jedes Event
event_intervals = {}  # event_id -> interval
event_starts = {}    # event_id -> start_time
event_ends = {}      # event_id -> end_time
event_presence = {}  # event_id -> presence

# Erstelle Event-Variablen
for i, event in enumerate(events):
    start_min = time_to_minutes(event['earliest_start'])
    end_max = time_to_minutes(event['latest_end'])
    duration = event['duration']
    
    start = model.NewIntVar(start_min, end_max - duration, f'start_{i}')
    end = model.NewIntVar(start_min + duration, end_max, f'end_{i}')
    
    event_starts[i] = start
    event_ends[i] = end

    # Erstelle Interval für dieses Event. Die einzelnen Events dürfen überlappen.
    event_intervals[i] = model.NewIntervalVar(start, duration, end, f'interval_{i}')

# Mitarbeiter-Zuweisungen
assignments = {}  # (employee, event_id) -> bool_var
employee_intervals = {emp: [] for emp in employees}

for emp_name, work_hours in employees.items():
    emp_start = time_to_minutes(work_hours['start'])
    emp_end = time_to_minutes(work_hours['end'])
    
    for event_id in range(len(events)):
        # Zuweisungsvariable für diesen Mitarbeiter und dieses Event
        assignment = model.NewBoolVar(f'assignment_{emp_name}_{event_id}')
        assignments[(emp_name, event_id)] = assignment
        
        # Event muss innerhalb der Arbeitszeit des Mitarbeiters liegen
        model.Add(event_starts[event_id] >= emp_start).OnlyEnforceIf(assignment)
        model.Add(event_ends[event_id] <= emp_end).OnlyEnforceIf(assignment)
        
        # Erstelle Interval für diesen Mitarbeiter; für jedes Event gibt es einen Interval für jeden Mitarbeiter;
        # wird aktiviert, wenn der Mitarbeiter dem Event zugewiesen ist
        interval = model.NewOptionalIntervalVar(
            event_starts[event_id], 
            events[event_id]['duration'],
            event_ends[event_id],
            assignment,
            f'interval_{emp_name}_{event_id}'
        )
        employee_intervals[emp_name].append(interval)

# Keine Überlappung für jeden Mitarbeiter
for emp_intervals in employee_intervals.values():
    model.AddNoOverlap(emp_intervals)

# Möglichst 2 Mitarbeiter pro Event (wenn es stattfindet)
for event_id in range(len(events)):
    event_assignments = [assignments[(emp, event_id)] for emp in employees]
    model.Add(sum(event_assignments) <= 2)

# Maximiere die Anzahl der Zuweisungen
model.Maximize(sum(assignments.values()))

# Löse das Modell
solver = cp_model.CpSolver()
status = solver.solve(model)

if status == cp_model.OPTIMAL:
    print("\nOptimale Lösung gefunden:")
    print(f"Gesamtzahl Zuweisungen: {solver.ObjectiveValue()}\n")
    
    for event_id, event in enumerate(events):
        start_time = minutes_to_time(solver.Value(event_starts[event_id]))
        end_time = minutes_to_time(solver.Value(event_ends[event_id]))
        print(f"\n{event['name']}:")
        print(f"  Zeit: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        print("  Zugewiesene Mitarbeiter:")
        for emp_name in employees:
            if solver.Value(assignments[(emp_name, event_id)]):
                print(f"    - {emp_name}")
        print("  Anzahl fehlender Mitarbeiter:", 2 - sum(solver.Value(assignments[(emp_name, event_id)])
                                                             for emp_name in employees))
else:
    print("Keine optimale Lösung gefunden!")
print("\nSolver Status:", status)