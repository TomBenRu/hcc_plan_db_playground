"""CLI-Helper: ``DATABASE_URL`` einmalig in den OS-Keyring schreiben.

Wird vom Desktop-Client / der kompilierten EXE genutzt, damit kein ``.env`` neben
der EXE liegen muss. Der gespeicherte Eintrag wird beim App-Start ueber
``configuration.db_config.get_database_url()`` ausgelesen.

Verwendung:
    uv run python scripts/set_db_url_in_keyring.py

Liest die DB-URL ueber ``getpass`` (kein Echo im Terminal) und persistiert sie via
``keyring`` unter Service ``hcc_plan_db`` / Item ``database_url``.

Loeschen des Eintrags:
    uv run python -c "from configuration.db_config import delete_database_url; delete_database_url()"
"""

from __future__ import annotations

import sys
from getpass import getpass

from configuration.db_config import (
    KEYRING_DATABASE_URL,
    KEYRING_SERVICE,
    get_database_url,
    save_database_url,
)


def main() -> int:
    print(f"Service: {KEYRING_SERVICE!r} / Item: {KEYRING_DATABASE_URL!r}")

    if existing := get_database_url():
        masked = existing[:18] + "…" + existing[-12:] if len(existing) > 30 else "***"
        print(f"Aktuell gespeichert: {masked}")
        if input("Ueberschreiben? [y/N] ").strip().lower() not in {"y", "j"}:
            print("Abgebrochen.")
            return 0

    url = getpass("DATABASE_URL eingeben (kein Echo): ").strip()
    if not url:
        print("Keine URL eingegeben — abgebrochen.", file=sys.stderr)
        return 1

    if not url.startswith(("postgresql://", "postgres://", "sqlite:///")):
        print(
            f"Warnung: URL beginnt nicht mit postgresql:// / postgres:// / sqlite:/// "
            f"— trotzdem speichern? [y/N] ",
            end="",
        )
        if input().strip().lower() not in {"y", "j"}:
            print("Abgebrochen.")
            return 1

    save_database_url(url)
    print("Gespeichert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
