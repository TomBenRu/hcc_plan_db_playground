import os
import time

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


def simulate_loading(splash: SplashScreen):
    alignment = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
    color = Qt.GlobalColor.darkBlue
    message = 'hcc-plan\nLoading...'
    for percent in range(0, 101, 5):
        splash.showMessage(f'{message} {percent}%', alignment, color)
        time.sleep(0.1)
