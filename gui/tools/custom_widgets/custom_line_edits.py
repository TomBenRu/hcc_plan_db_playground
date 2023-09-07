from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLineEdit, QWidget


class LineEditWithCustomFont(QLineEdit):
    def __init__(self, *, parent: QWidget | None, font: QFont | None, letter_spacing: float | None):
        super().__init__(parent=parent)

        self.custom_font = font or self.font()
        if letter_spacing:
            self.custom_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, letter_spacing)
        self.setFont(self.custom_font)
