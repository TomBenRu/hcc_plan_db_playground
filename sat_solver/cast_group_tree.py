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
        self.fixed_cast_only_if_available: bool | None = cast_group_db.fixed_cast_only_if_available if cast_group_db else None
        self.prefer_fixed_cast_events: bool | None = cast_group_db.prefer_fixed_cast_events if cast_group_db else None
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
    def __init__(self, plan_period_id: UUID = None,
                 from_root: CastGroup = None):
        """
        Initialisiert einen CastGroupTree.
        
        Args:
            plan_period_id: PlanPeriod UUID für Single-Period Tree
            from_root: Bereits konstruierter Root-Node für Combined Multi-Period Tree
        """
        if from_root:
            # Multi-Period Mode: Nutze übergebenen Root
            self.root = from_root
            self.nodes = self._collect_all_nodes(from_root)
            self.plan_period_id = None  # Nicht anwendbar bei Combined Tree
        else:
            # Single-Period Mode: Bestehende Logik
            self.plan_period_id = plan_period_id
            self.nodes: dict[UUID | int, CastGroup] = {}
            self.root: CastGroup | None = None
            self.construct_cast_group_tree()

    def _collect_all_nodes(self, root: CastGroup) -> dict[UUID | int, CastGroup]:
        """
        Sammelt alle Nodes aus einem bereits konstruierten Tree.

        Args:
            root: Root-Node des Trees

        Returns:
            Dictionary mit allen Nodes (cast_group_id -> CastGroup)
        """
        nodes = {root.cast_group_id: root}
        nodes.update({node.cast_group_id: node for node in root.descendants})
        return nodes

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


def get_combined_cast_group_tree(plan_period_ids: list[UUID]) -> CastGroupTree:
    """
    Erstellt einen kombinierten CastGroupTree über mehrere PlanPeriods.

    Diese Funktion ermöglicht die Multi-Period Kalkulation, indem sie einen
    Super-Root erstellt, der alle einzelnen PlanPeriod Trees als Children enthält.

    Struktur des kombinierten Trees:
        Super-Root (cast_group_id=0)
        ├─ PlanPeriod 1 CastGroups
        │  ├─ CastGroup 1 (Event 1)
        │  │  └─ Child CastGroups
        │  └─ CastGroup 2 (Event 2)
        └─ PlanPeriod 2 CastGroups
           ├─ CastGroup 3 (Event 3)
           └─ CastGroup 4 (Event 4)

    Args:
        plan_period_ids: Liste von PlanPeriod UUIDs (mindestens 2)

    Returns:
        CastGroupTree mit Super-Root die alle Periode-Trees enthält

    Raises:
        ValueError: Wenn weniger als 2 PlanPeriods übergeben werden
    """
    if len(plan_period_ids) < 2:
        raise ValueError(f"Multi-Period calculation requires at least 2 periods, got {len(plan_period_ids)}")

    cast_group_trees = [get_cast_group_tree(pp_id) for pp_id in plan_period_ids]

    # 1. Setze eindeutige IDs für alle Root-Nodes
    for i, tree in enumerate(cast_group_trees, start=1):
        tree.root.cast_group_id = i

    # 2. Erstelle Super-Root mit allen PlanPeriod-Roots als Children
    super_root = CastGroup(
        cast_group_db=None,  # Kein DB-Objekt für Super-Root
        children=[tree.root for tree in cast_group_trees],  # Alle PlanPeriod-Roots als Children
        parent=None
    )
    super_root.name = "Super-Root"

    return CastGroupTree(from_root=super_root)


def get_combined_cast_group_tree_deprecated(plan_period_ids: list[UUID]) -> CastGroupTree:
    """
    Erstellt einen kombinierten CastGroupTree über mehrere PlanPeriods.
    
    Diese Funktion ermöglicht die Multi-Period Kalkulation, indem sie einen
    Super-Root erstellt, der alle einzelnen PlanPeriod Trees als Children enthält.
    
    Struktur des kombinierten Trees:
        Super-Root (cast_group_id=0)
        ├─ PlanPeriod 1 CastGroups
        │  ├─ CastGroup 1 (Event 1)
        │  │  └─ Child CastGroups
        │  └─ CastGroup 2 (Event 2)
        └─ PlanPeriod 2 CastGroups
           ├─ CastGroup 3 (Event 3)
           └─ CastGroup 4 (Event 4)
    
    Args:
        plan_period_ids: Liste von PlanPeriod UUIDs (mindestens 2)
        
    Returns:
        CastGroupTree mit Super-Root die alle Periode-Trees enthält
        
    Raises:
        ValueError: Wenn weniger als 2 PlanPeriods übergeben werden
    """
    if len(plan_period_ids) < 2:
        raise ValueError(f"Multi-Period calculation requires at least 2 periods, got {len(plan_period_ids)}")
    
    # 1. Erstelle Super-Root (ohne Children zunächst)
    super_root = CastGroup(
        cast_group_db=None,  # Kein DB-Objekt für Super-Root
        children=[],  # Wird befüllt
        parent=None
    )
    super_root.cast_group_id = 0  # Spezielle ID für Super-Root
    super_root.name = "Super-Root"
    
    # 2. Erstelle für jede PlanPeriod einen Tree und füge als Children hinzu
    all_top_nodes = []  # Sammle alle Top-Level Nodes
    
    for pp_id in plan_period_ids:
        # Hole alle Top-Level CastGroups dieser PlanPeriod (die ohne Parent)
        all_cast_groups_db = db_services.CastGroup.get_all_from__plan_period(pp_id)
        cast_groups_db_top = [cg for cg in all_cast_groups_db if not cg.parent_groups]
        
        # Erstelle Top-Level Nodes für diese PlanPeriod
        for cg_top in cast_groups_db_top:
            # Top-Level CastGroup wird als CastGroup-Objekt erstellt
            curr_node = CastGroup(cg_top, None, None)  # Parent wird später gesetzt
            all_top_nodes.append(curr_node)
    
    # 3. Setze alle Top-Level Nodes als Children des Super-Root
    super_root.children = all_top_nodes
    for node in all_top_nodes:
        node.parent = super_root
    
    # 4. Baue rekursiv Child-CastGroups auf
    nodes_to_process = list(all_top_nodes)
    
    while nodes_to_process:
        current_nodes = nodes_to_process
        nodes_to_process = []
        
        for node in current_nodes:
            if node.cast_group_db and node.cast_group_db.child_groups:
                for cg_db in node.cast_group_db.child_groups:
                    cg_db = db_services.CastGroup.get(cg_db.id)
                    child_node = CastGroup(cg_db, None, node)
                    if cg_db.child_groups:
                        nodes_to_process.append(child_node)
    
    # 5. Erstelle CastGroupTree mit dem konstruierten Super-Root
    return CastGroupTree(from_root=super_root)


def render_cast_group_tree(cast_group_tree: CastGroupTree):
    print(RenderTree(cast_group_tree.root, ContRoundStyle))


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    cast_group_tree = get_cast_group_tree(PLAN_PERIOD_ID)
    render_cast_group_tree(cast_group_tree)
