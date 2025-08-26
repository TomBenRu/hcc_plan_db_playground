from uuid import UUID

from uuid import UUID
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QSpinBox, QDialogButtonBox, \
    QPushButton

from database import db_services, schemas
from tools.helper_functions import setup_form_help, date_to_string


class DlgNumActorsApp(QDialog):
    def __init__(self, parent: QWidget, location_plan_period_id: UUID):
        super().__init__(parent)
        self.location_plan_period = db_services.LocationPlanPeriod.get(location_plan_period_id)
        self.parent = parent
        self._setup_ui()
        
        # Help-Integration
        setup_form_help(self, "num_actors_app", add_help_button=True)

    def _setup_ui(self):
        self.setWindowTitle(self.tr("Number of Employees per Event"))
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(20)
        self.layout_head = QVBoxLayout()
        self.layout_body = QFormLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_explanation = QLabel(self.tr("Please enter the number of employees per event."))
        self.layout_head.addWidget(self.lb_explanation)
        self.spinbox_num_actors = QSpinBox()
        self.layout_body.addRow(self.tr("Number of employees:"), self.spinbox_num_actors)
        self.spinbox_num_actors.setMinimum(0)
        self.spinbox_num_actors.setValue(self.location_plan_period.nr_actors)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.bt_reset = QPushButton(self.tr("Reset"))
        self.bt_reset.setToolTip(self.tr('Resets the number of employees to the facility default value.'))
        self.bt_reset.clicked.connect(self.reset_num_actors)
        self.button_box.addButton(self.bt_reset, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def reset_num_actors(self):
        self.spinbox_num_actors.setValue(self.location_plan_period.location_of_work.nr_actors)

    @property
    def num_actors(self) -> int:
        return self.spinbox_num_actors.value()


class DlgNumEmployeesEvent(QDialog):
    def __init__(self, parent: QWidget, event: schemas.EventShow):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Number of Employees'))

        self.event = event
        self._setup_ui()
        
        # Help-Integration
        setup_form_help(self, "num_actors_app", add_help_button=True)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(20)
        self.layout_head = QVBoxLayout()
        self.layout_body = QFormLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)
        self.lb_description = QLabel(
            self.tr('Enter the number of employees\n'
                    'for the event on {date} ({time_of_day})\n'
                    'in {location}:').format(
                date=date_to_string(self.event.date),
                time_of_day=self.event.time_of_day.name,
                location=self.event.location_plan_period.location_of_work.name_an_city
            )
        )
        self.layout_head.addWidget(self.lb_description)
        self.spin_num_employees = QSpinBox()
        self.spin_num_employees.setRange(0, 100)
        self.spin_num_employees.setValue(self.event.cast_group.nr_actors)
        self.layout_body.addRow(self.tr('Number of employees'), self.spin_num_employees)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def get_num_employees(self) -> int:
        return self.spin_num_employees.value()
