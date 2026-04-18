"""Initial-Admin-User fuer die Web-API anlegen (Bootstrap-Tool).

Loest das Henne-Ei-Problem beim ersten Start: ohne diesen Schritt existiert
kein Login-Konto, und damit kann niemand die Web-UI oder Desktop-API nutzen.

Das Skript arbeitet direkt gegen die DB — nicht ueber HTTP. Es muss auf dem
Server ausgefuehrt werden, wo DB-Zugriff existiert (gleiche DB-Credentials
wie die App). Passwoerter werden mit bcrypt gehasht (gleiches Verfahren wie
der Login-Endpoint via web_api.auth.service.hash_password).

Aufrufe:
    # Interaktiv (empfohlen):
    uv run scripts/create_admin.py --email owner@firma.de

    # Mit expliziter Rolle:
    uv run scripts/create_admin.py --email disp@firma.de --role dispatcher

    # Passwort zuruecksetzen bzw. Rolle ergaenzen:
    uv run scripts/create_admin.py --email owner@firma.de --force

    # Nicht-interaktiv (z. B. fuer CI/Scripted-Setup — unsicher, landet in
    # Shell-History; nur nutzen, wenn du weisst, was du tust):
    uv run scripts/create_admin.py --email o@f.de --password 'geheim1234'
"""

import argparse
import getpass
import os
import sys

# Windows: UTF-8 fuer stdout erzwingen
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# Projektroot in sys.path (fuer "database"- und "web_api"-Imports)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, select

from database.database import engine
from web_api.auth.service import hash_password
from web_api.models.web_models import WebUser, WebUserRole, WebUserRoleLink


EXIT_OK = 0
EXIT_USER_EXISTS = 2
EXIT_WEAK_PASSWORD = 3
EXIT_ABORTED = 4

MIN_PASSWORD_LENGTH = 8


def _prompt_password() -> str:
    """Liest Passwort via getpass (kein Terminal-Echo, keine Shell-History)."""
    pw1 = getpass.getpass("Passwort: ")
    if len(pw1) < MIN_PASSWORD_LENGTH:
        print(
            f"Fehler: Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein.",
            file=sys.stderr,
        )
        sys.exit(EXIT_WEAK_PASSWORD)
    pw2 = getpass.getpass("Passwort (Wiederholung): ")
    if pw1 != pw2:
        print("Fehler: Passwoerter stimmen nicht ueberein.", file=sys.stderr)
        sys.exit(EXIT_ABORTED)
    return pw1


def create_admin(email: str, role: WebUserRole, password: str | None, force: bool) -> int:
    email = email.strip().lower()

    with Session(engine) as session:
        existing = session.exec(select(WebUser).where(WebUser.email == email)).first()

        if existing and not force:
            print(
                f"Fehler: User mit E-Mail '{email}' existiert bereits "
                f"(user_id={existing.id}).",
                file=sys.stderr,
            )
            print(
                "        Nutze --force zum Passwort-Reset oder zur Rollen-Ergaenzung.",
                file=sys.stderr,
            )
            return EXIT_USER_EXISTS

        if password is None:
            password = _prompt_password()
        elif len(password) < MIN_PASSWORD_LENGTH:
            print(
                f"Fehler: Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein.",
                file=sys.stderr,
            )
            return EXIT_WEAK_PASSWORD

        hashed = hash_password(password)

        if existing:
            # --force: Passwort resetten + Rolle ergaenzen, falls fehlt.
            # (WebUserRoleLink hat Composite-PK (user_id, role) — Duplikat-Insert
            #  waere UNIQUE-Violation.)
            existing.hashed_password = hashed
            existing.is_active = True
            has_role = session.exec(
                select(WebUserRoleLink).where(
                    WebUserRoleLink.web_user_id == existing.id,
                    WebUserRoleLink.role == role,
                )
            ).first()
            if not has_role:
                session.add(WebUserRoleLink(web_user_id=existing.id, role=role))
            session.commit()
            print(
                f"[OK] Passwort fuer '{email}' zurueckgesetzt; "
                f"Rolle '{role.value}' gesichert."
            )
            print(f"     user_id = {existing.id}")
            return EXIT_OK

        web_user = WebUser(email=email, hashed_password=hashed, is_active=True)
        session.add(web_user)
        session.flush()  # benoetigt fuer web_user.id im Link-Objekt

        session.add(WebUserRoleLink(web_user_id=web_user.id, role=role))
        session.commit()

        print(f"[OK] User angelegt: {email}")
        print(f"     Rolle:    {role.value}")
        print(f"     user_id:  {web_user.id}")
        return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Legt einen Admin- oder Dispatcher-User in der Web-API an "
            "(Bootstrap-Tool, laeuft direkt gegen die DB)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Passwort wird interaktiv abgefragt (getpass), landet nicht in der "
            "Shell-History. Mit --password kann es explizit uebergeben werden, "
            "das ist aber nur fuer automatisierte Setups gedacht."
        ),
    )
    parser.add_argument(
        "--email",
        required=True,
        help="E-Mail-Adresse (wird zum Login-Namen).",
    )
    parser.add_argument(
        "--role",
        default="admin",
        choices=[r.value for r in WebUserRole],
        help="Rolle (default: admin).",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Passwort (unsicher — interaktive Eingabe bevorzugen).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Wenn User existiert: Passwort zuruecksetzen + Rolle ergaenzen.",
    )
    args = parser.parse_args(argv)

    if args.password:
        print(
            "Warnung: --password landet ggf. in der Shell-History. "
            "Interaktive Eingabe ist sicherer.",
            file=sys.stderr,
        )

    role = WebUserRole(args.role)
    return create_admin(args.email, role, args.password, args.force)


if __name__ == "__main__":
    sys.exit(main())
