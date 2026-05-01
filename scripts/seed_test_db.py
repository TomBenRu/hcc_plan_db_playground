"""scripts/seed_test_db.py — Minimal-Seed fuer eine leere Test-DB.

Erzeugt:
  - 1 Project ("Test")
  - 4 Personen (Admin/Dispatcher + 3 Mitarbeiter), alle Email + TeamActorAssign
  - 1 Team ("Hauptteam") mit der Admin-Person als Dispatcher
  - 1 WebUser (admin@example.com / test123) mit allen drei Rollen:
      admin + dispatcher + employee

Voraussetzung: DATABASE_URL zeigt auf eine DB mit ausgefuehrten Alembic-
Migrationen (alembic upgrade head). Idempotent: skipped, wenn der WebUser
admin@example.com bereits existiert.

Aufruf (aus Repo-Root):
    uv run --package hcc-plan-web-api python scripts/seed_test_db.py
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlmodel import Session, select

from database.enums import Gender, Role
from database.models import Person, Project, Team, TeamActorAssign
from web_api.auth.service import hash_password
from web_api.config import get_settings
from web_api.models.web_models import WebUser, WebUserRole, WebUserRoleLink


ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "test123"


def main() -> int:
    engine = create_engine(get_settings().DATABASE_URL)

    with Session(engine) as session:
        existing = session.exec(
            select(WebUser).where(WebUser.email == ADMIN_EMAIL)
        ).first()
        if existing is not None:
            print(f"WebUser {ADMIN_EMAIL} existiert bereits — skip seed.")
            return 0

        # 1) Project — ExcelExportSettings wird vom Listener autoerzeugt.
        project = Project(name="Test", active=True)
        session.add(project)
        session.flush()

        # 2) Personen. password ist Pflichtfeld (Desktop-Legacy) — Dummy reicht,
        #    weil der Web-Login ueber WebUser.hashed_password laeuft.
        # gender muss explizit gesetzt sein: Pydantic-Schema PersonCreate hat
        # `gender: Gender` ohne Optional, leerer DB-Wert wuerde model_validate
        # zur Render-Zeit scheitern lassen.
        # Email-TLD `.com` (example.com) statt `.local`, weil der EmailStr-
        # Validator (email-validator) `.local` als reserviert ablehnt.
        person_data = [
            ("Admin",  "Tester",  ADMIN_EMAIL,           "admin",  Role.DISPATCHER, Gender.divers),
            ("Alice",  "Mueller", "alice@example.com",   "alice",  Role.EMPLOYEE,   Gender.female),
            ("Bob",    "Schmidt", "bob@example.com",     "bob",    Role.EMPLOYEE,   Gender.male),
            ("Carol",  "Weber",   "carol@example.com",   "carol",  Role.EMPLOYEE,   Gender.female),
        ]
        persons: list[Person] = []
        for f_name, l_name, email, username, role, gender in person_data:
            p = Person(
                f_name=f_name, l_name=l_name, email=email, gender=gender,
                username=username, password="seed-unused",
                project=project, role=role,
            )
            session.add(p)
            persons.append(p)
        session.flush()

        admin_person = persons[0]

        # 3) Team — excel_export_settings wird vom Listener vom Project geerbt.
        team = Team(name="Hauptteam", project=project, dispatcher=admin_person)
        session.add(team)
        session.flush()

        # 4) TeamActorAssign fuer alle 4 Personen, ab vor 30 Tagen, offenes Ende.
        start = datetime.date.today() - datetime.timedelta(days=30)
        for p in persons:
            session.add(TeamActorAssign(person=p, team=team, start=start, end=None))

        # 5) WebUser fuer admin_person mit allen drei Rollen.
        admin_user = WebUser(
            email=ADMIN_EMAIL,
            person_id=admin_person.id,
            hashed_password=hash_password(ADMIN_PASSWORD),
            is_active=True,
        )
        session.add(admin_user)
        session.flush()
        for role in (WebUserRole.admin, WebUserRole.dispatcher, WebUserRole.employee):
            session.add(WebUserRoleLink(web_user_id=admin_user.id, role=role))

        session.commit()

        print("Seed abgeschlossen.")
        print(f"  Project:           {project.name} ({project.id})")
        print(f"  Team:              {team.name} ({team.id})")
        print(f"  Personen:          {len(persons)}")
        print(f"  TeamActorAssigns:  {len(persons)} (alle ab {start})")
        print(f"  WebUser-Login:     {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print( "  Rollen:            admin + dispatcher + employee")

    return 0


if __name__ == "__main__":
    sys.exit(main())
