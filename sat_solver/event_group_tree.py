from typing import Optional
from uuid import UUID

from anytree import NodeMixin, RenderTree, ContRoundStyle

from database import schemas, db_services


class EventGroup(NodeMixin):
    def __init__(self, event_group_db: schemas.EventGroupShow | None,
                 children: list['EventGroup'] = None,
                 parent: Optional['EventGroup'] = None,
                 root_is_location_plan_period_master_group: bool = False):
        super().__init__()
        self.root_is_location_plan_period_master_group = root_is_location_plan_period_master_group
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
                f'nr_active_children: {self.nr_of_active_children}, children: {len(self.children)}, '
                f'event: {event_date}')


class EventGroupTree:
    def __init__(self, location_plan_period_ids: list[UUID] = None,
                 from_root: EventGroup = None):
        """
        Initialisiert einen EventGroupTree.
        
        Args:
            location_plan_period_ids: Liste von LocationPlanPeriod UUIDs für Single-Period Tree
            from_root: Bereits konstruierter Root-Node für Combined Multi-Period Tree
        """
        if from_root:
            # Multi-Period Mode: Nutze übergebenen Root
            self.root = from_root
            self.nodes = self._collect_all_nodes(from_root)
            self.location_plan_period_ids = []  # Leer bei Combined Tree
        else:
            # Single-Period Mode: Bestehende Logik
            self.location_plan_period_ids = location_plan_period_ids
            self.nodes: dict[UUID | int, EventGroup] = {}
            self.root: EventGroup = self.construct_root_node()
            self.construct_event_group_tree()

    def _collect_all_nodes(self, root: EventGroup) -> dict[UUID | int, EventGroup]:
        """
        Sammelt alle Nodes aus einem bereits konstruierten Tree.
        
        Args:
            root: Root-Node des Trees
            
        Returns:
            Dictionary mit allen Nodes (event_group_id -> EventGroup)
        """
        nodes = {root.event_group_id: root}
        
        def collect_recursive(node: EventGroup):
            for child in node.children:
                nodes[child.event_group_id] = child
                collect_recursive(child)
        
        collect_recursive(root)
        return nodes

    def construct_root_node(self) -> EventGroup:
        if len(self.location_plan_period_ids) == 1:
            event_group_db = (db_services.EventGroup
                              .get_master_from__location_plan_period(self.location_plan_period_ids[0]))
            child_groups = [db_services.EventGroup.get(evg.id) for evg in event_group_db.event_groups]
            root = EventGroup(event_group_db, [EventGroup(child) for child in child_groups], None, True)
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


def get_combined_event_group_tree(plan_period_ids: list[UUID]) -> EventGroupTree:
    """
    Erstellt einen kombinierten EventGroupTree über mehrere PlanPeriods.

    Diese Funktion ermöglicht die Multi-Period Kalkulation, indem sie einen
    Super-Root erstellt, der alle einzelnen PlanPeriod Trees als Children enthält.

    Struktur des kombinierten Trees:
        Super-Root (event_group_id=0)
        ├─ PlanPeriod 1 Root
        │  ├─ Master von LocationPlanPeriod 1
        │  └─ Master von LocationPlanPeriod 2
        └─ PlanPeriod 2 Root
           ├─ Master von LocationPlanPeriod 3
           └─ Master von LocationPlanPeriod 4

    Args:
        plan_period_ids: Liste von PlanPeriod UUIDs (mindestens 2)

    Returns:
        EventGroupTree mit Super-Root die alle Periode-Trees enthält

    Raises:
        ValueError: Wenn weniger als 2 PlanPeriods übergeben werden
    """
    if len(plan_period_ids) < 2:
        raise ValueError(f"Multi-Period calculation requires at least 2 periods, got {len(plan_period_ids)}")

    event_group_trees = [get_event_group_tree(pp_id) for pp_id in plan_period_ids]

    # 1. Setze eindeutige IDs für alle Root-Nodes
    for i, tree in enumerate(event_group_trees, start=1):
        tree.root.event_group_id = i

    # 2. Erstelle Super-Root mit allen PlanPeriod-Roots als Children
    super_root = EventGroup(
        event_group_db=None,  # Kein DB-Objekt für Super-Root
        children=[tree.root for tree in event_group_trees],  # Alle PlanPeriod-Roots als Children
        parent=None,
        root_is_location_plan_period_master_group=False
    )
    super_root.event_group_id = 0  # Spezielle ID für Super-Root
    super_root.name = "Super-Root"
    super_root.nr_of_active_children = len(plan_period_ids)  # Alle Perioden aktiv

    # 3. Setze Super-Root als Parent für alle PlanPeriod-Roots
    for pp_root in super_root.children:
        pp_root.parent = super_root

    return EventGroupTree(from_root=super_root)


def get_combined_event_group_tree_deprecated(plan_period_ids: list[UUID]) -> EventGroupTree:
    """
    Erstellt einen kombinierten EventGroupTree über mehrere PlanPeriods.
    
    Diese Funktion ermöglicht die Multi-Period Kalkulation, indem sie einen
    Super-Root erstellt, der alle einzelnen PlanPeriod Trees als Children enthält.
    
    Struktur des kombinierten Trees:
        Super-Root (event_group_id=0)
        ├─ PlanPeriod 1 Root
        │  ├─ Master von LocationPlanPeriod 1
        │  └─ Master von LocationPlanPeriod 2
        └─ PlanPeriod 2 Root
           ├─ Master von LocationPlanPeriod 3
           └─ Master von LocationPlanPeriod 4
    
    Args:
        plan_period_ids: Liste von PlanPeriod UUIDs (mindestens 2)
        
    Returns:
        EventGroupTree mit Super-Root die alle Periode-Trees enthält
        
    Raises:
        ValueError: Wenn weniger als 2 PlanPeriods übergeben werden
    """
    if len(plan_period_ids) < 2:
        raise ValueError(f"Multi-Period calculation requires at least 2 periods, got {len(plan_period_ids)}")
    
    # 1. Erstelle alle PlanPeriod-Roots (ohne Parent zunächst)
    pp_roots = []
    
    for pp_id in plan_period_ids:
        # Hole alle LocationPlanPeriods dieser PlanPeriod
        location_plan_periods = db_services.PlanPeriod.get(pp_id).location_plan_periods
        lpp_ids = [lpp.id for lpp in location_plan_periods]
        
        # Erstelle PlanPeriod-Root (analog zu EventGroupTree.construct_root_node)
        if len(lpp_ids) == 1:
            # Einzelne LocationPlanPeriod: Master-EventGroup direkt als Root
            event_group_db = (db_services.EventGroup
                              .get_master_from__location_plan_period(lpp_ids[0]))
            child_groups = [db_services.EventGroup.get(evg.id) for evg in event_group_db.event_groups]
            pp_root = EventGroup(
                event_group_db, 
                [EventGroup(child) for child in child_groups], 
                None,  # Parent wird später gesetzt
                True
            )
        else:
            # Multiple LocationPlanPeriods: Erstelle Container-Root
            child_groups = [db_services.EventGroup.get_master_from__location_plan_period(lpp_id)
                            for lpp_id in lpp_ids]
            pp_root = EventGroup(
                None, 
                [EventGroup(child) for child in child_groups],
                None  # Parent wird später gesetzt
            )
        
        pp_roots.append(pp_root)
    
    # 2. Erstelle Super-Root mit allen PlanPeriod-Roots als Children
    super_root = EventGroup(
        event_group_db=None,  # Kein DB-Objekt für Super-Root
        children=pp_roots,  # Alle PlanPeriod-Roots als Children
        parent=None,
        root_is_location_plan_period_master_group=False
    )
    super_root.event_group_id = 0  # Spezielle ID für Super-Root
    super_root.name = "Super-Root"
    super_root.weight = None
    super_root.nr_of_active_children = len(plan_period_ids)  # Alle Perioden aktiv
    
    # WICHTIG: Setze Super-Root als Parent für alle PlanPeriod-Roots
    # UND setze pp_root als Parent für alle ihre direkten Children
    for pp_root in pp_roots:
        pp_root.parent = super_root
        for child in pp_root.children:
            child.parent = pp_root
    
    # 3. Baue rekursiv den Rest des Trees für jede PlanPeriod auf
    def construct_recursive(parent: EventGroup):
        if parent.event_group_db:
            for event_group_db in parent.event_group_db.event_groups:
                evg = db_services.EventGroup.get(event_group_db.id)
                child = EventGroup(evg, None, parent)
                construct_recursive(child)
    
    for pp_root in pp_roots:
        for child in pp_root.children:
            construct_recursive(child)
    
    # 4. Erstelle EventGroupTree mit dem konstruierten Super-Root
    return EventGroupTree(from_root=super_root)


def render_event_group_tree(event_group_tree: EventGroupTree):
    print(RenderTree(event_group_tree.root, ContRoundStyle))


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    get_event_group_tree(PLAN_PERIOD_ID)
