from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QSpinBox


class CustomSpinBox(QSpinBox):
    def __init__(self, values, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.values = values
        self.setRange(min(values), max(values))
        self.setValue(min(values))

    def stepBy(self, steps):
        current_index = self.values.index(self.value())
        new_index = current_index + steps
        if new_index < 0:
            new_index = 0
        elif new_index >= len(self.values):
            new_index = len(self.values) - 1
        self.setValue(self.values[new_index])


class CustomSpinBox2(QSpinBox):
    def __init__(self, disallowed_values, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.disallowed_values = disallowed_values

    def setMinimum(self, value):
        super().setMinimum(value)
        if self.value() in self.disallowed_values:
            new_value = self.value()
            while new_value in self.disallowed_values:
                new_value += 1
            self.setValue(new_value)

    def validate(self, text, pos):
        value = int(text)
        if value in self.disallowed_values:
            return QValidator.State.Invalid, text, pos
        else:
            return super().validate(text, pos)

    def fixup(self, text):
        value = int(text)
        if value in self.disallowed_values:
            if value > min(self.disallowed_values):
                self.setValue(value - 1)
            else:
                self.setValue(value + 1)

    def stepBy(self, steps):
        new_value = self.value() + steps
        while new_value in self.disallowed_values:
            if (steps > 0 and new_value >= self.maximum()) or (steps < 0 and new_value <= self.minimum()):
                return
            new_value += steps
        self.setValue(new_value)

app = QApplication([])

window = QWidget()
layout = QVBoxLayout(window)

spinbox1 = CustomSpinBox([2, 3, 5])
spinbox2 = CustomSpinBox2([1, 2, 4])
spinbox2.setMinimum(1)

layout.addWidget(spinbox1)
layout.addWidget(spinbox2)

window.show()

app.exec_()
