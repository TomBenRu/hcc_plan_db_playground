from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel, QLineEdit, QMessageBox

from database import db_services


class FrmNewTeam(QDialog):
    def __init__(self, parent):
        super().__init__(parent=parent)
        self.setWindowTitle('Neues Team')

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.save_team)
        self.button_box.rejected.connect(self.reject)

        self.lb_team_name = QLabel('Wie soll der Name des Teams sein?')
        self.le_team_name = QLineEdit()

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)
        self.setLayout(self.layout)

        self.layout.addWidget(self.lb_team_name)
        self.layout.addWidget(self.le_team_name)
        self.layout.addWidget(self.button_box)

    def save_team(self):
        dlg = QMessageBox()
        try:
            team = db_services.new_team(self.le_team_name.text(), 'Humor Hilft Heilen')
            dlg.setText(f'{team}')
        except Exception as e:
            dlg.setText(f'Fehler: {e}')
        dlg.exec()
        self.close()



