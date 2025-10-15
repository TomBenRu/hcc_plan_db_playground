import datetime
from uuid import UUID

from PySide6.QtCore import QThread, Signal, QObject, Slot, Qt, QThreadPool
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QMessageBox, \
    QFormLayout, QSpinBox, QHBoxLayout, QGroupBox

import tools
from commands import command_base_classes
from commands.database_commands import plan_commands, appointment_commands, max_fair_shifts_per_app
from database import db_services, schemas
from gui import data_processing
from gui.concurrency import general_worker
from gui.custom_widgets.progress_bars import DlgProgressInfinite, DlgProgressSteps
from gui.observer import signal_handling
from tools.helper_functions import generate_fixed_cast_clear_text, time_to_string, date_to_string, setup_form_help


class DlgAskNrPlansToSave(QDialog):
    def __init__(self, parent: QWidget, poss_nr_plans: int):
        super().__init__(parent=parent)

        self.poss_nr_plans = poss_nr_plans

        self.layout = QFormLayout(self)
        self.lb_question = QLabel(
            self.tr('A total of {count} plans have been calculated.\n'
                   'How many would you like to use?').format(count=poss_nr_plans))

        self.spin_nr_plans = QSpinBox()
        self.spin_nr_plans.setRange(1, poss_nr_plans)
        self.spin_nr_plans.setValue(self.poss_nr_plans)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addRow(self.lb_question)
        self.layout.addRow(self.tr('Number of plans:'), self.spin_nr_plans)
        self.layout.addRow(self.button_box)

    def get_nr_versions_to_use(self):
        return self.spin_nr_plans.value()


class DlgCalculate(QDialog):
    def __init__(self, parent: QWidget, team_id: UUID):
        super().__init__(parent)

        # TODO: Bulk Operation für mehrere Monate bei Berechnung der gerechten Aufteilung über all diese Monate

        # Help-System Integration
        setup_form_help(self, "calculate_plan", add_help_button=True)

        # Signal connection für solver_quit wird lazy in _calculate_schedule_versions gemacht

        self.team_id = team_id
        self.curr_plan_period_id: UUID | None = None
        self._created_plan_ids: list[UUID] = []
        self.num_actor_plan_periods: int | None = None

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QHBoxLayout()
        self.group_plan_select = QGroupBox(self.tr('Period and Count'))
        self.group_time_config = QGroupBox(self.tr('Calculation Times (sec)'))
        self.layout_body.addWidget(self.group_plan_select)
        self.layout_body.addWidget(self.group_time_config)
        self.layout_plan_select = QFormLayout(self.group_plan_select)
        self.layout_times_config = QFormLayout(self.group_time_config)
        self.layout_foot = QVBoxLayout()

        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_explanation = QLabel()
        self.layout_head.addWidget(self.lb_explanation)
        self.combo_plan_periods = QComboBox()
        self.spin_num_plans = QSpinBox()
        self.layout_plan_select.addRow(self.tr('Planning Period'), self.combo_plan_periods)
        self.layout_plan_select.addRow(self.tr('Number of Planning Proposals'), self.spin_num_plans)
        self.spin_time_calculate_max_shifts = QSpinBox()
        self.spin_time_calculate_fair_distribution = QSpinBox()
        self.spin_time_calculate_plan = QSpinBox()
        self.layout_times_config.addRow(self.tr('Max. Time for Preprocessing'), self.spin_time_calculate_max_shifts)
        self.layout_times_config.addRow(self.tr('Max. Time for Fair Distribution Calculation'),
                                      self.spin_time_calculate_fair_distribution)
        self.layout_times_config.addRow(self.tr('Max. Time for Plan Calculation'), self.spin_time_calculate_plan)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                           | QDialogButtonBox.StandardButton.Cancel)
        self.layout_foot.addWidget(self.button_box)

        self.button_box.accepted.connect(self._calculate_schedule_versions)
        self.button_box.rejected.connect(self.reject)

        self.fill_out_widgets()

    def _calculate_schedule_versions(self):
        if not self.curr_plan_period_id:
            QMessageBox.critical(self, self.tr('Period'), 
                               self.tr('Please select a period first.'))
            return

        if not db_services.Event.get_all_from__plan_period(self.curr_plan_period_id):
            QMessageBox.critical(self, self.tr('Create Plans'),
                               self.tr('No plans can be created for the period {period}.\n'
                                     'Please select assignments in the locations first.')
                               .format(period=self.combo_plan_periods.currentText()))
            return

        # Lazy Import: OR-Tools nur laden wenn Spielplanerstellung benötigt (Performance-Optimierung)
        from sat_solver import solver_main
        
        # Signal für Solver-Cancel lazy verbinden
        signal_handling.handler_solver.signal_cancel_solving.connect(solver_main.solver_quit,
                                                                     Qt.ConnectionType.QueuedConnection)

        self.progress_dialog_solver = DlgProgressSteps(
            self, 
            self.tr('Calculating Plan'), 
            self.tr('Calculating plans.'),
            0, 
            self.spin_num_plans.value() + self.num_actor_plan_periods + 2,
            self.tr('Cancel'), 
            signal_handling.handler_solver.cancel_solving
        )
        self.progress_dialog_solver.show()

        self.worker = general_worker.WorkerCalculatePlan(
            solver_main.solve, self.curr_plan_period_id, self.spin_num_plans.value(),
            self.spin_time_calculate_max_shifts.value(),
            self.spin_time_calculate_fair_distribution.value() // self.num_actor_plan_periods,
            self.spin_time_calculate_plan.value(),
        )
        self.worker.signals.finished.connect(self._save_plan_to_db, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(self.worker)

    def fill_out_widgets(self):
        team = db_services.Team.get(self.team_id)

        self.setWindowTitle(self.tr('Schedule Creation {team_name}').format(team_name=team.name))

        self.lb_explanation.setText(
            self.tr('You can automatically create schedules for team {team_name}\n'
                   'for a selected planning period.').format(team_name=team.name))

        self.spin_time_calculate_fair_distribution.setMaximum(10000)

        plan_periods = sorted([pp for pp in team.plan_periods if not pp.prep_delete],
                              key=lambda x: x.start, reverse=True)
        for plan_period in plan_periods:
            self.combo_plan_periods.addItem(f'{date_to_string(plan_period.start)} - {date_to_string(plan_period.end)}',
                                            plan_period.id)
        self.combo_plan_periods.currentIndexChanged.connect(self.combo_plan_periods_index_changed)
        self.combo_plan_periods_index_changed()
        self.spin_num_plans.setMinimum(1)
        self.spin_time_calculate_max_shifts.setMinimum(5)
        self.spin_time_calculate_plan.setMinimum(5)
        self.spin_time_calculate_max_shifts.setValue(20)  # Vorberechnungen
        self.spin_time_calculate_plan.setValue(60)

    def combo_plan_periods_index_changed(self):
        self.curr_plan_period_id = self.combo_plan_periods.currentData()
        self.num_actor_plan_periods = len(db_services.PlanPeriod.get(self.curr_plan_period_id).actor_plan_periods)
        self.spin_time_calculate_fair_distribution.setMinimum(self.num_actor_plan_periods * 5)
        self.spin_time_calculate_fair_distribution.setSingleStep(self.num_actor_plan_periods)
        self.spin_time_calculate_fair_distribution.setValue(self.num_actor_plan_periods * 50)

    @Slot(object, object, object, object, object)
    def _save_plan_to_db(self, schedule_versions: list[list[schemas.AppointmentCreate]] | None,
                        fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], int] | None,
                        skill_conflicts: dict[str, int] | None,
                        max_shifts_per_app: dict[UUID, int] | None,
                        fair_shifts_per_app: dict[UUID, float]):
        if schedule_versions is None and fixed_cast_conflicts is None:
            QMessageBox.critical(
                self, 
                self.tr('Error'),
                self.tr('No solutions were found.\nThis could be due to early termination,\n'
                       'or the time limits for plan creation were too low,\n'
                       'or the planning requirements were contradictory.')
            )
            self.reject()
            return

        if sum(fixed_cast_conflicts.values()) > 0:
            events = [db_services.Event.get(id_event) for (_, _, id_event), v in fixed_cast_conflicts.items() if v > 0]
            conflict_string = '\n'.join([
                self.tr('  - {date} ({time_of_day}) {location}:\n'
                       '      - Fixed cast: {fixed_cast}').format(
                    date=date_to_string(e.date),
                    time_of_day=e.time_of_day.name,
                    location=e.location_plan_period.location_of_work.name,
                    fixed_cast=generate_fixed_cast_clear_text(e.cast_group.fixed_cast)
                ) for e in events
            ])
            QMessageBox.critical(
                self, 
                self.tr('Error'),
                self.tr('{count} fixed cast conflicts found.\n{conflicts}').format(
                    count=sum(fixed_cast_conflicts.values()),
                    conflicts=conflict_string
                )
            )
            self.reject()
            return

        if sum(skill_conflicts.values()) > 0:
            conflict_string = '\n'.join([
                self.tr('  - {skill}: {count}').format(skill=skill, count=v) 
                for skill, v in skill_conflicts.items() if v > 0
            ])
            QMessageBox.critical(
                self, 
                self.tr('Error'),
                self.tr('{count} skill conflicts found.\n{conflicts}').format(
                    count=sum(skill_conflicts.values()),
                    conflicts=conflict_string
                )
            )
            self.reject()
            return

        nr_versions_to_use = (len_versions := len(schedule_versions))
        if len_versions > 1:
            dlg = DlgAskNrPlansToSave(self, len_versions)
            if dlg.exec():
                nr_versions_to_use = dlg.get_nr_versions_to_use()
            else:
                self.reject()
                return

        self.plans_save_progress_bar = DlgProgressInfinite(
            self, 
            self.tr('Save Plans'), 
            self.tr('In Progress...'), 
            self.tr('Cancel'),
            signal_handling.handler_solver.cancel_solving
        )
        self.plans_save_progress_bar.show()
        self.worker = general_worker.WorkerSavePlans(
            data_processing.save_schedule_versions_to_db, self.curr_plan_period_id, self.team_id,
            schedule_versions, max_shifts_per_app, fair_shifts_per_app,
            nr_versions_to_use, self.controller
        )
        self.worker.signals.finished.connect(self._collect_plan_ids, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(self.worker)

    @Slot(list)
    def _collect_plan_ids(self, plan_ids: list[UUID]):
        self._created_plan_ids = plan_ids
        self.plans_save_progress_bar.close()
        self.accept()

    def get_saved_plan_period_names(self) -> set[str]:
        return set(db_services.Plan.get_all_from__team(self.team_id, True, True).keys())

    def get_created_plan_ids(self):
        return self._created_plan_ids

    def reject(self):
        if hasattr(self, 'progress_dialog_solver') and self.progress_dialog_solver:
            self.progress_dialog_solver.close()
        super().reject()
