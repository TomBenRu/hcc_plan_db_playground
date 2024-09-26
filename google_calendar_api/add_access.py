from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_calendar_api.authenticate import authenticate_google


def add_or_update_access_to_calendar(calendar_id: str, email: str, role: str = 'reader'):
    """
    Diese Funktion fügt einem Nutzer Zugriffsrechte hinzu oder aktualisiert die bestehenden Rechte, wenn sie bereits vorhanden sind.

    :param calendar_id: Die Kalender-ID des Kalenders.
    :param email: Die E-Mail-Adresse des Nutzers.
    :param role: Die Zugriffsrolle (default: 'reader'). Mögliche Werte: 'owner', 'writer', 'reader', 'freeBusyReader'.
    :return: Die erstellte oder aktualisierte ACL-Regel oder None bei einem Fehler.
    """
    creds = authenticate_google()
    service = build('calendar', 'v3', credentials=creds)

    try:
        # Bestehende ACLs für den Kalender abrufen
        acl_result = service.acl().list(calendarId=calendar_id).execute()
        acl_entries = acl_result.get('items', [])

        # Überprüfen, ob die E-Mail bereits Zugriff hat
        for acl in acl_entries:
            if acl['scope'].get('value') == email:
                # Wenn die Berechtigung existiert, aktualisiere sie nur, wenn die Rolle anders ist
                if acl['role'] != role:
                    acl_id = acl['id']
                    acl['role'] = role
                    updated_rule = service.acl().update(calendarId=calendar_id, ruleId=acl_id, body=acl).execute()
                    print(f"Zugriffsregel für {email} aktualisiert auf Rolle {role}.")
                    return updated_rule
                else:
                    print(f"{email} hat bereits die Rolle {role}. Keine Änderung erforderlich.")
                    return acl

        # Wenn keine Zugriffsregel für die E-Mail existiert, eine neue Regel hinzufügen
        rule = {
            'scope': {
                'type': 'user',
                'value': email
            },
            'role': role
        }

        created_rule = service.acl().insert(calendarId=calendar_id, body=rule).execute()
        print(f"Zugriffsregel erfolgreich hinzugefügt für {email} mit Rolle {role}.")
        return created_rule

    except HttpError as error:
        print(f"Fehler beim Hinzufügen oder Aktualisieren der Zugriffsregel: {error}")
        return None
