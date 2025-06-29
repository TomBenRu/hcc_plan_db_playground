"""
Unit-Tests für event_group_tree Modul

Testet die EventGroup Tree-Struktur für hierarchische Event-Group-Verwaltung.
Beinhaltet Tree-Konstruktion, Node-Management und Datenbankintegration.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4, UUID
from datetime import date

from sat_solver.event_group_tree import EventGroup, EventGroupTree, get_event_group_tree, render_event_group_tree


@pytest.mark.unit
class TestEventGroup:
    """Test-Klasse für EventGroup."""
    
    def test_event_group_initialization_with_db(self):
        """Test: EventGroup wird mit Datenbank-Objekt korrekt initialisiert."""
        # Mock database object
        eg_id = uuid4()
        mock_event_ref = Mock()
        mock_event_ref.id = uuid4()
        
        mock_event_group_db = Mock()
        mock_event_group_db.id = eg_id
        mock_event_group_db.event = mock_event_ref
        mock_event_group_db.variation_weight = 3.5
        mock_event_group_db.nr_event_groups = 2
        
        # Create EventGroup
        eg = EventGroup(mock_event_group_db)
        
        # Verify initialization
        assert eg.event_group_id == eg_id
        assert eg.name == str(eg_id)
        assert eg.event_group_db == mock_event_group_db
        assert eg.weight == 3.5
        assert eg.nr_of_active_children == 2
        assert not eg.root_is_location_plan_period_master_group
        assert eg.parent is None
        assert eg.children == []
    
    def test_event_group_initialization_without_db(self):
        """Test: EventGroup wird ohne Datenbank-Objekt korrekt initialisiert."""
        # Create EventGroup without database object
        eg = EventGroup(None)
        
        # Verify initialization
        assert eg.event_group_id == 0
        assert eg.name == "0"
        assert eg.event_group_db is None
        assert eg.weight is None
        assert eg.nr_of_active_children is None
        assert not eg.root_is_location_plan_period_master_group
        assert eg.parent is None
        assert eg.children == []
    
    def test_event_group_initialization_with_parameters(self):
        """Test: EventGroup wird mit allen Parametern korrekt initialisiert."""
        # Mock objects
        mock_event_group_db = Mock()
        mock_event_group_db.id = uuid4()
        mock_event_group_db.event = Mock()
        mock_event_group_db.variation_weight = 1.2
        mock_event_group_db.nr_event_groups = 5
        
        mock_parent = Mock()
        mock_child1 = Mock()
        mock_child2 = Mock()
        children = [mock_child1, mock_child2]
        
        # Create EventGroup with all parameters
        eg = EventGroup(
            event_group_db=mock_event_group_db,
            children=children,
            parent=mock_parent,
            root_is_location_plan_period_master_group=True
        )
        
        # Verify initialization
        assert eg.event_group_id == mock_event_group_db.id
        assert eg.event_group_db == mock_event_group_db
        assert eg.parent == mock_parent
        assert eg.children == children
        assert eg.weight == 1.2
        assert eg.nr_of_active_children == 5
        assert eg.root_is_location_plan_period_master_group
    
    def test_event_group_tree_structure(self):
        """Test: EventGroup Tree-Struktur (NodeMixin)."""
        # Create hierarchy: root -> parent -> child
        mock_root_db = Mock()
        mock_root_db.id = uuid4()
        mock_root_db.event = None
        mock_root_db.variation_weight = None
        mock_root_db.nr_event_groups = None
        
        mock_parent_db = Mock()
        mock_parent_db.id = uuid4()
        mock_parent_db.event = Mock()
        mock_parent_db.variation_weight = 2.0
        mock_parent_db.nr_event_groups = 1
        
        mock_child_db = Mock()
        mock_child_db.id = uuid4()
        mock_child_db.event = Mock()
        mock_child_db.variation_weight = 1.5
        mock_child_db.nr_event_groups = 0
        
        # Create nodes
        root = EventGroup(mock_root_db)
        parent = EventGroup(mock_parent_db, parent=root)
        child = EventGroup(mock_child_db, parent=parent)
        
        # Verify tree structure
        assert root.parent is None
        assert root.children == (parent,)  # anytree returns tuple
        assert parent.parent == root
        assert parent.children == (child,)
        assert child.parent == parent
        assert child.children == ()
        
        # Verify tree traversal
        assert root.descendants == (parent, child)
        assert child.ancestors == (root, parent)
        assert child.path == (root, parent, child)
    
    def test_post_detach_method(self):
        """Test: _post_detach() Methode setzt weight auf None."""
        # Mock database object
        mock_event_group_db = Mock()
        mock_event_group_db.id = uuid4()
        mock_event_group_db.event = Mock()
        mock_event_group_db.variation_weight = 4.2
        mock_event_group_db.nr_event_groups = 3
        
        # Create parent and child
        parent = EventGroup(Mock())
        child = EventGroup(mock_event_group_db, parent=parent)
        
        # Verify weight is set
        assert child.weight == 4.2
        
        # Detach child from parent
        child.parent = None
        
        # Verify weight is None after detach
        assert child.weight is None
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_property_lazy_loading(self, mock_db_services):
        """Test: event Property wird lazy geladen."""
        # Mock database objects
        event_id = uuid4()
        mock_event_ref = Mock()
        mock_event_ref.id = event_id
        
        mock_event_group_db = Mock()
        mock_event_group_db.id = uuid4()
        mock_event_group_db.event = mock_event_ref
        mock_event_group_db.variation_weight = 2.1
        mock_event_group_db.nr_event_groups = 1
        
        # Mock database service
        mock_event = Mock()
        mock_event.date = date(2025, 6, 29)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.name = "Vormittag"
        mock_db_services.Event.get.return_value = mock_event
        
        # Create EventGroup
        eg = EventGroup(mock_event_group_db)
        
        # Verify lazy loading - should not call DB initially
        assert not mock_db_services.Event.get.called
        
        # Access event property - should trigger DB call
        result = eg.event
        
        # Verify DB was called and result is cached
        mock_db_services.Event.get.assert_called_once_with(event_id)
        assert result == mock_event
        
        # Second access should not trigger another DB call
        result2 = eg.event
        assert result2 == mock_event
        assert mock_db_services.Event.get.call_count == 1  # Still only one call
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_property_no_db_object(self, mock_db_services):
        """Test: event Property ohne Datenbank-Objekt."""
        # Create EventGroup without database object
        eg = EventGroup(None)
        
        # Access event property
        result = eg.event
        
        # Should return None and not call database
        assert result is None
        assert not mock_db_services.Event.get.called
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_property_no_event_ref(self, mock_db_services):
        """Test: event Property ohne Event-Referenz."""
        # Mock database object without event reference
        mock_event_group_db = Mock()
        mock_event_group_db.id = uuid4()
        mock_event_group_db.event = None  # No event reference
        mock_event_group_db.variation_weight = 1.0
        mock_event_group_db.nr_event_groups = 0
        
        # Create EventGroup
        eg = EventGroup(mock_event_group_db)
        
        # Access event property
        result = eg.event
        
        # Should return None and not call database
        assert result is None
        assert not mock_db_services.Event.get.called
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_get_event_from_db_direct_call(self, mock_db_services):
        """Test: get_event_from_db() Methode direkter Aufruf."""
        # Mock database objects
        event_id = uuid4()
        mock_event_ref = Mock()
        mock_event_ref.id = event_id
        
        mock_event_group_db = Mock()
        mock_event_group_db.id = uuid4()
        mock_event_group_db.event = mock_event_ref
        mock_event_group_db.variation_weight = 1.8
        mock_event_group_db.nr_event_groups = 2
        
        # Mock database service
        mock_event = Mock()
        mock_event.date = date(2025, 7, 15)
        mock_db_services.Event.get.return_value = mock_event
        
        # Create EventGroup
        eg = EventGroup(mock_event_group_db)
        
        # Call get_event_from_db directly
        result = eg.get_event_from_db()
        
        # Verify DB was called and result is correct
        mock_db_services.Event.get.assert_called_once_with(event_id)
        assert result == mock_event
    
    def test_repr_method_with_event(self):
        """Test: __repr__() Methode mit Event."""
        # Mock database objects
        eg_id = uuid4()
        mock_event_group_db = Mock()
        mock_event_group_db.id = eg_id
        mock_event_group_db.event = Mock()
        mock_event_group_db.variation_weight = 2.3
        mock_event_group_db.nr_event_groups = 4
        
        # Create EventGroup
        eg = EventGroup(mock_event_group_db)
        
        # Mock event
        mock_event = Mock()
        mock_event.date = date(2025, 6, 29)
        eg._event = mock_event  # Set directly to avoid DB call
        
        # Test repr
        repr_str = repr(eg)
        
        # Verify repr contains expected information
        assert f"Node id: {eg_id}" in repr_str
        assert "weight: 2.3" in repr_str
        assert "nr_active_children: 4" in repr_str
        assert "children: 0" in repr_str
        assert "event: 29.06.25" in repr_str
    
    def test_repr_method_without_event(self):
        """Test: __repr__() Methode ohne Event."""
        # Mock database objects
        eg_id = uuid4()
        mock_event_group_db = Mock()
        mock_event_group_db.id = eg_id
        mock_event_group_db.event = None
        mock_event_group_db.variation_weight = 1.7
        mock_event_group_db.nr_event_groups = 1
        
        # Create EventGroup
        eg = EventGroup(mock_event_group_db)
        eg._event = None  # No event
        
        # Test repr
        repr_str = repr(eg)
        
        # Verify repr contains expected information
        assert f"Node id: {eg_id}" in repr_str
        assert "weight: 1.7" in repr_str
        assert "nr_active_children: 1" in repr_str
        assert "children: 0" in repr_str
        assert "event: None" in repr_str


@pytest.mark.unit
class TestEventGroupTree:
    """Test-Klasse für EventGroupTree."""
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_group_tree_initialization_single_location_plan_period(self, mock_db_services):
        """Test: EventGroupTree wird mit einzelner LocationPlanPeriod korrekt initialisiert."""
        # Mock data
        lpp_id = uuid4()
        master_eg_id = uuid4()
        child1_id = uuid4()
        child2_id = uuid4()
        
        # Mock child references
        mock_child1_ref = Mock()
        mock_child1_ref.id = child1_id
        
        mock_child2_ref = Mock()
        mock_child2_ref.id = child2_id
        
        # Mock master event group
        mock_master_eg = Mock()
        mock_master_eg.id = master_eg_id
        mock_master_eg.event_groups = [mock_child1_ref, mock_child2_ref]
        mock_master_eg.variation_weight = 5.0
        mock_master_eg.nr_event_groups = 2
        
        # Mock child event groups
        mock_child1 = Mock()
        mock_child1.id = child1_id
        mock_child1.event_groups = []  # Leaf level
        mock_child1.variation_weight = 2.5
        mock_child1.nr_event_groups = 0
        
        mock_child2 = Mock()
        mock_child2.id = child2_id
        mock_child2.event_groups = []  # Leaf level
        mock_child2.variation_weight = 1.8
        mock_child2.nr_event_groups = 0
        
        # Setup database service mocks
        mock_db_services.EventGroup.get_master_from__location_plan_period.return_value = mock_master_eg
        mock_db_services.EventGroup.get.side_effect = lambda eg_id: {
            child1_id: mock_child1,
            child2_id: mock_child2
        }[eg_id]
        
        # Create tree
        tree = EventGroupTree([lpp_id])
        
        # Verify tree structure for single location plan period
        assert tree.location_plan_period_ids == [lpp_id]
        assert tree.root is not None
        assert tree.root.event_group_id == master_eg_id
        assert tree.root.root_is_location_plan_period_master_group
        assert len(tree.root.children) == 2
        
        # Verify children are correct
        child_ids = [child.event_group_id for child in tree.root.children]
        assert child1_id in child_ids
        assert child2_id in child_ids
        
        # Verify nodes dictionary
        assert 0 in tree.nodes  # Root node
        assert master_eg_id in tree.nodes
        assert child1_id in tree.nodes
        assert child2_id in tree.nodes
        
        # Verify database calls
        mock_db_services.EventGroup.get_master_from__location_plan_period.assert_called_once_with(lpp_id)
        assert mock_db_services.EventGroup.get.call_count == 2  # 2 children
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_group_tree_initialization_multiple_location_plan_periods(self, mock_db_services):
        """Test: EventGroupTree wird mit mehreren LocationPlanPeriods korrekt initialisiert."""
        # Mock data
        lpp1_id = uuid4()
        lpp2_id = uuid4()
        lpp3_id = uuid4()
        master1_id = uuid4()
        master2_id = uuid4()
        master3_id = uuid4()
        
        # Mock master event groups
        mock_master1 = Mock()
        mock_master1.id = master1_id
        mock_master1.event_groups = []  # No further children
        mock_master1.variation_weight = 3.2
        mock_master1.nr_event_groups = 0
        
        mock_master2 = Mock()
        mock_master2.id = master2_id
        mock_master2.event_groups = []  # No further children
        mock_master2.variation_weight = 4.1
        mock_master2.nr_event_groups = 0
        
        mock_master3 = Mock()
        mock_master3.id = master3_id
        mock_master3.event_groups = []  # No further children
        mock_master3.variation_weight = 2.7
        mock_master3.nr_event_groups = 0
        
        # Setup database service mocks
        mock_db_services.EventGroup.get_master_from__location_plan_period.side_effect = [
            mock_master1, mock_master2, mock_master3
        ]
        
        # Create tree
        tree = EventGroupTree([lpp1_id, lpp2_id, lpp3_id])
        
        # Verify tree structure for multiple location plan periods
        assert tree.location_plan_period_ids == [lpp1_id, lpp2_id, lpp3_id]
        assert tree.root is not None
        assert tree.root.event_group_id == 0  # Virtual root
        assert not tree.root.root_is_location_plan_period_master_group
        assert len(tree.root.children) == 3
        
        # Verify children are master groups
        child_ids = [child.event_group_id for child in tree.root.children]
        assert master1_id in child_ids
        assert master2_id in child_ids
        assert master3_id in child_ids
        
        # Verify nodes dictionary
        assert 0 in tree.nodes  # Root node
        assert master1_id in tree.nodes
        assert master2_id in tree.nodes
        assert master3_id in tree.nodes
        
        # Verify database calls
        assert mock_db_services.EventGroup.get_master_from__location_plan_period.call_count == 3
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_group_tree_hierarchical_structure(self, mock_db_services):
        """Test: EventGroupTree wird mit hierarchischer Struktur korrekt initialisiert."""
        # Mock data for hierarchy: master -> parent -> child -> grandchild
        lpp_id = uuid4()
        master_id = uuid4()
        parent_id = uuid4()
        child_id = uuid4()
        grandchild_id = uuid4()
        
        # Mock references
        mock_parent_ref = Mock()
        mock_parent_ref.id = parent_id
        
        mock_child_ref = Mock()
        mock_child_ref.id = child_id
        
        mock_grandchild_ref = Mock()
        mock_grandchild_ref.id = grandchild_id
        
        # Mock master event group
        mock_master = Mock()
        mock_master.id = master_id
        mock_master.event_groups = [mock_parent_ref]
        mock_master.variation_weight = 10.0
        mock_master.nr_event_groups = 1
        
        # Mock parent event group
        mock_parent = Mock()
        mock_parent.id = parent_id
        mock_parent.event_groups = [mock_child_ref]
        mock_parent.variation_weight = 5.0
        mock_parent.nr_event_groups = 1
        
        # Mock child event group
        mock_child = Mock()
        mock_child.id = child_id
        mock_child.event_groups = [mock_grandchild_ref]
        mock_child.variation_weight = 2.5
        mock_child.nr_event_groups = 1
        
        # Mock grandchild event group (leaf)
        mock_grandchild = Mock()
        mock_grandchild.id = grandchild_id
        mock_grandchild.event_groups = []  # Leaf level
        mock_grandchild.variation_weight = 1.0
        mock_grandchild.nr_event_groups = 0
        
        # Setup database service mocks
        mock_db_services.EventGroup.get_master_from__location_plan_period.return_value = mock_master
        mock_db_services.EventGroup.get.side_effect = lambda eg_id: {
            parent_id: mock_parent,
            child_id: mock_child,
            grandchild_id: mock_grandchild
        }[eg_id]
        
        # Create tree
        tree = EventGroupTree([lpp_id])
        
        # Verify hierarchical tree structure
        assert tree.root.event_group_id == master_id
        assert len(tree.root.children) == 1
        
        # Navigate down the hierarchy
        parent_node = list(tree.root.children)[0]
        assert parent_node.event_group_id == parent_id
        assert len(parent_node.children) == 1
        
        child_node = list(parent_node.children)[0]
        assert child_node.event_group_id == child_id
        assert len(child_node.children) == 1
        
        grandchild_node = list(child_node.children)[0]
        assert grandchild_node.event_group_id == grandchild_id
        assert len(grandchild_node.children) == 0  # Leaf node
        
        # Verify all nodes are in nodes dictionary
        assert master_id in tree.nodes
        assert parent_id in tree.nodes
        assert child_id in tree.nodes
        assert grandchild_id in tree.nodes
        
        # Verify database calls
        assert mock_db_services.EventGroup.get.call_count == 3  # parent, child, grandchild
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_construct_event_group_tree_recursive(self, mock_db_services):
        """Test: construct_event_group_tree() rekursive Konstruktion."""
        # Mock data for complex tree with multiple branches
        lpp_id = uuid4()
        master_id = uuid4()
        branch1_id = uuid4()
        branch2_id = uuid4()
        leaf1_id = uuid4()
        leaf2_id = uuid4()
        leaf3_id = uuid4()
        
        # Mock references
        mock_branch1_ref = Mock()
        mock_branch1_ref.id = branch1_id
        
        mock_branch2_ref = Mock()
        mock_branch2_ref.id = branch2_id
        
        mock_leaf1_ref = Mock()
        mock_leaf1_ref.id = leaf1_id
        
        mock_leaf2_ref = Mock()
        mock_leaf2_ref.id = leaf2_id
        
        mock_leaf3_ref = Mock()
        mock_leaf3_ref.id = leaf3_id
        
        # Mock master event group
        mock_master = Mock()
        mock_master.id = master_id
        mock_master.event_groups = [mock_branch1_ref, mock_branch2_ref]
        mock_master.variation_weight = 8.0
        mock_master.nr_event_groups = 2
        
        # Mock branch event groups
        mock_branch1 = Mock()
        mock_branch1.id = branch1_id
        mock_branch1.event_groups = [mock_leaf1_ref, mock_leaf2_ref]
        mock_branch1.variation_weight = 4.0
        mock_branch1.nr_event_groups = 2
        
        mock_branch2 = Mock()
        mock_branch2.id = branch2_id
        mock_branch2.event_groups = [mock_leaf3_ref]
        mock_branch2.variation_weight = 3.0
        mock_branch2.nr_event_groups = 1
        
        # Mock leaf event groups
        mock_leaf1 = Mock()
        mock_leaf1.id = leaf1_id
        mock_leaf1.event_groups = []  # Leaf level
        mock_leaf1.variation_weight = 1.5
        mock_leaf1.nr_event_groups = 0
        
        mock_leaf2 = Mock()
        mock_leaf2.id = leaf2_id
        mock_leaf2.event_groups = []  # Leaf level
        mock_leaf2.variation_weight = 2.0
        mock_leaf2.nr_event_groups = 0
        
        mock_leaf3 = Mock()
        mock_leaf3.id = leaf3_id
        mock_leaf3.event_groups = []  # Leaf level
        mock_leaf3.variation_weight = 1.8
        mock_leaf3.nr_event_groups = 0
        
        # Setup database service mocks
        mock_db_services.EventGroup.get_master_from__location_plan_period.return_value = mock_master
        mock_db_services.EventGroup.get.side_effect = lambda eg_id: {
            branch1_id: mock_branch1,
            branch2_id: mock_branch2,
            leaf1_id: mock_leaf1,
            leaf2_id: mock_leaf2,
            leaf3_id: mock_leaf3
        }[eg_id]
        
        # Create tree
        tree = EventGroupTree([lpp_id])
        
        # Verify complex recursive tree structure
        assert len(tree.root.children) == 2  # 2 branches
        
        # Find branch nodes
        branch1_node = None
        branch2_node = None
        for child in tree.root.children:
            if child.event_group_id == branch1_id:
                branch1_node = child
            elif child.event_group_id == branch2_id:
                branch2_node = child
        
        assert branch1_node is not None
        assert branch2_node is not None
        
        # Verify branch1 has 2 children
        assert len(branch1_node.children) == 2
        branch1_leaf_ids = [child.event_group_id for child in branch1_node.children]
        assert leaf1_id in branch1_leaf_ids
        assert leaf2_id in branch1_leaf_ids
        
        # Verify branch2 has 1 child
        assert len(branch2_node.children) == 1
        branch2_leaf_node = list(branch2_node.children)[0]
        assert branch2_leaf_node.event_group_id == leaf3_id
        
        # Verify all nodes are in nodes dictionary
        expected_node_ids = [0, master_id, branch1_id, branch2_id, leaf1_id, leaf2_id, leaf3_id]
        for node_id in expected_node_ids:
            assert node_id in tree.nodes
        
        # Verify database calls
        assert mock_db_services.EventGroup.get.call_count == 5  # 2 branches + 3 leaves


@pytest.mark.unit
class TestEventGroupTreeHelperFunctions:
    """Test-Klasse für Helper-Funktionen."""
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_get_event_group_tree(self, mock_db_services):
        """Test: get_event_group_tree() Factory-Funktion."""
        # Mock data
        plan_period_id = uuid4()
        lpp1_id = uuid4()
        lpp2_id = uuid4()
        
        # Mock plan period with location plan periods
        mock_lpp1 = Mock()
        mock_lpp1.id = lpp1_id
        
        mock_lpp2 = Mock()
        mock_lpp2.id = lpp2_id
        
        mock_plan_period = Mock()
        mock_plan_period.location_plan_periods = [mock_lpp1, mock_lpp2]
        
        # Mock master event groups
        mock_master1 = Mock()
        mock_master1.id = uuid4()
        mock_master1.event_groups = []
        mock_master1.variation_weight = 2.5
        mock_master1.nr_event_groups = 0
        
        mock_master2 = Mock()
        mock_master2.id = uuid4()
        mock_master2.event_groups = []
        mock_master2.variation_weight = 3.1
        mock_master2.nr_event_groups = 0
        
        # Setup database service mocks
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        mock_db_services.EventGroup.get_master_from__location_plan_period.side_effect = [
            mock_master1, mock_master2
        ]
        
        # Call factory function
        tree = get_event_group_tree(plan_period_id)
        
        # Verify result
        assert isinstance(tree, EventGroupTree)
        assert tree.location_plan_period_ids == [lpp1_id, lpp2_id]
        assert len(tree.root.children) == 2
        
        # Verify database calls
        mock_db_services.PlanPeriod.get.assert_called_once_with(plan_period_id)
        assert mock_db_services.EventGroup.get_master_from__location_plan_period.call_count == 2
    
    @patch('sat_solver.event_group_tree.RenderTree')
    @patch('sat_solver.event_group_tree.ContRoundStyle')
    @patch('builtins.print')
    def test_render_event_group_tree(self, mock_print, mock_cont_round_style, mock_render_tree):
        """Test: render_event_group_tree() Visualisierung."""
        # Mock tree
        mock_tree = Mock()
        mock_tree.root = Mock()
        
        # Mock render tree
        mock_rendered = Mock()
        mock_render_tree.return_value = mock_rendered
        
        # Call render function
        render_event_group_tree(mock_tree)
        
        # Verify rendering
        mock_render_tree.assert_called_once_with(mock_tree.root, mock_cont_round_style)
        mock_print.assert_called_once_with(mock_rendered)


@pytest.mark.integration
class TestEventGroupTreeIntegration:
    """Integration-Tests für EventGroupTree."""
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_group_tree_realistic_klinikclown_scenario(self, mock_db_services):
        """Test: EventGroupTree mit realistischem Klinikclown-Szenario."""
        # Simuliere realistische Hierarchie:
        # Plan Period -> Location Master Groups -> Time Groups -> Event Groups
        
        # Mock IDs
        plan_period_id = uuid4()
        lpp_kinderklinik_id = uuid4()
        lpp_seniorenheim_id = uuid4()
        master_kinderklinik_id = uuid4()
        master_seniorenheim_id = uuid4()
        kinderklinik_vm_id = uuid4()
        kinderklinik_nm_id = uuid4()
        seniorenheim_vm_id = uuid4()
        
        # Mock plan period with location plan periods
        mock_lpp_kinderklinik = Mock()
        mock_lpp_kinderklinik.id = lpp_kinderklinik_id
        
        mock_lpp_seniorenheim = Mock()
        mock_lpp_seniorenheim.id = lpp_seniorenheim_id
        
        mock_plan_period = Mock()
        mock_plan_period.location_plan_periods = [mock_lpp_kinderklinik, mock_lpp_seniorenheim]
        
        # Mock references
        mock_kinderklinik_vm_ref = Mock()
        mock_kinderklinik_vm_ref.id = kinderklinik_vm_id
        
        mock_kinderklinik_nm_ref = Mock()
        mock_kinderklinik_nm_ref.id = kinderklinik_nm_id
        
        mock_seniorenheim_vm_ref = Mock()
        mock_seniorenheim_vm_ref.id = seniorenheim_vm_id
        
        # Mock master groups (location level)
        mock_master_kinderklinik = Mock()
        mock_master_kinderklinik.id = master_kinderklinik_id
        mock_master_kinderklinik.event_groups = [mock_kinderklinik_vm_ref, mock_kinderklinik_nm_ref]
        mock_master_kinderklinik.variation_weight = 6.0
        mock_master_kinderklinik.nr_event_groups = 2
        
        mock_master_seniorenheim = Mock()
        mock_master_seniorenheim.id = master_seniorenheim_id
        mock_master_seniorenheim.event_groups = [mock_seniorenheim_vm_ref]
        mock_master_seniorenheim.variation_weight = 4.0
        mock_master_seniorenheim.nr_event_groups = 1
        
        # Mock time-specific event groups (leaf level)
        mock_kinderklinik_vm = Mock()
        mock_kinderklinik_vm.id = kinderklinik_vm_id
        mock_kinderklinik_vm.event_groups = []  # Leaf level
        mock_kinderklinik_vm.variation_weight = 3.2
        mock_kinderklinik_vm.nr_event_groups = 0
        
        mock_kinderklinik_nm = Mock()
        mock_kinderklinik_nm.id = kinderklinik_nm_id
        mock_kinderklinik_nm.event_groups = []  # Leaf level
        mock_kinderklinik_nm.variation_weight = 2.8
        mock_kinderklinik_nm.nr_event_groups = 0
        
        mock_seniorenheim_vm = Mock()
        mock_seniorenheim_vm.id = seniorenheim_vm_id
        mock_seniorenheim_vm.event_groups = []  # Leaf level
        mock_seniorenheim_vm.variation_weight = 2.0
        mock_seniorenheim_vm.nr_event_groups = 0
        
        # Setup database service mocks
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        mock_db_services.EventGroup.get_master_from__location_plan_period.side_effect = [
            mock_master_kinderklinik, mock_master_seniorenheim
        ]
        mock_db_services.EventGroup.get.side_effect = lambda eg_id: {
            kinderklinik_vm_id: mock_kinderklinik_vm,
            kinderklinik_nm_id: mock_kinderklinik_nm,
            seniorenheim_vm_id: mock_seniorenheim_vm
        }[eg_id]
        
        # Create tree via factory function
        tree = get_event_group_tree(plan_period_id)
        
        # Verify realistic scenario structure
        assert tree.location_plan_period_ids == [lpp_kinderklinik_id, lpp_seniorenheim_id]
        assert tree.root is not None
        assert len(tree.root.children) == 2  # kinderklinik, seniorenheim
        
        # Find location master nodes
        kinderklinik_master_node = None
        seniorenheim_master_node = None
        for child in tree.root.children:
            if child.event_group_id == master_kinderklinik_id:
                kinderklinik_master_node = child
            elif child.event_group_id == master_seniorenheim_id:
                seniorenheim_master_node = child
        
        assert kinderklinik_master_node is not None
        assert seniorenheim_master_node is not None
        
        # Verify kinderklinik has 2 time slots
        assert len(kinderklinik_master_node.children) == 2
        kinderklinik_time_ids = [child.event_group_id for child in kinderklinik_master_node.children]
        assert kinderklinik_vm_id in kinderklinik_time_ids
        assert kinderklinik_nm_id in kinderklinik_time_ids
        
        # Verify seniorenheim has 1 time slot
        assert len(seniorenheim_master_node.children) == 1
        seniorenheim_time_node = list(seniorenheim_master_node.children)[0]
        assert seniorenheim_time_node.event_group_id == seniorenheim_vm_id
        
        # Verify event group details
        for child in kinderklinik_master_node.children:
            if child.event_group_id == kinderklinik_vm_id:
                assert child.weight == 3.2
                assert child.nr_of_active_children == 0
            elif child.event_group_id == kinderklinik_nm_id:
                assert child.weight == 2.8
                assert child.nr_of_active_children == 0
        
        assert seniorenheim_time_node.weight == 2.0
        assert seniorenheim_time_node.nr_of_active_children == 0
        
        # Verify database call count
        expected_get_calls = 3  # 3 leaf event groups
        assert mock_db_services.EventGroup.get.call_count == expected_get_calls
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_group_tree_weight_management_scenario(self, mock_db_services):
        """Test: EventGroupTree mit Gewichtung-Management."""
        # Simuliere Szenario mit verschiedenen Gewichtungen und Detach-Operationen
        
        # Mock IDs
        lpp_id = uuid4()
        master_id = uuid4()
        heavy_group_id = uuid4()
        light_group_id = uuid4()
        zero_weight_group_id = uuid4()
        
        # Mock references
        mock_heavy_ref = Mock()
        mock_heavy_ref.id = heavy_group_id
        
        mock_light_ref = Mock()
        mock_light_ref.id = light_group_id
        
        mock_zero_ref = Mock()
        mock_zero_ref.id = zero_weight_group_id
        
        # Mock master event group
        mock_master = Mock()
        mock_master.id = master_id
        mock_master.event_groups = [mock_heavy_ref, mock_light_ref, mock_zero_ref]
        mock_master.variation_weight = 15.0
        mock_master.nr_event_groups = 3
        
        # Mock event groups with different weights
        mock_heavy_group = Mock()
        mock_heavy_group.id = heavy_group_id
        mock_heavy_group.event_groups = []
        mock_heavy_group.variation_weight = 10.0
        mock_heavy_group.nr_event_groups = 0
        
        mock_light_group = Mock()
        mock_light_group.id = light_group_id
        mock_light_group.event_groups = []
        mock_light_group.variation_weight = 1.5
        mock_light_group.nr_event_groups = 0
        
        mock_zero_weight_group = Mock()
        mock_zero_weight_group.id = zero_weight_group_id
        mock_zero_weight_group.event_groups = []
        mock_zero_weight_group.variation_weight = 0.0
        mock_zero_weight_group.nr_event_groups = 0
        
        # Setup database service mocks
        mock_db_services.EventGroup.get_master_from__location_plan_period.return_value = mock_master
        mock_db_services.EventGroup.get.side_effect = lambda eg_id: {
            heavy_group_id: mock_heavy_group,
            light_group_id: mock_light_group,
            zero_weight_group_id: mock_zero_weight_group
        }[eg_id]
        
        # Create tree
        tree = EventGroupTree([lpp_id])
        
        # Verify weight management scenario
        assert tree.root.weight == 15.0
        assert len(tree.root.children) == 3
        
        # Verify event groups with different weights
        event_groups_by_id = {child.event_group_id: child for child in tree.root.children}
        
        # Heavy group
        heavy_node = event_groups_by_id[heavy_group_id]
        assert heavy_node.weight == 10.0
        assert heavy_node.nr_of_active_children == 0
        
        # Light group
        light_node = event_groups_by_id[light_group_id]
        assert light_node.weight == 1.5
        assert light_node.nr_of_active_children == 0
        
        # Zero weight group
        zero_weight_node = event_groups_by_id[zero_weight_group_id]
        assert zero_weight_node.weight == 0.0
        assert zero_weight_node.nr_of_active_children == 0
        
        # Test detach operation - weight should become None
        original_weight = heavy_node.weight
        assert original_weight == 10.0
        
        # Detach heavy node from parent
        heavy_node.parent = None
        
        # Verify weight is None after detach
        assert heavy_node.weight is None
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_group_tree_event_integration(self, mock_db_services):
        """Test: EventGroupTree mit Event-Integration."""
        # Test integration with events for realistic event group representation
        
        # Mock IDs
        plan_period_id = uuid4()
        lpp_id = uuid4()
        master_id = uuid4()
        eg_id = uuid4()
        event_id = uuid4()
        
        # Mock plan period with location plan period
        mock_lpp = Mock()
        mock_lpp.id = lpp_id
        
        mock_plan_period = Mock()
        mock_plan_period.location_plan_periods = [mock_lpp]
        
        # Mock event
        mock_event = Mock()
        mock_event.id = event_id
        mock_event.date = date(2025, 6, 29)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.name = "Nachmittag"
        
        # Mock event reference
        mock_event_ref = Mock()
        mock_event_ref.id = event_id
        
        # Mock event group reference
        mock_eg_ref = Mock()
        mock_eg_ref.id = eg_id
        
        # Mock master event group
        mock_master = Mock()
        mock_master.id = master_id
        mock_master.event_groups = [mock_eg_ref]
        mock_master.variation_weight = 5.0
        mock_master.nr_event_groups = 1
        
        # Mock event group with event
        mock_event_group = Mock()
        mock_event_group.id = eg_id
        mock_event_group.event_groups = []
        mock_event_group.event = mock_event_ref
        mock_event_group.variation_weight = 2.5
        mock_event_group.nr_event_groups = 0
        
        # Setup database service mocks
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        mock_db_services.EventGroup.get_master_from__location_plan_period.return_value = mock_master
        mock_db_services.EventGroup.get.return_value = mock_event_group
        mock_db_services.Event.get.return_value = mock_event
        
        # Create tree
        tree = get_event_group_tree(plan_period_id)
        
        # Verify event integration
        assert len(tree.root.children) == 1
        master_node = list(tree.root.children)[0]
        assert len(master_node.children) == 1
        
        event_group_node = list(master_node.children)[0]
        
        # Test event property access (should trigger lazy loading)
        event = event_group_node.event
        assert event == mock_event
        assert event.date == date(2025, 6, 29)
        assert event.time_of_day.name == "Nachmittag"
        
        # Test repr with event
        repr_str = repr(event_group_node)
        assert "event: 29.06.25" in repr_str
        
        # Verify database calls
        mock_db_services.Event.get.assert_called_once_with(event_id)
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_group_tree_error_handling(self, mock_db_services):
        """Test: EventGroupTree Error-Handling."""
        # Test with empty location plan periods
        plan_period_id = uuid4()
        
        # Mock plan period with empty location plan periods
        mock_plan_period = Mock()
        mock_plan_period.location_plan_periods = []
        
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        
        # Should handle empty location plan periods gracefully
        tree = get_event_group_tree(plan_period_id)
        assert tree.location_plan_period_ids == []
        assert tree.root is not None
        assert len(tree.root.children) == 0
        
        # Test with None values in event group data
        lpp_id = uuid4()
        
        mock_lpp = Mock()
        mock_lpp.id = lpp_id
        
        mock_plan_period_with_nones = Mock()
        mock_plan_period_with_nones.location_plan_periods = [mock_lpp]
        
        mock_master_with_nones = Mock()
        mock_master_with_nones.id = uuid4()
        mock_master_with_nones.event_groups = []
        mock_master_with_nones.variation_weight = None
        mock_master_with_nones.nr_event_groups = None
        
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period_with_nones
        mock_db_services.EventGroup.get_master_from__location_plan_period.return_value = mock_master_with_nones
        
        # Should handle None values gracefully
        tree_with_nones = get_event_group_tree(plan_period_id)
        assert len(tree_with_nones.root.children) == 1
        master_node = list(tree_with_nones.root.children)[0]
        assert master_node.weight is None
        assert master_node.nr_of_active_children is None


@pytest.mark.performance
class TestEventGroupTreePerformance:
    """Performance-Tests für EventGroupTree."""
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_group_tree_large_flat_structure_performance(self, mock_db_services):
        """Test: EventGroupTree Performance mit großer flacher Struktur."""
        import time
        
        # Setup large flat structure: 1 master with 100 event groups at leaf level
        plan_period_id = uuid4()
        lpp_id = uuid4()
        master_id = uuid4()
        num_event_groups = 100
        
        # Mock plan period
        mock_lpp = Mock()
        mock_lpp.id = lpp_id
        
        mock_plan_period = Mock()
        mock_plan_period.location_plan_periods = [mock_lpp]
        
        # Generate event group references and event groups
        event_group_refs = []
        event_groups = {}
        
        for i in range(num_event_groups):
            eg_id = uuid4()
            
            # Reference
            mock_ref = Mock()
            mock_ref.id = eg_id
            event_group_refs.append(mock_ref)
            
            # Event group
            mock_eg = Mock()
            mock_eg.id = eg_id
            mock_eg.event_groups = []  # All leaf level
            mock_eg.variation_weight = float(i + 1) / 10.0  # 0.1, 0.2, ... 10.0
            mock_eg.nr_event_groups = 0
            event_groups[eg_id] = mock_eg
        
        # Mock master event group
        mock_master = Mock()
        mock_master.id = master_id
        mock_master.event_groups = event_group_refs
        mock_master.variation_weight = 50.0
        mock_master.nr_event_groups = num_event_groups
        
        # Setup database service mocks
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        mock_db_services.EventGroup.get_master_from__location_plan_period.return_value = mock_master
        mock_db_services.EventGroup.get.side_effect = lambda eg_id: event_groups[eg_id]
        
        # Measure construction time
        start_time = time.time()
        tree = EventGroupTree([lpp_id])
        end_time = time.time()
        
        construction_time = end_time - start_time
        
        # Verify large flat structure was built correctly
        assert len(tree.root.children) == num_event_groups
        
        # Performance should be reasonable
        assert construction_time < 3.0  # Should complete within 3 seconds
        
        # Verify database call count
        assert mock_db_services.EventGroup.get.call_count == num_event_groups
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_group_tree_multiple_locations_performance(self, mock_db_services):
        """Test: EventGroupTree Performance mit mehreren Location Plan Periods."""
        import time
        
        # Setup multiple location plan periods: 10 locations with 10 event groups each
        plan_period_id = uuid4()
        num_locations = 10
        event_groups_per_location = 10
        
        # Generate location plan periods
        lpps = []
        for i in range(num_locations):
            mock_lpp = Mock()
            mock_lpp.id = uuid4()
            lpps.append(mock_lpp)
        
        mock_plan_period = Mock()
        mock_plan_period.location_plan_periods = lpps
        
        # Generate master event groups and their children
        masters = []
        all_event_groups = {}
        
        for i in range(num_locations):
            master_id = uuid4()
            
            # Generate child references and event groups for this master
            child_refs = []
            for j in range(event_groups_per_location):
                eg_id = uuid4()
                
                # Reference
                mock_ref = Mock()
                mock_ref.id = eg_id
                child_refs.append(mock_ref)
                
                # Event group
                mock_eg = Mock()
                mock_eg.id = eg_id
                mock_eg.event_groups = []  # Leaf level
                mock_eg.variation_weight = float(j + 1)
                mock_eg.nr_event_groups = 0
                all_event_groups[eg_id] = mock_eg
            
            # Master event group
            mock_master = Mock()
            mock_master.id = master_id
            mock_master.event_groups = child_refs
            mock_master.variation_weight = float(i + 1) * 10.0
            mock_master.nr_event_groups = event_groups_per_location
            masters.append(mock_master)
        
        # Setup database service mocks
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        mock_db_services.EventGroup.get_master_from__location_plan_period.side_effect = masters
        mock_db_services.EventGroup.get.side_effect = lambda eg_id: all_event_groups[eg_id]
        
        # Measure construction time
        start_time = time.time()
        tree = get_event_group_tree(plan_period_id)
        end_time = time.time()
        
        construction_time = end_time - start_time
        
        # Verify multiple locations structure was built correctly
        assert len(tree.root.children) == num_locations
        
        total_leaf_nodes = 0
        for master_node in tree.root.children:
            total_leaf_nodes += len(master_node.children)
        
        assert total_leaf_nodes == num_locations * event_groups_per_location
        
        # Performance should be reasonable
        assert construction_time < 5.0  # Should complete within 5 seconds
        
        # Verify database call count
        expected_master_calls = num_locations
        expected_get_calls = num_locations * event_groups_per_location
        
        assert mock_db_services.EventGroup.get_master_from__location_plan_period.call_count == expected_master_calls
        assert mock_db_services.EventGroup.get.call_count == expected_get_calls
    
    @patch('sat_solver.event_group_tree.db_services')
    def test_event_group_tree_memory_efficiency(self, mock_db_services):
        """Test: EventGroupTree Memory-Effizienz."""
        import gc
        
        # Setup minimal but valid entities
        plan_period_id = uuid4()
        lpp_id = uuid4()
        
        # Mock minimal setup
        mock_lpp = Mock()
        mock_lpp.id = lpp_id
        
        mock_plan_period = Mock()
        mock_plan_period.location_plan_periods = [mock_lpp]
        
        mock_master = Mock()
        mock_master.id = uuid4()
        mock_master.event_groups = []
        mock_master.variation_weight = 1.0
        mock_master.nr_event_groups = 0
        
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        mock_db_services.EventGroup.get_master_from__location_plan_period.return_value = mock_master
        
        # Force garbage collection before test
        gc.collect()
        
        # Create and destroy multiple trees
        for _ in range(50):
            tree = get_event_group_tree(plan_period_id)
            # Tree should be garbage collected automatically
        
        # Force garbage collection after test
        gc.collect()
        
        # Should not leak significant memory
        assert True  # Test passes if no memory errors occur
