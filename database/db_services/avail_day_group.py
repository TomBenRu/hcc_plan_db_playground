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
from ._eager_loading import avail_day_group_dialog_options


def get(avail_day_group_id: UUID) -> schemas.AvailDayGroupShow:
    with get_session() as session:
        return schemas.AvailDayGroupShow.model_validate(session.get(models.AvailDayGroup, avail_day_group_id))


def get_for_dialog_properties(avail_day_group_id: UUID) -> schemas.AvailDayGroupForDialog:
    """Lädt eine einzelne AvailDayGroup mit minimalen Optionen für den Gruppen-Eigenschaften-Dialog.

    Ersetzt get() in get_group_from_id für post-Mutations-Refreshes (nr_childs_changed,
    chk_none_toggled) — kein avail_day_groups-Feld (Kinder-Liste), kein actor_plan_period-Chain.
    Gegenüber get() spart das ~90 % model_validate-Zeit (kein AvailDayGroupShow-Overhead).
    """
    with get_session() as session:
        stmt = (
            select(models.AvailDayGroup)
            .where(models.AvailDayGroup.id == avail_day_group_id)
            .options(*avail_day_group_dialog_options())
        )
        adg = session.exec(stmt).unique().one()
        return schemas.AvailDayGroupForDialog.model_validate(adg)


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


def get_flat_tree_for_dialog__actor_plan_period(
        actor_plan_period_id: UUID,
) -> tuple[schemas.AvailDayGroupForDialog | None, dict[UUID, list[schemas.AvailDayGroupForDialog]]]:
    """Lädt den gesamten AvailDayGroup-Baum eines APPs für den Dialog in 2 Roundtrips.

    Ersetzt N× get_child_groups_from__parent_group() in setup_tree() + sortByColumn()
    durch:
      1. Rekursiver CTE → alle (id, avail_day_group_id) des Baums (1 Roundtrip)
      2. Batch-SELECT aller AvailDayGroups mit avail_day_group_dialog_options() (1 Roundtrip)

    Gibt AvailDayGroupForDialog zurück (kein avail_day_groups-Feld, nur AvailDayForDialogTree
    als avail_day-Objekt) — eliminiert die rekursive Pydantic-Validierung der Kinder.

    Returns:
        (master_group, {parent_avail_day_group_id: [child AvailDayGroupForDialogs]})
    """
    with get_session() as session:
        # ── Schritt 1: alle IDs + Parent-IDs via rekursivem CTE ─────────────
        base = (
            select(models.AvailDayGroup.id, models.AvailDayGroup.avail_day_group_id)
            .where(models.AvailDayGroup.actor_plan_period_id == actor_plan_period_id)
            .cte(name='adg_tree', recursive=True)
        )
        recursive = (
            select(models.AvailDayGroup.id, models.AvailDayGroup.avail_day_group_id)
            .join(base, models.AvailDayGroup.avail_day_group_id == base.c.id)
        )
        cte = base.union_all(recursive)
        id_rows: list[tuple[UUID, UUID | None]] = session.exec(select(cte.c.id, cte.c.avail_day_group_id)).all()

        if not id_rows:
            return None, {}

        all_ids = [row[0] for row in id_rows]
        id__parent_id: dict[UUID, UUID | None] = {row[0]: row[1] for row in id_rows}

        # ── Schritt 2: Batch-Load mit minimalen Dialog-Optionen ─────────────
        stmt = (
            select(models.AvailDayGroup)
            .where(models.AvailDayGroup.id.in_(all_ids))
            .options(*avail_day_group_dialog_options())
        )
        all_adgs = session.exec(stmt).unique().all()

        id__adg: dict[UUID, schemas.AvailDayGroupForDialog] = {
            adg.id: schemas.AvailDayGroupForDialog.model_validate(adg)
            for adg in all_adgs
        }

        # ── Schritt 3: Parent→Children-Dict aufbauen (in-memory) ────────────
        parent__children: dict[UUID, list[schemas.AvailDayGroupForDialog]] = {}
        master: schemas.AvailDayGroupForDialog | None = None

        for adg_id, parent_id in id__parent_id.items():
            adg = id__adg.get(adg_id)
            if adg is None:
                continue
            if parent_id is None:
                master = adg
            else:
                parent__children.setdefault(parent_id, []).append(adg)

        return master, parent__children


def get_parent_info(avail_day_group_id: UUID) -> tuple[UUID | None, int | None]:
    """Gibt (parent_id, parent.nr_avail_day_groups) ohne AvailDayGroupShow.model_validate().

    Ersetzt AvailDayGroup.get(id).avail_day_group in SetNewParent.execute() — 1 Roundtrip statt
    1 teures get() + rekursives model_validate.
    """
    with get_session() as session:
        parent_id = session.exec(
            select(models.AvailDayGroup.avail_day_group_id)
            .where(models.AvailDayGroup.id == avail_day_group_id)
        ).one_or_none()
        if parent_id is None:
            return None, None
        parent_nr = session.exec(
            select(models.AvailDayGroup.nr_avail_day_groups)
            .where(models.AvailDayGroup.id == parent_id)
        ).one_or_none()
        return parent_id, parent_nr


def count_children(avail_day_group_id: UUID) -> int:
    """Gibt die Anzahl direkter Kinder zurück ohne Objekte zu laden.

    Ersetzt len(get_child_groups_from__parent_group(id)) — 1 COUNT-Query statt N model_validate.
    """
    from sqlalchemy import func
    with get_session() as session:
        return session.exec(
            select(func.count()).where(models.AvailDayGroup.avail_day_group_id == avail_day_group_id)
        ).one()


def set_new_parent_batch(
        moves: list[tuple[UUID, UUID]],
) -> tuple[list[tuple[UUID | None, int | None]], dict[UUID, int]]:
    """Führt N Parent-Verschiebungen in einer einzigen Session durch.

    Bulk-lädt alle Kinder + alten Parents in je einer IN-Query statt N einzelnen
    session.get()-Calls — eliminiert den O(N)-Session-Overhead.

    Args:
        moves: [(child_avail_day_group_id, new_parent_id), ...]

    Returns:
        old_parent_infos: [(old_parent_id, old_parent_nr_avail_day_groups), ...] — parallel zu moves
        nr_resets:         {old_parent_id: saved_nr_avail_day_groups} — für Undo
    """
    from sqlalchemy import func

    child_ids = [child_id for child_id, _ in moves]
    new_parent_ids = {new_id for _, new_id in moves}

    with get_session() as session:
        # ── Bulk-Load: alle zu verschiebenden Kinder ──────────────────────────
        children_list = session.exec(
            select(models.AvailDayGroup).where(models.AvailDayGroup.id.in_(child_ids))
        ).all()
        child_map: dict[UUID, models.AvailDayGroup] = {c.id: c for c in children_list}

        # ── Bulk-Load: alle alten Parents ─────────────────────────────────────
        old_parent_ids: set[UUID] = {
            c.avail_day_group_id for c in child_map.values() if c.avail_day_group_id
        }
        if old_parent_ids:
            old_parents_list = session.exec(
                select(models.AvailDayGroup).where(models.AvailDayGroup.id.in_(old_parent_ids))
            ).all()
            _ = old_parents_list

        # ── Bulk-Load: neue Parents (sofern noch nicht in Identity-Map) ───────
        missing_new = new_parent_ids - old_parent_ids
        if missing_new:
            session.exec(
                select(models.AvailDayGroup).where(models.AvailDayGroup.id.in_(missing_new))
            ).all()

        # ── Alle Moves durchführen (Identity-Map → kein DB-Call) ──────────────
        old_parent_infos: list[tuple[UUID | None, int | None]] = []
        for child_id, new_parent_id in moves:
            child = child_map.get(child_id)
            if child is None:
                old_parent_infos.append((None, None))
                continue
            old_parent_id = child.avail_day_group_id
            old_parent = session.get(models.AvailDayGroup, old_parent_id) if old_parent_id else None
            old_parent_nr = old_parent.nr_avail_day_groups if old_parent else None
            child.avail_day_group = session.get(models.AvailDayGroup, new_parent_id)
            old_parent_infos.append((old_parent_id, old_parent_nr))

        session.flush()

        # ── nr_avail_day_groups-Konsistenz nach Move ──────────────────────────
        nr_resets: dict[UUID, int] = {}
        for (_, _), (old_parent_id, old_parent_nr) in zip(moves, old_parent_infos):
            if not (old_parent_id and old_parent_nr and old_parent_id not in nr_resets):
                continue
            remaining = session.exec(
                select(func.count()).where(models.AvailDayGroup.avail_day_group_id == old_parent_id)
            ).one()
            if old_parent_nr > remaining:
                parent_obj = session.get(models.AvailDayGroup, old_parent_id)
                parent_obj.nr_avail_day_groups = None
                nr_resets[old_parent_id] = old_parent_nr

        if nr_resets:
            session.flush()

        return old_parent_infos, nr_resets


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


def set_new_parent(avail_day_group_id: UUID, new_parent_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        adg.avail_day_group = session.get(models.AvailDayGroup, new_parent_id)
        session.flush()


def delete(avail_day_group_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.AvailDayGroup, avail_day_group_id))