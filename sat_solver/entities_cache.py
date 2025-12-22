"""
Entities-Cache für schnelle Plan-Validierung.

Dieses Modul stellt einen Worker für das Hintergrund-Laden von Entities bereit.
Die Entities werden nach plan_period_id gecacht und können von mehreren Plänen
der gleichen PlanPeriod wiederverwendet werden.

Verwendung:
    - TabManager verwaltet den Cache: dict[UUID, Entities]
    - Beim Tab-Wechsel wird geprüft ob Entities geladen werden müssen
    - WorkerLoadEntities lädt Entities im Hintergrund
    - test_plan() verwendet gecachte Entities falls vorhanden
"""

import logging
import threading
import time
from uuid import UUID

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

logger = logging.getLogger(__name__)


class SignalsLoadEntities(QObject):
    """Signals für den Entities-Lade-Worker."""

    # Signal wenn Entities erfolgreich geladen wurden
    # Parameter: plan_period_id, generation, entities
    finished = Signal(UUID, int, object)

    # Signal bei Fehler
    # Parameter: plan_period_id, generation, error_message
    error = Signal(UUID, int, str)

    # Signal bei Abbruch
    # Parameter: plan_period_id, generation
    cancelled = Signal(UUID, int)


class WorkerLoadEntities(QRunnable):
    """
    Worker für das Laden von Entities im Hintergrund.

    Lädt alle für die Plan-Validierung benötigten Entities:
    - event_group_tree
    - avail_day_group_tree
    - cast_group_tree
    - entities (create_data_models)
    - shifts_exclusive (populate_shifts_exclusive)

    Unterstützt Abbruch via cancel() Methode.
    """

    def __init__(self, plan_period_id: UUID, generation: int):
        super().__init__()
        self.plan_period_id = plan_period_id
        self.generation = generation
        self.signals = SignalsLoadEntities()
        # Thread-safe Abbruch-Flag
        self._cancelled = threading.Event()

    def cancel(self):
        """
        Markiert den Worker als abgebrochen.
        Thread-safe, kann von jedem Thread aufgerufen werden.
        """
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        """Prüft ob Abbruch angefordert wurde."""
        return self._cancelled.is_set()

    def _check_cancelled(self, stage: str) -> bool:
        """
        Prüft Abbruch und emittiert Signal falls abgebrochen.

        Args:
            stage: Name der aktuellen Phase für Logging

        Returns:
            True wenn abgebrochen, False sonst
        """
        if self._cancelled.is_set():
            logger.debug(f"WorkerLoadEntities abgebrochen in Phase '{stage}' "
                         f"für plan_period_id={self.plan_period_id}")
            self.signals.cancelled.emit(self.plan_period_id, self.generation)
            return True
        return False

    @Slot()
    def run(self):
        """Lädt Entities im Hintergrund-Thread mit Abbruch-Prüfungen."""
        try:
            # Lazy Import um zirkuläre Imports zu vermeiden
            # WICHTIG: Imports aus data_loading.py statt solver_main.py
            # um OR-Tools Threading-Crash zu vermeiden (siehe HANDOVER_ortools_threading_crash_fix)
            from sat_solver.event_group_tree import get_event_group_tree
            from sat_solver.avail_day_group_tree import get_avail_day_group_tree
            from sat_solver.cast_group_tree import get_cast_group_tree
            from sat_solver.data_loading import (
                create_data_models,
                populate_shifts_exclusive,
            )

            total_start = time.perf_counter()

            # Phase 1: Event Group Tree
            if self._check_cancelled("before_event_group_tree"):
                return
            start = time.perf_counter()
            event_group_tree = get_event_group_tree(self.plan_period_id)
            logger.info(f"[Entities-Preload] get_event_group_tree: {time.perf_counter() - start:.3f}s")

            # Phase 2: Avail Day Group Tree
            if self._check_cancelled("after_event_group_tree"):
                return
            start = time.perf_counter()
            avail_day_group_tree = get_avail_day_group_tree(self.plan_period_id)
            logger.info(f"[Entities-Preload] get_avail_day_group_tree: {time.perf_counter() - start:.3f}s")

            # Phase 3: Cast Group Tree
            if self._check_cancelled("after_avail_day_group_tree"):
                return
            start = time.perf_counter()
            cast_group_tree = get_cast_group_tree(self.plan_period_id)
            logger.info(f"[Entities-Preload] get_cast_group_tree: {time.perf_counter() - start:.3f}s")

            # Phase 4: Create Data Models (mit feinkörniger Abbruch-Prüfung)
            if self._check_cancelled("after_cast_group_tree"):
                return
            start = time.perf_counter()
            entities = create_data_models(
                event_group_tree,
                avail_day_group_tree,
                cast_group_tree,
                self.plan_period_id,
                cancelled_check=self.is_cancelled
            )
            logger.info(f"[Entities-Preload] create_data_models: {time.perf_counter() - start:.3f}s")
            if entities is None:
                self.signals.cancelled.emit(self.plan_period_id, self.generation)
                return

            # Phase 5: Populate Shifts Exclusive
            if self._check_cancelled("after_preload_avail_days"):
                return
            start = time.perf_counter()
            populate_shifts_exclusive(entities)
            logger.info(f"[Entities-Preload] populate_shifts_exclusive: {time.perf_counter() - start:.3f}s")

            # Finale Prüfung vor Signal
            if self._check_cancelled("after_populate_shifts_exclusive"):
                return

            logger.info(f"[Entities-Preload] TOTAL: {time.perf_counter() - total_start:.3f}s")

            # Erfolg signalisieren
            self.signals.finished.emit(self.plan_period_id, self.generation, entities)

        except Exception as e:
            # Fehler nur signalisieren wenn nicht abgebrochen
            if not self._cancelled.is_set():
                self.signals.error.emit(self.plan_period_id, self.generation, str(e))
