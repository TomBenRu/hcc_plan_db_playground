from typing import Literal, Iterable

from PySide6.QtGui import QMouseEvent, Qt
from PySide6.QtWidgets import (QWidget, QApplication, QVBoxLayout, QPushButton, QGraphicsView, QGraphicsScene,
                               QGraphicsProxyWidget, QHBoxLayout, QLabel, QScrollArea, QCheckBox)
from PySide6.QtCore import QPropertyAnimation, QPoint, QEasingCurve, QEvent


class RotatableContainer(QGraphicsView):
    def __init__(self, widget: QWidget, rotation: float):
        super().__init__()

        scene = QGraphicsScene(self)
        self.setScene(scene)

        self.proxy = QGraphicsProxyWidget()
        self.proxy.setWidget(widget)
        self.proxy.setTransformOriginPoint(self.proxy.boundingRect().center())
        self.proxy.setRotation(rotation)
        scene.addItem(self.proxy)

    def rotate(self, rotation: float):
        self.proxy.setRotation(rotation)


class WidgetSideMenu(QWidget):
    def __init__(self, parent: QWidget, menu_width: int, snap_width: int, align: Literal['left', 'right']):
        super().__init__(parent)
        """
Initializes a custom side menu widget.

Args:
    parent (QWidget): The parent widget.
    menu_width (int): The width of the side menu.
    snap_width (int): The snap width.
    align (Literal['left', 'right']): The alignment of the side menu.

Returns:
    None

Examples:
    widget = WidgetSideMenu(parent_widget, 200, 50, 'left')
"""

        self.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background-color: rgba(255, 255, 255, 0);")

        self.parent = parent
        self.align = align
        self.menu_width = menu_width
        self.snap_width = snap_width
        self.pos_x_hide = 0
        self.pos_x_show = 0

        self.set_positions()
        self.setGeometry(self.pos_x_hide, 0, menu_width, 600)
        self.color_buttons = '#e1e1e1'
        self.color_text = 'black'

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.scrollarea_fields = QScrollArea()
        self.scrollarea_fields.setStyleSheet("background-color: rgba(130, 205, 203, 100);")
        self.layout.addWidget(self.scrollarea_fields)
        self.container_fields = QLabel()
        self.container_fields.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.container_fields.setMinimumWidth(menu_width - 20)
        self.container_fields.setContentsMargins(20, 20, 0, 20)
        self.scrollarea_fields.setWidget(self.container_fields)

        self.layout_fields = QVBoxLayout(self.container_fields)

        self.layout_fields.setAlignment(Qt.AlignTop)

        self.container_fields.setMinimumHeight(len(self.container_fields.children()) * 30 + 30)

        self.animation = QPropertyAnimation(self, b"pos")

        parent.resizeEvent = self.parent_resize_event

    def set_positions(self):
        if self.align == 'left':
            self.pos_x_hide = self.snap_width - self.menu_width
            self.pos_x_show = 0
        elif self.align == 'right':
            self.pos_x_hide = self.parent.width() - self.snap_width
            self.pos_x_show = self.parent.width() - self.menu_width

    def parent_resize_event(self, e):
        self.set_positions()
        self.setGeometry(self.pos_x_hide, 0, self.menu_width, self.parent.height())

    def enterEvent(self, event: QMouseEvent) -> None:
        self.show_sidemenu()

    def leaveEvent(self, event: QEvent) -> None:
        self.hide_siedemenu()

    def show_sidemenu(self):
        self.animation.setEasingCurve(QEasingCurve.OutBounce)
        self.animation.setEndValue(QPoint(self.pos_x_show, 0))
        self.animation.setDuration(750)
        self.animation.start()

    def hide_siedemenu(self):
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.setEndValue(QPoint(self.pos_x_hide, 0))
        self.animation.setDuration(750)
        self.animation.start()

    def set_side_menu_width(self, width: int):
        self.menu_width = width
        self.setGeometry(self.pos_x_hide, 0, self.menu_width, self.parent.height())

    def add_button(self, button: QPushButton):
        button.setStyleSheet(f"background-color: {self.color_buttons}; color: {self.color_text};")
        self.layout_fields.addWidget(button)
        self.container_fields.setMinimumHeight(len(self.container_fields.children()) * 30 + 30)

    def add_check_box(self, check_box: QCheckBox):
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {self.color_buttons}; color: {self.color_text};")
        widget.setContentsMargins(10, 2, 10, 2)
        widget_layout = QVBoxLayout(widget)
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.addWidget(check_box)
        self.layout_fields.addWidget(widget)
        self.container_fields.setMinimumHeight(len(self.container_fields.children()) * 30 + 30)

    def delete_all_buttons(self):
        buttons: Iterable[QPushButton] = self.findChildren(QPushButton)
        for button in buttons:
            button.deleteLater()


if __name__ == '__main__':
    app = QApplication()

    class Window(QWidget):
        def __init__(self):
            super().__init__()
            self.resize(800, 600)
            self.layout = QVBoxLayout()
            self.setLayout(self.layout)
            self.layout.addWidget(QLabel('dlkfjlakdsjflöaksdjflkjadslfjalsdkjflaskdjflasdjflkajsdflkajsd'))

            self.side_menu = WidgetSideMenu(self, 150, 10, 'left')
            for i in range(1, 11):
                button = QPushButton(f'Option {i:02}')
                self.side_menu.add_button(button)


    window = Window()
    window.show()
    app.exec()
