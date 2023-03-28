import datetime
from typing import Literal
from uuid import UUID

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QTimeEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QFormLayout, QComboBox, QSpinBox

from database import schemas, db_services
from .protocol_widget_classes import ManipulateTimeOfDays
from .tools.qcombobox_find_data import QComboBoxToFindData


class FrmTimeOfDay(QDialog):
    def __init__(self, parent: QWidget, time_of_day: schemas.TimeOfDayShow, project: schemas.ProjectShow,
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


def edit_time_of_days(parent: ManipulateTimeOfDays, pydantic_model: schemas.ModelWithTimeOfDays,
                      project: schemas.ProjectShow, field__time_of_days__parent_model: Literal['project_defaults',
                      'persons_defaults', 'actor_plan_periods_defaults', 'locations_of_work_defaults',
                      'location_plan_periods_defaults'] | None):

    only_new_time_of_day = False
    only_new_time_of_day_cause_parent_model = False

    if not (curr_data := parent.cb_time_of_days.currentData()):
        only_new_time_of_day = True
    else:
        time_of_day_show_in_project = db_services.TimeOfDay.get(curr_data.id)

        '''Falls die Tageszeit dem parent model zugewiesen ist, soll die abgeänderte Tageszeit als neue Tageszeit mit 
        Referenz zu aktuellen model gespeichert werden.'''
        if field__time_of_days__parent_model:
            if time_of_day_show_in_project.__getattribute__(field__time_of_days__parent_model):
                only_new_time_of_day_cause_parent_model = True
                only_new_time_of_day = True
    if t_o_d := parent.cb_time_of_days.currentData():
        '''Wenn sich die aktuelle Tagesz. in den Standarts des aktuellen Modells befindet, wird "standard" auf True
        gesetztz und dem Dialog mitgeteilt.'''
        standard = t_o_d.id in [t.id for t in pydantic_model.time_of_day_standards]
    else:
        standard = False

    dlg = FrmTimeOfDay(parent, parent.cb_time_of_days.currentData(), project, only_new_time_of_day=only_new_time_of_day,
                       standard=standard)
    if not dlg.exec():  # Wenn der Dialog nicht mit OK bestätigt wird...
        return
    if dlg.chk_new_mode.isChecked():
        if only_new_time_of_day_cause_parent_model:
            '''Die aktuell gewählte Tageszeit ist dem parent-model zugeordnet
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
            dlg.time_of_day_standard_id = t_o_d_created.id  # wird zum späteren Setzen o. Löschen gesetzt.
            parent.new_time_of_day_to_delete.append(t_o_d_created)
            '''Neue TimeOfDay wurde erstellt, aber noch nicht der aktuellen model zugeordnet.'''
            pydantic_model.time_of_days.append(t_o_d_created)
            QMessageBox.information(parent, 'Tageszeit',
                                    f'Die Tageszeit wurde erstellt, wird aber erst mit Bestätigen des vorhergehenden '
                                    f'Dialogs übernommen:\n{t_o_d_created}')
            parent.fill_time_of_days()
        return dlg

    else:
        '''Tageszeit löschen...'''
        if dlg.to_delete_status:
            for t_o_d in pydantic_model.time_of_days:
                if t_o_d.id == dlg.curr_time_of_day.id:
                    parent.time_of_days_to_delete.append(t_o_d)
                    pydantic_model.time_of_days.remove(t_o_d)
            QMessageBox.information(parent, 'Tageszeit Löschen',
                                    f'Die Tageszeit wird mit Bestätigen der vorhergehenden Dialogs gelöscht:\n'
                                    f'{dlg.curr_time_of_day}')
            parent.fill_time_of_days()
            return dlg
        '''Tageszeit updaten...'''
        if dlg.curr_time_of_day.name in [t.name for t in pydantic_model.time_of_days
                                         if not t.prep_delete and dlg.curr_time_of_day.id != t.id]:
            QMessageBox.critical(dlg, 'Fehler',
                                 f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
        else:
            dlg.time_of_day_standard_id = dlg.curr_time_of_day.id  # wird zum späteren Setzen o. Löschen gesetzt.
            for t_o_d in pydantic_model.time_of_days:
                if t_o_d.id == dlg.curr_time_of_day.id:
                    pydantic_model.time_of_days.remove(t_o_d)
                    pydantic_model.time_of_days.append(dlg.curr_time_of_day)
                    parent.time_of_days_to_update.append(dlg.curr_time_of_day)
                    break
            QMessageBox.information(parent, 'Tageszeit', f'Die Tageszeit wird mit Bestätigen des vorhergehenden Dialogs'
                                                         f' geupdated:\n{dlg.curr_time_of_day.name}')
            parent.fill_time_of_days()
        return dlg


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
