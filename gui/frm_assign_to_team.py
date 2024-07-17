import datetime
from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QDateEdit, QDialogButtonBox, QLabel

from database import db_services


class DlgAssignDate(QDialog):
    def __init__(self, parent: QWidget, curr_team_id: UUID | None, new_team_id: UUID | None):
        super().__init__(parent)

        self.setWindowTitle('Team-Wechsel')

        self.curr_team_id = curr_team_id
        self.new_team_id = new_team_id

        self.start_date_new_team: datetime.date | None = None

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(20)
        self.layout_head = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout_body = QFormLayout()
        self.layout.addLayout(self.layout_body)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_foot)

        self.lb_explanation = QLabel()
        self.layout_head.addWidget(self.lb_explanation)

        self.dt_change_team = QDateEdit()
        self.layout_body.addRow('Beginn der Änderung:', self.dt_change_team)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

        self.setup_data()

    def setup_data(self):
        curr_team = db_services.Team.get(self.curr_team_id) if self.curr_team_id else None
        new_team = db_services.Team.get(self.new_team_id) if self.new_team_id else None

        text_explanation = f'Hier kommt noc eine Info rein, ob der Wechsel während laufenden Planperioden stattfindet.\n'

        self.lb_explanation.setText(text_explanation)

        self.dt_change_team.setDate(datetime.date.today())
        self.dt_change_team.setMinimumDate(datetime.date.today())

    def accept(self) -> None:
        self.start_date_new_team = self.dt_change_team.date().toPython()
        super().accept()

