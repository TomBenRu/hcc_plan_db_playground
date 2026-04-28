import datetime
import os
from abc import ABC, abstractmethod
from functools import partial
from typing import Callable
from uuid import UUID

from PySide6.QtCore import QTimer, QCoreApplication, QTime
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QLineEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QFormLayout, QSpinBox, QTableWidget, QAbstractItemView, QTableWidgetItem, \
    QApplication, QLabel

from database import schemas, db_services
from commands import command_base_classes
from commands.database_commands import actor_plan_period_commands, location_plan_period_commands, project_commands, \
    person_commands, location_of_work_commands, time_of_day_commands
from gui.custom_widgets.custom_date_and_time_edit import TimeEditLocale
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from tools.helper_functions import time_to_string, setup_form_help


class DlgTimeOfDayEditListBuilderABC(ABC):
    def __init__(self, parent: QWidget, object_with_time_of_days: schemas.ModelWithTimeOfDays):
        self.parent_widget = parent
        self.object_with_time_of_days: schemas.ModelWithTimeOfDays = object_with_time_of_days.model_copy()
        self.window_title: str = ''
        self.project_id: UUID | None = None
        self.parent_time_of_days: list[schemas.TimeOfDay] | None = None
        self.parent_time_of_day_standards: list[schemas.TimeOfDay] | None = None
        self.put_in_command: Callable[[UUID], command_base_classes.Command] | None = None
        self.remove_command: Callable[[UUID], command_base_classes.Command] | None = None
        self.new_time_of_day_standard_command: Callable[[UUID], command_base_classes.Command] | None = None
        self.remove_time_of_day_standard_command: Callable[[UUID], command_base_classes.Command] | None = None

        self._generate_field_values()

    @abstractmethod
    def _generate_field_values(self):
        """
        self.window_title = ...

        self.project_id = ...

        self.parent_time_of_days = ...

        self.parent_time_of_day_standards = ...

        self.put_in_command = ... partial function, which generates the time_of_day input command with parameter = time_of_day_id

        self.remove_command = ... partial function, which generates the time_of_day remove command with parameter = time_of_day_id

        self.new_time_of_day_standard_command = ... partial function, which generates the new_time_of_day_standard command with parameter = time_of_day_id

        self.remove_time_of_day_standard_command = ... partial function, which generates the remove_time_of_day_standard command with parameter = time_of_day_id
        """

    @abstractmethod
    def reload_object_with_time_of_days(self):
        ...

    def build(self) -> 'DlgTimeOfDaysEditList':
        return DlgTimeOfDaysEditList(self.parent_widget, self)


class DlgTimeOfDayEditListBuilderProject(DlgTimeOfDayEditListBuilderABC):
    def __init__(self, parent: QWidget, project: schemas.ProjectShow):
        super().__init__(parent=parent, object_with_time_of_days=project)

        self.object_with_time_of_days: schemas.ProjectShow = project.model_copy()

    def _generate_field_values(self):
        self.window_title = QCoreApplication.translate("TimeOfDayEditList", "Times of day for project {}").format(
            self.object_with_time_of_days.name)
        self.project_id = self.object_with_time_of_days.id
        self.put_in_command = partial(project_commands.PutInTimeOfDay, self.object_with_time_of_days.id)
        self.remove_command = partial(project_commands.RemoveTimeOfDay, self.object_with_time_of_days.id)
        self.new_time_of_day_standard_command = partial(project_commands.NewTimeOfDayStandard,
                                                        self.object_with_time_of_days.id)
        self.remove_time_of_day_standard_command = partial(project_commands.RemoveTimeOfDayStandard,
                                                           self.object_with_time_of_days.id)

    def reload_object_with_time_of_days(self):
        self.object_with_time_of_days = db_services.Project.get(self.object_with_time_of_days.id)


class DlgTimeOfDayEditListBuilderPerson(DlgTimeOfDayEditListBuilderABC):
    def __init__(self, parent: QWidget, person: schemas.PersonShow):
        super().__init__(parent=parent, object_with_time_of_days=person)

        self.object_with_time_of_days: schemas.PersonShow = person.model_copy()

    def _generate_field_values(self):
        self.window_title = QCoreApplication.translate("TimeOfDayEditList", "Times of day for {} {}").format(
            self.object_with_time_of_days.f_name, self.object_with_time_of_days.l_name)
        self.project_id = self.object_with_time_of_days.project.id
        project = db_services.Project.get(self.project_id)
        self.parent_time_of_days = project.time_of_days
        self.parent_time_of_day_standards = project.time_of_day_standards
        self.put_in_command = partial(person_commands.PutInTimeOfDay, self.object_with_time_of_days.id)
        self.remove_command = partial(person_commands.RemoveTimeOfDay, self.object_with_time_of_days.id)
        self.new_time_of_day_standard_command = partial(person_commands.NewTimeOfDayStandard,
                                                        self.object_with_time_of_days.id)
        self.remove_time_of_day_standard_command = partial(person_commands.RemoveTimeOfDayStandard,
                                                           self.object_with_time_of_days.id)

    def reload_object_with_time_of_days(self):
        self.object_with_time_of_days = db_services.Person.get(self.object_with_time_of_days.id)


class DlgTimeOfDayEditListBuilderLocation(DlgTimeOfDayEditListBuilderABC):
    def __init__(self, parent: QWidget, location: schemas.LocationOfWorkShow):
        super().__init__(parent=parent, object_with_time_of_days=location)

        self.object_with_time_of_days: schemas.LocationOfWorkShow = location.model_copy()

    def _generate_field_values(self):
        self.window_title = QCoreApplication.translate("TimeOfDayEditList", "Times of day for facility {} {}").format(
            self.object_with_time_of_days.name, self.object_with_time_of_days.address.city)
        self.project_id = self.object_with_time_of_days.project.id
        project = db_services.Project.get(self.project_id)
        self.parent_time_of_days = [t_o_d for t_o_d in project.time_of_days if not t_o_d.prep_delete]
        self.parent_time_of_day_standards = [t_o_d_st for t_o_d_st in project.time_of_day_standards
                                             if not t_o_d_st.prep_delete]
        self.put_in_command = partial(location_of_work_commands.PutInTimeOfDay, self.object_with_time_of_days.id)
        self.remove_command = partial(location_of_work_commands.RemoveTimeOfDay, self.object_with_time_of_days.id)
        self.new_time_of_day_standard_command = partial(location_of_work_commands.NewTimeOfDayStandard,
                                                        self.object_with_time_of_days.id)
        self.remove_time_of_day_standard_command = partial(location_of_work_commands.RemoveTimeOfDayStandard,
                                                           self.object_with_time_of_days.id)

    def reload_object_with_time_of_days(self):
        self.object_with_time_of_days = db_services.LocationOfWork.get(self.object_with_time_of_days.id)


class DlgTimeOfDayEditListBuilderActorPlanPeriod(DlgTimeOfDayEditListBuilderABC):
    def __init__(self, parent: QWidget, actor_plan_period: schemas.ActorPlanPeriodForMask):
        super().__init__(parent=parent, object_with_time_of_days=actor_plan_period)

        self.object_with_time_of_days: schemas.ActorPlanPeriodForMask = actor_plan_period.model_copy()

    def _generate_field_values(self):
        self.window_title = QCoreApplication.translate("TimeOfDayEditList", "Times of day for planning period, {} {}").format(
            self.object_with_time_of_days.person.f_name, self.object_with_time_of_days.person.l_name)
        self.project_id = self.object_with_time_of_days.project.id
        self.parent_time_of_days = [
                t_o_d for t_o_d in db_services.Person.get(self.object_with_time_of_days.person.id).time_of_days
                if not t_o_d.prep_delete
        ]
        self.parent_time_of_day_standards = [
                t_o_d for t_o_d in db_services.Person.get(self.object_with_time_of_days.person.id).time_of_day_standards
                if not t_o_d.prep_delete
            ]
        self.put_in_command = partial(actor_plan_period_commands.PutInTimeOfDay, self.object_with_time_of_days.id)
        self.remove_command = partial(actor_plan_period_commands.RemoveTimeOfDay, self.object_with_time_of_days.id)
        self.new_time_of_day_standard_command = partial(actor_plan_period_commands.NewTimeOfDayStandard,
                                                        self.object_with_time_of_days.id)
        self.remove_time_of_day_standard_command = partial(actor_plan_period_commands.RemoveTimeOfDayStandard,
                                                           self.object_with_time_of_days.id)

    def reload_object_with_time_of_days(self):
        self.object_with_time_of_days = db_services.ActorPlanPeriod.get_for_mask(self.object_with_time_of_days.id)


class DlgTimeOfDayEditListBuilderLocationPlanPeriod(DlgTimeOfDayEditListBuilderABC):
    def __init__(self, parent: QWidget, location_plan_period: schemas.LocationPlanPeriodShow):
        super().__init__(parent=parent, object_with_time_of_days=location_plan_period)

        self.object_with_time_of_days: schemas.LocationPlanPeriodShow = location_plan_period.model_copy()

    def _generate_field_values(self):
        self.window_title = QCoreApplication.translate("TimeOfDayEditList", "Times of day for planning period, {} {}").format(
            self.object_with_time_of_days.location_of_work.name,
            self.object_with_time_of_days.location_of_work.address.city)
        self.project_id = self.object_with_time_of_days.project.id
        self.parent_time_of_days = [
            t_o_d for t_o_d in
            db_services.LocationOfWork.get(self.object_with_time_of_days.location_of_work.id).time_of_days
            if not t_o_d.prep_delete
        ]
        self.parent_time_of_day_standards = [
            t_o_d for t_o_d in
            db_services.LocationOfWork.get(self.object_with_time_of_days.location_of_work.id).time_of_day_standards
            if not t_o_d.prep_delete
        ]
        self.put_in_command = partial(location_plan_period_commands.PutInTimeOfDay,
                                      self.object_with_time_of_days.id)
        self.remove_command = partial(location_plan_period_commands.RemoveTimeOfDay,
                                      self.object_with_time_of_days.id)
        self.new_time_of_day_standard_command = partial(location_plan_period_commands.NewTimeOfDayStandard,
                                                        self.object_with_time_of_days.id)
        self.remove_time_of_day_standard_command = partial(location_plan_period_commands.RemoveTimeOfDayStandard,
                                                           self.object_with_time_of_days.id)

    def reload_object_with_time_of_days(self):
        self.object_with_time_of_days = db_services.LocationPlanPeriod.get(self.object_with_time_of_days.id)


class DlgTimeOfDayEdit(QDialog):
    def __init__(self, parent: QWidget, time_of_day: schemas.TimeOfDayShow | None, project: schemas.ProjectShow,
                 standard: bool):
        super().__init__(parent)

        self.curr_time_of_day = time_of_day
        self.new_time_of_day: schemas.TimeOfDayCreate | None = None
        self.project = project
        self.standard = standard
        self.to_delete_status = False

        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.layout = QFormLayout(self)

        self.le_name = QLineEdit()
        # `QTime(0, 0)` als Default, um Verhalten des frueheren `QTimeEdit()`
        # beizubehalten — `TimeEditLocale` setzt sonst die aktuelle Zeit.
        self.te_start = TimeEditLocale(time=QTime(0, 0))
        self.te_end = TimeEditLocale(time=QTime(0, 0))
        # Hinweis-Tooltip + Live-Dauer-Label fuer Mitternachts-Konvention
        # (siehe `database/slot_arithmetic.py`).
        midnight_hint = self.tr(
            "End time before start time = span across midnight. Maximum 24 hours."
        )
        self.te_start.setToolTip(midnight_hint)
        self.te_end.setToolTip(midnight_hint)
        self.lbl_duration = QLabel()
        self.lbl_duration.setStyleSheet("color: #64748b; font-size: 11px;")
        self.te_start.timeChanged.connect(self._update_duration_display)
        self.te_end.timeChanged.connect(self._update_duration_display)

        self.cb_time_of_day_enum = QComboBoxToFindData()
        self.cb_time_of_day_enum.currentIndexChanged.connect(self.time_of_day_enum_changed)
        self.chk_default = QCheckBox()
        self.bt_delete = QPushButton(self.tr('Delete'), clicked=self.delete)
        self.chk_new_mode = QCheckBox(self.tr('Save as new time of day?'))
        self.chk_new_mode.toggled.connect(self.change_new_mode)

        self.bt_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bt_box.addButton(self.bt_delete, QDialogButtonBox.ButtonRole.ActionRole)
        self.bt_box.accepted.connect(self.accept)
        self.bt_box.rejected.connect(self.reject)

        self.layout.addRow(self.tr('Name'), self.le_name)
        self.layout.addRow(self.tr('Start time'), self.te_start)
        self.layout.addRow(self.tr('End time'), self.te_end)
        self.layout.addRow('', self.lbl_duration)
        self.layout.addRow(self.tr('Time of day standard'), self.cb_time_of_day_enum)
        self.layout.addRow(self.chk_default)
        self.layout.addRow(self.chk_new_mode)

        self.layout.addRow(self.bt_box)

        self.autofill()
        self._update_duration_display()

        # Help-Integration
        setup_form_help(self, "time_of_day", add_help_button=True)

    def autofill(self):
        for t_o_d_enum in self.project.time_of_day_enums:
            self.cb_time_of_day_enum.addItem(QIcon(os.path.join(self.path_to_icons, 'clock.png')),
                                             f'{t_o_d_enum.name} / {t_o_d_enum.abbreviation}', t_o_d_enum.id)
        if self.curr_time_of_day:
            self.le_name.setText(self.curr_time_of_day.name)
            self.te_start.setTime(self.curr_time_of_day.start)
            self.te_end.setTime(self.curr_time_of_day.end)
            self.cb_time_of_day_enum.setCurrentIndex(
                self.cb_time_of_day_enum.findData(self.curr_time_of_day.time_of_day_enum.id))
            self.chk_default.setChecked(self.standard)
        if not self.curr_time_of_day:
            self.chk_new_mode.setChecked(True)
            self.chk_new_mode.setDisabled(True)

    def change_new_mode(self):
        if self.chk_new_mode.isChecked():
            self.bt_delete.setDisabled(True)
        else:
            self.bt_delete.setEnabled(True)

    def _update_duration_display(self):
        """Aktualisiert das Dauer-Label.

        Konvention `slot_arithmetic.slot_to_range`: end < start = Wrap
        (Spanne ueber Mitternacht, +24h). end == start = 0-Dauer (visuell
        als Warnung markiert, aber nicht hart abgelehnt).
        """
        start = self.te_start.time()
        end = self.te_end.time()
        start_min = start.hour() * 60 + start.minute()
        end_min = end.hour() * 60 + end.minute()
        wrapped = end_min < start_min
        if wrapped:
            end_min += 24 * 60
        total = end_min - start_min
        if total == 0:
            text = self.tr("⚠ Duration: 0 min")
            self.lbl_duration.setStyleSheet("color: #d97706; font-size: 11px;")
        else:
            h, m = divmod(total, 60)
            parts: list[str] = []
            if h:
                parts.append(f"{h} {self.tr('hr')}")
            if m:
                parts.append(f"{m} {self.tr('min')}")
            text = self.tr("Duration:") + " " + " ".join(parts)
            if wrapped:
                text += " 🌙"
                self.lbl_duration.setStyleSheet("color: #d97706; font-size: 11px;")
            else:
                self.lbl_duration.setStyleSheet("color: #64748b; font-size: 11px;")
        self.lbl_duration.setText(text)

    def time_of_day_enum_changed(self):
        if t_o_d_enum := self.cb_time_of_day_enum.currentText():
            self.chk_default.setText(self.tr('Save as default for {}?').format(t_o_d_enum))

    def accept(self):
        name = self.le_name.text()
        if not name:
            QMessageBox.information(self, self.tr('Error'), self.tr('You must specify a name for this time of day.'))
            return
        if not self.cb_time_of_day_enum.currentData():
            QMessageBox.critical(self, self.tr('Time of day'), self.tr('A time of day category must be created first.'))
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
        super().accept()

    def delete(self):
        self.to_delete_status = True
        super().accept()

    def set_new_mode(self, enabled: bool):
        self.chk_new_mode.setChecked(enabled)

    def set_new_mode_disabled(self):
        self.chk_new_mode.setDisabled(True)

    def set_delete_disabled(self):
        self.bt_delete.setDisabled(True)


class DlgTimeOfDaysEditList(QDialog):
    def __init__(self, parent: QWidget, builder: DlgTimeOfDayEditListBuilderABC):
        super().__init__(parent)

        self.resize(450, 350)

        self.builder = builder

        self.setWindowTitle(self.builder.window_title)

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QGridLayout(self)

        self.table_time_of_days: QTableWidget | None = None
        self.setup_table_time_of_days()

        self.bt_new = QPushButton(self.tr('New...'), clicked=self.new_time_of_day)
        self.bt_edit = QPushButton(self.tr('Edit...'), clicked=self.edit_time_of_day)
        self.bt_delete = QPushButton(self.tr('Delete'), clicked=self.delete_time_of_day)
        self.bt_reset = QPushButton(self.tr('Reset'), clicked=self.reset_time_of_days)
        if self.builder.parent_time_of_days is None:
            self.bt_reset.setDisabled(True)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.setCenterButtons(True)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.bt_new, 1, 0)
        self.layout.addWidget(self.bt_edit, 1, 1)
        self.layout.addWidget(self.bt_delete, 1, 2)
        self.layout.addWidget(self.bt_reset, 2, 1)
        self.layout.addWidget(self.button_box, 3, 0, 1, 3)

        # Help-Integration
        setup_form_help(self, "time_of_day", add_help_button=True)

    def setup_table_time_of_days(self):
        if self.table_time_of_days:
            self.table_time_of_days.deleteLater()
        self.table_time_of_days = QTableWidget()
        self.table_time_of_days.cellDoubleClicked.connect(self.edit_time_of_day)
        self.layout.addWidget(self.table_time_of_days, 0, 0, 1, 3)
        time_of_days = sorted((t_o_d for t_o_d in self.builder.object_with_time_of_days.time_of_days
                               if not t_o_d.prep_delete),  key=lambda x: x.time_of_day_enum.time_index)
        time_of_day_standards = [t_o_d for t_o_d in self.builder.object_with_time_of_days.time_of_day_standards
                                 if not t_o_d.prep_delete]
        header_labels = ['id', self.tr('Name'), self.tr('Time span'), self.tr('Category'), self.tr('Standard')]
        self.table_time_of_days.setRowCount(len(time_of_days))
        self.table_time_of_days.setColumnCount(len(header_labels))
        self.table_time_of_days.setHorizontalHeaderLabels(header_labels)
        self.table_time_of_days.setSortingEnabled(True)
        self.table_time_of_days.setAlternatingRowColors(True)
        self.table_time_of_days.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_time_of_days.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_time_of_days.horizontalHeader().setHighlightSections(False)
        self.table_time_of_days.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")
        self.table_time_of_days.hideColumn(0)

        for row, t_o_d in enumerate(time_of_days):
            self.table_time_of_days.setItem(row, 0, QTableWidgetItem(str(t_o_d.id)))
            self.table_time_of_days.setItem(row, 1, QTableWidgetItem(t_o_d.name))
            text_times = f'{time_to_string(t_o_d.start)}-{time_to_string(t_o_d.end)}'
            self.table_time_of_days.setItem(row, 2, QTableWidgetItem(text_times))
            self.table_time_of_days.setItem(row, 3, QTableWidgetItem(t_o_d.time_of_day_enum.name))
            if t_o_d.id in [t.id for t in time_of_day_standards]:
                text_standard = self.tr('yes')
            else:
                text_standard = self.tr('no')
            self.table_time_of_days.setItem(row, 4, QTableWidgetItem(text_standard))

    def accept(self) -> None:
        self.controller.execute(
            time_of_day_commands.DeleteUnusedInProject(self.builder.project_id))
        super().accept()

    def reject(self) -> None:
        self.controller.undo_all()
        self.controller.execute(
            time_of_day_commands.DeleteUnusedInProject(self.builder.project_id))
        super().reject()

    def new_time_of_day(self):
        project = db_services.Project.get(self.builder.project_id)
        dlg = DlgTimeOfDayEdit(self, None, project, False)
        dlg.set_new_mode(True)
        dlg.set_new_mode_disabled()
        dlg.set_delete_disabled()

        if not dlg.exec():
            return
        self.create_time_of_day(dlg.new_time_of_day, dlg.chk_default.isChecked())
        self.builder.reload_object_with_time_of_days()
        self.setup_table_time_of_days()

    def edit_time_of_day(self):
        curr_row = self.table_time_of_days.currentRow()
        if curr_row == -1:
            QMessageBox.critical(self, self.tr('Times of day'), self.tr('You must first select a time of day to edit.'))
            return
        curr_t_o_d_id = UUID(self.table_time_of_days.item(curr_row, 0).text())
        curr_t_o_d = db_services.TimeOfDay.get(curr_t_o_d_id, True)

        project = db_services.Project.get(self.builder.project_id)
        standard = curr_t_o_d_id in [t.id for t in self.builder.object_with_time_of_days.time_of_day_standards
                                     if not t.prep_delete]
        dlg = DlgTimeOfDayEdit(self, curr_t_o_d, project, standard)
        dlg.set_delete_disabled()
        dlg.set_new_mode_disabled()

        if not dlg.exec():
            return

        self.controller.execute(self.builder.remove_command(dlg.curr_time_of_day.id))
        if standard:
            self.controller.execute(self.builder.remove_time_of_day_standard_command(curr_t_o_d_id))
        self.builder.object_with_time_of_days.time_of_days = [
            t for t in self.builder.object_with_time_of_days.time_of_days if t.id != dlg.curr_time_of_day.id]
        new_time_of_day = schemas.TimeOfDayCreate.model_validate(dlg.curr_time_of_day)
        # alternativ: new_time_of_day = schemas.TimeOfDayCreate(**dlg.curr_time_of_day.model_dump())
        self.create_time_of_day(new_time_of_day, dlg.chk_default.isChecked())

        self.builder.reload_object_with_time_of_days()
        self.setup_table_time_of_days()

    def create_time_of_day(self, time_of_day: schemas.TimeOfDayCreate, standard: bool):
        if time_of_day.name in [t.name for t in self.builder.object_with_time_of_days.time_of_days if not t.prep_delete]:
            '''Der Name der neu zu erstellenden Tageszeit ist schon in time_of_days vorhanden.'''
            QMessageBox.critical(self, 'Fehler', f'Die Tageszeit "{time_of_day.name}" ist schon vorhanden.')
            return
        create_command = time_of_day_commands.Create(time_of_day, self.builder.project_id)
        self.controller.execute(create_command)
        created_t_o_d_id = create_command.time_of_day_id

        self.controller.execute(self.builder.put_in_command(created_t_o_d_id))

        curr_time_of_day_standards = [t_o_d.id for t_o_d in self.builder.object_with_time_of_days.time_of_day_standards
                                      if not t_o_d.prep_delete]
        if standard and (created_t_o_d_id not in curr_time_of_day_standards):
            self.controller.execute(self.builder.new_time_of_day_standard_command(created_t_o_d_id))

    def reset_time_of_days(self):
        for t_o_d in self.builder.object_with_time_of_days.time_of_days:
            self.controller.execute(self.builder.remove_command(t_o_d.id))
        for t_o_d in self.builder.object_with_time_of_days.time_of_day_standards:
            self.controller.execute(
                self.builder.remove_time_of_day_standard_command(t_o_d.id))

        for t_o_d in self.builder.parent_time_of_days:
            self.controller.execute(self.builder.put_in_command(t_o_d.id))
        for t_o_d in self.builder.parent_time_of_day_standards:
            self.controller.execute(self.builder.new_time_of_day_standard_command(t_o_d.id))

        self.builder.reload_object_with_time_of_days()

        QMessageBox.information(
            self, self.tr('Times of day reset'),
            self.tr('The times of day have been reset:\n') +
            '\n'.join(f'{t_o_d.name} ({time_to_string(t_o_d.start)} - {time_to_string(t_o_d.end)})'
                      for t_o_d in self.builder.object_with_time_of_days.time_of_days))

        self.setup_table_time_of_days()

    def delete_time_of_day(self):
        curr_row = self.table_time_of_days.currentRow()
        if curr_row == -1:
            QMessageBox.critical(self, self.tr('Times of day'), self.tr('You must first select a time of day to delete.'))
            return

        curr_t_o_d_id = UUID(self.table_time_of_days.item(curr_row, 0).text())

        self.controller.execute(self.builder.remove_command(curr_t_o_d_id))
        self.controller.execute(self.builder.remove_time_of_day_standard_command(curr_t_o_d_id))
        curr_time_of_day = db_services.TimeOfDay.get(curr_t_o_d_id)
        QMessageBox.information(self, self.tr('Time of day deleted'), self.tr('The time of day has been deleted:\n') + curr_time_of_day.name)
        self.builder.reload_object_with_time_of_days()
        self.setup_table_time_of_days()


class DlgTimeOfDayEnum(QDialog):  # todo: zu Tabelle wie DlgTimeOfDay ändern. Option 'standard' hinzufügen.
    def __init__(self, parent: QWidget, project: schemas.ProjectShow,
                 time_of_day_enum: schemas.TimeOfDayEnumShow | None):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Time of day category'))

        self.project = project.model_copy()
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

        self.chk_new_mode = QCheckBox(self.tr('Save as new time of day category?'))
        self.chk_new_mode.toggled.connect(self.change_new_mode)

        self.bt_delete = QPushButton(self.tr('Delete'), clicked=self.delete)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.bt_delete, QDialogButtonBox.ButtonRole.DestructiveRole)
        self.button_box.accepted.connect(self.save)
        self.button_box.rejected.connect(self.reject)

        self.layout.addRow(self.tr('Name'), self.le_name)
        self.layout.addRow(self.tr('Abbreviation'), self.le_abbreviation)
        self.layout.addRow(self.tr('Order in day'), self.sp_time_index)
        self.layout.addRow(self.chk_new_mode)
        self.layout.addRow(self.button_box)

        self.autofill()

        # Help-Integration
        setup_form_help(self, "time_of_day", add_help_button=True)

    def save(self):
        name = self.le_name.text()
        abbreviation = self.le_abbreviation.text()
        time_index = self.sp_time_index.value()
        if not name or not abbreviation:
            QMessageBox.critical(self, self.tr('Time of day category'), self.tr('You must specify both name and abbreviation.'))
            return
        if self.chk_new_mode.isChecked():
            if (n := self.le_name.text()) in [t.name for t in self.project.time_of_day_enums]:
                QMessageBox.critical(self, self.tr('Time of day category'), self.tr('The name {} is already in the categories.').format(n))
                return
            if (k := self.le_name.text()) in [t.abbreviation for t in self.project.time_of_day_enums]:
                QMessageBox.critical(self, self.tr('Time of day category'), self.tr('The abbreviation {} is already in the categories.').format(k))
                return
            self.new_time_of_day_enum = schemas.TimeOfDayEnumCreate(name=name, abbreviation=abbreviation,
                                                                    time_index=time_index, project=self.project)
        else:
            if (n := self.le_name.text()) in [t.name for t in self.project.time_of_day_enums
                                              if t.id != self.curr_time_of_day_enum.id]:
                QMessageBox.critical(self, self.tr('Time of day category'), self.tr('The name {} is already in the categories.').format(n))
                return
            if (k := self.le_name.text()) in [t.abbreviation for t in self.project.time_of_day_enums
                                              if t.id != self.curr_time_of_day_enum.id]:
                QMessageBox.critical(self, self.tr('Time of day category'), self.tr('The abbreviation {} is already in the categories.').format(k))
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
