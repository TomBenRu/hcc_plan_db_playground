"""
Solution Callbacks für SAT-Solver

Diese Datei enthält Callbacks für die Verarbeitung von Zwischenlösungen
während des Solving-Prozesses.
"""

import logging
from collections import defaultdict
from typing import List, Dict, Optional
from uuid import UUID

from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

from database import schemas


logger = logging.getLogger(__name__)


class PartialSolutionCallback(cp_model.CpSolverSolutionCallback):
    """
    Callback für Zwischenlösungen des SAT-Solvers.
    
    Diese Klasse entspricht der ursprünglichen PartialSolutionCallback
    aus solver_main.py und sammelt/verarbeitet Zwischenlösungen.
    """
    
    def __init__(self, 
                 unassigned_shifts_per_event: List[IntVar],
                 sum_assigned_shifts: Dict[UUID, IntVar], 
                 sum_squared_deviations: IntVar,
                 fixed_cast_conflicts: Dict,
                 limit: Optional[int] = None,
                 print_results: bool = False,
                 collect_schedule_versions: bool = False):
        """
        Initialisiert den Solution Callback.
        
        Args:
            unassigned_shifts_per_event: Liste der Unassigned-Shifts-Variablen
            sum_assigned_shifts: Dictionary der Assigned-Shifts-Variablen pro Mitarbeiter
            sum_squared_deviations: Variable für quadratische Abweichungen
            fixed_cast_conflicts: Dictionary der Fixed-Cast-Conflict-Variablen
            limit: Maximale Anzahl Lösungen (None = unbegrenzt)
            print_results: Ob Ergebnisse geloggt werden sollen
            collect_schedule_versions: Ob Schedule-Versionen gesammelt werden sollen
        """
        super().__init__()
        
        self._unassigned_shifts_per_event = unassigned_shifts_per_event
        self._sum_assigned_shifts = sum_assigned_shifts
        self._sum_squared_deviations = sum_squared_deviations
        self._fixed_cast_conflicts = fixed_cast_conflicts
        self._solution_limit = limit
        self._print_results = print_results
        self._collect_schedule_versions = collect_schedule_versions
        
        # Tracking-Variablen
        self._solution_count = 0
        self._max_assigned_shifts: defaultdict[UUID, int] = defaultdict(int)
        self._sum_max_assigned = 0
        self._count_same_max_assigned = 0
        self._curr_objective_value = float('inf')
        self._num_equal_objective_values = 0
        
        # Schedule-Versionen
        self._schedule_versions: List[List[schemas.AppointmentCreate]] = []
        
        logger.debug("PartialSolutionCallback initialized")
    
    def on_solution_callback(self) -> None:
        """
        Wird bei jeder gefundenen Lösung aufgerufen.
        """
        current_objective = self.ObjectiveValue()
        logger.debug(f"Solution found: objective={current_objective}")
        
        # Prüfe auf ähnliche Zielfunktions-Werte (Stopping-Kriterium)
        if abs(self._curr_objective_value - current_objective) <= 50:
            self._num_equal_objective_values += 1
            logger.debug(f"Similar objective values: {self._num_equal_objective_values}/5")
        else:
            self._num_equal_objective_values = 0
        
        # Stoppe nach 5 ähnlichen Lösungen
        if self._num_equal_objective_values >= 5:
            logger.info("Stopping search after 5 similar objective values")
            self.StopSearch()
        
        self._curr_objective_value = current_objective
        self._solution_count += 1
        
        # Verarbeite Lösung
        if self._print_results:
            self._print_solution_details()
        
        if self._collect_schedule_versions:
            self._collect_current_schedule()
        
        # Update maximale Zuweisungen
        self._update_max_assigned_shifts()
        
        # Prüfe Solution Limit
        if self._solution_limit and self._solution_count >= self._solution_limit:
            logger.info(f"Stopping search after {self._solution_count} solutions")
            self.StopSearch()
    
    def _print_solution_details(self) -> None:
        """Druckt Details der aktuellen Lösung."""
        logger.info(f"Solution {self._solution_count}:")
        logger.info(f"  Objective Value: {self.ObjectiveValue()}")
        
        # Unassigned Shifts
        if self._unassigned_shifts_per_event:
            unassigned_values = [self.Value(var) for var in self._unassigned_shifts_per_event]
            logger.info(f"  Unassigned Shifts: {unassigned_values}")
        
        # Assigned Shifts pro Mitarbeiter
        if self._sum_assigned_shifts:
            # Würde hier Namen brauchen - vereinfacht für Demo
            assigned_counts = {str(app_id)[:8]: self.Value(var) 
                             for app_id, var in self._sum_assigned_shifts.items()}
            logger.info(f"  Assigned Shifts: {assigned_counts}")
        
        # Squared Deviations
        if self._sum_squared_deviations:
            logger.info(f"  Sum Squared Deviations: {self.Value(self._sum_squared_deviations)}")
        
        # Fixed Cast Conflicts
        if self._fixed_cast_conflicts:
            conflicts = {str(key)[:50]: self.Value(var) 
                        for key, var in self._fixed_cast_conflicts.items()}
            nonzero_conflicts = {k: v for k, v in conflicts.items() if v > 0}
            if nonzero_conflicts:
                logger.info(f"  Fixed Cast Conflicts: {nonzero_conflicts}")
    
    def _collect_current_schedule(self) -> None:
        """
        Sammelt die aktuelle Lösung als Schedule-Version.
        
        Diese Methode muss Zugriff auf entities haben um Schedules zu sammeln.
        """
        try:
            # Prüfe ob entities verfügbar sind (über context)
            if not hasattr(self, '_context') or not self._context:
                logger.warning("No context available for schedule collection")
                return
            
            entities = self._context.entities
            current_schedule = []
            
            # Sammle alle aktiven Events und ihre Zuweisungen
            for event_group in sorted(list(entities.event_groups_with_event.values()),
                                      key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index)):
                
                if not self.Value(entities.event_group_vars[event_group.event_group_id]):
                    continue
                
                # Finde alle zugewiesenen AvailDayGroups für dieses Event
                scheduled_adg_ids = []
                for (adg_id, eg_id), var in entities.shift_vars.items():
                    if eg_id == event_group.event_group_id and self.Value(var):
                        scheduled_adg_ids.append(adg_id)
                
                if scheduled_adg_ids:
                    event = event_group.event
                    avail_days = [entities.avail_day_groups_with_avail_day[adg_id].avail_day 
                                 for adg_id in scheduled_adg_ids]
                    current_schedule.append(schemas.AppointmentCreate(avail_days=avail_days, event=event))
            
            self._schedule_versions.append(current_schedule)
            logger.debug(f"Collected schedule version {len(self._schedule_versions)} with {len(current_schedule)} appointments")
            
        except Exception as e:
            logger.error(f"Failed to collect schedule: {e}")
            # Füge leere Schedule hinzu um Index-Konsistenz zu behalten
            self._schedule_versions.append([])
    
    def _update_max_assigned_shifts(self) -> None:
        """Aktualisiert die maximalen Zuweisungen pro Mitarbeiter."""
        for app_id, shift_var in self._sum_assigned_shifts.items():
            current_value = self.Value(shift_var)
            self._max_assigned_shifts[app_id] = max(self._max_assigned_shifts[app_id], current_value)
    
    def _count_same_max_assigned_shifts(self) -> None:
        """Zählt aufeinanderfolgende Lösungen mit gleichen maximalen Zuweisungen."""
        old_sum = self._sum_max_assigned
        new_sum = sum(self._max_assigned_shifts.values())
        
        if new_sum != old_sum:
            self._sum_max_assigned = new_sum
            self._count_same_max_assigned = 0
        else:
            self._count_same_max_assigned += 1
    
    def get_max_assigned_shifts(self) -> Dict[UUID, int]:
        """
        Gibt die maximalen Zuweisungen pro Mitarbeiter zurück.
        
        Returns:
            Dictionary {app_id: max_shifts}
        """
        return dict(self._max_assigned_shifts)
    
    def get_schedule_versions(self) -> List[List[schemas.AppointmentCreate]]:
        """
        Gibt alle gesammelten Schedule-Versionen zurück.
        
        Returns:
            Liste der Schedule-Versionen
        """
        return self._schedule_versions.copy()
    
    def solution_count(self) -> int:
        """
        Gibt die Anzahl gefundener Lösungen zurück.
        
        Returns:
            Anzahl der Lösungen
        """
        return self._solution_count
    
    def get_statistics(self) -> Dict:
        """
        Gibt Statistiken des Callback zurück.
        
        Returns:
            Dictionary mit Callback-Statistiken
        """
        return {
            'solution_count': self._solution_count,
            'max_assigned_shifts': dict(self._max_assigned_shifts),
            'schedule_versions_count': len(self._schedule_versions),
            'current_objective_value': self._curr_objective_value,
            'equal_objective_count': self._num_equal_objective_values,
            'solution_limit': self._solution_limit,
            'print_results': self._print_results,
            'collect_schedules': self._collect_schedule_versions
        }
    
    def reset(self) -> None:
        """Setzt den Callback für eine neue Solving-Session zurück."""
        self._solution_count = 0
        self._max_assigned_shifts.clear()
        self._sum_max_assigned = 0
        self._count_same_max_assigned = 0
        self._curr_objective_value = float('inf')
        self._num_equal_objective_values = 0
        self._schedule_versions.clear()
        
        logger.debug("PartialSolutionCallback reset")


class SimpleSolutionCallback(cp_model.CpSolverSolutionCallback):
    """
    Vereinfachter Solution Callback für Basic-Logging.
    
    Für Fälle wo nur grundlegende Lösung-Informationen benötigt werden.
    """
    
    def __init__(self, log_solutions: bool = True):
        """
        Initialisiert den Simple Callback.
        
        Args:
            log_solutions: Ob Lösungen geloggt werden sollen
        """
        super().__init__()
        self._solution_count = 0
        self._log_solutions = log_solutions
        self._best_objective = None
        
    def on_solution_callback(self) -> None:
        """Wird bei jeder Lösung aufgerufen."""
        self._solution_count += 1
        current_objective = self.ObjectiveValue()
        
        if self._best_objective is None or current_objective < self._best_objective:
            self._best_objective = current_objective
        
        if self._log_solutions:
            logger.info(f"Solution {self._solution_count}: objective={current_objective}")
    
    def solution_count(self) -> int:
        """Gibt die Anzahl gefundener Lösungen zurück."""
        return self._solution_count
    
    def best_objective(self) -> Optional[float]:
        """Gibt den besten Zielfunktions-Wert zurück."""
        return self._best_objective


class ProgressCallback(cp_model.CpSolverSolutionCallback):
    """
    Callback für Progress-Updates während des Solving.
    """
    
    def __init__(self, progress_callback=None, update_interval: int = 10):
        """
        Initialisiert den Progress Callback.
        
        Args:
            progress_callback: Funktion die für Progress-Updates aufgerufen wird
            update_interval: Interval zwischen Updates (Anzahl Lösungen)
        """
        super().__init__()
        self._progress_callback = progress_callback
        self._update_interval = update_interval
        self._solution_count = 0
    
    def on_solution_callback(self) -> None:
        """Wird bei jeder Lösung aufgerufen."""
        self._solution_count += 1
        
        if (self._progress_callback and 
            self._solution_count % self._update_interval == 0):
            
            try:
                self._progress_callback(
                    solutions_found=self._solution_count,
                    current_objective=self.ObjectiveValue()
                )
            except Exception as e:
                logger.error(f"Progress callback failed: {e}")
    
    def solution_count(self) -> int:
        """Gibt die Anzahl gefundener Lösungen zurück."""
        return self._solution_count
