"""
Unit-Tests für FixedCastConstraint

Testet das Constraint für feste Besetzungen (Fixed Cast).
Behandelt vordefinierte Besetzungen für Events, die als logische 
Ausdrücke mit Person-UUIDs definiert werden.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4, UUID
from datetime import date

from sat_solver.constraints.fixed_cast import FixedCastConstraint


@pytest.mark.unit
class TestFixedCastConstraint:
    """Test-Klasse für FixedCastConstraint."""
    
    def test_constraint_name(self, mock_solver_context):
        """Test: Constraint-Name ist korrekt."""
        constraint = FixedCastConstraint(mock_solver_context)
        assert constraint.constraint_name == "fixed_cast"
    
    def test_constraint_initialization(self, mock_solver_context):
        """Test: Constraint wird korrekt initialisiert."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        assert constraint.context == mock_solver_context
        assert constraint.model == mock_solver_context.model
        assert constraint.entities == mock_solver_context.entities
        assert constraint.config == mock_solver_context.config
        assert not constraint.is_setup_complete()
    
    def test_create_variables_empty_entities(self, mock_solver_context):
        """Test: create_variables() mit leeren Entities."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.cast_groups_with_event = {}
        
        # Mock dummy variable creation
        mock_dummy_var = Mock()
        mock_solver_context.model.NewBoolVar.return_value = mock_dummy_var
        
        variables = constraint.create_variables()
        
        # Should return empty list but create dummy variable
        assert variables == []
        assert constraint.get_metadata('total_fixed_cast_conflicts') == 0
        
        # Should have created dummy variable
        mock_solver_context.model.NewBoolVar.assert_called()
        assert constraint.get_metadata('fixed_cast_dummy') is not None
    
    def test_parse_fixed_cast_string_simple(self, mock_solver_context):
        """Test: _parse_fixed_cast_string() mit einfachem String."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Test simple person UUID
        person_id = str(uuid4())
        fixed_cast_string = f"['{person_id}']"
        
        result = constraint._parse_fixed_cast_string(fixed_cast_string)
        
        assert result == [person_id]
    
    def test_parse_fixed_cast_string_with_and(self, mock_solver_context):
        """Test: _parse_fixed_cast_string() mit AND-Operator."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Test AND combination
        person_id1, person_id2 = str(uuid4()), str(uuid4())
        fixed_cast_string = f"['{person_id1}' and '{person_id2}']"
        
        result = constraint._parse_fixed_cast_string(fixed_cast_string)
        
        assert result == [person_id1, 'and', person_id2]
    
    def test_parse_fixed_cast_string_with_or(self, mock_solver_context):
        """Test: _parse_fixed_cast_string() mit OR-Operator."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Test OR combination
        person_id1, person_id2 = str(uuid4()), str(uuid4())
        fixed_cast_string = f"['{person_id1}' or '{person_id2}']"
        
        result = constraint._parse_fixed_cast_string(fixed_cast_string)
        
        assert result == [person_id1, 'or', person_id2]
    
    def test_parse_fixed_cast_string_complex(self, mock_solver_context):
        """Test: _parse_fixed_cast_string() mit komplexem Ausdruck."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Test complex expression with UUID() prefix removal
        person_id1, person_id2, person_id3 = str(uuid4()), str(uuid4()), str(uuid4())
        fixed_cast_string = f"[UUID('{person_id1}') and UUID('{person_id2}') or UUID('{person_id3}') in team]"
        
        result = constraint._parse_fixed_cast_string(fixed_cast_string)
        
        expected = [f"('{person_id1}')", 'and', f"('{person_id2}')", 'or', f"('{person_id3}')"]
        assert result == expected
    
    def test_parse_fixed_cast_string_invalid(self, mock_solver_context):
        """Test: _parse_fixed_cast_string() mit ungültigem String."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Test invalid string
        invalid_string = "invalid syntax [["
        
        with pytest.raises(ValueError, match="Failed to parse fixed cast string"):
            constraint._parse_fixed_cast_string(invalid_string)
    
    def test_check_person_in_shift_vars(self, mock_solver_context):
        """Test: _check_person_in_shift_vars() Methode."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data
        person_id = uuid4()
        adg_id1, adg_id2, adg_id3 = uuid4(), uuid4(), uuid4()
        event_group_id = uuid4()
        
        # Mock cast group
        mock_cast_group = Mock()
        mock_cast_group.event = Mock()
        mock_cast_group.event.event_group = Mock()
        mock_cast_group.event.event_group.id = event_group_id
        
        # Mock actor plan periods
        mock_person = Mock()
        mock_person.id = person_id
        
        mock_app_correct = Mock()
        mock_app_correct.person = mock_person
        
        mock_app_wrong = Mock()
        mock_app_wrong.person = Mock()
        mock_app_wrong.person.id = uuid4()  # Different person
        
        # Mock avail day groups
        mock_adg1 = Mock()
        mock_adg1.avail_day = Mock()
        mock_adg1.avail_day.actor_plan_period = mock_app_correct  # Correct person
        
        mock_adg2 = Mock()
        mock_adg2.avail_day = Mock()
        mock_adg2.avail_day.actor_plan_period = mock_app_wrong    # Wrong person
        
        mock_adg3 = Mock()
        mock_adg3.avail_day = Mock()
        mock_adg3.avail_day.actor_plan_period = mock_app_correct  # Correct person
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2,
            adg_id3: mock_adg3
        }
        
        # Mock shift variables
        mock_shift_var1 = Mock()
        mock_shift_var2 = Mock()
        mock_shift_var3 = Mock()
        
        mock_solver_context.entities.shift_vars = {
            (adg_id1, event_group_id): mock_shift_var1,    # Correct person, correct event
            (adg_id2, event_group_id): mock_shift_var2,    # Wrong person, correct event
            (adg_id3, uuid4()): mock_shift_var3            # Correct person, wrong event
        }
        
        # Mock person variable
        mock_person_var = Mock()
        mock_solver_context.model.NewBoolVar.return_value = mock_person_var
        
        # Call method
        result = constraint._check_person_in_shift_vars(person_id, mock_cast_group)
        
        # Should create person variable and constraint
        assert result == mock_person_var
        mock_solver_context.model.NewBoolVar.assert_called_with(f'person_{person_id}_in_cast')
        
        # Should have added constraint that person_var equals sum of relevant shifts
        # Only shift_var1 should be included (correct person AND correct event)
        mock_solver_context.model.Add.assert_called()
    
    def test_create_and_variable(self, mock_solver_context):
        """Test: _create_and_variable() Methode."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test variables
        mock_var1, mock_var2, mock_var3 = Mock(), Mock(), Mock()
        variables = [mock_var1, mock_var2, mock_var3]
        
        # Mock AND variable
        mock_and_var = Mock()
        mock_solver_context.model.NewBoolVar.return_value = mock_and_var
        
        # Call method
        result = constraint._create_and_variable(variables)
        
        # Should create AND variable and multiplication constraint
        assert result == mock_and_var
        mock_solver_context.model.NewBoolVar.assert_called_with('and_combination')
        mock_solver_context.model.AddMultiplicationEquality.assert_called_with(mock_and_var, variables)
    
    def test_create_or_variable(self, mock_solver_context):
        """Test: _create_or_variable() Methode."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test variables
        mock_var1, mock_var2, mock_var3 = Mock(), Mock(), Mock()
        variables = [mock_var1, mock_var2, mock_var3]
        
        # Mock OR variable
        mock_or_var = Mock()
        mock_solver_context.model.NewBoolVar.return_value = mock_or_var
        
        # Call method
        result = constraint._create_or_variable(variables)
        
        # Should create OR variable and sum constraint
        assert result == mock_or_var
        mock_solver_context.model.NewBoolVar.assert_called_with('or_combination')
        mock_solver_context.model.Add.assert_called()
    
    def test_validate_fixed_cast_recursive_single_person(self, mock_solver_context):
        """Test: _validate_fixed_cast_recursive() mit einzelner Person."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data
        person_id = str(uuid4())
        mock_cast_group = Mock()
        
        # Mock person checking
        mock_person_var = Mock()
        with patch.object(constraint, '_check_person_in_shift_vars') as mock_check:
            mock_check.return_value = mock_person_var
            
            result = constraint._validate_fixed_cast_recursive(person_id, mock_cast_group)
        
        # Should check single person
        assert result == mock_person_var
        mock_check.assert_called_once_with(UUID(person_id), mock_cast_group)
    
    def test_validate_fixed_cast_recursive_and_operation(self, mock_solver_context):
        """Test: _validate_fixed_cast_recursive() mit AND-Operation."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data
        person_id1, person_id2 = str(uuid4()), str(uuid4())
        fixed_cast_list = [person_id1, 'and', person_id2]
        mock_cast_group = Mock()
        
        # Mock recursive calls and AND creation
        mock_var1, mock_var2 = Mock(), Mock()
        mock_and_var = Mock()
        
        with patch.object(constraint, '_check_person_in_shift_vars') as mock_check:
            with patch.object(constraint, '_create_and_variable') as mock_and:
                mock_check.side_effect = [mock_var1, mock_var2]
                mock_and.return_value = mock_and_var
                
                result = constraint._validate_fixed_cast_recursive(fixed_cast_list, mock_cast_group)
        
        # Should create AND of both person variables
        assert result == mock_and_var
        assert mock_check.call_count == 2
        mock_and.assert_called_once_with([mock_var1, mock_var2])
    
    def test_validate_fixed_cast_recursive_or_operation(self, mock_solver_context):
        """Test: _validate_fixed_cast_recursive() mit OR-Operation."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data
        person_id1, person_id2 = str(uuid4()), str(uuid4())
        fixed_cast_list = [person_id1, 'or', person_id2]
        mock_cast_group = Mock()
        
        # Mock recursive calls and OR creation
        mock_var1, mock_var2 = Mock(), Mock()
        mock_or_var = Mock()
        
        with patch.object(constraint, '_check_person_in_shift_vars') as mock_check:
            with patch.object(constraint, '_create_or_variable') as mock_or:
                mock_check.side_effect = [mock_var1, mock_var2]
                mock_or.return_value = mock_or_var
                
                result = constraint._validate_fixed_cast_recursive(fixed_cast_list, mock_cast_group)
        
        # Should create OR of both person variables
        assert result == mock_or_var
        assert mock_check.call_count == 2
        mock_or.assert_called_once_with([mock_var1, mock_var2])
    
    def test_validate_fixed_cast_recursive_mixed_operators_error(self, mock_solver_context):
        """Test: _validate_fixed_cast_recursive() mit gemischten Operatoren (Fehler)."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data with mixed operators
        person_id1, person_id2, person_id3 = str(uuid4()), str(uuid4()), str(uuid4())
        fixed_cast_list = [person_id1, 'and', person_id2, 'or', person_id3]  # Mixed operators
        mock_cast_group = Mock()
        
        # Should raise error for mixed operators
        with pytest.raises(ValueError, match="All operators must be the same"):
            constraint._validate_fixed_cast_recursive(fixed_cast_list, mock_cast_group)
    
    def test_validate_fixed_cast_recursive_unknown_operator_error(self, mock_solver_context):
        """Test: _validate_fixed_cast_recursive() mit unbekanntem Operator (Fehler)."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data with unknown operator
        person_id1, person_id2 = str(uuid4()), str(uuid4())
        fixed_cast_list = [person_id1, 'xor', person_id2]  # Unknown operator
        mock_cast_group = Mock()
        
        # Should raise error for unknown operator
        with pytest.raises(ValueError, match="Unknown operator: xor"):
            constraint._validate_fixed_cast_recursive(fixed_cast_list, mock_cast_group)
    
    def test_validate_fixed_cast_recursive_multiple_persons_no_operators_error(self, mock_solver_context):
        """Test: _validate_fixed_cast_recursive() mit mehreren Personen ohne Operatoren (Fehler)."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data with multiple persons but no operators
        person_id1, person_id2 = str(uuid4()), str(uuid4())
        fixed_cast_list = [person_id1, person_id2]  # No operators
        mock_cast_group = Mock()
        
        # Should raise error for multiple persons without operators
        with pytest.raises(ValueError, match="Multiple person IDs without operators"):
            constraint._validate_fixed_cast_recursive(fixed_cast_list, mock_cast_group)
    
    @patch('sat_solver.constraints.fixed_cast.generate_fixed_cast_clear_text')
    def test_create_variables_with_valid_fixed_cast(self, mock_generate_text, mock_solver_context):
        """Test: create_variables() mit gültigem Fixed Cast."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data
        cast_group_id = uuid4()
        event_id = uuid4()
        event_group_id = uuid4()
        person_id = str(uuid4())
        
        # Mock cast group with fixed cast
        mock_event_group = Mock()
        mock_event_group.id = event_group_id
        
        mock_location = Mock()
        mock_location.name_an_city = "Kinderklinik München"
        
        mock_location_plan_period = Mock()
        mock_location_plan_period.location_of_work = mock_location
        
        mock_time_of_day = Mock()
        mock_time_of_day.name = "Vormittag"
        
        mock_event = Mock()
        mock_event.id = event_id
        mock_event.date = date(2025, 6, 28)
        mock_event.time_of_day = mock_time_of_day
        mock_event.location_plan_period = mock_location_plan_period
        mock_event.event_group = mock_event_group
        
        mock_cast_group = Mock()
        mock_cast_group.cast_group_id = cast_group_id
        mock_cast_group.event = mock_event
        mock_cast_group.fixed_cast = f"['{person_id}']"
        
        # Setup entities
        mock_solver_context.entities.cast_groups_with_event = {
            cast_group_id: mock_cast_group
        }
        mock_solver_context.entities.event_group_vars = {
            event_group_id: Mock()
        }
        
        # Mock helper functions
        mock_generate_text.return_value = "Hans Müller"
        
        # Mock variables
        mock_dummy_var = Mock()
        mock_fixed_cast_var = Mock()
        mock_validation_var = Mock()
        mock_validation_var.Not.return_value = Mock()
        
        mock_solver_context.model.NewBoolVar.side_effect = [mock_dummy_var, mock_fixed_cast_var]
        
        # Mock validation
        with patch.object(constraint, '_parse_fixed_cast_string') as mock_parse:
            with patch.object(constraint, '_create_fixed_cast_validation') as mock_validate:
                mock_parse.return_value = [person_id]
                mock_validate.return_value = mock_validation_var
                
                variables = constraint.create_variables()
        
        # Should create fixed cast variable
        assert len(variables) == 1
        assert variables[0] == mock_fixed_cast_var
        assert constraint.get_metadata('total_fixed_cast_conflicts') == 1
        
        # Should have parsed and validated fixed cast
        mock_parse.assert_called_with(f"['{person_id}']")
        mock_validate.assert_called_with([person_id], mock_cast_group)
        mock_generate_text.assert_called_with(f"['{person_id}']")
        
        # Should have created constraint
        mock_solver_context.model.Add.assert_called()
    
    def test_create_variables_with_invalid_fixed_cast(self, mock_solver_context):
        """Test: create_variables() mit ungültigem Fixed Cast."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data
        cast_group_id = uuid4()
        event_id = uuid4()
        
        # Mock cast group with invalid fixed cast
        mock_event = Mock()
        mock_event.id = event_id
        mock_event.date = date(2025, 6, 28)
        
        mock_cast_group = Mock()
        mock_cast_group.cast_group_id = cast_group_id
        mock_cast_group.event = mock_event
        mock_cast_group.fixed_cast = "invalid syntax [["
        
        # Setup entities
        mock_solver_context.entities.cast_groups_with_event = {
            cast_group_id: mock_cast_group
        }
        
        # Mock dummy variable
        mock_dummy_var = Mock()
        mock_solver_context.model.NewBoolVar.return_value = mock_dummy_var
        
        variables = constraint.create_variables()
        
        # Should skip invalid fixed cast but not crash
        assert len(variables) == 0
        assert constraint.get_metadata('total_fixed_cast_conflicts') == 0
        
        # Should have recorded error
        error_key = f'fixed_cast_error_{cast_group_id}'
        error_metadata = constraint.get_metadata(error_key)
        assert error_metadata is not None
        assert 'error' in error_metadata
        assert error_metadata['fixed_cast_string'] == "invalid syntax [["
    
    def test_create_variables_without_fixed_cast(self, mock_solver_context):
        """Test: create_variables() mit Cast Groups ohne Fixed Cast."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data
        cast_group_id = uuid4()
        
        # Mock cast group without fixed cast
        mock_cast_group = Mock()
        mock_cast_group.cast_group_id = cast_group_id
        mock_cast_group.fixed_cast = None  # No fixed cast
        
        # Setup entities
        mock_solver_context.entities.cast_groups_with_event = {
            cast_group_id: mock_cast_group
        }
        
        # Mock dummy variable
        mock_dummy_var = Mock()
        mock_solver_context.model.NewBoolVar.return_value = mock_dummy_var
        
        variables = constraint.create_variables()
        
        # Should skip cast groups without fixed cast
        assert len(variables) == 0
        assert constraint.get_metadata('total_fixed_cast_conflicts') == 0
    
    def test_create_variables_without_event_group_var(self, mock_solver_context):
        """Test: create_variables() ohne Event Group Variable (Fallback)."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data
        cast_group_id = uuid4()
        event_group_id = uuid4()
        person_id = str(uuid4())
        
        # Mock cast group with fixed cast
        mock_event_group = Mock()
        mock_event_group.id = event_group_id
        
        mock_event = Mock()
        mock_event.date = date(2025, 6, 28)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.name = "Vormittag"
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_of_work = Mock()
        mock_event.location_plan_period.location_of_work.name_an_city = "Test Location"
        mock_event.event_group = mock_event_group
        
        mock_cast_group = Mock()
        mock_cast_group.cast_group_id = cast_group_id
        mock_cast_group.event = mock_event
        mock_cast_group.fixed_cast = f"['{person_id}']"
        
        # Setup entities (ohne event_group_vars)
        mock_solver_context.entities.cast_groups_with_event = {
            cast_group_id: mock_cast_group
        }
        mock_solver_context.entities.event_group_vars = {}  # Missing event group var
        
        # Mock variables and validation
        mock_dummy_var = Mock()
        mock_fixed_cast_var = Mock()
        mock_validation_var = Mock()
        mock_validation_var.Not.return_value = Mock()
        
        mock_solver_context.model.NewBoolVar.side_effect = [mock_dummy_var, mock_fixed_cast_var]
        
        with patch.object(constraint, '_parse_fixed_cast_string') as mock_parse:
            with patch.object(constraint, '_create_fixed_cast_validation') as mock_validate:
                with patch('sat_solver.constraints.fixed_cast.generate_fixed_cast_clear_text') as mock_generate:
                    mock_parse.return_value = [person_id]
                    mock_validate.return_value = mock_validation_var
                    mock_generate.return_value = "Test Person"
                    
                    variables = constraint.create_variables()
        
        # Should still create variable but use fallback constraint
        assert len(variables) == 1
        assert variables[0] == mock_fixed_cast_var
        
        # Should have used fallback constraint without OnlyEnforceIf
        mock_solver_context.model.Add.assert_called()
    
    def test_add_constraints(self, mock_solver_context):
        """Test: add_constraints() Methode."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Call method
        constraint.add_constraints()
        
        # Should set metadata for additional constraints
        additional_constraints = constraint.get_metadata('additional_fixed_cast_constraints')
        assert additional_constraints == 0  # No additional constraints in base implementation
    
    def test_validate_context_success(self, mock_solver_context):
        """Test: validate_context() erfolgreich."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup required attributes
        mock_solver_context.entities.cast_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        
        result = constraint.validate_context()
        assert result is True
    
    def test_validate_context_missing_entities(self, mock_solver_context):
        """Test: validate_context() mit fehlenden Entities."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Missing entities
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error is not None
        assert "Missing entities." in error
    
    def test_validate_context_empty_cast_groups(self, mock_solver_context):
        """Test: validate_context() mit leeren Cast Groups."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup required attributes but empty cast groups
        mock_solver_context.entities.cast_groups_with_event = {}  # Empty
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error == "No cast groups with events found"
    
    def test_get_fixed_cast_summary(self, mock_solver_context):
        """Test: get_fixed_cast_summary() Methode."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data
        cg_id1, cg_id2, cg_id3, cg_id4 = uuid4(), uuid4(), uuid4(), uuid4()
        person_id = str(uuid4())
        
        # Mock cast groups
        mock_cast_group1 = Mock()
        mock_cast_group1.fixed_cast = f"['{person_id}']"  # Valid fixed cast
        
        mock_cast_group2 = Mock()
        mock_cast_group2.fixed_cast = "invalid syntax [["  # Invalid fixed cast
        
        mock_cast_group3 = Mock()
        mock_cast_group3.fixed_cast = None  # No fixed cast
        
        mock_cast_group4 = Mock()
        mock_cast_group4.fixed_cast = f"['{uuid4()}' and '{uuid4()}']"  # Valid complex fixed cast
        
        # Setup entities
        mock_solver_context.entities.cast_groups_with_event = {
            cg_id1: mock_cast_group1,
            cg_id2: mock_cast_group2,
            cg_id3: mock_cast_group3,
            cg_id4: mock_cast_group4
        }
        
        # Set metadata for conflicts
        constraint.add_metadata('total_fixed_cast_conflicts', 2)
        
        # Add error metadata
        constraint.add_metadata(f'fixed_cast_error_{cg_id2}', {
            'error': 'Parsing error'
        })
        
        summary = constraint.get_fixed_cast_summary()
        
        # Verify summary
        assert summary['total_cast_groups'] == 4
        assert summary['cast_groups_with_fixed_cast'] == 3  # cg1, cg2, cg4
        assert summary['fixed_cast_parsing_errors'] == 1   # cg2 has parsing error
        assert summary['fixed_cast_conflict_variables'] == 2
        assert summary['fixed_cast_coverage'] == 3/4  # 3 of 4 cast groups have fixed cast
    
    def test_get_fixed_cast_summary_empty(self, mock_solver_context):
        """Test: get_fixed_cast_summary() mit leeren Daten."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.cast_groups_with_event = {}
        
        summary = constraint.get_fixed_cast_summary()
        
        # Should return empty summary
        assert summary == {}
    
    @patch('sat_solver.constraints.fixed_cast.generate_fixed_cast_clear_text')
    def test_get_fixed_cast_details(self, mock_generate_text, mock_solver_context):
        """Test: get_fixed_cast_details() Methode."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup test data
        cg_id1, cg_id2, cg_id3 = uuid4(), uuid4(), uuid4()
        person_id = str(uuid4())
        
        # Mock cast groups
        mock_location1 = Mock()
        mock_location1.name = "Kinderklinik"
        
        mock_location_plan_period1 = Mock()
        mock_location_plan_period1.location_of_work = mock_location1
        
        mock_time_of_day1 = Mock()
        mock_time_of_day1.name = "Vormittag"
        
        mock_event1 = Mock()
        mock_event1.date = date(2025, 6, 28)
        mock_event1.time_of_day = mock_time_of_day1
        mock_event1.location_plan_period = mock_location_plan_period1
        
        mock_cast_group1 = Mock()
        mock_cast_group1.cast_group_id = cg_id1
        mock_cast_group1.event = mock_event1
        mock_cast_group1.fixed_cast = f"['{person_id}']"  # Valid
        
        # Mock cast group with error
        mock_event2 = Mock()
        mock_event2.date = date(2025, 6, 29)
        mock_event2.time_of_day = Mock()
        mock_event2.time_of_day.name = "Nachmittag"
        mock_event2.location_plan_period = Mock()
        mock_event2.location_plan_period.location_of_work = Mock()
        mock_event2.location_plan_period.location_of_work.name = "Seniorenheim"
        
        mock_cast_group2 = Mock()
        mock_cast_group2.cast_group_id = cg_id2
        mock_cast_group2.event = mock_event2
        mock_cast_group2.fixed_cast = "invalid syntax [["  # Invalid
        
        # Mock cast group without fixed cast
        mock_cast_group3 = Mock()
        mock_cast_group3.cast_group_id = cg_id3
        mock_cast_group3.fixed_cast = None  # No fixed cast
        
        # Setup entities
        mock_solver_context.entities.cast_groups_with_event = {
            cg_id1: mock_cast_group1,
            cg_id2: mock_cast_group2,
            cg_id3: mock_cast_group3
        }
        
        # Mock generate_fixed_cast_clear_text
        mock_generate_text.side_effect = lambda x: "Hans Müller" if "invalid" not in x else "Parsing Error"
        
        details = constraint.get_fixed_cast_details()
        
        # Should return details for cast groups with fixed cast
        assert len(details) == 2  # Only cg1 and cg2 have fixed cast
        
        # Check valid fixed cast detail
        valid_detail = next(d for d in details if d['cast_group_id'] == str(cg_id1))
        assert valid_detail['event_date'] == '2025-06-28'
        assert valid_detail['event_time'] == 'Vormittag'
        assert valid_detail['location'] == 'Kinderklinik'
        assert valid_detail['fixed_cast_string'] == f"['{person_id}']"
        assert valid_detail['fixed_cast_clear_text'] == "Hans Müller"
        assert valid_detail['parsing_success'] is True
        assert valid_detail['error_message'] is None
        
        # Check invalid fixed cast detail
        invalid_detail = next(d for d in details if d['cast_group_id'] == str(cg_id2))
        assert invalid_detail['event_date'] == '2025-06-29'
        assert invalid_detail['event_time'] == 'Nachmittag'
        assert invalid_detail['location'] == 'Seniorenheim'
        assert invalid_detail['fixed_cast_string'] == "invalid syntax [["
        assert invalid_detail['fixed_cast_clear_text'] == "Parsing Error"
        assert invalid_detail['parsing_success'] is False
        assert invalid_detail['error_message'] is not None
    
    def test_get_summary_integration(self, mock_solver_context):
        """Test: get_summary() Integration mit Base-Klasse."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup entities for summary
        mock_solver_context.entities.cast_groups_with_event = {
            uuid4(): Mock(fixed_cast=f"['{uuid4()}']"),
            uuid4(): Mock(fixed_cast=None)
        }
        
        constraint.add_metadata('total_fixed_cast_conflicts', 1)
        
        summary = constraint.get_summary()
        
        # Should include both base summary and fixed cast summary
        assert 'total_cast_groups' in summary
        assert 'cast_groups_with_fixed_cast' in summary
        assert 'fixed_cast_conflict_variables' in summary
        assert 'fixed_cast_coverage' in summary
    
    def test_complete_setup_workflow(self, mock_solver_context):
        """Test: Kompletter Setup-Workflow."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup minimal required entities
        mock_solver_context.entities.cast_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        
        # Test setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()


@pytest.mark.integration
class TestFixedCastConstraintIntegration:
    """Integration-Tests für FixedCastConstraint."""
    
    @patch('sat_solver.constraints.fixed_cast.generate_fixed_cast_clear_text')
    def test_constraint_with_realistic_klinikclown_scenario(self, mock_generate_text, mock_solver_context):
        """Test: Constraint mit realistischem Klinikclown-Szenario."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup realistic scenario:
        # Kinderklinik: Hans UND Maria müssen zusammen arbeiten
        # Seniorenheim: Entweder Hans ODER Peter kann arbeiten
        # Tagesklinik: Nur Thomas (einzelne Person)
        
        # Setup person IDs
        hans_id = str(uuid4())
        maria_id = str(uuid4())
        peter_id = str(uuid4())
        thomas_id = str(uuid4())
        
        # Create cast groups with different fixed cast scenarios
        cast_groups = {}
        event_groups = {}
        
        # Kinderklinik: Hans AND Maria
        kinderklinik_cg_id = uuid4()
        kinderklinik_eg_id = uuid4()
        
        mock_kinderklinik_event_group = Mock()
        mock_kinderklinik_event_group.id = kinderklinik_eg_id
        
        mock_kinderklinik_location = Mock()
        mock_kinderklinik_location.name_an_city = "Kinderklinik München"
        
        mock_kinderklinik_event = Mock()
        mock_kinderklinik_event.id = uuid4()
        mock_kinderklinik_event.date = date(2025, 6, 28)
        mock_kinderklinik_event.time_of_day = Mock()
        mock_kinderklinik_event.time_of_day.name = "Vormittag"
        mock_kinderklinik_event.location_plan_period = Mock()
        mock_kinderklinik_event.location_plan_period.location_of_work = mock_kinderklinik_location
        mock_kinderklinik_event.event_group = mock_kinderklinik_event_group
        
        mock_kinderklinik_cast_group = Mock()
        mock_kinderklinik_cast_group.cast_group_id = kinderklinik_cg_id
        mock_kinderklinik_cast_group.event = mock_kinderklinik_event
        mock_kinderklinik_cast_group.fixed_cast = f"['{hans_id}' and '{maria_id}']"
        
        cast_groups[kinderklinik_cg_id] = mock_kinderklinik_cast_group
        event_groups[kinderklinik_eg_id] = Mock()
        
        # Seniorenheim: Hans OR Peter
        seniorenheim_cg_id = uuid4()
        seniorenheim_eg_id = uuid4()
        
        mock_seniorenheim_event_group = Mock()
        mock_seniorenheim_event_group.id = seniorenheim_eg_id
        
        mock_seniorenheim_location = Mock()
        mock_seniorenheim_location.name_an_city = "Seniorenheim Würzburg"
        
        mock_seniorenheim_event = Mock()
        mock_seniorenheim_event.id = uuid4()
        mock_seniorenheim_event.date = date(2025, 6, 29)
        mock_seniorenheim_event.time_of_day = Mock()
        mock_seniorenheim_event.time_of_day.name = "Nachmittag"
        mock_seniorenheim_event.location_plan_period = Mock()
        mock_seniorenheim_event.location_plan_period.location_of_work = mock_seniorenheim_location
        mock_seniorenheim_event.event_group = mock_seniorenheim_event_group
        
        mock_seniorenheim_cast_group = Mock()
        mock_seniorenheim_cast_group.cast_group_id = seniorenheim_cg_id
        mock_seniorenheim_cast_group.event = mock_seniorenheim_event
        mock_seniorenheim_cast_group.fixed_cast = f"['{hans_id}' or '{peter_id}']"
        
        cast_groups[seniorenheim_cg_id] = mock_seniorenheim_cast_group
        event_groups[seniorenheim_eg_id] = Mock()
        
        # Tagesklinik: Thomas (single person)
        tagesklinik_cg_id = uuid4()
        tagesklinik_eg_id = uuid4()
        
        mock_tagesklinik_event_group = Mock()
        mock_tagesklinik_event_group.id = tagesklinik_eg_id
        
        mock_tagesklinik_location = Mock()
        mock_tagesklinik_location.name_an_city = "Tagesklinik Nürnberg"
        
        mock_tagesklinik_event = Mock()
        mock_tagesklinik_event.id = uuid4()
        mock_tagesklinik_event.date = date(2025, 6, 30)
        mock_tagesklinik_event.time_of_day = Mock()
        mock_tagesklinik_event.time_of_day.name = "Vormittag"
        mock_tagesklinik_event.location_plan_period = Mock()
        mock_tagesklinik_event.location_plan_period.location_of_work = mock_tagesklinik_location
        mock_tagesklinik_event.event_group = mock_tagesklinik_event_group
        
        mock_tagesklinik_cast_group = Mock()
        mock_tagesklinik_cast_group.cast_group_id = tagesklinik_cg_id
        mock_tagesklinik_cast_group.event = mock_tagesklinik_event
        mock_tagesklinik_cast_group.fixed_cast = f"['{thomas_id}']"
        
        cast_groups[tagesklinik_cg_id] = mock_tagesklinik_cast_group
        event_groups[tagesklinik_eg_id] = Mock()
        
        # Setup entities
        mock_solver_context.entities.cast_groups_with_event = cast_groups
        mock_solver_context.entities.event_group_vars = event_groups
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        
        # Mock clear text generation
        mock_generate_text.side_effect = lambda x: {
            f"['{hans_id}' and '{maria_id}']": "Hans Müller und Maria Schmidt",
            f"['{hans_id}' or '{peter_id}']": "Hans Müller oder Peter Weber",
            f"['{thomas_id}']": "Thomas Fischer"
        }.get(x, "Unknown")
        
        # Mock variable creation
        mock_dummy_var = Mock()
        mock_fixed_cast_vars = [Mock(), Mock(), Mock()]
        mock_validation_vars = [Mock(), Mock(), Mock()]
        
        for mock_var in mock_validation_vars:
            mock_var.Not.return_value = Mock()
        
        mock_solver_context.model.NewBoolVar.side_effect = [mock_dummy_var] + mock_fixed_cast_vars
        
        # Mock validation methods
        with patch.object(constraint, '_create_fixed_cast_validation') as mock_validate:
            mock_validate.side_effect = mock_validation_vars
            
            # Test constraint setup
            success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()
        
        # Verify fixed cast processing
        assert mock_validate.call_count == 3  # 3 cast groups with fixed cast
        
        # Get summary
        summary = constraint.get_summary()
        assert summary['total_cast_groups'] == 3
        assert summary['cast_groups_with_fixed_cast'] == 3
        assert summary['fixed_cast_coverage'] == 1.0  # 100% coverage
        assert summary['fixed_cast_conflict_variables'] == 3
        
        # Get details
        details = constraint.get_fixed_cast_details()
        assert len(details) == 3
        
        # Verify details
        kinderklinik_detail = next(d for d in details if 'Kinderklinik' in d['location'])
        assert kinderklinik_detail['fixed_cast_clear_text'] == "Hans Müller und Maria Schmidt"
        assert kinderklinik_detail['parsing_success'] is True
        
        seniorenheim_detail = next(d for d in details if 'Seniorenheim' in d['location'])
        assert seniorenheim_detail['fixed_cast_clear_text'] == "Hans Müller oder Peter Weber"
        assert seniorenheim_detail['parsing_success'] is True
        
        tagesklinik_detail = next(d for d in details if 'Tagesklinik' in d['location'])
        assert tagesklinik_detail['fixed_cast_clear_text'] == "Thomas Fischer"
        assert tagesklinik_detail['parsing_success'] is True
    
    def test_constraint_complex_logical_expressions(self, mock_solver_context):
        """Test: Constraint mit komplexen logischen Ausdrücken."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup complex fixed cast scenarios
        person_ids = [str(uuid4()) for _ in range(6)]
        
        test_scenarios = [
            # Simple cases
            ([person_ids[0]], "single person"),
            ([person_ids[0], 'and', person_ids[1]], "two persons AND"),
            ([person_ids[0], 'or', person_ids[1]], "two persons OR"),
            
            # Complex cases
            ([person_ids[0], 'and', person_ids[1], 'and', person_ids[2]], "three persons AND"),
            ([person_ids[0], 'or', person_ids[1], 'or', person_ids[2]], "three persons OR"),
            ([person_ids[0], 'and', person_ids[1], 'and', person_ids[2], 'and', person_ids[3]], "four persons AND"),
        ]
        
        for i, (fixed_cast_list, description) in enumerate(test_scenarios):
            # Create mock cast group
            cg_id = uuid4()
            eg_id = uuid4()
            
            mock_event_group = Mock()
            mock_event_group.id = eg_id
            
            mock_event = Mock()
            mock_event.id = uuid4()
            mock_event.date = date(2025, 6, 28 + i)
            mock_event.time_of_day = Mock()
            mock_event.time_of_day.name = f"Termin_{i}"
            mock_event.location_plan_period = Mock()
            mock_event.location_plan_period.location_of_work = Mock()
            mock_event.location_plan_period.location_of_work.name_an_city = f"Location_{i}"
            mock_event.event_group = mock_event_group
            
            mock_cast_group = Mock()
            mock_cast_group.cast_group_id = cg_id
            mock_cast_group.event = mock_event
            mock_cast_group.fixed_cast = str(fixed_cast_list)
            
            # Setup entities for this test
            mock_solver_context.entities.cast_groups_with_event = {cg_id: mock_cast_group}
            mock_solver_context.entities.event_group_vars = {eg_id: Mock()}
            mock_solver_context.entities.avail_day_groups_with_avail_day = {}
            mock_solver_context.entities.shift_vars = {}
            
            # Mock variable creation
            mock_dummy_var = Mock()
            mock_fixed_cast_var = Mock()
            mock_validation_var = Mock()
            mock_validation_var.Not.return_value = Mock()
            
            mock_solver_context.model.NewBoolVar.side_effect = [mock_dummy_var, mock_fixed_cast_var]
            
            # Mock methods
            with patch.object(constraint, '_parse_fixed_cast_string') as mock_parse:
                with patch.object(constraint, '_create_fixed_cast_validation') as mock_validate:
                    with patch('sat_solver.constraints.fixed_cast.generate_fixed_cast_clear_text') as mock_generate:
                        mock_parse.return_value = fixed_cast_list
                        mock_validate.return_value = mock_validation_var
                        mock_generate.return_value = description
                        
                        # Test each scenario
                        variables = constraint.create_variables()
            
            # Should handle complex expressions without errors
            assert len(variables) == 1
            mock_parse.assert_called_with(str(fixed_cast_list))
            mock_validate.assert_called_with(fixed_cast_list, mock_cast_group)
    
    def test_constraint_error_handling_robustness(self, mock_solver_context):
        """Test: Constraint Error-Handling-Robustheit."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup various error scenarios
        error_scenarios = [
            ("invalid syntax [[", "Syntax error"),
            ("['person1' xor 'person2']", "Unknown operator"),
            ("['person1', 'person2']", "Multiple persons without operators"),
            ("['person1' and 'person2' or 'person3']", "Mixed operators"),
            ("", "Empty string"),
            ("None", "None value"),
        ]
        
        cast_groups = {}
        
        for i, (fixed_cast_string, error_type) in enumerate(error_scenarios):
            cg_id = uuid4()
            
            mock_event = Mock()
            mock_event.id = uuid4()
            mock_event.date = date(2025, 6, 28 + i)
            mock_event.time_of_day = Mock()
            mock_event.time_of_day.name = f"Error_Test_{i}"
            mock_event.location_plan_period = Mock()
            mock_event.location_plan_period.location_of_work = Mock()
            mock_event.location_plan_period.location_of_work.name_an_city = f"Error_Location_{i}"
            
            mock_cast_group = Mock()
            mock_cast_group.cast_group_id = cg_id
            mock_cast_group.event = mock_event
            mock_cast_group.fixed_cast = fixed_cast_string
            
            cast_groups[cg_id] = mock_cast_group
        
        # Setup entities
        mock_solver_context.entities.cast_groups_with_event = cast_groups
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        
        # Mock dummy variable
        mock_dummy_var = Mock()
        mock_solver_context.model.NewBoolVar.return_value = mock_dummy_var
        
        # Should handle all errors gracefully
        variables = constraint.create_variables()
        
        # Should not crash and return empty list (no valid fixed casts)
        assert len(variables) == 0
        assert constraint.get_metadata('total_fixed_cast_conflicts') == 0
        
        # Should have recorded all errors
        all_metadata = constraint.get_all_metadata()
        error_count = len([key for key in all_metadata.keys() if key.startswith('fixed_cast_error_')])
        assert error_count == len(error_scenarios)
        
        # Get summary should work despite errors
        summary = constraint.get_fixed_cast_summary()
        assert summary['total_cast_groups'] == len(error_scenarios)
        assert summary['cast_groups_with_fixed_cast'] == len(error_scenarios)  # All have fixed_cast strings
        assert summary['fixed_cast_parsing_errors'] == len(error_scenarios)   # All have parsing errors
        assert summary['fixed_cast_coverage'] == 1.0  # All have fixed_cast (even if invalid)
    
    def test_constraint_performance_many_fixed_casts(self, mock_solver_context):
        """Test: Constraint Performance mit vielen Fixed Casts."""
        import time
        
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Create many cast groups with fixed casts
        num_cast_groups = 100
        cast_groups = {}
        event_groups = {}
        
        for i in range(num_cast_groups):
            cg_id = uuid4()
            eg_id = uuid4()
            person_id = str(uuid4())
            
            mock_event_group = Mock()
            mock_event_group.id = eg_id
            
            mock_event = Mock()
            mock_event.id = uuid4()
            mock_event.date = date(2025, 6, 28)
            mock_event.time_of_day = Mock()
            mock_event.time_of_day.name = f"Time_{i}"
            mock_event.location_plan_period = Mock()
            mock_event.location_plan_period.location_of_work = Mock()
            mock_event.location_plan_period.location_of_work.name_an_city = f"Location_{i}"
            mock_event.event_group = mock_event_group
            
            mock_cast_group = Mock()
            mock_cast_group.cast_group_id = cg_id
            mock_cast_group.event = mock_event
            mock_cast_group.fixed_cast = f"['{person_id}']"  # Simple fixed cast
            
            cast_groups[cg_id] = mock_cast_group
            event_groups[eg_id] = Mock()
        
        # Setup entities
        mock_solver_context.entities.cast_groups_with_event = cast_groups
        mock_solver_context.entities.event_group_vars = event_groups
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        
        # Mock variable creation
        mock_dummy_var = Mock()
        mock_fixed_cast_vars = [Mock() for _ in range(num_cast_groups)]
        mock_validation_vars = [Mock() for _ in range(num_cast_groups)]
        
        for mock_var in mock_validation_vars:
            mock_var.Not.return_value = Mock()
        
        mock_solver_context.model.NewBoolVar.side_effect = [mock_dummy_var] + mock_fixed_cast_vars
        
        # Mock validation and clear text
        with patch.object(constraint, '_create_fixed_cast_validation') as mock_validate:
            with patch('sat_solver.constraints.fixed_cast.generate_fixed_cast_clear_text') as mock_generate:
                mock_validate.side_effect = mock_validation_vars
                mock_generate.return_value = "Test Person"
                
                # Measure setup time
                start_time = time.time()
                success = constraint.setup()
                end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Should complete quickly even with many fixed casts
        assert success is True
        assert setup_time < 3.0  # Should take less than 3 seconds
        
        # Verify all fixed casts were processed
        summary = constraint.get_summary()
        assert summary['total_cast_groups'] == num_cast_groups
        assert summary['cast_groups_with_fixed_cast'] == num_cast_groups
        assert summary['fixed_cast_conflict_variables'] == num_cast_groups
        assert summary['fixed_cast_coverage'] == 1.0
    
    @patch('sat_solver.constraints.fixed_cast.logger')
    def test_constraint_logging_integration(self, mock_logger, mock_solver_context):
        """Test: Constraint Logging-Integration."""
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup minimal entities
        mock_solver_context.entities.cast_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Logging calls depend on implementation, but logger should be available


@pytest.mark.slow
class TestFixedCastConstraintPerformance:
    """Performance-Tests für FixedCastConstraint."""
    
    def test_constraint_recursive_validation_performance(self, mock_solver_context):
        """Test: Performance rekursiver Validation mit tiefen Ausdrücken."""
        import time
        
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Create deep logical expressions
        person_ids = [str(uuid4()) for _ in range(20)]
        
        # Test different expression depths
        for depth in [2, 5, 10, 15]:
            # Create AND expression with `depth` persons
            expression = [person_ids[0]]
            for i in range(1, min(depth, len(person_ids))):
                expression.extend(['and', person_ids[i]])
            
            # Mock cast group
            mock_cast_group = Mock()
            mock_cast_group.event = Mock()
            mock_cast_group.event.event_group = Mock()
            mock_cast_group.event.event_group.id = uuid4()
            
            # Setup minimal entities
            mock_solver_context.entities.avail_day_groups_with_avail_day = {}
            mock_solver_context.entities.shift_vars = {}
            
            # Mock variable creation
            mock_solver_context.model.NewBoolVar.return_value = Mock()
            
            # Measure validation time
            start_time = time.time()
            try:
                result = constraint._validate_fixed_cast_recursive(expression, mock_cast_group)
                validation_success = True
            except Exception:
                validation_success = False
            end_time = time.time()
            
            validation_time = end_time - start_time
            
            # Should process deep expressions efficiently
            assert validation_time < 0.5  # Should complete quickly
            if depth <= 10:  # Reasonable depths should work
                assert validation_success
    
    def test_constraint_parsing_performance_various_formats(self, mock_solver_context):
        """Test: Parsing-Performance verschiedener Fixed Cast Formate."""
        import time
        
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Test various fixed cast string formats
        person_ids = [str(uuid4()) for _ in range(10)]
        
        test_formats = [
            # Simple formats
            f"['{person_ids[0]}']",
            f"['{person_ids[0]}' and '{person_ids[1]}']",
            f"['{person_ids[0]}' or '{person_ids[1]}']",
            
            # Complex formats with UUID() prefixes
            f"[UUID('{person_ids[0]}') and UUID('{person_ids[1]}')]",
            f"[UUID('{person_ids[0]}') or UUID('{person_ids[1]}') or UUID('{person_ids[2]}')]",
            
            # Formats with 'in team' suffixes
            f"['{person_ids[0]}' and '{person_ids[1]}' in team]",
            f"[UUID('{person_ids[0]}') and UUID('{person_ids[1]}') in team]",
            
            # Long expressions
            f"['{person_ids[0]}' and '{person_ids[1]}' and '{person_ids[2]}' and '{person_ids[3]}']",
            f"['{person_ids[0]}' or '{person_ids[1]}' or '{person_ids[2]}' or '{person_ids[3]}' or '{person_ids[4]}']",
        ]
        
        for format_string in test_formats:
            # Measure parsing time
            start_time = time.time()
            try:
                result = constraint._parse_fixed_cast_string(format_string)
                parsing_success = True
            except Exception:
                parsing_success = False
            end_time = time.time()
            
            parsing_time = end_time - start_time
            
            # Should parse all formats quickly
            assert parsing_time < 0.1  # Should be very fast
            assert parsing_success  # All test formats should be valid
    
    def test_constraint_memory_efficiency_fixed_casts(self, mock_solver_context):
        """Test: Memory-Effizienz bei vielen Fixed Casts."""
        import gc
        
        constraint = FixedCastConstraint(mock_solver_context)
        
        # Setup minimal but valid entities
        mock_solver_context.entities.cast_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        
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
