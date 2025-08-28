import string

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QValidator, QRegularExpressionValidator
from email_validator import validate_email, EmailNotValidError


class LettersAndSymbolsValidator(QValidator):
    def __init__(self, symbols: str, ascii_letters: bool, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._symbols = symbols
        self.ascii_letters = ascii_letters

    def validate(self, value, pos):
        if self.ascii_letters:
            if all((char in string.ascii_letters) or char in self._symbols for char in value):
                return QValidator.State.Acceptable, value, pos
            else:
                return QValidator.State.Invalid, value, pos
        if all(char in self._symbols for char in value):
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


def validate_email_str(email: str) -> dict[str, bool | str]:
    """
    Validiert eine E-Mail-Adresse.

    Args:
        email: Die zu validierende E-Mail-Adresse

    Returns:
        Dictionary mit dem Validierungs-Ergebnis und einem optionalen Fehler-Text
        {'valid': bool, 'error': str}
    """

    try:
        validate_email(email)
        return {'valid': True, 'error': ''}
    except EmailNotValidError as e:
        return {'valid': False, 'error': str(e)}
