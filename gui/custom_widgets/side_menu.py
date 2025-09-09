from typing import Literal, Iterable

from PySide6.QtGui import QMouseEvent, Qt
from PySide6.QtWidgets import (QWidget, QApplication, QVBoxLayout, QPushButton, QGraphicsView, QGraphicsScene,
                               QGraphicsProxyWidget, QHBoxLayout, QLabel, QScrollArea, QCheckBox, QLayout, QTableWidget)
from PySide6.QtCore import QPropertyAnimation, QPoint, QEasingCurve, QEvent, Slot, QTimer


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
        widgets: Iterable[QPushButton] = self.container_fields.findChildren(QWidget)
        for widget in widgets:
            widget.deleteLater()


class SlideInMenu(QWidget):
    def __init__(self, parent: QWidget, menu_size: int, snap_size: int,
                 align: Literal['left', 'right', 'top', 'bottom'],
                 content_margins: tuple[int, int, int, int] = (20, 20, 0, 20),
                 menu_background: tuple[int, ...] = (130, 205, 203, 100),
                 pinnable: bool = False):
        """
        Initializes a custom side/top/bottom menu widget.

        Args:
            parent: The parent widget.
            menu_size: The size (width for left/right, height for top/bottom) of the menu.
            snap_size: The snap size.
            align: The alignment of the menu.
            content_margins: The padding of containing widgets ('left', 'top', 'right', 'bottom')
            pinable: If True, adds a pin button to keep menu open when cursor leaves.

        Returns:
            None
        """
        super().__init__(parent)

        parent.resize_signal.connect(self.parent_resize_event)

        self.setObjectName('slide_in_menu')

        self.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background-color: rgba(255, 255, 255, 0);")

        self.parent = parent
        self.align = align
        self.menu_size = menu_size  # Width or Height depending on alignment
        self.snap_size = snap_size
        self.content_margins = content_margins
        self.menu_background = menu_background
        self.pinnable = pinnable
        self.pos_hide = 0
        self.pos_show = 0

        self.set_positions()

        self.color_buttons = '#e1e1e1'
        self.color_text = 'black'

        self._setup_ui()

        self.animation = QPropertyAnimation(self, b"pos")

        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_menu)

        # Stay-open Option: Menu bleibt offen auch wenn Cursor den Bereich verlässt
        self.stay_open = False

    def _setup_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.scroll_area_fields = QScrollArea()
        self.scroll_area_fields.setObjectName('scroll_area_fields')
        self.scroll_area_fields.setStyleSheet(
            f"QWidget#scroll_area_fields {{background-color: rgba{self.menu_background};}}")
        self.layout.addWidget(self.scroll_area_fields)
        self.container_fields = QWidget()
        self.container_fields.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.container_fields.setContentsMargins(*self.content_margins)
        self.scroll_area_fields.setWidget(self.container_fields)

        if self.align in ('left', 'right'):
            self.setGeometry(self.pos_hide, 0, self.menu_size, self.parent.height())
            self.container_fields.setMinimumWidth(self.menu_size - self.snap_size)
            self.layout_fields = QVBoxLayout(self.container_fields)
            self.layout_fields.setContentsMargins(0, 0, 0, 0)
            self.layout_fields.setAlignment(Qt.AlignmentFlag.AlignTop)
        else:
            self.setGeometry(0, self.pos_hide, self.parent.width(), self.menu_size)
            self.container_fields.setMinimumHeight(self.menu_size - self.snap_size
                                                   - self.content_margins[1] - self.content_margins[3])
            self.layout_fields = QHBoxLayout(self.container_fields)
            self.layout_fields.setContentsMargins(0, 0, 0, 0)
            self.layout_fields.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Pin-Button Setup wenn pinable=True
        if self.pinnable:
            self._create_pin_button()
            # Positionierung wird nach dem ersten Show-Event gesetzt

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

    @Slot()
    def parent_resize_event(self):
        """Handle resizing of the parent widget."""
        self.set_positions()
        if self.align in ['left', 'right']:
            self.setGeometry(self.pos_hide, 0, self.menu_size, self.parent.height())
        else:
            self.setGeometry(0, self.pos_hide, self.parent.width(), self.menu_size)
            if len(self.widgets_of_container) == 1 and isinstance(self.widgets_of_container[0], QTableWidget):
                self._adjust_container_size()
        
        # Pin-Button repositionieren nach Größenänderung
        if self.pinnable:
            self._position_pin_button()

    def enterEvent(self, event: QMouseEvent) -> None:
        """Show the menu when the mouse enters."""
        self._hide_timer.stop()  # Timer stoppen falls aktiv
        self.show_menu()

    def leaveEvent(self, event: QEvent) -> None:
        """Hide the menu when the mouse leaves with delay (if stay_open=False)."""
        if not self.stay_open:  # Nur verstecken wenn nicht stay_open
            self._hide_timer.start(500)  # 500ms Verzögerung

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

    def set_stay_open(self, stay_open: bool):
        """
        Enable/disable automatic hiding when cursor leaves menu.
        
        Args:
            stay_open: If True, menu stays open when cursor leaves. 
                      If False, menu auto-hides after 500ms delay.
        """
        self.stay_open = stay_open

    def _create_pin_button(self):
        """Erstellt kleinen Pin-Button in der Menü-Ecke für Stay-Open-Funktionalität."""
        # Kleiner Icon-Only-Button (20x20px)
        self.bt_pin_menu = QPushButton("📌")
        self.bt_pin_menu.setObjectName('bt_pin_menu')
        self.bt_pin_menu.setParent(self)  # Direkt auf SlideInMenu, nicht im Layout
        self.bt_pin_menu.setFixedSize(20, 20)
        self.bt_pin_menu.setCheckable(True)
        self.bt_pin_menu.setToolTip(self.tr("Keep menu open"))
        self.bt_pin_menu.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 150);
                border: 1px solid #ccc;
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 200);
            }
            QPushButton:checked {
                background-color: #006d6d;
                color: white;
                border: 1px solid #004d4d;
            }
        """)
        self.bt_pin_menu.toggled.connect(self._pin_button_toggled)

    def _position_pin_button(self):
        """Positioniert den Pin-Button in der entsprechenden Ecke basierend auf Menu-Alignment."""
        if not hasattr(self, 'bt_pin_menu'):
            return
            
        # Ecken-Positionierung basierend auf Alignment
        margin = 5
        if self.align == 'left':
            # Rechts-oben
            self.bt_pin_menu.move(self.width() - 20 - margin, margin)
        elif self.align == 'right':
            # Links-oben
            self.bt_pin_menu.move(margin, margin)
        elif self.align == 'bottom':
            # Links-oben (vom Bottom-Menu aus gesehen)
            self.bt_pin_menu.move(margin, margin)
        elif self.align == 'top':
            # Links-unten (vom Top-Menu aus gesehen) 
            self.bt_pin_menu.move(margin, self.height() - 20 - margin)
        
        # Button sichtbar machen
        self.bt_pin_menu.show()

    def showEvent(self, event):
        """Wird aufgerufen wenn das Menu angezeigt wird - positioniert Pin-Button."""
        super().showEvent(event)
        if self.pinnable:
            self._position_pin_button()
    
    def resizeEvent(self, event):
        """Wird aufgerufen wenn das Menu in der Größe verändert wird - repositioniert Pin-Button."""
        super().resizeEvent(event)
        if self.pinnable:
            self._position_pin_button()

    def _pin_button_toggled(self, checked: bool):
        """Handler für Pin-Button Toggle - aktiviert/deaktiviert Stay-Open-Modus."""
        self.set_stay_open(checked)

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
        self._adjust_container_size()

    def add_check_box(self, check_box: QCheckBox):
        """Add a checkbox to the menu."""
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {self.color_buttons}; color: {self.color_text};")
        widget.setContentsMargins(10, 2, 10, 2)
        widget_layout = QVBoxLayout(widget)
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.addWidget(check_box)
        self.layout_fields.addWidget(widget)
        self._adjust_container_size()

    def add_widget(self, widget: QWidget):
        self.layout_fields.addWidget(widget)
        self._adjust_container_size()

    def _adjust_container_size(self):
        """Adjust the container size based on the number of child widgets."""
        self.widgets_of_container = [w for w in self.container_fields.children()
                                     if isinstance(w, QWidget) and w.parent() == self.container_fields]
        if self.align in ['left', 'right']:
            self.container_fields.setMinimumHeight(
                sum(w.sizeHint().height() for w in self.widgets_of_container)
                + self.container_fields.layout().spacing() * (len(self.widgets_of_container) - 1)
                + sum((w.contentsMargins().top() + w.contentsMargins().bottom()) for w in self.widgets_of_container)
                + self.content_margins[1] + self.content_margins[3]
            )
        else:
            if len(self.widgets_of_container) == 1 and isinstance(self.widgets_of_container[0], QTableWidget):
                # Damit die Breite der Tabelle auf die Breite des Containers begrenzt ist
                # und somit der horizontale Scrollbalken der Tabelle erscheint.
                self.container_fields.setFixedWidth(self.width() - 10)
                return
            table_width = 0
            for widget in self.widgets_of_container:
                if isinstance(widget, QTableWidget):
                    # Breite des horizontalen Headers des QTableWidget ermitteln
                    header_width = widget.horizontalHeader().length()  # Gesamtlänge der Spalten
                    table_width += header_width + widget.verticalHeader().width()
            self.container_fields.setMinimumWidth(
                sum(w.sizeHint().width() for w in self.widgets_of_container if not isinstance(w, QTableWidget))
                + self.container_fields.layout().spacing() * (len(self.widgets_of_container) - 1)
                + sum((w.contentsMargins().left() + w.contentsMargins().right()) for w in self.widgets_of_container)
                + self.content_margins[0] + self.content_margins[2]
                + table_width or 0
            )

    def delete_all_buttons(self):
        """Delete all buttons from the menu."""
        buttons: Iterable[QPushButton] = self.findChildren(QPushButton)
        for button in buttons:
            if button.objectName() == 'bt_pin_menu':
                continue
            button.deleteLater()
