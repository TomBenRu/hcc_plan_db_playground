import logging
import os.path
import sys
import time

from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.custom_widgets.splash_screen import SplashScreen
from gui.tools.screen import Screen

logging.basicConfig(filename='pony.log', level=logging.INFO,
                    format='%(created)f-%(asctime)s\n%(message)s\n')
logging.Formatter.converter = time.gmtime

# sys.argv += ['-platform', 'windows:darkmode=1']

app = QApplication(sys.argv)

# Bug ab Pyside6 Version 6.7: setForeground funktioniert nicht. Wird mit Version 6.7.3 gefixt.
# Workaround: app.setStyle('Fusion') oder app.setStyle('Windows')
app.setStyle('Fusion')

app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'resources', 'hcc-dispo_klein.png')))

Screen.set_screen_size()

window = MainWindow(app, Screen.screen_width, Screen.screen_height)

window.show()

alignment = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
color = Qt.GlobalColor.darkBlue

splash = SplashScreen()

message = 'hcc-plan\nLoading...'
for percent in range(0, 101, 5):
    splash.showMessage(f'{message} {percent}%', alignment, color)
    time.sleep(0.08)

splash.finish(window)

# app.exec()
