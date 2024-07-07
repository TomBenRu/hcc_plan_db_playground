from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
import sys


class Person:
    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age

    def __repr__(self):
        return f'Person({self.name}, {self.age})'


class MyCustomSignal(QObject):
    signal1 = Signal(Person, int)
    signal2 = Signal()


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.custom_signal = MyCustomSignal()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('My Window')
        self.setGeometry(300, 300, 300, 200)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.label = QLabel('Label 1')
        self.layout.addWidget(self.label)
        self.button = QPushButton('Button 1')
        self.button.clicked.connect(lambda: self.custom_signal.signal1.emit(Person('Tom', 25), 1))
        self.button.clicked.connect(self.custom_signal.signal2.emit)
        self.custom_signal.signal1.connect(self.label_set_text)
        self.custom_signal.signal2.connect(self.button_clicked)

        self.button.clicked.connect(lambda: self.button_clicked(button=self.button))
        self.layout.addWidget(self.button)

        self.show()

    @Slot(Person, int, result=None)
    def label_set_text(self, person: Person, position: int):
        self.label.setText(f'{person=}, {type(person)=}, {position=}')
        print(f'{person=}, {type(person)=}, {position=}')

    @Slot()
    def button_clicked(self, *args, **kwargs):
        print(f'Button clicked, {args=}, {kwargs=}')
        if button := kwargs.get('button'):
            print(f'{button=}')
            button.setStyleSheet("background-color: red;")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MyWindow()
    sys.exit(app.exec())
