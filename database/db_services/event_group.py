"""Service-Funktionen für EventGroup (Veranstaltungsgruppen-Baum).

EventGroups bilden wie AvailDayGroups eine Baumstruktur. Jeder Blattknoten
referenziert ein einzelnes Event; interne Knoten steuern über `nr_event_groups`
und `variation_weight`, wie viele Events aus der Gruppe geplant werden müssen.
Der Master-Knoten gehört zur LocationPlanPeriod.
"""
import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import event_group_dialog_options


def _build_tree_nodes_from_ids(adg_ids: list[UUID], session) -> dict[UUID, schemas.EventGroupTreeNode]:
    """Baut EventGroupTreeNode-Dicts aus EventGroup-IDs mit minimalem SQL (3 Queries).

    Der FK event_group_id liegt auf der Event-Seite, deshalb 3 separate Queries:
    1. EventGroup-Skalare (id, variation_weight, nr_event_groups, location_plan_period_id)
    2. Event.id WHERE event_group_id IN (...) → event_id pro Node
    3. Kinder-IDs WHERE event_group_id IN (...)
    Kein ORM-Mapping auf Relationships, kein Pydantic model_validate.
    """
    if not adg_ids:
        return {}
    # Query 1: EventGroup-Skalare
    rows = session.exec(
        select(models.EventGroup.id,
               models.EventGroup.variation_weight,
               models.EventGroup.nr_event_groups,
               models.EventGroup.location_plan_period_id)
        .where(models.EventGroup.id.in_(adg_ids))
    ).all()
    nodes: dict[UUID, schemas.EventGroupTreeNode] = {
        row.id: schemas.EventGroupTreeNode(
            id=row.id,
            variation_weight=row.variation_weight or 1,
            nr_event_groups=row.nr_event_groups,
            location_plan_period_id=row.location_plan_period_id,
        )
        for row in rows
    }
    # Query 2: Event-IDs (FK liegt auf Event-Seite)
    event_rows = session.exec(
        select(models.Event.id, models.Event.event_group_id)
        .where(models.Event.event_group_id.in_(adg_ids))
    ).all()
    for event_row in event_rows:
        node = nodes.get(event_row.event_group_id)
        if node is not None:
            node.event_id = event_row.id
    # Query 3: Kinder-IDs (event_group_id FK = Parent-ID)
    child_rows = session.exec(
        select(models.EventGroup.id, models.EventGroup.event_group_id)
        .where(models.EventGroup.event_group_id.in_(adg_ids))
    ).all()
    for child_row in child_rows:
        parent_node = nodes.get(child_row.event_group_id)
        if parent_node is not None:
            parent_node.child_ids.append(child_row.id)
    return nodes


def get_batch_for_tree(event_group_ids: list[UUID]) -> dict[UUID, schemas.EventGroupTreeNode]:
    """Lädt mehrere EventGroups als leichtgewichtige TreeNodes für den EventGroupTree.

    Ersetzt get_batch() (20 Eager-Loading-Optionen + EventGroupShow.model_validate) durch
    direkten Scalar-SELECT ohne Pydantic-Relationen. 3 SQL-Queries statt komplexer JOINs.
    """
    if not event_group_ids:
        return {}
    with get_session() as session:
        return _build_tree_nodes_from_ids(event_group_ids, session)


def get_batch_masters_for_tree(location_plan_period_ids: list[UUID]) -> dict[UUID, schemas.EventGroupTreeNode]:
    """Lädt Master-EventGroupTreeNodes für mehrere LocationPlanPeriods.

    Ersetzt get_batch_masters_from__location_plan_periods() (EventGroupShow) durch
    direkten Scalar-SELECT (3 Queries). Rückgabe: location_plan_period_id → EventGroupTreeNode.
    """
    if not location_plan_period_ids:
        return {}
    with get_session() as session:
        # Query 1: Master-Skalare (WHERE location_plan_period_id IN ...)
        master_rows = session.exec(
            select(models.EventGroup.id,
                   models.EventGroup.variation_weight,
                   models.EventGroup.nr_event_groups,
                   models.EventGroup.location_plan_period_id)
            .where(models.EventGroup.location_plan_period_id.in_(location_plan_period_ids))
        ).all()
        nodes_by_lpp: dict[UUID, schemas.EventGroupTreeNode] = {
            row.location_plan_period_id: schemas.EventGroupTreeNode(
                id=row.id,
                variation_weight=row.variation_weight or 1,
                nr_event_groups=row.nr_event_groups,
                location_plan_period_id=row.location_plan_period_id,
            )
            for row in master_rows
        }
        master_ids = [n.id for n in nodes_by_lpp.values()]
        if not master_ids:
            return nodes_by_lpp
        # Query 2: Event-IDs (Masters sind Root-Nodes ohne Event, aber sicherheitshalber)
        event_rows = session.exec(
            select(models.Event.id, models.Event.event_group_id)
            .where(models.Event.event_group_id.in_(master_ids))
        ).all()
        master_by_id = {n.id: n for n in nodes_by_lpp.values()}
        for event_row in event_rows:
            node = master_by_id.get(event_row.event_group_id)
            if node is not None:
                node.event_id = event_row.id
        # Query 3: Kinder-IDs für alle Master
        child_rows = session.exec(
            select(models.EventGroup.id, models.EventGroup.event_group_id)
            .where(models.EventGroup.event_group_id.in_(master_ids))
        ).all()
        for child_row in child_rows:
            parent_node = master_by_id.get(child_row.event_group_id)
            if parent_node is not None:
                parent_node.child_ids.append(child_row.id)
        return nodes_by_lpp


def get_flat_tree_for_dialog__location_plan_period(
        location_plan_period_id: UUID,
) -> tuple[schemas.EventGroupForDialog | None, dict[UUID, list[schemas.EventGroupForDialog]]]:
    """Lädt den gesamten EventGroup-Baum einer LPP für den Dialog in 2 Roundtrips.

    Ersetzt N× get_child_groups_from__parent_group() in setup_tree() + sortByColumn()
    durch:
      1. Rekursiver CTE → alle (id, event_group_id) des Baums (1 Roundtrip)
      2. Batch-SELECT aller EventGroups mit event_group_dialog_options() (1 Roundtrip)

    Gibt EventGroupForDialog zurück (kein event_groups-Feld, nur EventForDialogTree
    als event-Objekt) — eliminiert die rekursive Pydantic-Validierung der Kinder.

    Returns:
        (master_group, {parent_event_group_id: [child EventGroupForDialogs]})
    """
    with get_session() as session:
        # ── Schritt 1: alle IDs + Parent-IDs via rekursivem CTE ─────────────
        base = (
            select(models.EventGroup.id, models.EventGroup.event_group_id)
            .where(models.EventGroup.location_plan_period_id == location_plan_period_id)
            .cte(name='eg_tree', recursive=True)
        )
        recursive = (
            select(models.EventGroup.id, models.EventGroup.event_group_id)
            .join(base, models.EventGroup.event_group_id == base.c.id)
        )
        cte = base.union_all(recursive)
        id_rows = session.exec(select(cte.c.id, cte.c.event_group_id)).all()

        if not id_rows:
            return None, {}

        all_ids = [row[0] for row in id_rows]
        id__parent_id: dict[UUID, UUID | None] = {row[0]: row[1] for row in id_rows}

        # ── Schritt 2: Batch-Load mit minimalen Dialog-Optionen ─────────────
        stmt = (
            select(models.EventGroup)
            .where(models.EventGroup.id.in_(all_ids))
            .options(*event_group_dialog_options())
        )
        all_egs = session.exec(stmt).unique().all()

        id__eg: dict[UUID, schemas.EventGroupForDialog] = {
            eg.id: schemas.EventGroupForDialog.model_validate(eg)
            for eg in all_egs
        }

        # ── Schritt 3: Parent→Children-Dict aufbauen (in-memory) ────────────
        parent__children: dict[UUID, list[schemas.EventGroupForDialog]] = {}
        master: schemas.EventGroupForDialog | None = None

        for eg_id, parent_id in id__parent_id.items():
            eg = id__eg.get(eg_id)
            if eg is None:
                continue
            if parent_id is None:
                master = eg
            else:
                parent__children.setdefault(parent_id, []).append(eg)

        return master, parent__children


def get(event_group_id: UUID) -> schemas.EventGroupShow:
    with get_session() as session:
        return schemas.EventGroupShow.model_validate(session.get(models.EventGroup, event_group_id))


def _event_group_show_options():
    """Vollständige Eager-Loading-Optionen für EventGroupShow.model_validate() ohne Lazy-Loads.

    EventGroupShow traversiert beim model_validate() folgende Chains (3 Ebenen tief):
    - event → time_of_day → time_of_day_enum
    - event → location_plan_period → plan_period → team
    - event → flags
    - location_plan_period → plan_period → team  (Root-Nodes)
    - event_group (Parent-Referenz, Ebene 1)
      ↳ .location_plan_period → plan_period → team
      ↳ .event → time_of_day → time_of_day_enum
      ↳ .event → location_plan_period → plan_period → team
      ↳ .event → flags
      ↳ .event_group (Großeltern, Ebene 2)
           ↳ .location_plan_period → plan_period → team
           ↳ .event_group (Ebene 3, = NULL für Root → kein Lazy-Load mehr)
    Kinder (event_groups): Selbe Chains über Sub-Optionen von selectinload.
    """
    from sqlalchemy.orm import selectinload, joinedload
    return [
        # ── Kinder (selectinload + alle Sub-Chains) ──────────────────────────
        selectinload(models.EventGroup.event_groups)
        .joinedload(models.EventGroup.location_plan_period)
        .joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team),
        selectinload(models.EventGroup.event_groups)
        .joinedload(models.EventGroup.event)
        .joinedload(models.Event.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum),
        selectinload(models.EventGroup.event_groups)
        .joinedload(models.EventGroup.event)
        .joinedload(models.Event.location_plan_period)
        .joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team),
        selectinload(models.EventGroup.event_groups)
        .joinedload(models.EventGroup.event)
        .selectinload(models.Event.flags),
        # ── Haupt-Node: event-Chain ───────────────────────────────────────────
        joinedload(models.EventGroup.event)
        .joinedload(models.Event.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum),
        joinedload(models.EventGroup.event)
        .joinedload(models.Event.location_plan_period)
        .joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team),
        joinedload(models.EventGroup.event)
        .selectinload(models.Event.flags),
        # ── Haupt-Node: location_plan_period (Root-Nodes) ────────────────────
        joinedload(models.EventGroup.location_plan_period)
        .joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team),
        # ── Haupt-Node: event_group Ebene 1 (Parent) mit Sub-Chains ──────────
        joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.location_plan_period)
        .joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team),
        joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event)
        .joinedload(models.Event.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum),
        joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event)
        .joinedload(models.Event.location_plan_period)
        .joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team),
        joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event)
        .selectinload(models.Event.flags),
        # ── event_group Ebene 2 (Großeltern) mit Sub-Chains ──────────────────
        joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.location_plan_period)
        .joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team),
        joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event)
        .joinedload(models.Event.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum),
        joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event)
        .joinedload(models.Event.location_plan_period)
        .joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team),
        joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event)
        .selectinload(models.Event.flags),
        # ── event_group Ebene 3 (Root-Parent = NULL → verhindert Lazy-Load) ──
        joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event_group)
        .joinedload(models.EventGroup.event_group),
    ]


def get_batch(event_group_ids: list[UUID]) -> dict[UUID, schemas.EventGroupShow]:
    """Lädt mehrere EventGroups in einer Batch-Abfrage ohne Lazy-Loads.

    Ersetzt N einzelne get()-Aufrufe (N Sessions) durch eine einzige Query.
    Vollständiges Eager-Loading via _event_group_show_options().
    """
    if not event_group_ids:
        return {}
    with get_session() as session:
        stmt = (select(models.EventGroup)
                .where(models.EventGroup.id.in_(event_group_ids))
                .options(*_event_group_show_options()))
        groups = session.exec(stmt).unique().all()
        return {g.id: schemas.EventGroupShow.model_validate(g) for g in groups}


def get_master_from__location_plan_period(location_plan_period_id: UUID) -> schemas.EventGroupShow:
    """Lädt den Root-EventGroup einer LocationPlanPeriod mit vollständigem Eager-Loading."""
    with get_session() as session:
        stmt = (select(models.EventGroup)
                .where(models.EventGroup.location_plan_period_id == location_plan_period_id)
                .options(*_event_group_show_options()))
        eg = session.exec(stmt).first()
        return schemas.EventGroupShow.model_validate(eg)


def get_batch_masters_from__location_plan_periods(
        location_plan_period_ids: list[UUID]) -> dict[UUID, schemas.EventGroupShow]:
    """Lädt Root-EventGroups für mehrere LocationPlanPeriods in einer einzigen Batch-Abfrage.

    Ersetzt N× get_master_from__location_plan_period() (N Sessions) durch eine einzige Query.
    Verwendet WHERE location_plan_period_id IN (...) mit vollem Eager-Loading.

    Returns:
        Dict: location_plan_period_id → EventGroupShow
    """
    if not location_plan_period_ids:
        return {}
    with get_session() as session:
        stmt = (select(models.EventGroup)
                .where(models.EventGroup.location_plan_period_id.in_(location_plan_period_ids))
                .options(*_event_group_show_options()))
        groups = session.exec(stmt).unique().all()
        return {g.location_plan_period_id: schemas.EventGroupShow.model_validate(g)
                for g in groups}


def get_child_groups_from__parent_group(event_group_id) -> list[schemas.EventGroupShow]:
    with get_session() as session:
        eg = session.get(models.EventGroup, event_group_id)
        return [schemas.EventGroupShow.model_validate(e) for e in eg.event_groups]


def get_grand_parent_event_group_id_from_event(event_id: UUID) -> UUID | None:
    with get_session() as session:
        event = session.get(models.Event, event_id)
        return event.event_group.event_group.id if event.event_group.event_group else None


def create(*, location_plan_period_id: Optional[UUID] = None,
           event_group_id: Optional[UUID] = None, undo_group_id: UUID = None) -> schemas.EventGroupShow:
    log_function_info()
    with get_session() as session:
        kwargs = {}
        if location_plan_period_id:
            kwargs['location_plan_period'] = session.get(models.LocationPlanPeriod, location_plan_period_id)
        if event_group_id:
            kwargs['event_group'] = session.get(models.EventGroup, event_group_id)
        if undo_group_id:
            kwargs['id'] = undo_group_id
        eg = models.EventGroup(**kwargs)
        session.add(eg)
        session.flush()
        return schemas.EventGroupShow.model_validate(eg)


def update_nr_event_groups(event_group_id: UUID, nr_event_groups: int | None) -> schemas.EventGroupShow:
    log_function_info()
    with get_session() as session:
        eg = session.get(models.EventGroup, event_group_id)
        eg.nr_event_groups = nr_event_groups
        session.flush()
        return schemas.EventGroupShow.model_validate(eg)


def update_variation_weight(event_group_id: UUID, variation_weight: int) -> schemas.EventGroupShow:
    log_function_info()
    with get_session() as session:
        eg = session.get(models.EventGroup, event_group_id)
        eg.variation_weight = variation_weight
        session.flush()
        return schemas.EventGroupShow.model_validate(eg)


def set_new_parent_batch(
        moves: list[tuple[UUID, UUID]],
) -> tuple[list[tuple[UUID | None, int | None]], dict[UUID, int]]:
    """Führt N Parent-Verschiebungen in einer einzigen Session durch.

    Bulk-lädt alle Kinder + alten Parents in je einer IN-Query statt N einzelnen
    session.get()-Calls — eliminiert den O(N)-Session-Overhead.

    Args:
        moves: [(child_event_group_id, new_parent_id), ...]

    Returns:
        old_parent_infos: [(old_parent_id, old_parent_nr_event_groups), ...] — parallel zu moves
        nr_resets:         {old_parent_id: saved_nr_event_groups} — für Undo
    """
    from sqlalchemy import func

    child_ids = [child_id for child_id, _ in moves]
    new_parent_ids = {new_id for _, new_id in moves}

    with get_session() as session:
        # ── Bulk-Load: alle zu verschiebenden Kinder ──────────────────────────
        children_list = session.exec(
            select(models.EventGroup).where(models.EventGroup.id.in_(child_ids))
        ).all()
        child_map: dict[UUID, models.EventGroup] = {c.id: c for c in children_list}

        # ── Bulk-Load: alle alten Parents ─────────────────────────────────────
        old_parent_ids: set[UUID] = {
            c.event_group_id for c in child_map.values() if c.event_group_id
        }
        if old_parent_ids:
            old_parents_list = session.exec(
                select(models.EventGroup).where(models.EventGroup.id.in_(old_parent_ids))
            ).all()
            # bereits in Identity-Map — kein weiterer DB-Call für session.get() nötig
            _ = old_parents_list

        # ── Bulk-Load: neue Parents (sofern noch nicht in Identity-Map) ───────
        missing_new = new_parent_ids - old_parent_ids
        if missing_new:
            session.exec(
                select(models.EventGroup).where(models.EventGroup.id.in_(missing_new))
            ).all()

        # ── Alle Moves durchführen (Identity-Map → kein DB-Call) ──────────────
        old_parent_infos: list[tuple[UUID | None, int | None]] = []
        for child_id, new_parent_id in moves:
            child = child_map.get(child_id)
            if child is None:
                old_parent_infos.append((None, None))
                continue
            old_parent_id = child.event_group_id
            old_parent = session.get(models.EventGroup, old_parent_id) if old_parent_id else None
            old_parent_nr = old_parent.nr_event_groups if old_parent else None
            child.event_group = session.get(models.EventGroup, new_parent_id)
            old_parent_infos.append((old_parent_id, old_parent_nr))

        session.flush()

        # ── nr_event_groups-Konsistenz nach Move ──────────────────────────────
        nr_resets: dict[UUID, int] = {}
        for (_, _), (old_parent_id, old_parent_nr) in zip(moves, old_parent_infos):
            if not (old_parent_id and old_parent_nr and old_parent_id not in nr_resets):
                continue
            remaining = session.exec(
                select(func.count()).where(models.EventGroup.event_group_id == old_parent_id)
            ).one()
            if old_parent_nr > remaining:
                parent_obj = session.get(models.EventGroup, old_parent_id)
                parent_obj.nr_event_groups = None
                nr_resets[old_parent_id] = old_parent_nr

        if nr_resets:
            session.flush()

        return old_parent_infos, nr_resets


def get_parent_info(event_group_id: UUID) -> tuple[UUID | None, int | None]:
    """Gibt (parent_id, parent.nr_event_groups) ohne EventGroupShow.model_validate().

    Ersetzt EventGroup.get(id).event_group in SetNewParent.execute() — 1 Roundtrip statt
    1 teures get() + rekursives model_validate.
    """
    with get_session() as session:
        parent_id = session.exec(
            select(models.EventGroup.event_group_id)
            .where(models.EventGroup.id == event_group_id)
        ).one_or_none()
        if parent_id is None:
            return None, None
        parent_nr = session.exec(
            select(models.EventGroup.nr_event_groups)
            .where(models.EventGroup.id == parent_id)
        ).one_or_none()
        return parent_id, parent_nr


def count_children(event_group_id: UUID) -> int:
    """Gibt die Anzahl direkter Kinder zurück ohne Objekte zu laden.

    Ersetzt len(get_child_groups_from__parent_group(id)) — 1 COUNT-Query statt N model_validate.
    """
    from sqlalchemy import func
    with get_session() as session:
        return session.exec(
            select(func.count()).where(models.EventGroup.event_group_id == event_group_id)
        ).one()


def set_new_parent(event_group_id: UUID, new_parent_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        eg = session.get(models.EventGroup, event_group_id)
        eg.event_group = session.get(models.EventGroup, new_parent_id)
        session.flush()


def delete(event_group_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.EventGroup, event_group_id))