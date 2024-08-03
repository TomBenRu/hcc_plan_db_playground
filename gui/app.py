import logging
import os.path
import sys
import time

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from gui.custom_widgets.splash_screen import SplashScreen
from gui.tools import proof_only_one_instance

app = QApplication(sys.argv)
app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'resources', 'hcc-dispo_klein.png')))

# proof_only_one_instance:
if not proof_only_one_instance.check():
    QMessageBox.critical(None, "HCC Dispo", "hcc-dispo wird bereits ausgeführt.\n"
                                            "Sie können nur eine Instanz des Programms öffnen.")
    sys.exit(0)

splash = SplashScreen()
splash.show()
splash.simulate_loading()


from gui.main_window import MainWindow
from gui.tools.screen import Screen

logging.basicConfig(filename='pony.log', level=logging.INFO,
                    format='%(created)f-%(asctime)s\n%(message)s\n')
logging.Formatter.converter = time.gmtime

# sys.argv += ['-platform', 'windows:darkmode=1']

# Bug ab Pyside6 Version 6.7: setForeground funktioniert nicht. Wird mit Version 6.7.3 gefixt.
# Workaround: app.setStyle('Fusion') oder app.setStyle('Windows')
app.setStyle('Fusion')

Screen.set_screen_size()
window = MainWindow(app, Screen.screen_width, Screen.screen_height)

window.show()
splash.finish(window)
