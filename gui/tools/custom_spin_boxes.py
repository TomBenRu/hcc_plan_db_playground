from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QSpinBox


class CustomSpinBoxAllowedValues(QSpinBox):
    def __init__(self, values: list[int], *args, **kwargs):
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


class CustomSpinBoxDisallowedValues(QSpinBox):
    def __init__(self, disallowed_values: list[int] | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.disallowed_values = disallowed_values or []

    def setDisallowedValues(self, disallowed_values: list[int]):
        self.disallowed_values = disallowed_values
        self.adjustValue()

    def setMinimum(self, value):
        super().setMinimum(value)
        if self.value() in self.disallowed_values:
            self.adjustValue()

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

    def adjustValue(self):
        new_value = self.value()
        while new_value in self.disallowed_values:
            new_value += 1
        self.setValue(new_value)
