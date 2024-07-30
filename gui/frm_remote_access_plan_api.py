import json

import jwt
import requests
from PySide6.QtWidgets import QDialog, QVBoxLayout, QGroupBox, QFormLayout, QComboBox, QDialogButtonBox, QMessageBox

from configuration import api_remote_config


class DlgRemoteAccessPlanApi(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Plan API')

        self.config_remote = api_remote_config.current_config_handler.get_api_remote()
        self.session = requests.Session()
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
        for key, value in self.config_remote:
            if not key.startswith('endpoint_get'):
                continue
            self.combo_endpoint.addItem(key, value)

    def create_button_box(self):
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def login_to_api(self):
        response = self.session.post(f'{self.config_remote.host}/{self.config_remote.endpoint_auth}',
                                     data={'username': self.config_remote.username,
                                           'password': self.config_remote.password})
        payload = jwt.decode(response.json()['access_token'], options={"verify_signature": False})
        QMessageBox.information(self, 'Login', f'Eingeloggt als: {", ".join(payload["roles"])}')
        self.session.headers.update({'Authorization': f'Bearer {response.json()["access_token"]}'})

    def accept(self):
        endpoint = self.combo_endpoint.currentData()
        response = self.session.get(f'{self.config_remote.host}/{endpoint}')
        print(response.json())


