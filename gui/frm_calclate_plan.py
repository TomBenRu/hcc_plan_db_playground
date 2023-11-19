import pprint
import random
from uuid import UUID

from PySide6.QtCore import QThread, Signal, QObject, Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QMessageBox, \
    QProgressDialog, QFormLayout, QSpinBox

import sat_solver.solver_main
from commands import command_base_classes
from commands.database_commands import plan_commands, appointment_commands
from database import db_services, schemas


class DlgAskNrPlansToSave(QDialog):
    def __init__(self, parent: QWidget, poss_nr_plans: int):
        super().__init__(parent=parent)

        self.poss_nr_plans = poss_nr_plans

        self.layout = QFormLayout(self)
        self.lb_question = QLabel(f'Es wurden insgesamt {poss_nr_plans} berechnet.\n'
                                  f'Wie viele davon möchten Sie verwenden?')
        self.spin_nr_plans = QSpinBox()
        self.spin_nr_plans.setRange(1, poss_nr_plans)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addRow(self.lb_question)
        self.layout.addRow('Anzahl Pläne:', self.spin_nr_plans)
        self.layout.addRow(self.button_box)

    def get_nr_versions_to_use(self):
        return self.spin_nr_plans.value()



class SolverThread(QThread):
    finished = Signal(object)  # Signal emitted when the solver finishes

    def __init__(self, parent: QObject, plan_period_id: UUID):
        super().__init__(parent)
        self.plan_period_id = plan_period_id

    def run(self):
        # Call the solver function here
        schedule_versions = sat_solver.solver_main.solve(self.plan_period_id)
        self.finished.emit(schedule_versions)  # Emit the finished signal when the solver completes


class DlgCalculate(QDialog):
    def __init__(self, parent: QWidget, team_id: UUID):
        super().__init__(parent)

        self.team_id = team_id
        self.curr_plan_period_id: UUID | None = None
        self._created_plan_ids: list[UUID] = []

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()

        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_explanation = QLabel()
        self.layout_head.addWidget(self.lb_explanation)
        self.lb_combo_plan_periods = QLabel('Wählen Sie den entsprechenden Zeitraum für die Planung:')
        self.layout_body.addWidget(self.lb_combo_plan_periods)
        self.combo_plan_periods = QComboBox()
        self.layout_body.addWidget(self.combo_plan_periods)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                           | QDialogButtonBox.StandardButton.Cancel)
        self.layout_foot.addWidget(self.button_box)

        self.button_box.accepted.connect(self.calculate_schedule_versions)
        self.button_box.rejected.connect(self.reject)

        self.fill_out_widgets()

    def calculate_schedule_versions(self):
        if not self.curr_plan_period_id:
            QMessageBox.critical(self, 'Zeitraum', 'Bitte wählen Sie zuerst einen Zeitraum.')
            return

        # Create and configure the progress dialog
        progress_dialog = QProgressDialog(self)
        progress_dialog.setLabelText("Solving...")
        progress_dialog.setRange(0, 0)  # Indeterminate progress bar
        progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)  # Set as modal window
        progress_dialog.setFixedWidth(300)
        progress_dialog.setCancelButton(None)

        # Create the solver thread and connect the finished signal to close the progress dialog
        solver_thread = SolverThread(self, self.curr_plan_period_id)
        solver_thread.finished.connect(progress_dialog.close)
        solver_thread.finished.connect(lambda schedule_versions: self.save_plan_to_db(schedule_versions))
        solver_thread.finished.connect(self.accept)

        # Show the progress dialog and start the solver thread
        progress_dialog.show()
        solver_thread.start()

    def fill_out_widgets(self):
        team = db_services.Team.get(self.team_id)

        self.setWindowTitle(f'Einsatzplan-Erstellung {team.name}')

        self.lb_explanation.setText(f'Sie können automatisch für das Team {team.name}\n'
                                    f'Spielpläne für einen gewählten Planungszeitraum erstellen.')

        plan_periods = sorted([pp for pp in team.plan_periods if not pp.prep_delete],
                              key=lambda x: x.start, reverse=True)
        for plan_period in plan_periods:
            self.combo_plan_periods.addItem(f'{plan_period.start:%d.%m.%y} - {plan_period.end:%d.%m.%y}',
                                            plan_period.id)
        self.combo_plan_periods.currentIndexChanged.connect(self.combo_index_changed)
        self.combo_index_changed()

    def combo_index_changed(self):
        self.curr_plan_period_id = self.combo_plan_periods.currentData()

    def save_plan_to_db(self, schedule_versions: list[list[schemas.AppointmentCreate]]):
        plan_period = db_services.PlanPeriod.get(self.curr_plan_period_id)
        nr_versions_to_use = (len_versions := len(schedule_versions))
        if len_versions > 1:
            dlg = DlgAskNrPlansToSave(self, len_versions)
            if dlg.exec():
                nr_versions_to_use = dlg.get_nr_versions_to_use()

        versions_to_use = random.sample(schedule_versions, k=nr_versions_to_use)

        saved_plan_names = self.get_saved_plan_period_names()
        plan_base_name = f'{plan_period.start:%d.%m.%y}-{plan_period.end:%d.%m.%y}'
        new_first_plan_index = 0
        while f'{plan_base_name} ({new_first_plan_index})' in saved_plan_names:
            new_first_plan_index += 1

        for i, version in enumerate(versions_to_use, start=new_first_plan_index):
            version: list[schemas.AppointmentCreate]
            name_plan = f'{plan_base_name} ({i:0>2})'

            plan_create_command = plan_commands.Create(self.curr_plan_period_id, name_plan)
            self.controller.execute(plan_create_command)
            self._created_plan_ids.append(plan_create_command.plan.id)
            for appointment in version:
                self.controller.execute(
                    appointment_commands.Create(appointment, self._created_plan_ids[-1]))

    def get_saved_plan_period_names(self) -> set[str]:
        return {p.name for p in db_services.Plan.get_all_from__team(self.team_id)}

    def get_created_plan_ids(self):
        return self._created_plan_ids
