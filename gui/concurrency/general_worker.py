import datetime
import datetime
from typing import Callable
from uuid import UUID

from PySide6.QtCore import QObject, Signal, QRunnable, Slot

from commands import command_base_classes
from database import schemas


class WorkerSignals(QObject):
    finished = Signal()
    progress = Signal(int)


class SignalsCheckPlan(QObject):
    finished = Signal(bool, list, list)  # success, problems, infos


class SignalsGetMaxFairShifts(QObject):
    finished = Signal(object, object)


class WorkerSignalsReturnValue(QObject):
    finished = Signal(object)

class SignalsCalculatePlan(QObject):
    finished = Signal(object, object, object, object, object)



class SignalsCalculateMultiPeriod(QObject):
    finished = Signal(object, object, object, object, object, object)


class WorkerGeneral(QRunnable):
    def __init__(self, function: Callable, has_return_val: bool = False, *args, **kwargs):
        super().__init__()
        self.function = function  # Die Funktion, die ausgeführt wird
        self.args = args          # Argumente für die Funktion
        self.has_return_val = has_return_val
        self.kwargs = kwargs      # Keyword-Argumente für die Funktion
        self.signals = WorkerSignalsReturnValue() if has_return_val else WorkerSignals()

    @Slot()  # Der Worker wird als Slot ausgeführt
    def run(self):
        # Führe die übergebene Funktion mit den Argumenten aus
        result = self.function(*self.args, **self.kwargs)
        if self.has_return_val:
            self.signals.finished.emit(result)
        else:
            self.signals.finished.emit()  # Signal für den Abschluss senden


class WorkerCalculatePlan(QRunnable):
    def __init__(self,
                 function: Callable[[UUID, int, int, int, int],
                 tuple[list[list[schemas.AppointmentCreate]],
                 dict[tuple[datetime.date, str, UUID], int], dict[str, int], dict[UUID, int], dict[UUID, float]]],
                 plan_period_id: UUID, num_plans: int, time_calc_max_shifts: int, time_calc_fair_distribution: int,
                 time_calc_plan: int):
        super().__init__()
        self.function = function
        self.plan_period_id = plan_period_id
        self.num_plans = num_plans
        self.time_calc_max_shifts = time_calc_max_shifts
        self.time_calc_fair_distribution = time_calc_fair_distribution
        self.time_calc_plan = time_calc_plan
        self.signals = SignalsCalculatePlan()

    @Slot()
    def run(self):
        (schedule_versions, fixed_cast_conflicts, skill_conflicts,
         max_shifts_per_app, fair_shifts_per_app) = self.function(self.plan_period_id,
                                                                  self.num_plans,
                                                                  self.time_calc_max_shifts,
                                                                  self.time_calc_fair_distribution,
                                                                  self.time_calc_plan)
        self.signals.finished.emit(schedule_versions, fixed_cast_conflicts, skill_conflicts,
                                   max_shifts_per_app, fair_shifts_per_app)



class WorkerCalculateMultiPeriod(QRunnable):
    """
    Worker für Multi-Period Plan-Berechnung.
    
    Ruft solve_multi_period() auf und emittiert die Ergebnisse zusammen mit
    den selected_pp_ids für die Speicherung.
    
    OPTIMIERT: Pläne sind bereits pro Periode strukturiert (all_plans[period_idx][plan_idx]).
    """
    def __init__(self,
                 function: Callable[[list[UUID], int, int, int, int],
                 tuple[list[list[list[schemas.AppointmentCreate]]],
                 dict[tuple[datetime.date, str, UUID], int], dict[str, int], dict[UUID, int], dict[UUID, float]]],
                 plan_period_ids: list[UUID],
                 num_plans: int,
                 time_calc_max_shifts: int,
                 time_calc_fair_distribution: int,
                 time_calc_plan: int):
        super().__init__()
        self.function = function
        self.plan_period_ids = plan_period_ids
        self.num_plans = num_plans
        self.time_calc_max_shifts = time_calc_max_shifts
        self.time_calc_fair_distribution = time_calc_fair_distribution
        self.time_calc_plan = time_calc_plan
        self.signals = SignalsCalculateMultiPeriod()

    @Slot()
    def run(self):
        """
        Führt die Multi-Period Berechnung aus.
        
        Emittiert plan_period_ids als erstes Argument, damit die GUI
        weiß für welche Perioden der Plan aufgeteilt werden muss.
        """
        (schedule_versions, fixed_cast_conflicts, skill_conflicts,
         max_shifts_per_app, fair_shifts_per_app) = self.function(
            self.plan_period_ids,
            self.num_plans,
            self.time_calc_max_shifts,
            self.time_calc_fair_distribution,
            self.time_calc_plan
        )
        
        # Emittiere Ergebnisse zusammen mit den plan_period_ids
        self.signals.finished.emit(
            self.plan_period_ids,
            schedule_versions,
            fixed_cast_conflicts,
            skill_conflicts,
            max_shifts_per_app,
            fair_shifts_per_app
        )


class WorkerSavePlans(QRunnable):
    def __init__(self, function: Callable[[UUID, UUID, list[list[schemas.AppointmentCreate]], dict[UUID, int],
                 dict[UUID, float], int, command_base_classes.ContrExecUndoRedo], list[UUID]],
                 plan_period_id: UUID, team_id: UUID, schedule_versions: list[list[schemas.AppointmentCreate]],
                 max_shifts_per_app: dict[UUID, int], fair_shifts_per_app: dict[UUID, float],
                 nr_versions_to_use: int, controller: command_base_classes.ContrExecUndoRedo):
        super().__init__()
        self.function = function
        self.plan_period_id = plan_period_id
        self.team_id = team_id
        self.schedule_versions = schedule_versions
        self.max_shifts_per_app = max_shifts_per_app
        self.fair_shifts_per_app = fair_shifts_per_app
        self.nr_versions_to_use = nr_versions_to_use
        self.controller = controller
        self.signals = WorkerSignalsReturnValue()

    @Slot()
    def run(self):
        created_plan_ids = self.function(self.plan_period_id, self.team_id, self.schedule_versions,
                                        self.max_shifts_per_app, self.fair_shifts_per_app,
                                        self.nr_versions_to_use, self.controller)
        self.signals.finished.emit(created_plan_ids)


class WorkerCheckPlan(QRunnable):
    def __init__(self, function: Callable[[UUID], tuple[bool, list[str], list[str]]], plan_id: UUID):
        super().__init__()
        self.function = function
        self.plan_id = plan_id
        self.signals = SignalsCheckPlan()

    @Slot()
    def run(self):
        success, problems, infos = self.function(self.plan_id)
        self.signals.finished.emit(success, problems, infos)


class WorkerGetMaxFairShifts(QRunnable):
    def __init__(self, function: Callable[[UUID, int, int, bool], bool | tuple[dict[UUID, int], dict[UUID, float]]],
                 plan_period_id: UUID,  time_calc_max_shifts: int, time_calc_fair_distribution: int):
        super().__init__()

        self.function = function
        self.plan_period_id = plan_period_id
        self.time_calc_max_shifts = time_calc_max_shifts
        self.time_calc_fair_distribution = time_calc_fair_distribution
        self.signals = SignalsGetMaxFairShifts()

    @Slot()
    def run(self):
        max_shifts, fair_shifts = self.function(self.plan_period_id, self.time_calc_max_shifts,
                                                self.time_calc_fair_distribution, False)
        self.signals.finished.emit(max_shifts, fair_shifts)
