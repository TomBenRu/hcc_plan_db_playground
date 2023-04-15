from PySide6.QtGui import QMouseEvent, QResizeEvent, Qt
from PySide6.QtWidgets import QWidget, QApplication, QVBoxLayout, QPushButton, QGraphicsView, QGraphicsScene, \
    QGraphicsProxyWidget, QHBoxLayout, QLabel, QSizePolicy, QSpacerItem, QScrollArea
from PySide6.QtCore import QPropertyAnimation, QPoint, QEasingCurve, QEvent

app = QApplication()


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
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        #self.setStyleSheet("background-color:red;border-radius:0px;")
        self.setGeometry(-110, 0, 120, 600)
        self.setContentsMargins(0, 0, 0, 0)

        self.parent = parent

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.scrollarea_fields = QScrollArea()
        self.scrollarea_fields.setStyleSheet("background-color:red;")
        self.layout.addWidget(self.scrollarea_fields)
        self.container_fields = QLabel()
        self.container_fields.setMinimumWidth(95)
        self.scrollarea_fields.setWidget(self.container_fields)

        self.layout_fields = QVBoxLayout(self.container_fields)

        self.layout_fields.setAlignment(Qt.AlignTop)
        for i in range(1, 11):
            button = QPushButton(f'Option {i:02}')
            button.setStyleSheet("background-color:blue;")
            self.layout_fields.addWidget(button)

        self.container_fields.setMinimumHeight(len(self.container_fields.children()) * 30)

        #self.layout_fields.addStretch()

        # self.lb_show_side_menu = QLabel('schow')
        # self.lb_show_side_menu.setMinimumWidth(len(self.container_fields.children()) * 30)
        # self.rot_container = RotatableContainer(self.lb_show_side_menu, -90)
        # self.layout.addWidget(self.rot_container)

        # self.bt_show_sidemenu = QPushButton('Sidemenu')
        # self.bt_show_sidemenu.setMinimumWidth(400)
        # self.bt_show_sidemenu.clicked.connect(self.animate_sidemenu)
        # self.rot_container = RotatableContainer(self.bt_show_sidemenu, -90)
        # self.layout.addWidget(self.rot_container)

        self.anim = QPropertyAnimation(self, b"pos")

        parent.resizeEvent = lambda e: self.resize(self.width(), parent.height())

    def enterEvent(self, event: QMouseEvent) -> None:
        if self.pos().x() < 0:
            self.animate_sidemenu()

    def leaveEvent(self, event: QEvent) -> None:
        self.animate_sidemenu()

    def animate_sidemenu(self):
        if self.pos().x() < 0:
            self.show_sidemenu()
        else:
            self.hide_siedemenu()

    def show_sidemenu(self):
        self.anim.setEasingCurve(QEasingCurve.OutBounce)
        self.anim.setEndValue(QPoint(0, 0))
        self.anim.setDuration(750)
        self.anim.start()

    def hide_siedemenu(self):
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.setEndValue(QPoint(-110, 0))
        self.anim.setDuration(750)
        self.anim.start()


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(600, 600)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.side_menu = WidgetSideMenu(self)

    # def resizeEvent(self, event: QResizeEvent) -> None:
    #     print(event.size().height())
    #     self.child.resize(self.child.size().width(), event.size().height())


window = Window()
window.show()
app.exec()
