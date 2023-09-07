from PySide6.QtGui import QValidator


class LettersAndSymbolsValidator(QValidator):
    def __init__(self, symbols, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._symbols = symbols

    def validate(self, value, pos):
        if all(char.isalpha() or char in self._symbols for char in value):
            return QValidator.State.Acceptable, value, pos
        else:
            return QValidator.State.Invalid, value, pos
