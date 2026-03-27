"""
Profiling-Skript für die Plan-Validierung (registry.validate_plan).

Misst die Zeit jedes einzelnen Constraints sowie Plan.get() und zeigt
per-Zeilen-Profiling für die langsamsten Constraint-Implementierungen.

Ausführen:
    uv run python scripts/profile_plan_validation.py
    uv run python scripts/profile_plan_validation.py --plan-period-start 2026-06-01
    uv run python scripts/profile_plan_validation.py --team "Baden-Württemberg"
    uv run python scripts/profile_plan_validation.py --output profile_validation.txt
    uv run python scripts/profile_plan_validation.py --top 3

Das Skript:
1. Sucht automatisch einen Plan mit Appointments in der gewählten Planperiode
2. Lädt Entities synchron (wie WorkerLoadEntities)
3. Misst die Zeit jedes Constraints einzeln mit time.perf_counter
4. Profiliert die N langsamsten Constraints mit line_profiler (Zeilen-Ebene)
5. Gibt sortierte Gesamtübersicht aus

Profilierte Bereiche:
  Plan-Laden:     db_services.Plan.get + plan_show_options eager-loading
  Entities:       get_event_group_tree, get_avail_day_group_tree, ...
  Validierung:    jeder validate_plan() Call einzeln (per constraint)
"""

import argparse
import datetime
import io
import os
import sys
import time

# Windows-Terminal: UTF-8 für Umlaute
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# ── Sys-Path für Projekt-Imports ──────────────────────────────────────────────
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ── Argumente ──────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description='Plan-Validierung profilen')
parser.add_argument('--plan-period-start', default='2026-06-01',
                    help='Start-Datum der Planperiode (Standard: 2026-06-01)')
parser.add_argument('--team', default='Baden-Württemberg',
                    help='Team-Name (Standard: Baden-Württemberg)')
parser.add_argument('--output', default=None,
                    help='Ausgabe-Datei (Standard: stdout)')
parser.add_argument('--top', type=int, default=3,
                    help='Anzahl der langsamsten Constraints für line_profiler (Standard: 3)')
args = parser.parse_args()

# ── line_profiler importieren ──────────────────────────────────────────────────
try:
    from line_profiler import LineProfiler
except ImportError:
    print("FEHLER: line_profiler nicht installiert.")
    print("Installation: uv add line-profiler --dev")
    sys.exit(1)

# Qt-Dummy damit PySide6-Imports nicht abstürzen
import platform
if platform.system() == 'Windows':
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ── Projekt-Imports ────────────────────────────────────────────────────────────
from database import db_services
from database.db_services import plan_period as pp_svc
from sat_solver.event_group_tree import EventGroupTree
from sat_solver.avail_day_group_tree import AvailDayGroupTree
from sat_solver.cast_group_tree import get_cast_group_tree
from sat_solver.data_loading import (
    create_data_models,
    preload_avail_days,
    populate_shifts_exclusive,
)
from sat_solver.constraints import ConstraintRegistry
from sat_solver.constraints.base import Validatable

# ── Planperiode suchen ─────────────────────────────────────────────────────────
try:
    target_start = datetime.date.fromisoformat(args.plan_period_start)
except ValueError:
    print(f"FEHLER: Ungültiges Datum '{args.plan_period_start}'. Format: YYYY-MM-DD")
    sys.exit(1)

print(f"\nSuche Planperiode: Start={target_start}, Team='{args.team}'")
print("=" * 70)

plan_period = None
all_active = []
for project in db_services.Project.get_all():
    for pp in db_services.PlanPeriod.get_all_from__project(project.id):
        if pp.prep_delete:
            continue
        all_active.append(pp)
        if pp.start == target_start and args.team.lower() in pp.team.name.lower():
            plan_period = pp
            break
    if plan_period:
        break

if plan_period is None:
    print("FEHLER: Keine Planperiode gefunden.")
    print("  Verfügbare aktive Perioden:")
    for pp in sorted(all_active, key=lambda x: x.start):
        print(f"    {pp.start} – {pp.end}  [Team: {pp.team.name}]")
    sys.exit(1)

print(f"  Team:     {plan_period.team.name}")
print(f"  Periode:  {plan_period.start} – {plan_period.end}")

# ── Plan mit Appointments suchen ───────────────────────────────────────────────
plans = db_services.Plan.get_all_from__plan_period(plan_period.id)
plan = next((p for p in plans if p.appointments), None)

if plan is None:
    print(f"\nFEHLER: Kein Plan mit Appointments in Periode {plan_period.start} gefunden.")
    print(f"  Pläne in dieser Periode: {len(plans)} (alle ohne Appointments)")
    sys.exit(1)

print(f"  Plan:     '{plan.name}'")
print(f"  Appointments: {len(plan.appointments)}")
print(f"  AvailDays gesamt: {sum(len(a.avail_days) for a in plan.appointments)}")
print()

plan_id = plan.id

# ── Phase A: Plan.get() timing ─────────────────────────────────────────────────
print("Phase A: Plan.get() (mit eager-loading)...")
t_plan_get = time.perf_counter()
plan_fresh = db_services.Plan.get(plan_id)
t_plan_get_end = time.perf_counter()
plan_get_ms = (t_plan_get_end - t_plan_get) * 1000
print(f"  Plan.get():  {plan_get_ms:.1f} ms")
print()

# ── Phase B: Entities laden ────────────────────────────────────────────────────
print("Phase B: Entities laden...")
t_ent = time.perf_counter()

lpp_ids, app_ids = pp_svc.get_lpp_and_app_ids(plan_period.id)
t_lpp = time.perf_counter()
print(f"  get_lpp_and_app_ids:       {(t_lpp - t_ent) * 1000:.1f} ms")

event_group_tree = EventGroupTree(lpp_ids)
t_egt = time.perf_counter()
print(f"  EventGroupTree:            {(t_egt - t_lpp) * 1000:.1f} ms")

avail_day_group_tree = AvailDayGroupTree(app_ids)
t_adgt = time.perf_counter()
print(f"  AvailDayGroupTree:         {(t_adgt - t_egt) * 1000:.1f} ms")

cast_group_tree = get_cast_group_tree(plan_period.id)
t_cgt = time.perf_counter()
print(f"  get_cast_group_tree:       {(t_cgt - t_adgt) * 1000:.1f} ms")

entities = create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period.id)
t_cdm = time.perf_counter()
print(f"  create_data_models:        {(t_cdm - t_cgt) * 1000:.1f} ms")

preload_avail_days(entities)
populate_shifts_exclusive(entities)
t_ent_end = time.perf_counter()
print(f"  preload+populate:          {(t_ent_end - t_cdm) * 1000:.1f} ms")
print(f"  GESAMT Entities:           {(t_ent_end - t_ent) * 1000:.1f} ms")
print()

# ── Phase C: Einzelne Constraint-Zeiten messen ────────────────────────────────
print("Phase C: validate_plan() je Constraint...")
print("-" * 70)

registry = ConstraintRegistry(entities)
registry.register_plan_test_constraints()

validatable_constraints = [c for c in registry._constraints if isinstance(c, Validatable)]
print(f"  Registrierte Constraints mit validate_plan(): {len(validatable_constraints)}")
print()

constraint_times: list[tuple[float, str, object]] = []

for constraint in validatable_constraints:
    t0 = time.perf_counter()
    results = constraint.validate_plan(plan_fresh)
    t1 = time.perf_counter()
    elapsed_ms = (t1 - t0) * 1000
    n_errors = sum(1 for r in results if not hasattr(r, 'is_info') or not r.is_info)
    constraint_times.append((elapsed_ms, constraint.name, constraint))
    print(f"  {constraint.name:<40} {elapsed_ms:8.1f} ms   ({len(results)} Ergebnisse)")

constraint_times.sort(reverse=True)
total_validation_ms = sum(ms for ms, _, _ in constraint_times)

print("-" * 70)
print(f"  {'GESAMT validate_plan()':<40} {total_validation_ms:8.1f} ms")
print()

# ── Phase D: Gesamtzeit ────────────────────────────────────────────────────────
gesamtzeit_ms = plan_get_ms + (t_ent_end - t_ent) * 1000 + total_validation_ms
print("=" * 70)
print("  GESAMTBILD (Plan.get + Entities + Validation)")
print("=" * 70)
print(f"  Plan.get():          {plan_get_ms:8.1f} ms  ({plan_get_ms/gesamtzeit_ms*100:5.1f}%)")
ent_ms = (t_ent_end - t_ent) * 1000
print(f"  Entities laden:      {ent_ms:8.1f} ms  ({ent_ms/gesamtzeit_ms*100:5.1f}%)")
print(f"  validate_plan():     {total_validation_ms:8.1f} ms  ({total_validation_ms/gesamtzeit_ms*100:5.1f}%)")
print(f"  ─────────────────────────────────")
print(f"  GESAMT:              {gesamtzeit_ms:8.1f} ms")
print()

# ── Phase E: line_profiler für die N langsamsten Constraints ──────────────────
top_n = min(args.top, len(constraint_times))
print(f"Phase E: line_profiler für die {top_n} langsamsten Constraints...")
print("=" * 70)

profiler = LineProfiler()
for _, name, constraint in constraint_times[:top_n]:
    profiler.add_function(constraint.validate_plan)
    print(f"  Profiliere: {name}")
print()

# Alle top-N Constraints nochmals ausführen unter dem Profiler
for _, name, constraint in constraint_times[:top_n]:
    constraint.validate_plan = profiler(constraint.validate_plan)

for _, name, constraint in constraint_times[:top_n]:
    constraint.validate_plan(plan_fresh)

# ── Ausgabe ────────────────────────────────────────────────────────────────────
result_header = (
    f"Profiling plan_validation – {datetime.datetime.now().isoformat()}\n"
    f"Plan:        '{plan_fresh.name}'\n"
    f"Planperiode: {plan_period.start} – {plan_period.end}  [{plan_period.team.name}]\n"
    f"Appointments: {len(plan_fresh.appointments)} | "
    f"AvailDays: {sum(len(a.avail_days) for a in plan_fresh.appointments)}\n\n"
    f"Zeiten je Constraint (sortiert):\n"
)
for ms, name, _ in constraint_times:
    pct = ms / total_validation_ms * 100 if total_validation_ms > 0 else 0
    result_header += f"  {name:<40} {ms:8.1f} ms  ({pct:5.1f}%)\n"
result_header += f"\n{'GESAMT validate_plan()':<40} {total_validation_ms:8.1f} ms\n\n"

buf = io.StringIO()
profiler.print_stats(stream=buf, output_unit=1e-3)
line_profiler_output = buf.getvalue()

print(result_header)
print(line_profiler_output)

if args.output:
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(result_header)
        f.write(line_profiler_output)
    print(f"Ergebnis gespeichert in: {args.output}")

# ── Empfehlungen ───────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("  INTERPRETATION")
print("=" * 70)
print()
print(f"  Langsamste Constraints:")
for ms, name, _ in constraint_times[:5]:
    pct = ms / total_validation_ms * 100 if total_validation_ms > 0 else 0
    bar = '█' * int(pct / 2)
    print(f"  {name:<40} {ms:7.1f} ms  {pct:5.1f}%  {bar}")
print()
print("  Richtwerte:")
print("  > 500ms  pro Constraint → dringend optimieren")
print("  > 100ms  pro Constraint → Optimierung empfohlen")
print("  <  50ms  pro Constraint → akzeptabel")