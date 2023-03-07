from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QComboBox, QHBoxLayout, QGridLayout, QPushButton, \
    QMessageBox
from pony.orm import TransactionIntegrityError

from database import schemas, db_services


class FrmTeam(QDialog):
    def __init__(self, parent: QWidget, project: schemas.ProjectShow, team: schemas.TeamShow):
        super().__init__(parent=parent)

        self.setWindowTitle('Team')

        self.project = project
        self.team = team
        self.new_team_mode = False

        self.layout = QGridLayout(self)

        self.lb_name = QLabel('Name')
        self.le_name = QLineEdit()
        self.lb_dispatcher = QLabel('Planung')
        self.cb_dispatcher = QComboBox()
        self.lb_excel_export_settings = QLabel('Excel-Settings')
        self.bt_excel_export_settings = QPushButton('Ändern')
        self.layout_excel_export_settings = QHBoxLayout()
        self.layout_excel_export_settings.setContentsMargins(0, 20, 0, 0)
        self.layout_excel_export_settings.setSpacing(0)
        self.bt_excel_export_settings.setLayout(self.layout_excel_export_settings)
        self.bt_new = QPushButton('Neues Team', clicked=self.data_as_new_team)
        self.bt_save = QPushButton('Speichern', clicked=self.save)
        self.bt_delete = QPushButton('Löschen', clicked=self.delete)
        self.lb_note_new_team = QLabel('Angaben werden als neues Team gespeichert!')

        self.layout.addWidget(self.lb_name, 0, 0)
        self.layout.addWidget(self.le_name, 0, 1)
        self.layout.addWidget(self.lb_dispatcher, 1, 0)
        self.layout.addWidget(self.cb_dispatcher, 1, 1)
        self.layout.addWidget(self.lb_excel_export_settings, 2, 0)
        self.layout.addWidget(self.bt_excel_export_settings, 2, 1)
        self.layout.addWidget(self.bt_new, 4, 1)
        self.layout.addWidget(self.bt_delete, 5, 1)
        self.layout.addWidget(self.bt_save, 6, 1)

        self.autofill()

    def autofill(self):
        self.cb_dispatcher.addItem(QIcon('resources/toolbar_icons/icons/cross.png'), 'Kein Planer', None)
        for p in self.project.persons:
            self.cb_dispatcher.addItem(QIcon('resources/toolbar_icons/icons/user-business.png'),
                                       f'{p.f_name} {p.l_name}', p)
        if not self.team or self.new_team_mode:
            self.new_team_mode = True
            self.bt_excel_export_settings.setDisabled(True)
            self.bt_delete.setDisabled(True)
            return
        self.bt_excel_export_settings.setEnabled(True)
        self.bt_delete.setEnabled(True)
        self.le_name.setText(self.team.name)
        if self.team.dispatcher:
            self.cb_dispatcher.setCurrentText(f'{self.team.dispatcher.f_name} {self.team.dispatcher.l_name}')
        if self.team.excel_export_settings:
            for color in self.team.excel_export_settings.dict(exclude={'id'}).values():
                w = QWidget()
                w.setStyleSheet(f'background-color: {color}; border: 1px solid black;')
                self.layout_excel_export_settings.addWidget(w)

    def save(self):
        if not self.le_name.text():
            QMessageBox.critical(self, 'unvollständig', 'Sie müssen einen Team-Namen angeben')
            return
        dispatcher_id = self.cb_dispatcher.currentData().id if self.cb_dispatcher.currentData() else None
        if self.new_team_mode:
            if (team_name := self.le_name.text()) in [t.name for t in self.project.teams if not t.prep_delete]:
                QMessageBox.critical(self, 'Neues Team', f'Teamname {team_name} ist schon vorhanden.\n'
                                                         f'Bitte wählen sie einen anderen Namen.')
                return
            try:
                team_created = db_services.new_team(team_name=self.le_name.text(), project_id=self.project.id,
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
            self.team.name = self.le_name.text()
            self.team.dispatcher = self.cb_dispatcher.currentData()
            updated_team = db_services.update_team(self.team)
            QMessageBox.information(self, 'Team Update', f'Team wurde upgedated:\n{updated_team}')
        self.accept()

    def delete(self):
        deleted_team = db_services.delete_team(self.team.id)
        QMessageBox.information(self, 'Team Löschung', f'Das Team wurde gelöscht:\n{deleted_team}')
        self.accept()

    def data_as_new_team(self):
        self.new_team_mode = False if self.new_team_mode else True
        if self.new_team_mode:
            self.layout.addWidget(self.lb_note_new_team, self.layout.rowCount(), 0, 1, 2)
            self.bt_new.setText('...zurück (vorh. Team)')
            self.cb_dispatcher.clear()
            for w in self.bt_excel_export_settings.findChildren(QWidget):
                w.setParent(None)
        else:
            if self.team:
                self.cb_dispatcher.clear()
                self.lb_note_new_team.setParent(None)
                self.bt_new.setText('Neues Team')
                for w in self.bt_excel_export_settings.findChildren(QWidget):
                    w.setParent(None)

        self.autofill()





