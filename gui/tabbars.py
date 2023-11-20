from typing import Literal, Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QMenu


class TabBar(QTabWidget):
    """Puts a tabbar to a blank QWidget"""
    def __init__(self, parent: QWidget, position: Literal['west', 'north', 'east', 'south'] = None,
                 font_size: int = None, tab_height: int = None, tab_width: int = None, set_movable: bool = True,
                 set_closable: bool = True, context_menu_slot: Callable[[QPoint, int], None] = None,
                 object_name: str = None):
        super().__init__(parent=parent)

        self.context_menu_slot = context_menu_slot

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        parent.setLayout(layout)
        layout.addWidget(self)

        self.setMovable(set_movable)

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

        if context_menu_slot:
            self.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
            self.tabBar().customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, point: QPoint):
        index = self.tabBar().tabAt(point)
        if index >= 0:
            self.context_menu_slot(point, index)

