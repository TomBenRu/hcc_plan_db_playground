from typing import Optional
from uuid import UUID

from anytree import NodeMixin, RenderTree, ContRoundStyle

from database import schemas, db_services


class CastGroup(NodeMixin):
    def __init__(self, cast_group_db: schemas.CastGroupShow | None,
                 children: list['CastGroup'] = None,
                 parent: Optional['CastGroup'] = None):
        super().__init__()
        self.cast_group_id = cast_group_db.id if cast_group_db else 0
        self.name = str(self.cast_group_id)
        self.cast_group_db = cast_group_db
        self._event = None
        self.parent: Optional['CastGroup'] = parent
        self.children: list['CastGroup'] = children if children is not None else []
        self.fixed_cast: str | None = cast_group_db.fixed_cast if cast_group_db else None
        self.nr_actors: int | None = cast_group_db.nr_actors if cast_group_db else None
        self.cast_rule: str | None = ((cast_group_db.custom_rule or (cast_group_db.cast_rule.rule
                                                                     if cast_group_db.cast_rule else None))
                                      if cast_group_db else None)
        self.strict_rule_pref: int | None = cast_group_db.strict_cast_pref if cast_group_db else None

    @property
    def event(self) -> schemas.EventShow:
        if self._event is None:
            self._event = self.get_event_from_db()
        return self._event

    def get_event_from_db(self):
        return (db_services.Event.get(self.cast_group_db.event.id)
                if (self.cast_group_db and self.cast_group_db.event) else None)

    def __repr__(self):
        return (f'cast group with event {self.event.date: %d.%m.%y} ({self.event.time_of_day.name})'
                if self.event else 'cast group')


class CastGroupTree:
    def __init__(self, plan_period_id: UUID):
        self.plan_period_id = plan_period_id
        self.nodes: dict[UUID | int, CastGroup] = {}
        self.root: CastGroup | None = None

        self.construct_cast_group_tree()

    def construct_cast_group_tree(self):
        self.root = CastGroup(None)
        all_cast_groups_db = db_services.CastGroup.get_all_from__plan_period(self.plan_period_id)
        cast_groups_db_top = [cg for cg in all_cast_groups_db if not cg.parent_groups]
        top_nodes: list[CastGroup] = []
        lower_nodes: list[CastGroup] = []

        for cg_top in cast_groups_db_top:
            curr_node = CastGroup(cg_top, None, self.root)
            if cg_top.child_groups:
                top_nodes.append(curr_node)

        while top_nodes:
            for node in top_nodes:
                for cg_db in node.cast_group_db.child_groups:
                    cg_db = db_services.CastGroup.get(cg_db.id)
                    curr_node = CastGroup(cg_db, None, node)
                    if cg_db.child_groups:
                        lower_nodes.append(curr_node)
            top_nodes, lower_nodes = lower_nodes, []


def get_cast_group_tree(plan_period_id: UUID) -> CastGroupTree:
    return CastGroupTree(plan_period_id)


def render_cast_group_tree(cast_group_tree: CastGroupTree):
    print(RenderTree(cast_group_tree.root, ContRoundStyle))


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    cast_group_tree = get_cast_group_tree(PLAN_PERIOD_ID)
    render_cast_group_tree(cast_group_tree)
