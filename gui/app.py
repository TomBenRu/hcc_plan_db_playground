import json
import logging
import os.path
import sys
import time

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyleFactory

from gui.main_window import MainWindow

logging.basicConfig(filename='pony.log', level=logging.INFO,
                    format='%(created)f-%(asctime)s\n%(message)s\n')
logging.Formatter.converter = time.gmtime

# sys.argv += ['-platform', 'windows:darkmode=1']

app = QApplication(sys.argv)
# app.setStyle(QStyleFactory.create('Fusion'))
app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'resources', 'hcc-dispo_klein.png')))

window = MainWindow(app)

screen_width, screen_height = app.primaryScreen().size().toTuple()

with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
    print(f"{os.path.join(os.path.dirname(__file__), 'config.json')=}")
    config_data = json.load(f)
if not config_data.get('screen_size'):
    config_data['screen_size'] = {}
config_data['screen_size']['width'], config_data['screen_size']['height'] = screen_width, screen_height
with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'w') as f:
    json.dump(config_data, f)

window.show()

# app.exec()
