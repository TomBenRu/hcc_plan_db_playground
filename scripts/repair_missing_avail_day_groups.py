"""Repariert fehlende Master-AvailDayGroups fuer ActorPlanPeriods.

Hintergrund: Vor dem Listener-Fix vom 2026-05-15 hat
`web_api/admin/teams/mutations.py::create_actor_plan_periods` beim
Auto-Anlegen von APPs keine Master-`AvailDayGroup` erzeugt. Dadurch schlug
das Eintragen einer Verfuegbarkeit fuer diese APPs mit HTTP 500 fehl
("Root-AvailDayGroup fehlt").

Dieses Script findet alle APPs ohne Master-Group und legt eine an.

Aufruf:
    # Nur listen (Default):
    DATABASE_URL="postgresql://..." uv run python -u scripts/repair_missing_avail_day_groups.py
    # Tatsaechlich schreiben:
    DATABASE_URL="postgresql://..." uv run python -u scripts/repair_missing_avail_day_groups.py --apply
"""

import os
import sys

# Projekt-Root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select as sa_select
from sqlmodel import Session, create_engine

from database.event_listeners import register_listeners
from database.models import (
    ActorPlanPeriod,
    AvailDayGroup,
    Person,
    PlanPeriod,
    Team,
)


def _find_apps_without_master(session: Session) -> list[ActorPlanPeriod]:
    """Liefert alle ActorPlanPeriods, die KEINE Master-AvailDayGroup besitzen.

    Master = AvailDayGroup mit actor_plan_period_id == app.id (parent_avail_day_group_id IS NULL).
    Wir filtern via NOT EXISTS, damit das Script auch auf SQLite/PG identisch laeuft.
    """
    master_exists = (
        sa_select(AvailDayGroup.id)
        .where(AvailDayGroup.actor_plan_period_id == ActorPlanPeriod.id)
        .where(AvailDayGroup.avail_day_group_id.is_(None))
        .exists()
    )
    stmt = sa_select(ActorPlanPeriod).where(~master_exists)
    return list(session.execute(stmt).scalars().all())


def _format_app(app: ActorPlanPeriod, person: Person | None, pp: PlanPeriod | None, team: Team | None) -> str:
    person_label = "?"
    if person is not None:
        person_label = f"{person.f_name} {person.l_name}".strip() or str(person.id)
    if pp is not None and team is not None:
        return f"  - APP {app.id}  Person={person_label}  Team={team.name}  PP={pp.start}..{pp.end}"
    return f"  - APP {app.id}  Person={person_label}"


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Fehler: DATABASE_URL nicht gesetzt.", file=sys.stderr)
        return 1

    apply_changes = "--apply" in sys.argv[1:]

    # PFLICHT: DATABASE_URL anzeigen — User-Sign-Off vor jedem destruktiven Lauf
    print("=" * 72)
    print(f"DATABASE_URL = {db_url}")
    print(f"Mode         = {'APPLY (schreibt)' if apply_changes else 'DRY-RUN (zeigt nur)'}")
    print("=" * 72)
    if apply_changes:
        ans = input("Mit dem Schreiben gegen die obige Datenbank fortfahren? [yes/NO]: ").strip().lower()
        if ans != "yes":
            print("Abgebrochen.")
            return 1

    # Wichtig: Listener registrieren, damit auch andere Inserts (sollten in diesem
    # Script keine vorkommen) wie im Server-Run laufen. Schaedlich ist es nicht;
    # wir fuegen nur AvailDayGroup-Rows ein, und AvailDayGroup hat keinen eigenen
    # Insert-Hook, der hier irgendwas triggern wuerde.
    register_listeners()

    engine = create_engine(db_url)
    with Session(engine) as session:
        broken = _find_apps_without_master(session)
        print(f"ActorPlanPeriods ohne Master-AvailDayGroup: {len(broken)}")

        if not broken:
            print("Nichts zu reparieren.")
            return 0

        # Detail-Liste (Person/Team/Range fuer manuelle Kontrolle)
        for app in broken:
            person = session.get(Person, app.person_id) if app.person_id else None
            pp = session.get(PlanPeriod, app.plan_period_id) if app.plan_period_id else None
            team = session.get(Team, pp.team_id) if pp and pp.team_id else None
            print(_format_app(app, person, pp, team))

        if not apply_changes:
            print()
            print("Dry-Run: keine Aenderung geschrieben.")
            print("Mit --apply ausfuehren, um die fehlenden Master-Groups anzulegen.")
            return 0

        # Apply: pro APP genau eine Master-AvailDayGroup
        for app in broken:
            session.add(AvailDayGroup(actor_plan_period=app))
        session.commit()

        # Verifizieren
        still_broken = _find_apps_without_master(session)
        print()
        print(f"Repariert: {len(broken) - len(still_broken)}")
        if still_broken:
            print(f"WARNUNG: Noch {len(still_broken)} APPs ohne Master-Group.", file=sys.stderr)
            return 2
        print("Alle Master-Groups vorhanden.")
        return 0


if __name__ == "__main__":
    sys.exit(main())