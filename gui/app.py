import json
import logging
import time

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyleFactory

from gui.main_window import MainWindow

logging.basicConfig(filename='pony.log', level=logging.INFO,
                    format='%(created)f-%(asctime)s\n%(message)s\n')
logging.Formatter.converter = time.gmtime

app = QApplication()
# app.setStyle(QStyleFactory.create('Fusion'))
app.setWindowIcon(QIcon('resources/hcc-dispo_klein.png'))

window = MainWindow(app)

screen_width, screen_height = app.primaryScreen().size().toTuple()

with open('config.json') as f:
    config_data = json.load(f)
if not config_data.get('screen_size'):
    config_data['screen_size'] = {}
config_data['screen_size']['width'], config_data['screen_size']['height'] = screen_width, screen_height
with open('config.json', 'w') as f:
    json.dump(config_data, f)

window.show()

app.exec()
