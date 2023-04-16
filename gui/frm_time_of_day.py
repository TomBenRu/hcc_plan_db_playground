import datetime
from typing import Literal
from uuid import UUID

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QTimeEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QFormLayout, QComboBox, QSpinBox, QTableWidget, QAbstractItemView, QTableWidgetItem

from database import schemas, db_services
from .commands import command_base_classes, time_of_day_commands, actor_plan_period_commands
from .protocol_widget_classes import ManipulateTimeOfDays, ManipulateTimeOfDaysFurther
from .tools.qcombobox_find_data import QComboBoxToFindData


class FrmTimeOfDayEdit(QDialog):
    def __init__(self, parent: QWidget, time_of_day: schemas.TimeOfDayShow | None, project: schemas.ProjectShow,
                 only_new_time_of_day=False, standard=False):
        super().__init__(parent)
        self.setWindowTitle('Tageszeit')

        self.only_new_time_of_day = only_new_time_of_day

        self.project = project
        self.standard = standard
        self.curr_time_of_day = time_of_day.copy() if time_of_day else None
        self.new_time_of_day: schemas.TimeOfDayCreate | None = None
        self.time_of_day_standard_id: UUID | None = None
        self.to_delete_status = False
        self.new_mode = False

        self.layout = QFormLayout(self)

        self.le_name = QLineEdit()
        self.te_start = QTimeEdit()
        self.te_end = QTimeEdit()
        self.cb_time_of_day_enum = QComboBoxToFindData()
        self.cb_time_of_day_enum.currentIndexChanged.connect(self.time_of_day_enum_changed)
        self.chk_default = QCheckBox()
        self.bt_delete = QPushButton('Löschen', clicked=self.delete)
        self.chk_new_mode = QCheckBox('Als neue Tageszeit speichern?')
        self.chk_new_mode.toggled.connect(self.change_new_mode)

        self.bt_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bt_box.addButton(self.bt_delete, QDialogButtonBox.ButtonRole.ActionRole)
        self.bt_box.accepted.connect(self.save_time_of_day)
        self.bt_box.rejected.connect(self.reject)

        self.layout.addRow('Name', self.le_name)
        self.layout.addRow('Zeitpunkt Start', self.te_start)
        self.layout.addRow('Zeitpunkt Ende', self.te_end)
        self.layout.addRow('Tagesz.-Standart', self.cb_time_of_day_enum)
        self.layout.addRow(self.chk_default)
        self.layout.addRow(self.chk_new_mode)

        self.layout.addRow(self.bt_box)

        self.autofill()

    def autofill(self):
        for t_o_d_enum in self.project.time_of_day_enums:
            self.cb_time_of_day_enum.addItem(QIcon('resources/toolbar_icons/icons/clock.png'),
                                             f'{t_o_d_enum.name} / {t_o_d_enum.abbreviation}', t_o_d_enum.id)
        if self.curr_time_of_day:
            self.le_name.setText(self.curr_time_of_day.name)
            self.te_start.setTime(self.curr_time_of_day.start)
            self.te_end.setTime(self.curr_time_of_day.end)
            self.cb_time_of_day_enum.setCurrentIndex(
                self.cb_time_of_day_enum.findData(self.curr_time_of_day.time_of_day_enum.id))
            self.chk_default.setChecked(self.standard)
        if not self.curr_time_of_day or self.new_mode or self.only_new_time_of_day:
            self.new_mode = True
            self.chk_new_mode.setChecked(True)
            if not self.new_time_of_day or self.only_new_time_of_day:
                self.chk_new_mode.setDisabled(True)

    def change_new_mode(self):
        if self.chk_new_mode.isChecked():
            self.bt_delete.setDisabled(True)
        else:
            self.bt_delete.setEnabled(True)

    def time_of_day_enum_changed(self):
        if t_o_d_enum := self.cb_time_of_day_enum.currentText():
            self.chk_default.setText(f'Als Default für {t_o_d_enum} speichern?')

    def save_time_of_day(self):
        name = self.le_name.text()
        if not name:
            QMessageBox.information(self, 'Fehler', 'Sie müsser einen Namen für diese Tageszeit angeben.')
            return
        if not self.cb_time_of_day_enum.currentData():
            QMessageBox.critical(self, 'Tageszeit', 'Es muss zuerst ein Tageszeit-Standart angelegt werden.')
            self.reject()
        start = datetime.time(self.te_start.time().hour(), self.te_start.time().minute())
        end = datetime.time(self.te_end.time().hour(), self.te_end.time().minute())
        time_of_day_enum = db_services.TimeOfDayEnum.get(self.cb_time_of_day_enum.currentData())
        proj_default = self.project if self.chk_default.isChecked() else None

        if self.chk_new_mode.isChecked():
            self.new_time_of_day = schemas.TimeOfDayCreate(name=name, start=start, end=end,
                                                           time_of_day_enum=time_of_day_enum)
        else:
            self.curr_time_of_day.name = name
            self.curr_time_of_day.start = start
            self.curr_time_of_day.end = end
            self.curr_time_of_day.time_of_day_enum = time_of_day_enum
            self.curr_time_of_day.project_standard = proj_default
        self.accept()

    def delete(self):
        self.to_delete_status = True
        self.accept()

    def set_delete_disabled(self):
        self.bt_delete.setDisabled(True)

    def set_new_mode(self, enabled: bool):
        self.chk_new_mode.setChecked(enabled)

    def set_new_mode_disabled(self):
        self.chk_new_mode.setDisabled(True)


class TimeOfDaysEditList(QDialog):
    def __init__(self, parent: QWidget, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__(parent)

        self.resize(450, 350)
        self.setWindowTitle(f'Tageszeiten des Planungszeitraums, '
                            f'{actor_plan_period.person.f_name} {actor_plan_period.person.l_name}')

        self.actor_plan_period = actor_plan_period

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QGridLayout(self)

        self.table_time_of_days: QTableWidget | None = None
        self.setup_table_time_of_days()

        self.bt_new = QPushButton('Neu...', clicked=self.create_time_of_day)
        self.bt_edit = QPushButton('Berabeiten...', clicked=self.edit_time_of_day)
        self.bt_delete = QPushButton('Löschen', clicked=self.delete_time_of_day)
        self.bt_reset = QPushButton('Reset', clicked=self.reset_time_of_days)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.setCenterButtons(True)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.bt_new, 1, 0)
        self.layout.addWidget(self.bt_edit, 1, 1)
        self.layout.addWidget(self.bt_delete, 1, 2)
        self.layout.addWidget(self.bt_reset, 2, 1)
        self.layout.addWidget(self.button_box, 3, 0, 1, 3)

    def setup_table_time_of_days(self):
        if self.table_time_of_days:
            self.table_time_of_days.deleteLater()
        self.table_time_of_days = QTableWidget()
        self.layout.addWidget(self.table_time_of_days, 0, 0, 1, 3)
        time_of_days = sorted(self.actor_plan_period.time_of_days, key=lambda x: x.time_of_day_enum.time_index)
        time_of_day_standards = self.actor_plan_period.time_of_day_standards
        header_labels = ['id', 'Name', 'Zeitspanne', 'Enum', 'Standard']
        self.table_time_of_days.setRowCount(len(time_of_days))
        self.table_time_of_days.setColumnCount(len(header_labels))
        self.table_time_of_days.setHorizontalHeaderLabels(header_labels)
        self.table_time_of_days.setSortingEnabled(True)
        self.table_time_of_days.setAlternatingRowColors(True)
        self.table_time_of_days.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_time_of_days.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_time_of_days.horizontalHeader().setHighlightSections(False)
        self.table_time_of_days.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")
        self.table_time_of_days.hideColumn(0)

        for row, t_o_d in enumerate(time_of_days):
            self.table_time_of_days.setItem(row, 0, QTableWidgetItem(str(t_o_d.id)))
            self.table_time_of_days.setItem(row, 1, QTableWidgetItem(t_o_d.name))
            text_times = f'{t_o_d.start.strftime("%H:%M")}-{t_o_d.end.strftime("%H:%M")}'
            self.table_time_of_days.setItem(row, 2, QTableWidgetItem(text_times))
            self.table_time_of_days.setItem(row, 3, QTableWidgetItem(t_o_d.time_of_day_enum.name))
            if t_o_d.id in [t.id for t in time_of_day_standards]:
                text_standard = 'ja'
            else:
                text_standard = 'nein'
            self.table_time_of_days.setItem(row, 4, QTableWidgetItem(text_standard))

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def create_time_of_day(self):
        project = db_services.Project.get(self.actor_plan_period.project.id)
        dlg = FrmTimeOfDayEdit(self, None, project, True)
        dlg.set_new_mode_disabled()
        dlg.set_delete_disabled()

        if not dlg.exec():
            return

        if dlg.new_time_of_day.name in [t.name for t in self.actor_plan_period.time_of_days if not t.prep_delete]:
            '''Der Name der neu zu erstellenden Tageszeit ist schon in time_of_days vorhanden.'''
            QMessageBox.critical(dlg, 'Fehler', f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
            return

        create_command = time_of_day_commands.Create(dlg.new_time_of_day, self.actor_plan_period.project.id)
        self.controller.execute(create_command)
        created_t_o_d_id = create_command.get_created_time_of_day_id()

        if dlg.chk_default.isChecked():
            self.controller.execute(
                actor_plan_period_commands.NewTimeOfDayStandard(self.actor_plan_period.id, created_t_o_d_id))

        self.actor_plan_period.time_of_days.append(db_services.TimeOfDay.get(created_t_o_d_id))

        self.controller.execute(actor_plan_period_commands.Update(self.actor_plan_period))
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
        self.setup_table_time_of_days()

    def edit_time_of_day(self):
        curr_row = self.table_time_of_days.currentRow()
        if curr_row == -1:
            QMessageBox.critical(self, 'Tageszeiten', 'Sie müssen zuerst eine Tageszeit zur Bearbeitung auswählen.')
            return
        curr_t_o_d_id = UUID(self.table_time_of_days.item(curr_row, 0).text())
        curr_t_o_d = db_services.TimeOfDay.get(curr_t_o_d_id)
        _, only_new_time_of_day_cause_parent_model, standard = set_params_for__frm_time_of_day(
            self.actor_plan_period, curr_t_o_d_id, 'persons_defaults')

        project = db_services.Project.get(self.actor_plan_period.project.id)
        dlg = FrmTimeOfDayEdit(self, curr_t_o_d, project, only_new_time_of_day_cause_parent_model, standard)
        dlg.set_delete_disabled()
        dlg.set_new_mode_disabled()

        if not dlg.exec():
            return

        if dlg.chk_new_mode.isChecked():
            if only_new_time_of_day_cause_parent_model:
                '''Die aktuell gewählte Tageszeit ist dem parent-model zugeordnet 
                und wird daher aus time_of_days entfernt.'''
                for t_o_d in self.actor_plan_period.time_of_days:
                    if t_o_d.id == curr_t_o_d_id:
                        self.actor_plan_period.time_of_days.remove(t_o_d)
                        break
            if dlg.new_time_of_day.name in [t.name for t in self.actor_plan_period.time_of_days if not t.prep_delete]:
                '''Der Name der neu zu erstellenden Tageszeit ist schon in time_of_days vorhanden.'''
                QMessageBox.critical(dlg, 'Fehler', f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
                if only_new_time_of_day_cause_parent_model:  # Die zuvor entfernte Tagesz. wird wieder hinzugefügt
                    self.actor_plan_period.time_of_days.append(curr_t_o_d)
            else:
                if only_new_time_of_day_cause_parent_model:
                    '''Die aktuelle Tageszeit wurde aus times_of_days entfernt, weil sie zum Parent-Model gehöhrt.
                     Falls sie sich auch in den Personenstandarts befindet, wird sie auch da entfernt.'''
                    if curr_t_o_d_id in [t.id for t in self.actor_plan_period.time_of_day_standards]:
                        self.controller.execute(
                            actor_plan_period_commands.RemoveTimeOfDayStandard(self.actor_plan_period.id,
                                                                               curr_t_o_d_id))

                create_command = time_of_day_commands.Create(dlg.new_time_of_day, self.actor_plan_period.project.id)
                self.controller.execute(create_command)
                created_t_o_d_id = create_command.time_of_day_id
                self.actor_plan_period.time_of_days.append(db_services.TimeOfDay.get(created_t_o_d_id))
                self.controller.execute(actor_plan_period_commands.Update(self.actor_plan_period))

                if dlg.chk_default.isChecked():
                    self.controller.execute(
                        actor_plan_period_commands.NewTimeOfDayStandard(self.actor_plan_period.id, created_t_o_d_id))
                else:
                    self.controller.execute(
                        actor_plan_period_commands.RemoveTimeOfDayStandard(self.actor_plan_period.id, created_t_o_d_id))

        else:
            if dlg.curr_time_of_day.name in [t.name for t in self.actor_plan_period.time_of_days
                                             if not t.prep_delete and dlg.curr_time_of_day.id != t.id]:
                QMessageBox.critical(dlg, 'Fehler',
                                     f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
            else:
                curr_t_o_d_id = dlg.curr_time_of_day.id
                self.controller.execute(time_of_day_commands.Update(dlg.curr_time_of_day))

                if dlg.chk_default.isChecked():
                    self.controller.execute(
                        actor_plan_period_commands.NewTimeOfDayStandard(self.actor_plan_period.id, curr_t_o_d_id))
                else:
                    self.controller.execute(
                        actor_plan_period_commands.RemoveTimeOfDayStandard(self.actor_plan_period.id, curr_t_o_d_id))

        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
        self.setup_table_time_of_days()

    def reset_time_of_days(self):
        project = db_services.Project.get(self.actor_plan_period.project.id)
        for t_o_d in self.actor_plan_period.time_of_days:
            '''Alle nicht nur zur ActorPlanPeriod gehörigen TimeOfDays werden mit dem Controller gelöscht.
            Diese werden dann mit Bestätigen des vorherigen Dialogs entgültig gelöscht.'''
            if not db_services.TimeOfDay.get(t_o_d.id).persons_defaults:
                '''Das funktioniert, weil der Eintrag nicht wirklich gelöscht wird, 
                sondern nur das Attribut "prep_delete" gesetzt wird.'''
                self.controller.execute(time_of_day_commands.Delete(t_o_d.id))
        for t_o_d in self.actor_plan_period.time_of_day_standards:
            self.controller.execute(actor_plan_period_commands.RemoveTimeOfDayStandard(self.actor_plan_period.id,
                                                                                       t_o_d.id))
        self.actor_plan_period.time_of_days.clear()  # notendig?
        for t_o_d in [t for t in project.time_of_days if not t.prep_delete]:
            self.actor_plan_period.time_of_days.append(t_o_d)
            if t_o_d.project_standard:
                self.controller.execute(actor_plan_period_commands.NewTimeOfDayStandard(self.actor_plan_period.id,
                                                                                        t_o_d.id))

        self.controller.execute(actor_plan_period_commands.Update(self.actor_plan_period))
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)

        QMessageBox.information(self, 'Tageszeiten reset',
                                f'Die Tageszeiten wurden zurückgesetzt:\n'
                                f'{[(t_o_d.name, t_o_d.start, t_o_d.end) for t_o_d in self.actor_plan_period.time_of_days]}')
        self.setup_table_time_of_days()

    def delete_time_of_day(self):
        curr_row = self.table_time_of_days.currentRow()
        if curr_row == -1:
            QMessageBox.critical(self, 'Tageszeiten', 'Sie müssen zuerst eine Tageszeit zur Bearbeitung auswählen.')
            return
        curr_t_o_d_id = UUID(self.table_time_of_days.item(curr_row, 0).text())

        _, only_new_time_of_day_cause_parent_model, _ = set_params_for__frm_time_of_day(
            self.actor_plan_period, curr_t_o_d_id, 'persons_defaults')

        if only_new_time_of_day_cause_parent_model:
            for t_o_d in self.actor_plan_period.time_of_days:
                if t_o_d.id == curr_t_o_d_id:
                    self.actor_plan_period.time_of_days.remove(t_o_d)
                    self.controller.execute(
                        actor_plan_period_commands.RemoveTimeOfDayStandard(self.actor_plan_period.id, curr_t_o_d_id))
                    break
            self.controller.execute(actor_plan_period_commands.Update(self.actor_plan_period))
        else:
            self.controller.execute(time_of_day_commands.Delete(curr_t_o_d_id))
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
        self.setup_table_time_of_days()


class FrmTimeOfDayEnum(QDialog):
    def __init__(self, parent: QWidget, project: schemas.ProjectShow,
                 time_of_day_enum: schemas.TimeOfDayEnumShow | None):
        super().__init__(parent)
        self.setWindowTitle('Tageszeit Standard')

        self.project = project.copy()
        self.curr_time_of_day_enum: schemas.TimeOfDayEnumShow | None = time_of_day_enum
        self.new_time_of_day_enum: schemas.TimeOfDayEnumCreate | None = None
        self.to_delete_status = False

        self.layout = QFormLayout(self)

        self.le_name = QLineEdit()
        self.le_name.setMaxLength(50)
        self.le_abbreviation = QLineEdit()
        self.le_abbreviation.setMaxLength(10)
        self.sp_time_index = QSpinBox()
        self.sp_time_index.setMinimum(1)

        self.chk_new_mode = QCheckBox('Als neuen Tagesz.-Standard speichern?')
        self.chk_new_mode.toggled.connect(self.change_new_mode)

        self.bt_delete = QPushButton('Löschen', clicked=self.delete)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.bt_delete, QDialogButtonBox.ButtonRole.DestructiveRole)
        self.button_box.accepted.connect(self.save)
        self.button_box.rejected.connect(self.reject)

        self.layout.addRow('Name', self.le_name)
        self.layout.addRow('Kürzel', self.le_abbreviation)
        self.layout.addRow('Einordnung am Tag', self.sp_time_index)
        self.layout.addRow(self.chk_new_mode)
        self.layout.addRow(self.button_box)

        self.autofill()

    def save(self):
        name = self.le_name.text()
        abbreviation = self.le_abbreviation.text()
        time_index = self.sp_time_index.value()
        if not name or not abbreviation:
            QMessageBox.critical(self, 'Tagesz.-Standard', 'Sie müssen sowohl Namen als auch Kürzel angeben.')
            return
        if self.chk_new_mode.isChecked():
            if (n := self.le_name.text()) in [t.name for t in self.project.time_of_day_enums]:
                QMessageBox.critical(self, 'Tagesz.-Standard', f'Der Name {n} ist schon unter den Standards vorhanden.')
                return
            if (k := self.le_name.text()) in [t.abbreviation for t in self.project.time_of_day_enums]:
                QMessageBox.critical(self, 'Tagesz.-Standard', f'Das Kürzel {k} ist schon unter den Standards vorhanden.')
                return
            self.new_time_of_day_enum = schemas.TimeOfDayEnumCreate(name=name, abbreviation=abbreviation,
                                                                    time_index=time_index, project=self.project)
            self.accept()
        else:
            if (n := self.le_name.text()) in [t.name for t in self.project.time_of_day_enums
                                              if t.id != self.curr_time_of_day_enum.id]:
                QMessageBox.critical(self, 'Tagesz.-Standard', f'Der Name {n} ist schon unter den Standards vorhanden.')
                return
            if (k := self.le_name.text()) in [t.abbreviation for t in self.project.time_of_day_enums
                                              if t.id != self.curr_time_of_day_enum.id]:
                QMessageBox.critical(self, 'Tagesz.-Standard', f'Das Kürzel {k} ist schon unter den Standards vorhanden.')
                return
            self.curr_time_of_day_enum.name = name
            self.curr_time_of_day_enum.abbreviation = abbreviation
            self.curr_time_of_day_enum.time_index = time_index
            self.accept()

    def delete(self):
        self.to_delete_status = True
        self.accept()

    def autofill(self):
        if self.curr_time_of_day_enum:
            self.le_name.setText(self.curr_time_of_day_enum.name)
            self.le_abbreviation.setText(self.curr_time_of_day_enum.abbreviation)
            self.sp_time_index.setValue(self.curr_time_of_day_enum.time_index)
        else:
            self.chk_new_mode.setChecked(True)
            self.chk_new_mode.setDisabled(True)
            if self.project.time_of_day_enums:
                self.sp_time_index.setValue(max(d_o_t_enum.time_index
                                                for d_o_t_enum in self.project.time_of_day_enums) + 1)
            else:
                self.sp_time_index.setValue(1)

    def change_new_mode(self):
        if self.chk_new_mode.isChecked():
            self.bt_delete.setDisabled(True)
        else:
            self.bt_delete.setEnabled(True)


def set_params_for__frm_time_of_day(pydantic_model: schemas.ModelWithTimeOfDays, curr_time_of_day_id: UUID | None,
                                    field__time_of_days__parent_model: Literal['project_defaults',
                                    'persons_defaults', 'actor_plan_periods_defaults', 'locations_of_work_defaults',
                                    'location_plan_periods_defaults'] | None):
    """Returns 3 boolean parameters to note, when editing time_of_days:

    only_new_time_of_day (is there a time_of_day instance to edit?),

    only_new_time_of_day_cause_parent_model (current time_of_day instance is also an instance of the parent model),

    standard (is current time_of_day also part of time_of_day_standart in the current model?)"""

    only_new_time_of_day = False
    only_new_time_of_day_cause_parent_model = False

    if not curr_time_of_day_id:
        only_new_time_of_day = True
    else:
        time_of_day_show_in_project = db_services.TimeOfDay.get(curr_time_of_day_id)

        '''Falls die Tageszeit dem parent model zugewiesen ist, soll die abgeänderte Tageszeit als neue Tageszeit mit 
        Referenz zu aktuellen model gespeichert werden.'''
        if field__time_of_days__parent_model:
            if time_of_day_show_in_project.__getattribute__(field__time_of_days__parent_model):
                only_new_time_of_day_cause_parent_model = True
                only_new_time_of_day = True
    if curr_time_of_day_id:
        '''Wenn sich die aktuelle Tagesz. in den Standards des aktuellen Modells befindet, wird "standard" auf True
        gesetzt und dem Dialog mitgeteilt.'''
        standard = curr_time_of_day_id in [t.id for t in pydantic_model.time_of_day_standards]
    else:
        standard = False

    return only_new_time_of_day, only_new_time_of_day_cause_parent_model, standard
