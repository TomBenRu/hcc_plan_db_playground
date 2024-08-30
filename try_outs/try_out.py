import time

from PySide6.QtCore import Slot, Signal, QObject
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton


class SignalHandler(QObject):
    custom_signal = Signal()

    def emit_custom_signal(self):
        self.custom_signal.emit()


signal_handler = SignalHandler()


class Window(QWidget):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent=parent)
        signal_handler.custom_signal.connect(self.custom_signal_emitted)
        self.layout = QVBoxLayout(self)
        self.button = QPushButton('send')
        self.layout.addWidget(self.button)
        self.button.clicked.connect(self.button_clicked)

    @Slot()
    def button_clicked(self):
        signal_handler.custom_signal.emit()

    @Slot()
    def custom_signal_emitted(self):
        print('custom signal received')


if __name__ == '__main__':
    app = QApplication()
    window = Window()
    window.show()
    app.exec()

