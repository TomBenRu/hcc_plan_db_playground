import datetime
from typing import Literal
from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QTimeEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QFormLayout

from database import schemas, db_services
from .protocol_widget_classes import ManipulateTimeOfDays


class FrmTimeOfDay(QDialog):
    def __init__(self, parent: QWidget, time_of_day: schemas.TimeOfDayShow, only_new_time_of_day=False):
        super().__init__(parent)
        self.setWindowTitle('Tageszeit')

        self.only_new_time_of_day = only_new_time_of_day

        self.curr_time_of_day = time_of_day.copy() if time_of_day else None
        self.new_time_of_day: schemas.TimeOfDayCreate | None = None
        self.to_delete_status = False
        self.new_mode = False

        self.layout = QFormLayout(self)

        self.le_name = QLineEdit()
        self.te_start = QTimeEdit()
        self.te_end = QTimeEdit()
        self.bt_delete = QPushButton('Löschen', clicked=self.delete)
        self.chk_new_mode = QCheckBox('Als neue Tageszeit speichern?')
        self.chk_new_mode.toggled.connect(self.change_new_mode)

        self.bt_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bt_box.addButton(self.bt_delete, QDialogButtonBox.ButtonRole.DestructiveRole)
        self.bt_box.accepted.connect(self.save_time_of_day)
        self.bt_box.rejected.connect(self.reject)

        self.layout.addRow('Name', self.le_name)
        self.layout.addRow('Zeitpunkt Start', self.te_start)
        self.layout.addRow('Zeitpunkt Ende', self.te_end)
        self.layout.addRow(self.chk_new_mode)

        self.layout.addRow(self.bt_box)

        self.autofill()

    def autofill(self):
        if self.curr_time_of_day:
            self.le_name.setText(self.curr_time_of_day.name)
            self.te_start.setTime(self.curr_time_of_day.start)
            self.te_end.setTime(self.curr_time_of_day.end)
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

    def save_time_of_day(self):
        name = self.le_name.text()
        if not name:
            QMessageBox.information(self, 'Fehler', 'Sie müsser einen Namen für diese Tageszeit angeben.')
            return
        start = datetime.time(self.te_start.time().hour(), self.te_start.time().minute())
        end = datetime.time(self.te_end.time().hour(), self.te_end.time().minute())

        if self.chk_new_mode.isChecked():
            self.new_time_of_day = schemas.TimeOfDayCreate(name=name, start=start, end=end)
        else:
            self.curr_time_of_day.name = name
            self.curr_time_of_day.start = start
            self.curr_time_of_day.end = end
        self.accept()

    def delete(self):
        self.to_delete_status = True
        self.accept()


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

        self.chk_new_mode = QCheckBox('Als neuen Tagesz.-Standard speichern?')
        self.chk_new_mode.toggled.connect(self.change_new_mode)

        self.bt_delete = QPushButton('Löschen', clicked=self.delete)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.bt_delete, QDialogButtonBox.ButtonRole.DestructiveRole)
        self.button_box.accepted.connect(self.save)
        self.button_box.rejected.connect(self.reject)

        self.layout.addRow('Name', self.le_name)
        self.layout.addRow('Kürzel', self.le_abbreviation)
        self.layout.addRow(self.chk_new_mode)
        self.layout.addRow(self.button_box)

        self.autofill()

    def save(self):
        name = self.le_name.text()
        abbreviation = self.le_abbreviation.text()
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
                                                                    project=self.project)
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
            self.accept()

    def delete(self):
        self.to_delete_status = True
        self.accept()

    def autofill(self):
        if self.curr_time_of_day_enum:
            self.le_name.setText(self.curr_time_of_day_enum.name)
            self.le_abbreviation.setText(self.curr_time_of_day_enum.abbreviation)
        else:
            self.chk_new_mode.setChecked(True)
            self.chk_new_mode.setDisabled(True)

    def change_new_mode(self):
        if self.chk_new_mode.isChecked():
            self.bt_delete.setDisabled(True)
        else:
            self.bt_delete.setEnabled(True)


def edit_time_of_days(parent: ManipulateTimeOfDays, pydantic_model: schemas.ModelWithTimeOfDays,
                      field__time_of_days__parent_model: Literal['project_defaults', 'persons_defaults',
                      'actor_plan_periods_defaults', 'avail_days_defaults', 'locations_of_work_defaults',
                      'location_plan_periods_defaults', 'events_defaults']):
    if not (curr_data := parent.cb_time_of_days.currentData()):
        only_new_time_of_day_cause_parent_model = True
    else:
        time_of_day_show_in_project = db_services.TimeOfDay.get(curr_data.id)

        '''Falls die Tageszeit dem Projekt zugewiesen ist, soll die abgeänderte Tageszeit als neue Tageszeit mit 
        Referenz zur Location gespeichert werden.'''
        only_new_time_of_day_cause_parent_model = (
            True if time_of_day_show_in_project.__getattribute__(field__time_of_days__parent_model) else False
        )

    dlg = FrmTimeOfDay(parent, parent.cb_time_of_days.currentData(),
                       only_new_time_of_day=only_new_time_of_day_cause_parent_model)
    if not dlg.exec():  # Wenn der Dialog nicht mit OK bestätigt wird...
        return
    if dlg.chk_new_mode.isChecked():
        if only_new_time_of_day_cause_parent_model:
            '''Die aktuell gewählte Tageszeit ist dem Projekt zugeordnet
               und wird daher aus time_of_days entfernt.'''
            pydantic_model.time_of_days.remove(parent.cb_time_of_days.currentData())
        if dlg.new_time_of_day.name in [t.name for t in pydantic_model.time_of_days if not t.prep_delete]:
            '''Der Name der neu zu erstellenden Tageszeit ist schon in time_of_days vorhanden.'''
            QMessageBox.critical(dlg, 'Fehler',
                                 f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
            if only_new_time_of_day_cause_parent_model:
                pydantic_model.time_of_days.append(parent.cb_time_of_days.currentData())
                parent.fill_time_of_days()
        else:
            t_o_d_created = db_services.TimeOfDay.create(dlg.new_time_of_day, parent.project_id)
            '''Neue TimeOfDay wurde erstellt, aber noch nicht der Location zugeordnet.'''
            pydantic_model.time_of_days.append(t_o_d_created)
            # self.location_of_work = db_services.update_location_of_work(self.location_of_work)
            QMessageBox.information(parent, 'Tageszeit',
                                    f'Die Tageszeit wurde erstellt, wird aber erst mit Bestätigen dieses Dialogs '
                                    f'übernommen:\n{t_o_d_created}')
            parent.fill_time_of_days()

    else:
        if dlg.to_delete_status:
            for t_o_d in pydantic_model.time_of_days:
                if t_o_d.id == dlg.curr_time_of_day.id:
                    parent.time_of_days_to_delete.append(t_o_d)
                    pydantic_model.time_of_days.remove(t_o_d)
            QMessageBox.information(parent, 'Tageszeit Löschen',
                                    f'Die Tageszeit wird gelöscht:\n{dlg.curr_time_of_day}')
            parent.fill_time_of_days()
            return
        if dlg.curr_time_of_day.name in [t.name for t in pydantic_model.time_of_days
                                         if not t.prep_delete and dlg.curr_time_of_day.id != t.id]:
            QMessageBox.critical(dlg, 'Fehler',
                                 f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
        else:
            for t_o_d in pydantic_model.time_of_days:
                if t_o_d.id == dlg.curr_time_of_day.id:

                    pydantic_model.time_of_days.remove(t_o_d)
                    pydantic_model.time_of_days.append(dlg.curr_time_of_day)
                    parent.time_of_days_to_update.append(dlg.curr_time_of_day)
            QMessageBox.information(parent, 'Tageszeit', f'Die Tageszeit wird upgedated:\n{dlg.curr_time_of_day}')
            parent.fill_time_of_days()


def reset_time_of_days(parent: ManipulateTimeOfDays, pydantic_model: schemas.ModelWithTimeOfDays,
                       default_time_of_days: list[schemas.TimeOfDayShow],
                       field__time_of_days__parent_model: Literal['project_defaults', 'persons_defaults',
                       'actor_plan_periods_defaults', 'avail_days_defaults', 'locations_of_work_defaults',
                       'location_plan_periods_defaults', 'events_defaults']):

    for t_o_d in pydantic_model.time_of_days:
        '''Alle nicht nur zur Location gehörigen TimeOfDays werden nach self.time_of_days_to_delete geschoben.
        Diese werden dann mit bestätigen des Dialogs gelöscht.'''
        if not t_o_d.__getattribute__(field__time_of_days__parent_model):
            parent.time_of_days_to_delete.append(t_o_d)
    pydantic_model.time_of_days.clear()
    for t_o_d in [t for t in default_time_of_days if not t.prep_delete]:
        pydantic_model.time_of_days.append(t_o_d)

    QMessageBox.information(parent, 'Tageszeiten reset',
                            f'Die Tageszeiten wurden zurückgesetzt:\n'
                            f'{[(t_o_d.name, t_o_d.start, t_o_d.end) for t_o_d in pydantic_model.time_of_days]}')
    parent.fill_time_of_days()
