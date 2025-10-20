from typing import Optional
from uuid import UUID

from anytree import NodeMixin, RenderTree, ContRoundStyle

from database import schemas, db_services


class AvailDayGroup(NodeMixin):
    def __init__(self,
                 avail_day_group_db: schemas.AvailDayGroupShow | None,
                 children: list['AvailDayGroup'] = None,
                 parent: Optional['AvailDayGroup'] = None,
                 group_is_actor_plan_period_master_group: bool = False):
        super().__init__()
        self.group_is_actor_plan_period_master_group = group_is_actor_plan_period_master_group
        self.avail_day_group_id = avail_day_group_db.id if avail_day_group_db else 0
        self.name = str(self.avail_day_group_id)
        self.avail_day_group_db = avail_day_group_db
        self._avail_day: schemas.AvailDayShow | None = None
        self.parent: Optional['AvailDayGroup'] = parent
        self.children: list['AvailDayGroup'] = children if children is not None else []
        self.weight = avail_day_group_db.variation_weight if avail_day_group_db else None
        self.nr_of_active_children = avail_day_group_db.nr_avail_day_groups if avail_day_group_db else None
        self._required_avail_day_groups: schemas.RequiredAvailDayGroups | None = None

    def _post_detach(self, parent):
        self.weight = None

    @property
    def avail_day(self) -> schemas.AvailDayShow:
        if self._avail_day is None:
            self._avail_day = self._get_avail_day_from_db()
        return self._avail_day

    @property
    def required_avail_day_groups(self) -> schemas.RequiredAvailDayGroups | None:
        if not self.avail_day_group_db:
            return None
        if self._required_avail_day_groups is None:
            self._required_avail_day_groups = db_services.RequiredAvailDayGroups.get_from__avail_day_group(
                self.avail_day_group_id)
        return self._required_avail_day_groups

    def _get_avail_day_from_db(self):
        return (db_services.AvailDay.get(self.avail_day_group_db.avail_day.id)
                if (self.avail_day_group_db and self.avail_day_group_db.avail_day) else None)

    def __repr__(self):
        date = self.avail_day.date.strftime('%d.%m.%y') if self.avail_day else None
        return (f'Node id: {self.avail_day_group_id}, weight: {self.weight}, '
                f'nr_active_children: {self.nr_of_active_children}, '
                f'parent: {self.parent.avail_day_group_id if self.parent else None}, children: {len(self.children)}, '
                f'avail_day_date: {date}')


class AvailDayGroupTree:
    def __init__(self, actor_plan_period_ids: list[UUID] = None,
                 from_root: AvailDayGroup = None):
        """
        Initialisiert einen AvailDayGroupTree.
        
        Args:
            actor_plan_period_ids: Liste von ActorPlanPeriod UUIDs für Single-Period Tree
            from_root: Bereits konstruierter Root-Node für Combined Multi-Period Tree
        """
        if from_root:
            # Multi-Period Mode: Nutze übergebenen Root
            self.root = from_root
            self.nodes = self._collect_all_nodes(from_root)
            self.actor_plan_period_ids = []  # Leer bei Combined Tree
        else:
            # Single-Period Mode: Bestehende Logik
            self.actor_plan_period_ids = actor_plan_period_ids
            self.nodes: dict[UUID | int, AvailDayGroup] = {}
            self.root: AvailDayGroup = self.construct_root_node()
            self.construct_event_group_tree()

    def _collect_all_nodes(self, root: AvailDayGroup) -> dict[UUID | int, AvailDayGroup]:
        """
        Sammelt alle Nodes aus einem bereits konstruierten Tree.
        
        Args:
            root: Root-Node des Trees
            
        Returns:
            Dictionary mit allen Nodes (avail_day_group_id -> AvailDayGroup)
        """
        nodes = {root.avail_day_group_id: root}
        
        def collect_recursive(node: AvailDayGroup):
            for child in node.children:
                nodes[child.avail_day_group_id] = child
                collect_recursive(child)
        
        collect_recursive(root)
        return nodes

    def construct_root_node(self) -> AvailDayGroup:
        if len(self.actor_plan_period_ids) == 1:
            avail_day_group_db = (db_services.AvailDayGroup
                                  .get_master_from__actor_plan_period(self.actor_plan_period_ids[0]))
            child_groups = [db_services.AvailDayGroup.get(adg.id) for adg in avail_day_group_db.avail_day_groups]
            root = AvailDayGroup(avail_day_group_db,
                                 [AvailDayGroup(child) for child in child_groups],
                                 None,
                                 True)
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


def get_combined_avail_day_group_tree(plan_period_ids: list[UUID]) -> AvailDayGroupTree:
    """
    Erstellt einen kombinierten AvailDayGroupTree über mehrere PlanPeriods.

    Diese Funktion ermöglicht die Multi-Period Kalkulation, indem sie einen
    Super-Root erstellt, der alle einzelnen PlanPeriod Trees als Children enthält.

    Struktur des kombinierten Trees:
        Super-Root (avail_day_group_id=0)
        ├─ PlanPeriod 1 Root
        │  ├─ Master von ActorPlanPeriod 1
        │  └─ Master von ActorPlanPeriod 2
        └─ PlanPeriod 2 Root
           ├─ Master von ActorPlanPeriod 3
           └─ Master von ActorPlanPeriod 4

    Args:
        plan_period_ids: Liste von PlanPeriod UUIDs (mindestens 2)

    Returns:
        AvailDayGroupTree mit Super-Root die alle Periode-Trees enthält

    Raises:
        ValueError: Wenn weniger als 2 PlanPeriods übergeben werden
    """
    if len(plan_period_ids) < 2:
        raise ValueError(f"Multi-Period calculation requires at least 2 periods, got {len(plan_period_ids)}")

    avail_day_group_trees = [get_avail_day_group_tree(pp_id) for pp_id in plan_period_ids]

    # 1. Setze eindeutige IDs für alle Root-Nodes
    for i, tree in enumerate(avail_day_group_trees, start=1):
        tree.root.avail_day_group_id = i

    # 2. Erstelle Super-Root mit allen PlanPeriod-Roots als Children
    super_root = AvailDayGroup(
        avail_day_group_db=None,  # Kein DB-Objekt für Super-Root
        children=[tree.root for tree in avail_day_group_trees],  # Alle PlanPeriod-Roots als Children
        parent=None,
        group_is_actor_plan_period_master_group=False
    )
    super_root.name = "Super-Root"
    super_root.nr_of_active_children = len(plan_period_ids)  # Alle Perioden aktiv

    # WICHTIG: Setze Super-Root als Parent für alle PlanPeriod-Roots
    for pp_root in super_root.children:
        pp_root.parent = super_root

    return AvailDayGroupTree(from_root=super_root)


def get_combined_avail_day_group_tree_deprecated(plan_period_ids: list[UUID]) -> AvailDayGroupTree:
    """
    Erstellt einen kombinierten AvailDayGroupTree über mehrere PlanPeriods.
    
    Diese Funktion ermöglicht die Multi-Period Kalkulation, indem sie einen
    Super-Root erstellt, der alle einzelnen PlanPeriod Trees als Children enthält.
    
    Struktur des kombinierten Trees:
        Super-Root (avail_day_group_id=0)
        ├─ PlanPeriod 1 Root
        │  ├─ Master von ActorPlanPeriod 1
        │  └─ Master von ActorPlanPeriod 2
        └─ PlanPeriod 2 Root
           ├─ Master von ActorPlanPeriod 3
           └─ Master von ActorPlanPeriod 4
    
    Args:
        plan_period_ids: Liste von PlanPeriod UUIDs (mindestens 2)
        
    Returns:
        AvailDayGroupTree mit Super-Root die alle Periode-Trees enthält
        
    Raises:
        ValueError: Wenn weniger als 2 PlanPeriods übergeben werden
    """
    if len(plan_period_ids) < 2:
        raise ValueError(f"Multi-Period calculation requires at least 2 periods, got {len(plan_period_ids)}")
    
    # 1. Erstelle alle PlanPeriod-Roots (ohne Parent zunächst)
    pp_roots = []
    
    for pp_id in plan_period_ids:
        # Hole alle ActorPlanPeriods dieser PlanPeriod
        actor_plan_periods = db_services.PlanPeriod.get(pp_id).actor_plan_periods
        app_ids = [app.id for app in actor_plan_periods]
        
        # Erstelle PlanPeriod-Root (analog zu AvailDayGroupTree.construct_root_node)
        if len(app_ids) == 1:
            # Einzelner ActorPlanPeriod: Master-AvailDayGroup direkt als Root
            avail_day_group_db = (db_services.AvailDayGroup
                                  .get_master_from__actor_plan_period(app_ids[0]))
            child_groups = [db_services.AvailDayGroup.get(adg.id) for adg in avail_day_group_db.avail_day_groups]
            pp_root = AvailDayGroup(
                avail_day_group_db,
                [AvailDayGroup(child) for child in child_groups],
                None,  # Parent wird später gesetzt
                True
            )
        else:
            # Multiple ActorPlanPeriods: Erstelle Container-Root
            child_groups = [db_services.AvailDayGroup.get_master_from__actor_plan_period(app_id)
                            for app_id in app_ids]
            pp_root = AvailDayGroup(
                None,
                [AvailDayGroup(child) for child in child_groups],
                None  # Parent wird später gesetzt
            )
        
        pp_roots.append(pp_root)
    
    # 2. Erstelle Super-Root mit allen PlanPeriod-Roots als Children
    super_root = AvailDayGroup(
        avail_day_group_db=None,  # Kein DB-Objekt für Super-Root
        children=pp_roots,  # Alle PlanPeriod-Roots als Children
        parent=None,
        group_is_actor_plan_period_master_group=False
    )
    super_root.avail_day_group_id = 0  # Spezielle ID für Super-Root
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
    def construct_recursive(parent: AvailDayGroup):
        if parent.avail_day_group_db:
            for avail_day_group_db in parent.avail_day_group_db.avail_day_groups:
                adg = db_services.AvailDayGroup.get(avail_day_group_db.id)
                child = AvailDayGroup(adg, None, parent)
                construct_recursive(child)
    
    for pp_root in pp_roots:
        for child in pp_root.children:
            construct_recursive(child)
    
    # 4. Erstelle AvailDayGroupTree mit dem konstruierten Super-Root
    return AvailDayGroupTree(from_root=super_root)


def render_event_group_tree(avail_day_group_tree: AvailDayGroupTree):
    print(RenderTree(avail_day_group_tree.root, ContRoundStyle))


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    avail_day_group_tree = get_avail_day_group_tree(PLAN_PERIOD_ID)
    render_event_group_tree(avail_day_group_tree)
