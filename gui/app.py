import logging
import time

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow

logging.basicConfig(filename='pony.log', level=logging.INFO,
                    format='%(created)f-%(asctime)s\n%(message)s\n')
logging.Formatter.converter = time.gmtime

app = QApplication()
app.setWindowIcon(QIcon('resources/hcc-dispo_klein.png'))

window = MainWindow(app)

window.show()

app.exec()
