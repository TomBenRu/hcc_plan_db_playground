import datetime
import datetime
from uuid import UUID

from PySide6.QtCore import QThread, Signal, QObject, Slot, Qt, QThreadPool
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QMessageBox, \
    QFormLayout, QSpinBox, QHBoxLayout, QGroupBox, QCheckBox, QListWidget, QListWidgetItem, QAbstractItemView, \
    QApplication, QSpacerItem, QSizePolicy

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
        self.spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.layout.addSpacerItem(self.spacer)

        self.lb_explanation = QLabel()
        self.layout_head.addWidget(self.lb_explanation)
        
        # Multi-Period Mode Checkbox
        self.cb_multi_period = QCheckBox(
            self.tr('Calculate fair distribution across multiple periods')
        )
        self.cb_multi_period.stateChanged.connect(self._toggle_multi_period_mode)
        self.layout_head.addWidget(self.cb_multi_period)
        
        # Single-Period: ComboBox (Standard)
        self.combo_plan_periods = QComboBox()
        self.layout_plan_select.addRow(self.tr('Planning Period'), self.combo_plan_periods)
        
        # Multi-Period: List Widget (initial versteckt)
        self.list_plan_periods = QListWidget()
        self.list_plan_periods.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.list_plan_periods.setVisible(False)
        self.layout_plan_select.addRow(self.tr('Select Periods:'), self.list_plan_periods)
        
        self.spin_num_plans = QSpinBox()
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


    def _toggle_multi_period_mode(self):
        """
        Schaltet zwischen Single- und Multi-Period Mode um.
        
        Im Multi-Period Mode:
        - ComboBox wird ausgeblendet
        - List Widget wird angezeigt und gefüllt
        - User kann mehrere Perioden auswählen
        
        Im Single-Period Mode:
        - ComboBox wird angezeigt
        - List Widget wird ausgeblendet
        """
        is_multi = self.cb_multi_period.isChecked()
        
        # Toggle Sichtbarkeit
        self.combo_plan_periods.setVisible(not is_multi)
        self.list_plan_periods.setVisible(is_multi)
        
        # Fülle List Widget beim ersten Aktivieren
        if is_multi:
            self.spacer.changeSize(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self.lb_explanation.setText(self.tr('You can automatically create schedules for team {team_name}\n'
                                                'Multi-Period Mode: Select at least two periods.\n'
                                                '(The result may be slightly less accurate '
                                                'than when calculating for single periods.)')
                                        .format(team_name=db_services.Team.get(self.team_id).name)
                                        )
            if self.list_plan_periods.count() == 0:
                self._fill_plan_periods_list()
        else:
            self.spacer.changeSize(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
            self.lb_explanation.setText(self.tr('You can automatically create schedules for team {team_name}\n'
                                                'for a selected planning period.').format(
                    team_name=db_services.Team.get(self.team_id).name
                )
            )
    
    def _fill_plan_periods_list(self):
        """
        Füllt das List Widget mit allen verfügbaren PlanPeriods des Teams.
        """
        team = db_services.Team.get(self.team_id)
        plan_periods = sorted(
            [pp for pp in team.plan_periods if not pp.prep_delete],
            key=lambda x: x.start, reverse=True
        )
        
        for pp in plan_periods:
            item = QListWidgetItem(
                f'{date_to_string(pp.start)} - {date_to_string(pp.end)}'
            )
            item.setData(Qt.ItemDataRole.UserRole, pp.id)
            self.list_plan_periods.addItem(item)

    def _calculate_schedule_versions(self):
        # Prüfe ob Multi-Period Mode aktiv ist
        if self.cb_multi_period.isChecked():
            self._calculate_multi_period()
            return
        
        # Standard Single-Period Berechnung
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


    def _calculate_multi_period(self):
        """
        Startet die Multi-Period Plan-Berechnung.
        
        Workflow:
        1. Sammle ausgewählte PlanPeriods aus List Widget
        2. Validiere Auswahl (min. 2 Perioden, alle haben Events)
        3. Starte Worker für solve_multi_period()
        4. Nach Berechnung: Teile Gesamtplan auf und speichere einzeln
        """
        # 1. Sammle ausgewählte PlanPeriods
        selected_pp_ids = []
        for i in range(self.list_plan_periods.count()):
            item = self.list_plan_periods.item(i)
            if item.isSelected():
                selected_pp_ids.append(item.data(Qt.ItemDataRole.UserRole))
        
        # 2. Validierung: Mindestens 2 Perioden
        if len(selected_pp_ids) < 2:
            QMessageBox.warning(
                self, 
                self.tr('Period Selection'),
                self.tr('Please select at least 2 periods for multi-period calculation.')
            )
            return
        
        # 3. Validierung: Alle Perioden haben Events
        for pp_id in selected_pp_ids:
            if not db_services.Event.get_all_from__plan_period(pp_id):
                pp = db_services.PlanPeriod.get(pp_id)
                QMessageBox.critical(
                    self,
                    self.tr('No Events'),
                    self.tr('Period {period} has no events.\n'
                           'Please add assignments first.').format(
                        period=f'{date_to_string(pp.start)} - {date_to_string(pp.end)}'
                    )
                )
                return
        
        # 4. Lazy Import
        from sat_solver import solver_main
        
        # Signal für Solver-Cancel lazy verbinden
        signal_handling.handler_solver.signal_cancel_solving.connect(
            solver_main.solver_quit,
            Qt.ConnectionType.QueuedConnection
        )
        
        # 5. Berechne Anzahl ActorPlanPeriods über alle Perioden
        total_actor_plan_periods = 0
        for pp_id in selected_pp_ids:
            total_actor_plan_periods += len(db_services.ActorPlanPeriod.get_all_from__plan_period(pp_id))
        
        # 6. Progress Dialog
        # OPTIMIERT: Plan-Erstellung läuft jetzt pro Periode
        # Steps (nur Aufrufe die tatsächlich incrementieren): 
        # - "Vorberechnungen (Multi-Period)..." (1)
        # - While-Loop Generator: "Max Shifts für Periode..." 
        #   Progress-Call kommt NACH next(), daher genau total_actor_plan_periods Calls
        # - "Berechne faire Verteilung (Multi-Period)..." (1)
        # - "Erstelle Pläne für Periode..." pro Periode (len(selected_pp_ids))
        # - "Plan x/y für Periode..." (num_plans * len(selected_pp_ids))
        # - "Layouts der Multi-Period Pläne werden erstellt." (1)
        total_steps = (1 + total_actor_plan_periods + 1 + len(selected_pp_ids)
                       + (self.spin_num_plans.value() * len(selected_pp_ids)) + 1)
        self.progress_dialog_solver = DlgProgressSteps(
            self, 
            self.tr('Multi-Period Calculation'),
            self.tr('Calculating fair distribution across periods...'),
            0,
            total_steps,
            self.tr('Cancel'),
            signal_handling.handler_solver.cancel_solving
        )
        self.progress_dialog_solver.show()
        
        # 7. Starte Worker
        self.worker = general_worker.WorkerCalculateMultiPeriod(
            solver_main.solve_multi_period,
            selected_pp_ids,
            self.spin_num_plans.value(),
            self.spin_time_calculate_max_shifts.value(),
            self.spin_time_calculate_fair_distribution.value() // total_actor_plan_periods,
            self.spin_time_calculate_plan.value()
        )
        self.worker.signals.finished.connect(
            self._save_multi_period_plans,
            Qt.ConnectionType.QueuedConnection
        )
        QThreadPool.globalInstance().start(self.worker)


    @Slot(object, object, object, object, object, object)
    def _save_multi_period_plans(
        self,
        selected_pp_ids: list[UUID],
        schedule_versions: list[list[list[schemas.AppointmentCreate]]] | None,
        fixed_cast_conflicts: dict[tuple[datetime.date, str, UUID], int] | None,
        skill_conflicts: dict[str, int] | None,
        max_shifts_per_app: dict[UUID, int] | None,
        fair_shifts_per_app: dict[UUID, float]
    ):
        """
        Speichert Multi-Period Pläne in die Datenbank.
        
        Diese Methode:
        1. Führt Error-Handling durch (wie _save_plan_to_db)
        2. Speichert die Pläne pro Periode (bereits getrennt strukturiert)
        
        OPTIMIERT: Pläne sind bereits pro Periode erstellt (schedule_versions[period_idx][plan_idx]),
        daher ist keine Aufteilung mehr nötig.
        
        Args:
            selected_pp_ids: Liste der PlanPeriod IDs
            schedule_versions: Pläne pro Periode (all_plans[period_idx][plan_idx])
            fixed_cast_conflicts: Fixed cast Konflikte
            skill_conflicts: Skill Konflikte
            max_shifts_per_app: Maximale Einsätze pro ActorPlanPeriod
            fair_shifts_per_app: Faire Einsätze pro ActorPlanPeriod
        """
        # Error-Handling analog zu _save_plan_to_db
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
                    fixed_cast=generate_fixed_cast_clear_text(e.cast_group.fixed_cast,
                                                              e.cast_group.fixed_cast_only_if_available,
                                                              e.cast_group.prefer_fixed_cast_events)
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

        # Optional: User fragen wie viele Versionen gespeichert werden sollen
        # schedule_versions ist jetzt all_plans[period_idx][plan_idx]
        # Anzahl der Plans pro Periode (alle Perioden haben gleich viele Plans)
        nr_versions_to_use = (len_versions := len(schedule_versions[0]))
        if len_versions > 1:
            dlg = DlgAskNrPlansToSave(self, len_versions)
            if dlg.exec():
                nr_versions_to_use = dlg.get_nr_versions_to_use()
            else:
                self.reject()
                return

        # Lazy Import
        from sat_solver import solver_main
        
        # Schließe Solver Progress Dialog bevor Save Dialog gezeigt wird
        if hasattr(self, 'progress_dialog_solver') and self.progress_dialog_solver:
            self.progress_dialog_solver.close()
        
        # Für jede Plan-Version: Teile nach Perioden auf und speichere
        self.plans_save_progress_bar = DlgProgressInfinite(
            self, 
            self.tr('Save Multi-Period Plans'), 
            self.tr('In Progress...'), 
            self.tr('Cancel'),
            signal_handling.handler_solver.cancel_solving
        )
        self.plans_save_progress_bar.show()
        
        # Speichere nur die ausgewählte Anzahl von Versionen
        # OPTIMIERT: schedule_versions ist bereits pro Periode strukturiert (all_plans[period_idx][plan_idx])
        # Kein extract_appointments_by_period() mehr nötig!
        for version_idx in range(nr_versions_to_use):
            # Speichere jede Periode einzeln
            for period_idx, pp_id in enumerate(selected_pp_ids):
                # Direkter Zugriff auf Periode-spezifischen Plan
                period_appointments = schedule_versions[period_idx][version_idx]
                
                # Nutze existierende save-Funktion (nur mit einer Version)
                plan_ids = data_processing.save_schedule_versions_to_db(
                    pp_id,
                    self.team_id,
                    [period_appointments],  # Als Liste mit einem Element
                    max_shifts_per_app,
                    fair_shifts_per_app,
                    1,  # Nur eine Version pro Periode
                    self.controller
                )
                
                # Sammle erstellte Plan IDs
                self._created_plan_ids.extend(plan_ids)
                
                # Erlaube UI-Updates während des Speicherns
                QApplication.processEvents()
        
        self.plans_save_progress_bar.close()
        
        # Erfolgs-Meldung
        QMessageBox.information(
            self,
            self.tr('Success'),
            self.tr('Multi-period calculation completed successfully!\n'
                    'Plans for {count} periods have been created.\n'
                    'Total {total} plan versions saved.').format(
                count=len(selected_pp_ids),
                total=nr_versions_to_use * len(selected_pp_ids)
            )
        )
        
        self.accept()

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
                    fixed_cast=generate_fixed_cast_clear_text(e.cast_group.fixed_cast,
                                                              e.cast_group.fixed_cast_only_if_available,
                                                              e.cast_group.prefer_fixed_cast_events)
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

        # Schließe Solver Progress Dialog bevor Save Dialog gezeigt wird
        if hasattr(self, 'progress_dialog_solver') and self.progress_dialog_solver:
            self.progress_dialog_solver.close()

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
