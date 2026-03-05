import datetime
from typing import Any

from PySide6.QtCore import QDate, QCoreApplication
from PySide6.QtWidgets import QDialog, QVBoxLayout, QCalendarWidget, QDialogButtonBox, QWidget, QMessageBox

from gui.custom_widgets.custom_date_and_time_edit import CalendarLocale


class TeamAssignmentDateDialog(QDialog):
    def __init__(self, parent: QWidget, current_date: datetime.date | None = None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Team-Zuweisungsdatum")
        self.setMinimumWidth(300)
        self.current_date = current_date

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.calendar = CalendarLocale()
        layout.addWidget(self.calendar)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        if self.current_date:
            self.calendar.setSelectedDate(QDate(self.current_date.year, self.current_date.month, self.current_date.day))
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)


def show_email_send_result(parent: QWidget, stats: dict[str, Any]) -> bool:
    """
    Zeigt das Ergebnis des E-Mail-Versands in einem Dialog an.

    Bekannte Fehlercodes in stats['error']:
      'smtp_authentication_error' – Anmeldedaten ungültig
      'rate_limit_exceeded'       – Rate-Limit erreicht

    Returns:
        True wenn der aufrufende Dialog sich schließen soll, False wenn nicht (vollständiger Fehlschlag).
    """
    success_count = stats.get('success', 0)
    failed_count = stats.get('failed', 0)
    error_code = stats.get('error')

    if error_code == "smtp_authentication_error":
        error_text = QCoreApplication.translate(
            "EmailSender",
            "Authentication error: Username or password is invalid.\n"
            "Please check your email configuration.",
            None)
    elif error_code == "rate_limit_exceeded":
        error_text = QCoreApplication.translate(
            "EmailSender",
            "Rate limit reached: Too many emails sent in a short period of time.",
            None)
    elif error_code:
        error_text = (QCoreApplication.translate("EmailSender", "Technical error: ", None)
                      + error_code)
    else:
        error_text = None

    if failed_count > 0 and success_count == 0:
        msg = QCoreApplication.translate("EmailSender", "Email sending failed.", None)
        if error_text:
            msg += "\n\n" + error_text
        QMessageBox.critical(
            parent,
            QCoreApplication.translate("EmailSender", "Email sending failed", None),
            msg)
        return False  # Dialog bleibt offen

    elif failed_count > 0:
        msg = (QCoreApplication.translate("EmailSender", "Successfully sent: {}", None).format(success_count)
               + "\n"
               + QCoreApplication.translate("EmailSender", "Failed: {}", None).format(failed_count))
        if error_text:
            msg += "\n\n" + error_text
        QMessageBox.warning(
            parent,
            QCoreApplication.translate("EmailSender", "Email sending partially failed", None),
            msg)
        return True

    else:
        QMessageBox.information(
            parent,
            QCoreApplication.translate("EmailSender", "Email sending completed", None),
            QCoreApplication.translate("EmailSender", "All emails sent successfully: {}", None).format(success_count))
        return True
