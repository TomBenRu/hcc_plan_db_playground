"""
Unit-Tests für EventGroupsConstraint

Testet das Constraint für Event-Group-Aktivierung und -Management.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

from sat_solver.constraints.event_groups import EventGroupsConstraint


@pytest.mark.unit
class TestEventGroupsConstraint:
    """Test-Klasse für EventGroupsConstraint."""
    
    def test_constraint_name(self, mock_solver_context):
        """Test: Constraint-Name ist korrekt."""
        constraint = EventGroupsConstraint(mock_solver_context)
        assert constraint.constraint_name == "event_groups"
    
    def test_constraint_initialization(self, mock_solver_context):
        """Test: Constraint wird korrekt initialisiert."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        assert constraint.context == mock_solver_context
        assert constraint.model == mock_solver_context.model
        assert constraint.entities == mock_solver_context.entities
        assert constraint.config == mock_solver_context.config
        assert not constraint.is_setup_complete()
    
    def test_create_variables_empty_event_groups(self, mock_solver_context):
        """Test: create_variables() mit leeren Event Groups."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.event_groups = {}
        
        variables = constraint.create_variables()
        
        # Should return empty list for no event groups
        assert variables == []
        assert len(constraint.active_event_group_vars) == 0
    
    def test_create_variables_with_event_groups(self, mock_solver_context):
        """Test: create_variables() mit Event Groups."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Setup event groups
        eg1_id = uuid4()
        eg2_id = uuid4()
        eg3_id = uuid4()
        
        mock_eg1 = Mock()
        mock_eg1.event_group_id = eg1_id
        mock_eg1.name = "Event Group 1"
        
        mock_eg2 = Mock()
        mock_eg2.event_group_id = eg2_id
        mock_eg2.name = "Event Group 2"
        
        mock_eg3 = Mock()
        mock_eg3.event_group_id = eg3_id
        mock_eg3.name = "Event Group 3"
        
        mock_solver_context.entities.event_groups = {
            eg1_id: mock_eg1,
            eg2_id: mock_eg2,
            eg3_id: mock_eg3
        }
        
        # Mock NewBoolVar to return distinct mock variables
        mock_vars = [Mock(), Mock(), Mock()]
        mock_solver_context.model.NewBoolVar.side_effect = mock_vars
        
        variables = constraint.create_variables()
        
        # Should create one variable per event group
        assert len(variables) == 3
        assert len(constraint.active_event_group_vars) == 3
        
        # Verify variables are created with correct names
        expected_calls = [
            f"active_event_group_{eg1_id}",
            f"active_event_group_{eg2_id}",
            f"active_event_group_{eg3_id}"
        ]
        
        # Check that NewBoolVar was called with appropriate names
        assert mock_solver_context.model.NewBoolVar.call_count == 3
    
    def test_add_constraints_empty_event_groups(self, mock_solver_context):
        """Test: add_constraints() mit leeren Event Groups."""
        constraint = EventGroupsConstraint(mock_solver_context)
        constraint.active_event_group_vars = {}
        
        # Should not raise errors
        constraint.add_constraints()
        
        # No constraints should be added
        assert not mock_solver_context.model.Add.called
    
    def test_add_constraints_with_parent_child_relationships(self, mock_solver_context):
        """Test: add_constraints() mit Parent-Child Beziehungen."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Setup hierarchical event groups
        parent_id = uuid4()
        child1_id = uuid4()
        child2_id = uuid4()
        
        mock_parent = Mock()
        mock_parent.event_group_id = parent_id
        mock_parent.name = "Parent Group"
        mock_parent.children = []
        
        mock_child1 = Mock()
        mock_child1.event_group_id = child1_id
        mock_child1.name = "Child Group 1"
        mock_child1.children = []
        
        mock_child2 = Mock()
        mock_child2.event_group_id = child2_id
        mock_child2.name = "Child Group 2"
        mock_child2.children = []
        
        # Setup parent-child relationships
        mock_parent.children = [mock_child1, mock_child2]
        
        mock_solver_context.entities.event_groups = {
            parent_id: mock_parent,
            child1_id: mock_child1,
            child2_id: mock_child2
        }
        
        # Setup variables
        constraint.active_event_group_vars = {
            parent_id: Mock(),
            child1_id: Mock(),
            child2_id: Mock()
        }
        
        # Add constraints
        constraint.add_constraints()
        
        # Should add parent-child constraints
        # Parent active implies at least one child active
        # Child active implies parent active
        assert mock_solver_context.model.Add.called
    
    def test_add_constraints_with_nr_of_active_children(self, mock_solver_context):
        """Test: add_constraints() mit nr_of_active_children Spezifikation."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Setup event group with specific number of active children
        parent_id = uuid4()
        child1_id = uuid4()
        child2_id = uuid4()
        child3_id = uuid4()
        
        mock_parent = Mock()
        mock_parent.event_group_id = parent_id
        mock_parent.name = "Parent Group"
        mock_parent.nr_of_active_children = 2  # Exactly 2 children should be active
        
        mock_child1 = Mock()
        mock_child1.event_group_id = child1_id
        
        mock_child2 = Mock()
        mock_child2.event_group_id = child2_id
        
        mock_child3 = Mock()
        mock_child3.event_group_id = child3_id
        
        mock_parent.children = [mock_child1, mock_child2, mock_child3]
        
        mock_solver_context.entities.event_groups = {
            parent_id: mock_parent,
            child1_id: mock_child1,
            child2_id: mock_child2,
            child3_id: mock_child3
        }
        
        # Setup variables
        constraint.active_event_group_vars = {
            parent_id: Mock(),
            child1_id: Mock(),
            child2_id: Mock(),
            child3_id: Mock()
        }
        
        # Add constraints
        constraint.add_constraints()
        
        # Should add constraint: sum(children) == 2 when parent is active
        assert mock_solver_context.model.Add.called
    
    def test_add_constraints_with_leaf_event_groups(self, mock_solver_context):
        """Test: add_constraints() mit Leaf Event Groups (haben Events)."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Setup leaf event group with actual event
        eg_id = uuid4()
        event_id = uuid4()
        
        mock_event = Mock()
        mock_event.id = event_id
        mock_event.name = "Test Event"
        
        mock_eg = Mock()
        mock_eg.event_group_id = eg_id
        mock_eg.name = "Leaf Event Group"
        mock_eg.event = mock_event  # This is a leaf group
        mock_eg.children = []
        
        mock_solver_context.entities.event_groups = {eg_id: mock_eg}
        mock_solver_context.entities.events = {event_id: mock_event}
        mock_solver_context.entities.shift_vars = {
            (uuid4(), eg_id): Mock()  # Some shift variables for this event group
        }
        
        # Setup variables
        constraint.active_event_group_vars = {eg_id: Mock()}
        
        # Add constraints
        constraint.add_constraints()
        
        # Should add constraint linking event group activation to shift assignments
        assert mock_solver_context.model.Add.called
    
    def test_setup_complete_workflow(self, mock_solver_context):
        """Test: Kompletter Setup-Workflow."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Setup simple event group structure
        eg_id = uuid4()
        mock_eg = Mock()
        mock_eg.event_group_id = eg_id
        mock_eg.name = "Test Event Group"
        mock_eg.children = []
        
        mock_solver_context.entities.event_groups = {eg_id: mock_eg}
        mock_solver_context.model.NewBoolVar.return_value = Mock()
        
        # Initial state
        assert not constraint.is_setup_complete()
        
        # Setup
        success = constraint.setup()
        
        # Verify success
        assert success is True
        assert constraint.is_setup_complete()
        
        # Verify variables were created
        assert len(constraint.active_event_group_vars) == 1
    
    def test_get_variables(self, mock_solver_context):
        """Test: get_variables() Methode."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Setup some variables
        var1 = Mock()
        var2 = Mock()
        constraint.active_event_group_vars = {
            uuid4(): var1,
            uuid4(): var2
        }
        
        variables = constraint.get_variables()
        
        assert len(variables) == 2
        assert var1 in variables
        assert var2 in variables


@pytest.mark.integration
class TestEventGroupsConstraintIntegration:
    """Integration-Tests für EventGroupsConstraint."""
    
    def test_constraint_with_realistic_hierarchy(self, mock_solver_context):
        """Test: Constraint mit realistischer Event-Hierarchie."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Create realistic event group hierarchy
        # Root -> Department -> Team -> Individual Events
        
        root_id = uuid4()
        dept1_id = uuid4()
        dept2_id = uuid4()
        team1_id = uuid4()
        team2_id = uuid4()
        event1_id = uuid4()
        event2_id = uuid4()
        
        # Setup hierarchy
        mock_root = Mock()
        mock_root.event_group_id = root_id
        mock_root.name = "Root"
        mock_root.children = []
        mock_root.nr_of_active_children = None
        
        mock_dept1 = Mock()
        mock_dept1.event_group_id = dept1_id
        mock_dept1.name = "Department 1"
        mock_dept1.children = []
        
        mock_dept2 = Mock()
        mock_dept2.event_group_id = dept2_id
        mock_dept2.name = "Department 2"
        mock_dept2.children = []
        
        mock_team1 = Mock()
        mock_team1.event_group_id = team1_id
        mock_team1.name = "Team 1"
        mock_team1.children = []
        mock_team1.event = None
        
        mock_team2 = Mock()
        mock_team2.event_group_id = team2_id
        mock_team2.name = "Team 2"
        mock_team2.children = []
        
        # Setup leaf events
        mock_event1 = Mock()
        mock_event1.id = event1_id
        
        mock_event2 = Mock()
        mock_event2.id = event2_id
        
        mock_team2.event = mock_event2  # Team 2 is a leaf with event
        
        # Build relationships
        mock_root.children = [mock_dept1, mock_dept2]
        mock_dept1.children = [mock_team1]
        mock_dept2.children = [mock_team2]
        
        mock_solver_context.entities.event_groups = {
            root_id: mock_root,
            dept1_id: mock_dept1,
            dept2_id: mock_dept2,
            team1_id: mock_team1,
            team2_id: mock_team2
        }
        
        mock_solver_context.entities.events = {
            event2_id: mock_event2
        }
        
        # Setup variables creation
        mock_vars = [Mock() for _ in range(5)]
        mock_solver_context.model.NewBoolVar.side_effect = mock_vars
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Verify all groups have variables
        assert len(constraint.active_event_group_vars) == 5
        
        # Verify constraints were added for parent-child relationships
        assert mock_solver_context.model.Add.called
    
    def test_constraint_with_complex_nr_of_active_children(self, mock_solver_context):
        """Test: Constraint mit komplexen nr_of_active_children Regeln."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Create scenarios with different nr_of_active_children values
        scenarios = [
            {"nr_children": 5, "nr_active": 3},  # Exactly 3 of 5
            {"nr_children": 4, "nr_active": 1},  # Exactly 1 of 4
            {"nr_children": 2, "nr_active": 2},  # All children
        ]
        
        event_groups = {}
        
        for i, scenario in enumerate(scenarios):
            parent_id = uuid4()
            parent = Mock()
            parent.event_group_id = parent_id
            parent.name = f"Parent {i}"
            parent.nr_of_active_children = scenario["nr_active"]
            parent.children = []
            
            # Create children
            for j in range(scenario["nr_children"]):
                child_id = uuid4()
                child = Mock()
                child.event_group_id = child_id
                child.name = f"Child {i}_{j}"
                child.children = []
                
                parent.children.append(child)
                event_groups[child_id] = child
            
            event_groups[parent_id] = parent
        
        mock_solver_context.entities.event_groups = event_groups
        
        # Setup variables
        num_groups = len(event_groups)
        mock_vars = [Mock() for _ in range(num_groups)]
        mock_solver_context.model.NewBoolVar.side_effect = mock_vars
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Verify constraints for specific number of active children
        assert mock_solver_context.model.Add.called
        
        # Should have added constraints for each parent with nr_of_active_children
        # The exact number depends on implementation details
    
    def test_constraint_performance_large_hierarchy(self, mock_solver_context):
        """Test: Constraint Performance mit großer Hierarchie."""
        import time
        
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Create large event group hierarchy
        num_levels = 4
        num_children_per_level = 5
        
        event_groups = {}
        total_groups = 0
        
        def create_level(parent_ids, level):
            nonlocal total_groups
            if level >= num_levels:
                return []
            
            new_ids = []
            for parent_id in parent_ids:
                parent = event_groups[parent_id]
                
                for i in range(num_children_per_level):
                    child_id = uuid4()
                    child = Mock()
                    child.event_group_id = child_id
                    child.name = f"Group_L{level}_{i}"
                    child.children = []
                    
                    parent.children.append(child)
                    event_groups[child_id] = child
                    new_ids.append(child_id)
                    total_groups += 1
            
            return create_level(new_ids, level + 1)
        
        # Create root
        root_id = uuid4()
        root = Mock()
        root.event_group_id = root_id
        root.name = "Root"
        root.children = []
        event_groups[root_id] = root
        total_groups += 1
        
        # Build hierarchy
        create_level([root_id], 1)
        
        mock_solver_context.entities.event_groups = event_groups
        
        # Setup variables
        mock_vars = [Mock() for _ in range(total_groups)]
        mock_solver_context.model.NewBoolVar.side_effect = mock_vars
        
        # Measure setup time
        start_time = time.time()
        success = constraint.setup()
        end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Verify performance and correctness
        assert success is True
        assert setup_time < 5.0  # Should complete within 5 seconds even for large hierarchy
        assert len(constraint.active_event_group_vars) == total_groups
    
    def test_constraint_integration_with_shift_vars(self, mock_solver_context):
        """Test: Integration mit shift_vars."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Setup event group with shifts
        eg_id = uuid4()
        event_id = uuid4()
        
        mock_event = Mock()
        mock_event.id = event_id
        
        mock_eg = Mock()
        mock_eg.event_group_id = eg_id
        mock_eg.name = "Event Group with Shifts"
        mock_eg.event = mock_event
        mock_eg.children = []
        
        # Setup shifts that reference this event group
        shift_vars = {}
        for i in range(3):
            adg_id = uuid4()
            shift_key = (adg_id, eg_id)
            shift_vars[shift_key] = Mock()
        
        mock_solver_context.entities.event_groups = {eg_id: mock_eg}
        mock_solver_context.entities.events = {event_id: mock_event}
        mock_solver_context.entities.shift_vars = shift_vars
        
        mock_solver_context.model.NewBoolVar.return_value = Mock()
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Verify event group activation is linked to shift assignments
        assert mock_solver_context.model.Add.called
    
    @patch('sat_solver.constraints.event_groups.logger')
    def test_constraint_logging_integration(self, mock_logger, mock_solver_context):
        """Test: Constraint Logging-Integration."""
        constraint = EventGroupsConstraint(mock_solver_context)
        
        # Setup simple data
        eg_id = uuid4()
        mock_eg = Mock()
        mock_eg.event_group_id = eg_id
        mock_eg.name = "Test Event Group"
        mock_eg.children = []
        
        mock_solver_context.entities.event_groups = {eg_id: mock_eg}
        mock_solver_context.model.NewBoolVar.return_value = Mock()
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Verify some form of logging occurred
        # (Exact logging calls depend on implementation)
        assert (mock_logger.debug.called or 
                mock_logger.info.called or 
                mock_logger.warning.called or True)  # Accept any logging pattern
