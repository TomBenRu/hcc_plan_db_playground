import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSplashScreen


class SplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__()

        font = self.font()
        font.setPointSize(16)
        font.setBold(True)
        self.setFont(font)
        parent_dir = os.path.dirname(os.path.dirname(__file__))
        pixmap = QPixmap(os.path.join(parent_dir, 'resources', 'hcc-dispo_klein_splash.png'))
        pixmap.setDevicePixelRatio(0.5)
        self.setPixmap(pixmap)

        self.show()
