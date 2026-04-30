"""DB-URL-Konfiguration mit keyring-Backing.

Reihenfolge:
1. Env-Var ``DATABASE_URL`` — höchste Priorität (Server-Deploys: Render, Docker, CI).
2. Systemkeychain (Desktop-Client / kompilierte EXE) — Fallback.
3. ``None`` — Aufrufer fällt auf SQLite zurück.

Auf Headless-Servern ohne Keyring-Backend ist der ``keyring``-Aufruf in try/except
gekapselt; fehlt der Backend, wird stillschweigend ``None`` zurückgegeben statt zu crashen.
"""

from __future__ import annotations

import os

KEYRING_SERVICE = "hcc_plan_db"
KEYRING_DATABASE_URL = "database_url"


def get_database_url() -> str | None:
    """Liefert die DB-URL aus Env-Var, sonst aus dem OS-Keyring, sonst ``None``."""
    if env_url := os.environ.get("DATABASE_URL"):
        return env_url

    try:
        import keyring

        if url := keyring.get_password(KEYRING_SERVICE, KEYRING_DATABASE_URL):
            return url
    except Exception:
        # keyring-Backend nicht verfuegbar (z.B. Headless-Server) — stilles Fallback
        pass

    return None


def save_database_url(url: str) -> None:
    """Schreibt die DB-URL in den OS-Keyring (Desktop-Setup)."""
    import keyring

    keyring.set_password(KEYRING_SERVICE, KEYRING_DATABASE_URL, url)


def delete_database_url() -> None:
    """Loescht den Keyring-Eintrag (z.B. fuer Account-Wechsel oder Cleanup)."""
    import keyring

    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_DATABASE_URL)
    except keyring.errors.PasswordDeleteError:
        pass