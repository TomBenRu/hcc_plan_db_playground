"""
Profiling-Skript für FrmLocationPlanPeriod.change_mode__event_group.

Misst die Zeit je Codezeile für:
  Phase 1 — Dialog-Initialisierung:
               DlgGroupModeBuilderLocationPlanPeriod._generate_field_values
                 → get_flat_tree_for_dialog__location_plan_period (neu, 2 Roundtrips)
               DlgGroupMode.__init__ → TreeWidget.setup_tree
                 → get_child_groups_from__parent_group (alt, Soll: 0 Hits nach Opt.)
               TreeWidgetItem.calculate_earliest_date_object (Sort-Overhead)

  Phase 2 — refresh_tree (= Verhalten bei Cancel / delete_unused_groups):
               DlgGroupModeBuilderLocationPlanPeriod.reload_object_with_groups
                 → get_flat_tree_for_dialog__location_plan_period
               TreeWidget.setup_tree (erneuter Aufruf mit frischem Cache)

Daten: Team Mainz, PlanPeriod.start 01.06.2026

Ausführen:
    uv run python scripts/profile_event_group_dialog.py
    uv run python scripts/profile_event_group_dialog.py --phase 1   # nur Dialog-Init
    uv run python scripts/profile_event_group_dialog.py --phase 2   # nur refresh_tree

Auswertung:
  Hits > 0 bei get_child_groups_from__parent_group  →  Cache greift nicht
  % Time > 20% bei get_flat_tree_for_dialog...      →  DB Bottleneck (CTE + Batch-Load)
  % Time > 20% bei model_validate                   →  Pydantic Bottleneck
  % Time > 20% bei calculate_earliest_date_object   →  Sort-Overhead (nutzt Cache)
"""

import argparse
import datetime
import os
import platform
import sys
import time

# Windows-Terminal: UTF-8 für Umlaute
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Projekt-Root in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ── Ziel-Daten ────────────────────────────────────────────────────────────────
TARGET_START = datetime.date(2026, 6, 1)
TARGET_TEAM = "Mainz"

# ── Argumente ─────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description='change_mode__event_group profilen')
parser.add_argument('--phase', choices=['1', '2', 'both'], default='both',
                    help='Welche Phase profilen: 1=Dialog-Init, 2=refresh_tree, both=alle (Standard: both)')
args = parser.parse_args()

# ── Qt-Setup ──────────────────────────────────────────────────────────────────
if platform.system() == 'Windows':
    os.environ['QT_QPA_PLATFORM'] = 'windows:darkmode=2'
    os.environ['QT_STYLE_OVERRIDE'] = 'Fusion'

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

# Screen-Größe setzen, damit resize_dialog() nicht auf None - int trifft
from tools.screen import Screen  # noqa: E402
Screen.set_screen_size()

# ── line_profiler ─────────────────────────────────────────────────────────────
try:
    from line_profiler import LineProfiler
except ImportError:
    print("FEHLER: line_profiler nicht installiert.")
    print("Installation: uv add line-profiler --dev")
    sys.exit(1)

# ── Projekt-Imports ───────────────────────────────────────────────────────────
from database import db_services  # noqa: E402
import gui.frm_group_mode as frm_group_mode_module  # noqa: E402
from gui.frm_group_mode import (  # noqa: E402
    DlgGroupMode,
    DlgGroupModeBuilderLocationPlanPeriod,
    TreeWidget,
    TreeWidgetItem,
)
from gui.frm_location_plan_period import (  # noqa: E402
    FrmTabLocationPlanPeriods,
    FrmLocationPlanPeriod,
)

# ── Planungsperiode finden ────────────────────────────────────────────────────
print(f"Suche PlanPeriod '{TARGET_START}' für Team '{TARGET_TEAM}'...")
t0 = time.perf_counter()

projects = db_services.Project.get_all()
if not projects:
    print("FEHLER: Keine Projekte in der Datenbank gefunden.")
    sys.exit(1)

plan_period = None
all_active: list = []
for project in projects:
    for pp in db_services.PlanPeriod.get_all_from__project(project.id):
        if pp.prep_delete:
            continue
        all_active.append(pp)
        if pp.start == TARGET_START and TARGET_TEAM.lower() in pp.team.name.lower():
            plan_period = pp
            break
    if plan_period:
        break

if plan_period is None:
    print(f"FEHLER: Keine PlanPeriod für Team '{TARGET_TEAM}' mit Start {TARGET_START} gefunden.")
    print("  Verfügbare aktive Perioden:")
    for pp in all_active:
        print(f"    {pp.start} – {pp.end}  [Team: {pp.team.name}]")
    sys.exit(1)

print(f"  Team:       {plan_period.team.name}")
print(f"  PlanPeriod: {plan_period.start} – {plan_period.end}")
print(f"  Ladezeit:   {(time.perf_counter() - t0) * 1000:.1f} ms\n")

# ── Tab-Widget aufbauen ───────────────────────────────────────────────────────
print("-" * 70)
print("Vorbereitung: FrmTabLocationPlanPeriods aufbauen...")
t_tab = time.perf_counter()
try:
    tab_widget = FrmTabLocationPlanPeriods(None, plan_period)
except Exception as e:
    print(f"FEHLER beim Aufbau von FrmTabLocationPlanPeriods: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
print(f"  Tab-Init: {(time.perf_counter() - t_tab) * 1000:.1f} ms")

location_id = next(iter(tab_widget.location_id__location_pp), None)
if location_id is None:
    print("FEHLER: Keine Location-PlanPeriod in dieser Planungsperiode.")
    sys.exit(1)

print(f"  data_setup für Location-ID: {location_id}...")
t_ds = time.perf_counter()
try:
    tab_widget.data_setup(location_id=location_id)
except Exception as e:
    print(f"FEHLER in data_setup: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

lpp_widget: FrmLocationPlanPeriod = tab_widget.frame_events
if lpp_widget is None:
    print("FEHLER: frame_events ist None nach data_setup.")
    sys.exit(1)

location_plan_period = lpp_widget.location_plan_period
print(f"  Standort:   {location_plan_period.location_of_work.name}")
print(f"  data_setup: {(time.perf_counter() - t_ds) * 1000:.1f} ms\n")

# Schnell-Check: Wie viele EventGroups gibt es?
t_eg = time.perf_counter()
master, eg_cache = db_services.EventGroup.get_flat_tree_for_dialog__location_plan_period(
    location_plan_period.id)
total_nodes = 1 + sum(len(v) for v in eg_cache.values()) if master else 0
n_leaf = sum(
    1 for children in eg_cache.values()
    for child in children
    if child.event is not None
)
n_internal = total_nodes - n_leaf - (1 if master else 0)
print(f"  EventGroup-Baum: {total_nodes} Knoten total")
print(f"    Master: 1, Intermediate: {n_internal}, Blätter: {n_leaf}")
print(f"  Vorbau-Ladezeit: {(time.perf_counter() - t_eg) * 1000:.1f} ms\n")


# ── Hilfsfunktion ─────────────────────────────────────────────────────────────
def print_results(profiler: LineProfiler, title: str) -> None:
    print("=" * 70)
    print(f"  PROFILING: {title}")
    print("=" * 70)
    profiler.print_stats(output_unit=1e-3)  # Zeiten in ms
    print()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Dialog-Initialisierung
# ══════════════════════════════════════════════════════════════════════════════

if args.phase in ('1', 'both'):
    print("-" * 70)
    print("PHASE 1: DlgGroupModeBuilderLocationPlanPeriod + DlgGroupMode.__init__")
    print("  (= Öffnen des Dialogs in change_mode__event_group)")
    print("-" * 70)

    profiler1 = LineProfiler()

    # Dialog-Klassen
    profiler1.add_function(DlgGroupModeBuilderLocationPlanPeriod._generate_field_values)
    profiler1.add_function(DlgGroupModeBuilderLocationPlanPeriod.reload_object_with_groups)
    profiler1.add_function(DlgGroupMode.__init__)
    profiler1.add_function(TreeWidget.setup_tree)
    profiler1.add_function(TreeWidgetItem.calculate_earliest_date_object)

    # DB-Services: neu (Soll: 2–3 Hits) vs alt (Soll: 0 Hits nach Optimierung)
    profiler1.add_function(db_services.EventGroup.get_flat_tree_for_dialog__location_plan_period)
    profiler1.add_function(db_services.EventGroup.get_child_groups_from__parent_group)
    profiler1.add_function(db_services.EventGroup.get_master_from__location_plan_period)

    # Methoden patchen
    DlgGroupModeBuilderLocationPlanPeriod._generate_field_values = profiler1(
        DlgGroupModeBuilderLocationPlanPeriod._generate_field_values)
    DlgGroupModeBuilderLocationPlanPeriod.reload_object_with_groups = profiler1(
        DlgGroupModeBuilderLocationPlanPeriod.reload_object_with_groups)
    DlgGroupMode.__init__ = profiler1(DlgGroupMode.__init__)
    TreeWidget.setup_tree = profiler1(TreeWidget.setup_tree)
    TreeWidgetItem.calculate_earliest_date_object = profiler1(
        TreeWidgetItem.calculate_earliest_date_object)

    # DB-Services patchen (Modul-Funktionen über db_services alias)
    db_services.EventGroup.get_flat_tree_for_dialog__location_plan_period = profiler1(
        db_services.EventGroup.get_flat_tree_for_dialog__location_plan_period)
    db_services.EventGroup.get_child_groups_from__parent_group = profiler1(
        db_services.EventGroup.get_child_groups_from__parent_group)
    db_services.EventGroup.get_master_from__location_plan_period = profiler1(
        db_services.EventGroup.get_master_from__location_plan_period)

    t_phase1 = time.perf_counter()
    try:
        builder = DlgGroupModeBuilderLocationPlanPeriod(None, location_plan_period)
        dlg = DlgGroupMode(None, builder)
    except Exception as e:
        print(f"FEHLER beim Dialog-Aufbau: {e}")
        import traceback
        traceback.print_exc()
        dlg = None
    else:
        elapsed1 = (time.perf_counter() - t_phase1) * 1000
        print(f"\n  Dialog-Init Gesamtzeit: {elapsed1:.1f} ms")
        print(f"  EventGroups im Cache:   {sum(len(v) for v in builder._eg_children_cache.values())}")

    print_results(profiler1, "Phase 1 — Dialog-Initialisierung")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — refresh_tree (Cache-Reload + erneutes setup_tree)
# ══════════════════════════════════════════════════════════════════════════════

if args.phase in ('2', 'both'):
    print("-" * 70)
    print("PHASE 2: refresh_tree (= Verhalten nach Cancel / delete_unused_groups)")
    print("  reload_object_with_groups → get_flat_tree_for_dialog... → setup_tree")
    print("-" * 70)

    # Dialog neu aufbauen (ohne Profiler-Patch für Init)
    try:
        builder2 = DlgGroupModeBuilderLocationPlanPeriod(None, location_plan_period)
        dlg2 = DlgGroupMode(None, builder2)
    except Exception as e:
        print(f"FEHLER beim Dialog-Aufbau für Phase 2: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    profiler2 = LineProfiler()

    profiler2.add_function(DlgGroupModeBuilderLocationPlanPeriod.reload_object_with_groups)
    profiler2.add_function(TreeWidget.setup_tree)
    profiler2.add_function(TreeWidgetItem.calculate_earliest_date_object)
    profiler2.add_function(db_services.EventGroup.get_flat_tree_for_dialog__location_plan_period)
    profiler2.add_function(db_services.EventGroup.get_child_groups_from__parent_group)
    profiler2.add_function(db_services.LocationPlanPeriod.get)

    DlgGroupModeBuilderLocationPlanPeriod.reload_object_with_groups = profiler2(
        DlgGroupModeBuilderLocationPlanPeriod.reload_object_with_groups)
    TreeWidget.setup_tree = profiler2(TreeWidget.setup_tree)
    TreeWidgetItem.calculate_earliest_date_object = profiler2(
        TreeWidgetItem.calculate_earliest_date_object)
    db_services.EventGroup.get_flat_tree_for_dialog__location_plan_period = profiler2(
        db_services.EventGroup.get_flat_tree_for_dialog__location_plan_period)
    db_services.EventGroup.get_child_groups_from__parent_group = profiler2(
        db_services.EventGroup.get_child_groups_from__parent_group)
    db_services.LocationPlanPeriod.get = profiler2(db_services.LocationPlanPeriod.get)

    t_phase2 = time.perf_counter()
    try:
        dlg2.tree_groups.refresh_tree()
    except Exception as e:
        print(f"FEHLER in refresh_tree: {e}")
        import traceback
        traceback.print_exc()
    else:
        elapsed2 = (time.perf_counter() - t_phase2) * 1000
        print(f"\n  refresh_tree Gesamtzeit: {elapsed2:.1f} ms")

    print_results(profiler2, "Phase 2 — refresh_tree")


# ── Zusammenfassung ───────────────────────────────────────────────────────────
print("=" * 70)
print("INTERPRETATION")
print("=" * 70)
print()
print("  PHASE 1 — Dialog-Öffnen:")
print("  ┌──────────────────────────────────────────────────────────────────┐")
print("  │ get_child_groups_from__parent_group: Hits = 0?                  │")
print("  │   → Ja: Cache greift korrekt, N+1 eliminiert                    │")
print("  │   → Nein: Cache-Pfad wird nicht verwendet                       │")
print("  │                                                                  │")
print("  │ get_flat_tree_for_dialog...: Hits = 1?                          │")
print("  │   → Gesamtzeit = CTE-Query + Batch-Load + model_validate-Zeit   │")
print("  │                                                                  │")
print("  │ calculate_earliest_date_object: Hits = 0?                       │")
print("  │   → Ja: Sortierung nutzt In-Memory-Cache via get_child_groups... │")
print("  └──────────────────────────────────────────────────────────────────┘")
print()
print("  PHASE 2 — refresh_tree:")
print("  ┌──────────────────────────────────────────────────────────────────┐")
print("  │ reload_object_with_groups: 1 Aufruf?                            │")
print("  │   → 1 get_flat_tree_for_dialog + 1 LocationPlanPeriod.get       │")
print("  │ setup_tree: läuft vollständig aus Cache (keine DB-Calls)?        │")
print("  └──────────────────────────────────────────────────────────────────┘")
print()
print("  Kennzahlen:")
print("  % Time  | Enthält                                  | Bedeutung")
print("  --------|------------------------------------------|--------------------")
print("  > 50%   | get_flat_tree_for_dialog...              | DB-Roundtrip (normal)")
print("  > 20%   | model_validate                           | Pydantic-Overhead")
print("  > 5%    | get_child_groups_from__parent_group      | Cache greift NICHT")
print("  > 20%   | calculate_earliest_date_object + DB-Call | Sort-Overhead unkached")