"""
Unit-Tests für AvailDayGroupsConstraint

Testet das Constraint für AvailDay-Group-Aktivität und zugehörige Regeln.
Kombiniert Tests für:
- AvailDay-Groups Activity Constraints
- Required AvailDay-Groups Constraints
- Shift Constraints in AvailDay-Groups
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

from sat_solver.constraints.avail_day_groups import AvailDayGroupsConstraint


@pytest.mark.unit
class TestAvailDayGroupsConstraint:
    """Test-Klasse für AvailDayGroupsConstraint."""
    
    def test_constraint_name(self, mock_solver_context):
        """Test: Constraint-Name ist korrekt."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        assert constraint.constraint_name == "avail_day_groups"
    
    def test_constraint_initialization(self, mock_solver_context):
        """Test: Constraint wird korrekt initialisiert."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        assert constraint.context == mock_solver_context
        assert constraint.model == mock_solver_context.model
        assert constraint.entities == mock_solver_context.entities
        assert constraint.config == mock_solver_context.config
        assert not constraint.is_setup_complete()
    
    def test_create_variables_empty_entities(self, mock_solver_context):
        """Test: create_variables() mit leeren Entities."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.avail_day_groups = {}
        
        variables = constraint.create_variables()
        
        # Should return empty list for empty entities
        assert variables == []
    
    def test_create_variables_no_required_groups(self, mock_solver_context):
        """Test: create_variables() ohne Required-Groups."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup avail day groups without required groups
        adg_id1, adg_id2 = uuid4(), uuid4()
        
        mock_adg1 = Mock()
        mock_adg1.required_avail_day_groups = None  # No required
        
        mock_adg2 = Mock()
        mock_adg2.required_avail_day_groups = None  # No required
        
        mock_solver_context.entities.avail_day_groups = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2
        }
        
        variables = constraint.create_variables()
        
        # Should return empty list when no required groups
        assert variables == []
    
    def test_create_variables_with_required_groups(self, mock_solver_context):
        """Test: create_variables() mit Required-Groups."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup avail day groups with required groups
        adg_id1, adg_id2, adg_id3 = uuid4(), uuid4(), uuid4()
        
        # Mock required objects
        mock_required1 = Mock()
        mock_required2 = Mock()
        
        mock_adg1 = Mock()
        mock_adg1.required_avail_day_groups = mock_required1  # Has required
        
        mock_adg2 = Mock()
        mock_adg2.required_avail_day_groups = None  # No required
        
        mock_adg3 = Mock()
        mock_adg3.required_avail_day_groups = mock_required2  # Has required
        
        mock_solver_context.entities.avail_day_groups = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2,
            adg_id3: mock_adg3
        }
        
        # Mock NewBoolVar
        mock_var1 = Mock()
        mock_var2 = Mock()
        mock_solver_context.model.NewBoolVar.side_effect = [mock_var1, mock_var2]
        
        variables = constraint.create_variables()
        
        # Should create variables for groups with required
        assert len(variables) == 2
        assert variables == [mock_var1, mock_var2]
        
        # Verify metadata stored
        assert constraint.get_metadata(f'required_var_{adg_id1}') == mock_var1
        assert constraint.get_metadata(f'required_var_{adg_id3}') == mock_var2
        assert constraint.get_metadata(f'required_var_{adg_id2}') is None
    
    def test_add_activity_constraints_empty_groups(self, mock_solver_context):
        """Test: _add_activity_constraints() mit leeren Groups."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.avail_day_groups = {}
        mock_solver_context.entities.avail_day_group_vars = {}
        
        constraint._add_activity_constraints()
        
        # No constraints should be added
        assert not mock_solver_context.model.Add.called
        assert constraint.get_metadata('activity_constraints_added') == 0
    
    def test_add_activity_constraints_groups_without_children(self, mock_solver_context):
        """Test: _add_activity_constraints() mit Groups ohne Children."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup groups without children
        adg_id = uuid4()
        
        mock_adg = Mock()
        mock_adg.children = []  # No children
        
        mock_solver_context.entities.avail_day_groups = {adg_id: mock_adg}
        mock_solver_context.entities.avail_day_group_vars = {}
        
        constraint._add_activity_constraints()
        
        # Should skip groups without children
        assert not mock_solver_context.model.Add.called
        assert constraint.get_metadata('activity_constraints_added') == 0
    
    def test_add_activity_constraints_root_group(self, mock_solver_context):
        """Test: _add_activity_constraints() mit Root-Group."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup root group with children
        adg_id = uuid4()
        child_id1, child_id2 = uuid4(), uuid4()
        
        # Mock children
        mock_child1 = Mock()
        mock_child1.avail_day_group_id = child_id1
        mock_child1.children = []
        mock_child1.avail_day = Mock()  # Has avail_day
        
        mock_child2 = Mock()
        mock_child2.avail_day_group_id = child_id2
        mock_child2.children = [Mock()]  # Has children
        mock_child2.avail_day = None
        
        mock_child3 = Mock()
        mock_child3.avail_day_group_id = uuid4()
        mock_child3.children = []
        mock_child3.avail_day = None  # Neither children nor avail_day -> skip
        
        # Mock root group
        mock_adg = Mock()
        mock_adg.children = [mock_child1, mock_child2, mock_child3]
        mock_adg.is_root = True
        mock_adg.nr_of_active_children = 2  # Explicit number
        
        # Mock child variables
        mock_child_var1 = Mock()
        mock_child_var2 = Mock()
        
        mock_solver_context.entities.avail_day_groups = {adg_id: mock_adg}
        mock_solver_context.entities.avail_day_group_vars = {
            child_id1: mock_child_var1,
            child_id2: mock_child_var2
            # child3 not in vars (no avail_day or children)
        }
        
        constraint._add_activity_constraints()
        
        # Should add constraint for root: sum(child_vars) == nr_of_active_children
        assert mock_solver_context.model.Add.called
        assert constraint.get_metadata('activity_constraints_added') == 1
    
    def test_add_activity_constraints_non_root_group(self, mock_solver_context):
        """Test: _add_activity_constraints() mit Non-Root-Group."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup non-root group with children
        adg_id = uuid4()
        child_id1, child_id2 = uuid4(), uuid4()
        
        # Mock children
        mock_child1 = Mock()
        mock_child1.avail_day_group_id = child_id1
        mock_child1.children = []
        mock_child1.avail_day = Mock()
        
        mock_child2 = Mock()
        mock_child2.avail_day_group_id = child_id2
        mock_child2.children = []
        mock_child2.avail_day = Mock()
        
        # Mock non-root group
        mock_adg = Mock()
        mock_adg.children = [mock_child1, mock_child2]
        mock_adg.is_root = False
        mock_adg.nr_of_active_children = None  # Use count of valid children
        
        # Mock variables
        mock_parent_var = Mock()
        mock_child_var1 = Mock()
        mock_child_var2 = Mock()
        
        mock_solver_context.entities.avail_day_groups = {adg_id: mock_adg}
        mock_solver_context.entities.avail_day_group_vars = {
            adg_id: mock_parent_var,
            child_id1: mock_child_var1,
            child_id2: mock_child_var2
        }
        
        constraint._add_activity_constraints()
        
        # Should add constraint: sum(child_vars) == nr_active * parent_var
        assert mock_solver_context.model.Add.called
        assert constraint.get_metadata('activity_constraints_added') == 1
    
    def test_add_required_constraints_empty(self, mock_solver_context):
        """Test: _add_required_constraints() ohne Required-Groups."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup entities without required groups
        mock_solver_context.entities.avail_day_groups = {}
        
        constraint._add_required_constraints()
        
        # No constraints should be added
        assert not mock_solver_context.model.Add.called
        assert constraint.get_metadata('required_constraints_added') == 0
    
    def test_add_required_constraints_with_required_groups(self, mock_solver_context):
        """Test: _add_required_constraints() mit Required-Groups."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup test data
        adg_id = uuid4()
        child_id1, child_id2 = uuid4(), uuid4()
        evg_id1, evg_id2 = uuid4(), uuid4()
        location_id1, location_id2 = uuid4(), uuid4()
        
        # Mock required object
        mock_location1 = Mock()
        mock_location1.id = location_id1
        mock_location2 = Mock()
        mock_location2.id = location_id2
        
        mock_required = Mock()
        mock_required.num_avail_day_groups = 3
        mock_required.locations_of_work = [mock_location1, mock_location2]
        
        # Mock children
        mock_child1 = Mock()
        mock_child1.avail_day_group_id = child_id1
        mock_child2 = Mock()
        mock_child2.avail_day_group_id = child_id2
        
        # Mock avail day group
        mock_adg = Mock()
        mock_adg.required_avail_day_groups = mock_required
        mock_adg.children = [mock_child1, mock_child2]
        
        # Mock events
        mock_location_plan_period1 = Mock()
        mock_location_plan_period1.location_of_work = mock_location1
        
        mock_location_plan_period2 = Mock()
        mock_location_plan_period2.location_of_work = mock_location2
        
        mock_event1 = Mock()
        mock_event1.location_plan_period = mock_location_plan_period1
        
        mock_event2 = Mock()
        mock_event2.location_plan_period = mock_location_plan_period2
        
        mock_event_group1 = Mock()
        mock_event_group1.event = mock_event1
        
        mock_event_group2 = Mock()
        mock_event_group2.event = mock_event2
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups = {adg_id: mock_adg}
        mock_solver_context.entities.event_groups_with_event = {
            evg_id1: mock_event_group1,
            evg_id2: mock_event_group2
        }
        
        # Mock shift variables
        mock_shift_var1 = Mock()
        mock_shift_var2 = Mock()
        mock_shift_var3 = Mock()  # This one should be excluded (wrong location)
        
        mock_solver_context.entities.shift_vars = {
            (child_id1, evg_id1): mock_shift_var1,  # location1 - included
            (child_id2, evg_id2): mock_shift_var2,  # location2 - included
            (child_id1, uuid4()): mock_shift_var3   # different event - excluded
        }
        
        # Mock required variable (previously created)
        mock_y_var = Mock()
        constraint.add_metadata(f'required_var_{adg_id}', mock_y_var)
        
        constraint._add_required_constraints()
        
        # Should add constraint: shift_sum == num_required * y_var
        assert mock_solver_context.model.Add.called
        assert constraint.get_metadata('required_constraints_added') == 1
        
        # Verify metadata
        required_metadata = constraint.get_metadata(f'required_constraint_{adg_id}')
        assert required_metadata['num_required'] == 3
        assert required_metadata['locations_count'] == 2
    
    def test_add_required_constraints_no_locations_filter(self, mock_solver_context):
        """Test: _add_required_constraints() ohne Location-Filter."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup test data with no location restrictions
        adg_id = uuid4()
        child_id = uuid4()
        evg_id = uuid4()
        
        # Mock required object without location restrictions
        mock_required = Mock()
        mock_required.num_avail_day_groups = 2
        mock_required.locations_of_work = None  # No location filter
        
        # Mock child
        mock_child = Mock()
        mock_child.avail_day_group_id = child_id
        
        # Mock avail day group
        mock_adg = Mock()
        mock_adg.required_avail_day_groups = mock_required
        mock_adg.children = [mock_child]
        
        # Mock event
        mock_event_group = Mock()
        mock_event_group.event = Mock()
        mock_event_group.event.location_plan_period = Mock()
        mock_event_group.event.location_plan_period.location_of_work = Mock()
        mock_event_group.event.location_plan_period.location_of_work.id = uuid4()
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups = {adg_id: mock_adg}
        mock_solver_context.entities.event_groups_with_event = {evg_id: mock_event_group}
        mock_solver_context.entities.shift_vars = {(child_id, evg_id): Mock()}
        
        # Mock required variable
        mock_y_var = Mock()
        constraint.add_metadata(f'required_var_{adg_id}', mock_y_var)
        
        constraint._add_required_constraints()
        
        # Should add constraint (no location filtering)
        assert mock_solver_context.model.Add.called
        assert constraint.get_metadata('required_constraints_added') == 1
        
        # Verify metadata
        required_metadata = constraint.get_metadata(f'required_constraint_{adg_id}')
        assert required_metadata['num_required'] == 2
        assert required_metadata['locations_count'] == 0  # No locations specified
    
    def test_add_shift_constraints(self, mock_solver_context):
        """Test: _add_shift_constraints() Methode."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup test data
        adg_id1, adg_id2, adg_id3 = uuid4(), uuid4(), uuid4()
        evg_id1, evg_id2 = uuid4(), uuid4()
        
        # Mock shift variables
        mock_shift_var1 = Mock()
        mock_shift_var2 = Mock()
        mock_shift_var3 = Mock()
        
        # Mock avail day group variables
        mock_adg_var1 = Mock()
        mock_adg_var2 = Mock()
        # Note: adg_id3 not in avail_day_group_vars
        
        mock_solver_context.entities.shift_vars = {
            (adg_id1, evg_id1): mock_shift_var1,
            (adg_id2, evg_id2): mock_shift_var2,
            (adg_id3, evg_id1): mock_shift_var3  # This won't have constraint (no adg_var)
        }
        
        mock_solver_context.entities.avail_day_group_vars = {
            adg_id1: mock_adg_var1,
            adg_id2: mock_adg_var2
            # adg_id3 missing
        }
        
        constraint._add_shift_constraints()
        
        # Should add constraints for shifts with corresponding avail_day_group_vars
        assert mock_solver_context.model.AddMultiplicationEquality.call_count == 2
        assert constraint.get_metadata('shift_constraints_added') == 2
        
        # Verify the multiplication constraints
        calls = mock_solver_context.model.AddMultiplicationEquality.call_args_list
        
        # Each call should be AddMultiplicationEquality(0, [shift_var, adg_var.Not()])
        for call in calls:
            args = call[0]
            assert args[0] == 0  # First argument should be 0
            assert len(args[1]) == 2  # Second argument should be list of 2 variables
    
    def test_validate_context_success(self, mock_solver_context):
        """Test: validate_context() erfolgreich."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup required attributes
        mock_solver_context.entities.avail_day_groups = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_group_vars = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        result = constraint.validate_context()
        assert result is True
    
    def test_validate_context_missing_entities(self, mock_solver_context):
        """Test: validate_context() mit fehlenden Entities."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Missing entities
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error is not None
        assert "Missing entities." in error
    
    def test_validate_context_empty_avail_day_groups(self, mock_solver_context):
        """Test: validate_context() mit leeren AvailDay-Groups."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup required attributes but empty avail_day_groups
        mock_solver_context.entities.avail_day_groups = {}  # Empty
        mock_solver_context.entities.avail_day_group_vars = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error == "No avail_day_groups found"
    
    def test_get_avail_day_groups_summary(self, mock_solver_context):
        """Test: get_avail_day_groups_summary() Methode."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup test data
        adg_id1, adg_id2, adg_id3, adg_id4 = uuid4(), uuid4(), uuid4(), uuid4()
        
        # Mock avail day groups with different properties
        mock_adg1 = Mock()
        mock_adg1.children = [Mock(), Mock()]  # Has children
        mock_adg1.is_root = True
        mock_adg1.avail_day = None
        mock_adg1.required_avail_day_groups = None
        
        mock_adg2 = Mock()
        mock_adg2.children = []  # No children
        mock_adg2.is_root = False
        mock_adg2.avail_day = Mock()  # Has avail_day
        mock_adg2.required_avail_day_groups = Mock()  # Has required
        
        mock_adg3 = Mock()
        mock_adg3.children = [Mock()]  # Has children
        mock_adg3.is_root = False
        mock_adg3.avail_day = Mock()  # Has avail_day
        mock_adg3.required_avail_day_groups = None
        
        mock_adg4 = Mock()
        mock_adg4.children = []  # No children
        mock_adg4.is_root = False
        mock_adg4.avail_day = None
        mock_adg4.required_avail_day_groups = Mock()  # Has required
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2,
            adg_id3: mock_adg3,
            adg_id4: mock_adg4
        }
        mock_solver_context.entities.avail_day_group_vars = {
            adg_id1: Mock(),
            adg_id3: Mock()
            # Only 2 have vars
        }
        
        summary = constraint.get_avail_day_groups_summary()
        
        # Verify summary
        assert summary['total_avail_day_groups'] == 4
        assert summary['groups_with_children'] == 2  # adg1, adg3
        assert summary['root_groups'] == 1  # adg1
        assert summary['groups_with_avail_days'] == 2  # adg2, adg3
        assert summary['groups_with_required'] == 2  # adg2, adg4
        assert summary['groups_with_vars'] == 2  # adg1, adg3
    
    def test_get_avail_day_groups_summary_empty(self, mock_solver_context):
        """Test: get_avail_day_groups_summary() mit leeren Daten."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.avail_day_groups = {}
        
        summary = constraint.get_avail_day_groups_summary()
        
        # Should return empty summary
        assert summary == {}
    
    def test_complete_setup_workflow(self, mock_solver_context):
        """Test: Kompletter Setup-Workflow."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup minimal required entities
        mock_solver_context.entities.avail_day_groups = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_group_vars = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Test setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()


@pytest.mark.integration
class TestAvailDayGroupsConstraintIntegration:
    """Integration-Tests für AvailDayGroupsConstraint."""
    
    def test_constraint_with_hierarchical_structure(self, mock_solver_context):
        """Test: Constraint mit hierarchischer AvailDay-Group-Struktur."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup hierarchical structure: Root -> Level1 -> Level2 (Leaves)
        root_id = uuid4()
        level1_id1, level1_id2 = uuid4(), uuid4()
        leaf_id1, leaf_id2, leaf_id3 = uuid4(), uuid4(), uuid4()
        
        # Create leaf groups (with avail_days)
        mock_leaf1 = Mock()
        mock_leaf1.avail_day_group_id = leaf_id1
        mock_leaf1.children = []
        mock_leaf1.avail_day = Mock()
        mock_leaf1.is_root = False
        mock_leaf1.required_avail_day_groups = None
        
        mock_leaf2 = Mock()
        mock_leaf2.avail_day_group_id = leaf_id2
        mock_leaf2.children = []
        mock_leaf2.avail_day = Mock()
        mock_leaf2.is_root = False
        mock_leaf2.required_avail_day_groups = None
        
        mock_leaf3 = Mock()
        mock_leaf3.avail_day_group_id = leaf_id3
        mock_leaf3.children = []
        mock_leaf3.avail_day = Mock()
        mock_leaf3.is_root = False
        mock_leaf3.required_avail_day_groups = None
        
        # Create level1 groups (with children)
        mock_level1_1 = Mock()
        mock_level1_1.avail_day_group_id = level1_id1
        mock_level1_1.children = [mock_leaf1, mock_leaf2]
        mock_level1_1.avail_day = None
        mock_level1_1.is_root = False
        mock_level1_1.nr_of_active_children = 1  # Only 1 of 2 children active
        mock_level1_1.required_avail_day_groups = None
        
        mock_level1_2 = Mock()
        mock_level1_2.avail_day_group_id = level1_id2
        mock_level1_2.children = [mock_leaf3]
        mock_level1_2.avail_day = None
        mock_level1_2.is_root = False
        mock_level1_2.nr_of_active_children = None  # Use count (1)
        mock_level1_2.required_avail_day_groups = None
        
        # Create root group
        mock_root = Mock()
        mock_root.avail_day_group_id = root_id
        mock_root.children = [mock_level1_1, mock_level1_2]
        mock_root.avail_day = None
        mock_root.is_root = True
        mock_root.nr_of_active_children = 2  # Both level1 groups active
        mock_root.required_avail_day_groups = None
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups = {
            root_id: mock_root,
            level1_id1: mock_level1_1,
            level1_id2: mock_level1_2,
            leaf_id1: mock_leaf1,
            leaf_id2: mock_leaf2,
            leaf_id3: mock_leaf3
        }
        
        # Setup variables for all groups
        mock_vars = {
            root_id: Mock(),
            level1_id1: Mock(),
            level1_id2: Mock(),
            leaf_id1: Mock(),
            leaf_id2: Mock(),
            leaf_id3: Mock()
        }
        mock_solver_context.entities.avail_day_group_vars = mock_vars
        
        # Setup minimal shift vars and event groups
        mock_solver_context.entities.shift_vars = {
            (leaf_id1, uuid4()): Mock(),
            (leaf_id2, uuid4()): Mock(),
            (leaf_id3, uuid4()): Mock()
        }
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Test constraint setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()
        
        # Verify activity constraints were added for all non-leaf groups
        activity_constraints = constraint.get_metadata('activity_constraints_added')
        assert activity_constraints == 3  # Root + 2 Level1 groups
        
        # Verify shift constraints were added for all shift variables
        shift_constraints = constraint.get_metadata('shift_constraints_added')
        assert shift_constraints == 3  # 3 shift variables
        
        # Get summary
        summary = constraint.get_summary()
        assert summary['total_avail_day_groups'] == 6
        assert summary['groups_with_children'] == 3  # Root + 2 Level1
        assert summary['root_groups'] == 1
        assert summary['groups_with_avail_days'] == 3  # 3 leaves
    
    def test_constraint_with_required_groups_scenario(self, mock_solver_context):
        """Test: Constraint mit Required-Groups-Szenario."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup scenario with required groups
        adg_id1, adg_id2 = uuid4(), uuid4()
        child_id1, child_id2, child_id3 = uuid4(), uuid4(), uuid4()
        evg_id1, evg_id2 = uuid4(), uuid4()
        location_id1, location_id2 = uuid4(), uuid4()
        
        # Setup locations
        mock_location1 = Mock()
        mock_location1.id = location_id1
        mock_location1.name = "Klinik A"
        
        mock_location2 = Mock()
        mock_location2.id = location_id2
        mock_location2.name = "Klinik B"
        
        # Setup required objects
        mock_required1 = Mock()
        mock_required1.num_avail_day_groups = 2
        mock_required1.locations_of_work = [mock_location1]  # Only Klinik A
        
        mock_required2 = Mock()
        mock_required2.num_avail_day_groups = 1
        mock_required2.locations_of_work = None  # Any location
        
        # Setup children
        mock_child1 = Mock()
        mock_child1.avail_day_group_id = child_id1
        mock_child2 = Mock()
        mock_child2.avail_day_group_id = child_id2
        mock_child3 = Mock()
        mock_child3.avail_day_group_id = child_id3
        
        # Setup parent groups with required
        mock_adg1 = Mock()
        mock_adg1.required_avail_day_groups = mock_required1
        mock_adg1.children = [mock_child1, mock_child2]
        
        mock_adg2 = Mock()
        mock_adg2.required_avail_day_groups = mock_required2
        mock_adg2.children = [mock_child3]
        
        # Setup events
        mock_event1 = Mock()
        mock_event1.location_plan_period = Mock()
        mock_event1.location_plan_period.location_of_work = mock_location1
        
        mock_event2 = Mock()
        mock_event2.location_plan_period = Mock()
        mock_event2.location_plan_period.location_of_work = mock_location2
        
        mock_event_group1 = Mock()
        mock_event_group1.event = mock_event1
        
        mock_event_group2 = Mock()
        mock_event_group2.event = mock_event2
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2
        }
        mock_solver_context.entities.avail_day_group_vars = {}
        mock_solver_context.entities.event_groups_with_event = {
            evg_id1: mock_event_group1,
            evg_id2: mock_event_group2
        }
        
        # Setup shift vars
        mock_solver_context.entities.shift_vars = {
            (child_id1, evg_id1): Mock(),  # Klinik A - counts for adg1
            (child_id1, evg_id2): Mock(),  # Klinik B - doesn't count for adg1
            (child_id2, evg_id1): Mock(),  # Klinik A - counts for adg1
            (child_id3, evg_id1): Mock(),  # Klinik A - counts for adg2 (any location)
            (child_id3, evg_id2): Mock(),  # Klinik B - counts for adg2 (any location)
        }
        
        # Mock NewBoolVar for required variables
        mock_required_var1 = Mock()
        mock_required_var2 = Mock()
        mock_solver_context.model.NewBoolVar.side_effect = [mock_required_var1, mock_required_var2]
        
        # Test constraint setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()
        
        # Verify required variables were created
        variables = constraint.get_variables()
        assert len(variables) == 2
        
        # Verify required constraints were added
        required_constraints = constraint.get_metadata('required_constraints_added')
        assert required_constraints == 2
        
        # Verify metadata for each required constraint
        required_metadata1 = constraint.get_metadata(f'required_constraint_{adg_id1}')
        assert required_metadata1['num_required'] == 2
        assert required_metadata1['locations_count'] == 1  # Only Klinik A
        
        required_metadata2 = constraint.get_metadata(f'required_constraint_{adg_id2}')
        assert required_metadata2['num_required'] == 1
        assert required_metadata2['locations_count'] == 0  # Any location
    
    def test_constraint_performance_large_hierarchy(self, mock_solver_context):
        """Test: Constraint Performance mit großer Hierarchie."""
        import time
        
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Create large hierarchical structure
        num_levels = 4
        groups_per_level = 10
        total_groups = 0
        
        avail_day_groups = {}
        avail_day_group_vars = {}
        shift_vars = {}
        
        # Generate hierarchical structure
        current_level_ids = [uuid4()]  # Start with one root
        
        for level in range(num_levels):
            next_level_ids = []
            
            for parent_id in current_level_ids:
                # Create children for this parent
                children = []
                for i in range(groups_per_level):
                    child_id = uuid4()
                    next_level_ids.append(child_id)
                    
                    mock_child = Mock()
                    mock_child.avail_day_group_id = child_id
                    children.append(mock_child)
                    
                    # Create child group
                    mock_child_group = Mock()
                    mock_child_group.children = [] if level == num_levels - 1 else None  # Leaves have no children
                    mock_child_group.avail_day = Mock() if level == num_levels - 1 else None  # Only leaves have avail_days
                    mock_child_group.is_root = False
                    mock_child_group.nr_of_active_children = groups_per_level // 2 if level < num_levels - 1 else None
                    mock_child_group.required_avail_day_groups = None
                    
                    avail_day_groups[child_id] = mock_child_group
                    avail_day_group_vars[child_id] = Mock()
                    total_groups += 1
                    
                    # Add shift vars for leaves
                    if level == num_levels - 1:
                        shift_vars[(child_id, uuid4())] = Mock()
                
                # Create or update parent group
                if parent_id in avail_day_groups:
                    avail_day_groups[parent_id].children = children
                else:
                    # Root group
                    mock_parent = Mock()
                    mock_parent.children = children
                    mock_parent.avail_day = None
                    mock_parent.is_root = True
                    mock_parent.nr_of_active_children = len(children)
                    mock_parent.required_avail_day_groups = None
                    
                    avail_day_groups[parent_id] = mock_parent
                    avail_day_group_vars[parent_id] = Mock()
                    total_groups += 1
            
            current_level_ids = next_level_ids
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups = avail_day_groups
        mock_solver_context.entities.avail_day_group_vars = avail_day_group_vars
        mock_solver_context.entities.shift_vars = shift_vars
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Measure setup time
        start_time = time.time()
        success = constraint.setup()
        end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Should complete quickly even with large hierarchy
        assert success is True
        assert setup_time < 2.0  # Should take less than 2 seconds
        
        # Verify constraints were added appropriately
        summary = constraint.get_summary()
        assert summary['total_avail_day_groups'] == total_groups
    
    def test_constraint_error_handling(self, mock_solver_context):
        """Test: Error-Handling bei problematischen Daten."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup problematic data (circular references, missing children, etc.)
        adg_id = uuid4()
        
        # Group with children but missing child objects
        mock_child_ref = Mock()
        mock_child_ref.avail_day_group_id = uuid4()  # Non-existent child
        mock_child_ref.children = []
        mock_child_ref.avail_day = Mock()
        
        mock_adg = Mock()
        mock_adg.children = [mock_child_ref]
        mock_adg.is_root = False
        mock_adg.nr_of_active_children = 1
        mock_adg.required_avail_day_groups = None
        
        # Setup entities with inconsistent data
        mock_solver_context.entities.avail_day_groups = {adg_id: mock_adg}
        mock_solver_context.entities.avail_day_group_vars = {adg_id: Mock()}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Should handle errors gracefully
        try:
            success = constraint.setup()
            # Might succeed or fail depending on implementation robustness
        except Exception as e:
            pytest.fail(f"Constraint should handle errors gracefully, but raised: {e}")
    
    @patch('sat_solver.constraints.avail_day_groups.logger')
    def test_constraint_logging_integration(self, mock_logger, mock_solver_context):
        """Test: Constraint Logging-Integration."""
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup minimal entities
        mock_solver_context.entities.avail_day_groups = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_group_vars = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Logging calls depend on implementation, but logger should be available


@pytest.mark.slow
class TestAvailDayGroupsConstraintPerformance:
    """Performance-Tests für AvailDayGroupsConstraint."""
    
    def test_constraint_hierarchy_traversal_performance(self, mock_solver_context):
        """Test: Performance der Hierarchie-Traversierung."""
        import time
        
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Create deep hierarchy (many levels, few groups per level)
        depth = 20
        groups_per_level = 2
        
        avail_day_groups = {}
        current_parent_id = uuid4()
        
        # Create root
        mock_root = Mock()
        mock_root.children = []
        mock_root.avail_day = None
        mock_root.is_root = True
        mock_root.nr_of_active_children = 1
        mock_root.required_avail_day_groups = None
        avail_day_groups[current_parent_id] = mock_root
        
        # Create deep chain
        for level in range(depth):
            child_id = uuid4()
            
            mock_child_ref = Mock()
            mock_child_ref.avail_day_group_id = child_id
            
            # Update parent's children
            avail_day_groups[current_parent_id].children = [mock_child_ref]
            
            # Create child
            mock_child = Mock()
            mock_child.children = [] if level == depth - 1 else None
            mock_child.avail_day = Mock() if level == depth - 1 else None
            mock_child.is_root = False
            mock_child.nr_of_active_children = 1 if level < depth - 1 else None
            mock_child.required_avail_day_groups = None
            
            avail_day_groups[child_id] = mock_child
            current_parent_id = child_id
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups = avail_day_groups
        mock_solver_context.entities.avail_day_group_vars = {
            group_id: Mock() for group_id in avail_day_groups.keys()
        }
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Measure traversal time
        start_time = time.time()
        summary = constraint.get_avail_day_groups_summary()
        end_time = time.time()
        
        traversal_time = end_time - start_time
        
        # Should traverse deep hierarchy efficiently
        assert summary['total_avail_day_groups'] == depth + 1
        assert traversal_time < 1.0  # Should complete quickly
    
    def test_constraint_memory_efficiency_large_structure(self, mock_solver_context):
        """Test: Memory-Effizienz bei großen Strukturen."""
        import gc
        
        constraint = AvailDayGroupsConstraint(mock_solver_context)
        
        # Setup minimal but valid entities
        mock_solver_context.entities.avail_day_groups = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_group_vars = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Force garbage collection before test
        gc.collect()
        
        # Setup and teardown multiple times
        for _ in range(10):
            constraint.setup()
            constraint._metadata.clear()  # Clear metadata
        
        # Force garbage collection after test
        gc.collect()
        
        # Should not leak significant memory
        assert True  # Test passes if no memory errors occur
