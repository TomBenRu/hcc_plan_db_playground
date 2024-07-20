from typing import Optional
from uuid import UUID

from anytree import NodeMixin, RenderTree, ContRoundStyle

from database import schemas, db_services


class EventGroup(NodeMixin):
    def __init__(self, event_group_db: schemas.EventGroupShow | None,
                 children: list['EventGroup'] = None,
                 parent: Optional['EventGroup'] = None):
        super().__init__()
        self.event_group_id = event_group_db.id if event_group_db else 0
        self.name = str(self.event_group_id)
        self.event_group_db = event_group_db
        self._event: schemas.EventShow | None = None
        self.parent: Optional['EventGroup'] = parent
        self.children: list['EventGroup'] = children if children is not None else []
        self.weight = event_group_db.variation_weight if event_group_db else None
        self.nr_of_active_children = event_group_db.nr_event_groups if event_group_db else None

    def _post_detach(self, parent):
        self.weight = None

    @property
    def event(self) -> schemas.EventShow:
        if self._event is None:
            self._event = self.get_event_from_db()
        return self._event

    def get_event_from_db(self):
        return (db_services.Event.get(self.event_group_db.event.id)
                if (self.event_group_db and self.event_group_db.event) else None)

    def __repr__(self):
        event_date = self.event.date.strftime('%d.%m.%y') if self.event else None
        return (f'Node id: {self.event_group_id}, weight: {self.weight}, '
                f'nr_active_children: {self.nr_of_active_children}, event: {event_date}')


class EventGroupTree:
    def __init__(self, location_plan_period_ids: list[UUID]):
        self.location_plan_period_ids = location_plan_period_ids
        self.nodes: dict[UUID | int, EventGroup] = {}
        self.root: EventGroup = self.construct_root_node()

        self.construct_event_group_tree()

    def construct_root_node(self) -> EventGroup:
        if len(self.location_plan_period_ids) == 1:
            event_group_db = db_services.EventGroup.get_master_from__location_plan_period(self.location_plan_period_ids[0])
            child_groups = [db_services.EventGroup.get(evg.id) for evg in event_group_db.event_groups]
            root = EventGroup(event_group_db, [EventGroup(child) for child in child_groups], None)
        else:
            child_groups = [db_services.EventGroup.get_master_from__location_plan_period(lpp_id)
                            for lpp_id in self.location_plan_period_ids]
            root = EventGroup(None, [EventGroup(child) for child in child_groups])
        self.nodes[0] = root
        self.nodes.update({n.event_group_id: n for n in root.children})

        return root

    def construct_event_group_tree(self):

        def construct_recursive(parent: EventGroup):
            for event_group_db in parent.event_group_db.event_groups:
                evg = db_services.EventGroup.get(event_group_db.id)
                child = EventGroup(evg, None, parent)
                self.nodes[child.event_group_id] = child
                construct_recursive(child)

        for child in self.root.children:
            construct_recursive(child)


def get_event_group_tree(plan_period_id: UUID) -> EventGroupTree:
    location_plan_periods = db_services.PlanPeriod.get(plan_period_id).location_plan_periods
    return EventGroupTree([lpp.id for lpp in location_plan_periods])


def render_event_group_tree(event_group_tree: EventGroupTree):
    print(RenderTree(event_group_tree.root, ContRoundStyle))


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    get_event_group_tree(PLAN_PERIOD_ID)
