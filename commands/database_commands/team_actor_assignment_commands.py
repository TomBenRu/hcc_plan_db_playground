"""Command-Klassen für TeamActorAssign (Akteur-Team-Zuweisung).

Primitive Bausteine für Zuordnungsoperationen, die von `person_commands.AssignToTeam`,
`AddToTeam` und `RemoveFromTeam` intern über `ContrExecUndoRedo` orchestriert werden.

- `Create`: Erstellt eine Zuweisung; Undo löscht hart.
- `ChangeEndDate`: Setzt das Enddatum (auch `None` für unbegrenzt); speichert Vorher-Wert.
- `Delete`: Löscht hart; Undo re-erstellt mit der Original-ID.
"""
import datetime
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import team_actor_assign as api_taa


class Create(Command):
    def __init__(self, person_id, team_id, start: datetime.date):
        super().__init__()
        self.start = start
        self.person = db_services.Person.get(person_id)
        self.team = db_services.Team.get(team_id)
        self.created_team_actor_assign: schemas.TeamActorAssignShow | None = None

    def execute(self):
        self.created_team_actor_assign = api_taa.create(
            person_id=self.person.id, team_id=self.team.id, start=self.start,
        )

    def _undo(self):
        api_taa.delete(self.created_team_actor_assign.id)

    def _redo(self):
        self.execute()


class ChangeEndDate(Command):
    def __init__(self, assignment_id: UUID, end_date: datetime.date | None):
        super().__init__()
        self.assignment_id = assignment_id
        self.end_date = end_date
        self.old_end_date = db_services.TeamActorAssign.get(assignment_id).end

    def execute(self):
        api_taa.set_end_date(self.assignment_id, self.end_date)

    def _undo(self):
        api_taa.set_end_date(self.assignment_id, self.old_end_date)

    def _redo(self):
        self.execute()

class Delete(Command):
    def __init__(self, assignment_id: UUID):
        super().__init__()
        self.assignment_id = assignment_id
        self.assignment = db_services.TeamActorAssign.get(assignment_id)


    def execute(self):
        api_taa.delete(self.assignment_id)

    def _undo(self):
        api_taa.create(
            person_id=self.assignment.person.id, team_id=self.assignment.team.id,
            start=self.assignment.start, end=self.assignment.end,
            assign_id=self.assignment_id,
        )

    def _redo(self):
        self.execute()