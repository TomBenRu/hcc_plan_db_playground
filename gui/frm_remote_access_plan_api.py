import json
import pprint
from typing import Union

import jwt
import requests
from PySide6.QtWidgets import QDialog, QVBoxLayout, QGroupBox, QFormLayout, QComboBox, QDialogButtonBox, QMessageBox
from pydantic import BaseModel

from configuration import api_remote_config
from database import schemas_plan_api, db_services


class DlgRemoteAccessPlanApi(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Plan API')

        self.config_remote = api_remote_config.current_config_handler.get_api_remote()
        self.session = requests.Session()
        self.remote_schemas: dict[str, BaseModel] = {'get_project': schemas_plan_api.Project,
                                                     'get_persons': schemas_plan_api.PersonShow,
                                                     'get_teams': schemas_plan_api.Team}
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
                QMessageBox.critical(self, 'Fehler', 'Projekt mit diesem Namen oder ID existiert bereits')
                return
            else:

        if isinstance(response.json(), list):
            pprint.pprint([schema.model_validate(d) for d in response.json()])
        else:
            pprint.pprint(schema.model_validate(response.json()))

    def write_entity_to_db(self, entity):
        ...

    def get_data_from_endpoint(self):
        endpoint = self.combo_endpoint.currentData()
        response = self.session.get(f'{self.config_remote.host}/{endpoint}')
        self.proof_for_data_in_db(response)

    def accept(self):
        self.get_data_from_endpoint()
        # super().accept()





