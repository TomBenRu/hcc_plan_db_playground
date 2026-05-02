"""Service-Schicht fuer die Notification-Groups-Verwaltungs-View.

Aggregiert Group-Daten + zugeordnete PlanPerioden + NotificationLog-
Statistik in einem View-Modell, das die Templates direkt rendern. Der
Datenzugriff laeuft ueber die injected Request-Session — Mutations sind
in Phase E in dieser Datei verankert.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import select as sa_select
from sqlalchemy.orm import selectinload
from sqlmodel import Session

from database.models import (
    NotificationGroup,
    NotificationLog,
    PlanPeriod,
)


# ── View-Dataclasses ───────────────────────────────────────────────────────


@dataclass
class PlanPeriodInGroup:
    """Schlanker PP-View fuer die NG-Card — nur Felder, die das Template
    rendert (Datum, Status, Drag-Item-Daten)."""

    id: uuid.UUID
    start: datetime.date
    end: datetime.date
    closed: bool
    is_softdel: bool


@dataclass
class ReminderKindStat:
    """Aggregat pro Reminder-Stufe (t7/t3/t1/catchup) fuer die Inline-
    Versand-Historie auf der Group-Card."""

    kind: str
    success_count: int = 0
    failed_count: int = 0
    last_sent: datetime.datetime | None = None


@dataclass
class NotificationGroupView:
    id: uuid.UUID
    deadline: datetime.date
    name: str | None
    plan_periods: list[PlanPeriodInGroup] = field(default_factory=list)
    stats: dict[str, ReminderKindStat] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        if not self.plan_periods:
            return "Leere Group"
        n = len(self.plan_periods)
        return f"{n} Periode{'n' if n != 1 else ''}"

    @property
    def days_until_deadline(self) -> int:
        return (self.deadline - datetime.date.today()).days


# ── Lese-Funktionen ────────────────────────────────────────────────────────


_REMINDER_KINDS: tuple[str, ...] = ("t7", "t3", "t1", "catchup")


def _aggregate_logs(logs: Sequence[NotificationLog]) -> dict[str, ReminderKindStat]:
    """Pro `kind` Erfolg+Fehler+letzter Versand aufbauen. Stufen ohne
    Eintraege bekommen einen leeren Default-Stat fuer konsistentes Rendering."""
    stats: dict[str, ReminderKindStat] = {
        kind: ReminderKindStat(kind=kind) for kind in _REMINDER_KINDS
    }
    for log in logs:
        stat = stats.setdefault(log.kind, ReminderKindStat(kind=log.kind))
        if log.success:
            stat.success_count += 1
        else:
            stat.failed_count += 1
        if stat.last_sent is None or log.sent_at > stat.last_sent:
            stat.last_sent = log.sent_at
    return stats


def list_groups_for_team(
    session: Session, team_id: uuid.UUID,
) -> list[NotificationGroupView]:
    """Alle NotificationGroups eines Teams + zugeordnete (non-deleted) PPs
    + aggregierte NotificationLog-Statistik. Sortierung: Deadline absteigend
    (juengste zuerst — relevant fuer den Dispatcher)."""
    stmt = (
        sa_select(NotificationGroup)
        .where(NotificationGroup.team_id == team_id)
        .options(
            selectinload(NotificationGroup.plan_periods),
            selectinload(NotificationGroup.notification_logs),
        )
        .order_by(NotificationGroup.deadline.desc())
    )
    groups = session.execute(stmt).scalars().all()

    views: list[NotificationGroupView] = []
    for group in groups:
        pp_views = [
            PlanPeriodInGroup(
                id=pp.id,
                start=pp.start,
                end=pp.end,
                closed=pp.closed,
                is_softdel=pp.prep_delete is not None,
            )
            for pp in sorted(group.plan_periods, key=lambda p: p.start)
            if pp.prep_delete is None  # Papierkorb-PPs ausblenden in der NG-View
        ]
        views.append(
            NotificationGroupView(
                id=group.id,
                deadline=group.deadline,
                name=group.name,
                plan_periods=pp_views,
                stats=_aggregate_logs(group.notification_logs),
            )
        )
    return views


def list_orphan_pps(session: Session, team_id: uuid.UUID) -> list[PlanPeriodInGroup]:
    """PPs des Teams ohne Reminder-Group ("Ohne Reminder"-Sektion).

    Filtert soft-deleted PPs aus — die haben in dieser View nichts verloren.
    Sortierung: Start aufsteigend (chronologisch, weil das die natuerliche
    Lese-Reihenfolge fuer "kommende Perioden" ist).
    """
    stmt = (
        sa_select(PlanPeriod)
        .where(PlanPeriod.team_id == team_id)
        .where(PlanPeriod.notification_group_id.is_(None))
        .where(PlanPeriod.prep_delete.is_(None))
        .order_by(PlanPeriod.start.asc())
    )
    pps = session.execute(stmt).scalars().all()
    return [
        PlanPeriodInGroup(
            id=pp.id, start=pp.start, end=pp.end,
            closed=pp.closed, is_softdel=False,
        )
        for pp in pps
    ]
