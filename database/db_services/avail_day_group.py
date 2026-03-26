"""Service-Funktionen für AvailDayGroup (Verfügbarkeitstag-Gruppe).

AvailDayGroups bilden eine Baumstruktur unterhalb eines ActorPlanPeriod-Masters.
Jeder Blattknoten referenziert genau einen AvailDay. Interne Knoten steuern
über `nr_avail_day_groups` und `variation_weight`, wie viele Tage aus der
Gruppe gefordert werden und wie stark Variationen gewichtet sind.
`get_all_for_tree` lädt den kompletten Baum in einem einzigen Session-Kontext.
"""
import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(avail_day_group_id: UUID) -> schemas.AvailDayGroupShow:
    with get_session() as session:
        return schemas.AvailDayGroupShow.model_validate(session.get(models.AvailDayGroup, avail_day_group_id))


def get_master_from__actor_plan_period(actor_plan_period_id: UUID) -> schemas.AvailDayGroupShow:
    with get_session() as session:
        return schemas.AvailDayGroupShow.model_validate(
            session.get(models.ActorPlanPeriod, actor_plan_period_id).avail_day_group)


def get_child_groups_from__parent_group(avail_day_group_id) -> list[schemas.AvailDayGroupShow]:
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        return [schemas.AvailDayGroupShow.model_validate(c) for c in adg.avail_day_groups]


def get_all_for_tree(actor_plan_period_id: UUID) -> dict[UUID, schemas.AvailDayGroupTreeNode]:
    """Lädt alle AvailDayGroups eines ActorPlanPeriods mit Level-by-Level Batch-Queries.

    Ersetzt die rekursive collect()-Traversierung (N Lazy-Loads pro Session) durch
    O(depth) IN-Queries. AvailDay-IDs werden per direkter FK-Map ohne Relationship-Traversal
    ermittelt (verhindert den Lazy-Load auf AvailDayGroup.avail_day).
    """
    with get_session() as session:
        # Schritt 1: Master-AvailDayGroup direkt laden – vermeidet Lazy-Load via ActorPlanPeriod.avail_day_group
        master = session.exec(
            select(models.AvailDayGroup)
            .where(models.AvailDayGroup.actor_plan_period_id == actor_plan_period_id)
        ).first()
        if master is None:
            return {}

        # Schritt 2: Alle Descendants Level-by-Level laden (O(depth) IN-Queries)
        all_adgs: dict[UUID, models.AvailDayGroup] = {master.id: master}
        current_parent_ids: set[UUID] = {master.id}

        while current_parent_ids:
            children = session.exec(
                select(models.AvailDayGroup)
                .where(models.AvailDayGroup.avail_day_group_id.in_(current_parent_ids))
            ).all()
            if not children:
                break
            current_parent_ids = set()
            for child in children:
                all_adgs[child.id] = child
                current_parent_ids.add(child.id)

        # Schritt 3: Alle AvailDays für Leaf-Nodes in einem Batch laden
        # Direkte FK-Map: avail_day_group_id → avail_day.id
        # Vermeidet den Lazy-Load auf AvailDayGroup.avail_day (Identity-Map befüllt die
        # Relationship NICHT automatisch – jeder Zugriff auf adg.avail_day würde eine Query auslösen)
        avail_days = session.exec(
            select(models.AvailDay)
            .where(models.AvailDay.avail_day_group_id.in_(all_adgs.keys()))
        ).all()
        avail_day_id_by_adg: dict[UUID, UUID] = {
            ad.avail_day_group_id: ad.id for ad in avail_days
        }

        # Schritt 4: Child-IDs in-memory bestimmen und TreeNodes bauen
        child_ids_map: dict[UUID, list[UUID]] = {adg_id: [] for adg_id in all_adgs}
        for adg in all_adgs.values():
            if adg.avail_day_group_id and adg.avail_day_group_id in child_ids_map:
                child_ids_map[adg.avail_day_group_id].append(adg.id)

        return {
            adg_id: schemas.AvailDayGroupTreeNode(
                id=adg.id,
                variation_weight=adg.variation_weight or 1,
                nr_avail_day_groups=adg.nr_avail_day_groups,
                child_ids=child_ids_map[adg_id],
                avail_day_id=avail_day_id_by_adg.get(adg_id),
            )
            for adg_id, adg in all_adgs.items()
        }


def get_all_for_trees_batch(actor_plan_period_ids: list[UUID]) -> dict[UUID, dict[UUID, schemas.AvailDayGroupTreeNode]]:
    """Batch-Version: Lädt alle AvailDayGroup-Bäume für mehrere ActorPlanPeriods in EINER Session.

    Ersetzt N einzelne get_all_for_tree()-Aufrufe (N Sessions) durch eine einzige Session.
    Alle BFS-Levels werden mit IN-Queries quer über alle APPs traversiert.

    Returns:
        Dict: actor_plan_period_id → {adg_id → AvailDayGroupTreeNode}
    """
    if not actor_plan_period_ids:
        return {}
    with get_session() as session:
        # Schritt 1: Alle Master-Nodes in einem Query
        masters = session.exec(
            select(models.AvailDayGroup)
            .where(models.AvailDayGroup.actor_plan_period_id.in_(actor_plan_period_ids))
        ).all()
        if not masters:
            return {app_id: {} for app_id in actor_plan_period_ids}

        all_adgs: dict[UUID, models.AvailDayGroup] = {m.id: m for m in masters}
        # Welcher Master gehört zu welchem APP?
        master_app_map: dict[UUID, UUID] = {m.id: m.actor_plan_period_id for m in masters}
        current_parent_ids: set[UUID] = {m.id for m in masters}

        # Schritt 2: BFS Level-by-Level für ALLE Bäume gleichzeitig
        while current_parent_ids:
            children = session.exec(
                select(models.AvailDayGroup)
                .where(models.AvailDayGroup.avail_day_group_id.in_(current_parent_ids))
            ).all()
            if not children:
                break
            current_parent_ids = set()
            for child in children:
                all_adgs[child.id] = child
                current_parent_ids.add(child.id)

        # Schritt 3: Alle AvailDays in einem Batch
        avail_days = session.exec(
            select(models.AvailDay)
            .where(models.AvailDay.avail_day_group_id.in_(all_adgs.keys()))
        ).all()
        avail_day_id_by_adg: dict[UUID, UUID] = {
            ad.avail_day_group_id: ad.id for ad in avail_days
        }

        # Schritt 4: Child-IDs in-memory bestimmen
        child_ids_map: dict[UUID, list[UUID]] = {adg_id: [] for adg_id in all_adgs}
        for adg in all_adgs.values():
            if adg.avail_day_group_id and adg.avail_day_group_id in child_ids_map:
                child_ids_map[adg.avail_day_group_id].append(adg.id)

        # Schritt 5: BFS – jedem ADG die APP-ID zuweisen (von Master nach unten)
        adg_to_app: dict[UUID, UUID] = {}
        for master in masters:
            app_id = master.actor_plan_period_id
            queue = [master.id]
            while queue:
                current_id = queue.pop()
                adg_to_app[current_id] = app_id
                queue.extend(child_ids_map[current_id])

        # Schritt 6: Ergebnis-Dict pro APP aufbauen
        result: dict[UUID, dict[UUID, schemas.AvailDayGroupTreeNode]] = {
            app_id: {} for app_id in actor_plan_period_ids
        }
        for adg_id, adg in all_adgs.items():
            app_id = adg_to_app.get(adg_id)
            if app_id is None:
                continue
            result[app_id][adg_id] = schemas.AvailDayGroupTreeNode(
                id=adg.id,
                variation_weight=adg.variation_weight or 1,
                nr_avail_day_groups=adg.nr_avail_day_groups,
                child_ids=child_ids_map[adg_id],
                avail_day_id=avail_day_id_by_adg.get(adg_id),
            )
        return result


def create(*, actor_plan_period_id: Optional[UUID] = None,
           avail_day_group_id: Optional[UUID] = None, undo_id: UUID = None) -> schemas.AvailDayGroupShow:
    log_function_info()
    with get_session() as session:
        kwargs = {}
        if actor_plan_period_id:
            kwargs['actor_plan_period'] = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        if avail_day_group_id:
            kwargs['avail_day_group'] = session.get(models.AvailDayGroup, avail_day_group_id)
        if undo_id:
            kwargs['id'] = undo_id
        adg = models.AvailDayGroup(**kwargs)
        session.add(adg)
        session.flush()
        return schemas.AvailDayGroupShow.model_validate(adg)


def update_nr_avail_day_groups(avail_day_group_id: UUID, nr_avail_day_groups: int | None) -> schemas.AvailDayGroupShow:
    log_function_info()
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        adg.nr_avail_day_groups = nr_avail_day_groups
        session.flush()
        return schemas.AvailDayGroupShow.model_validate(adg)


def update_variation_weight(avail_day_group_id: UUID, variation_weight: int) -> schemas.AvailDayGroupShow:
    log_function_info()
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        adg.variation_weight = variation_weight
        session.flush()
        return schemas.AvailDayGroupShow.model_validate(adg)


def update_mandatory_nr_avail_day_groups(avail_day_group_id: UUID, mandatory_nr_avail_day_groups: int | None) -> schemas.AvailDayGroupShow:
    log_function_info()
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        adg.mandatory_nr_avail_day_groups = mandatory_nr_avail_day_groups
        session.flush()
        return schemas.AvailDayGroupShow.model_validate(adg)


def set_new_parent(avail_day_group_id: UUID, new_parent_id: UUID) -> schemas.AvailDayGroupShow:
    log_function_info()
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        adg.avail_day_group = session.get(models.AvailDayGroup, new_parent_id)
        session.flush()
        return schemas.AvailDayGroupShow.model_validate(adg)


def delete(avail_day_group_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.AvailDayGroup, avail_day_group_id))