from typing import Callable

from PySide6.QtCore import Slot
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QProgressDialog, QWidget

from gui.observer import signal_handling


class DlgProgressInfinite(QProgressDialog):
    def __init__(self, parent: QWidget, window_title: str, label_text: str, cancel_button_text: str):
        super().__init__(label_text, cancel_button_text, 0, 0, parent)
        self.setWindowTitle(window_title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        # self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)

    def cancel(self):
        signal_handling.handler_solver.cancel_solving()
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
