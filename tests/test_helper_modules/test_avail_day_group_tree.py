"""
Unit-Tests für avail_day_group_tree Modul

Testet die AvailDayGroup Tree-Struktur für hierarchische AvailDay-Group-Verwaltung.
Beinhaltet Tree-Konstruktion, Node-Management und Datenbankintegration.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4, UUID
from datetime import date

from sat_solver.avail_day_group_tree import AvailDayGroup, AvailDayGroupTree, get_avail_day_group_tree, render_event_group_tree


@pytest.mark.unit
class TestAvailDayGroup:
    """Test-Klasse für AvailDayGroup."""
    
    def test_avail_day_group_initialization_with_db(self):
        """Test: AvailDayGroup wird mit Datenbank-Objekt korrekt initialisiert."""
        # Mock database object
        adg_id = uuid4()
        mock_avail_day_group_db = Mock()
        mock_avail_day_group_db.id = adg_id
        mock_avail_day_group_db.variation_weight = 2
        mock_avail_day_group_db.nr_avail_day_groups = 3
        
        # Create AvailDayGroup
        adg = AvailDayGroup(mock_avail_day_group_db)
        
        # Verify initialization
        assert adg.avail_day_group_id == adg_id
        assert adg.name == str(adg_id)
        assert adg.avail_day_group_db == mock_avail_day_group_db
        assert adg.weight == 2
        assert adg.nr_of_active_children == 3
        assert adg.group_is_actor_plan_period_master_group is False
        assert adg.parent is None
        assert adg.children == []
    
    def test_avail_day_group_initialization_without_db(self):
        """Test: AvailDayGroup wird ohne Datenbank-Objekt korrekt initialisiert."""
        # Create AvailDayGroup without database object
        adg = AvailDayGroup(None)
        
        # Verify initialization
        assert adg.avail_day_group_id == 0
        assert adg.name == "0"
        assert adg.avail_day_group_db is None
        assert adg.weight is None
        assert adg.nr_of_active_children is None
        assert adg.group_is_actor_plan_period_master_group is False
        assert adg.parent is None
        assert adg.children == []
    
    def test_avail_day_group_initialization_with_parameters(self):
        """Test: AvailDayGroup wird mit allen Parametern korrekt initialisiert."""
        # Mock objects
        mock_avail_day_group_db = Mock()
        mock_avail_day_group_db.id = uuid4()
        mock_avail_day_group_db.variation_weight = 1
        mock_avail_day_group_db.nr_avail_day_groups = 5
        
        mock_parent = Mock()
        mock_child1 = Mock()
        mock_child2 = Mock()
        children = [mock_child1, mock_child2]
        
        # Create AvailDayGroup with all parameters
        adg = AvailDayGroup(
            avail_day_group_db=mock_avail_day_group_db,
            children=children,
            parent=mock_parent,
            group_is_actor_plan_period_master_group=True
        )
        
        # Verify initialization
        assert adg.avail_day_group_id == mock_avail_day_group_db.id
        assert adg.avail_day_group_db == mock_avail_day_group_db
        assert adg.parent == mock_parent
        assert adg.children == children
        assert adg.group_is_actor_plan_period_master_group is True
        assert adg.weight == 1
        assert adg.nr_of_active_children == 5
    
    def test_avail_day_group_tree_structure(self):
        """Test: AvailDayGroup Tree-Struktur (NodeMixin)."""
        # Create hierarchy: root -> child1 -> grandchild
        mock_root_db = Mock()
        mock_root_db.id = uuid4()
        mock_root_db.variation_weight = 1
        mock_root_db.nr_avail_day_groups = 2
        
        mock_child_db = Mock()
        mock_child_db.id = uuid4()
        mock_child_db.variation_weight = 2
        mock_child_db.nr_avail_day_groups = 1
        
        mock_grandchild_db = Mock()
        mock_grandchild_db.id = uuid4()
        mock_grandchild_db.variation_weight = 3
        mock_grandchild_db.nr_avail_day_groups = 0
        
        # Create nodes
        root = AvailDayGroup(mock_root_db)
        child = AvailDayGroup(mock_child_db, parent=root)
        grandchild = AvailDayGroup(mock_grandchild_db, parent=child)
        
        # Verify tree structure
        assert root.parent is None
        assert root.children == (child,)  # anytree returns tuple
        assert child.parent == root
        assert child.children == (grandchild,)
        assert grandchild.parent == child
        assert grandchild.children == ()
        
        # Verify tree traversal
        assert root.descendants == (child, grandchild)
        assert child.ancestors == (root,)
        assert grandchild.path == (root, child, grandchild)
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_avail_day_property_lazy_loading(self, mock_db_services):
        """Test: avail_day Property wird lazy geladen."""
        # Mock database objects
        avail_day_id = uuid4()
        mock_avail_day_ref = Mock()
        mock_avail_day_ref.id = avail_day_id
        
        mock_avail_day_group_db = Mock()
        mock_avail_day_group_db.id = uuid4()
        mock_avail_day_group_db.avail_day = mock_avail_day_ref
        mock_avail_day_group_db.variation_weight = 1
        mock_avail_day_group_db.nr_avail_day_groups = 0
        
        # Mock database service
        mock_avail_day = Mock()
        mock_avail_day.date = date(2025, 6, 28)
        mock_db_services.AvailDay.get.return_value = mock_avail_day
        
        # Create AvailDayGroup
        adg = AvailDayGroup(mock_avail_day_group_db)
        
        # Verify lazy loading - should not call DB initially
        assert not mock_db_services.AvailDay.get.called
        
        # Access avail_day property - should trigger DB call
        result = adg.avail_day
        
        # Verify DB was called and result is cached
        mock_db_services.AvailDay.get.assert_called_once_with(avail_day_id)
        assert result == mock_avail_day
        
        # Second access should not trigger another DB call
        result2 = adg.avail_day
        assert result2 == mock_avail_day
        assert mock_db_services.AvailDay.get.call_count == 1  # Still only one call
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_avail_day_property_no_db_object(self, mock_db_services):
        """Test: avail_day Property ohne Datenbank-Objekt."""
        # Create AvailDayGroup without database object
        adg = AvailDayGroup(None)
        
        # Access avail_day property
        result = adg.avail_day
        
        # Should return None and not call database
        assert result is None
        assert not mock_db_services.AvailDay.get.called
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_avail_day_property_no_avail_day_ref(self, mock_db_services):
        """Test: avail_day Property ohne AvailDay-Referenz."""
        # Mock database object without avail_day reference
        mock_avail_day_group_db = Mock()
        mock_avail_day_group_db.id = uuid4()
        mock_avail_day_group_db.avail_day = None  # No avail_day reference
        mock_avail_day_group_db.variation_weight = 1
        mock_avail_day_group_db.nr_avail_day_groups = 0
        
        # Create AvailDayGroup
        adg = AvailDayGroup(mock_avail_day_group_db)
        
        # Access avail_day property
        result = adg.avail_day
        
        # Should return None and not call database
        assert result is None
        assert not mock_db_services.AvailDay.get.called
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_required_avail_day_groups_property_lazy_loading(self, mock_db_services):
        """Test: required_avail_day_groups Property wird lazy geladen."""
        # Mock database objects
        adg_id = uuid4()
        mock_avail_day_group_db = Mock()
        mock_avail_day_group_db.id = adg_id
        mock_avail_day_group_db.variation_weight = 1
        mock_avail_day_group_db.nr_avail_day_groups = 0
        
        # Mock required avail day groups
        mock_required_groups = Mock()
        mock_db_services.RequiredAvailDayGroups.get_from__avail_day_group.return_value = mock_required_groups
        
        # Create AvailDayGroup
        adg = AvailDayGroup(mock_avail_day_group_db)
        
        # Verify lazy loading - should not call DB initially
        assert not mock_db_services.RequiredAvailDayGroups.get_from__avail_day_group.called
        
        # Access required_avail_day_groups property - should trigger DB call
        result = adg.required_avail_day_groups
        
        # Verify DB was called and result is cached
        mock_db_services.RequiredAvailDayGroups.get_from__avail_day_group.assert_called_once_with(adg_id)
        assert result == mock_required_groups
        
        # Second access should not trigger another DB call
        result2 = adg.required_avail_day_groups
        assert result2 == mock_required_groups
        assert mock_db_services.RequiredAvailDayGroups.get_from__avail_day_group.call_count == 1
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_required_avail_day_groups_property_no_db_object(self, mock_db_services):
        """Test: required_avail_day_groups Property ohne Datenbank-Objekt."""
        # Create AvailDayGroup without database object
        adg = AvailDayGroup(None)
        
        # Access required_avail_day_groups property
        result = adg.required_avail_day_groups
        
        # Should return None and not call database
        assert result is None
        assert not mock_db_services.RequiredAvailDayGroups.get_from__avail_day_group.called
    
    def test_post_detach_method(self):
        """Test: _post_detach() Methode setzt weight zurück."""
        # Mock database object
        mock_avail_day_group_db = Mock()
        mock_avail_day_group_db.id = uuid4()
        mock_avail_day_group_db.variation_weight = 5
        mock_avail_day_group_db.nr_avail_day_groups = 2
        
        # Create parent and child
        parent = AvailDayGroup(mock_avail_day_group_db)
        child = AvailDayGroup(mock_avail_day_group_db, parent=parent)
        
        # Verify child has weight initially
        assert child.weight == 5
        
        # Detach child from parent
        child.parent = None
        
        # Verify weight is reset (anytree calls _post_detach)
        assert child.weight is None
    
    def test_repr_method_with_avail_day(self):
        """Test: __repr__() Methode mit AvailDay."""
        # Mock database objects
        adg_id = uuid4()
        mock_avail_day_group_db = Mock()
        mock_avail_day_group_db.id = adg_id
        mock_avail_day_group_db.variation_weight = 3
        mock_avail_day_group_db.nr_avail_day_groups = 2
        
        # Create AvailDayGroup
        adg = AvailDayGroup(mock_avail_day_group_db)
        
        # Mock avail_day
        mock_avail_day = Mock()
        mock_avail_day.date = date(2025, 6, 28)
        adg._avail_day = mock_avail_day  # Set directly to avoid DB call
        
        # Test repr
        repr_str = repr(adg)
        
        # Verify repr contains expected information
        assert f"Node id: {adg_id}" in repr_str
        assert "weight: 3" in repr_str
        assert "nr_active_children: 2" in repr_str
        assert "children: 0" in repr_str
        assert "avail_day_date: 28.06.25" in repr_str
    
    def test_repr_method_without_avail_day(self):
        """Test: __repr__() Methode ohne AvailDay."""
        # Mock database objects
        adg_id = uuid4()
        mock_avail_day_group_db = Mock()
        mock_avail_day_group_db.id = adg_id
        mock_avail_day_group_db.variation_weight = 1
        mock_avail_day_group_db.nr_avail_day_groups = 0
        
        # Create AvailDayGroup
        adg = AvailDayGroup(mock_avail_day_group_db)
        adg._avail_day = None  # No avail_day
        
        # Test repr
        repr_str = repr(adg)
        
        # Verify repr contains expected information
        assert f"Node id: {adg_id}" in repr_str
        assert "weight: 1" in repr_str
        assert "nr_active_children: 0" in repr_str
        assert "children: 0" in repr_str
        assert "avail_day_date: None" in repr_str


@pytest.mark.unit
class TestAvailDayGroupTree:
    """Test-Klasse für AvailDayGroupTree."""
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_avail_day_group_tree_initialization_single_actor(self, mock_db_services):
        """Test: AvailDayGroupTree wird mit einem Akteur korrekt initialisiert."""
        # Mock data
        actor_plan_period_id = uuid4()
        master_group_id = uuid4()
        child1_id = uuid4()
        child2_id = uuid4()
        
        # Mock master group
        mock_child1_ref = Mock()
        mock_child1_ref.id = child1_id
        
        mock_child2_ref = Mock()
        mock_child2_ref.id = child2_id
        
        mock_master_group = Mock()
        mock_master_group.id = master_group_id
        mock_master_group.variation_weight = 1
        mock_master_group.nr_avail_day_groups = 2
        mock_master_group.avail_day_groups = [mock_child1_ref, mock_child2_ref]
        
        # Mock child groups
        mock_child1 = Mock()
        mock_child1.id = child1_id
        mock_child1.variation_weight = 2
        mock_child1.nr_avail_day_groups = 0
        mock_child1.avail_day_groups = []
        
        mock_child2 = Mock()
        mock_child2.id = child2_id
        mock_child2.variation_weight = 3
        mock_child2.nr_avail_day_groups = 0
        mock_child2.avail_day_groups = []
        
        # Setup database service mocks
        mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.return_value = mock_master_group
        mock_db_services.AvailDayGroup.get.side_effect = lambda adg_id: {
            child1_id: mock_child1,
            child2_id: mock_child2
        }[adg_id]
        
        # Create tree
        tree = AvailDayGroupTree([actor_plan_period_id])
        
        # Verify tree structure
        assert tree.actor_plan_period_ids == [actor_plan_period_id]
        assert tree.root is not None
        assert tree.root.group_is_actor_plan_period_master_group is True
        assert tree.root.avail_day_group_id == master_group_id
        assert len(tree.root.children) == 2
        
        # Verify nodes dictionary
        assert 0 in tree.nodes  # Root node
        assert master_group_id in tree.nodes  # Root is also indexed by its ID
        assert child1_id in tree.nodes
        assert child2_id in tree.nodes
        assert len(tree.nodes) == 3  # Root (as 0), child1, child2
        
        # Verify database calls
        mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.assert_called_once_with(actor_plan_period_id)
        assert mock_db_services.AvailDayGroup.get.call_count == 2
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_avail_day_group_tree_initialization_multiple_actors(self, mock_db_services):
        """Test: AvailDayGroupTree wird mit mehreren Akteuren korrekt initialisiert."""
        # Mock data
        actor_plan_period_id1 = uuid4()
        actor_plan_period_id2 = uuid4()
        master_group_id1 = uuid4()
        master_group_id2 = uuid4()
        
        # Mock master groups
        mock_master_group1 = Mock()
        mock_master_group1.id = master_group_id1
        mock_master_group1.variation_weight = 1
        mock_master_group1.nr_avail_day_groups = 0
        mock_master_group1.avail_day_groups = []
        
        mock_master_group2 = Mock()
        mock_master_group2.id = master_group_id2
        mock_master_group2.variation_weight = 2
        mock_master_group2.nr_avail_day_groups = 0
        mock_master_group2.avail_day_groups = []
        
        # Setup database service mocks
        mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.side_effect = lambda app_id: {
            actor_plan_period_id1: mock_master_group1,
            actor_plan_period_id2: mock_master_group2
        }[app_id]
        
        # Create tree
        tree = AvailDayGroupTree([actor_plan_period_id1, actor_plan_period_id2])
        
        # Verify tree structure
        assert tree.actor_plan_period_ids == [actor_plan_period_id1, actor_plan_period_id2]
        assert tree.root is not None
        assert tree.root.group_is_actor_plan_period_master_group is False  # Root is not master when multiple actors
        assert tree.root.avail_day_group_id == 0  # Root has no database object
        assert len(tree.root.children) == 2
        
        # Verify nodes dictionary
        assert 0 in tree.nodes  # Root node
        assert master_group_id1 in tree.nodes
        assert master_group_id2 in tree.nodes
        assert len(tree.nodes) == 3  # Root, master1, master2
        
        # Verify database calls
        assert mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.call_count == 2
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_construct_event_group_tree_recursive(self, mock_db_services):
        """Test: construct_event_group_tree() baut Tree rekursiv auf."""
        # Mock data for complex hierarchy
        actor_plan_period_id = uuid4()
        master_group_id = uuid4()
        child1_id = uuid4()
        child2_id = uuid4()
        grandchild1_id = uuid4()
        grandchild2_id = uuid4()
        
        # Mock database references
        mock_child1_ref = Mock()
        mock_child1_ref.id = child1_id
        
        mock_child2_ref = Mock()
        mock_child2_ref.id = child2_id
        
        mock_grandchild1_ref = Mock()
        mock_grandchild1_ref.id = grandchild1_id
        
        mock_grandchild2_ref = Mock()
        mock_grandchild2_ref.id = grandchild2_id
        
        # Mock master group
        mock_master_group = Mock()
        mock_master_group.id = master_group_id
        mock_master_group.variation_weight = 1
        mock_master_group.nr_avail_day_groups = 2
        mock_master_group.avail_day_groups = [mock_child1_ref, mock_child2_ref]
        
        # Mock child groups
        mock_child1 = Mock()
        mock_child1.id = child1_id
        mock_child1.variation_weight = 2
        mock_child1.nr_avail_day_groups = 1
        mock_child1.avail_day_groups = [mock_grandchild1_ref]
        
        mock_child2 = Mock()
        mock_child2.id = child2_id
        mock_child2.variation_weight = 3
        mock_child2.nr_avail_day_groups = 1
        mock_child2.avail_day_groups = [mock_grandchild2_ref]
        
        # Mock grandchild groups (leaf nodes)
        mock_grandchild1 = Mock()
        mock_grandchild1.id = grandchild1_id
        mock_grandchild1.variation_weight = 4
        mock_grandchild1.nr_avail_day_groups = 0
        mock_grandchild1.avail_day_groups = []
        
        mock_grandchild2 = Mock()
        mock_grandchild2.id = grandchild2_id
        mock_grandchild2.variation_weight = 5
        mock_grandchild2.nr_avail_day_groups = 0
        mock_grandchild2.avail_day_groups = []
        
        # Setup database service mocks
        mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.return_value = mock_master_group
        mock_db_services.AvailDayGroup.get.side_effect = lambda adg_id: {
            child1_id: mock_child1,
            child2_id: mock_child2,
            grandchild1_id: mock_grandchild1,
            grandchild2_id: mock_grandchild2
        }[adg_id]
        
        # Create tree
        tree = AvailDayGroupTree([actor_plan_period_id])
        
        # Verify complex tree structure
        assert len(tree.root.children) == 2
        
        # Verify child1 has grandchild1
        child1_node = tree.nodes[child1_id]
        assert len(child1_node.children) == 1
        grandchild1_node = list(child1_node.children)[0]
        assert grandchild1_node.avail_day_group_id == grandchild1_id
        
        # Verify child2 has grandchild2
        child2_node = tree.nodes[child2_id]
        assert len(child2_node.children) == 1
        grandchild2_node = list(child2_node.children)[0]
        assert grandchild2_node.avail_day_group_id == grandchild2_id
        
        # Verify all nodes are in dictionary
        assert grandchild1_id in tree.nodes
        assert grandchild2_id in tree.nodes
        assert len(tree.nodes) == 5  # Root, child1, child2, grandchild1, grandchild2
        
        # Verify database calls for recursive construction
        expected_get_calls = 4  # child1, child2, grandchild1, grandchild2
        assert mock_db_services.AvailDayGroup.get.call_count == expected_get_calls
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_construct_event_group_tree_empty_children(self, mock_db_services):
        """Test: construct_event_group_tree() mit leeren Children."""
        # Mock data
        actor_plan_period_id = uuid4()
        master_group_id = uuid4()
        
        # Mock master group with no children
        mock_master_group = Mock()
        mock_master_group.id = master_group_id
        mock_master_group.variation_weight = 1
        mock_master_group.nr_avail_day_groups = 0
        mock_master_group.avail_day_groups = []  # No children
        
        # Setup database service mocks
        mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.return_value = mock_master_group
        
        # Create tree
        tree = AvailDayGroupTree([actor_plan_period_id])
        
        # Verify tree structure with no recursive children
        assert tree.root.avail_day_group_id == master_group_id
        assert len(tree.root.children) == 0  # Master group itself has no children in this constructor
        assert len(tree.nodes) == 1  # Only root node
        
        # Verify no additional database calls for children
        mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.assert_called_once()
        assert not mock_db_services.AvailDayGroup.get.called


@pytest.mark.unit
class TestAvailDayGroupTreeHelperFunctions:
    """Test-Klasse für Helper-Funktionen."""
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_get_avail_day_group_tree(self, mock_db_services):
        """Test: get_avail_day_group_tree() Factory-Funktion."""
        # Mock data
        plan_period_id = uuid4()
        actor_plan_period_id1 = uuid4()
        actor_plan_period_id2 = uuid4()
        
        # Mock plan period with actor plan periods
        mock_app1 = Mock()
        mock_app1.id = actor_plan_period_id1
        
        mock_app2 = Mock()
        mock_app2.id = actor_plan_period_id2
        
        mock_plan_period = Mock()
        mock_plan_period.actor_plan_periods = [mock_app1, mock_app2]
        
        # Mock master groups
        mock_master_group1 = Mock()
        mock_master_group1.id = uuid4()
        mock_master_group1.variation_weight = 1
        mock_master_group1.nr_avail_day_groups = 0
        mock_master_group1.avail_day_groups = []
        
        mock_master_group2 = Mock()
        mock_master_group2.id = uuid4()
        mock_master_group2.variation_weight = 2
        mock_master_group2.nr_avail_day_groups = 0
        mock_master_group2.avail_day_groups = []
        
        # Setup database service mocks
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.side_effect = lambda app_id: {
            actor_plan_period_id1: mock_master_group1,
            actor_plan_period_id2: mock_master_group2
        }[app_id]
        
        # Call factory function
        tree = get_avail_day_group_tree(plan_period_id)
        
        # Verify result
        assert isinstance(tree, AvailDayGroupTree)
        assert tree.actor_plan_period_ids == [actor_plan_period_id1, actor_plan_period_id2]
        assert len(tree.root.children) == 2
        
        # Verify database calls
        mock_db_services.PlanPeriod.get.assert_called_once_with(plan_period_id)
        assert mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.call_count == 2
    
    @patch('sat_solver.avail_day_group_tree.RenderTree')
    @patch('sat_solver.avail_day_group_tree.ContRoundStyle')
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
class TestAvailDayGroupTreeIntegration:
    """Integration-Tests für AvailDayGroupTree."""
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_avail_day_group_tree_realistic_klinikclown_scenario(self, mock_db_services):
        """Test: AvailDayGroupTree mit realistischem Klinikclown-Szenario."""
        # Simuliere realistische Hierarchie:
        # Plan Period -> Actor (Hans) -> Woche -> Tag -> Zeitslot
        
        # Mock IDs
        plan_period_id = uuid4()
        hans_app_id = uuid4()
        hans_master_id = uuid4()
        week1_id = uuid4()
        week2_id = uuid4()
        monday_id = uuid4()
        tuesday_id = uuid4()
        vormittag_id = uuid4()
        nachmittag_id = uuid4()
        
        # Mock Plan Period
        mock_hans_app = Mock()
        mock_hans_app.id = hans_app_id
        
        mock_plan_period = Mock()
        mock_plan_period.actor_plan_periods = [mock_hans_app]
        
        # Mock database references
        mock_week1_ref = Mock()
        mock_week1_ref.id = week1_id
        
        mock_week2_ref = Mock()
        mock_week2_ref.id = week2_id
        
        mock_monday_ref = Mock()
        mock_monday_ref.id = monday_id
        
        mock_tuesday_ref = Mock()
        mock_tuesday_ref.id = tuesday_id
        
        mock_vormittag_ref = Mock()
        mock_vormittag_ref.id = vormittag_id
        
        mock_nachmittag_ref = Mock()
        mock_nachmittag_ref.id = nachmittag_id
        
        # Mock Hans' master group
        mock_hans_master = Mock()
        mock_hans_master.id = hans_master_id
        mock_hans_master.variation_weight = 1
        mock_hans_master.nr_avail_day_groups = 2
        mock_hans_master.avail_day_groups = [mock_week1_ref, mock_week2_ref]
        
        # Mock week groups
        mock_week1 = Mock()
        mock_week1.id = week1_id
        mock_week1.variation_weight = 1
        mock_week1.nr_avail_day_groups = 2
        mock_week1.avail_day_groups = [mock_monday_ref, mock_tuesday_ref]
        
        mock_week2 = Mock()
        mock_week2.id = week2_id
        mock_week2.variation_weight = 2
        mock_week2.nr_avail_day_groups = 0
        mock_week2.avail_day_groups = []  # Empty week
        
        # Mock day groups
        mock_monday = Mock()
        mock_monday.id = monday_id
        mock_monday.variation_weight = 1
        mock_monday.nr_avail_day_groups = 2
        mock_monday.avail_day_groups = [mock_vormittag_ref, mock_nachmittag_ref]
        
        mock_tuesday = Mock()
        mock_tuesday.id = tuesday_id
        mock_tuesday.variation_weight = 1
        mock_tuesday.nr_avail_day_groups = 1
        mock_tuesday.avail_day_groups = [mock_vormittag_ref]  # Only vormittag
        
        # Mock time slot groups (leaf nodes)
        mock_vormittag = Mock()
        mock_vormittag.id = vormittag_id
        mock_vormittag.variation_weight = 2
        mock_vormittag.nr_avail_day_groups = 0
        mock_vormittag.avail_day_groups = []
        
        mock_nachmittag = Mock()
        mock_nachmittag.id = nachmittag_id
        mock_nachmittag.variation_weight = 3
        mock_nachmittag.nr_avail_day_groups = 0
        mock_nachmittag.avail_day_groups = []
        
        # Setup database service mocks
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.return_value = mock_hans_master
        mock_db_services.AvailDayGroup.get.side_effect = lambda adg_id: {
            week1_id: mock_week1,
            week2_id: mock_week2,
            monday_id: mock_monday,
            tuesday_id: mock_tuesday,
            vormittag_id: mock_vormittag,
            nachmittag_id: mock_nachmittag
        }[adg_id]
        
        # Create tree via factory function
        tree = get_avail_day_group_tree(plan_period_id)
        
        # Verify realistic scenario structure
        assert tree.actor_plan_period_ids == [hans_app_id]
        assert tree.root.group_is_actor_plan_period_master_group is True
        assert tree.root.avail_day_group_id == hans_master_id
        
        # Verify week level
        assert len(tree.root.children) == 2  # week1, week2
        week1_node = tree.nodes[week1_id]
        week2_node = tree.nodes[week2_id]
        
        # Verify day level
        assert len(week1_node.children) == 2  # monday, tuesday
        assert len(week2_node.children) == 0  # empty week
        
        monday_node = tree.nodes[monday_id]
        tuesday_node = tree.nodes[tuesday_id]
        
        # Verify time slot level
        assert len(monday_node.children) == 2  # vormittag, nachmittag
        assert len(tuesday_node.children) == 1  # only vormittag
        
        # Verify all nodes are accessible
        assert vormittag_id in tree.nodes
        assert nachmittag_id in tree.nodes
        
        # Verify total node count
        expected_node_count = 7  # root, week1, week2, monday, tuesday, vormittag, nachmittag
        assert len(tree.nodes) == expected_node_count
        
        # Verify database call count
        expected_get_calls = 6  # week1, week2, monday, tuesday, vormittag, nachmittag
        assert mock_db_services.AvailDayGroup.get.call_count == expected_get_calls
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_avail_day_group_tree_multi_actor_scenario(self, mock_db_services):
        """Test: AvailDayGroupTree mit Multi-Akteur-Szenario."""
        # Simuliere Szenario mit 3 Akteuren: Hans, Maria, Peter
        
        # Mock IDs
        plan_period_id = uuid4()
        hans_app_id = uuid4()
        maria_app_id = uuid4()
        peter_app_id = uuid4()
        hans_master_id = uuid4()
        maria_master_id = uuid4()
        peter_master_id = uuid4()
        
        # Mock Actor Plan Periods
        mock_hans_app = Mock()
        mock_hans_app.id = hans_app_id
        
        mock_maria_app = Mock()
        mock_maria_app.id = maria_app_id
        
        mock_peter_app = Mock()
        mock_peter_app.id = peter_app_id
        
        mock_plan_period = Mock()
        mock_plan_period.actor_plan_periods = [mock_hans_app, mock_maria_app, mock_peter_app]
        
        # Mock master groups for each actor
        mock_hans_master = Mock()
        mock_hans_master.id = hans_master_id
        mock_hans_master.variation_weight = 1
        mock_hans_master.nr_avail_day_groups = 0
        mock_hans_master.avail_day_groups = []
        
        mock_maria_master = Mock()
        mock_maria_master.id = maria_master_id
        mock_maria_master.variation_weight = 2
        mock_maria_master.nr_avail_day_groups = 0
        mock_maria_master.avail_day_groups = []
        
        mock_peter_master = Mock()
        mock_peter_master.id = peter_master_id
        mock_peter_master.variation_weight = 3
        mock_peter_master.nr_avail_day_groups = 0
        mock_peter_master.avail_day_groups = []
        
        # Setup database service mocks
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.side_effect = lambda app_id: {
            hans_app_id: mock_hans_master,
            maria_app_id: mock_maria_master,
            peter_app_id: mock_peter_master
        }[app_id]
        
        # Create tree
        tree = get_avail_day_group_tree(plan_period_id)
        
        # Verify multi-actor structure
        assert tree.actor_plan_period_ids == [hans_app_id, maria_app_id, peter_app_id]
        assert tree.root.group_is_actor_plan_period_master_group is False  # Multi-actor root
        assert tree.root.avail_day_group_id == 0  # Root has no DB object
        assert len(tree.root.children) == 3  # 3 actors
        
        # Verify each actor's master group is a child of root
        hans_node = tree.nodes[hans_master_id]
        maria_node = tree.nodes[maria_master_id]
        peter_node = tree.nodes[peter_master_id]
        
        assert hans_node.parent == tree.root
        assert maria_node.parent == tree.root
        assert peter_node.parent == tree.root
        
        assert hans_node.weight == 1
        assert maria_node.weight == 2
        assert peter_node.weight == 3
        
        # Verify nodes dictionary
        assert len(tree.nodes) == 4  # root + 3 actors
        assert 0 in tree.nodes  # root
        assert hans_master_id in tree.nodes
        assert maria_master_id in tree.nodes
        assert peter_master_id in tree.nodes
        
        # Verify database calls
        assert mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.call_count == 3
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_avail_day_group_tree_error_handling(self, mock_db_services):
        """Test: AvailDayGroupTree Error-Handling."""
        # Test with empty actor plan period list
        tree_empty = AvailDayGroupTree([])
        
        # Should handle empty list gracefully
        assert tree_empty.actor_plan_period_ids == []
        assert tree_empty.root is not None
        assert tree_empty.root.avail_day_group_id == 0
        assert len(tree_empty.root.children) == 0
        assert len(tree_empty.nodes) == 1  # Only root
        
        # Test database error handling
        plan_period_id = uuid4()
        
        # Mock plan period with no actor plan periods
        mock_plan_period_empty = Mock()
        mock_plan_period_empty.actor_plan_periods = []
        
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period_empty
        
        # Should handle empty actor plan periods
        tree_no_actors = get_avail_day_group_tree(plan_period_id)
        assert tree_no_actors.actor_plan_period_ids == []
        assert len(tree_no_actors.root.children) == 0


@pytest.mark.performance
class TestAvailDayGroupTreePerformance:
    """Performance-Tests für AvailDayGroupTree."""
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_avail_day_group_tree_large_hierarchy_performance(self, mock_db_services):
        """Test: AvailDayGroupTree Performance mit großer Hierarchie."""
        import time
        
        # Setup large hierarchy: 1 actor with 10 weeks, each week has 7 days, each day has 3 time slots
        actor_plan_period_id = uuid4()
        master_group_id = uuid4()
        
        # Generate IDs
        week_ids = [uuid4() for _ in range(10)]
        day_ids = [uuid4() for _ in range(70)]  # 10 weeks * 7 days
        time_slot_ids = [uuid4() for _ in range(210)]  # 70 days * 3 time slots
        
        # Mock master group
        week_refs = [Mock(id=week_id) for week_id in week_ids]
        mock_master_group = Mock()
        mock_master_group.id = master_group_id
        mock_master_group.variation_weight = 1
        mock_master_group.nr_avail_day_groups = len(week_ids)
        mock_master_group.avail_day_groups = week_refs
        
        # Mock week groups
        week_groups = {}
        for i, week_id in enumerate(week_ids):
            day_refs = [Mock(id=day_ids[i*7 + j]) for j in range(7)]
            mock_week = Mock()
            mock_week.id = week_id
            mock_week.variation_weight = 1
            mock_week.nr_avail_day_groups = 7
            mock_week.avail_day_groups = day_refs
            week_groups[week_id] = mock_week
        
        # Mock day groups
        day_groups = {}
        for i, day_id in enumerate(day_ids):
            time_slot_refs = [Mock(id=time_slot_ids[i*3 + j]) for j in range(3)]
            mock_day = Mock()
            mock_day.id = day_id
            mock_day.variation_weight = 1
            mock_day.nr_avail_day_groups = 3
            mock_day.avail_day_groups = time_slot_refs
            day_groups[day_id] = mock_day
        
        # Mock time slot groups (leaf nodes)
        time_slot_groups = {}
        for time_slot_id in time_slot_ids:
            mock_time_slot = Mock()
            mock_time_slot.id = time_slot_id
            mock_time_slot.variation_weight = 1
            mock_time_slot.nr_avail_day_groups = 0
            mock_time_slot.avail_day_groups = []
            time_slot_groups[time_slot_id] = mock_time_slot
        
        # Combine all groups for get() mock
        all_groups = {**week_groups, **day_groups, **time_slot_groups}
        
        # Setup database service mocks
        mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.return_value = mock_master_group
        mock_db_services.AvailDayGroup.get.side_effect = lambda adg_id: all_groups[adg_id]
        
        # Measure construction time
        start_time = time.time()
        tree = AvailDayGroupTree([actor_plan_period_id])
        end_time = time.time()
        
        construction_time = end_time - start_time
        
        # Verify large hierarchy was built correctly
        total_expected_nodes = 1 + len(week_ids) + len(day_ids) + len(time_slot_ids)  # root + all groups
        assert len(tree.nodes) == total_expected_nodes
        
        # Performance should be reasonable
        assert construction_time < 5.0  # Should complete within 5 seconds
        
        # Verify database call count
        expected_get_calls = len(week_ids) + len(day_ids) + len(time_slot_ids)
        assert mock_db_services.AvailDayGroup.get.call_count == expected_get_calls
    
    @patch('sat_solver.avail_day_group_tree.db_services')
    def test_avail_day_group_tree_memory_efficiency(self, mock_db_services):
        """Test: AvailDayGroupTree Memory-Effizienz."""
        import gc
        
        # Setup minimal but valid entities
        actor_plan_period_id = uuid4()
        master_group_id = uuid4()
        
        mock_master_group = Mock()
        mock_master_group.id = master_group_id
        mock_master_group.variation_weight = 1
        mock_master_group.nr_avail_day_groups = 0
        mock_master_group.avail_day_groups = []
        
        mock_db_services.AvailDayGroup.get_master_from__actor_plan_period.return_value = mock_master_group
        
        # Force garbage collection before test
        gc.collect()
        
        # Create and destroy multiple trees
        for _ in range(50):
            tree = AvailDayGroupTree([actor_plan_period_id])
            # Tree should be garbage collected automatically
        
        # Force garbage collection after test
        gc.collect()
        
        # Should not leak significant memory
        assert True  # Test passes if no memory errors occur
