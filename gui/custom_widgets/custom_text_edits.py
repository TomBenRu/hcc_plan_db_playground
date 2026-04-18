from PySide6.QtCore import Signal
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QTextEdit, QWidget


class NotesTextEdit(QTextEdit):
    """QTextEdit, das editing_finished beim Fokus-Verlust emittiert.

    Verwendung für Notizen-Felder, die erst am Ende einer Bearbeitung (statt pro
    Tastendruck) persistiert werden sollen — vermeidet DB-Roundtrip pro Keystroke
    und Undo-Spam.
    """

    editing_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self.editing_finished.emit()
