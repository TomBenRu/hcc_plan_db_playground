import datetime
from uuid import UUID

import jwt
import requests
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QGroupBox, QFormLayout, QComboBox, QDialogButtonBox, QMessageBox,
                               QWidget)
from pydantic import BaseModel

from commands import command_base_classes
from commands.database_commands import entities_api_to_db_commands
from configuration import api_remote_config
from database import schemas_plan_api, db_services, schemas
from database.schemas_plan_api import AvailDay
from database.special_schema_requests import get_locations_of_team_at_date, get_persons_of_team_at_date


def get_locations_actors_in_period(start: datetime.date, end: datetime.date,
                                   team_id: UUID) -> tuple[set[UUID], set[UUID]]:
    """Gibt ein Tuple von Sets zurück: location_ids, actor_ids"""
    location_ids = set()
    actor_ids = set()
    for delta in range((end - start).days + 1):
        location_ids |= {
            loc.id for loc in
            get_locations_of_team_at_date(team_id, start + datetime.timedelta(days=delta))}
        actor_ids |= {
            pers.id for pers in
            get_persons_of_team_at_date(team_id, start + datetime.timedelta(days=delta))}
    return location_ids, actor_ids


class DlgChooseTeam(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent)
        self.setWindowTitle('Team')

        self.project_id = project_id
        self.team_id: UUID | None = None
        self.layout = QVBoxLayout(self)
        self.group_team = QGroupBox('Team')
        self.layout.addWidget(self.group_team)
        self.form_team = QFormLayout(self.group_team)
        self.combo_team = QComboBox(self)
        self.form_team.addRow('auswählen:', self.combo_team)
        self.fill_combo_team()

        self.create_button_box()

    def fill_combo_team(self):
        for team in db_services.Team.get_all_from__project(self.project_id):
            self.combo_team.addItem(team.name, team.id)

    def create_button_box(self):
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def accept(self):
        self.team_id = self.combo_team.currentData()
        super().accept()



class DlgRemoteAccessPlanApi(QDialog):
    def __init__(self, parent=None, project_id: UUID = None):
        super().__init__(parent)
        self.setWindowTitle('Plan API')

        self.project_id = project_id
        self.controller = command_base_classes.ContrExecUndoRedo()
        self.config_remote = api_remote_config.current_config_handler.get_api_remote()
        self.session = requests.Session()
        self.remote_schemas: dict[str, BaseModel] = {'get_project': schemas_plan_api.Project,
                                                     'get_persons': schemas_plan_api.PersonShow,
                                                     'get_teams': schemas_plan_api.Team,
                                                     'get_plan_periods': schemas_plan_api.PlanPeriod}
        self.login_to_api()

        self.setup_layout()

    def setup_layout(self):
        self.layout = QVBoxLayout(self)
        self.group_endpoint = QGroupBox('Endpoint')
        self.layout.addWidget(self.group_endpoint)
        self.form_endpoint = QFormLayout(self.group_endpoint)
        self.combo_endpoint = QComboBox(self)
        self.form_endpoint.addRow('auswählen:', self.combo_endpoint)
        self.fill_combo_endpoint()

        self.create_button_box()

    def fill_combo_endpoint(self):
        for key, value in self.config_remote.endpoints:
            if not key.startswith('get'):
                continue
            self.combo_endpoint.addItem(key, value)

    def create_button_box(self):
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def login_to_api(self):
        response = self.session.post(f'{self.config_remote.host}/{self.config_remote.endpoints.auth}',
                                     data={'username': self.config_remote.authentication.username,
                                           'password': self.config_remote.authentication.password})
        payload = jwt.decode(response.json()['access_token'], options={"verify_signature": False})
        QMessageBox.information(self, 'Login', f'Eingeloggt als: {", ".join(payload["roles"])}')
        self.session.headers.update({'Authorization': f'Bearer {response.json()["access_token"]}'})

    def proof_for_data_in_db(self, response: requests.Response):
        schema = self.remote_schemas[self.combo_endpoint.currentText()]
        if self.combo_endpoint.currentText() == 'get_project':
            entity: schemas_plan_api.Project = schema.model_validate(response.json())
            project_in_db = db_services.Project.get_all()
            if entity.name in [p.name for p in project_in_db] or entity.id in [p.id for p in project_in_db]:
                QMessageBox.critical(self, 'Fehler', f'Projekt mit diesem Namen oder ID existiert bereits:\n'
                                                     f'{entity.name}, id: {entity.id}')
                return
            else:
                command = entities_api_to_db_commands.WriteProjectToDB(entity)
                self.controller.execute(command)
                QMessageBox.information(self, 'Erfolg', f'Projekt mit Namen {entity.name} und ID {entity.id}\n'
                                                        f'wurde angelegt.')
        elif self.combo_endpoint.currentText() == 'get_persons':
            for p in response.json():
                entity: schemas_plan_api.PersonShow = schema.model_validate(p)
                persons_in_db = db_services.Person.get_all_from__project(self.project_id)
                if (entity.f_name in [p.f_name for p in persons_in_db]
                        or entity.l_name in [p.l_name for p in persons_in_db]
                        or entity.id in [p.id for p in persons_in_db]):
                    QMessageBox.critical(self, 'Fehler', f'Person mit diesem Namen oder ID existiert bereits:\n'
                                                         f'{entity.f_name} {entity.l_name}, id: {entity.id}')
                    continue
                else:
                    command = entities_api_to_db_commands.WritePersonToDB(entity)
                    self.controller.execute(command)
                    QMessageBox.information(self, 'Erfolg',
                                            f'Person mit Namen {entity.f_name} {entity.l_name} und ID {entity.id}\n'
                                            f'wurde angelegt.')
        elif self.combo_endpoint.currentText() == 'get_teams':
            for t in response.json():
                entity: schemas_plan_api.Team = schema.model_validate(t)
                teams_in_db = db_services.Team.get_all_from__project(self.project_id)
                if entity.name in [t.name for t in teams_in_db] or entity.id in [t.id for t in teams_in_db]:
                    QMessageBox.critical(self, 'Fehler', f'Team mit diesem Namen oder ID existiert bereits:\n'
                                                         f'{entity.name}, id: {entity.id}')
                    continue
                else:
                    command = entities_api_to_db_commands.WriteTeamToDB(entity)
                    self.controller.execute(command)
                    QMessageBox.information(self, 'Erfolg',
                                            f'Team mit Namen {entity.name} und ID {entity.id}\n'
                                            f'wurde angelegt.')
        elif self.combo_endpoint.currentText() == 'get_plan_periods':
            team_id = response.json()[0]['team']['id']
            question = QMessageBox.warning(self, 'Planperioden hinzufügen',
                                           f'Wenn sie fortfahren werden alle zum Löschen markierten Planperioden '
                                           f'endgültig gelöscht.\nSind sie sicher, dass sie fortfahren wollen?',
                                           QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Cancel)
            if question == QMessageBox.StandardButton.Cancel:
                return
            db_services.PlanPeriod.delete_prep_deletes(UUID(team_id))
            for p in sorted(response.json(), key=lambda x: x['start']):
                entity: schemas_plan_api.PlanPeriod = schemas_plan_api.PlanPeriod.model_validate(p)
                plan_periods_in_db = db_services.PlanPeriod.get_all_from__project(self.project_id)
                if entity.id in [p.id for p in plan_periods_in_db]:
                    QMessageBox.critical(self, 'Fehler', f'Plan-Periode mit dieser ID existiert bereits:\n'
                                                         f'id: {entity.id}')
                    continue
                else:
                    question = QMessageBox.question(self, 'Planperiode hinzufügen',
                                                    f'Soll die Planperiode hinzugefügt werde?\n'
                                                    f'{entity.start: %d.%m.%y} - {entity.end: %d.%m.%y}')
                    if question == QMessageBox.StandardButton.Yes:
                        location_ids, person_ids = get_locations_actors_in_period(entity.start, entity.end,
                                                                                  entity.team.id)
                        command = entities_api_to_db_commands.WritePlanPeriodToDB(entity, person_ids, location_ids)
                        self.controller.execute(command)
                        QMessageBox.information(self, 'Erfolg',
                                                f'Plan {entity.start: %d.%m.%y} - {entity.end: %d.%m.%y}, '
                                                f'ID {entity.id}\nwurde angelegt.')

    def write_entity_to_db(self, entity):
        ...

    def get_data_from_endpoint(self):
        endpoint = self.combo_endpoint.currentData()
        if self.combo_endpoint.currentText() == 'get_plan_periods':
            dlg = DlgChooseTeam(self, self.project_id)
            if not dlg.exec():
                return
            team_id = str(dlg.team_id)
            response = self.session.get(f'{self.config_remote.host}/{endpoint}', params={'team_id': team_id})
        else:
            response = self.session.get(f'{self.config_remote.host}/{endpoint}')
        self.proof_for_data_in_db(response)

    def accept(self):
        self.get_data_from_endpoint()
        # super().accept()


class FetchAvailDaysFromAPI:
    def __init__(self):
        self.session = requests.Session()
        self.config_remote = api_remote_config.current_config_handler.get_api_remote()

    def fetch_data(self, parent: QWidget, plan_period_id: UUID) -> list[dict]:
        if not self.session.headers.get('Authorization'):
            self.authorize(parent)
        while True:
            response = self.session.get(f'{self.config_remote.host}/{self.config_remote.endpoints.fetch_avail_days}',
                                        params={'planperiod_id': str(plan_period_id)})
            if response.status_code == 200 and response.json().get('status_code') != 401:
                QMessageBox.information(parent, 'Erfolg', 'Daten wurden erfolgreich heruntergeladen.')
                break
            self.authorize(parent)

        data = {person_id: {'notes': dict_notes_days['notes'],
                            'days': [AvailDay.model_validate(d) for d in dict_notes_days['days']]}
                for person_id, dict_notes_days in response.json().items()}
        return data

    def authorize(self, parent: QWidget):
        response = self.session.post(f'{self.config_remote.host}/{self.config_remote.endpoints.auth}',
                                     data={'username': self.config_remote.authentication.username,
                                           'password': self.config_remote.authentication.password})
        payload = jwt.decode(response.json()['access_token'], options={"verify_signature": False})
        QMessageBox.information(parent, 'Login', f'Eingeloggt als: {", ".join(payload["roles"])}')
        self.session.headers.update({'Authorization': f'Bearer {response.json()["access_token"]}'})


fetch_available_days = FetchAvailDaysFromAPI()





