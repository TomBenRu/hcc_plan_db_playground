"""Desktop-Auth-Modul: Token-Persistenz, Login-Dialog, Startup-Bootstrap.

Hinweis: LoginDialog wird bewusst **nicht** hier re-exportiert, weil es
api_client.client importiert, und api_client.client wiederum token_store
braucht. Damit der Kreis nicht schliesst: `from gui.auth.login_dialog
import LoginDialog` direkt aus dem Submodul importieren.
"""

from gui.auth.token_store import (
    TokenStoreError,
    clear_refresh_token,
    load_refresh_token,
    save_refresh_token,
)

__all__ = [
    "TokenStoreError",
    "clear_refresh_token",
    "load_refresh_token",
    "save_refresh_token",
]
