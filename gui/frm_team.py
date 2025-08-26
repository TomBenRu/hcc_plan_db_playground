import os

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QLineEdit, QHBoxLayout, QPushButton, \
    QMessageBox, QFormLayout, QCheckBox, QDialogButtonBox
from pony.orm import TransactionIntegrityError

from database import schemas, db_services
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from tools.helper_functions import setup_form_help


class FrmTeam(QDialog):
    def __init__(self, parent: QWidget, project: schemas.ProjectShow, team: schemas.TeamShow | None):
        super().__init__(parent=parent)
        
        # Help-System Integration
        setup_form_help(self, "team", add_help_button=True, help_button_style="titlebar")

        self.setWindowTitle(self.tr('Team'))

        self.project = project
        self.curr_team = team
        self.new_team: schemas.TeamCreate | None = None
        self.new_mode = False
        self.to_delete_status = False

        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.layout = QFormLayout(self)

        self.le_name = QLineEdit()
        self.cb_dispatcher = QComboBoxToFindData()
        self.bt_excel_export_settings = QPushButton(self.tr('Change'))
        self.layout_excel_export_settings = QHBoxLayout()
        self.layout_excel_export_settings.setContentsMargins(0, 20, 0, 0)
        self.layout_excel_export_settings.setSpacing(0)
        self.bt_excel_export_settings.setLayout(self.layout_excel_export_settings)
        self.bt_delete = QPushButton(self.tr('Delete'), clicked=self.delete)

        self.chk_new_mode = QCheckBox(self.tr('Save as new team?'))
        self.chk_new_mode.toggled.connect(self.change_new_mode)

        self.bt_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bt_box.addButton(self.bt_delete, QDialogButtonBox.ButtonRole.ActionRole)
        self.bt_box.accepted.connect(self.save)
        self.bt_box.rejected.connect(self.reject)

        self.layout.addRow(self.tr('Name'), self.le_name)
        self.layout.addRow(self.tr('Dispatcher'), self.cb_dispatcher)
        self.layout.addRow(self.tr('Excel Settings'), self.bt_excel_export_settings)
        self.layout.addRow(self.chk_new_mode)
        self.layout.addRow(self.bt_box)

        self.autofill()

    def autofill(self):
        self.cb_dispatcher.addItem(QIcon(os.path.join(self.path_to_icons, 'cross.png')),
                                 self.tr('No Dispatcher'), None)
        for p in self.project.persons:
            self.cb_dispatcher.addItem(QIcon(os.path.join(self.path_to_icons, 'user-business.png')),
                                     f'{p.full_name}', p.id)
        if not self.curr_team or self.new_mode:
            self.new_mode = True
            self.bt_excel_export_settings.setDisabled(True)
            self.chk_new_mode.setChecked(True)
            self.chk_new_mode.setDisabled(True)
            self.bt_delete.setDisabled(True)
            return
        self.bt_excel_export_settings.setEnabled(True)
        self.bt_delete.setEnabled(True)
        self.le_name.setText(self.curr_team.name)
        if self.curr_team.dispatcher:
            self.cb_dispatcher.setCurrentIndex(self.cb_dispatcher.findData(self.curr_team.dispatcher.id))
        if self.curr_team.excel_export_settings:
            for color in self.curr_team.excel_export_settings.model_dump(exclude={'id'}).values():
                w = QWidget()
                w.setStyleSheet(f'background-color: {color}; border: 1px solid black;')
                self.layout_excel_export_settings.addWidget(w)

    def save(self):
        if not self.le_name.text():
            QMessageBox.critical(self, self.tr('Incomplete'),
                               self.tr('You must specify a team name'))
            return
        dispatcher_id = self.cb_dispatcher.currentData()
        if self.chk_new_mode.isChecked():
            if (team_name := self.le_name.text()) in [t.name for t in self.project.teams if not t.prep_delete]:
                QMessageBox.critical(self, self.tr('New Team'),
                                   self.tr('Team name {name} already exists.\nPlease choose a different name.')
                                   .format(name=team_name))
                return
            try:
                team_created = db_services.Team.create(team_name=self.le_name.text(), project_id=self.project.id,
                                                       dispatcher_id=dispatcher_id)
            except TransactionIntegrityError as e:
                if str(e.original_exc).startswith('UNIQUE constraint failed'):
                    QMessageBox.critical(self, self.tr('Error'),
                                       self.tr('A team named "{name}" already exists but is marked for deletion.\n'
                                             'You must first synchronize with the server database '
                                             'to successfully complete this action.')
                                       .format(name=self.le_name.text()))
                else:
                    QMessageBox.critical(self, self.tr('Error'), f'{e}')
                return

            QMessageBox.information(self, self.tr('New Team'),
                                  self.tr('The team has been created:\n{team}')
                                  .format(team=team_created))
        else:
            self.curr_team.name = self.le_name.text()
            self.curr_team.dispatcher = db_services.Person.get(dispatcher_id) if dispatcher_id else None
            updated_team = db_services.Team.update(self.curr_team)
            QMessageBox.information(self, self.tr('Team Update'),
                                  self.tr('Team has been updated:\n{team}')
                                  .format(team=updated_team))
        self.accept()

    def delete(self):
        deleted_team = db_services.Team.delete(self.curr_team.id)
        QMessageBox.information(self, self.tr('Team Deletion'),
                              self.tr('The team has been deleted:\n{team}')
                              .format(team=deleted_team))
        self.accept()

    def change_new_mode(self):
        if self.chk_new_mode.isChecked():
            self.bt_delete.setDisabled(True)
            self.bt_excel_export_settings.setDisabled(True)
        else:
            self.bt_delete.setEnabled(True)
            self.bt_excel_export_settings.setEnabled(True)






