from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow

app = QApplication()

window = MainWindow(app)

window.show()

app.exec()
