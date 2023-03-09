import datetime
from uuid import UUID

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox, QHBoxLayout,
                               QGroupBox, QPushButton, QTimeEdit, QMessageBox)
from pony.orm import TransactionIntegrityError

from database import db_services, schemas, models
from database.models import Project
from gui.frm_excel_settings import FrmExcelExportSettings
from gui.frm_team import FrmTeam
from gui.frm_time_of_day import FrmTimeOfDay


class SettingsProject(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent)
        self.setWindowTitle('Projekt-Einstellungen')

        self.project_id = project_id

        self.project = db_services.get_project(project_id)

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
        self.lb_excel_export_settings = QLabel('Excel-Settings')
        self.layout_excel_export_settings = QHBoxLayout()
        self.layout_excel_export_settings.setSpacing(2)
        self.color_widgets = [QWidget() for _ in self.project.excel_export_settings.dict(exclude={'id'})]

        self.bt_name_save = QPushButton('Speichern')
        self.bt_teams = QPushButton('Neu/Ändern/Löschen', clicked=self.edit_team)
        self.bt_admin = QPushButton('Speichern')
        self.bt_time_of_day = QPushButton('Neu/Ändern/Löschen', clicked=self.edit_time_of_day)
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
        self.layout_group_project_data.addWidget(self.lb_excel_export_settings, 4, 0)
        self.layout_group_project_data.addLayout(self.layout_excel_export_settings, 4, 1)
        self.layout_group_project_data.addWidget(self.bt_excel_export_settings, 4, 2)
        for widget in self.color_widgets:
            self.layout_excel_export_settings.addWidget(widget)

        self.autofill()

    def autofill(self):
        self.le_name.setText(self.project.name)
        self.fill_teams()
        self.cb_admin.clear()
        for p in self.project.persons:
            self.cb_admin.addItem(QIcon('resources/toolbar_icons/icons/user-business.png'), f'{p.f_name} {p.l_name}', p)
        self.fill_time_of_days()
        self.fill_excel_colors()

    def fill_teams(self):
        self.cb_teams.clear()
        for t in sorted([t for t in self.project.teams if not t.prep_delete], key=lambda x: x.name):
            self.cb_teams.addItem(QIcon('resources/toolbar_icons/icons/users.png'), t.name, t)

    def fill_time_of_days(self):
        self.cb_time_of_days.clear()
        for t in sorted([tod for tod in self.project.time_of_days_default if not tod.prep_delete],
                        key=lambda t: t.start):
            self.cb_time_of_days.addItem(QIcon('resources/toolbar_icons/icons/clock-select.png'),
                                         f'{t.name} -> {t.start.hour:02}:{t.start.minute:02} - '
                                         f'{t.end.hour:02}:{t.end.minute:02}', t)

    def fill_excel_colors(self):
        if self.project.excel_export_settings:
            for i, color in enumerate(self.project.excel_export_settings.dict(exclude={'id'}).values()):
                self.color_widgets[i].setStyleSheet(f'background-color: {color}; border: 1px solid black;')

    def edit_team(self):
        if FrmTeam(self, self.project, self.cb_teams.currentData()).exec():
            self.project = db_services.get_project(self.project_id)
            self.fill_teams()

    def edit_time_of_day(self):
        dlg = FrmTimeOfDay(self, self.cb_time_of_days.currentData())
        if dlg.exec():  # Wenn der Dialog mit OK bestätigt wird...
            if dlg.to_delete_status:
                deleted_time_of_day = db_services.delete_time_of_day(dlg.curr_time_of_day.id)
                QMessageBox.information(self, 'Löschen', f'Die Tageszeit "{deleted_time_of_day.name}" wurde gelöscht.')
                return
            if dlg.chk_new_mode.isChecked():
                if dlg.new_time_of_day.name in [t.name for t in self.project.time_of_days_default if not t.prep_delete]:
                    QMessageBox.critical(dlg, 'Fehler',
                                         f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
                else:
                    t_o_d_created = db_services.create_time_of_day(dlg.new_time_of_day, self.project_id)
                    QMessageBox.information(self, 'Tageszeit', f'Die Tageszeit wurde erstellt:\n{t_o_d_created}')
                    instance = db_services.put_time_of_day_to_model(t_o_d_created, self.project, models.Project)
                    QMessageBox.information(self, 'Tageszeit', f'Die Tageszeit wurde hinzugefügt zu:\n{instance}')
                    self.project = db_services.get_project(self.project_id)
                    self.fill_time_of_days()

            else:
                if dlg.curr_time_of_day.name in [t.name for t in self.project.time_of_days_default
                                                 if not t.prep_delete and dlg.curr_time_of_day.id != t.id]:
                    QMessageBox.critical(dlg, 'Fehler',
                                         f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
                else:
                    t_o_d_updated = db_services.update_time_of_day(dlg.curr_time_of_day)
                    QMessageBox.information(self, 'Tageszeit', f'Die Tageszeit wurde upgedated:\n{t_o_d_updated}')
                    self.project = db_services.get_project(self.project_id)
                    self.fill_time_of_days()

    def edit_excel_export_settings(self):
        dlg = FrmExcelExportSettings(self, self.project.excel_export_settings)
        if dlg.exec():
            updated_excel_settings = db_services.update_excel_export_settings(dlg.excel_settings)
            QMessageBox.information(self, 'Excel Expert-Settings', f'Update wurde durchgeführt:\n'
                                                                   f'{updated_excel_settings}')
            self.project = db_services.get_project(self.project_id)
            self.fill_excel_colors()
