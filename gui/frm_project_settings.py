import os
from uuid import UUID

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QDialog, QWidget, QGridLayout, QLabel, QLineEdit, QComboBox, QHBoxLayout,
                               QGroupBox, QPushButton, QMessageBox)

from database import db_services
from commands import command_base_classes
from commands.database_commands import project_commands, person_commands
from . import frm_time_of_day, frm_cast_rule
from .frm_excel_settings import DlgExcelExportSettings
from .frm_skills import DlgEditSkills
from .frm_team import FrmTeam
from .frm_time_of_day_enum import DlgTimeOfDayEnumsEditList
from tools.helper_functions import setup_form_help


class DlgSettingsProject(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent)
        self.setWindowTitle(self.tr('Project Settings'))

        self.project_id = project_id
        self.controller = command_base_classes.ContrExecUndoRedo()

        self.project = db_services.Project.get(project_id)

        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.layout = QHBoxLayout()
        self.setLayout(self.layout)

        self.group_project_data = QGroupBox(self.tr('Project Data'))
        self.layout_group_project_data = QGridLayout()
        self.group_project_data.setLayout(self.layout_group_project_data)
        self.layout.addWidget(self.group_project_data)

        self.lb_name = QLabel(self.tr('Name'))
        self.le_name = QLineEdit()
        self.lb_teams = QLabel(self.tr('Teams'))
        self.cb_teams = QComboBox()
        self.lb_admin = QLabel(self.tr('Admin'))
        self.cb_admin = QComboBox()
        self.lb_time_of_days = QLabel(self.tr('Times of Day'))
        self.lb_time_of_day_enums = QLabel(self.tr('Time of Day Categories'))
        self.cb_time_of_day_enums = QComboBox()
        self.lb_skills = QLabel(self.tr('Skills'))
        self.lb_cast_rules = QLabel(self.tr('Cast Rules'))
        self.lb_excel_export_settings = QLabel(self.tr('Excel Settings'))
        self.layout_excel_export_settings = QHBoxLayout()
        self.layout_excel_export_settings.setSpacing(2)
        self.color_widgets = [QWidget() for _ in self.project.excel_export_settings.model_dump(exclude={'id'})]

        self.bt_name_save = QPushButton(self.tr('Save'), clicked=self.save_name)
        self.bt_teams = QPushButton(self.tr('New/Edit/Delete'), clicked=self.edit_team)
        self.bt_admin = QPushButton(self.tr('Save'), clicked=self.save_admin)
        self.bt_time_of_day = QPushButton(self.tr('New/Edit/Delete'), clicked=self.edit_time_of_day)
        self.bt_time_of_day_enums = QPushButton(self.tr('New/Edit/Delete'), clicked=self.edit_time_of_day_enums)
        self.bt_skills = QPushButton(self.tr('New/Edit/Delete'), clicked=self.edit_skills)
        self.bt_cast_rules = QPushButton(self.tr('New/Edit/Delete'), clicked=self.edit_cast_rules)
        self.bt_excel_export_settings = QPushButton(self.tr('Edit'), clicked=self.edit_excel_export_settings)

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
        #self.layout_group_project_data.addWidget(self.cb_time_of_days, 3, 1)
        self.layout_group_project_data.addWidget(self.bt_time_of_day, 3, 2)
        self.layout_group_project_data.addWidget(self.lb_time_of_day_enums, 4, 0)
        self.layout_group_project_data.addWidget(self.cb_time_of_day_enums, 4, 1)
        self.layout_group_project_data.addWidget(self.bt_time_of_day_enums, 4, 2)
        self.layout_group_project_data.addWidget(self.lb_skills, 5, 0)
        self.layout_group_project_data.addWidget(self.bt_skills, 5, 2)
        self.layout_group_project_data.addWidget(self.lb_cast_rules, 6, 0)
        self.layout_group_project_data.addWidget(self.bt_cast_rules, 6, 2)
        self.layout_group_project_data.addWidget(self.lb_excel_export_settings, 7, 0)
        self.layout_group_project_data.addLayout(self.layout_excel_export_settings, 7, 1)
        self.layout_group_project_data.addWidget(self.bt_excel_export_settings, 7, 2)
        for widget in self.color_widgets:
            self.layout_excel_export_settings.addWidget(widget)

        self.autofill()
        setup_form_help(self, "project_settings", add_help_button=True)

    def autofill(self):
        self.le_name.setText(self.project.name)
        self.fill_teams()
        self.fill_admins()
        #self.fill_time_of_days()
        self.fill_excel_colors()
        self.fill_time_of_day_enums()

    def fill_teams(self):
        self.cb_teams.clear()
        for t in sorted([t for t in self.project.teams if not t.prep_delete], key=lambda x: x.name):
            self.cb_teams.addItem(QIcon(os.path.join(self.path_to_icons, 'users.png')), t.name, t)

    def fill_admins(self):
        self.cb_admin.clear()
        for p in self.project.persons:
            self.cb_admin.addItem(QIcon(os.path.join(self.path_to_icons, 'user-business.png')), f'{p.f_name} {p.l_name}', p)
        if self.project.admin:
            self.cb_admin.setCurrentText(f'{self.project.admin.f_name} {self.project.admin.l_name}')
        else:
            self.cb_admin.addItem(self.tr('no admin'), None)
            self.cb_admin.setCurrentText(self.tr('no admin'))

    def fill_time_of_day_enums(self):
        self.cb_time_of_day_enums.clear()
        for t_o_d_enum in sorted(self.project.time_of_day_enums, key=lambda x: x.time_index):
            self.cb_time_of_day_enums.addItem(QIcon(os.path.join(self.path_to_icons, 'clock.png')),
                                              f'{t_o_d_enum.name} ({t_o_d_enum.abbreviation})', t_o_d_enum)

    def fill_excel_colors(self):
        if self.project.excel_export_settings:
            for i, color in enumerate(self.project.excel_export_settings.model_dump(exclude={'id'}).values()):
                self.color_widgets[i].setStyleSheet(f'background-color: {color}; border: 1px solid black;')

    def save_name(self):
        new_name = self.le_name.text()
        if new_name == self.project.name:
            return
        self.controller.execute(project_commands.UpdateProjectName(new_name, self.project_id))
        self.project = db_services.Project.get(self.project_id)
        QMessageBox.information(self, self.tr('Project'),
                              self.tr('Name has been updated:\n{}').format(new_name))

    def edit_team(self):
        if FrmTeam(self, self.project, self.cb_teams.currentData()).exec():
            self.project = db_services.Project.get(self.project_id)
            self.fill_teams()

    def save_admin(self):
        new_admin = self.cb_admin.currentData()
        old_admin_id = self.project.admin.id if self.project.admin else None
        if old_admin_id == new_admin.id:
            return
        self.controller.execute(
            person_commands.UpdateAdminOfProject(new_admin.id, self.project_id,
                                                  old_admin_id=old_admin_id))
        QMessageBox.information(self, self.tr('Project'),
                              self.tr('Admin of project "{}" is now "{} {}"').format(
                                  self.project.name,
                                  new_admin.f_name,
                                  new_admin.l_name))
        self.project = db_services.Project.get(self.project_id)
        self.fill_admins()

    def edit_time_of_day(self):
        dlg = frm_time_of_day.DlgTimeOfDayEditListBuilderProject(self, self.project).build()
        if dlg.exec():
            self.project = db_services.Project.get(self.project.id)

    def edit_time_of_day_enums(self):
        # todo: Löschen von Enums führt zur Löschung von time_of_days, welche damit related sind. Und zur Löschung von
        #  events und avail_days welche mit den time_of_days related sind.
        #  DONE: Workaround: 2 Felder in Project für time_of_day_enum anlegen.
        #  1.: time_of_day_enums, welche im Projekt verwendet werden.
        #  2.: time_of_day_enums, welche Standard für künftige Planungen sind.
        #  Löschen von time_of_das_enums bedeutet, dass diese aus den Standards entfernt werden.

        dlg = DlgTimeOfDayEnumsEditList(self, self.project)
        if dlg.exec():
            self.project = db_services.Project.get(self.project.id)

    def edit_skills(self):
        dlg = DlgEditSkills(self, self.project_id)
        if dlg.exec():
            QMessageBox.information(self, self.tr('Skills'),
                                  self.tr('Skills have been modified'))
        else:
            dlg.controller.undo_all()
            QMessageBox.information(self, self.tr('Skills'),
                                  self.tr('Skills have not been modified'))

    def edit_cast_rules(self):
        dlg = frm_cast_rule.DlgCastRules(self, self.project_id)
        if dlg.exec():
            ...
        else:
            dlg.controller.undo_all()

    def edit_excel_export_settings(self):
        dlg = DlgExcelExportSettings(self, self.project.excel_export_settings)
        if dlg.exec():
            updated_excel_settings = db_services.ExcelExportSettings.update(dlg.excel_settings)
            QMessageBox.information(self, self.tr('Excel Export Settings'),
                                  self.tr('Update completed:\n{}').format(updated_excel_settings))
            self.project = db_services.Project.get(self.project_id)
            self.fill_excel_colors()
