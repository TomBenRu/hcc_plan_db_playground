from uuid import UUID

from commands.command_base_classes import Command
from database import schemas, db_services


class Create(Command):
    def __init__(self, avail_day_group_id: UUID, num_avail_day_groups: int, location_of_work_ids: list[UUID]):
        self.avail_day_group_id = avail_day_group_id
        self.num_avail_day_groups = num_avail_day_groups
        self.location_of_work_ids = location_of_work_ids
        self.created_required_avail_day_groups: schemas.RequiredAvailDayGroupsShow | None = None

    def execute(self):
        self.created_required_avail_day_groups = db_services.RequiredAvailDayGroups.create(
            self.num_avail_day_groups, self.avail_day_group_id, self.location_of_work_ids)

    def undo(self):
        db_services.RequiredAvailDayGroups.delete(self.created_required_avail_day_groups.id)

    def redo(self):
        self.created_required_avail_day_groups = db_services.RequiredAvailDayGroups.create(
            self.num_avail_day_groups, self.avail_day_group_id,
            self.location_of_work_ids, self.created_required_avail_day_groups.id
        )


class Update(Command):
    def __init__(self, required_avail_day_group_id: UUID, num_avail_day_groups: int,
                 location_of_work_ids: list[UUID] | None):
        self.required_avail_day_group_id = required_avail_day_group_id
        self.required_avail_day_group = db_services.RequiredAvailDayGroups.get(required_avail_day_group_id)
        self.num_avail_day_groups = num_avail_day_groups
        self.location_of_work_ids = (location_of_work_ids if location_of_work_ids is not None
                                     else [l.id for l in self.required_avail_day_group.locations_of_work])
        self.updated_required_avail_day_groups: schemas.RequiredAvailDayGroups | None = None

    def execute(self):
        self.updated_required_avail_day_groups = db_services.RequiredAvailDayGroups.update(
            self.required_avail_day_group_id, self.num_avail_day_groups, self.location_of_work_ids
        )

    def undo(self):
        db_services.RequiredAvailDayGroups.update(
            self.required_avail_day_group_id, self.required_avail_day_group.num_avail_day_groups,
            [l.id for l in self.required_avail_day_group.locations_of_work]
        )

    def redo(self):
        self.updated_required_avail_day_groups = db_services.RequiredAvailDayGroups.update(
            self.required_avail_day_group_id, self.num_avail_day_groups, self.location_of_work_ids
        )


class Delete(Command):
    def __init__(self, required_avail_day_group_id: UUID):
        self.required_avail_day_group_id = required_avail_day_group_id
        self.required_avail_day_group = db_services.RequiredAvailDayGroups.get(required_avail_day_group_id)

    def execute(self):
        db_services.RequiredAvailDayGroups.delete(self.required_avail_day_group_id)

    def undo(self):
        db_services.RequiredAvailDayGroups.create(
            self.required_avail_day_group.num_avail_day_groups, self.required_avail_day_group.avail_day_group.id,
            [l.id for l in self.required_avail_day_group.locations_of_work], self.required_avail_day_group.id
        )

    def redo(self):
        db_services.RequiredAvailDayGroups.delete(self.required_avail_day_group_id)
