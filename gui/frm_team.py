from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QComboBox, QHBoxLayout, QGridLayout, QPushButton, \
    QMessageBox, QFormLayout, QCheckBox, QDialogButtonBox
from pony.orm import TransactionIntegrityError

from database import schemas, db_services
from gui.tools.qcombobox_find_data import QComboBoxToFindData


class FrmTeam(QDialog):
    def __init__(self, parent: QWidget, project: schemas.ProjectShow, team: schemas.TeamShow | None):
        super().__init__(parent=parent)

        self.setWindowTitle('Team')

        self.project = project
        self.curr_team = team
        self.new_team: schemas.TeamCreate | None = None
        self.new_mode = False
        self.to_delete_status = False

        self.layout = QFormLayout(self)

        self.le_name = QLineEdit()
        self.cb_dispatcher = QComboBoxToFindData()
        self.bt_excel_export_settings = QPushButton('Ändern')
        self.layout_excel_export_settings = QHBoxLayout()
        self.layout_excel_export_settings.setContentsMargins(0, 20, 0, 0)
        self.layout_excel_export_settings.setSpacing(0)
        self.bt_excel_export_settings.setLayout(self.layout_excel_export_settings)
        self.bt_delete = QPushButton('Löschen', clicked=self.delete)

        self.chk_new_mode = QCheckBox('Als neues Team speichern?')
        self.chk_new_mode.toggled.connect(self.change_new_mode)

        self.bt_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bt_box.addButton(self.bt_delete, QDialogButtonBox.ButtonRole.ActionRole)
        self.bt_box.accepted.connect(self.save)
        self.bt_box.rejected.connect(self.reject)

        self.layout.addRow('Name', self.le_name)
        self.layout.addRow('Planer*in', self.cb_dispatcher)
        self.layout.addRow('Excel-Settings', self.bt_excel_export_settings)
        self.layout.addRow(self.chk_new_mode)
        self.layout.addRow(self.bt_box)

        self.autofill()

    def autofill(self):
        self.cb_dispatcher.addItem(QIcon('resources/toolbar_icons/icons/cross.png'), 'Kein Planer', None)
        for p in self.project.persons:
            self.cb_dispatcher.addItem(QIcon('resources/toolbar_icons/icons/user-business.png'),
                                       f'{p.f_name} {p.l_name}', p.id)
        if not self.curr_team or self.new_mode:
            self.new_mode = True
            self.bt_excel_export_settings.setDisabled(True)
            self.bt_delete.setDisabled(True)
            return
        self.bt_excel_export_settings.setEnabled(True)
        self.bt_delete.setEnabled(True)
        self.le_name.setText(self.curr_team.name)
        if self.curr_team.dispatcher:
            self.cb_dispatcher.setCurrentIndex(self.cb_dispatcher.findData(self.curr_team.dispatcher.id))
        if self.curr_team.excel_export_settings:
            for color in self.curr_team.excel_export_settings.dict(exclude={'id'}).values():
                w = QWidget()
                w.setStyleSheet(f'background-color: {color}; border: 1px solid black;')
                self.layout_excel_export_settings.addWidget(w)

    def save(self):
        if not self.le_name.text():
            QMessageBox.critical(self, 'unvollständig', 'Sie müssen einen Team-Namen angeben')
            return
        dispatcher_id = self.cb_dispatcher.currentData()
        if self.new_mode:
            if (team_name := self.le_name.text()) in [t.name for t in self.project.teams if not t.prep_delete]:
                QMessageBox.critical(self, 'Neues Team', f'Teamname {team_name} ist schon vorhanden.\n'
                                                         f'Bitte wählen sie einen anderen Namen.')
                return
            try:
                team_created = db_services.Team.create(team_name=self.le_name.text(), project_id=self.project.id,
                                                       dispatcher_id=dispatcher_id)
            except TransactionIntegrityError as e:
                if str(e.original_exc).startswith('UNIQUE constraint failed'):
                    QMessageBox.critical(self, 'Fehler', f'Ein Team mit Namen "{self.le_name.text()}" ist beireits '
                                                         f'vorhanden aber zum Löschen markiert.\n'
                                                         f'Sie müssen zuerst mit der Serverdatenbank synchronisieren,'
                                                         f'damit sie diese Aktion erfolgreich durchführen können.')
                else:
                    QMessageBox.critical(self, 'Fehler', f'{e}')
                return

            QMessageBox.information(self, 'Neues Team', f'Das Team wurde erstellt:\n{team_created}')
        else:
            self.curr_team.name = self.le_name.text()
            self.curr_team.dispatcher = db_services.Person.get(dispatcher_id) if dispatcher_id else None
            updated_team = db_services.Team.update(self.curr_team)
            QMessageBox.information(self, 'Team Update', f'Team wurde upgedated:\n{updated_team}')
        self.accept()

    def delete(self):
        deleted_team = db_services.Team.delete(self.curr_team.id)
        QMessageBox.information(self, 'Team Löschung', f'Das Team wurde gelöscht:\n{deleted_team}')
        self.accept()

    def change_new_mode(self):
        if self.chk_new_mode.isChecked():
            self.bt_delete.setDisabled(True)
            self.bt_excel_export_settings.setDisabled(True)
        else:
            self.bt_delete.setEnabled(True)
            self.bt_excel_export_settings.setEnabled(True)






