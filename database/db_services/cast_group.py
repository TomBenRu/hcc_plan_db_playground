"""Service-Funktionen für CastGroup (Besetzungsgruppe).

Eine CastGroup definiert, wie viele Akteure für ein Event benötigt werden und
welche Regeln (CastRule, fixed_cast, strict_cast_pref) dabei gelten. CastGroups
können hierarchisch verschachtelt sein (parent/child). Das Erstellen unterstützt
einen Restore-Modus, um bei Undo-Operationen exakt die gleiche Struktur
wiederherzustellen.
"""
import datetime
from uuid import UUID

from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import cast_group_show_options


def get(cast_group_id: UUID) -> schemas.CastGroupShow:
    with get_session() as session:
        return schemas.CastGroupShow.model_validate(session.get(models.CastGroup, cast_group_id))


def get_all_from__plan_period(plan_period_id: UUID) -> list[schemas.CastGroupShow]:
    with get_session() as session:
        stmt = (select(models.CastGroup)
                .where(models.CastGroup.plan_period_id == plan_period_id)
                .options(*cast_group_show_options()))
        cast_groups = session.exec(stmt).unique().all()
        return [schemas.CastGroupShow.model_validate(cg) for cg in cast_groups]


def get_all_for_button__plan_period(plan_period_id: UUID) -> list[schemas.CastGroupForButton]:
    """Lädt alle CastGroups eines PlanPeriods als minimales CastGroupForButton-Schema.

    Verwendet nur selectinload(event) ohne tiefe Relationship-Chains – spart
    parent_groups, child_groups, cast_rule, plan_period-Ketten vollständig ein.
    Für ButtonFixedCast geeignet, da nur id, fixed_cast* und event.location_plan_period_id
    + event.date benötigt werden.
    """
    with get_session() as session:
        stmt = (select(models.CastGroup)
                .where(models.CastGroup.plan_period_id == plan_period_id)
                .options(selectinload(models.CastGroup.event)))
        cast_groups = session.exec(stmt).all()
        return [schemas.CastGroupForButton.model_validate(cg) for cg in cast_groups]


def get_all_for_button__location_plan_period(
        location_plan_period_id: UUID) -> list[schemas.CastGroupForButton]:
    """Batch-Variante: alle CastGroupForButton einer LocationPlanPeriod in einer Query.

    Ersetzt N×get_all_for_button__location_plan_period_at_date() durch eine einzige Abfrage.
    Der Aufrufer verteilt die Ergebnisse anhand event.date auf die einzelnen Buttons.
    """
    with get_session() as session:
        stmt = (select(models.CastGroup)
                .join(models.Event)
                .where(models.Event.location_plan_period_id == location_plan_period_id)
                .options(selectinload(models.CastGroup.event)))
        cgs = session.exec(stmt).all()
        return [schemas.CastGroupForButton.model_validate(cg) for cg in cgs]


def get_all_for_button__location_plan_period_at_date(
        location_plan_period_id: UUID, date: datetime.date) -> list[schemas.CastGroupForButton]:
    """Minimale CastGroupForButton-Variante für ButtonFixedCast-Reload nach Signalauslösung."""
    with get_session() as session:
        stmt = (select(models.CastGroup)
                .join(models.Event)
                .where(models.Event.date == date,
                       models.Event.location_plan_period_id == location_plan_period_id)
                .options(selectinload(models.CastGroup.event)))
        cgs = session.exec(stmt).all()
        return [schemas.CastGroupForButton.model_validate(cg) for cg in cgs]


def get_all_from__location_plan_period_at_date(
        location_plan_period_id: UUID, date: datetime.date) -> list[schemas.CastGroupShow]:
    with get_session() as session:
        cgs = session.exec(
            select(models.CastGroup).join(models.Event)
            .where(models.Event.date == date,
                   models.Event.location_plan_period_id == location_plan_period_id)
        ).all()
        return [schemas.CastGroupShow.model_validate(cg) for cg in cgs]


def get_cast_group_of_event(event_id: UUID) -> schemas.CastGroupShow:
    with get_session() as session:
        stmt = (select(models.CastGroup)
                .join(models.Event, models.Event.cast_group_id == models.CastGroup.id)
                .where(models.Event.id == event_id)
                .options(*cast_group_show_options()))
        cg = session.exec(stmt).unique().first()
        return schemas.CastGroupShow.model_validate(cg)


def get_nr_actors_of_event(event_id: UUID) -> int:
    """Gibt nur nr_actors zurück – spart das vollständige CastGroupShow-Loading."""
    with get_session() as session:
        stmt = (select(models.CastGroup.nr_actors)
                .join(models.Event, models.Event.cast_group_id == models.CastGroup.id)
                .where(models.Event.id == event_id))
        return session.exec(stmt).first()


def get_nr_actors_by_event_ids(event_ids: list[UUID]) -> dict[UUID, int]:
    """Gibt {event_id: nr_actors} in einer einzigen Query zurück.

    Ersetzt N einzelne get_cast_group_of_event()-Aufrufe durch eine
    Batch-Abfrage. Für den Plan-Tab deutlich schneller bei vielen Events.
    """
    if not event_ids:
        return {}
    with get_session() as session:
        stmt = (select(models.Event)
                .where(models.Event.id.in_(event_ids))
                .options(joinedload(models.Event.cast_group)))
        events = session.exec(stmt).unique().all()
        return {e.id: e.cast_group.nr_actors for e in events}


def create(*, plan_period_id: UUID, restore_cast_group: schemas.CastGroupShow = None) -> schemas.CastGroupShow:
    log_function_info()
    with get_session() as session:
        pp = session.get(models.PlanPeriod, plan_period_id)
        if restore_cast_group:
            cast_rule = session.get(models.CastRule, restore_cast_group.cast_rule.id) if restore_cast_group.cast_rule else None
            cg = models.CastGroup(id=restore_cast_group.id, nr_actors=0, plan_period=pp, cast_rule=cast_rule)
            session.add(cg)
            session.flush()
            for pg in restore_cast_group.parent_groups:
                cg.parent_groups.append(session.get(models.CastGroup, pg.id))
            for child in restore_cast_group.child_groups:
                cg.child_groups.append(session.get(models.CastGroup, child.id))
            cg.nr_actors = restore_cast_group.nr_actors
            cg.fixed_cast = restore_cast_group.fixed_cast
            cg.strict_cast_pref = restore_cast_group.strict_cast_pref
        else:
            cg = models.CastGroup(nr_actors=0, plan_period=pp)
            session.add(cg)
        session.flush()
        return schemas.CastGroupShow.model_validate(cg)


def set_new_parent(cast_group_id: UUID, new_parent_id: UUID | None) -> schemas.CastGroupShow:
    log_function_info()
    with get_session() as session:
        cg = session.get(models.CastGroup, cast_group_id)
        cg.parent_groups.append(session.get(models.CastGroup, new_parent_id))
        session.flush()
        return schemas.CastGroupShow.model_validate(cg)


def remove_from_parent(cast_group_id: UUID, parent_group_id: UUID | None) -> schemas.CastGroupShow:
    log_function_info()
    with get_session() as session:
        cg = session.get(models.CastGroup, cast_group_id)
        cg.parent_groups.remove(session.get(models.CastGroup, parent_group_id))
        session.flush()
        return schemas.CastGroupShow.model_validate(cg)


def update_fixed_cast(cast_group_id: UUID, fixed_cast: str,
                      fixed_cast_only_if_available: bool) -> schemas.CastGroupShow:
    log_function_info()
    with get_session() as session:
        cg = session.get(models.CastGroup, cast_group_id)
        cg.fixed_cast = fixed_cast
        cg.fixed_cast_only_if_available = fixed_cast_only_if_available
        session.flush()
        return schemas.CastGroupShow.model_validate(cg)


def update_nr_actors(cast_group_id: UUID, nr_actors: int) -> schemas.CastGroupShow:
    log_function_info()
    with get_session() as session:
        cg = session.get(models.CastGroup, cast_group_id)
        cg.nr_actors = nr_actors
        session.flush()
        return schemas.CastGroupShow.model_validate(cg)


def update_strict_cast_pref(cast_group_id: UUID, strict_cast_pref: int) -> schemas.CastGroupShow:
    log_function_info()
    with get_session() as session:
        cg = session.get(models.CastGroup, cast_group_id)
        cg.strict_cast_pref = strict_cast_pref
        session.flush()
        return schemas.CastGroupShow.model_validate(cg)


def update_prefer_fixed_cast_events(cast_group_id: UUID, prefer_fixed_cast_events: bool) -> schemas.CastGroupShow:
    log_function_info()
    with get_session() as session:
        cg = session.get(models.CastGroup, cast_group_id)
        cg.prefer_fixed_cast_events = prefer_fixed_cast_events
        session.flush()
        return schemas.CastGroupShow.model_validate(cg)


def update_custom_rule(cast_group_id: UUID, custom_rule: str) -> schemas.CastGroupShow:
    log_function_info()
    with get_session() as session:
        cg = session.get(models.CastGroup, cast_group_id)
        cg.custom_rule = custom_rule
        session.flush()
        return schemas.CastGroupShow.model_validate(cg)


def update_cast_rule(cast_group_id: UUID, cast_rule_id: UUID | None) -> schemas.CastGroupShow:
    log_function_info()
    with get_session() as session:
        cg = session.get(models.CastGroup, cast_group_id)
        cg.cast_rule = session.get(models.CastRule, cast_rule_id) if cast_rule_id else None
        session.flush()
        return schemas.CastGroupShow.model_validate(cg)


def delete(cast_group_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.CastGroup, cast_group_id))