"""Service-Funktionen für Person (Akteur / Mitarbeiter).

Verwaltet Personen innerhalb eines Projekts inklusive Adresse, Tageszeiten,
Standortpräferenzen, Skills und Flags. Passwörter werden vor dem Speichern
gehasht. Bietet einen Bulk-Import aus Excel-Dateien (`create_persons_from_xlsx`).
Soft-Delete via `prep_delete`-Timestamp. Spezielle Abfragen filtern Personen
nach PlanPeriod oder nach aktiven TeamActorAssign-Zeiträumen.
"""
import datetime
from uuid import UUID

from sqlalchemy import or_
from sqlmodel import select

import pandas as pd

from .. import schemas, models
from ..authentication import hash_psw
from ..database import get_session
from ..models import _utcnow
from ..enums import Gender
from ._common import log_function_info
from ._eager_loading import person_show_options, person_for_comb_loc_dialog_options
from .combination_locations_possible import is_comb_loc_orphaned


def get(person_id: UUID) -> schemas.PersonShow:
    with get_session() as session:
        stmt = (select(models.Person)
                .where(models.Person.id == person_id)
                .options(*person_show_options()))
        person = session.exec(stmt).unique().one()
        return schemas.PersonShow.model_validate(person)


def get_for_comb_loc_dialog(person_id: UUID) -> schemas.PersonForCombLocDialog:
    """Lädt nur team_actor_assigns + combination_locations_possibles für DlgCombLocPossibleEditList."""
    with get_session() as session:
        stmt = (select(models.Person)
                .where(models.Person.id == person_id)
                .options(*person_for_comb_loc_dialog_options()))
        person = session.exec(stmt).unique().one()
        return schemas.PersonForCombLocDialog.model_validate(person)


def get_full_name_of_person(person_id: UUID) -> str:
    with get_session() as session:
        p = session.get(models.Person, person_id)
        return f'{p.f_name} {p.l_name}'


def get_full_names_for_ids(person_ids: list[UUID]) -> dict[UUID, str]:
    """Batch-Abfrage: Lädt Vor- und Nachnamen für mehrere Personen in einer einzigen DB-Session."""
    with get_session() as session:
        persons = session.exec(
            select(models.Person.id, models.Person.f_name, models.Person.l_name)
            .where(models.Person.id.in_(person_ids))
        ).all()
        return {p_id: f'{f_name} {l_name}' for p_id, f_name, l_name in persons}


def get_all_from__project(project_id: UUID, minimal: bool = False) -> list[schemas.PersonShow | tuple[str, UUID]]:
    with get_session() as session:
        persons = session.exec(
            select(models.Person).where(
                models.Person.project_id == project_id,
                models.Person.prep_delete.is_(None)
            )
        ).all()
        return ([(p.full_name, p.id) for p in persons] if minimal
                else [schemas.PersonShow.model_validate(p) for p in persons])


def get_all_from__plan_period(plan_period_id: UUID) -> list[schemas.PersonShow]:
    with get_session() as session:
        persons = session.exec(
            select(models.Person).join(models.ActorPlanPeriod)
            .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)
        ).unique().all()
        return [schemas.PersonShow.model_validate(p) for p in persons]


def get_all_from__plan_period_minimal(plan_period_id: UUID) -> dict['str', UUID]:
    with get_session() as session:
        pp_db = session.get(models.PlanPeriod, plan_period_id)
        return {app.person.full_name: app.person.id for app in pp_db.actor_plan_periods}


def get_all_possible_from__plan_period_minimal(plan_period_id: UUID) -> dict['str', UUID]:
    with get_session() as session:
        pp_db = session.get(models.PlanPeriod, plan_period_id)
        assigns = session.exec(
            select(models.TeamActorAssign).where(
                models.TeamActorAssign.team_id == pp_db.team_id,
                models.TeamActorAssign.start < pp_db.end,
                or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end > pp_db.end)
            )
        ).all()
        return {taa.person.full_name: taa.person.id for taa in assigns}


def get_dispatchers_from__project(project_id: UUID) -> list[schemas.PersonShow]:
    with get_session() as session:
        dispatchers = session.exec(
            select(models.Person).join(models.Team, models.Team.dispatcher_id == models.Person.id)
            .where(models.Person.project_id == project_id)
        ).unique().all()
        return [schemas.PersonShow.model_validate(d) for d in dispatchers]


def create(person: schemas.PersonCreate, project_id: UUID, person_id: UUID = None) -> schemas.Person:
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        if person.address:
            address_db = models.Address(**person.address.model_dump(exclude={'project_id'}), project=project_db)
            session.add(address_db)
        else:
            address_db = None
        person_data = person.model_dump(exclude={'address'})
        person_data['password'] = hash_psw(person.password)
        if person_id:
            person_data['id'] = person_id
        person_db = models.Person(**person_data, address=address_db, project=project_db)
        session.add(person_db)
        session.flush()
        return schemas.Person.model_validate(person_db)


def create_persons_from_xlsx(file_name: str, project_id: UUID) -> list[schemas.Person]:
    log_function_info()
    with get_session() as session:
        team_db = session.exec(select(models.Team).where(models.Team.project_id == project_id)).first()
        try:
            df = pd.read_excel(file_name)
        except Exception as e:
            raise ValueError(f'Error while reading xlsx file: {e}')
        persons_list: list[schemas.Person] = []
        project_db = session.get(models.Project, project_id)
        for _, row in df.iterrows():
            person_db = models.Person(
                f_name=row['First name'], l_name=row['Last name'],
                email='fake@email.com', gender=Gender.divers, phone_nr=None,
                username=row['username'], password=hash_psw('password'),
                project=project_db, address=None)
            session.add(person_db)
            session.flush()
            taa = models.TeamActorAssign(start=datetime.date.today(), person=person_db, team=team_db)
            session.add(taa)
            session.flush()
            persons_list.append(schemas.Person.model_validate(person_db))
        return persons_list


def update(person: schemas.PersonShow) -> schemas.Person:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person.id)
        if person_db.address:
            if person.address:
                addr = session.get(models.Address, person.address.id)
                for k, v in person.address.model_dump(include={'name', 'street', 'postal_code', 'city'}).items():
                    setattr(addr, k, v)
            else:
                person_db.address = None
        elif person.address:
            person_db.address = session.get(models.Address, person.address.id)
        person_db.time_of_days.clear()
        for t_o_d in person.time_of_days:
            person_db.time_of_days.append(session.get(models.TimeOfDay, t_o_d.id))
        for k, v in person.model_dump(include={'f_name', 'l_name', 'email', 'gender', 'phone_nr', 'requested_assignments', 'notes'}).items():
            setattr(person_db, k, v)
        session.flush()
        return schemas.Person.model_validate(person_db)


def update_project_of_admin(person_id: UUID, project_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.project_of_admin = session.get(models.Project, project_id)
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def put_in_time_of_day(person_id: UUID, time_of_day_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.time_of_days.append(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def remove_in_time_of_day(person_id: UUID, time_of_day_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.time_of_days.remove(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def new_time_of_day_standard(person_id: UUID, time_of_day_id: UUID) -> tuple[schemas.PersonShow, UUID | None]:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        tod_db = session.get(models.TimeOfDay, time_of_day_id)
        old_id = None
        for t in list(person_db.time_of_day_standards):
            if t.time_of_day_enum.id == tod_db.time_of_day_enum.id:
                person_db.time_of_day_standards.remove(t)
                old_id = t.id
                break
        person_db.time_of_day_standards.append(tod_db)
        session.flush()
        return schemas.PersonShow.model_validate(person_db), old_id


def remove_time_of_day_standard(person_id: UUID, time_of_day_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.time_of_day_standards.remove(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def delete(person_id: UUID) -> schemas.Person:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.prep_delete = _utcnow()
        session.flush()
        return schemas.Person.model_validate(person_db)


def put_in_comb_loc_possible(person_id: UUID, comb_loc_possible_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.combination_locations_possibles.append(
            session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def remove_comb_loc_possible(person_id: UUID, comb_loc_possible_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.combination_locations_possibles.remove(
            session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def replace_comb_loc_possibles(
        person_id: UUID,
        original_ids: set[UUID],
        pending_creates: list[tuple[UUID, schemas.CombinationLocationsPossibleCreate]],
        current_combs: list[schemas.CombinationLocationsPossible],
) -> dict[str, list[UUID]]:
    """Ersetzt alle CombLocPossibles einer Person in einer einzigen Session.

    Neue CLPs werden aus pending_creates angelegt. Verwaiste CLPs werden soft-deleted.
    Returns: {'old_comb_ids': [...], 'new_comb_ids': [...]}
    """
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        old_ids = {c.id for c in person_db.combination_locations_possibles}

        # Neue CLPs anlegen und Temp-IDs auflösen
        temp_to_real: dict[UUID, UUID] = {}
        for temp_id, create_schema in pending_creates:
            new_clp = models.CombinationLocationsPossible(
                project=session.get(models.Project, create_schema.project.id),
                time_span_between=create_schema.time_span_between)
            session.add(new_clp)
            session.flush()
            for loc in create_schema.locations_of_work:
                new_clp.locations_of_work.append(session.get(models.LocationOfWork, loc.id))
            session.flush()
            temp_to_real[temp_id] = new_clp.id

        # Finale echte IDs bestimmen und Assoziationen ersetzen
        final_ids = {temp_to_real.get(c.id, c.id) for c in current_combs}
        person_db.combination_locations_possibles = [
            session.get(models.CombinationLocationsPossible, clp_id) for clp_id in final_ids]
        session.flush()

        # Verwaiste CLPs soft-deleten
        now = _utcnow()
        for removed_id in old_ids - final_ids:
            clp = session.get(models.CombinationLocationsPossible, removed_id)
            if clp and not clp.prep_delete and is_comb_loc_orphaned(session, removed_id):
                clp.prep_delete = now
        session.flush()

        return {'old_comb_ids': list(old_ids), 'new_comb_ids': list(final_ids)}


def restore_comb_loc_possibles(
        person_id: UUID,
        comb_ids_to_restore: list[UUID],
) -> None:
    """Undo/Redo-Gegenstück zu replace_comb_loc_possibles für Person."""
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        current_ids = {c.id for c in person_db.combination_locations_possibles}
        ids_to_restore = set(comb_ids_to_restore)

        for clp_id in ids_to_restore:
            clp = session.get(models.CombinationLocationsPossible, clp_id)
            if clp and clp.prep_delete:
                clp.prep_delete = None

        person_db.combination_locations_possibles = [
            session.get(models.CombinationLocationsPossible, clp_id)
            for clp_id in ids_to_restore]
        session.flush()

        now = _utcnow()
        for removed_id in current_ids - ids_to_restore:
            clp = session.get(models.CombinationLocationsPossible, removed_id)
            if clp and not clp.prep_delete and is_comb_loc_orphaned(session, removed_id):
                clp.prep_delete = now
        session.flush()


def put_in_location_pref(person_id: UUID, actor_loc_pref_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.actor_location_prefs_defaults.append(session.get(models.ActorLocationPref, actor_loc_pref_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def remove_location_pref(person_id: UUID, actor_loc_pref_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.actor_location_prefs_defaults.remove(session.get(models.ActorLocationPref, actor_loc_pref_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def put_in_partner_location_pref(person_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.actor_partner_location_prefs_defaults.append(
            session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def remove_partner_location_pref(person_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.actor_partner_location_prefs_defaults.remove(
            session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def add_skill(person_id: UUID, skill_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.skills.append(session.get(models.Skill, skill_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def remove_skill(person_id: UUID, skill_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.skills.remove(session.get(models.Skill, skill_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def put_in_flag(person_id: UUID, flag_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.flags.append(session.get(models.Flag, flag_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def remove_flag(person_id: UUID, flag_id: UUID) -> schemas.PersonShow:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        person_db.flags.remove(session.get(models.Flag, flag_id))
        session.flush()
        return schemas.PersonShow.model_validate(person_db)


def get_persons_of_team_at_date(team_id: UUID, date: datetime.date) -> list[schemas.PersonForFixedCastCombo]:
    """Gibt Personen eines Teams an einem Datum zurück.

    Ersetzt den zweistufigen Ansatz (TeamActorAssign laden → persons extrahieren)
    durch einen einzigen JOIN-Query mit SQL-seitigem prep_delete-Filter.
    """
    cutoff = datetime.datetime.combine(date, datetime.time.max)
    with get_session() as session:
        stmt = (
            select(models.Person)
            .join(models.TeamActorAssign, models.TeamActorAssign.person_id == models.Person.id)
            .where(
                models.TeamActorAssign.team_id == team_id,
                models.TeamActorAssign.start <= date,
                or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end > date),
                or_(models.Person.prep_delete.is_(None), models.Person.prep_delete > cutoff),
            )
            .order_by(models.Person.f_name)
        )
        return [schemas.PersonForFixedCastCombo.model_validate(p) for p in session.exec(stmt).unique().all()]


def get_persons_of_team_between_dates(team_id: UUID, date_start: datetime.date,
                                      date_end: datetime.date) -> list[schemas.PersonForFixedCastCombo]:
    """Alle Personen, die dem Team in [date_start, date_end] angehörten (Vereinigung, 1 Query).

    Ersetzt N einzelne get_persons_of_team_at_date()-Aufrufe (einen pro Tag) durch
    einen einzigen JOIN-Query über den gesamten Datumsbereich.
    """
    cutoff_end = datetime.datetime.combine(date_end, datetime.time.max)
    with get_session() as session:
        stmt = (
            select(models.Person)
            .join(models.TeamActorAssign, models.TeamActorAssign.person_id == models.Person.id)
            .where(
                models.TeamActorAssign.team_id == team_id,
                models.TeamActorAssign.start <= date_end,
                or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end > date_start),
                or_(models.Person.prep_delete.is_(None), models.Person.prep_delete > cutoff_end),
            )
            .order_by(models.Person.f_name)
        )
        return [schemas.PersonForFixedCastCombo.model_validate(p) for p in session.exec(stmt).unique().all()]
