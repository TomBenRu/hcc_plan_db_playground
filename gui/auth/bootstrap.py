"""Startup-Flow: sicherstellen, dass der Desktop-API-Client eingeloggt ist.

Abfolge beim App-Start:
1. Silent-Login-Versuch mit dem im Keyring gespeicherten Refresh-Token.
2. Faellt der weg oder schlaegt fehl: LoginDialog anzeigen.
3. Bricht der User den Dialog ab, signalisiert `ensure_authenticated`
   False — der Aufrufer beendet die App.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QWidget

from gui.api_client.client import get_api_client
from gui.auth.login_dialog import LoginDialog


def ensure_authenticated(parent: QWidget | None = None) -> bool:
    """Garantiert einen eingeloggten API-Client oder signalisiert Abbruch.

    Returns True, wenn der Client nach Rueckkehr dieser Funktion ein
    gueltiges Access-Token hat. Returns False, wenn der User den
    Login-Dialog abgebrochen hat.
    """
    client = get_api_client()

    # Falls ein Refresh-Token im Keyring liegt: stillen Login probieren.
    # Bei Erfolg sind wir sofort durch — kein Dialog noetig.
    if client.try_silent_login():
        return True

    dialog = LoginDialog(client, parent=parent)
    return dialog.exec() == QDialog.DialogCode.Accepted