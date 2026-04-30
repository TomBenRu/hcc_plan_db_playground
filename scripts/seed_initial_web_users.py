"""Seed initialer WebUser-Eintraege fuer Admins, Dispatcher und aktuelle Team-Mitglieder.

Erstellt fuer jede Person, die zum aktuellen Zeitpunkt mindestens **eine** der
folgenden drei Beziehungen hat, einen WebUser:

* **Admin**:      ``Person.admin_of_project_id IS NOT NULL`` ODER
                  ``Person.role IN {ADMIN, SUPERVISOR}``
* **Dispatcher**: ``Team.dispatcher_id == person.id`` ODER
                  ``Person.role == DISPATCHER``
* **Employee**:   aktive ``TeamActorAssign`` (``start <= today`` UND
                  (``end IS NULL`` ODER ``end > today``))

Die zugewiesenen WebUser-Rollen entsprechen 1:1 diesen drei Beziehungen — eine
Person kann mehrere Rollen erhalten (z. B. Admin + Employee).

Konfiguration:

* E-Mail: ``Person.email`` (case-insensitive normalisiert)
* Passwort: ``initial_password`` (bcrypt-Hash; einmal gehasht, fuer alle Nutzer)

Doppelte E-Mails (mehrere Personen mit identischer E-Mail) werden zu einem
WebUser zusammengefasst, Rollen werden vereinigt. Idempotent: Bestehende
WebUser werden nicht neu angelegt (Passwort bleibt unangetastet), aber
fehlende Rollen werden ergaenzt — vorhandene Rollen unveraendert.

Aufruf:
    DATABASE_URL="postgresql://..." uv run python -u scripts/seed_initial_web_users.py
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import date

# Projekt-Root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import or_, select as sa_select
from sqlmodel import Session, create_engine

from database.enums import Role as PersonRoleEnum
from database.models import Person, Team, TeamActorAssign
from web_api.auth.service import hash_password
from web_api.models.web_models import WebUser, WebUserRole, WebUserRoleLink


PASSWORD = "initial_password"


def _derive_roles(
    person: Person,
    dispatcher_person_ids: set,
    active_team_person_ids: set,
) -> set[WebUserRole]:
    """Leitet WebUser-Rollen aus den drei Beziehungen ab."""
    roles: set[WebUserRole] = set()

    if person.admin_of_project_id is not None or person.role in (
        PersonRoleEnum.ADMIN,
        PersonRoleEnum.SUPERVISOR,
    ):
        roles.add(WebUserRole.admin)

    if person.id in dispatcher_person_ids or person.role == PersonRoleEnum.DISPATCHER:
        roles.add(WebUserRole.dispatcher)

    if person.id in active_team_person_ids:
        roles.add(WebUserRole.employee)

    return roles


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Fehler: DATABASE_URL nicht gesetzt.", file=sys.stderr)
        return 1

    engine = create_engine(db_url)
    today = date.today()

    with Session(engine) as session:
        persons: list[Person] = list(
            session.execute(
                sa_select(Person).where(Person.prep_delete.is_(None))
            ).scalars().all()
        )
        print(f"Aktive Personen (nicht soft-deleted): {len(persons)}")

        dispatcher_person_ids: set = set(
            session.execute(
                sa_select(Team.dispatcher_id).where(Team.dispatcher_id.is_not(None))
            ).scalars().all()
        )
        print(f"Distinct Dispatcher-Person-IDs: {len(dispatcher_person_ids)}")

        active_team_person_ids: set = set(
            session.execute(
                sa_select(TeamActorAssign.person_id)
                .where(TeamActorAssign.start <= today)
                .where(or_(TeamActorAssign.end.is_(None), TeamActorAssign.end > today))
            ).scalars().all()
        )
        print(f"Distinct aktuell zugewiesene Team-Personen: {len(active_team_person_ids)}")

        existing_emails: set[str] = set(
            session.execute(sa_select(WebUser.email)).scalars().all()
        )
        if existing_emails:
            print(f"Bereits vorhandene WebUser: {len(existing_emails)}")

        by_email: dict[str, dict] = defaultdict(
            lambda: {"person_id": None, "roles": set(), "persons_count": 0}
        )
        skipped_no_email = 0
        skipped_no_relation = 0
        for p in persons:
            roles = _derive_roles(p, dispatcher_person_ids, active_team_person_ids)
            if not roles:
                skipped_no_relation += 1
                continue
            if not p.email or not p.email.strip():
                skipped_no_email += 1
                continue
            email = p.email.strip().lower()
            entry = by_email[email]
            entry["persons_count"] += 1
            if entry["person_id"] is None:
                entry["person_id"] = p.id
            entry["roles"] |= roles

        print(f"Personen ohne Admin/Dispatcher/aktive Team-Beziehung: {skipped_no_relation}")
        print(f"Personen mit Beziehung aber ohne E-Mail uebersprungen: {skipped_no_email}")
        print(f"Distinct Email-Buckets: {len(by_email)}")
        print()

        hashed_pw = hash_password(PASSWORD)

        created = updated = unchanged = 0
        roles_histogram: dict[str, int] = defaultdict(int)

        for email, entry in sorted(by_email.items()):
            if email in existing_emails:
                # Bestehender WebUser: nur fehlende Rollen ergaenzen, Passwort intakt lassen
                existing_user = session.execute(
                    sa_select(WebUser).where(WebUser.email == email)
                ).scalar_one()
                existing_roles = set(
                    session.execute(
                        sa_select(WebUserRoleLink.role).where(
                            WebUserRoleLink.web_user_id == existing_user.id
                        )
                    ).scalars().all()
                )
                missing_roles = entry["roles"] - existing_roles
                if not missing_roles:
                    unchanged += 1
                    continue
                for role in missing_roles:
                    session.add(WebUserRoleLink(web_user_id=existing_user.id, role=role))
                    roles_histogram[role.value] += 1
                print(
                    f"  ~ {email}  + ({', '.join(sorted(r.value for r in missing_roles))})",
                    flush=True,
                )
                updated += 1
                continue

            web_user = WebUser(
                email=email,
                person_id=entry["person_id"],
                hashed_password=hashed_pw,
                is_active=True,
            )
            session.add(web_user)
            session.flush()

            for role in entry["roles"]:
                session.add(WebUserRoleLink(web_user_id=web_user.id, role=role))
                roles_histogram[role.value] += 1

            print(
                f"  + {email}  ({', '.join(sorted(r.value for r in entry['roles']))})",
                flush=True,
            )
            created += 1

        session.commit()

        print()
        print(f"Angelegte WebUser: {created}")
        print(f"Bestehende WebUser mit ergaenzten Rollen: {updated}")
        print(f"Bestehende WebUser ohne Aenderung: {unchanged}")
        print()
        print("Rollen-Histogramm (neu vergebene):")
        for role_name, count in sorted(roles_histogram.items()):
            print(f"  {role_name}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())