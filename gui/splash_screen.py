import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSplashScreen


class SplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Splash Screen')
        self.resize(300, 200)

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: white; border-radius: 10px; border: 2px solid blue;")
        self.setLayout(self.layout)

        self.lb_title = QLabel('HCC-Planer')
        self.lb_title.setContentsMargins(10, 10, 10, 10)

        self.lb_title_font = self.lb_title.font()
        self.lb_title_font.setPointSize(16)
        self.lb_title_font.setBold(True)
        self.lb_title.setFont(self.lb_title_font)

        self.layout.addWidget(self.lb_title)

        pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'resources', 'hcc-dispo_klein.png'))
        pixmap.setDevicePixelRatio(0.5)
        self.setPixmap(pixmap)

        self.show()
