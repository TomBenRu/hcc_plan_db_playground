from typing import Callable

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QWidget, QMainWindow


class Action(QAction):
    def __init__(self, parent: QMainWindow, icon_path: str, text: str, status_tip: str | None, slot: Callable):
        super().__init__(QIcon(icon_path), text, parent)
        if status_tip:
            self.setStatusTip(status_tip)
        self.triggered.connect(slot)
