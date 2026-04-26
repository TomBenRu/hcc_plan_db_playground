"""Service-Funktionen für ActorPlanPeriod (Akteur-Planperiode).

Verknüpft eine Person mit einer PlanPeriod und speichert deren individuelle
Einstellungen wie gewünschte Einsätze, Tageszeiten, Standortpräferenzen und
Standortkombinationen. Enthält auch eine speziell optimierte Abfrage für den
Solver (`get_all_for_solver`).
"""
import datetime
from uuid import UUID

from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import actor_plan_period_show_options, actor_plan_period_mask_options
from .combination_locations_possible import is_comb_loc_orphaned


def get_multiple(actor_plan_period_ids: list[UUID]) -> list[schemas.ActorPlanPeriodShow]:
    """Lädt mehrere ActorPlanPeriodShow-Objekte in einer Batch-Abfrage.

    Effizient für das Vorabladen mehrerer aktiver ActorPlanPeriods — spart
    N einzelne get()-Roundtrips durch einen einzigen IN-Query.
    """
    if not actor_plan_period_ids:
        return []
    with get_session() as session:
        stmt = (select(models.ActorPlanPeriod)
                .where(models.ActorPlanPeriod.id.in_(actor_plan_period_ids))
                .options(*actor_plan_period_show_options()))
        apps = session.exec(stmt).unique().all()
        return [schemas.ActorPlanPeriodShow.model_validate(a) for a in apps]


def get(actor_plan_period_id: UUID) -> schemas.ActorPlanPeriodShow:
    with get_session() as session:
        stmt = (select(models.ActorPlanPeriod)
                .where(models.ActorPlanPeriod.id == actor_plan_period_id)
                .options(*actor_plan_period_show_options()))
        app = session.exec(stmt).unique().one()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def get_multiple_for_mask(actor_plan_period_ids: list[UUID]) -> list[schemas.ActorPlanPeriodForMask]:
    """Lädt mehrere ActorPlanPeriodForMask-Objekte in einer Batch-Abfrage.

    Für Hintergrund-Vorladen aller Akteure einer Planperiode — spart N einzelne
    get_for_mask()-Roundtrips durch einen einzigen IN-Query.
    """
    if not actor_plan_period_ids:
        return []
    with get_session() as session:
        stmt = (select(models.ActorPlanPeriod)
                .where(models.ActorPlanPeriod.id.in_(actor_plan_period_ids))
                .options(*actor_plan_period_mask_options()))
        apps = session.exec(stmt).unique().all()
        return [schemas.ActorPlanPeriodForMask.model_validate(a) for a in apps]


def get_for_mask(actor_plan_period_id: UUID) -> schemas.ActorPlanPeriodForMask:
    """Lädt ActorPlanPeriodForMask für die Masken-Anzeige.

    Verwendet actor_plan_period_mask_options() statt actor_plan_period_show_options().
    Reduziert SQL-Queries von ~20 auf ~10 pro Aktor-Laden.
    """
    with get_session() as session:
        stmt = (select(models.ActorPlanPeriod)
                .where(models.ActorPlanPeriod.id == actor_plan_period_id)
                .options(*actor_plan_period_mask_options()))
        app = session.exec(stmt).unique().one()
        return schemas.ActorPlanPeriodForMask.model_validate(app)


def get_all_from__plan_period(plan_period_id: UUID, maximal: bool = False) -> list[schemas.ActorPlanPeriod | schemas.ActorPlanPeriodShow]:
    with get_session() as session:
        if maximal:
            stmt = (select(models.ActorPlanPeriod)
                    .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)
                    .options(*actor_plan_period_show_options()))
            apps = session.exec(stmt).unique().all()
            return [schemas.ActorPlanPeriodShow.model_validate(a) for a in apps]
        # Alle Pflichtfelder des schemas.ActorPlanPeriod eager laden:
        #   ActorPlanPeriodCreate.person  → joinedload(person)
        #   ActorPlanPeriodCreate.plan_period → PlanPeriodCreate.team → TeamCreate.project/dispatcher/excel
        # Ohne diese Kette entstehen 5 lazy-load Queries pro Session (plan_period→team→project usw.)
        plan_period_chain = (
            joinedload(models.ActorPlanPeriod.plan_period)
            .joinedload(models.PlanPeriod.team)
        )
        stmt = (select(models.ActorPlanPeriod)
                .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)
                .options(
                    joinedload(models.ActorPlanPeriod.person),
                    plan_period_chain.joinedload(models.Team.project),
                    plan_period_chain.joinedload(models.Team.dispatcher),
                    plan_period_chain.joinedload(models.Team.excel_export_settings),
                ))
        apps = session.exec(stmt).unique().all()
        return [schemas.ActorPlanPeriod.model_validate(a) for a in apps]


def get_all_for_solver(plan_period_id: UUID) -> dict[UUID, schemas.ActorPlanPeriodSolver]:
    from sqlalchemy.orm import joinedload
    with get_session() as session:
        apps = list(session.exec(
            select(models.ActorPlanPeriod)
            .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)
            .options(
                joinedload(models.ActorPlanPeriod.person),
                joinedload(models.ActorPlanPeriod.plan_period),
            )
        ).unique().all())
        if not apps:
            return {}
        app_ids = [a.id for a in apps]
        avail_days = session.exec(select(models.AvailDay).where(
            models.AvailDay.actor_plan_period_id.in_(app_ids),
            models.AvailDay.prep_delete.is_(None))).all()
        adg_by_app: dict[UUID, list[UUID]] = {aid: [] for aid in app_ids}
        for ad in avail_days:
            adg_by_app[ad.actor_plan_period_id].append(ad.avail_day_group_id)
        return {
            a.id: schemas.ActorPlanPeriodSolver(
                id=a.id, requested_assignments=a.requested_assignments,
                required_assignments=a.required_assignments,
                person=schemas.PersonSolver(id=a.person.id, f_name=a.person.f_name, l_name=a.person.l_name),
                plan_period=schemas.PlanPeriodSolver(id=a.plan_period.id, start=a.plan_period.start, end=a.plan_period.end),
                avail_day_group_ids=adg_by_app[a.id])
            for a in apps}


def create(plan_period_id: UUID, person_id: UUID,
           actor_plan_period_id: UUID = None) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        kwargs = dict(plan_period=session.get(models.PlanPeriod, plan_period_id),
                      person=session.get(models.Person, person_id))
        if actor_plan_period_id:
            kwargs['id'] = actor_plan_period_id
        app = models.ActorPlanPeriod(**kwargs)
        session.add(app)
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def delete(actor_plan_period_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.ActorPlanPeriod, actor_plan_period_id))


def update(actor_plan_period: schemas.ActorPlanPeriodShow) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        tod_ids = [t.id for t in actor_plan_period.time_of_days]
        tods_by_id = {
            t.id: t for t in session.exec(
                select(models.TimeOfDay).where(models.TimeOfDay.id.in_(tod_ids))
            ).all()
        } if tod_ids else {}
        app = session.get(models.ActorPlanPeriod, actor_plan_period.id)
        app.time_of_days.clear()
        app.time_of_days.extend(tods_by_id[t.id] for t in actor_plan_period.time_of_days)
        for k, v in actor_plan_period.model_dump(include={'notes', 'requested_assignments'}).items():
            setattr(app, k, v)
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def update_notes(actor_plan_period: schemas.ActorPlanPeriodUpdateNotes) -> None:
    """Aktualisiert nur das notes-Feld. Kein Rueckgabewert — der Client
    weiss, was er geschrieben hat, und aktualisiert seinen Cache selbst.

    Vermeidet bei remote DB mehrere lazy-loaded Queries (person, project,
    address, plan_period, team), die bei model_validate ausgeloest wuerden.
    """
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period.id)
        app.notes = actor_plan_period.notes
        session.flush()


def update_requested_assignments(actor_plan_period_id: UUID,
                                 requested_assignments: int, required_assignments: bool) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.requested_assignments = requested_assignments
        app.required_assignments = required_assignments
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def put_in_time_of_day(actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.time_of_days.append(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def remove_in_time_of_day(actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        tod = session.get(models.TimeOfDay, time_of_day_id)
        if tod in app.time_of_days:
            app.time_of_days.remove(tod)
            session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def remove_time_of_day_standard(actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        tod = session.get(models.TimeOfDay, time_of_day_id)
        if tod in app.time_of_day_standards:
            app.time_of_day_standards.remove(tod)
            session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def new_time_of_day_standard(actor_plan_period_id: UUID, time_of_day_id: UUID) -> tuple[schemas.ActorPlanPeriodShow, UUID | None]:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        tod = session.get(models.TimeOfDay, time_of_day_id)
        old_id = None
        for t in list(app.time_of_day_standards):
            if t.time_of_day_enum.id == tod.time_of_day_enum.id:
                app.time_of_day_standards.remove(t)
                old_id = t.id
                break
        app.time_of_day_standards.append(tod)
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app), old_id


def put_in_comb_loc_possible(actor_plan_period_id: UUID, comb_loc_possible_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.combination_locations_possibles.append(session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def remove_comb_loc_possible(actor_plan_period_id: UUID, comb_loc_possible_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.combination_locations_possibles.remove(session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def put_in_location_pref(actor_plan_period_id: UUID, actor_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.actor_location_prefs_defaults.append(session.get(models.ActorLocationPref, actor_loc_pref_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def remove_location_pref(actor_plan_period_id: UUID, actor_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.actor_location_prefs_defaults.remove(session.get(models.ActorLocationPref, actor_loc_pref_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def update_location_prefs_bulk(
        actor_plan_period_id: UUID,
        location_id_to_score: dict[UUID, float],
) -> dict[str, list[UUID]]:
    """Setzt die Location-Präferenzen einer ActorPlanPeriod in einer einzigen Session.

    Wiederverwendungslogik: Existiert bereits eine nicht-gelöschte ActorLocationPref
    der Person mit derselben Location UND demselben Score, wird sie übernommen statt
    neu angelegt. Verwaiste Prefs werden am Ende bereinigt.

    Returns: {'old_pref_ids': [...], 'new_pref_ids': [...]}
    """
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        person_id = app.person_id
        project_id = app.project.id

        existing_person_prefs: list[models.ActorLocationPref] = session.exec(
            select(models.ActorLocationPref)
            .where(models.ActorLocationPref.person_id == person_id)
            .where(models.ActorLocationPref.prep_delete == None)
        ).all()
        person_pref_index: dict[tuple[UUID, float], models.ActorLocationPref] = {
            (p.location_of_work_id, p.score): p for p in existing_person_prefs
        }

        old_pref_ids = [p.id for p in app.actor_location_prefs_defaults]

        new_prefs: list[models.ActorLocationPref] = []
        for loc_id, score in location_id_to_score.items():
            if score == 1.0:
                continue
            key = (loc_id, score)
            if key in person_pref_index:
                new_prefs.append(person_pref_index[key])
            else:
                new_pref = models.ActorLocationPref(
                    score=score,
                    project_id=project_id,
                    person_id=person_id,
                    location_of_work_id=loc_id,
                )
                session.add(new_pref)
                session.flush()
                new_prefs.append(new_pref)

        app.actor_location_prefs_defaults = new_prefs
        new_pref_ids = [p.id for p in new_prefs]

        now = _utcnow()
        for pref_id in set(old_pref_ids) - set(new_pref_ids):
            pref = session.get(models.ActorLocationPref, pref_id)
            if (pref and not pref.prep_delete
                    and not pref.actor_plan_periods_defaults
                    and not pref.avail_days_defaults
                    and not pref.person_default):
                pref.prep_delete = now

        session.flush()
        return {'old_pref_ids': old_pref_ids, 'new_pref_ids': new_pref_ids}


def restore_location_prefs_bulk(
        actor_plan_period_id: UUID,
        pref_ids_to_restore: list[UUID],
) -> None:
    """Undo-Gegenstück zu update_location_prefs_bulk: stellt alten Zustand wieder her."""
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        current_pref_ids = {p.id for p in app.actor_location_prefs_defaults}

        prefs_to_restore: list[models.ActorLocationPref] = []
        for pref_id in pref_ids_to_restore:
            pref = session.get(models.ActorLocationPref, pref_id)
            if pref:
                pref.prep_delete = None
                prefs_to_restore.append(pref)

        app.actor_location_prefs_defaults = prefs_to_restore

        now = _utcnow()
        for pref_id in current_pref_ids - set(pref_ids_to_restore):
            pref = session.get(models.ActorLocationPref, pref_id)
            if (pref and not pref.prep_delete
                    and not pref.actor_plan_periods_defaults
                    and not pref.avail_days_defaults
                    and not pref.person_default):
                pref.prep_delete = now

        session.flush()


def put_in_partner_location_pref(actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.actor_partner_location_prefs_defaults.append(session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def remove_partner_location_pref(actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.actor_partner_location_prefs_defaults.remove(session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)




def replace_comb_loc_possibles(
        actor_plan_period_id: UUID,
        person_id: UUID,
        original_ids: set[UUID],
        pending_creates: list[tuple[UUID, schemas.CombinationLocationsPossibleCreate]],
        current_combs: list[schemas.CombinationLocationsPossible],
) -> dict[str, list[UUID]]:
    """Ersetzt alle CombLocPossibles des ActorPlanPeriods in einer einzigen Session.

    Wiederverwendungslogik: Existiert in der Person bereits eine nicht-gelöschte
    CombLocPossible mit gleichem locations_of_work-ID-Set und time_span_between,
    wird sie übernommen statt neu angelegt.
    Verwaiste CombLocPossibles (kein Team/Person/APP/AvailDay-Bezug) werden soft-deleted.

    Returns: {'old_comb_ids': [...], 'new_comb_ids': [...]}
    """
    log_function_info()
    with get_session() as session:
        # Person-CLPs laden für Wiederverwendungs-Check
        person_clps = session.exec(
            select(models.CombinationLocationsPossible)
            .join(models.PersonCombLocLink,
                  models.PersonCombLocLink.combination_locations_possible_id
                  == models.CombinationLocationsPossible.id)
            .where(models.PersonCombLocLink.person_id == person_id)
            .where(models.CombinationLocationsPossible.prep_delete.is_(None))
            .options(selectinload(models.CombinationLocationsPossible.locations_of_work))
        ).all()

        # Index: (frozenset(loc_ids), time_span_between) → CombLocPossible
        person_clp_index: dict[tuple, models.CombinationLocationsPossible] = {
            (frozenset(loc.id for loc in clp.locations_of_work), clp.time_span_between): clp
            for clp in person_clps
        }

        # Temp-UUID → echte UUID auflösen
        temp_to_real: dict[UUID, UUID] = {}
        for temp_id, create_schema in pending_creates:
            loc_ids = frozenset(loc.id for loc in create_schema.locations_of_work)
            key = (loc_ids, create_schema.time_span_between)
            if key in person_clp_index:
                # Vorhandene CombLocPossible der Person wiederverwenden
                temp_to_real[temp_id] = person_clp_index[key].id
            else:
                # Neue CombLocPossible anlegen
                new_clp = models.CombinationLocationsPossible(
                    project=session.get(models.Project, create_schema.project.id),
                    time_span_between=create_schema.time_span_between)
                session.add(new_clp)
                session.flush()
                for loc in create_schema.locations_of_work:
                    new_clp.locations_of_work.append(session.get(models.LocationOfWork, loc.id))
                session.flush()
                temp_to_real[temp_id] = new_clp.id

        # Finale echte IDs bestimmen
        final_ids = {temp_to_real.get(c.id, c.id) for c in current_combs}

        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        old_ids = {c.id for c in app.combination_locations_possibles}

        # Assoziationen ersetzen
        app.combination_locations_possibles = [
            session.get(models.CombinationLocationsPossible, clp_id)
            for clp_id in final_ids
        ]
        session.flush()

        # Verwaiste CombLocPossibles soft-deleten
        now = _utcnow()
        for removed_id in old_ids - final_ids:
            clp = session.get(models.CombinationLocationsPossible, removed_id)
            if clp and not clp.prep_delete and is_comb_loc_orphaned(session, removed_id):
                clp.prep_delete = now
        session.flush()

        return {'old_comb_ids': list(old_ids), 'new_comb_ids': list(final_ids)}


def restore_comb_loc_possibles(
        actor_plan_period_id: UUID,
        comb_ids_to_restore: list[UUID],
) -> None:
    """Undo/Redo-Gegenstück zu replace_comb_loc_possibles: stellt einen früheren Zustand wieder her.

    Reaktiviert evtl. soft-gelöschte CombLocPossibles und setzt
    die Assoziationen des ActorPlanPeriods auf comb_ids_to_restore.
    Verwaiste CLPs aus dem aktuellen Zustand werden bereinigt.
    """
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        current_ids = {c.id for c in app.combination_locations_possibles}
        ids_to_restore = set(comb_ids_to_restore)

        # Evtl. soft-gelöschte CLPs reaktivieren
        for clp_id in ids_to_restore:
            clp = session.get(models.CombinationLocationsPossible, clp_id)
            if clp and clp.prep_delete:
                clp.prep_delete = None

        # Assoziationen ersetzen
        app.combination_locations_possibles = [
            session.get(models.CombinationLocationsPossible, clp_id)
            for clp_id in ids_to_restore
        ]
        session.flush()

        # Verwaiste CombLocPossibles soft-deleten
        now = _utcnow()
        for removed_id in current_ids - ids_to_restore:
            clp = session.get(models.CombinationLocationsPossible, removed_id)
            if clp and not clp.prep_delete and is_comb_loc_orphaned(session, removed_id):
                clp.prep_delete = now
        session.flush()