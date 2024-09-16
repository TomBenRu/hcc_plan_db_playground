import string

from PySide6.QtGui import QValidator


class LettersAndSymbolsValidator(QValidator):
    def __init__(self, symbols, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._symbols = symbols

    def validate(self, value, pos):
        if all((char in string.ascii_letters) or char in self._symbols for char in value):
            return QValidator.State.Acceptable, value, pos
        else:
            return QValidator.State.Invalid, value, pos


class IntAndFloatValidator(QValidator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self, text, pos):
        try:
            float(text)
            return QValidator.State.Acceptable, text, pos
        except ValueError:
            return QValidator.State.Invalid, text, pos


class IntValidator(QValidator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self, text, pos):
        try:
            int(text)
            return QValidator.State.Acceptable, text, pos
        except ValueError:
            return QValidator.State.Invalid, text, pos
