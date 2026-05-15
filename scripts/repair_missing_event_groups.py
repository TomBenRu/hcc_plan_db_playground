"""Repariert fehlende Master-EventGroups fuer LocationPlanPeriods.

Hintergrund: Vor dem Listener-Fix vom 2026-05-15 hat
`web_api/admin/teams/mutations.py::create_location_plan_periods` beim
Anlegen von LPPs (LPP-Anlage-Dialog, commit 1ffc5bb) keine Master-
`EventGroup` erzeugt. Dadurch schlug der Dispatcher-Pfad „Last-Minute-
Termin anlegen" mit HTTP 500 fehl ("Master-EventGroup fehlt für diese
Location-Plan-Period.", siehe web_api/plan_adjustment/service.py:687-697).

Spiegel zu scripts/repair_missing_avail_day_groups.py.

Aufruf:
    # Nur listen (Default):
    DATABASE_URL="postgresql://..." uv run python -u scripts/repair_missing_event_groups.py
    # Tatsaechlich schreiben:
    DATABASE_URL="postgresql://..." uv run python -u scripts/repair_missing_event_groups.py --apply
"""

import os
import sys

# Projekt-Root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select as sa_select
from sqlmodel import Session, create_engine

from database.event_listeners import register_listeners
from database.models import (
    EventGroup,
    LocationOfWork,
    LocationPlanPeriod,
    PlanPeriod,
    Team,
)


def _find_lpps_without_master(session: Session) -> list[LocationPlanPeriod]:
    """Liefert alle LocationPlanPeriods, die KEINE Master-EventGroup besitzen.

    Master = EventGroup mit location_plan_period_id == lpp.id (parent IS NULL).
    Wir filtern via NOT EXISTS, damit das Script auf SQLite/PG identisch laeuft.
    """
    master_exists = (
        sa_select(EventGroup.id)
        .where(EventGroup.location_plan_period_id == LocationPlanPeriod.id)
        .where(EventGroup.event_group_id.is_(None))
        .exists()
    )
    stmt = sa_select(LocationPlanPeriod).where(~master_exists)
    return list(session.execute(stmt).scalars().all())


def _format_lpp(
    lpp: LocationPlanPeriod,
    location: LocationOfWork | None,
    pp: PlanPeriod | None,
    team: Team | None,
) -> str:
    location_label = location.name if location else "?"
    if pp is not None and team is not None:
        return f"  - LPP {lpp.id}  Location={location_label}  Team={team.name}  PP={pp.start}..{pp.end}"
    return f"  - LPP {lpp.id}  Location={location_label}"


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

    # Listener registrieren — schadet hier nicht; EventGroup hat zwar einen
    # eigenen Insert-Hook (Validation), unsere Inserts erfuellen die
    # `has_lpp XOR has_parent`-Bedingung aber sicher.
    register_listeners()

    engine = create_engine(db_url)
    with Session(engine) as session:
        broken = _find_lpps_without_master(session)
        print(f"LocationPlanPeriods ohne Master-EventGroup: {len(broken)}")

        if not broken:
            print("Nichts zu reparieren.")
            return 0

        for lpp in broken:
            location = session.get(LocationOfWork, lpp.location_of_work_id) if lpp.location_of_work_id else None
            pp = session.get(PlanPeriod, lpp.plan_period_id) if lpp.plan_period_id else None
            team = session.get(Team, pp.team_id) if pp and pp.team_id else None
            print(_format_lpp(lpp, location, pp, team))

        if not apply_changes:
            print()
            print("Dry-Run: keine Aenderung geschrieben.")
            print("Mit --apply ausfuehren, um die fehlenden Master-Groups anzulegen.")
            return 0

        # Apply: pro LPP genau eine Master-EventGroup
        for lpp in broken:
            session.add(EventGroup(location_plan_period=lpp))
        session.commit()

        # Verifizieren
        still_broken = _find_lpps_without_master(session)
        print()
        print(f"Repariert: {len(broken) - len(still_broken)}")
        if still_broken:
            print(f"WARNUNG: Noch {len(still_broken)} LPPs ohne Master-Group.", file=sys.stderr)
            return 2
        print("Alle Master-Groups vorhanden.")
        return 0


if __name__ == "__main__":
    sys.exit(main())