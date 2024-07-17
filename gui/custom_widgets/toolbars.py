from PySide6.QtCore import QSize
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar


class MainToolBar(QToolBar):
    def __init__(self, title: str, actions: list[QAction | None], icon_size: int = 16):
        super().__init__(title)
        self.setIconSize(QSize(icon_size, icon_size))
        for action in actions:
            if action is None:
                self.addSeparator()
            else:
                self.addAction(action)
