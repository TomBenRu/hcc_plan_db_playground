from typing import Callable, Any

from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import QWidget, QMainWindow


class Action(QAction):
    def __init__(self, parent: QWidget, icon_path: str | None, text: str, status_tip: str | None, slot: Callable[[...], Any],
                 short_cut: str | None = None):
        super().__init__(QIcon(icon_path), text, parent)
        self.slot = slot
        if status_tip:
            self.setStatusTip(status_tip)
        self.triggered.connect(self.slot)
        if short_cut:
            self.setShortcut(QKeySequence(short_cut))
