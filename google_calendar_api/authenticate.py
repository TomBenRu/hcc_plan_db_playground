# Wenn der Zugriff auf den Kalender nur zum Erstellen/Ändern von Events benötigt wird
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar']
credentials_dir = os.path.join(os.path.dirname(__file__), 'credentials')


def authenticate_google():
    creds = None
    # Wenn Token schon existiert, laden
    if os.path.exists(token := os.path.join(credentials_dir, 'token.json')):
        creds = Credentials.from_authorized_user_file(token, SCOPES)
    # Wenn keine (gültigen) Anmeldeinformationen vorhanden, melde Benutzer erneut an
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(os.path.join(credentials_dir, 'credentials',
                                                                          'client_secret.json'),
                                                             SCOPES)
            creds = flow.run_local_server(port=0)
        # Speichere die Anmeldeinformationen für das nächste Mal
        with open(token, 'w') as token:
            token.write(creds.to_json())
    return creds