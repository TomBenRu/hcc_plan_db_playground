"""Übernimmt aktive Person-Einträge als WebUser.

Bedingungen:
  - Person.prep_delete IS NULL  (nicht zum Löschen vorgemerkt)
  - Person.role ist einem WebUserRole zuordenbar
  - Person.email ist nicht leer

Passwörter sind bereits bcrypt-gehasht und werden direkt übernommen.
Das Skript ist idempotent: bereits vorhandene WebUser werden übersprungen.

Ausführung:
    uv run scripts/seed_web_users.py
"""

import sys
import os

# Windows: UTF-8 für stdout erzwingen
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import Session, select
from database.database import engine
from database.enums import Role
from database.models import Person
from web_api.models.web_models import WebUser, WebUserRole, WebUserRoleLink

# ── Rollen-Mapping: Person.role → WebUserRole ─────────────────────────────────
# Personen mit role=None erhalten die Standardrolle (ROLE_DEFAULT).

ROLE_MAP: dict[Role, WebUserRole] = {
    Role.SUPERVISOR: WebUserRole.admin,
    Role.ADMIN:      WebUserRole.admin,
    Role.DISPATCHER: WebUserRole.dispatcher,
    Role.EMPLOYEE:   WebUserRole.employee,
    Role.APPRENTICE: WebUserRole.employee,
}

# Standardrolle für Personen ohne zugewiesene Rolle
ROLE_DEFAULT = WebUserRole.employee


def seed(dry_run: bool = False) -> None:
    created = skipped_existing = skipped_no_role = skipped_no_email = skipped_dup_email = 0

    with Session(engine) as session:
        persons = session.exec(
            select(Person).where(Person.prep_delete.is_(None))  # type: ignore[attr-defined]
        ).all()

        print(f"Gefundene aktive Personen: {len(persons)}")

        # Bereits vorhandene person_ids und emails in web_user sammeln (für Duplikat-Check)
        existing_person_ids = set(
            row for row in session.exec(
                select(WebUser.person_id).where(WebUser.person_id.is_not(None))  # type: ignore[attr-defined]
            ).all()
        )
        existing_emails = set(
            session.exec(select(WebUser.email)).all()
        )

        for person in persons:
            # ── Validierungen ──
            if not person.email or not person.email.strip():
                print(f"  ÜBERSPRUNGEN (keine E-Mail):  {person.f_name} {person.l_name}")
                skipped_no_email += 1
                continue

            web_role = ROLE_MAP.get(person.role) if person.role else None  # type: ignore[arg-type]
            if web_role is None:
                # Unbekannte oder fehlende Rolle → Standardrolle
                web_role = ROLE_DEFAULT
                print(f"  STANDARD-ROLLE ({ROLE_DEFAULT.value}): {person.f_name} {person.l_name} (role={person.role})")

            if person.id in existing_person_ids:
                skipped_existing += 1
                continue

            email = person.email.strip().lower()
            if email in existing_emails:
                print(f"  ÜBERSPRUNGEN (E-Mail-Duplikat '{email}'): {person.f_name} {person.l_name}")
                skipped_dup_email += 1
                continue

            # ── WebUser anlegen ──
            web_user = WebUser(
                person_id=person.id,
                email=email,
                hashed_password=person.password,  # bereits bcrypt-gehasht
                is_active=True,
            )

            print(f"  ERSTELLE: {email}  [{web_role.value}]")

            if not dry_run:
                session.add(web_user)
                session.flush()  # ID wird benötigt für das Link-Objekt

                role_link = WebUserRoleLink(
                    web_user_id=web_user.id,
                    role=web_role,
                )
                session.add(role_link)

            existing_emails.add(email)
            existing_person_ids.add(person.id)
            created += 1

        if not dry_run:
            session.commit()

    # ── Zusammenfassung ──
    label = "(DRY RUN) " if dry_run else ""
    print()
    print(f"-- Ergebnis {label}----------------------------")
    print(f"  Erstellt:                {created}")
    print(f"  Bereits vorhanden:       {skipped_existing}")
    print(f"  Uebersprungen (E-Mail):  {skipped_no_email}")
    print(f"  Uebersprungen (Duplik.): {skipped_dup_email}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN — keine Änderungen werden geschrieben ===\n")
    seed(dry_run=dry_run)
