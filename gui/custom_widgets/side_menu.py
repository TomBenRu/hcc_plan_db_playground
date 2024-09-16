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


class WidgetSideMenuOld(QWidget):
    def __init__(self, parent: QWidget, menu_size: int, snap_size: int, align: Literal['left', 'right']):
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
        self.menu_size = menu_size
        self.snap_width = snap_size
        self.pos_hide = 0
        self.pos_show = 0

        self.set_positions()
        if self.align in ['left', 'right']:
            self.setGeometry(self.pos_hide, 0, menu_size, self.parent.height())
        else:
            self.setGeometry(0, self.pos_hide, self.parent.width(), menu_size)
        self.color_buttons = '#e1e1e1'
        self.color_text = 'black'

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.scrollarea_fields = QScrollArea()
        self.scrollarea_fields.setStyleSheet("background-color: rgba(130, 205, 203, 100);")
        self.layout.addWidget(self.scrollarea_fields)
        self.container_fields = QWidget()
        self.container_fields.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.container_fields.setMinimumWidth(menu_size - 20)
        self.container_fields.setContentsMargins(20, 20, 0, 20)
        self.scrollarea_fields.setWidget(self.container_fields)

        self.layout_fields = QVBoxLayout(self.container_fields)

        self.layout_fields.setAlignment(Qt.AlignTop)

        self.container_fields.setMinimumHeight(len(self.container_fields.children()) * 30 + 30)

        self.animation = QPropertyAnimation(self, b"pos")

        parent.resizeEvent = self.parent_resize_event

    def set_positions(self):
        if self.align == 'left':
            self.pos_hide = self.snap_width - self.menu_size
            self.pos_show = 0
        elif self.align == 'right':
            self.pos_hide = self.parent.width() - self.snap_width
            self.pos_show = self.parent.width() - self.menu_size

    def parent_resize_event(self, e):
        self.set_positions()
        self.setGeometry(self.pos_hide, 0, self.menu_size, self.parent.height())

    def enterEvent(self, event: QMouseEvent) -> None:
        self.show_menu()

    def leaveEvent(self, event: QEvent) -> None:
        self.hide_menu()

    def show_menu(self):
        self.animation.setEasingCurve(QEasingCurve.OutBounce)
        self.animation.setEndValue(QPoint(self.pos_show, 0))
        self.animation.setDuration(750)
        self.animation.start()

    def hide_menu(self):
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.setEndValue(QPoint(self.pos_hide, 0))
        self.animation.setDuration(750)
        self.animation.start()

    def set_menu_size(self, width: int):
        self.menu_size = width
        self.setGeometry(self.pos_hide, 0, self.menu_size, self.parent.height())

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


class WidgetSideMenu(QWidget):
    def __init__(self, parent: QWidget, menu_size: int, snap_size: int,
                 align: Literal['left', 'right', 'top', 'bottom'],
                 content_margins: tuple[int, int, int, int] = (20, 20, 0, 20)):
        super().__init__(parent)
        """
        Initializes a custom side/top/bottom menu widget.

        Args:
            parent (QWidget): The parent widget.
            menu_size (int): The size (width for left/right, height for top/bottom) of the menu.
            snap_size (int): The snap size.
            align (Literal['left', 'right', 'top', 'bottom']): The alignment of the menu.

        Returns:
            None
        """
        self.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background-color: rgba(255, 255, 255, 0);")

        self.parent = parent
        self.align = align
        self.menu_size = menu_size  # Width or Height depending on alignment
        self.snap_size = snap_size
        self.pos_hide = 0
        self.pos_show = 0

        self.set_positions()

        self.color_buttons = '#e1e1e1'
        self.color_text = 'black'

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.scrollarea_fields = QScrollArea()
        self.scrollarea_fields.setStyleSheet("background-color: rgba(130, 205, 203, 100);")
        self.layout.addWidget(self.scrollarea_fields)
        self.container_fields = QWidget()
        self.container_fields.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.container_fields.setContentsMargins(*content_margins)
        self.scrollarea_fields.setWidget(self.container_fields)

        if align in ('left', 'right'):
            self.setGeometry(self.pos_hide, 0, menu_size, self.parent.height())
            self.container_fields.setMinimumWidth(menu_size - 20)
            self.layout_fields = QVBoxLayout(self.container_fields)
            self.layout_fields.setAlignment(Qt.AlignmentFlag.AlignTop)
        else:
            self.setGeometry(0, self.pos_hide, self.parent.width(), menu_size)
            self.container_fields.setMinimumHeight(menu_size - 20)
            self.layout_fields = QHBoxLayout(self.container_fields)
            self.layout_fields.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.animation = QPropertyAnimation(self, b"pos")

        parent.resizeEvent = self.parent_resize_event

    def set_positions(self):
        """Set the hide and show positions based on the alignment."""
        if self.align == 'left':
            self.pos_hide = self.snap_size - self.menu_size
            self.pos_show = 0
        elif self.align == 'right':
            self.pos_hide = self.parent.width() - self.snap_size
            self.pos_show = self.parent.width() - self.menu_size
        elif self.align == 'top':
            self.pos_hide = self.snap_size - self.menu_size
            self.pos_show = 0
        elif self.align == 'bottom':
            self.pos_hide = self.parent.height() - self.snap_size
            self.pos_show = self.parent.height() - self.menu_size

    def parent_resize_event(self, e):
        """Handle resizing of the parent widget."""
        self.set_positions()
        if self.align in ['left', 'right']:
            self.setGeometry(self.pos_hide, 0, self.menu_size, self.parent.height())
        else:
            self.setGeometry(0, self.pos_hide, self.parent.width(), self.menu_size)

    def enterEvent(self, event: QMouseEvent) -> None:
        """Show the menu when the mouse enters."""
        self.show_menu()

    def leaveEvent(self, event: QEvent) -> None:
        """Hide the menu when the mouse leaves."""
        self.hide_menu()

    def show_menu(self):
        """Show the menu with an animation."""
        self.animation.setEasingCurve(QEasingCurve.OutBounce)
        if self.align in ['left', 'right']:
            self.animation.setEndValue(QPoint(self.pos_show, 0))
        else:
            self.animation.setEndValue(QPoint(0, self.pos_show))
        self.animation.setDuration(750)
        self.animation.start()

    def hide_menu(self):
        """Hide the menu with an animation."""
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        if self.align in ['left', 'right']:
            self.animation.setEndValue(QPoint(self.pos_hide, 0))
        else:
            self.animation.setEndValue(QPoint(0, self.pos_hide))
        self.animation.setDuration(750)
        self.animation.start()

    def set_menu_size(self, size: int):
        """Set the width (left/right) or height (top/bottom) of the menu."""
        self.menu_size = size
        if self.align in ['left', 'right']:
            self.setGeometry(self.pos_hide, 0, self.menu_size, self.parent.height())
        else:
            self.setGeometry(0, self.pos_hide, self.parent.width(), self.menu_size)

    def add_button(self, button: QPushButton):
        """Add a button to the menu."""
        button.setStyleSheet(f"background-color: {self.color_buttons}; color: {self.color_text};")
        self.layout_fields.addWidget(button)
        self.adjust_container_size()

    def add_check_box(self, check_box: QCheckBox):
        """Add a checkbox to the menu."""
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {self.color_buttons}; color: {self.color_text};")
        widget.setContentsMargins(10, 2, 10, 2)
        widget_layout = QVBoxLayout(widget)
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.addWidget(check_box)
        self.layout_fields.addWidget(widget)
        self.adjust_container_size()

    def adjust_container_size(self):
        """Adjust the container size based on the number of child widgets."""
        if self.align in ['left', 'right']:
            self.container_fields.setMinimumHeight(len(self.container_fields.children()) * 30 + 30)
        else:
            self.container_fields.setMinimumWidth(len(self.container_fields.children()) * 100 + 30)

    def delete_all_buttons(self):
        """Delete all buttons from the menu."""
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
