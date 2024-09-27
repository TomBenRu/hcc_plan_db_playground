from typing import Callable
from uuid import UUID

from PySide6.QtCore import Slot, QObject, Signal
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QProgressDialog, QWidget, QApplication

from gui.observer import signal_handling


class DlgProgressInfinite(QProgressDialog):
    def __init__(self, parent: QWidget, window_title: str, label_text: str, cancel_button_text: str,
                 cancel_func: Callable[[], None] | None = None,
                 signal_for_label_text_update: Signal | None = None):
        super().__init__(label_text, cancel_button_text, 0, 0, parent)
        if signal_for_label_text_update:
            signal_for_label_text_update.connect(self.update_label)
        self.setWindowTitle(window_title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        # self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.cancel_func = cancel_func
        self.close()  # damit die Progressbar nicht automatisch nach Initialisierung angezeigt wird.

    @Slot(str)
    def update_label(self, message: str):
        self.setLabelText(message)

    def cancel(self):
        if self.cancel_func:
            self.cancel_func()
            super().cancel()


class DlgProgressSteps(QProgressDialog):
    def __init__(self, parent: QWidget, window_title: str, label_text: str,
                 minimum: int, maximum: int, cancel_button_text: str, cancel_func: Callable[[], None] | None = None):
        """
        Der Process-Balken wird mit jedem empfangenen Signal um 100 / (maximum - minimum) % erhöht.
        """
        super().__init__(label_text, cancel_button_text, minimum, maximum, parent)
        signal_handling.handler_solver.signal_progress.connect(self.update_progress)
        self.setWindowTitle(window_title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.label_text = label_text
        self.cancel_func = cancel_func

        self.curr_progress = -1

    @Slot(str)
    def update_progress(self, comment: str):
        self.curr_progress += 1
        self.setValue(self.curr_progress)
        self.setLabelText(f'{self.label_text}\n{comment}')

    def cancel(self):
        if self.cancel_func:
            self.cancel_func()
            super().cancel()


class GlobalUpdatePlanTabsProgressManager(QObject):
    def __init__(self, progress_bar: DlgProgressInfinite):
        super().__init__()
        self.progress_bar = progress_bar
        self.total_tabs = 0  # Gesamtzahl der zu aktualisierenden Tabs
        self.finished_tabs = 0  # Anzahl der abgeschlossenen Tabs
        self.processed_plan_ids = []

    def tab_started(self):
        # Setze die ProgressBar in den indeterministischen Modus
        if self.total_tabs == 0:
            self.start_progress_bar()
            # self.progress_bar.setRange(0, 0)  # Setzt die ProgressBar auf unbestimmt
        self.total_tabs += 1

    def tab_finished(self, plan_id: UUID):
        # Wird aufgerufen, wenn ein Tab die Aktualisierung abgeschlossen hat
        self.finished_tabs += 1
        self.processed_plan_ids.append(plan_id)
        if self.finished_tabs == self.total_tabs:
            self.progress_bar.close()
            self.total_tabs = 0
            self.finished_tabs = 0
            for p_id in self.processed_plan_ids:
                signal_handling.handler_plan_tabs.refresh_plan(p_id)
                QApplication.processEvents()
            self.processed_plan_ids.clear()
            # self.update_progress_bar()

    def update_progress_bar(self):
        # Fortschrittsbalken auf 100 % setzen, wenn alle Tabs abgeschlossen sind
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

    def start_progress_bar(self):
        self.progress_bar.show()
