"""Command-Klassen für Event (Veranstaltungstermin).

Verwaltet alle Änderungen an Events: Erstellen (legt automatisch EventGroup und
CastGroup an), Löschen (bereinigt beide), Datum-/Tageszeit-Änderungen, Notizen,
Flags und SkillGroups.

`Delete` speichert die komplette Event-Instanz, da beim Undo ein neues Event mit
denselben Daten neu erstellt werden muss (EventGroup und CastGroup werden separat
gelöscht und können nicht direkt wiederhergestellt werden).
"""
import datetime
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import event as api_event


class Create(Command):
    def __init__(self, event: schemas.EventCreate):
        super().__init__()
        self.event = event.model_copy()
        self.created_event: schemas.EventShow | None = None

    def execute(self):
        self.created_event = api_event.create(
            date=self.event.date,
            location_plan_period_id=self.event.location_plan_period.id,
            time_of_day_id=self.event.time_of_day.id,
        )

    def _undo(self):
        api_event.delete(self.created_event.id)

    def _redo(self):
        self.created_event = api_event.create(
            date=self.event.date,
            location_plan_period_id=self.event.location_plan_period.id,
            time_of_day_id=self.event.time_of_day.id,
        )


class CreateBulk(Command):
    """Erstellt mehrere Events in einem HTTP-Roundtrip.

    Reihenfolge der `created_events` entspricht der `events`-Eingabe — Caller
    duerfen darauf re-distributen (z.B. zurueck in Rule-Buckets).
    """

    def __init__(self, events: list[schemas.EventCreate]):
        super().__init__()
        self.items: list[tuple[UUID, datetime.date, UUID]] = [
            (e.location_plan_period.id, e.date, e.time_of_day.id) for e in events
        ]
        self.created_events: list[schemas.EventShow] = []

    def execute(self):
        self.created_events = api_event.create_bulk(self.items)

    def _undo(self):
        api_event.delete_bulk([e.id for e in self.created_events])

    def _redo(self):
        self.created_events = api_event.create_bulk(self.items)


class UpdateTimeOfDay(Command):
    def __init__(self, event: schemas.Event, new_time_of_day_id: UUID):
        super().__init__()
        self.event = event
        self.old_time_of_day_id = self.event.time_of_day.id
        self.new_time_of_day_id = new_time_of_day_id

    def execute(self):
        api_event.update_time_of_day_and_date(self.event.id, self.new_time_of_day_id)

    def _undo(self):
        api_event.update_time_of_day_and_date(self.event.id, self.old_time_of_day_id)

    def _redo(self):
        api_event.update_time_of_day_and_date(self.event.id, self.new_time_of_day_id)


class UpdateTimeOfDays(Command):
    def __init__(self, event_id: UUID, time_of_days: list[schemas.TimeOfDay]):
        super().__init__()
        self.event_id = event_id
        self.new_time_of_days = time_of_days
        self.old_time_of_days = db_services.TimeOfDay.get_time_of_days_from__event(event_id)

    def execute(self):
        api_event.update_time_of_days(self.event_id, self.new_time_of_days)

    def _undo(self):
        # Vorher-Bug: rief db_services.AvailDay.update_time_of_days auf
        # (falsches Service). Bei Migration gefixt auf api_event.
        api_event.update_time_of_days(self.event_id, self.old_time_of_days)

    def _redo(self):
        api_event.update_time_of_days(self.event_id, self.new_time_of_days)


class UpdateDateTimeOfDay(Command):
    def __init__(self, event: schemas.Event, new_date: datetime.date, new_time_of_day_id: UUID):
        super().__init__()
        self.event = event
        self.new_date = new_date
        self.new_time_of_day_id = new_time_of_day_id
    def execute(self):
        api_event.update_time_of_day_and_date(
            self.event.id, self.new_time_of_day_id, self.new_date)

    def _undo(self):
        api_event.update_time_of_day_and_date(
            self.event.id, self.event.time_of_day.id, self.event.date)

    def _redo(self):
        api_event.update_time_of_day_and_date(
            self.event.id, self.new_time_of_day_id, self.new_date)


class UpdateNotes(Command):
    def __init__(self, event: schemas.EventShow, notes: str):
        super().__init__()
        self.event = event
        self.notes = notes

    def execute(self):
        api_event.update_notes(self.event.id, self.notes)

    def _undo(self):
        api_event.update_notes(self.event.id, self.event.notes)

    def _redo(self):
        api_event.update_notes(self.event.id, self.notes)


class Delete(Command):
    def __init__(self, event_id):
        super().__init__()
        self.event_id = event_id
        self.event_to_delete = db_services.Event.get(event_id)
        self.containing_cast_groups = db_services.CastGroup.get(self.event_to_delete.cast_group.id).parent_groups

    def execute(self):
        api_event.delete(self.event_id)

    def _undo(self):
        # Vorher-Bug: self.event_id = Event.create(event_to_delete) (EventShow
        # als UUID gespeichert). Bei Migration gefixt — nimmt jetzt .id.
        recreated = api_event.create(
            date=self.event_to_delete.date,
            location_plan_period_id=self.event_to_delete.location_plan_period.id,
            time_of_day_id=self.event_to_delete.time_of_day.id,
        )
        self.event_id = recreated.id

    def _redo(self):
        api_event.delete(self.event_id)


class DeleteBulk(Command):
    """Hard-Delete fuer mehrere Events in einem HTTP-Roundtrip.

    Undo erzeugt frische Events mit denselben (date, lpp, time_of_day) — jedoch
    neuen UUIDs und frischen EventGroup/CastGroup. Wenn Events vor dem Delete
    in eine Parent-CastGroup-Struktur verschachtelt waren, kommt diese
    Verschachtelung beim Undo NICHT zurueck (identisches Verhalten wie
    Single-:class:`Delete`). Fuer den
    ``make_events_from_planning_rules``-Pfad bewusst akzeptiert, weil der User
    die Struktur ohnehin per neuem Run regeneriert.
    """

    def __init__(self, events: list[schemas.EventShow]):
        super().__init__()
        # Daten fuer Undo VOR dem Delete sichern; spaeter sind die DB-Rows weg.
        self.undo_items: list[tuple[UUID, datetime.date, UUID]] = [
            (e.location_plan_period.id, e.date, e.time_of_day.id) for e in events
        ]
        self.event_ids: list[UUID] = [e.id for e in events]

    def execute(self):
        api_event.delete_bulk(self.event_ids)

    def _undo(self):
        recreated = api_event.create_bulk(self.undo_items)
        # Neue UUIDs fuer evtl. Redo merken.
        self.event_ids = [e.id for e in recreated]

    def _redo(self):
        api_event.delete_bulk(self.event_ids)


class PutInFlag(Command):
    def __init__(self, event_id: UUID, flag_id: UUID):
        super().__init__()
        self.event_id = event_id
        self.flag_id = flag_id

    def execute(self):
        api_event.put_in_flag(self.event_id, self.flag_id)

    def _undo(self):
        api_event.remove_flag(self.event_id, self.flag_id)

    def _redo(self):
        api_event.put_in_flag(self.event_id, self.flag_id)


class RemoveFlag(Command):
    def __init__(self, event_id: UUID, flag_id: UUID):
        super().__init__()
        self.event_id = event_id
        self.flag_id = flag_id

    def execute(self):
        api_event.remove_flag(self.event_id, self.flag_id)

    def _undo(self):
        api_event.put_in_flag(self.event_id, self.flag_id)

    def _redo(self):
        api_event.remove_flag(self.event_id, self.flag_id)


class AddSkillGroup(Command):
    def __init__(self, event_id: UUID, skill_group_id: UUID):
        super().__init__()
        self.event_id = event_id
        self.skill_group_id = skill_group_id
        self.event: schemas.EventShow | None = None

    def execute(self):
        self.event = api_event.add_skill_group(self.event_id, self.skill_group_id)

    def _undo(self):
        self.event = api_event.remove_skill_group(self.event_id, self.skill_group_id)

    def _redo(self):
        self.event = api_event.add_skill_group(self.event_id, self.skill_group_id)

class RemoveSkillGroup(Command):
    def __init__(self, event_id: UUID, skill_group_id: UUID):
        super().__init__()
        self.event_id = event_id
        self.skill_group_id = skill_group_id
        self.event: schemas.EventShow | None = None

    def execute(self):
        self.event = api_event.remove_skill_group(self.event_id, self.skill_group_id)

    def _undo(self):
        self.event = api_event.add_skill_group(self.event_id, self.skill_group_id)

    def _redo(self):
        self.event = api_event.remove_skill_group(self.event_id, self.skill_group_id)
