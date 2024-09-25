from typing import Callable
from uuid import UUID

from PySide6.QtCore import QObject, Signal, QRunnable, Slot


class WorkerSignals(QObject):
    finished = Signal()
    progress = Signal(int)


class SignalsCheckPlan(QObject):
    finished = Signal(bool, list)


class SignalsGetMaxFairShifts(QObject):
    finished = Signal(object, object)


class WorkerSignalsReturnValue(QObject):
    finished = Signal(object)


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


class WorkerCheckPlan(QRunnable):
    def __init__(self, function: Callable[[UUID], tuple[bool, list[str]]], plan_id: UUID):
        super().__init__()
        self.function = function
        self.plan_id = plan_id
        self.signals = SignalsCheckPlan()

    @Slot()
    def run(self):
        success, problems = self.function(self.plan_id)
        self.signals.finished.emit(success, problems)


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
