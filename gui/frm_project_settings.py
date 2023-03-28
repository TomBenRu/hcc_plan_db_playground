from uuid import UUID

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox, QHBoxLayout,
                               QGroupBox, QPushButton, QTimeEdit, QMessageBox)

from database import db_services, schemas, models
from . import frm_time_of_day
from .frm_excel_settings import FrmExcelExportSettings
from .frm_team import FrmTeam
from .frm_time_of_day import FrmTimeOfDay, FrmTimeOfDayEnum


class SettingsProject(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent)
        self.setWindowTitle('Projekt-Einstellungen')

        self.project_id = project_id

        self.project = db_services.Project.get(project_id)

        self.new_time_of_day_to_delete: list[schemas.TimeOfDayShow] = []
        self.time_of_days_to_delete: list[schemas.TimeOfDayShow] = []
        self.time_of_days_to_update: list[schemas.TimeOfDayShow] = []

        self.layout = QHBoxLayout()
        self.setLayout(self.layout)

        self.group_project_data = QGroupBox('Projektdaten')
        self.layout_group_project_data = QGridLayout()
        self.group_project_data.setLayout(self.layout_group_project_data)
        self.layout.addWidget(self.group_project_data)

        self.lb_name = QLabel('Name')
        self.le_name = QLineEdit()
        self.lb_teams = QLabel('Teams')
        self.cb_teams = QComboBox()
        self.lb_admin = QLabel('Admin')
        self.cb_admin = QComboBox()
        self.lb_time_of_days = QLabel('Tageszeiten')
        self.cb_time_of_days = QComboBox()
        self.lb_time_of_days_enums = QLabel('Tagesz. Standards')
        self.cb_time_of_days_enums = QComboBox()
        self.lb_excel_export_settings = QLabel('Excel-Settings')
        self.layout_excel_export_settings = QHBoxLayout()
        self.layout_excel_export_settings.setSpacing(2)
        self.color_widgets = [QWidget() for _ in self.project.excel_export_settings.dict(exclude={'id'})]

        self.bt_name_save = QPushButton('Speichern', clicked=self.save_name)
        self.bt_teams = QPushButton('Neu/Ändern/Löschen', clicked=self.edit_team)
        self.bt_admin = QPushButton('Speichern', clicked=self.save_admin)
        self.bt_time_of_day = QPushButton('Neu/Ändern/Löschen', clicked=self.edit_time_of_day)
        self.bt_time_of_day_enums = QPushButton('Neu/Ändern/Löschen', clicked=self.edit_time_of_day_enums)
        self.bt_excel_export_settings = QPushButton('Bearbeiten', clicked=self.edit_excel_export_settings)

        self.layout_group_project_data.addWidget(self.lb_name, 0, 0)
        self.layout_group_project_data.addWidget(self.le_name, 0, 1)
        self.layout_group_project_data.addWidget(self.bt_name_save, 0, 2)
        self.layout_group_project_data.addWidget(self.lb_teams, 1, 0)
        self.layout_group_project_data.addWidget(self.cb_teams, 1, 1)
        self.layout_group_project_data.addWidget(self.bt_teams, 1, 2)
        self.layout_group_project_data.addWidget(self.lb_admin, 2, 0)
        self.layout_group_project_data.addWidget(self.cb_admin, 2, 1)
        self.layout_group_project_data.addWidget(self.bt_admin, 2, 2)
        self.layout_group_project_data.addWidget(self.lb_time_of_days, 3, 0)
        self.layout_group_project_data.addWidget(self.cb_time_of_days, 3, 1)
        self.layout_group_project_data.addWidget(self.bt_time_of_day, 3, 2)
        self.layout_group_project_data.addWidget(self.lb_time_of_days_enums, 4, 0)
        self.layout_group_project_data.addWidget(self.cb_time_of_days_enums, 4, 1)
        self.layout_group_project_data.addWidget(self.bt_time_of_day_enums, 4, 2)
        self.layout_group_project_data.addWidget(self.lb_excel_export_settings, 5, 0)
        self.layout_group_project_data.addLayout(self.layout_excel_export_settings, 5, 1)
        self.layout_group_project_data.addWidget(self.bt_excel_export_settings, 5, 2)
        for widget in self.color_widgets:
            self.layout_excel_export_settings.addWidget(widget)

        self.autofill()

    def autofill(self):
        self.le_name.setText(self.project.name)
        self.fill_teams()
        self.fill_admins()
        self.fill_time_of_days()
        self.fill_excel_colors()
        self.fill_time_of_day_enums()

    def fill_teams(self):
        self.cb_teams.clear()
        for t in sorted([t for t in self.project.teams if not t.prep_delete], key=lambda x: x.name):
            self.cb_teams.addItem(QIcon('resources/toolbar_icons/icons/users.png'), t.name, t)

    def fill_admins(self):
        self.cb_admin.clear()
        for p in self.project.persons:
            self.cb_admin.addItem(QIcon('resources/toolbar_icons/icons/user-business.png'), f'{p.f_name} {p.l_name}', p)
        if self.project.admin:
            self.cb_admin.setCurrentText(f'{self.project.admin.f_name} {self.project.admin.l_name}')
        else:
            self.cb_admin.addItem('kein Admin', None)
            self.cb_admin.setCurrentText('kein Admin')

    def fill_time_of_days(self):
        self.cb_time_of_days.clear()
        for t in sorted([tod for tod in self.project.time_of_days if not tod.prep_delete],
                        key=lambda t: t.start):
            self.cb_time_of_days.addItem(QIcon('resources/toolbar_icons/icons/clock-select.png'),
                                         f'{t.name} -> {t.start.hour:02}:{t.start.minute:02} - '
                                         f'{t.end.hour:02}:{t.end.minute:02}', t)

    def fill_time_of_day_enums(self):
        self.cb_time_of_days_enums.clear()
        for t_o_d_enum in sorted(self.project.time_of_day_enums, key=lambda x: x.time_index):
            self.cb_time_of_days_enums.addItem(QIcon('resources/toolbar_icons/icons/clock.png'),
                                               f'{t_o_d_enum.name}/{t_o_d_enum.abbreviation}', t_o_d_enum)

    def fill_excel_colors(self):
        if self.project.excel_export_settings:
            for i, color in enumerate(self.project.excel_export_settings.dict(exclude={'id'}).values()):
                self.color_widgets[i].setStyleSheet(f'background-color: {color}; border: 1px solid black;')

    def save_name(self):
        project_updated = db_services.Project.update_name(self.le_name.text(), self.project_id)
        QMessageBox.information(self, 'Projekt', f'Name wurde upgedatet:\n{project_updated}')

    def edit_team(self):
        if FrmTeam(self, self.project, self.cb_teams.currentData()).exec():
            self.project = db_services.Project.get(self.project_id)
            self.fill_teams()

    def save_admin(self):
        updated_person = db_services.Person.update_project_of_admin(self.cb_admin.currentData().id, self.project_id)
        QMessageBox.information(self, 'Projekt', f'Admin des Projektes "{self.project.name}" ist nun '
                                                 f'"{updated_person.f_name} {updated_person.l_name}"')
        self.project = db_services.Project.get(self.project_id)
        self.fill_admins()

    def edit_time_of_day(self):
        dlg = frm_time_of_day.edit_time_of_days(self, self.project, self.project, None)
        if dlg is None:
            return
        for t_o_d in self.time_of_days_to_delete:
            db_services.TimeOfDay.delete(t_o_d.id)
            return
        self.project = db_services.Project.update(self.project)
        if dlg.chk_default.isChecked():
            self.project = db_services.Project.new_time_of_day_standard(self.project_id, dlg.time_of_day_standard_id)
        else:
            self.project = db_services.Project.remove_time_of_day_standard(self.project_id, dlg.time_of_day_standard_id)

    def edit_time_of_day_enums(self):
        dlg = FrmTimeOfDayEnum(self, self.project, self.cb_time_of_days_enums.currentData())
        if dlg.exec():
            if dlg.chk_new_mode.isChecked():
                created_time_of_day_enum = db_services.TimeOfDayEnum.create(dlg.new_time_of_day_enum)
                QMessageBox.information(self, 'new time_of_day_enum', f'{created_time_of_day_enum}')
            elif dlg.to_delete_status:
                db_services.TimeOfDayEnum.delete(dlg.curr_time_of_day_enum.id)
                QMessageBox.information(self, 'deleted time_of_day_enum', f'{dlg.curr_time_of_day_enum}')
            else:
                updated_time_of_day_enum = db_services.TimeOfDayEnum.update(dlg.curr_time_of_day_enum)
                QMessageBox.information(self, 'update time_of_day_enum', f'{updated_time_of_day_enum}')

            self.project = db_services.Project.get(self.project_id)
            self.fill_time_of_day_enums()
            self.fill_time_of_days()

    def edit_excel_export_settings(self):
        dlg = FrmExcelExportSettings(self, self.project.excel_export_settings)
        if dlg.exec():
            updated_excel_settings = db_services.ExcelExportSettings.update(dlg.excel_settings)
            QMessageBox.information(self, 'Excel Expert-Settings', f'Update wurde durchgeführt:\n'
                                                                   f'{updated_excel_settings}')
            self.project = db_services.Project.get(self.project_id)
            self.fill_excel_colors()
