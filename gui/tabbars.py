from typing import Literal

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout


class TabBar(QTabWidget):
    """Puts a tabbar to a blank QWidget"""
    def __init__(self, parent: QWidget, position: Literal['west', 'north', 'east', 'south'] = None,
                 font_size: int = None, tab_height: int = None, tab_width: int = None, set_moveble: bool = True,
                 object_name: str = None):
        super().__init__(parent=parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        parent.setLayout(layout)
        layout.addWidget(self)

        self.setMovable(set_moveble)

        positions = {'west': QTabWidget.West, 'north': QTabWidget.North,
                     'east': QTabWidget.East, 'south': QTabWidget.South}
        if object_name is not None:
            self.setObjectName(object_name)
        if position is not None:
            self.setTabPosition(positions[position])
        if font_size is not None:
            self.setFont(QFont(self.font().family(), font_size))
        if tab_height is not None:
            self.setStyleSheet(f'QTabBar::tab {{height: {tab_height}px;}}')
        if tab_width is not None:
            self.setStyleSheet(f'QTabBar::tab {{width: {tab_width}px;}}')
