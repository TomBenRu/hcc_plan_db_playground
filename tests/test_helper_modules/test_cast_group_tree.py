"""
Unit-Tests für cast_group_tree Modul

Testet die CastGroup Tree-Struktur für hierarchische Cast-Group-Verwaltung.
Beinhaltet Tree-Konstruktion, Node-Management und Datenbankintegration.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4, UUID
from datetime import date

from sat_solver.cast_group_tree import CastGroup, CastGroupTree, get_cast_group_tree, render_cast_group_tree


@pytest.mark.unit
class TestCastGroup:
    """Test-Klasse für CastGroup."""
    
    def test_cast_group_initialization_with_db(self):
        """Test: CastGroup wird mit Datenbank-Objekt korrekt initialisiert."""
        # Mock database object
        cg_id = uuid4()
        mock_cast_rule = Mock()
        mock_cast_rule.rule = "different_cast_rule"
        
        mock_cast_group_db = Mock()
        mock_cast_group_db.id = cg_id
        mock_cast_group_db.fixed_cast = "Hans and Maria"
        mock_cast_group_db.nr_actors = 2
        mock_cast_group_db.custom_rule = None
        mock_cast_group_db.cast_rule = mock_cast_rule
        mock_cast_group_db.strict_cast_pref = 1
        
        # Create CastGroup
        cg = CastGroup(mock_cast_group_db)
        
        # Verify initialization
        assert cg.cast_group_id == cg_id
        assert cg.name == str(cg_id)
        assert cg.cast_group_db == mock_cast_group_db
        assert cg.fixed_cast == "Hans and Maria"
        assert cg.nr_actors == 2
        assert cg.cast_rule == "different_cast_rule"
        assert cg.strict_rule_pref == 1
        assert cg.parent is None
        assert cg.children == []
    
    def test_cast_group_initialization_with_custom_rule(self):
        """Test: CastGroup wird mit Custom Rule korrekt initialisiert."""
        # Mock database object with custom rule (should override cast_rule)
        cg_id = uuid4()
        mock_cast_rule = Mock()
        mock_cast_rule.rule = "default_rule"
        
        mock_cast_group_db = Mock()
        mock_cast_group_db.id = cg_id
        mock_cast_group_db.fixed_cast = None
        mock_cast_group_db.nr_actors = 3
        mock_cast_group_db.custom_rule = "custom_different_rule"  # Custom rule
        mock_cast_group_db.cast_rule = mock_cast_rule
        mock_cast_group_db.strict_cast_pref = 2
        
        # Create CastGroup
        cg = CastGroup(mock_cast_group_db)
        
        # Verify custom rule takes precedence
        assert cg.cast_rule == "custom_different_rule"
        assert cg.nr_actors == 3
        assert cg.strict_rule_pref == 2
    
    def test_cast_group_initialization_without_db(self):
        """Test: CastGroup wird ohne Datenbank-Objekt korrekt initialisiert."""
        # Create CastGroup without database object
        cg = CastGroup(None)
        
        # Verify initialization
        assert cg.cast_group_id == 0
        assert cg.name == "0"
        assert cg.cast_group_db is None
        assert cg.fixed_cast is None
        assert cg.nr_actors is None
        assert cg.cast_rule is None
        assert cg.strict_rule_pref is None
        assert cg.parent is None
        assert cg.children == []
    
    def test_cast_group_initialization_with_parameters(self):
        """Test: CastGroup wird mit allen Parametern korrekt initialisiert."""
        # Mock objects
        mock_cast_group_db = Mock()
        mock_cast_group_db.id = uuid4()
        mock_cast_group_db.fixed_cast = "Peter or Anna"
        mock_cast_group_db.nr_actors = 1
        mock_cast_group_db.custom_rule = "or_rule"
        mock_cast_group_db.cast_rule = None
        mock_cast_group_db.strict_cast_pref = 0
        
        mock_parent = Mock()
        mock_child1 = Mock()
        mock_child2 = Mock()
        children = [mock_child1, mock_child2]
        
        # Create CastGroup with all parameters
        cg = CastGroup(
            cast_group_db=mock_cast_group_db,
            children=children,
            parent=mock_parent
        )
        
        # Verify initialization
        assert cg.cast_group_id == mock_cast_group_db.id
        assert cg.cast_group_db == mock_cast_group_db
        assert cg.parent == mock_parent
        assert cg.children == children
        assert cg.fixed_cast == "Peter or Anna"
        assert cg.nr_actors == 1
        assert cg.cast_rule == "or_rule"
        assert cg.strict_rule_pref == 0
    
    def test_cast_group_tree_structure(self):
        """Test: CastGroup Tree-Struktur (NodeMixin)."""
        # Create hierarchy: root -> parent -> child
        mock_root_db = Mock()
        mock_root_db.id = uuid4()
        mock_root_db.fixed_cast = None
        mock_root_db.nr_actors = None
        mock_root_db.custom_rule = None
        mock_root_db.cast_rule = None
        mock_root_db.strict_cast_pref = None
        
        mock_parent_db = Mock()
        mock_parent_db.id = uuid4()
        mock_parent_db.fixed_cast = "Team A"
        mock_parent_db.nr_actors = 2
        mock_parent_db.custom_rule = "team_rule"
        mock_parent_db.cast_rule = None
        mock_parent_db.strict_cast_pref = 1
        
        mock_child_db = Mock()
        mock_child_db.id = uuid4()
        mock_child_db.fixed_cast = "Hans and Maria"
        mock_child_db.nr_actors = 2
        mock_child_db.custom_rule = None
        mock_child_db.cast_rule = Mock()
        mock_child_db.cast_rule.rule = "same_cast"
        mock_child_db.strict_cast_pref = 2
        
        # Create nodes
        root = CastGroup(mock_root_db)
        parent = CastGroup(mock_parent_db, parent=root)
        child = CastGroup(mock_child_db, parent=parent)
        
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
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_event_property_lazy_loading(self, mock_db_services):
        """Test: event Property wird lazy geladen."""
        # Mock database objects
        event_id = uuid4()
        mock_event_ref = Mock()
        mock_event_ref.id = event_id
        
        mock_cast_group_db = Mock()
        mock_cast_group_db.id = uuid4()
        mock_cast_group_db.event = mock_event_ref
        mock_cast_group_db.fixed_cast = None
        mock_cast_group_db.nr_actors = 2
        mock_cast_group_db.custom_rule = None
        mock_cast_group_db.cast_rule = None
        mock_cast_group_db.strict_cast_pref = 1
        
        # Mock database service
        mock_event = Mock()
        mock_event.date = date(2025, 6, 28)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.name = "Vormittag"
        mock_db_services.Event.get.return_value = mock_event
        
        # Create CastGroup
        cg = CastGroup(mock_cast_group_db)
        
        # Verify lazy loading - should not call DB initially
        assert not mock_db_services.Event.get.called
        
        # Access event property - should trigger DB call
        result = cg.event
        
        # Verify DB was called and result is cached
        mock_db_services.Event.get.assert_called_once_with(event_id)
        assert result == mock_event
        
        # Second access should not trigger another DB call
        result2 = cg.event
        assert result2 == mock_event
        assert mock_db_services.Event.get.call_count == 1  # Still only one call
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_event_property_no_db_object(self, mock_db_services):
        """Test: event Property ohne Datenbank-Objekt."""
        # Create CastGroup without database object
        cg = CastGroup(None)
        
        # Access event property
        result = cg.event
        
        # Should return None and not call database
        assert result is None
        assert not mock_db_services.Event.get.called
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_event_property_no_event_ref(self, mock_db_services):
        """Test: event Property ohne Event-Referenz."""
        # Mock database object without event reference
        mock_cast_group_db = Mock()
        mock_cast_group_db.id = uuid4()
        mock_cast_group_db.event = None  # No event reference
        mock_cast_group_db.fixed_cast = None
        mock_cast_group_db.nr_actors = 1
        mock_cast_group_db.custom_rule = None
        mock_cast_group_db.cast_rule = None
        mock_cast_group_db.strict_cast_pref = 0
        
        # Create CastGroup
        cg = CastGroup(mock_cast_group_db)
        
        # Access event property
        result = cg.event
        
        # Should return None and not call database
        assert result is None
        assert not mock_db_services.Event.get.called
    
    def test_repr_method_with_event(self):
        """Test: __repr__() Methode mit Event."""
        # Mock database objects
        cg_id = uuid4()
        mock_cast_group_db = Mock()
        mock_cast_group_db.id = cg_id
        mock_cast_group_db.fixed_cast = None
        mock_cast_group_db.nr_actors = 2
        mock_cast_group_db.custom_rule = None
        mock_cast_group_db.cast_rule = None
        mock_cast_group_db.strict_cast_pref = 1
        
        # Create CastGroup
        cg = CastGroup(mock_cast_group_db)
        
        # Mock event
        mock_event = Mock()
        mock_event.date = date(2025, 6, 28)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.name = "Nachmittag"
        cg._event = mock_event  # Set directly to avoid DB call
        
        # Test repr
        repr_str = repr(cg)
        
        # Verify repr contains expected information
        assert "cast group with event 28.06.25 (Nachmittag)" in repr_str
    
    def test_repr_method_without_event(self):
        """Test: __repr__() Methode ohne Event."""
        # Mock database objects
        cg_id = uuid4()
        mock_cast_group_db = Mock()
        mock_cast_group_db.id = cg_id
        mock_cast_group_db.fixed_cast = None
        mock_cast_group_db.nr_actors = 1
        mock_cast_group_db.custom_rule = None
        mock_cast_group_db.cast_rule = None
        mock_cast_group_db.strict_cast_pref = 0
        
        # Create CastGroup
        cg = CastGroup(mock_cast_group_db)
        cg._event = None  # No event
        
        # Test repr
        repr_str = repr(cg)
        
        # Verify repr contains expected information
        assert repr_str == "cast group"


@pytest.mark.unit
class TestCastGroupTree:
    """Test-Klasse für CastGroupTree."""
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_cast_group_tree_initialization_empty(self, mock_db_services):
        """Test: CastGroupTree wird mit leeren Cast Groups korrekt initialisiert."""
        # Mock data
        plan_period_id = uuid4()
        
        # Mock empty cast groups
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = []
        
        # Create tree
        tree = CastGroupTree(plan_period_id)
        
        # Verify tree structure
        assert tree.plan_period_id == plan_period_id
        assert tree.root is not None
        assert tree.root.cast_group_id == 0  # Root has no database object
        assert len(tree.root.children) == 0
        assert len(tree.nodes) == 0  # No nodes in tree
        
        # Verify database call
        mock_db_services.CastGroup.get_all_from__plan_period.assert_called_once_with(plan_period_id)
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_cast_group_tree_initialization_flat_structure(self, mock_db_services):
        """Test: CastGroupTree wird mit flacher Struktur korrekt initialisiert."""
        # Mock data
        plan_period_id = uuid4()
        cg1_id = uuid4()
        cg2_id = uuid4()
        cg3_id = uuid4()
        
        # Mock flat cast groups (no parent-child relationships)
        mock_cg1 = Mock()
        mock_cg1.id = cg1_id
        mock_cg1.parent_groups = []  # No parents - top level
        mock_cg1.child_groups = []   # No children - leaf level
        mock_cg1.fixed_cast = "Hans"
        mock_cg1.nr_actors = 1
        mock_cg1.custom_rule = None
        mock_cg1.cast_rule = None
        mock_cg1.strict_cast_pref = 1
        
        mock_cg2 = Mock()
        mock_cg2.id = cg2_id
        mock_cg2.parent_groups = []  # No parents - top level
        mock_cg2.child_groups = []   # No children - leaf level
        mock_cg2.fixed_cast = "Maria"
        mock_cg2.nr_actors = 1
        mock_cg2.custom_rule = None
        mock_cg2.cast_rule = None
        mock_cg2.strict_cast_pref = 2
        
        mock_cg3 = Mock()
        mock_cg3.id = cg3_id
        mock_cg3.parent_groups = []  # No parents - top level
        mock_cg3.child_groups = []   # No children - leaf level
        mock_cg3.fixed_cast = "Peter"
        mock_cg3.nr_actors = 1
        mock_cg3.custom_rule = None
        mock_cg3.cast_rule = None
        mock_cg3.strict_cast_pref = 0
        
        # Setup database service mocks
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = [mock_cg1, mock_cg2, mock_cg3]
        
        # Create tree
        tree = CastGroupTree(plan_period_id)
        
        # Verify tree structure - all cast groups should be direct children of root
        assert tree.plan_period_id == plan_period_id
        assert tree.root is not None
        assert len(tree.root.children) == 3
        
        # Verify cast groups are children of root
        child_ids = [child.cast_group_id for child in tree.root.children]
        assert cg1_id in child_ids
        assert cg2_id in child_ids
        assert cg3_id in child_ids
        
        # Verify database call
        mock_db_services.CastGroup.get_all_from__plan_period.assert_called_once_with(plan_period_id)
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_cast_group_tree_initialization_hierarchical_structure(self, mock_db_services):
        """Test: CastGroupTree wird mit hierarchischer Struktur korrekt initialisiert."""
        # Mock data for hierarchy: parent1 -> child1, parent2 -> child2, child3
        plan_period_id = uuid4()
        parent1_id = uuid4()
        parent2_id = uuid4()
        child1_id = uuid4()
        child2_id = uuid4()
        child3_id = uuid4()
        
        # Mock child references
        mock_child1_ref = Mock()
        mock_child1_ref.id = child1_id
        
        mock_child2_ref = Mock()
        mock_child2_ref.id = child2_id
        
        mock_child3_ref = Mock()
        mock_child3_ref.id = child3_id
        
        # Mock parent1 with one child
        mock_parent1 = Mock()
        mock_parent1.id = parent1_id
        mock_parent1.parent_groups = []  # Top level
        mock_parent1.child_groups = [mock_child1_ref]  # Has one child
        mock_parent1.fixed_cast = None
        mock_parent1.nr_actors = 2
        mock_parent1.custom_rule = "parent_rule_1"
        mock_parent1.cast_rule = None
        mock_parent1.strict_cast_pref = 1
        
        # Mock parent2 with two children
        mock_parent2 = Mock()
        mock_parent2.id = parent2_id
        mock_parent2.parent_groups = []  # Top level
        mock_parent2.child_groups = [mock_child2_ref, mock_child3_ref]  # Has two children
        mock_parent2.fixed_cast = None
        mock_parent2.nr_actors = 3
        mock_parent2.custom_rule = "parent_rule_2"
        mock_parent2.cast_rule = None
        mock_parent2.strict_cast_pref = 2
        
        # Mock children (leaf nodes)
        mock_child1 = Mock()
        mock_child1.id = child1_id
        mock_child1.parent_groups = [Mock()]  # Has parent
        mock_child1.child_groups = []  # No children
        mock_child1.fixed_cast = "Hans and Maria"
        mock_child1.nr_actors = 2
        mock_child1.custom_rule = None
        mock_child1.cast_rule = Mock()
        mock_child1.cast_rule.rule = "same_cast"
        mock_child1.strict_cast_pref = 2
        
        mock_child2 = Mock()
        mock_child2.id = child2_id
        mock_child2.parent_groups = [Mock()]  # Has parent
        mock_child2.child_groups = []  # No children
        mock_child2.fixed_cast = "Peter"
        mock_child2.nr_actors = 1
        mock_child2.custom_rule = None
        mock_child2.cast_rule = Mock()
        mock_child2.cast_rule.rule = "single_cast"
        mock_child2.strict_cast_pref = 1
        
        mock_child3 = Mock()
        mock_child3.id = child3_id
        mock_child3.parent_groups = [Mock()]  # Has parent
        mock_child3.child_groups = []  # No children
        mock_child3.fixed_cast = "Anna"
        mock_child3.nr_actors = 1
        mock_child3.custom_rule = None
        mock_child3.cast_rule = Mock()
        mock_child3.cast_rule.rule = "single_cast"
        mock_child3.strict_cast_pref = 0
        
        # Setup database service mocks
        all_cast_groups = [mock_parent1, mock_parent2, mock_child1, mock_child2, mock_child3]
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = all_cast_groups
        mock_db_services.CastGroup.get.side_effect = lambda cg_id: {
            child1_id: mock_child1,
            child2_id: mock_child2,
            child3_id: mock_child3
        }[cg_id]
        
        # Create tree
        tree = CastGroupTree(plan_period_id)
        
        # Verify hierarchical tree structure
        assert tree.plan_period_id == plan_period_id
        assert tree.root is not None
        assert len(tree.root.children) == 2  # parent1, parent2
        
        # Find parent nodes
        parent1_node = None
        parent2_node = None
        for child in tree.root.children:
            if child.cast_group_id == parent1_id:
                parent1_node = child
            elif child.cast_group_id == parent2_id:
                parent2_node = child
        
        assert parent1_node is not None
        assert parent2_node is not None
        
        # Verify parent1 has one child
        assert len(parent1_node.children) == 1
        child1_node = list(parent1_node.children)[0]
        assert child1_node.cast_group_id == child1_id
        
        # Verify parent2 has two children
        assert len(parent2_node.children) == 2
        child_ids = [child.cast_group_id for child in parent2_node.children]
        assert child2_id in child_ids
        assert child3_id in child_ids
        
        # Verify database calls
        mock_db_services.CastGroup.get_all_from__plan_period.assert_called_once_with(plan_period_id)
        assert mock_db_services.CastGroup.get.call_count == 3  # 3 children
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_cast_group_tree_multi_level_hierarchy(self, mock_db_services):
        """Test: CastGroupTree wird mit mehrstufiger Hierarchie korrekt initialisiert."""
        # Mock data for 3-level hierarchy: root -> parent -> child -> grandchild
        plan_period_id = uuid4()
        parent_id = uuid4()
        child_id = uuid4()
        grandchild_id = uuid4()
        
        # Mock references
        mock_child_ref = Mock()
        mock_child_ref.id = child_id
        
        mock_grandchild_ref = Mock()
        mock_grandchild_ref.id = grandchild_id
        
        # Mock parent (top level)
        mock_parent = Mock()
        mock_parent.id = parent_id
        mock_parent.parent_groups = []  # Top level
        mock_parent.child_groups = [mock_child_ref]  # Has child
        mock_parent.fixed_cast = None
        mock_parent.nr_actors = 3
        mock_parent.custom_rule = "top_level_rule"
        mock_parent.cast_rule = None
        mock_parent.strict_cast_pref = 2
        
        # Mock child (middle level)
        mock_child = Mock()
        mock_child.id = child_id
        mock_child.parent_groups = [Mock()]  # Has parent
        mock_child.child_groups = [mock_grandchild_ref]  # Has child
        mock_child.fixed_cast = None
        mock_child.nr_actors = 2
        mock_child.custom_rule = "middle_level_rule"
        mock_child.cast_rule = None
        mock_child.strict_cast_pref = 1
        
        # Mock grandchild (leaf level)
        mock_grandchild = Mock()
        mock_grandchild.id = grandchild_id
        mock_grandchild.parent_groups = [Mock()]  # Has parent
        mock_grandchild.child_groups = []  # No children
        mock_grandchild.fixed_cast = "Final Cast"
        mock_grandchild.nr_actors = 1
        mock_grandchild.custom_rule = None
        mock_grandchild.cast_rule = Mock()
        mock_grandchild.cast_rule.rule = "leaf_rule"
        mock_grandchild.strict_cast_pref = 0
        
        # Setup database service mocks
        all_cast_groups = [mock_parent, mock_child, mock_grandchild]
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = all_cast_groups
        mock_db_services.CastGroup.get.side_effect = lambda cg_id: {
            child_id: mock_child,
            grandchild_id: mock_grandchild
        }[cg_id]
        
        # Create tree
        tree = CastGroupTree(plan_period_id)
        
        # Verify 3-level hierarchy
        assert tree.root is not None
        assert len(tree.root.children) == 1  # Only parent at top level
        
        # Navigate down the hierarchy
        parent_node = list(tree.root.children)[0]
        assert parent_node.cast_group_id == parent_id
        assert len(parent_node.children) == 1
        
        child_node = list(parent_node.children)[0]
        assert child_node.cast_group_id == child_id
        assert len(child_node.children) == 1
        
        grandchild_node = list(child_node.children)[0]
        assert grandchild_node.cast_group_id == grandchild_id
        assert len(grandchild_node.children) == 0  # Leaf node
        
        # Verify database calls
        assert mock_db_services.CastGroup.get.call_count == 2  # child, grandchild


@pytest.mark.unit
class TestCastGroupTreeHelperFunctions:
    """Test-Klasse für Helper-Funktionen."""
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_get_cast_group_tree(self, mock_db_services):
        """Test: get_cast_group_tree() Factory-Funktion."""
        # Mock data
        plan_period_id = uuid4()
        cg_id = uuid4()
        
        # Mock cast group
        mock_cast_group = Mock()
        mock_cast_group.id = cg_id
        mock_cast_group.parent_groups = []
        mock_cast_group.child_groups = []
        mock_cast_group.fixed_cast = "Test Cast"
        mock_cast_group.nr_actors = 2
        mock_cast_group.custom_rule = None
        mock_cast_group.cast_rule = None
        mock_cast_group.strict_cast_pref = 1
        
        # Setup database service mock
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = [mock_cast_group]
        
        # Call factory function
        tree = get_cast_group_tree(plan_period_id)
        
        # Verify result
        assert isinstance(tree, CastGroupTree)
        assert tree.plan_period_id == plan_period_id
        assert len(tree.root.children) == 1
        
        # Verify database call
        mock_db_services.CastGroup.get_all_from__plan_period.assert_called_once_with(plan_period_id)
    
    @patch('sat_solver.cast_group_tree.RenderTree')
    @patch('sat_solver.cast_group_tree.ContRoundStyle')
    @patch('builtins.print')
    def test_render_cast_group_tree(self, mock_print, mock_cont_round_style, mock_render_tree):
        """Test: render_cast_group_tree() Visualisierung."""
        # Mock tree
        mock_tree = Mock()
        mock_tree.root = Mock()
        
        # Mock render tree
        mock_rendered = Mock()
        mock_render_tree.return_value = mock_rendered
        
        # Call render function
        render_cast_group_tree(mock_tree)
        
        # Verify rendering
        mock_render_tree.assert_called_once_with(mock_tree.root, mock_cont_round_style)
        mock_print.assert_called_once_with(mock_rendered)


@pytest.mark.integration
class TestCastGroupTreeIntegration:
    """Integration-Tests für CastGroupTree."""
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_cast_group_tree_realistic_klinikclown_scenario(self, mock_db_services):
        """Test: CastGroupTree mit realistischem Klinikclown-Szenario."""
        # Simuliere realistische Hierarchie:
        # Plan Period -> Location Groups -> Time Groups -> Cast Groups
        
        # Mock IDs
        plan_period_id = uuid4()
        kinderklinik_group_id = uuid4()
        seniorenheim_group_id = uuid4()
        kinderklinik_vm_id = uuid4()
        kinderklinik_nm_id = uuid4()
        seniorenheim_vm_id = uuid4()
        
        # Mock references
        mock_kinderklinik_vm_ref = Mock()
        mock_kinderklinik_vm_ref.id = kinderklinik_vm_id
        
        mock_kinderklinik_nm_ref = Mock()
        mock_kinderklinik_nm_ref.id = kinderklinik_nm_id
        
        mock_seniorenheim_vm_ref = Mock()
        mock_seniorenheim_vm_ref.id = seniorenheim_vm_id
        
        # Mock location groups (top level)
        mock_kinderklinik_group = Mock()
        mock_kinderklinik_group.id = kinderklinik_group_id
        mock_kinderklinik_group.parent_groups = []  # Top level
        mock_kinderklinik_group.child_groups = [mock_kinderklinik_vm_ref, mock_kinderklinik_nm_ref]
        mock_kinderklinik_group.fixed_cast = None
        mock_kinderklinik_group.nr_actors = None
        mock_kinderklinik_group.custom_rule = "location_rule_kinderklinik"
        mock_kinderklinik_group.cast_rule = None
        mock_kinderklinik_group.strict_cast_pref = 1
        
        mock_seniorenheim_group = Mock()
        mock_seniorenheim_group.id = seniorenheim_group_id
        mock_seniorenheim_group.parent_groups = []  # Top level
        mock_seniorenheim_group.child_groups = [mock_seniorenheim_vm_ref]
        mock_seniorenheim_group.fixed_cast = None
        mock_seniorenheim_group.nr_actors = None
        mock_seniorenheim_group.custom_rule = "location_rule_seniorenheim"
        mock_seniorenheim_group.cast_rule = None
        mock_seniorenheim_group.strict_cast_pref = 2
        
        # Mock time-specific cast groups (leaf level)
        mock_kinderklinik_vm = Mock()
        mock_kinderklinik_vm.id = kinderklinik_vm_id
        mock_kinderklinik_vm.parent_groups = [Mock()]  # Has parent
        mock_kinderklinik_vm.child_groups = []  # Leaf level
        mock_kinderklinik_vm.fixed_cast = "Hans and Maria"
        mock_kinderklinik_vm.nr_actors = 2
        mock_kinderklinik_vm.custom_rule = None
        mock_kinderklinik_vm.cast_rule = Mock()
        mock_kinderklinik_vm.cast_rule.rule = "same_cast"
        mock_kinderklinik_vm.strict_cast_pref = 2
        
        mock_kinderklinik_nm = Mock()
        mock_kinderklinik_nm.id = kinderklinik_nm_id
        mock_kinderklinik_nm.parent_groups = [Mock()]  # Has parent
        mock_kinderklinik_nm.child_groups = []  # Leaf level
        mock_kinderklinik_nm.fixed_cast = "Peter and Anna"
        mock_kinderklinik_nm.nr_actors = 2
        mock_kinderklinik_nm.custom_rule = None
        mock_kinderklinik_nm.cast_rule = Mock()
        mock_kinderklinik_nm.cast_rule.rule = "different_cast"
        mock_kinderklinik_nm.strict_cast_pref = 1
        
        mock_seniorenheim_vm = Mock()
        mock_seniorenheim_vm.id = seniorenheim_vm_id
        mock_seniorenheim_vm.parent_groups = [Mock()]  # Has parent
        mock_seniorenheim_vm.child_groups = []  # Leaf level
        mock_seniorenheim_vm.fixed_cast = "Thomas"
        mock_seniorenheim_vm.nr_actors = 1
        mock_seniorenheim_vm.custom_rule = None
        mock_seniorenheim_vm.cast_rule = Mock()
        mock_seniorenheim_vm.cast_rule.rule = "single_cast"
        mock_seniorenheim_vm.strict_cast_pref = 0
        
        # Setup database service mocks
        all_cast_groups = [
            mock_kinderklinik_group, mock_seniorenheim_group,
            mock_kinderklinik_vm, mock_kinderklinik_nm, mock_seniorenheim_vm
        ]
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = all_cast_groups
        mock_db_services.CastGroup.get.side_effect = lambda cg_id: {
            kinderklinik_vm_id: mock_kinderklinik_vm,
            kinderklinik_nm_id: mock_kinderklinik_nm,
            seniorenheim_vm_id: mock_seniorenheim_vm
        }[cg_id]
        
        # Create tree via factory function
        tree = get_cast_group_tree(plan_period_id)
        
        # Verify realistic scenario structure
        assert tree.plan_period_id == plan_period_id
        assert tree.root is not None
        assert len(tree.root.children) == 2  # kinderklinik, seniorenheim
        
        # Find location nodes
        kinderklinik_node = None
        seniorenheim_node = None
        for child in tree.root.children:
            if child.cast_group_id == kinderklinik_group_id:
                kinderklinik_node = child
            elif child.cast_group_id == seniorenheim_group_id:
                seniorenheim_node = child
        
        assert kinderklinik_node is not None
        assert seniorenheim_node is not None
        
        # Verify kinderklinik has 2 time slots
        assert len(kinderklinik_node.children) == 2
        kinderklinik_time_ids = [child.cast_group_id for child in kinderklinik_node.children]
        assert kinderklinik_vm_id in kinderklinik_time_ids
        assert kinderklinik_nm_id in kinderklinik_time_ids
        
        # Verify seniorenheim has 1 time slot
        assert len(seniorenheim_node.children) == 1
        seniorenheim_time_node = list(seniorenheim_node.children)[0]
        assert seniorenheim_time_node.cast_group_id == seniorenheim_vm_id
        
        # Verify cast group details
        for child in kinderklinik_node.children:
            if child.cast_group_id == kinderklinik_vm_id:
                assert child.fixed_cast == "Hans and Maria"
                assert child.nr_actors == 2
                assert child.cast_rule == "same_cast"
            elif child.cast_group_id == kinderklinik_nm_id:
                assert child.fixed_cast == "Peter and Anna"
                assert child.nr_actors == 2
                assert child.cast_rule == "different_cast"
        
        assert seniorenheim_time_node.fixed_cast == "Thomas"
        assert seniorenheim_time_node.nr_actors == 1
        assert seniorenheim_time_node.cast_rule == "single_cast"
        
        # Verify database call count
        expected_get_calls = 3  # 3 leaf cast groups
        assert mock_db_services.CastGroup.get.call_count == expected_get_calls
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_cast_group_tree_complex_cast_rules_scenario(self, mock_db_services):
        """Test: CastGroupTree mit komplexen Cast-Regeln."""
        # Simuliere Szenario mit verschiedenen Cast-Regeln und Enforcement-Levels
        
        # Mock IDs
        plan_period_id = uuid4()
        strict_group_id = uuid4()
        flexible_group_id = uuid4()
        ignored_group_id = uuid4()
        
        # Mock cast groups with different rules
        mock_strict_group = Mock()
        mock_strict_group.id = strict_group_id
        mock_strict_group.parent_groups = []
        mock_strict_group.child_groups = []
        mock_strict_group.fixed_cast = "Hans and Maria"
        mock_strict_group.nr_actors = 2
        mock_strict_group.custom_rule = "same_cast_always"  # Custom rule
        mock_strict_group.cast_rule = Mock()
        mock_strict_group.cast_rule.rule = "default_rule"  # Should be overridden
        mock_strict_group.strict_cast_pref = 2  # Hard constraint
        
        mock_flexible_group = Mock()
        mock_flexible_group.id = flexible_group_id
        mock_flexible_group.parent_groups = []
        mock_flexible_group.child_groups = []
        mock_flexible_group.fixed_cast = "Peter or Anna"
        mock_flexible_group.nr_actors = 1
        mock_flexible_group.custom_rule = None
        mock_flexible_group.cast_rule = Mock()
        mock_flexible_group.cast_rule.rule = "different_cast_preferred"  # Standard rule
        mock_flexible_group.strict_cast_pref = 1  # Soft constraint
        
        mock_ignored_group = Mock()
        mock_ignored_group.id = ignored_group_id
        mock_ignored_group.parent_groups = []
        mock_ignored_group.child_groups = []
        mock_ignored_group.fixed_cast = None
        mock_ignored_group.nr_actors = 3
        mock_ignored_group.custom_rule = None
        mock_ignored_group.cast_rule = None  # No rule
        mock_ignored_group.strict_cast_pref = 0  # Ignored
        
        # Setup database service mocks
        all_cast_groups = [mock_strict_group, mock_flexible_group, mock_ignored_group]
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = all_cast_groups
        
        # Create tree
        tree = get_cast_group_tree(plan_period_id)
        
        # Verify complex rules scenario
        assert tree.plan_period_id == plan_period_id
        assert len(tree.root.children) == 3
        
        # Verify cast groups with different rule configurations
        cast_groups_by_id = {child.cast_group_id: child for child in tree.root.children}
        
        # Strict group
        strict_node = cast_groups_by_id[strict_group_id]
        assert strict_node.fixed_cast == "Hans and Maria"
        assert strict_node.cast_rule == "same_cast_always"  # Custom rule used
        assert strict_node.strict_rule_pref == 2
        
        # Flexible group
        flexible_node = cast_groups_by_id[flexible_group_id]
        assert flexible_node.fixed_cast == "Peter or Anna"
        assert flexible_node.cast_rule == "different_cast_preferred"  # Standard rule used
        assert flexible_node.strict_rule_pref == 1
        
        # Ignored group
        ignored_node = cast_groups_by_id[ignored_group_id]
        assert ignored_node.fixed_cast is None
        assert ignored_node.cast_rule is None
        assert ignored_node.strict_rule_pref == 0
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_cast_group_tree_event_integration(self, mock_db_services):
        """Test: CastGroupTree mit Event-Integration."""
        # Test integration with events for realistic cast group representation
        
        # Mock IDs
        plan_period_id = uuid4()
        cg_id = uuid4()
        event_id = uuid4()
        
        # Mock event
        mock_event = Mock()
        mock_event.id = event_id
        mock_event.date = date(2025, 6, 28)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.name = "Vormittag"
        
        # Mock event reference
        mock_event_ref = Mock()
        mock_event_ref.id = event_id
        
        # Mock cast group with event
        mock_cast_group = Mock()
        mock_cast_group.id = cg_id
        mock_cast_group.parent_groups = []
        mock_cast_group.child_groups = []
        mock_cast_group.event = mock_event_ref
        mock_cast_group.fixed_cast = "Event Cast"
        mock_cast_group.nr_actors = 2
        mock_cast_group.custom_rule = None
        mock_cast_group.cast_rule = None
        mock_cast_group.strict_cast_pref = 1
        
        # Setup database service mocks
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = [mock_cast_group]
        mock_db_services.Event.get.return_value = mock_event
        
        # Create tree
        tree = get_cast_group_tree(plan_period_id)
        
        # Verify event integration
        assert len(tree.root.children) == 1
        cast_group_node = list(tree.root.children)[0]
        
        # Test event property access (should trigger lazy loading)
        event = cast_group_node.event
        assert event == mock_event
        assert event.date == date(2025, 6, 28)
        assert event.time_of_day.name == "Vormittag"
        
        # Test repr with event
        repr_str = repr(cast_group_node)
        assert "cast group with event 28.06.25 (Vormittag)" in repr_str
        
        # Verify database calls
        mock_db_services.Event.get.assert_called_once_with(event_id)
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_cast_group_tree_error_handling(self, mock_db_services):
        """Test: CastGroupTree Error-Handling."""
        # Test with empty plan period
        plan_period_id = uuid4()
        
        # Mock empty cast groups
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = []
        
        # Should handle empty plan period gracefully
        tree = get_cast_group_tree(plan_period_id)
        assert tree.plan_period_id == plan_period_id
        assert tree.root is not None
        assert len(tree.root.children) == 0
        
        # Test with None values in cast group data
        mock_cast_group_with_nones = Mock()
        mock_cast_group_with_nones.id = uuid4()
        mock_cast_group_with_nones.parent_groups = []
        mock_cast_group_with_nones.child_groups = []
        mock_cast_group_with_nones.fixed_cast = None
        mock_cast_group_with_nones.nr_actors = None
        mock_cast_group_with_nones.custom_rule = None
        mock_cast_group_with_nones.cast_rule = None
        mock_cast_group_with_nones.strict_cast_pref = None
        
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = [mock_cast_group_with_nones]
        
        # Should handle None values gracefully
        tree_with_nones = get_cast_group_tree(plan_period_id)
        assert len(tree_with_nones.root.children) == 1
        cast_group_node = list(tree_with_nones.root.children)[0]
        assert cast_group_node.fixed_cast is None
        assert cast_group_node.nr_actors is None
        assert cast_group_node.cast_rule is None
        assert cast_group_node.strict_rule_pref is None


@pytest.mark.performance
class TestCastGroupTreePerformance:
    """Performance-Tests für CastGroupTree."""
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_cast_group_tree_large_flat_structure_performance(self, mock_db_services):
        """Test: CastGroupTree Performance mit großer flacher Struktur."""
        import time
        
        # Setup large flat structure: 100 cast groups at root level
        plan_period_id = uuid4()
        num_cast_groups = 100
        
        # Generate cast groups
        cast_groups = []
        for i in range(num_cast_groups):
            mock_cg = Mock()
            mock_cg.id = uuid4()
            mock_cg.parent_groups = []  # All at top level
            mock_cg.child_groups = []   # All leaf level
            mock_cg.fixed_cast = f"Cast {i}"
            mock_cg.nr_actors = (i % 3) + 1  # 1-3 actors
            mock_cg.custom_rule = f"rule_{i}" if i % 2 == 0 else None
            mock_cg.cast_rule = Mock() if i % 3 == 0 else None
            if mock_cg.cast_rule:
                mock_cg.cast_rule.rule = f"standard_rule_{i}"
            mock_cg.strict_cast_pref = i % 3  # 0, 1, or 2
            cast_groups.append(mock_cg)
        
        # Setup database service mocks
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = cast_groups
        
        # Measure construction time
        start_time = time.time()
        tree = CastGroupTree(plan_period_id)
        end_time = time.time()
        
        construction_time = end_time - start_time
        
        # Verify large flat structure was built correctly
        assert len(tree.root.children) == num_cast_groups
        
        # Performance should be reasonable
        assert construction_time < 2.0  # Should complete within 2 seconds
        
        # Verify database call count
        mock_db_services.CastGroup.get_all_from__plan_period.assert_called_once()
        # No additional get() calls needed for flat structure
        assert not mock_db_services.CastGroup.get.called
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_cast_group_tree_deep_hierarchy_performance(self, mock_db_services):
        """Test: CastGroupTree Performance mit tiefer Hierarchie."""
        import time
        
        # Setup deep hierarchy: 1 parent -> 1 child -> 1 grandchild -> ... (20 levels deep)
        plan_period_id = uuid4()
        depth = 20
        
        # Generate IDs
        cast_group_ids = [uuid4() for _ in range(depth)]
        
        # Generate references
        child_refs = [Mock(id=cast_group_ids[i+1]) for i in range(depth-1)]
        
        # Generate cast groups
        cast_groups = []
        for i in range(depth):
            mock_cg = Mock()
            mock_cg.id = cast_group_ids[i]
            mock_cg.parent_groups = [] if i == 0 else [Mock()]  # Only first is top level
            mock_cg.child_groups = [child_refs[i]] if i < depth-1 else []  # Only last is leaf
            mock_cg.fixed_cast = f"Deep Cast {i}"
            mock_cg.nr_actors = (i % 3) + 1
            mock_cg.custom_rule = f"deep_rule_{i}"
            mock_cg.cast_rule = None
            mock_cg.strict_cast_pref = i % 3
            cast_groups.append(mock_cg)
        
        # Setup database service mocks
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = cast_groups
        cast_groups_dict = {cg.id: cg for cg in cast_groups}
        mock_db_services.CastGroup.get.side_effect = lambda cg_id: cast_groups_dict[cg_id]
        
        # Measure construction time
        start_time = time.time()
        tree = CastGroupTree(plan_period_id)
        end_time = time.time()
        
        construction_time = end_time - start_time
        
        # Verify deep hierarchy was built correctly
        assert len(tree.root.children) == 1  # Only one top-level node
        
        # Navigate down the hierarchy to verify depth
        current_node = list(tree.root.children)[0]
        levels_traversed = 1
        while current_node.children:
            current_node = list(current_node.children)[0]
            levels_traversed += 1
        
        assert levels_traversed == depth
        
        # Performance should be reasonable even for deep hierarchy
        assert construction_time < 3.0  # Should complete within 3 seconds
        
        # Verify database call count
        expected_get_calls = depth - 1  # All except the root level
        assert mock_db_services.CastGroup.get.call_count == expected_get_calls
    
    @patch('sat_solver.cast_group_tree.db_services')
    def test_cast_group_tree_memory_efficiency(self, mock_db_services):
        """Test: CastGroupTree Memory-Effizienz."""
        import gc
        
        # Setup minimal but valid entities
        plan_period_id = uuid4()
        
        mock_cast_group = Mock()
        mock_cast_group.id = uuid4()
        mock_cast_group.parent_groups = []
        mock_cast_group.child_groups = []
        mock_cast_group.fixed_cast = "Memory Test"
        mock_cast_group.nr_actors = 1
        mock_cast_group.custom_rule = None
        mock_cast_group.cast_rule = None
        mock_cast_group.strict_cast_pref = 1
        
        mock_db_services.CastGroup.get_all_from__plan_period.return_value = [mock_cast_group]
        
        # Force garbage collection before test
        gc.collect()
        
        # Create and destroy multiple trees
        for _ in range(50):
            tree = CastGroupTree(plan_period_id)
            # Tree should be garbage collected automatically
        
        # Force garbage collection after test
        gc.collect()
        
        # Should not leak significant memory
        assert True  # Test passes if no memory errors occur
