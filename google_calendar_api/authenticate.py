import json

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError

from exceptions.google_api import CredentialsNotAvailableError

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_NAME_CREDENTIALS = 'calendar_api_credentials'
SERVICE_NAME_TOKEN_DATA = 'calendar_api_token_data'
USER_NAME = 'hcc_plan'


def authenticate_google():
    credentials = keyring.get_password(SERVICE_NAME_CREDENTIALS, USER_NAME)
    token_data = keyring.get_password(SERVICE_NAME_TOKEN_DATA, USER_NAME)

    creds = None
    # Wenn Token schon existiert, laden
    if token_data:
        token_data = json.loads(token_data)
        creds: Credentials = Credentials.from_authorized_user_info(token_data, SCOPES)
    # Wenn keine (gültigen) Anmeldeinformationen vorhanden, melde Benutzer erneut an
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                save_token_data(creds.to_json())
            except RefreshError:
                print("Refresh token invalid. Forcing re-authentication.")
                keyring.delete_password(SERVICE_NAME_TOKEN_DATA, USER_NAME)
                return authenticate_google()  # Rekursiver Aufruf für Neuanmeldung
        else:
            if credentials:
                credentials = json.loads(credentials)
                flow = InstalledAppFlow.from_client_config(credentials, SCOPES)
                creds = flow.run_local_server(port=0)

                save_token_data(creds.to_json())
            else:
                raise CredentialsNotAvailableError("Keine gültigen Credentials vorhanden!")
    return creds


def save_credentials(path_to_credentials_file: str):
    with open(path_to_credentials_file, 'r') as f:
        credentials = json.load(f)
    keyring.set_password(SERVICE_NAME_CREDENTIALS, USER_NAME, json.dumps(credentials))


def save_token_data(token_data: str):
    keyring.set_password(SERVICE_NAME_TOKEN_DATA, USER_NAME, token_data)
