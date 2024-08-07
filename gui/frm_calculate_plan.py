import datetime
import pprint
import random
from uuid import UUID

from PySide6.QtCore import QThread, Signal, QObject, Qt, Slot
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QMessageBox, \
    QProgressDialog, QFormLayout, QSpinBox

import gui.tools.helper_functions
import sat_solver.solver_main
from commands import command_base_classes
from commands.database_commands import plan_commands, appointment_commands
from database import db_services, schemas
from gui import frm_cast_group
from gui.observer import signal_handling


class DlgAskNrPlansToSave(QDialog):
    def __init__(self, parent: QWidget, poss_nr_plans: int):
        super().__init__(parent=parent)

        self.poss_nr_plans = poss_nr_plans

        self.layout = QFormLayout(self)
        self.lb_question = QLabel(f'Es wurden insgesamt {poss_nr_plans} Pläne berechnet.\n'
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
    finished = Signal(object, object)  # Signal emitted when the solver finishes

    def __init__(self, parent: QObject, plan_period_id: UUID):
        super().__init__(parent)
        self.plan_period_id = plan_period_id

    def run(self):
        # Call the solver function here
        schedule_versions, fixed_cast_conflicts = sat_solver.solver_main.solve(self.plan_period_id)
        self.finished.emit(schedule_versions, fixed_cast_conflicts)  # Emit the finished signal when the solver completes


class DlgProgress(QProgressDialog):
    def __init__(self, parent: QWidget, window_title: str, label_text: str,
                 minimum: int, maximum: int, cancel_button_text: str):
        super().__init__(label_text, cancel_button_text, minimum, maximum, parent)
        signal_handling.handler_solver.signal_progress.connect(self.update_progress)
        self.setWindowTitle(window_title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumDuration(minimum)
        self.setMaximum(maximum)

        self.canceled.connect(self.cancel_solving)

    @Slot(int)
    def update_progress(self, progress: int):
        self.setValue(progress)

    @Slot()
    def cancel_solving(self):
        signal_handling.handler_solver.cancel_solving()


class DlgCalculate(QDialog):
    def __init__(self, parent: QWidget, team_id: UUID):
        super().__init__(parent)

        signal_handling.handler_solver.signal_cancel_solving.connect(self.quit_solver_tread)

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

        self.button_box.accepted.connect(self._calculate_schedule_versions)
        self.button_box.rejected.connect(self.reject)

        self.fill_out_widgets()

    def _calculate_schedule_versions(self):
        if not self.curr_plan_period_id:
            QMessageBox.critical(self, 'Zeitraum', 'Bitte wählen Sie zuerst einen Zeitraum.')
            return

        if not db_services.Event.get_all_from__plan_period(self.curr_plan_period_id):
            QMessageBox.critical(self, 'Pläne erstellen',
                                 f'Es können keine Pläne für den Zeitraum {self.combo_plan_periods.currentText()} '
                                 f'erstellt werden.\n'
                                 f'Bitte wählen Sie zuerst Einsätze in den Einrichtungen aus.')
            return

        progress_dialog = DlgProgress(self, 'Plan wird berechnet', 'Berechnung läuft...', 0, 4, 'Abbrechen')
        progress_dialog.show()

        # Create the solver thread
        self.solver_thread = SolverThread(self, self.curr_plan_period_id)
        self.solver_thread.finished.connect(self.save_plan_to_db)
        self.solver_thread.finished.connect(self.accept)

        # Start the solver thread
        self.solver_thread.start()

    @Slot()
    def quit_solver_tread(self):
        sat_solver.solver_main.solver_quit()

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

    @Slot(object, object)
    def save_plan_to_db(self, schedule_versions: list[list[schemas.AppointmentCreate]] | None,
                        fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], int] | None):
        if schedule_versions is None and fixed_cast_conflicts is None:
            QMessageBox.critical(self, 'Fehler',
                                 'Es wurden keine Lösungen gefunden.\nUrsache könnte eine vorzeitiger Abbruch sein,\n'
                                 'oder die Vorgaben zur Planerstellung waren widersprüchlich.')
            self.reject()
            return
        if sum(fixed_cast_conflicts.values()) > 0:
            events = [db_services.Event.get(id_event) for (_, _, id_event), v in fixed_cast_conflicts.items() if v > 0]
            conflict_string = '\n'.join([f'  - {e.date:%d.%m.%y} ({e.time_of_day.name}) '
                                         f'{e.location_plan_period.location_of_work.name}:\n'
                                         f'      - Feste Besetzung: '
                                         f'{gui.tools.helper_functions.generate_fixed_cast_clear_text(e.cast_group.fixed_cast)}'
                                         for e in events])
            QMessageBox.critical(self, 'Fehler',
                                 f'Es wurden {sum(fixed_cast_conflicts.values())} Fixcast-Konflikte gefunden.\n'
                                 f'{conflict_string}')
            self.reject()
            return
        plan_period = db_services.PlanPeriod.get(self.curr_plan_period_id)
        nr_versions_to_use = (len_versions := len(schedule_versions))
        if len_versions > 1:
            dlg = DlgAskNrPlansToSave(self, len_versions)
            if dlg.exec():
                nr_versions_to_use = dlg.get_nr_versions_to_use()
            else:
                self.reject()
                return

        versions_to_use = random.sample(schedule_versions, k=nr_versions_to_use)

        saved_plan_names = self.get_saved_plan_period_names()
        plan_base_name = f'{plan_period.start:%d.%m.%y}-{plan_period.end:%d.%m.%y}'
        new_first_plan_index = 1

        for version in versions_to_use:
            while f'{plan_base_name} ({new_first_plan_index:0>2})' in saved_plan_names:
                new_first_plan_index += 1
            version: list[schemas.AppointmentCreate]
            name_plan = f'{plan_base_name} ({new_first_plan_index:0>2})'
            new_first_plan_index += 1

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
