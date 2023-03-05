from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow

app = QApplication()
app.setWindowIcon(QIcon('resources/hcc-dispo_klein.png'))

window = MainWindow(app)

window.show()

app.exec()
