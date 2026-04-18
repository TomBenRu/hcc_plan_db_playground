"""Command-Klassen für TeamLocationAssign (Standort-Team-Zuweisung).

Analoges Pendant zu `team_actor_assignment_commands` für Standorte statt Personen.
Wird intern von `location_of_work_commands.AssignToTeam` und `LeaveTeam` über
`ContrExecUndoRedo` als atomare Unter-Commands verwendet.

- `Create`: Erstellt eine Standort-Zuweisung; Undo löscht hart.
- `ChangeEndDate`: Setzt Enddatum (oder `None`); speichert Vorher-Wert.
- `Delete`: Löscht hart; Undo re-erstellt mit der Original-ID.
"""
import datetime
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import team_location_assign as api_tla


class Create(Command):
    def __init__(self, location_id, team_id, start: datetime.date):
        super().__init__()
        self.start = start
        self.location = db_services.LocationOfWork.get(location_id)
        self.team = db_services.Team.get(team_id)
        self.created_team_loc_assign: schemas.TeamLocationAssignShow | None = None

    def execute(self):
        self.created_team_loc_assign = api_tla.create(
            location_of_work_id=self.location.id, team_id=self.team.id, start=self.start,
        )

    def _undo(self):
        api_tla.delete(self.created_team_loc_assign.id)

    def _redo(self):
        self.execute()


class ChangeEndDate(Command):
    def __init__(self, assignment_id: UUID, end_date: datetime.date | None):
        super().__init__()
        self.assignment_id = assignment_id
        self.end_date = end_date
        self.old_end_date = db_services.TeamLocationAssign.get(assignment_id).end

    def execute(self):
        api_tla.set_end_date(self.assignment_id, self.end_date)

    def _undo(self):
        api_tla.set_end_date(self.assignment_id, self.old_end_date)

    def _redo(self):
        self.execute()

class Delete(Command):
    def __init__(self, assignment_id: UUID):
        super().__init__()
        self.assignment_id = assignment_id
        self.assignment = db_services.TeamLocationAssign.get(assignment_id)


    def execute(self):
        api_tla.delete(self.assignment_id)

    def _undo(self):
        api_tla.create(
            location_of_work_id=self.assignment.location_of_work.id,
            team_id=self.assignment.team.id,
            start=self.assignment.start, end=self.assignment.end,
            assign_id=self.assignment_id,
        )

    def _redo(self):
        self.execute()
