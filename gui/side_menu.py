from typing import Literal

from PySide6.QtGui import QMouseEvent, Qt
from PySide6.QtWidgets import QWidget, QApplication, QVBoxLayout, QPushButton, QGraphicsView, QGraphicsScene, \
    QGraphicsProxyWidget, QHBoxLayout, QLabel, QScrollArea
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

        self.setContentsMargins(0, 0, 0, 0)

        self.parent = parent
        self.align = align
        self.menu_width = menu_width
        self.snap_width = snap_width
        self.pos_x_hide = 0
        self.pos_x_show = 0

        self.set_positions()
        self.setGeometry(self.pos_x_hide, 0, menu_width, 600)
        self.color_buttons = '#dfdfdf'

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.scrollarea_fields = QScrollArea()
        self.scrollarea_fields.setStyleSheet("background-color:#82cdcb;")
        self.layout.addWidget(self.scrollarea_fields)
        self.container_fields = QLabel()
        self.container_fields.setMinimumWidth(menu_width - 20)
        self.container_fields.setContentsMargins(20, 20, 0, 20)
        self.scrollarea_fields.setWidget(self.container_fields)

        self.layout_fields = QVBoxLayout(self.container_fields)

        self.layout_fields.setAlignment(Qt.AlignTop)

        self.container_fields.setMinimumHeight(len(self.container_fields.children()) * 30)

        self.anim = QPropertyAnimation(self, b"pos")

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
        self.anim.setEasingCurve(QEasingCurve.OutBounce)
        self.anim.setEndValue(QPoint(self.pos_x_show, 0))
        self.anim.setDuration(750)
        self.anim.start()

    def hide_siedemenu(self):
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.setEndValue(QPoint(self.pos_x_hide, 0))
        self.anim.setDuration(750)
        self.anim.start()

    def add_button(self, button: QPushButton):
        button.setStyleSheet(f"background-color: {self.color_buttons};")
        self.layout_fields.addWidget(button)
        self.container_fields.setMinimumHeight(len(self.container_fields.children()) * 30)


if __name__ == '__main__':
    app = QApplication()

    class Window(QWidget):
        def __init__(self):
            super().__init__()
            self.resize(600, 600)
            self.layout = QVBoxLayout()
            self.setLayout(self.layout)

            self.side_menu = WidgetSideMenu(self, 150, 10, 'right')
            for i in range(1, 11):
                button = QPushButton(f'Option {i:02}')
                self.side_menu.add_button(button)


    window = Window()
    window.show()
    app.exec()
