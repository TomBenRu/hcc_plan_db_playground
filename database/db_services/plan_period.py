"""Service-Funktionen für PlanPeriod (Planungszeitraum).

Eine PlanPeriod definiert den Zeitraum (Start, Ende, Deadline), für den ein
Team geplant wird. Bei einer Datumsänderung (`update`) werden automatisch alle
AvailDays und Events außerhalb des neuen Zeitraums soft-gelöscht; bei einer
Vergrößerung werden zuvor soft-gelöschte AvailDays/Events innerhalb der neuen
Range reaktiviert und fehlende LPP/APP für hinzugekommene Team-Mitglieder
nachgezogen.
`delete_prep_deletes` entfernt endgültig alle als gelöscht markierten Perioden
eines Teams.

Ein closed-Lifecycle blockiert struktur-relevante Mutationen (start/end/
deadline/remainder/Soft-Delete). Notes auf PP-Ebene sowie alle Mutationen
des PP-Inhalts (AvailDays, Events, Appointments, Casts) bleiben unbeeinflusst.
"""
import datetime
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import plan_period_show_options, plan_period_actor_tab_options
from ._soft_delete import active_team_pp_criteria


class PlanPeriodClosedError(Exception):
    """Wird geworfen, wenn ein struktur-relevanter Schreibzugriff auf eine
    geschlossene PlanPeriod versucht wird."""


class PlanPeriodPermissionError(Exception):
    """Wird geworfen, wenn ein Re-Open ohne Admin-Rolle versucht wird."""


def _team_member_person_ids_in_range(session, team_id: UUID,
                                     start: datetime.date, end: datetime.date) -> set[UUID]:
    """ID-Vereinigung aller Personen, die dem Team in [start, end] mind. 1 Tag
    angehört haben. Filtert weiche-gelöschte Personen nach end-cutoff."""
    cutoff_end = datetime.datetime.combine(end, datetime.time.max)
    stmt = (
        select(models.Person.id)
        .join(models.TeamActorAssign, models.TeamActorAssign.person_id == models.Person.id)
        .where(
            models.TeamActorAssign.team_id == team_id,
            models.TeamActorAssign.start <= end,
            or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end > start),
            or_(models.Person.prep_delete.is_(None), models.Person.prep_delete > cutoff_end),
        )
    )
    return set(session.exec(stmt).all())


def _team_location_ids_in_range(session, team_id: UUID,
                                start: datetime.date, end: datetime.date) -> set[UUID]:
    """ID-Vereinigung aller Locations, die dem Team in [start, end] mind. 1 Tag
    zugeordnet waren."""
    cutoff_end = datetime.datetime.combine(end, datetime.time.max)
    stmt = (
        select(models.LocationOfWork.id)
        .join(models.TeamLocationAssign, models.TeamLocationAssign.location_of_work_id == models.LocationOfWork.id)
        .where(
            models.TeamLocationAssign.team_id == team_id,
            models.TeamLocationAssign.start <= end,
            or_(models.TeamLocationAssign.end.is_(None), models.TeamLocationAssign.end > start),
            or_(models.LocationOfWork.prep_delete.is_(None), models.LocationOfWork.prep_delete > cutoff_end),
        )
    )
    return set(session.exec(stmt).all())


def get(plan_period_id: UUID, minimal: bool = False, *,
        include_deleted: bool = False) -> schemas.PlanPeriodShow | schemas.PlanPeriod:
    """Lädt eine PlanPeriod.

    minimal=True gibt schemas.PlanPeriod (id, start, end, team) zurück ohne
    actor_plan_periods, location_plan_periods und cast_groups — für Aufrufer,
    die nur Datum und ID benötigen (~120ms statt ~490ms).

    `include_deleted=False` (Default) blendet sowohl soft-deleted PPs als auch
    PPs eines soft-deleted Teams aus — letzteres greift über das mitgegebene
    `with_loader_criteria(Team, ...)` als zusätzliches WHERE über den Team-Join.
    """
    with get_session() as session:
        if minimal:
            stmt = (select(models.PlanPeriod)
                    .where(models.PlanPeriod.id == plan_period_id)
                    .options(
                        joinedload(models.PlanPeriod.team).joinedload(models.Team.project),
                        joinedload(models.PlanPeriod.team).joinedload(models.Team.dispatcher),
                        joinedload(models.PlanPeriod.team).joinedload(models.Team.excel_export_settings),
                    ))
            if not include_deleted:
                stmt = stmt.options(*active_team_pp_criteria())
            pp = session.exec(stmt).unique().one()
            return schemas.PlanPeriod.model_validate(pp)
        stmt = (select(models.PlanPeriod)
                .where(models.PlanPeriod.id == plan_period_id)
                .options(*plan_period_show_options()))
        if not include_deleted:
            stmt = stmt.options(*active_team_pp_criteria())
        pp = session.exec(stmt).unique().one()
        return schemas.PlanPeriodShow.model_validate(pp)


def get_for_actor_tab(plan_period_id: UUID, *,
                      include_deleted: bool = False) -> schemas.PlanPeriodForActorTab:
    """Lädt PlanPeriod für FrmTabActorPlanPeriods — ohne location_plan_periods, cast_groups, project.

    Spart ~600ms gegenüber get() mit vollem PlanPeriodShow, da die schweren
    location_plan_periods- und cast_groups-Chains nicht geladen werden.
    """
    with get_session() as session:
        stmt = (select(models.PlanPeriod)
                .where(models.PlanPeriod.id == plan_period_id)
                .options(*plan_period_actor_tab_options()))
        if not include_deleted:
            stmt = stmt.options(*active_team_pp_criteria())
        pp = session.exec(stmt).unique().one()
        return schemas.PlanPeriodForActorTab.model_validate(pp)


def get_lpp_and_app_ids(plan_period_id: UUID) -> tuple[list[UUID], list[UUID]]:
    """Lädt ausschließlich die LocationPlanPeriod- und ActorPlanPeriod-ID-Listen.

    Ersetzt 2× PlanPeriod.get() (je ~700ms mit vollem Eager-Loading) durch
    2 einfache SELECT-Queries (~10ms gesamt). Verwendet kein model_validate.
    Für den Solver-Tree-Aufbau, der nur die IDs benötigt.

    Returns:
        (lpp_ids, app_ids)
    """
    with get_session() as session:
        lpp_ids = session.exec(
            select(models.LocationPlanPeriod.id)
            .where(models.LocationPlanPeriod.plan_period_id == plan_period_id)
        ).all()
        app_ids = session.exec(
            select(models.ActorPlanPeriod.id)
            .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)
        ).all()
    return list(lpp_ids), list(app_ids)


def exists_any_from__project(project_id: UUID, *, include_deleted: bool = False) -> bool:
    """Gibt True zurück, wenn das Projekt mindestens einen Planungszeitraum hat (kein model_validate)."""
    with get_session() as session:
        stmt = (select(models.PlanPeriod)
                .join(models.Team)
                .where(models.Team.project_id == project_id)
                .limit(1))
        if not include_deleted:
            stmt = stmt.where(
                models.PlanPeriod.prep_delete.is_(None),
                models.Team.prep_delete.is_(None),
            )
        return session.exec(stmt).first() is not None


def get_all_from__project(project_id: UUID, *,
                          include_deleted: bool = False) -> list[schemas.PlanPeriod]:
    """Gibt alle PlanPeriod-Basis-Objekte eines Projekts zurück.

    Verwendet bewusst das Basis-Schema (nicht PlanPeriodShow), da Aufrufer
    nur id, start, end, prep_delete und team benötigen — kein Deep-Loading
    von actor_plan_periods, location_plan_periods oder cast_groups.
    """
    with get_session() as session:
        stmt = (select(models.PlanPeriod)
                .join(models.Team)
                .where(models.Team.project_id == project_id)
                .options(
                    joinedload(models.PlanPeriod.team).joinedload(models.Team.project),
                    joinedload(models.PlanPeriod.team).joinedload(models.Team.dispatcher),
                    joinedload(models.PlanPeriod.team).joinedload(models.Team.excel_export_settings),
                ))
        if not include_deleted:
            stmt = stmt.options(*active_team_pp_criteria())
        pps = session.exec(stmt).unique().all()
        return [schemas.PlanPeriod.model_validate(p) for p in pps]


def get_all_from__team(team_id: UUID, *,
                       include_deleted: bool = False) -> list[schemas.PlanPeriodShow]:
    with get_session() as session:
        stmt = select(models.PlanPeriod).where(models.PlanPeriod.team_id == team_id)
        if not include_deleted:
            stmt = stmt.options(*active_team_pp_criteria())
        pps = session.exec(stmt).all()
        return [schemas.PlanPeriodShow.model_validate(p) for p in pps]


def get_all_from__team_minimal(team_id: UUID, *,
                               include_deleted: bool = False) -> list[schemas.PlanPeriodMinimal]:
    with get_session() as session:
        stmt = select(models.PlanPeriod).where(models.PlanPeriod.team_id == team_id)
        if not include_deleted:
            stmt = stmt.options(*active_team_pp_criteria())
        pps = session.exec(stmt).all()
        return [schemas.PlanPeriodMinimal.model_validate(p) for p in pps]


def get_latest_end_for_team(team_id: UUID, exclude_id: UUID | None = None) -> datetime.date | None:
    """Liefert max(end) aller non-deleted PlanPeriods eines Teams.

    Wird vom Web-UI für sinnvolle Default-Werte (`default_start = latest_end + 1`)
    und für `min`-Attribute der Date-Inputs genutzt. `exclude_id` lässt die zu
    editierende PP außen vor (PATCH-Form-Defaults)."""
    with get_session() as session:
        stmt = select(func.max(models.PlanPeriod.end)).where(
            models.PlanPeriod.team_id == team_id,
            models.PlanPeriod.prep_delete.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(models.PlanPeriod.id != exclude_id)
        return session.execute(stmt).scalar()


def find_overlapping_period(
    team_id: UUID,
    start: datetime.date,
    end: datetime.date,
    exclude_id: UUID | None = None,
) -> schemas.PlanPeriodMinimal | None:
    """Findet die erste non-deleted PlanPeriod des Teams, deren Range mit
    [start, end] überlappt. `exclude_id` schließt die zu editierende PP aus
    (für PATCH-Validierung). None heißt: keine Überlappung gefunden.

    Range-Overlap-Formel: existing.start <= new.end AND existing.end >= new.start.
    """
    with get_session() as session:
        stmt = select(models.PlanPeriod).where(
            models.PlanPeriod.team_id == team_id,
            models.PlanPeriod.prep_delete.is_(None),
            models.PlanPeriod.start <= end,
            models.PlanPeriod.end >= start,
        )
        if exclude_id is not None:
            stmt = stmt.where(models.PlanPeriod.id != exclude_id)
        hit = session.exec(stmt).first()
        return schemas.PlanPeriodMinimal.model_validate(hit) if hit else None


def create(plan_period: schemas.PlanPeriodCreate) -> schemas.PlanPeriodShow:
    """Legacy: Anlage einer leeren PlanPeriod ohne Kinder. Bleibt für
    bestehende API-Konsumenten (POST /plan-periods). Neue Aufrufer sollten
    `create_with_children` verwenden."""
    log_function_info()
    with get_session() as session:
        pp = models.PlanPeriod(start=plan_period.start, end=plan_period.end, deadline=plan_period.deadline,
                               notes=plan_period.notes, notes_for_employees=plan_period.notes_for_employees,
                               team=session.get(models.Team, plan_period.team.id))
        session.add(pp)
        session.flush()
        return schemas.PlanPeriodShow.model_validate(pp)


def create_with_children(plan_period: schemas.PlanPeriodCreate) -> schemas.PlanPeriodShow:
    """Atomar: PlanPeriod + LocationPlanPeriod+EventGroup-Master + ActorPlanPeriod+
    AvailDayGroup-Master in einer einzigen Session/Transaktion.

    Personen und Locations werden als Vereinigung über alle Tage in [start, end]
    aufgelöst — wer mind. 1 Tag im Team war, bekommt eine eigene APP/LPP.

    Wichtig: Relationen (`plan_period`, `person`, `location_of_work`) werden als
    Objekte gesetzt, nicht nur FK-IDs — der `before_flush`-Listener in
    `database/event_listeners.py` kopiert daraus die Default-TimeOfDay-Standards,
    Combination-Locations-Possibles, Skills usw. und braucht die Relation
    SOFORT verfügbar, bevor er die `if app.person:` / `if lpp.location_of_work:`
    Checks macht.
    """
    log_function_info()
    with get_session() as session:
        team = session.get(models.Team, plan_period.team.id)
        pp = models.PlanPeriod(
            start=plan_period.start, end=plan_period.end, deadline=plan_period.deadline,
            notes=plan_period.notes, notes_for_employees=plan_period.notes_for_employees,
            remainder=plan_period.remainder, team=team,
        )
        session.add(pp)
        session.flush()

        person_ids = _team_member_person_ids_in_range(
            session, team.id, plan_period.start, plan_period.end)
        location_ids = _team_location_ids_in_range(
            session, team.id, plan_period.start, plan_period.end)

        for person_id in person_ids:
            person = session.get(models.Person, person_id)
            app = models.ActorPlanPeriod(plan_period=pp, person=person)
            session.add(app)
            session.flush()
            adg = models.AvailDayGroup(actor_plan_period=app)
            session.add(adg)

        for location_id in location_ids:
            location = session.get(models.LocationOfWork, location_id)
            lpp = models.LocationPlanPeriod(plan_period=pp, location_of_work=location)
            session.add(lpp)
            session.flush()
            eg = models.EventGroup(location_plan_period=lpp)
            session.add(eg)

        session.flush()
        return schemas.PlanPeriodShow.model_validate(pp)


def update(plan_period: schemas.PlanPeriod) -> schemas.PlanPeriodShow:
    """Aktualisiert PlanPeriod. Bei `closed=True` werden struktur-relevante
    Änderungen (start/end/deadline/remainder) blockiert (PlanPeriodClosedError);
    Notes-Änderungen bleiben erlaubt.

    Bei Änderung von start/end:
      - AvailDays/Events außerhalb der neuen Range werden soft-deleted.
      - Soft-deleted AvailDays/Events innerhalb der neuen Range werden reaktiviert.
      - Bei Vergrößerung werden fehlende LPP/APP+Master-Group für Team-Mitglieder
        in den hinzugekommenen Tagen automatisch nachgezogen.
    """
    log_function_info()
    with get_session() as session:
        pp = session.get(models.PlanPeriod, plan_period.id)

        structure_changed = (
            pp.start != plan_period.start
            or pp.end != plan_period.end
            or pp.deadline != plan_period.deadline
            or pp.remainder != plan_period.remainder
        )
        if pp.closed and structure_changed:
            raise PlanPeriodClosedError(
                f"PlanPeriod {pp.id} is closed; structural changes (start/end/deadline/remainder) "
                f"are blocked. Reopen first."
            )

        old_start = pp.start
        old_end = pp.end

        pp.start = plan_period.start
        pp.end = plan_period.end
        pp.deadline = plan_period.deadline
        pp.notes = plan_period.notes
        pp.notes_for_employees = plan_period.notes_for_employees
        pp.remainder = plan_period.remainder

        # Soft-Delete out-of-range
        for app in pp.actor_plan_periods:
            for ad in app.avail_days:
                if not (plan_period.start <= ad.date <= plan_period.end) and not ad.prep_delete:
                    ad.prep_delete = _utcnow()
        for lpp in pp.location_plan_periods:
            for event in lpp.events:
                if not (plan_period.start <= event.date <= plan_period.end) and not event.prep_delete:
                    event.prep_delete = _utcnow()

        # Reaktivierung soft-deleted in-range (symmetrisches Verhalten beim Vergrößern)
        for app in pp.actor_plan_periods:
            for ad in app.avail_days:
                if (plan_period.start <= ad.date <= plan_period.end) and ad.prep_delete:
                    ad.prep_delete = None
        for lpp in pp.location_plan_periods:
            for event in lpp.events:
                if (plan_period.start <= event.date <= plan_period.end) and event.prep_delete:
                    event.prep_delete = None

        # Auto-Nachziehen bei Vergrößerung (start früher oder end später)
        # Relationen als Objekte setzen, damit before_flush-Listener die Defaults
        # (TimeOfDay-Standards, CombLoc, Prefs) von Person/Location übernehmen.
        if plan_period.start < old_start or plan_period.end > old_end:
            person_ids = _team_member_person_ids_in_range(
                session, pp.team_id, plan_period.start, plan_period.end)
            existing_app_person_ids = {app.person_id for app in pp.actor_plan_periods}
            for person_id in person_ids - existing_app_person_ids:
                person = session.get(models.Person, person_id)
                app = models.ActorPlanPeriod(plan_period=pp, person=person)
                session.add(app)
                session.flush()
                session.add(models.AvailDayGroup(actor_plan_period=app))

            location_ids = _team_location_ids_in_range(
                session, pp.team_id, plan_period.start, plan_period.end)
            existing_lpp_location_ids = {lpp.location_of_work_id for lpp in pp.location_plan_periods}
            for location_id in location_ids - existing_lpp_location_ids:
                location = session.get(models.LocationOfWork, location_id)
                lpp = models.LocationPlanPeriod(plan_period=pp, location_of_work=location)
                session.add(lpp)
                session.flush()
                session.add(models.EventGroup(location_plan_period=lpp))

        session.flush()
        return schemas.PlanPeriodShow.model_validate(pp)


def update_notes(plan_period_id: UUID, notes: str) -> schemas.PlanPeriodShow:
    log_function_info()
    with get_session() as session:
        pp = session.get(models.PlanPeriod, plan_period_id)
        pp.notes = notes
        session.flush()
        return schemas.PlanPeriodShow.model_validate(pp)


def delete(plan_period_id: UUID) -> schemas.PlanPeriodMinimal:
    """Soft-Delete der PlanPeriod. Bei `closed=True` blockiert (PlanPeriodClosedError);
    Admin muss zuerst re-openen.

    Gibt PlanPeriodMinimal (id, start, end, closed, prep_delete, team_id) zurück
    — kein PlanPeriodShow, weil das bei großen Perioden hunderte Lazy-Queries
    triggert und die Mutation auf 30 s+ aufbläht.
    """
    log_function_info()
    with get_session() as session:
        pp = session.get(models.PlanPeriod, plan_period_id)
        if pp.closed:
            raise PlanPeriodClosedError(
                f"PlanPeriod {pp.id} is closed; soft-delete blocked. Reopen first."
            )
        pp.prep_delete = _utcnow()
        session.flush()
        return schemas.PlanPeriodMinimal.model_validate(pp)


def set_closed(plan_period_id: UUID, closed: bool, *,
               is_admin: bool = False) -> schemas.PlanPeriodMinimal:
    """Setzt PlanPeriod.closed. closed=True ist beliebigen Aufrufern erlaubt
    (Router prüft Disponenten-/Admin-Rolle vorher). closed=False (Re-Open)
    erfordert is_admin=True, sonst PlanPeriodPermissionError.

    Idempotent: ein erneuter Call mit gleichem Wert macht keinen Schaden.

    Gibt PlanPeriodMinimal zurück (siehe `delete` zur Bloat-Vermeidung).
    """
    log_function_info()
    if not closed and not is_admin:
        raise PlanPeriodPermissionError(
            f"Re-Open of PlanPeriod {plan_period_id} requires admin role."
        )
    with get_session() as session:
        pp = session.get(models.PlanPeriod, plan_period_id)
        pp.closed = closed
        session.flush()
        return schemas.PlanPeriodMinimal.model_validate(pp)


def undelete(plan_period_id: UUID) -> schemas.PlanPeriodMinimal:
    """Hebt Soft-Delete auf. Gibt PlanPeriodMinimal zurück (Bloat-Vermeidung)."""
    log_function_info()
    with get_session() as session:
        pp = session.get(models.PlanPeriod, plan_period_id)
        pp.prep_delete = None
        session.flush()
        return schemas.PlanPeriodMinimal.model_validate(pp)


def delete_prep_deletes(team_id: UUID):
    with get_session() as session:
        pps = session.exec(select(models.PlanPeriod).where(
            models.PlanPeriod.team_id == team_id, models.PlanPeriod.prep_delete.isnot(None))).all()
        for pp in pps:
            session.delete(pp)


def find_takeover_candidates(new_pp_id: UUID) -> schemas.TakeoverPreview:
    """Sucht soft-deleted AvailDays und Events anderer PPs des gleichen Teams,
    deren Datum in der Range der neuen PP liegt — Vorschau für den Confirm-Dialog
    im Web-UI. Zählt Events mit Appointments separat (Cascade-Warnung).
    """
    log_function_info()
    with get_session() as session:
        new_pp = session.get(models.PlanPeriod, new_pp_id)
        if new_pp is None:
            return schemas.TakeoverPreview(
                new_plan_period_id=new_pp_id, candidates=[],
                total_avail_days=0, total_events=0,
                events_with_appointments_count=0,
            )
        team_id = new_pp.team_id
        start, end = new_pp.start, new_pp.end

        other_pps = session.exec(
            select(models.PlanPeriod).where(
                models.PlanPeriod.team_id == team_id,
                models.PlanPeriod.id != new_pp_id,
                models.PlanPeriod.prep_delete.is_(None),
            )
        ).all()

        candidates: list[schemas.TakeoverCandidate] = []
        total_ad = 0
        total_ev = 0
        with_appts = 0

        for src in other_pps:
            src_app_ids = [app.id for app in src.actor_plan_periods]
            ads = []
            if src_app_ids:
                ads = session.exec(
                    select(models.AvailDay).where(
                        models.AvailDay.actor_plan_period_id.in_(src_app_ids),
                        models.AvailDay.prep_delete.isnot(None),
                        models.AvailDay.date >= start,
                        models.AvailDay.date <= end,
                    )
                ).all()

            src_lpp_ids = [lpp.id for lpp in src.location_plan_periods]
            evs = []
            if src_lpp_ids:
                evs = session.exec(
                    select(models.Event).where(
                        models.Event.location_plan_period_id.in_(src_lpp_ids),
                        models.Event.prep_delete.isnot(None),
                        models.Event.date >= start,
                        models.Event.date <= end,
                    )
                ).all()

            ev_appt_count = sum(1 for e in evs if e.appointments)

            if ads or evs:
                candidates.append(schemas.TakeoverCandidate(
                    source_plan_period_id=src.id,
                    avail_day_ids=[ad.id for ad in ads],
                    event_ids=[e.id for e in evs],
                    events_with_appointments_count=ev_appt_count,
                ))
                total_ad += len(ads)
                total_ev += len(evs)
                with_appts += ev_appt_count

        return schemas.TakeoverPreview(
            new_plan_period_id=new_pp_id,
            candidates=candidates,
            total_avail_days=total_ad,
            total_events=total_ev,
            events_with_appointments_count=with_appts,
        )


def execute_takeover(new_pp_id: UUID) -> schemas.TakeoverReport:
    """Kopiert soft-deleted AvailDays anderer PPs des gleichen Teams in die
    Tree-Struktur der neuen PlanPeriod und löscht die Originale hart.

    Tree-Pflege:
      - Pro kopierter AvailDay wird eine neue Tages-AvailDayGroup als Kind
        des APP-Master in der neuen PP angelegt.
      - Master-/strukturelle ADGs der Source-PP werden nie angefasst; nur
        Tages-Leaf-ADGs werden mit-gelöscht, sofern sie nach dem Hard-Delete
        der zugehörigen AvailDay keine weiteren aktiven Kinder/AvailDays haben.

    Limitation Phase 1: Events werden derzeit NICHT kopiert. Sie bleiben
    soft-deleted in ihrer Source-PP. Der Report meldet `copied_events=0`.
    Event-Take-Over ist als eigene Iteration vorgesehen (CastGroup-Mit-Anlage
    erfordert eigene Logik).

    Felder, die für AvailDays kopiert werden: date, time_of_day_id. M2M-Relations
    (skills, comb_loc_possibles, prefs) werden in dieser Phase NICHT mitkopiert
    — der Disponent muss bei Bedarf nachpflegen.
    """
    log_function_info()
    with get_session() as session:
        new_pp = session.get(models.PlanPeriod, new_pp_id)
        if new_pp is None:
            return schemas.TakeoverReport(
                new_plan_period_id=new_pp_id,
                copied_avail_days=0, copied_events=0,
                hard_deleted_avail_days=0, hard_deleted_avail_day_groups=0,
                hard_deleted_events=0, hard_deleted_event_groups=0,
                events_with_dropped_appointments=0,
            )
        team_id = new_pp.team_id
        start, end = new_pp.start, new_pp.end

        # Map: person_id → target APP in new_pp
        app_by_person: dict[UUID, models.ActorPlanPeriod] = {
            app.person_id: app for app in new_pp.actor_plan_periods
        }

        copied_avail_days = 0
        hard_deleted_avail_days = 0
        hard_deleted_avail_day_groups = 0

        other_pps = session.exec(
            select(models.PlanPeriod).where(
                models.PlanPeriod.team_id == team_id,
                models.PlanPeriod.id != new_pp_id,
                models.PlanPeriod.prep_delete.is_(None),
            )
        ).all()

        for src_pp in other_pps:
            for src_app in src_pp.actor_plan_periods:
                src_ads = [ad for ad in src_app.avail_days
                           if ad.prep_delete and start <= ad.date <= end]
                if not src_ads:
                    continue
                target_app = app_by_person.get(src_app.person_id)
                if target_app is None:
                    # Forever-Orphan: Person nicht mehr in neuer PP. Ignorieren.
                    continue
                # Master-ADG der Target-APP finden
                target_master_adg = session.exec(
                    select(models.AvailDayGroup).where(
                        models.AvailDayGroup.actor_plan_period_id == target_app.id
                    )
                ).first()
                if target_master_adg is None:
                    continue

                # Kopie pro AvailDay — Relationen als Objekte, damit der
                # before_flush-Listener `_on_insert_avail_day` die Defaults
                # (CombLoc, TimeOfDays, Prefs, Skills) von der APP übernimmt.
                for src_ad in src_ads:
                    new_adg = models.AvailDayGroup(avail_day_group=target_master_adg)
                    session.add(new_adg)
                    session.flush()
                    new_ad = models.AvailDay(
                        date=src_ad.date,
                        actor_plan_period=target_app,
                        avail_day_group=new_adg,
                        time_of_day_id=src_ad.time_of_day_id,
                    )
                    session.add(new_ad)
                    copied_avail_days += 1

                session.flush()

                # Hard-Delete der Originale + ggf. Tages-Leaf-ADG
                for src_ad in src_ads:
                    src_adg_id = src_ad.avail_day_group_id
                    session.delete(src_ad)
                    hard_deleted_avail_days += 1
                    if src_adg_id is None:
                        continue
                    src_adg = session.get(models.AvailDayGroup, src_adg_id)
                    # Nur Tages-Leaf-ADGs löschen (haben einen Eltern-FK,
                    # sind also nicht Master). Master-ADGs nie anfassen.
                    if src_adg is None or src_adg.avail_day_group_id is None:
                        continue
                    # Prüfen, ob keine weiteren Kinder oder AvailDays übrig
                    remaining_children = session.exec(
                        select(models.AvailDayGroup.id).where(
                            models.AvailDayGroup.avail_day_group_id == src_adg.id
                        ).limit(1)
                    ).first()
                    remaining_ads = session.exec(
                        select(models.AvailDay.id).where(
                            models.AvailDay.avail_day_group_id == src_adg.id
                        ).limit(1)
                    ).first()
                    if not remaining_children and not remaining_ads:
                        session.delete(src_adg)
                        hard_deleted_avail_day_groups += 1

                session.flush()

        return schemas.TakeoverReport(
            new_plan_period_id=new_pp_id,
            copied_avail_days=copied_avail_days,
            copied_events=0,  # Limitation: Event-Take-Over folgt in eigener Iteration
            hard_deleted_avail_days=hard_deleted_avail_days,
            hard_deleted_avail_day_groups=hard_deleted_avail_day_groups,
            hard_deleted_events=0,
            hard_deleted_event_groups=0,
            events_with_dropped_appointments=0,
        )