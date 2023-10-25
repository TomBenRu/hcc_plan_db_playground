from typing import Optional
from uuid import UUID

from anytree import NodeMixin, RenderTree, ContRoundStyle

from database import schemas, db_services


class AvailDayGroup(NodeMixin):
    def __init__(self, avail_day_group_db: schemas.AvailDayGroupShow | None,
                 children: list['AvailDayGroup'] = None,
                 parent: Optional['AvailDayGroup'] = None):
        super().__init__()
        self.avail_day_group_id = avail_day_group_db.id if avail_day_group_db else 0
        self.name = str(self.avail_day_group_id)
        self.avail_day_group_db = avail_day_group_db
        self._avail_day: schemas.AvailDayShow | None = None
        self.parent: Optional['AvailDayGroup'] = parent
        self.children: list['AvailDayGroup'] = children if children is not None else []
        self.weight = avail_day_group_db.variation_weight if avail_day_group_db else None
        self.nr_of_active_children = avail_day_group_db.nr_avail_day_groups if avail_day_group_db else None
        self.mandatory_nr_avail_day_groups = avail_day_group_db.mandatory_nr_avail_day_groups if avail_day_group_db else None

    def _post_detach(self, parent):
        self.weight = None

    @property
    def avail_day(self) -> schemas.AvailDayShow:
        if self._avail_day is None:
            self._avail_day = self.get_avail_day_from_db()
        return self._avail_day

    def get_avail_day_from_db(self):
        return (db_services.AvailDay.get(self.avail_day_group_db.avail_day.id)
                if (self.avail_day_group_db and self.avail_day_group_db.avail_day) else None)

    def __repr__(self):
        event_date = self.avail_day.date.strftime('%d.%m.%y') if self.avail_day else None
        return (f'Node id: {self.avail_day_group_id}, weight: {self.weight}, '
                f'nr_active_children: {self.nr_of_active_children}, event: {event_date}')


class AvailDayGroupTree:
    def __init__(self, actor_plan_period_ids: list[UUID]):
        self.actor_plan_period_ids = actor_plan_period_ids
        self.nodes: dict[UUID | int, AvailDayGroup] = {}
        self.root: AvailDayGroup = self.construct_root_node()

        self.construct_event_group_tree()

    def construct_root_node(self) -> AvailDayGroup:
        if len(self.actor_plan_period_ids) == 1:
            avail_day_group_db = db_services.AvailDayGroup.get_master_from__actor_plan_period(self.actor_plan_period_ids[0])
            child_groups = [db_services.AvailDayGroup.get(adg.id) for adg in avail_day_group_db.avail_day_groups]
            root = AvailDayGroup(avail_day_group_db, [AvailDayGroup(child) for child in child_groups], None)
        else:
            child_groups = [db_services.AvailDayGroup.get_master_from__actor_plan_period(app_id)
                            for app_id in self.actor_plan_period_ids]
            root = AvailDayGroup(None, [AvailDayGroup(child) for child in child_groups])
        self.nodes[0] = root
        self.nodes.update({n.avail_day_group_id: n for n in root.children})

        return root

    def construct_event_group_tree(self):

        def construct_recursive(parent: AvailDayGroup):
            for avail_day_group_db in parent.avail_day_group_db.avail_day_groups:
                adg = db_services.AvailDayGroup.get(avail_day_group_db.id)
                child = AvailDayGroup(adg, None, parent)
                self.nodes[child.avail_day_group_id] = child
                construct_recursive(child)

        for child in self.root.children:
            construct_recursive(child)


def get_avail_day_group_tree(plan_period_id: UUID) -> AvailDayGroupTree:
    actor_plan_periods = db_services.PlanPeriod.get(plan_period_id).actor_plan_periods
    return AvailDayGroupTree([app.id for app in actor_plan_periods])


def render_event_group_tree(avail_day_group_tree: AvailDayGroupTree):
    print(RenderTree(avail_day_group_tree.root, ContRoundStyle))


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    avail_day_group_tree = get_avail_day_group_tree(PLAN_PERIOD_ID)
    render_event_group_tree(avail_day_group_tree)
