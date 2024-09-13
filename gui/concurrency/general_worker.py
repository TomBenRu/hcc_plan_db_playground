from PySide6.QtCore import QObject, Signal, QRunnable, Slot


class WorkerSignals(QObject):
    finished = Signal()
    progress = Signal(int)


class Worker(QRunnable):
    def __init__(self, function, *args, **kwargs):
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
