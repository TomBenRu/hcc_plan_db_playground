from typing import Callable
from uuid import UUID

from PySide6.QtCore import QObject, Signal, QRunnable, Slot


class WorkerSignals(QObject):
    finished = Signal()
    progress = Signal(int)


class SignalsCheckPlan(QObject):
    finished = Signal(bool, list)


class WorkerGeneral(QRunnable):
    def __init__(self, function: Callable, *args, **kwargs):
        super().__init__()
        self.function = function  # Die Funktion, die ausgeführt wird
        self.args = args          # Argumente für die Funktion
        self.kwargs = kwargs      # Keyword-Argumente für die Funktion
        self.signals = WorkerSignals()

    @Slot()  # Der Worker wird als Slot ausgeführt
    def run(self):
        # Führe die übergebene Funktion mit den Argumenten aus
        self.function(*self.args, **self.kwargs)
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
    
