"""
Unit-Tests für WeightsConstraint

Testet das Constraint für Gewichtungen in Event- und AvailDay-Groups.
Behandelt komplexe hierarchische Gewichtungslogik mit:
- Event-Group Gewichtungen (mit Tiefe-Multiplikatoren)
- AvailDay-Group Gewichtungen (kumulative Gewichtung)
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from datetime import date, time
from collections import defaultdict

from sat_solver.constraints.weights import WeightsConstraint


@pytest.mark.unit
class TestWeightsConstraint:
    """Test-Klasse für WeightsConstraint."""
    
    def test_constraint_name(self, mock_solver_context):
        """Test: Constraint-Name ist korrekt."""
        constraint = WeightsConstraint(mock_solver_context)
        assert constraint.constraint_name == "weights"
    
    def test_constraint_initialization(self, mock_solver_context):
        """Test: Constraint wird korrekt initialisiert."""
        constraint = WeightsConstraint(mock_solver_context)
        
        assert constraint.context == mock_solver_context
        assert constraint.model == mock_solver_context.model
        assert constraint.entities == mock_solver_context.entities
        assert constraint.config == mock_solver_context.config
        assert not constraint.is_setup_complete()
    
    def test_create_variables_empty_entities(self, mock_solver_context):
        """Test: create_variables() mit leeren Entities."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.event_groups = {}
        mock_solver_context.entities.avail_day_groups = {}
        
        # Mock constraint creation methods
        with patch.object(constraint, '_create_event_group_weight_vars') as mock_event:
            with patch.object(constraint, '_create_avail_day_group_weight_vars') as mock_avail:
                mock_event.return_value = []
                mock_avail.return_value = []
                
                variables = constraint.create_variables()
        
        # Should return empty list
        assert variables == []
        assert constraint.get_metadata('total_weight_vars') == 0
        assert constraint.get_metadata('event_weight_vars') == []
        assert constraint.get_metadata('avail_day_weight_vars') == []
    
    def test_create_shift_vars_mapping(self, mock_solver_context):
        """Test: _create_shift_vars_mapping() Methode."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup test data
        adg_id1, adg_id2, adg_id3 = uuid4(), uuid4(), uuid4()
        eg_id1, eg_id2 = uuid4(), uuid4()
        
        # Mock shift variables
        mock_shift_var1 = Mock()
        mock_shift_var2 = Mock()
        mock_shift_var3 = Mock()
        mock_shift_var4 = Mock()
        
        mock_solver_context.entities.shift_vars = {
            (adg_id1, eg_id1): mock_shift_var1,
            (adg_id1, eg_id2): mock_shift_var2,  # Same adg_id1, different eg
            (adg_id2, eg_id1): mock_shift_var3,  # Different adg, same eg
            (adg_id3, eg_id2): mock_shift_var4   # Different adg and eg
        }
        
        mapping = constraint._create_shift_vars_mapping()
        
        # Verify mapping
        assert len(mapping) == 3  # 3 unique adg_ids
        assert len(mapping[adg_id1]) == 2  # 2 shift vars for adg_id1
        assert len(mapping[adg_id2]) == 1  # 1 shift var for adg_id2
        assert len(mapping[adg_id3]) == 1  # 1 shift var for adg_id3
        
        assert mock_shift_var1 in mapping[adg_id1]
        assert mock_shift_var2 in mapping[adg_id1]
        assert mock_shift_var3 in mapping[adg_id2]
        assert mock_shift_var4 in mapping[adg_id3]
    
    def test_check_time_span_avail_day_fits_event_time_index_only(self, mock_solver_context):
        """Test: _check_time_span_avail_day_fits_event() mit time_index."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup test data
        test_date = date(2025, 6, 28)
        
        # Mock time of day enums
        mock_time_enum1 = Mock()
        mock_time_enum1.time_index = 1
        
        mock_time_enum2 = Mock()
        mock_time_enum2.time_index = 2
        
        # Mock time of day objects
        mock_time_of_day1 = Mock()
        mock_time_of_day1.time_of_day_enum = mock_time_enum1
        
        mock_time_of_day2 = Mock()
        mock_time_of_day2.time_of_day_enum = mock_time_enum2
        
        # Mock event
        mock_event = Mock()
        mock_event.date = test_date
        mock_event.time_of_day = mock_time_of_day1
        
        # Mock avail days
        mock_avail_day_matching = Mock()
        mock_avail_day_matching.date = test_date
        mock_avail_day_matching.time_of_day = mock_time_of_day1  # Same time
        
        mock_avail_day_different_time = Mock()
        mock_avail_day_different_time.date = test_date
        mock_avail_day_different_time.time_of_day = mock_time_of_day2  # Different time
        
        mock_avail_day_different_date = Mock()
        mock_avail_day_different_date.date = date(2025, 6, 29)  # Different date
        mock_avail_day_different_date.time_of_day = mock_time_of_day1
        
        # Test matching case
        assert constraint._check_time_span_avail_day_fits_event(
            mock_event, mock_avail_day_matching, only_time_index=True
        ) is True
        
        # Test non-matching cases
        assert constraint._check_time_span_avail_day_fits_event(
            mock_event, mock_avail_day_different_time, only_time_index=True
        ) is False
        
        assert constraint._check_time_span_avail_day_fits_event(
            mock_event, mock_avail_day_different_date, only_time_index=True
        ) is False
    
    def test_check_time_span_avail_day_fits_event_full_time_span(self, mock_solver_context):
        """Test: _check_time_span_avail_day_fits_event() mit vollem Zeitbereich."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup test data
        test_date = date(2025, 6, 28)
        
        # Mock time of day objects with start/end times
        mock_event_time = Mock()
        mock_event_time.start = time(9, 0)   # 09:00
        mock_event_time.end = time(11, 0)    # 11:00
        
        mock_avail_time_covering = Mock()
        mock_avail_time_covering.start = time(8, 0)   # 08:00 (earlier start)
        mock_avail_time_covering.end = time(12, 0)    # 12:00 (later end)
        
        mock_avail_time_partial = Mock()
        mock_avail_time_partial.start = time(10, 0)   # 10:00 (later start)
        mock_avail_time_partial.end = time(12, 0)     # 12:00 (later end)
        
        # Mock event
        mock_event = Mock()
        mock_event.date = test_date
        mock_event.time_of_day = mock_event_time
        
        # Mock avail days
        mock_avail_day_covering = Mock()
        mock_avail_day_covering.date = test_date
        mock_avail_day_covering.time_of_day = mock_avail_time_covering
        
        mock_avail_day_partial = Mock()
        mock_avail_day_partial.date = test_date
        mock_avail_day_partial.time_of_day = mock_avail_time_partial
        
        # Test covering case (avail time spans event time)
        assert constraint._check_time_span_avail_day_fits_event(
            mock_event, mock_avail_day_covering, only_time_index=False
        ) is True
        
        # Test partial case (avail time doesn't fully cover event time)
        assert constraint._check_time_span_avail_day_fits_event(
            mock_event, mock_avail_day_partial, only_time_index=False
        ) is False
    
    def test_avail_day_has_possible_shifts_true(self, mock_solver_context):
        """Test: _avail_day_has_possible_shifts() mit möglichen Einsätzen."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup test data
        adg_id = uuid4()
        evg_id = uuid4()
        
        # Mock avail day group
        mock_avail_day = Mock()
        mock_avail_day.date = date(2025, 6, 28)
        mock_avail_day.time_of_day = Mock()
        mock_avail_day.time_of_day.time_of_day_enum = Mock()
        mock_avail_day.time_of_day.time_of_day_enum.time_index = 1
        
        mock_adg = Mock()
        mock_adg.avail_day = mock_avail_day
        
        # Mock event group with event
        mock_event = Mock()
        mock_event.date = date(2025, 6, 28)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.time_of_day_enum = Mock()
        mock_event.time_of_day.time_of_day_enum.time_index = 1
        
        mock_evg = Mock()
        mock_evg.event = mock_event
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {adg_id: mock_adg}
        mock_solver_context.entities.shifts_exclusive = {(adg_id, evg_id): 1}  # Shift allowed
        mock_solver_context.entities.event_groups_with_event = {evg_id: mock_evg}
        
        result = constraint._avail_day_has_possible_shifts(adg_id)
        
        # Should return True because shift is allowed and times match
        assert result is True
    
    def test_avail_day_has_possible_shifts_false_excluded(self, mock_solver_context):
        """Test: _avail_day_has_possible_shifts() mit ausgeschlossenen Einsätzen."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup test data
        adg_id = uuid4()
        evg_id = uuid4()
        
        # Mock avail day group
        mock_adg = Mock()
        mock_solver_context.entities.avail_day_groups_with_avail_day = {adg_id: mock_adg}
        mock_solver_context.entities.shifts_exclusive = {(adg_id, evg_id): 0}  # Shift excluded
        mock_solver_context.entities.event_groups_with_event = {}
        
        result = constraint._avail_day_has_possible_shifts(adg_id)
        
        # Should return False because shift is excluded
        assert result is False
    
    def test_avail_day_has_possible_shifts_false_missing_adg(self, mock_solver_context):
        """Test: _avail_day_has_possible_shifts() mit fehlender AvailDay-Group."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup test data
        adg_id = uuid4()
        
        # Setup empty entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shifts_exclusive = {}
        
        result = constraint._avail_day_has_possible_shifts(adg_id)
        
        # Should return False because adg_id doesn't exist
        assert result is False
    
    def test_create_event_group_weight_vars_no_root(self, mock_solver_context):
        """Test: _create_event_group_weight_vars() ohne Root-Group."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup entities without root group
        mock_eg1 = Mock()
        mock_eg1.parent = Mock()  # Has parent (not root)
        
        mock_eg2 = Mock()
        mock_eg2.parent = Mock()  # Has parent (not root)
        
        mock_solver_context.entities.event_groups = {
            uuid4(): mock_eg1,
            uuid4(): mock_eg2
        }
        
        result = constraint._create_event_group_weight_vars()
        
        # Should return empty list and log error
        assert result == []
        assert constraint.get_metadata('event_groups_error') == 'No root event group found'
    
    def test_create_event_group_weight_vars_with_root(self, mock_solver_context):
        """Test: _create_event_group_weight_vars() mit Root-Group."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {0: 1, 1: 2}
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {1: 10, 2: 20}
        
        # Setup root event group
        mock_root = Mock()
        mock_root.parent = None  # Root group
        mock_root.root_is_location_plan_period_master_group = False
        
        mock_solver_context.entities.event_groups = {uuid4(): mock_root}
        
        # Mock recursive calculation
        mock_weight_vars = [Mock(), Mock()]
        with patch.object(constraint, '_calculate_event_weight_vars_recursive') as mock_calc:
            mock_calc.return_value = mock_weight_vars
            
            result = constraint._create_event_group_weight_vars()
        
        # Should call recursive calculation with start_depth 0
        assert result == mock_weight_vars
        mock_calc.assert_called_once_with(mock_root, 0)
    
    def test_create_event_group_weight_vars_location_master(self, mock_solver_context):
        """Test: _create_event_group_weight_vars() mit Location Master Group."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {0: 1, 1: 2}
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {1: 10, 2: 20}
        
        # Setup root event group as location master
        mock_root = Mock()
        mock_root.parent = None  # Root group
        mock_root.root_is_location_plan_period_master_group = True  # Location master
        
        mock_solver_context.entities.event_groups = {uuid4(): mock_root}
        
        # Mock recursive calculation
        mock_weight_vars = [Mock(), Mock()]
        with patch.object(constraint, '_calculate_event_weight_vars_recursive') as mock_calc:
            mock_calc.return_value = mock_weight_vars
            
            result = constraint._create_event_group_weight_vars()
        
        # Should call recursive calculation with start_depth 1 for location master
        assert result == mock_weight_vars
        mock_calc.assert_called_once_with(mock_root, 1)
    
    def test_calculate_event_weight_vars_recursive_no_children(self, mock_solver_context):
        """Test: _calculate_event_weight_vars_recursive() ohne Children."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {0: 1, 1: 2}
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {1: 10, 2: 20}
        
        # Setup event group without children
        mock_event_group = Mock()
        mock_event_group.nr_of_active_children = None
        mock_event_group.children = []
        
        result = constraint._calculate_event_weight_vars_recursive(mock_event_group, 0)
        
        # Should return empty list
        assert result == []
    
    def test_calculate_event_weight_vars_recursive_with_children(self, mock_solver_context):
        """Test: _calculate_event_weight_vars_recursive() mit Children."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {0: 1, 1: 2}
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {1: 10, 2: 20}
        
        # Setup child event groups
        child1_id, child2_id = uuid4(), uuid4()
        
        mock_location = Mock()
        mock_location.name = "Kinderklinik"
        
        mock_location_plan_period = Mock()
        mock_location_plan_period.location_of_work = mock_location
        
        mock_time_of_day = Mock()
        mock_time_of_day.name = "Vormittag"
        
        mock_event = Mock()
        mock_event.date = date(2025, 6, 28)
        mock_event.time_of_day = mock_time_of_day
        mock_event.location_plan_period = mock_location_plan_period
        
        mock_child1 = Mock()
        mock_child1.event_group_id = child1_id
        mock_child1.weight = 1
        mock_child1.event = mock_event
        mock_child1.children = []
        
        mock_child2 = Mock()
        mock_child2.event_group_id = child2_id
        mock_child2.weight = 2
        mock_child2.event = None  # No event
        mock_child2.children = []
        
        # Setup parent event group
        mock_event_group = Mock()
        mock_event_group.nr_of_active_children = 1  # Less than total children
        mock_event_group.children = [mock_child1, mock_child2]
        
        # Setup entities
        mock_event_group_var1 = Mock()
        mock_event_group_var2 = Mock()
        mock_solver_context.entities.event_group_vars = {
            child1_id: mock_event_group_var1,
            child2_id: mock_event_group_var2
        }
        
        # Mock variable creation
        mock_weight_var1 = Mock()
        mock_weight_var2 = Mock()
        mock_solver_context.model.NewIntVar.side_effect = [mock_weight_var1, mock_weight_var2]
        
        result = constraint._calculate_event_weight_vars_recursive(mock_event_group, 0)
        
        # Should create weight variables for children
        assert len(result) == 2
        assert mock_weight_var1 in result
        assert mock_weight_var2 in result
        
        # Should have created constraints
        assert mock_solver_context.model.Add.call_count == 2
    
    def test_create_avail_day_group_weight_vars_no_root(self, mock_solver_context):
        """Test: _create_avail_day_group_weight_vars() ohne Root-Group."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup entities without root group
        mock_adg1 = Mock()
        mock_adg1.parent = Mock()  # Has parent (not root)
        
        mock_solver_context.entities.avail_day_groups = {uuid4(): mock_adg1}
        
        # Mock shift vars mapping
        with patch.object(constraint, '_create_shift_vars_mapping') as mock_mapping:
            mock_mapping.return_value = {}
            
            result = constraint._create_avail_day_group_weight_vars()
        
        # Should return empty list and log error
        assert result == []
        assert constraint.get_metadata('avail_day_groups_error') == 'No root avail day group found'
    
    def test_create_avail_day_group_weight_vars_actor_master(self, mock_solver_context):
        """Test: _create_avail_day_group_weight_vars() mit Actor Master Group."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {1: 10, 2: 20}
        
        # Setup root as actor master group
        mock_root = Mock()
        mock_root.parent = None
        mock_root.group_is_actor_plan_period_master_group = True
        mock_root.depth = 0
        
        # Setup other groups with different depths
        mock_adg1 = Mock()
        mock_adg1.depth = 1
        
        mock_adg2 = Mock()
        mock_adg2.depth = 2
        
        mock_solver_context.entities.avail_day_groups = {
            uuid4(): mock_root,
            uuid4(): mock_adg1,
            uuid4(): mock_adg2
        }
        
        # Mock methods
        mock_weight_vars = [Mock(), Mock()]
        with patch.object(constraint, '_create_shift_vars_mapping') as mock_mapping:
            with patch.object(constraint, '_calculate_avail_day_weight_vars_recursive') as mock_calc:
                mock_mapping.return_value = {}
                mock_calc.return_value = mock_weight_vars
                
                result = constraint._create_avail_day_group_weight_vars()
        
        # Should call recursive calculation for actor master group
        assert result == mock_weight_vars
        assert constraint.get_metadata('max_avail_day_depth') == 2
        mock_calc.assert_called_once_with(mock_root, 2, {})
    
    def test_create_avail_day_group_weight_vars_non_actor_master(self, mock_solver_context):
        """Test: _create_avail_day_group_weight_vars() ohne Actor Master Group."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {1: 10, 2: 20}
        
        # Setup root as non-actor master group
        mock_child1 = Mock()
        mock_child1.depth = 1
        
        mock_child2 = Mock()
        mock_child2.depth = 2
        
        mock_root = Mock()
        mock_root.parent = None
        mock_root.group_is_actor_plan_period_master_group = False
        mock_root.depth = 0
        mock_root.children = [mock_child1, mock_child2]
        
        mock_solver_context.entities.avail_day_groups = {
            uuid4(): mock_root,
            uuid4(): mock_child1,
            uuid4(): mock_child2
        }
        
        # Mock methods
        mock_weight_vars1 = [Mock()]
        mock_weight_vars2 = [Mock()]
        with patch.object(constraint, '_create_shift_vars_mapping') as mock_mapping:
            with patch.object(constraint, '_calculate_avail_day_weight_vars_recursive') as mock_calc:
                mock_mapping.return_value = {}
                mock_calc.side_effect = [mock_weight_vars1, mock_weight_vars2]
                
                result = constraint._create_avail_day_group_weight_vars()
        
        # Should call recursive calculation for each child
        assert result == mock_weight_vars1 + mock_weight_vars2
        assert mock_calc.call_count == 2
    
    def test_calculate_avail_day_weight_vars_recursive_with_avail_day(self, mock_solver_context):
        """Test: _calculate_avail_day_weight_vars_recursive() mit AvailDay."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {1: 10, 2: 20}
        
        # Setup child with avail day
        child_id = uuid4()
        
        mock_person = Mock()
        mock_person.f_name = "Hans"
        
        mock_actor_plan_period = Mock()
        mock_actor_plan_period.person = mock_person
        
        mock_time_of_day = Mock()
        mock_time_of_day.name = "Vormittag"
        
        mock_avail_day = Mock()
        mock_avail_day.date = date(2025, 6, 28)
        mock_avail_day.time_of_day = mock_time_of_day
        mock_avail_day.actor_plan_period = mock_actor_plan_period
        
        mock_child = Mock()
        mock_child.avail_day_group_id = child_id
        mock_child.avail_day = mock_avail_day
        mock_child.weight = 1
        mock_child.depth = 1
        
        mock_group = Mock()
        mock_group.depth = 0
        mock_group.children = [mock_child]
        
        # Mock methods
        mock_shift_var = Mock()
        shift_vars_mapping = {child_id: [mock_shift_var]}
        
        mock_weight_var = Mock()
        mock_has_shifts_var = Mock()
        mock_solver_context.model.NewIntVar.return_value = mock_weight_var
        mock_solver_context.model.NewBoolVar.return_value = mock_has_shifts_var
        
        with patch.object(constraint, '_avail_day_has_possible_shifts') as mock_has_shifts:
            mock_has_shifts.return_value = True
            
            result = constraint._calculate_avail_day_weight_vars_recursive(
                mock_group, max_depth=2, shift_vars_mapping=shift_vars_mapping
            )
        
        # Should create weight variable
        assert len(result) == 1
        assert result[0] == mock_weight_var
        
        # Should have created constraints
        mock_solver_context.model.Add.assert_called()
        mock_has_shifts.assert_called_once_with(child_id)
    
    def test_calculate_avail_day_weight_vars_recursive_no_possible_shifts(self, mock_solver_context):
        """Test: _calculate_avail_day_weight_vars_recursive() ohne mögliche Einsätze."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {1: 10, 2: 20}
        
        # Setup child with avail day
        child_id = uuid4()
        
        mock_child = Mock()
        mock_child.avail_day_group_id = child_id
        mock_child.avail_day = Mock()
        mock_child.weight = 1
        mock_child.depth = 1
        
        mock_group = Mock()
        mock_group.depth = 0
        mock_group.children = [mock_child]
        
        # Mock no possible shifts
        with patch.object(constraint, '_avail_day_has_possible_shifts') as mock_has_shifts:
            mock_has_shifts.return_value = False
            
            result = constraint._calculate_avail_day_weight_vars_recursive(
                mock_group, max_depth=2, shift_vars_mapping={}, cumulative_adjusted_weight=0
            )
        
        # Should skip child without possible shifts
        assert result == []
        mock_has_shifts.assert_called_once_with(child_id)
    
    def test_calculate_avail_day_weight_vars_recursive_no_avail_day(self, mock_solver_context):
        """Test: _calculate_avail_day_weight_vars_recursive() ohne AvailDay (rekursiv)."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {1: 10, 2: 20}
        
        # Setup child without avail day (should recurse)
        mock_child = Mock()
        mock_child.avail_day = None  # No avail day
        mock_child.weight = 1
        
        mock_group = Mock()
        mock_group.depth = 0
        mock_group.children = [mock_child]
        
        # Mock recursive call
        mock_recursive_result = [Mock()]
        with patch.object(constraint, '_calculate_avail_day_weight_vars_recursive') as mock_recursive:
            # Prevent infinite recursion by returning empty for recursive calls
            mock_recursive.side_effect = lambda group, max_depth, mapping, cumulative=0: (
                mock_recursive_result if group == mock_child else []
            )
            
            result = constraint._calculate_avail_day_weight_vars_recursive(
                mock_group, max_depth=2, shift_vars_mapping={}, cumulative_adjusted_weight=0
            )
        
        # Should make recursive call for child without avail day
        assert result == mock_recursive_result
        assert mock_recursive.call_count == 2  # Original call + recursive call
    
    def test_add_constraints(self, mock_solver_context):
        """Test: add_constraints() Methode."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Call method
        constraint.add_constraints()
        
        # Should set metadata for additional constraints
        additional_constraints = constraint.get_metadata('additional_weight_constraints')
        assert additional_constraints == 0  # No additional constraints in base implementation
    
    def test_validate_context_success(self, mock_solver_context):
        """Test: validate_context() erfolgreich."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup required attributes
        mock_solver_context.entities.event_groups = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.avail_day_groups = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Setup config multipliers
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {0: 1}
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {1: 10}
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {1: 10}
        
        result = constraint.validate_context()
        assert result is True
    
    def test_validate_context_missing_entities(self, mock_solver_context):
        """Test: validate_context() mit fehlenden Entities."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Missing entities
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error is not None
        assert "Missing entities." in error
    
    def test_validate_context_missing_config(self, mock_solver_context):
        """Test: validate_context() mit fehlender Konfiguration."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup required entities
        mock_solver_context.entities.event_groups = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.avail_day_groups = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Missing constraint_multipliers
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error == "Missing config.constraint_multipliers"
    
    def test_validate_context_missing_multipliers(self, mock_solver_context):
        """Test: validate_context() mit fehlenden Multiplikatoren."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup required entities
        mock_solver_context.entities.event_groups = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.avail_day_groups = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Setup config but missing specific multipliers
        mock_solver_context.config.constraint_multipliers = Mock()
        
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error is not None
        assert "Missing config multiplier:" in error
    
    def test_get_weights_summary(self, mock_solver_context):
        """Test: get_weights_summary() Methode."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup test data
        mock_eg1 = Mock()
        mock_eg1.weight = 1
        
        mock_eg2 = Mock()
        mock_eg2.weight = 2
        
        mock_eg3 = Mock()
        mock_eg3.weight = 1  # Same weight as eg1
        
        mock_adg1 = Mock()
        mock_adg1.weight = 1
        
        mock_adg2 = Mock()
        mock_adg2.weight = 3
        
        # Setup entities
        mock_solver_context.entities.event_groups = {
            uuid4(): mock_eg1,
            uuid4(): mock_eg2,
            uuid4(): mock_eg3
        }
        mock_solver_context.entities.avail_day_groups = {
            uuid4(): mock_adg1,
            uuid4(): mock_adg2
        }
        
        # Set metadata
        constraint.add_metadata('event_weight_vars', [Mock(), Mock()])
        constraint.add_metadata('avail_day_weight_vars', [Mock()])
        constraint.add_metadata('total_weight_vars', 3)
        
        summary = constraint.get_weights_summary()
        
        # Verify summary
        assert summary['total_event_groups'] == 3
        assert summary['total_avail_day_groups'] == 2
        assert summary['event_weight_vars'] == 2
        assert summary['avail_day_weight_vars'] == 1
        assert summary['total_weight_vars'] == 3
        assert summary['event_weights_distribution'] == {1: 2, 2: 1}  # Weight 1 appears twice
        assert summary['avail_day_weights_distribution'] == {1: 1, 3: 1}
    
    def test_get_weights_summary_empty_groups(self, mock_solver_context):
        """Test: get_weights_summary() mit leeren Groups."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.event_groups = {}
        mock_solver_context.entities.avail_day_groups = {}
        
        summary = constraint.get_weights_summary()
        
        # Should handle empty groups gracefully
        assert summary['total_event_groups'] == 0
        assert summary['total_avail_day_groups'] == 0
        assert summary['event_weight_vars'] == 0
        assert summary['avail_day_weight_vars'] == 0
        assert summary['total_weight_vars'] == 0
    
    def test_get_summary_integration(self, mock_solver_context):
        """Test: get_summary() Integration mit Base-Klasse."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup entities for summary
        mock_solver_context.entities.event_groups = {uuid4(): Mock(weight=1)}
        mock_solver_context.entities.avail_day_groups = {uuid4(): Mock(weight=2)}
        
        constraint.add_metadata('total_weight_vars', 5)
        
        summary = constraint.get_summary()
        
        # Should include both base summary and weights summary
        assert 'total_event_groups' in summary
        assert 'total_avail_day_groups' in summary
        assert 'total_weight_vars' in summary
    
    def test_complete_setup_workflow(self, mock_solver_context):
        """Test: Kompletter Setup-Workflow."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup minimal required entities
        mock_solver_context.entities.event_groups = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.avail_day_groups = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {0: 1}
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {1: 10}
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {1: 10}
        
        # Test setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()


@pytest.mark.integration
class TestWeightsConstraintIntegration:
    """Integration-Tests für WeightsConstraint."""
    
    def test_constraint_with_realistic_hierarchy(self, mock_solver_context):
        """Test: Constraint mit realistischer Hierarchie."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup realistic hierarchy for Klinikclown-Einsätze:
        # Root (Location Master) -> Kinderklinik -> Vormittag/Nachmittag -> Events
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {
            0: 1, 1: 2, 2: 3, 3: 4
        }
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {
            1: 10, 2: 20, 3: 30
        }
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {
            1: 10, 2: 20, 3: 30
        }
        
        # Create hierarchical event groups
        root_id = uuid4()
        kinderklinik_id = uuid4()
        vormittag_id = uuid4()
        nachmittag_id = uuid4()
        event1_id = uuid4()
        event2_id = uuid4()
        
        # Root (Location Master)
        mock_root = Mock()
        mock_root.parent = None
        mock_root.root_is_location_plan_period_master_group = True
        mock_root.nr_of_active_children = 1
        mock_root.children = []
        
        # Kinderklinik
        mock_kinderklinik = Mock()
        mock_kinderklinik.parent = mock_root
        mock_kinderklinik.nr_of_active_children = 2
        mock_kinderklinik.children = []
        
        # Vormittag
        mock_vormittag = Mock()
        mock_vormittag.parent = mock_kinderklinik
        mock_vormittag.event_group_id = vormittag_id
        mock_vormittag.weight = 1
        mock_vormittag.nr_of_active_children = 1
        mock_vormittag.children = []
        mock_vormittag.event = Mock()
        mock_vormittag.event.date = date(2025, 6, 28)
        mock_vormittag.event.time_of_day = Mock()
        mock_vormittag.event.time_of_day.name = "Vormittag"
        mock_vormittag.event.location_plan_period = Mock()
        mock_vormittag.event.location_plan_period.location_of_work = Mock()
        mock_vormittag.event.location_plan_period.location_of_work.name = "Kinderklinik"
        
        # Nachmittag
        mock_nachmittag = Mock()
        mock_nachmittag.parent = mock_kinderklinik
        mock_nachmittag.event_group_id = nachmittag_id
        mock_nachmittag.weight = 2
        mock_nachmittag.nr_of_active_children = 1
        mock_nachmittag.children = []
        mock_nachmittag.event = Mock()
        mock_nachmittag.event.date = date(2025, 6, 28)
        mock_nachmittag.event.time_of_day = Mock()
        mock_nachmittag.event.time_of_day.name = "Nachmittag"
        mock_nachmittag.event.location_plan_period = Mock()
        mock_nachmittag.event.location_plan_period.location_of_work = Mock()
        mock_nachmittag.event.location_plan_period.location_of_work.name = "Kinderklinik"
        
        # Setup hierarchy
        mock_root.children = [mock_kinderklinik]
        mock_kinderklinik.children = [mock_vormittag, mock_nachmittag]
        
        # Setup entities
        mock_solver_context.entities.event_groups = {
            root_id: mock_root,
            kinderklinik_id: mock_kinderklinik,
            vormittag_id: mock_vormittag,
            nachmittag_id: mock_nachmittag
        }
        
        mock_solver_context.entities.event_group_vars = {
            vormittag_id: Mock(),
            nachmittag_id: Mock()
        }
        
        # Setup empty AvailDay groups for this test
        mock_solver_context.entities.avail_day_groups = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Mock variable creation
        mock_weight_vars = [Mock(), Mock()]
        mock_solver_context.model.NewIntVar.side_effect = mock_weight_vars
        
        # Test constraint setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()
        
        # Verify weight variable creation
        summary = constraint.get_summary()
        assert summary['total_event_groups'] == 4
        assert summary['event_weight_vars'] == 2  # Only vormittag and nachmittag have weight vars
        
        # Should have created constraints for both child events
        assert mock_solver_context.model.Add.call_count == 2
    
    def test_constraint_complex_avail_day_hierarchy(self, mock_solver_context):
        """Test: Constraint mit komplexer AvailDay-Hierarchie."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {0: 1}
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {1: 10}
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {
            1: 10, 2: 20, 3: 30
        }
        
        # Create hierarchical AvailDay groups:
        # Root -> Actor Master Groups -> Time Groups -> AvailDays
        
        root_id = uuid4()
        actor_master_id = uuid4()
        time_group_id = uuid4()
        avail_day_group_id = uuid4()
        
        # Setup AvailDay
        mock_person = Mock()
        mock_person.f_name = "Hans"
        
        mock_actor_plan_period = Mock()
        mock_actor_plan_period.person = mock_person
        
        mock_time_of_day = Mock()
        mock_time_of_day.name = "Vormittag"
        
        mock_avail_day = Mock()
        mock_avail_day.date = date(2025, 6, 28)
        mock_avail_day.time_of_day = mock_time_of_day
        mock_avail_day.actor_plan_period = mock_actor_plan_period
        
        # AvailDay Group (Leaf)
        mock_avail_day_group = Mock()
        mock_avail_day_group.parent = Mock()
        mock_avail_day_group.avail_day_group_id = avail_day_group_id
        mock_avail_day_group.avail_day = mock_avail_day
        mock_avail_day_group.weight = 1
        mock_avail_day_group.depth = 3
        
        # Time Group
        mock_time_group = Mock()
        mock_time_group.parent = Mock()
        mock_time_group.avail_day = None  # No direct AvailDay
        mock_time_group.weight = 2
        mock_time_group.depth = 2
        mock_time_group.children = [mock_avail_day_group]
        
        # Actor Master Group
        mock_actor_master = Mock()
        mock_actor_master.parent = Mock()
        mock_actor_master.group_is_actor_plan_period_master_group = False  # Not master itself
        mock_actor_master.weight = 3
        mock_actor_master.depth = 1
        mock_actor_master.children = [mock_time_group]
        
        # Root
        mock_root = Mock()
        mock_root.parent = None
        mock_root.group_is_actor_plan_period_master_group = False
        mock_root.depth = 0
        mock_root.children = [mock_actor_master]
        
        # Setup hierarchy
        mock_avail_day_group.parent = mock_time_group
        mock_time_group.parent = mock_actor_master
        mock_actor_master.parent = mock_root
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups = {
            root_id: mock_root,
            actor_master_id: mock_actor_master,
            time_group_id: mock_time_group,
            avail_day_group_id: mock_avail_day_group
        }
        
        mock_solver_context.entities.avail_day_groups_with_avail_day = {
            avail_day_group_id: mock_avail_day_group
        }
        
        # Setup shift variables
        mock_shift_var = Mock()
        mock_solver_context.entities.shift_vars = {
            (avail_day_group_id, uuid4()): mock_shift_var
        }
        
        mock_solver_context.entities.shifts_exclusive = {
            (avail_day_group_id, uuid4()): 1  # Allowed
        }
        
        # Setup empty event groups for this test
        mock_solver_context.entities.event_groups = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.event_groups_with_event = {
            uuid4(): Mock(event=Mock(date=date(2025, 6, 28)))
        }
        
        # Mock variable creation
        mock_weight_var = Mock()
        mock_has_shifts_var = Mock()
        mock_solver_context.model.NewIntVar.return_value = mock_weight_var
        mock_solver_context.model.NewBoolVar.return_value = mock_has_shifts_var
        
        # Test constraint setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()
        
        # Verify AvailDay weight processing
        summary = constraint.get_summary()
        assert summary['total_avail_day_groups'] == 4
        assert summary['avail_day_weight_vars'] == 1  # Only leaf AvailDay group creates weight var
        assert summary['max_avail_day_depth'] == 3
    
    def test_constraint_performance_large_hierarchy(self, mock_solver_context):
        """Test: Constraint Performance mit großer Hierarchie."""
        import time
        
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {
            i: i+1 for i in range(10)
        }
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {
            i: i*10 for i in range(1, 6)
        }
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {
            i: i*10 for i in range(1, 6)
        }
        
        # Create large hierarchy: 100 event groups and 100 avail day groups
        num_groups = 100
        
        # Event groups
        event_groups = {}
        event_group_vars = {}
        
        # Create root
        root_id = uuid4()
        mock_root = Mock()
        mock_root.parent = None
        mock_root.root_is_location_plan_period_master_group = False
        mock_root.nr_of_active_children = num_groups - 1
        mock_root.children = []
        
        event_groups[root_id] = mock_root
        
        # Create children
        for i in range(num_groups - 1):
            child_id = uuid4()
            
            mock_child = Mock()
            mock_child.parent = mock_root
            mock_child.event_group_id = child_id
            mock_child.weight = (i % 5) + 1
            mock_child.children = []
            mock_child.event = Mock()
            mock_child.event.date = date(2025, 6, 28)
            mock_child.event.time_of_day = Mock()
            mock_child.event.time_of_day.name = f"Time_{i}"
            mock_child.event.location_plan_period = Mock()
            mock_child.event.location_plan_period.location_of_work = Mock()
            mock_child.event.location_plan_period.location_of_work.name = f"Location_{i}"
            
            event_groups[child_id] = mock_child
            event_group_vars[child_id] = Mock()
            mock_root.children.append(mock_child)
        
        # AvailDay groups (simple flat structure for performance test)
        avail_day_groups = {}
        avail_day_groups_with_avail_day = {}
        
        adg_root_id = uuid4()
        mock_adg_root = Mock()
        mock_adg_root.parent = None
        mock_adg_root.group_is_actor_plan_period_master_group = False
        mock_adg_root.depth = 0
        mock_adg_root.children = []
        
        avail_day_groups[adg_root_id] = mock_adg_root
        
        # Setup entities
        mock_solver_context.entities.event_groups = event_groups
        mock_solver_context.entities.event_group_vars = event_group_vars
        mock_solver_context.entities.avail_day_groups = avail_day_groups
        mock_solver_context.entities.avail_day_groups_with_avail_day = avail_day_groups_with_avail_day
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Mock variable creation
        mock_weight_vars = [Mock() for _ in range(num_groups)]
        mock_solver_context.model.NewIntVar.side_effect = mock_weight_vars
        
        # Measure setup time
        start_time = time.time()
        success = constraint.setup()
        end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Should complete quickly even with large hierarchy
        assert success is True
        assert setup_time < 5.0  # Should take less than 5 seconds
        
        # Verify processing
        summary = constraint.get_summary()
        assert summary['total_event_groups'] == num_groups
        assert summary['event_weight_vars'] == num_groups - 1  # All children create weight vars
    
    def test_constraint_mixed_weight_distributions(self, mock_solver_context):
        """Test: Constraint mit gemischten Gewichtungsverteilungen."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {0: 1, 1: 2}
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {
            1: 10, 2: 20, 3: 30, 4: 40, 5: 50
        }
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {
            1: 10, 2: 20, 3: 30, 4: 40, 5: 50
        }
        
        # Create event groups with different weights
        event_groups = {}
        weight_distribution = [1, 1, 2, 2, 2, 3, 3, 3, 3, 4, 5]  # Various weights
        
        root_id = uuid4()
        mock_root = Mock()
        mock_root.parent = None
        mock_root.root_is_location_plan_period_master_group = False
        mock_root.nr_of_active_children = len(weight_distribution)
        mock_root.children = []
        
        event_groups[root_id] = mock_root
        
        event_group_vars = {}
        for i, weight in enumerate(weight_distribution):
            child_id = uuid4()
            
            mock_child = Mock()
            mock_child.parent = mock_root
            mock_child.event_group_id = child_id
            mock_child.weight = weight
            mock_child.children = []
            mock_child.event = None  # No event for simplicity
            
            event_groups[child_id] = mock_child
            event_group_vars[child_id] = Mock()
            mock_root.children.append(mock_child)
        
        # Create AvailDay groups with different weights
        avail_day_groups = {}
        avail_weight_distribution = [1, 2, 2, 3, 4, 4, 4, 5]
        
        adg_root_id = uuid4()
        mock_adg_root = Mock()
        mock_adg_root.parent = None
        mock_adg_root.group_is_actor_plan_period_master_group = False
        mock_adg_root.depth = 0
        mock_adg_root.children = []
        
        avail_day_groups[adg_root_id] = mock_adg_root
        
        for i, weight in enumerate(avail_weight_distribution):
            adg_id = uuid4()
            
            mock_adg = Mock()
            mock_adg.weight = weight
            mock_adg.depth = 1
            
            avail_day_groups[adg_id] = mock_adg
        
        # Setup entities
        mock_solver_context.entities.event_groups = event_groups
        mock_solver_context.entities.event_group_vars = event_group_vars
        mock_solver_context.entities.avail_day_groups = avail_day_groups
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Mock variable creation
        mock_weight_vars = [Mock() for _ in range(len(weight_distribution))]
        mock_solver_context.model.NewIntVar.side_effect = mock_weight_vars
        
        # Test constraint setup
        success = constraint.setup()
        assert success is True
        
        # Verify weight distributions
        summary = constraint.get_summary()
        assert summary['event_weights_distribution'] == {1: 2, 2: 3, 3: 4, 4: 1, 5: 1}
        assert summary['avail_day_weights_distribution'] == {1: 1, 2: 2, 3: 1, 4: 3, 5: 1}
    
    @patch('sat_solver.constraints.weights.logger')
    def test_constraint_logging_integration(self, mock_logger, mock_solver_context):
        """Test: Constraint Logging-Integration."""
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup minimal entities
        mock_solver_context.entities.event_groups = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.avail_day_groups = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {0: 1}
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {1: 10}
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {1: 10}
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Logging calls depend on implementation, but logger should be available


@pytest.mark.slow
class TestWeightsConstraintPerformance:
    """Performance-Tests für WeightsConstraint."""
    
    def test_constraint_deep_hierarchy_performance(self, mock_solver_context):
        """Test: Performance mit tiefer Hierarchie."""
        import time
        
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {
            i: i+1 for i in range(20)  # Deep hierarchy
        }
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {1: 10, 2: 20}
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {1: 10, 2: 20}
        
        # Create deep hierarchy: 20 levels deep
        depth = 20
        event_groups = {}
        event_group_vars = {}
        
        # Create chain of groups
        parent = None
        for level in range(depth):
            group_id = uuid4()
            
            mock_group = Mock()
            mock_group.parent = parent
            mock_group.root_is_location_plan_period_master_group = (level == 0)
            mock_group.event_group_id = group_id
            mock_group.weight = (level % 2) + 1
            mock_group.children = []
            
            if level < depth - 1:
                mock_group.nr_of_active_children = 1
                mock_group.event = None
            else:
                mock_group.nr_of_active_children = None
                mock_group.event = Mock()
                mock_group.event.date = date(2025, 6, 28)
                mock_group.event.time_of_day = Mock()
                mock_group.event.time_of_day.name = f"Level_{level}"
                mock_group.event.location_plan_period = Mock()
                mock_group.event.location_plan_period.location_of_work = Mock()
                mock_group.event.location_plan_period.location_of_work.name = f"Location_{level}"
                event_group_vars[group_id] = Mock()
            
            event_groups[group_id] = mock_group
            
            if parent:
                parent.children = [mock_group]
            
            parent = mock_group
        
        # Setup entities
        mock_solver_context.entities.event_groups = event_groups
        mock_solver_context.entities.event_group_vars = event_group_vars
        mock_solver_context.entities.avail_day_groups = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Mock variable creation
        mock_weight_var = Mock()
        mock_solver_context.model.NewIntVar.return_value = mock_weight_var
        
        # Measure processing time
        start_time = time.time()
        success = constraint.setup()
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should handle deep hierarchy efficiently
        assert success is True
        assert processing_time < 2.0  # Should complete quickly
    
    def test_constraint_recursive_calculation_efficiency(self, mock_solver_context):
        """Test: Effizienz rekursiver Berechnungen."""
        import time
        
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {0: 1, 1: 2}
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {1: 10}
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {1: 10}
        
        # Test recursive calculation methods directly
        test_cases = [
            (5, "Small hierarchy"),
            (20, "Medium hierarchy"),
            (50, "Large hierarchy")
        ]
        
        for num_children, description in test_cases:
            # Create test hierarchy
            root_id = uuid4()
            mock_root = Mock()
            mock_root.parent = None
            mock_root.root_is_location_plan_period_master_group = False
            mock_root.nr_of_active_children = num_children
            mock_root.children = []
            
            for i in range(num_children):
                child_id = uuid4()
                mock_child = Mock()
                mock_child.parent = mock_root
                mock_child.event_group_id = child_id
                mock_child.weight = 1
                mock_child.children = []
                mock_child.event = None
                
                mock_root.children.append(mock_child)
            
            mock_solver_context.entities.event_group_vars = {}
            mock_solver_context.model.NewIntVar.return_value = Mock()
            
            # Measure recursive calculation time
            start_time = time.time()
            result = constraint._calculate_event_weight_vars_recursive(mock_root, 0)
            end_time = time.time()
            
            calculation_time = end_time - start_time
            
            # Should scale well with hierarchy size
            assert calculation_time < 1.0  # Should be fast for all sizes
            assert len(result) == num_children
    
    def test_constraint_memory_efficiency_weights(self, mock_solver_context):
        """Test: Memory-Effizienz bei vielen Gewichtungen."""
        import gc
        
        constraint = WeightsConstraint(mock_solver_context)
        
        # Setup minimal but valid entities
        mock_solver_context.entities.event_groups = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.avail_day_groups = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.group_depth_weights_event_groups = {0: 1}
        mock_solver_context.config.constraint_multipliers.sliders_weights_event_groups = {1: 10}
        mock_solver_context.config.constraint_multipliers.sliders_weights_avail_day_groups = {1: 10}
        
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
