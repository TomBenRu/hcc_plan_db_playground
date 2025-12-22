"""
Daten-Lade-Funktionen für den Solver.

Dieses Modul enthält Funktionen zum Laden und Vorbereiten von Entities
für die Plan-Kalkulation und -Validierung.

WICHTIG: Dieses Modul importiert NICHT OR-Tools, damit es sicher
in Hintergrund-Threads verwendet werden kann ohne Threading-Konflikte
mit dem OR-Tools Solver zu verursachen.

Siehe HANDOVER_ortools_threading_crash_fix_december_2025 für Details.
"""

import dataclasses
import logging
import time
from typing import Callable, Optional, TYPE_CHECKING
from uuid import UUID

from database import db_services, schemas
from sat_solver.event_group_tree import EventGroupTree, EventGroup
from sat_solver.avail_day_group_tree import AvailDayGroupTree, AvailDayGroup
from sat_solver.cast_group_tree import CastGroupTree, CastGroup
from sat_solver.constraints.helpers import (
    check_actor_location_prefs_fits_event,
    check_time_span_avail_day_fits_event,
)

logger = logging.getLogger(__name__)

# TYPE_CHECKING guard: IntVar wird nur für Type-Hints benötigt,
# nicht zur Laufzeit. Dies verhindert den OR-Tools Import.
if TYPE_CHECKING:
    from ortools.sat.python.cp_model import IntVar


@dataclasses.dataclass
class Entities:
    """Datencontainer für alle Solver-relevanten Entitäten."""
    actor_plan_periods: dict[UUID, schemas.ActorPlanPeriodSolver] = dataclasses.field(default_factory=dict)
    avail_day_groups: dict[UUID, AvailDayGroup] = dataclasses.field(default_factory=dict)
    avail_day_groups_with_avail_day: dict[UUID, AvailDayGroup] = dataclasses.field(default_factory=dict)
    avail_day_group_vars: dict[UUID, 'IntVar'] = dataclasses.field(default_factory=dict)
    event_groups: dict[UUID, EventGroup] = dataclasses.field(default_factory=dict)
    event_groups_with_event: dict[UUID, EventGroup] = dataclasses.field(default_factory=dict)
    event_group_vars: dict[UUID, 'IntVar'] = dataclasses.field(default_factory=dict)
    cast_groups: dict[UUID, CastGroup] = dataclasses.field(default_factory=dict)
    cast_groups_with_event: dict[UUID, CastGroup] = dataclasses.field(default_factory=dict)
    shift_vars: dict[tuple[UUID, UUID], 'IntVar'] = dataclasses.field(default_factory=dict)
    shifts_exclusive: dict[tuple[UUID, UUID], int] = dataclasses.field(default_factory=dict)


def create_data_models(event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree,
                       cast_group_tree: CastGroupTree, plan_period_id: UUID,
                       cancelled_check: Optional[Callable[[], bool]] = None) -> Optional[Entities]:
    """
    Erstellt und füllt ein neues Entities-Objekt mit allen Solver-Daten.

    Args:
        event_group_tree: Baum der Event-Gruppen
        avail_day_group_tree: Baum der Verfügbarkeits-Tage-Gruppen
        cast_group_tree: Baum der Cast-Gruppen
        plan_period_id: ID der Planperiode
        cancelled_check: Optional - Callable die True zurückgibt wenn abgebrochen werden soll

    Returns:
        Gefülltes Entities-Objekt, oder None wenn abgebrochen
    """
    entities = Entities()

    # ActorPlanPeriods laden - optimiert mit Batch-Abfrage statt N+1 Queries
    entities.actor_plan_periods = db_services.ActorPlanPeriod.get_all_for_solver(plan_period_id)
    if cancelled_check and cancelled_check():
        return None

    entities.event_groups = {
        event_group.event_group_id: event_group for event_group in event_group_tree.root.descendants
        if event_group.children or event_group.event
    }
    entities.event_groups = {event_group_tree.root.event_group_id: event_group_tree.root} | entities.event_groups

    entities.event_groups_with_event = {leave.event_group_id: leave for leave in event_group_tree.root.leaves
                                        if leave.event}

    entities.avail_day_groups = {
        avail_day_group.avail_day_group_id: avail_day_group for avail_day_group in avail_day_group_tree.root.descendants
        if avail_day_group.children or avail_day_group._avail_day_id
    }
    entities.avail_day_groups = ({avail_day_group_tree.root.avail_day_group_id: avail_day_group_tree.root}
                                 | entities.avail_day_groups)
    entities.avail_day_groups_with_avail_day = {
        leave.avail_day_group_id: leave for leave in avail_day_group_tree.root.leaves if leave._avail_day_id
    }

    entities.cast_groups = {cast_group_tree.root.cast_group_id: cast_group_tree.root} | {
        cast_group.cast_group_id: cast_group
        for cast_group in cast_group_tree.root.descendants
    }
    entities.cast_groups_with_event = {cast_group.cast_group_id: cast_group
                                       for cast_group in cast_group_tree.root.leaves if cast_group.event}

    # Preload AvailDays (Batch-Laden für spätere Verwendung)
    start = time.perf_counter()
    preload_avail_days(entities)
    logger.info(f"[Entities-Preload] preload_avail_days (innerhalb create_data_models): {time.perf_counter() - start:.3f}s")

    return entities


def create_data_models_multi_period(event_group_tree: EventGroupTree, avail_day_group_tree: AvailDayGroupTree,
                                   cast_group_tree: CastGroupTree, plan_period_ids: list[UUID]) -> Entities:
    """
    Erstellt und füllt ein neues Entities-Objekt für Multi-Period Kalkulation.
    
    Im Gegensatz zu create_data_models() werden hier ActorPlanPeriods, Events und CastGroups
    von ALLEN übergebenen PlanPeriods gesammelt.
    
    Args:
        event_group_tree: Combined EventGroupTree über alle Perioden
        avail_day_group_tree: Combined AvailDayGroupTree über alle Perioden
        cast_group_tree: Combined CastGroupTree über alle Perioden
        plan_period_ids: Liste aller PlanPeriod UUIDs
        
    Returns:
        Gefülltes Entities-Objekt
    """
    entities = Entities()

    # Sammle ActorPlanPeriods von ALLEN PlanPeriods - optimiert mit Batch-Abfrage
    for pp_id in plan_period_ids:
        entities.actor_plan_periods.update(
            db_services.ActorPlanPeriod.get_all_for_solver(pp_id)
        )

    # Rest analog zu create_data_models() - Tree-Struktur ist bereits kombiniert
    entities.event_groups = {
        event_group.event_group_id: event_group for event_group in event_group_tree.root.descendants
        if event_group.children or event_group.event
    }
    entities.event_groups = {event_group_tree.root.event_group_id: event_group_tree.root} | entities.event_groups

    entities.event_groups_with_event = {leave.event_group_id: leave for leave in event_group_tree.root.leaves
                                        if leave.event}

    entities.avail_day_groups = {
        avail_day_group.avail_day_group_id: avail_day_group for avail_day_group in avail_day_group_tree.root.descendants
        if avail_day_group.children or avail_day_group._avail_day_id
    }
    entities.avail_day_groups = ({avail_day_group_tree.root.avail_day_group_id: avail_day_group_tree.root}
                                 | entities.avail_day_groups)

    entities.avail_day_groups_with_avail_day = {
        leave.avail_day_group_id: leave for leave in avail_day_group_tree.root.leaves if leave._avail_day_id
    }

    entities.cast_groups = {cast_group_tree.root.cast_group_id: cast_group_tree.root} | {
        cast_group.cast_group_id: cast_group
        for cast_group in cast_group_tree.root.descendants
    }
    entities.cast_groups_with_event = {cast_group.cast_group_id: cast_group
                                       for cast_group in cast_group_tree.root.leaves if cast_group.event}

    return entities


def preload_avail_days(entities: Entities) -> None:
    """
    Lädt alle AvailDays für die avail_day_groups_with_avail_day in einer Batch-Abfrage.

    Dies verhindert N+1 Queries beim späteren Zugriff auf adg.avail_day.

    Args:
        entities: Entities-Objekt mit avail_day_groups_with_avail_day
    """
    # Sammle alle avail_day_ids
    avail_day_ids = [
        adg._avail_day_id for adg in entities.avail_day_groups_with_avail_day.values()
        if adg._avail_day_id
    ]

    if not avail_day_ids:
        return

    # Batch-Laden aller AvailDays (optimiertes Schema für Solver)
    avail_days = db_services.AvailDay.get_batch_minimal(avail_day_ids)

    # Cache in den Tree-Nodes setzen
    for adg in entities.avail_day_groups_with_avail_day.values():
        if adg._avail_day_id and adg._avail_day_id in avail_days:
            adg._avail_day = avail_days[adg._avail_day_id]


def populate_shifts_exclusive(entities: Entities) -> None:
    """
    Befüllt entities.shifts_exclusive mit Verfügbarkeitsinformationen.

    Für jede Kombination aus AvailDayGroup und EventGroup wird geprüft,
    ob eine Zuweisung möglich ist (basierend auf Standort-Präferenzen und Zeitfenstern).

    Diese Funktion kann unabhängig vom Solver aufgerufen werden, z.B. für Plan-Validierung.

    WICHTIG: preload_avail_days() sollte vorher aufgerufen werden, um N+1 Queries zu vermeiden.

    Args:
        entities: Entities-Objekt mit avail_day_groups_with_avail_day und event_groups_with_event
    """
    for adg_id, adg in entities.avail_day_groups_with_avail_day.items():
        for event_group_id, event_group in entities.event_groups_with_event.items():
            location_of_work = event_group.event.location_plan_period.location_of_work
            # Standardmäßig ist Zuweisung möglich
            entities.shifts_exclusive[adg_id, event_group_id] = 1
            # Prüfe Standort-Präferenzen (Score > 0 erforderlich)
            if not check_actor_location_prefs_fits_event(adg.avail_day, location_of_work):
                entities.shifts_exclusive[adg_id, event_group_id] = 0
            # Prüfe Zeitfenster und Datum
            if not check_time_span_avail_day_fits_event(event_group.event, adg.avail_day):
                entities.shifts_exclusive[adg_id, event_group_id] = 0
