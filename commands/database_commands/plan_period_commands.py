"""Command-Klassen für PlanPeriod (Planungszeitraum).

Enthält:
- `Create`: Legacy — Soft-Delete-Zyklus für leere PlanPeriod ohne Kinder.
- `CreateWithChildren`: Atomarer Create inkl. LPP/APP/Master-Groups (1 API-Call
  statt 1+2N+2M); ersetzt die alte Schleife in `DlgPlanPeriodCreate.accept()`.
- `Delete`: Soft-Delete-Zyklus.
- `Update`: Ändert Zeitraum, Deadline und Notizen; beim Service-Aufruf werden
  automatisch AvailDays und Events außerhalb des neuen Zeitraums soft-gelöscht
  und innerhalb der neuen Range reaktiviert; bei Vergrößerung werden fehlende
  LPP/APP für hinzugekommene Team-Mitglieder nachgezogen.
- `UpdateNotes`: Isoliertes Command für reine Notizänderungen.
"""
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import plan_period as api_plan_period


class Create(Command):
    def __init__(self, plan_period: schemas.PlanPeriodCreate):
        super().__init__()
        self.plan_period = plan_period
        self.created_plan_period: schemas.PlanPeriodShow | None = None

    def execute(self):
        self.created_plan_period = api_plan_period.create(
            start=self.plan_period.start, end=self.plan_period.end,
            team_id=self.plan_period.team.id,
            notes=self.plan_period.notes,
            notes_for_employees=self.plan_period.notes_for_employees,
        )

    def _undo(self):
        api_plan_period.delete(self.created_plan_period.id)

    def _redo(self):
        api_plan_period.undelete(self.created_plan_period.id)


class CreateWithChildren(Command):
    """Atomarer Create-Command — ein einziger API-Call legt PlanPeriod plus
    alle LocationPlanPeriods, ActorPlanPeriods und Master-Groups in einer
    Server-Transaktion an.

    Ersetzt die alte 1+2N+2M-Schleife in `DlgPlanPeriodCreate.accept()`.
    Undo soft-deletet die PlanPeriod (Kinder bleiben FK-bezogen erhalten);
    Redo macht den Soft-Delete rückgängig.
    """
    def __init__(self, plan_period: schemas.PlanPeriodCreate):
        super().__init__()
        self.plan_period = plan_period
        self.created_plan_period: schemas.PlanPeriodShow | None = None

    def execute(self):
        self.created_plan_period = api_plan_period.create_with_children(
            start=self.plan_period.start, end=self.plan_period.end,
            team_id=self.plan_period.team.id,
            notes=self.plan_period.notes,
            notes_for_employees=self.plan_period.notes_for_employees,
        )

    def _undo(self):
        api_plan_period.delete(self.created_plan_period.id)

    def _redo(self):
        api_plan_period.undelete(self.created_plan_period.id)


class Delete(Command):
    def __init__(self, plan_period_id: UUID):
        super().__init__()
        self.plan_period_id = plan_period_id

    def execute(self):
        api_plan_period.delete(self.plan_period_id)

    def _undo(self):
        api_plan_period.undelete(self.plan_period_id)

    def _redo(self):
        api_plan_period.delete(self.plan_period_id)


class Update(Command):
    def __init__(self, plan_period: schemas.PlanPeriod):
        super().__init__()
        self.plan_period = plan_period
        self.plan_period_old = db_services.PlanPeriod.get(plan_period.id)

    def execute(self):
        api_plan_period.update(self.plan_period)

    def _undo(self):
        api_plan_period.update(self.plan_period_old)

    def _redo(self):
        api_plan_period.update(self.plan_period)


class UpdateNotes(Command):
    def __init__(self, plan_period_id, notes: str):
        super().__init__()
        self.plan_period_id = plan_period_id
        self.plan_period = db_services.PlanPeriod.get(plan_period_id)
        self.updated_plan_period: schemas.PlanPeriodShow | None = None
        self.notes = notes

    def execute(self):
        self.updated_plan_period = api_plan_period.update_notes(self.plan_period_id, self.notes)

    def _undo(self):
        api_plan_period.update_notes(self.plan_period_id, self.plan_period.notes)

    def _redo(self):
        api_plan_period.update_notes(self.plan_period_id, self.notes)
