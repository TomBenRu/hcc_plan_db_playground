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
        # curr_team = db_services.Team.get(self.curr_team_id) if self.curr_team_id else None
        # new_team = db_services.Team.get(self.new_team_id) if self.new_team_id else None
        # if not curr_team or not curr_team.plan_periods:
        #     curr_team_earliest_date_to_change = datetime.date.today()
        # else:
        #     curr_team_last_plan_period_date = max(pp.end for pp in curr_team.plan_periods if not pp.prep_delete)
        #     curr_team_earliest_date_to_change = curr_team_last_plan_period_date + datetime.timedelta(days=1)
        #
        # if not new_team or not new_team.plan_periods:
        #     new_team_earliest_date_to_change = datetime.date.today()
        #
        # else:
        #     new_team_last_plan_period_date = max(pp.end for pp in new_team.plan_periods if not pp.prep_delete)
        #     new_team_earliest_date_to_change = new_team_last_plan_period_date + datetime.timedelta(days=1)
        #
        # earliest_date_to_change = max([curr_team_earliest_date_to_change, new_team_earliest_date_to_change])
        # text_explanation = f'Der früheste Zeitpunkt eines Wechsels ist der:\n' \
        #                            f'{earliest_date_to_change.strftime("%d.%m.%Y")}\n'
        #
        # self.dt_change_team.setDate(earliest_date_to_change)
        # self.dt_change_team.setMinimumDate(earliest_date_to_change)
        #
        # self.lb_explanation.setText(text_explanation)
        self.dt_change_team.setDate(datetime.date.today())
        self.dt_change_team.setMinimumDate(datetime.date.today())

    def accept(self) -> None:
        self.start_date_new_team = self.dt_change_team.date().toPython()
        super().accept()

