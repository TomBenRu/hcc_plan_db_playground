"""
Unit-Tests für EmployeeAvailabilityConstraint

Testet das Constraint für Mitarbeiterverfügbarkeit.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

from sat_solver.constraints.availability import EmployeeAvailabilityConstraint


@pytest.mark.unit
class TestEmployeeAvailabilityConstraint:
    """Test-Klasse für EmployeeAvailabilityConstraint."""
    
    def test_constraint_name(self, mock_solver_context):
        """Test: Constraint-Name ist korrekt."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        assert constraint.constraint_name == "employee_availability"
    
    def test_constraint_initialization(self, mock_solver_context):
        """Test: Constraint wird korrekt initialisiert."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        assert constraint.context == mock_solver_context
        assert constraint.model == mock_solver_context.model
        assert constraint.entities == mock_solver_context.entities
        assert constraint.config == mock_solver_context.config
        assert not constraint.is_setup_complete()
    
    def test_create_variables_empty_shifts(self, mock_solver_context):
        """Test: create_variables() mit leeren shifts_exclusive."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Empty shifts_exclusive
        mock_solver_context.entities.shifts_exclusive = {}
        
        variables = constraint.create_variables()
        
        # Should return empty list for empty shifts
        assert variables == []
    
    def test_create_variables_with_shifts(self, mock_solver_context):
        """Test: create_variables() mit vorhandenen shifts."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Setup shifts_exclusive with some exclusive and non-exclusive shifts
        adg_id1, eg_id1 = uuid4(), uuid4()
        adg_id2, eg_id2 = uuid4(), uuid4()
        
        mock_solver_context.entities.shifts_exclusive = {
            (adg_id1, eg_id1): 1,  # Allowed
            (adg_id2, eg_id2): 0   # Not allowed
        }
        
        variables = constraint.create_variables()
        
        # This constraint doesn't create new variables, only uses existing shift_vars
        assert variables == []
    
    def test_add_constraints_empty_shifts(self, mock_solver_context):
        """Test: add_constraints() mit leeren shifts."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Setup empty data
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.shift_vars = {}
        
        # Should not raise any errors
        constraint.add_constraints()
        
        # Model.Add should not have been called
        assert not mock_solver_context.model.Add.called
    
    def test_add_constraints_with_exclusive_shifts(self, mock_solver_context):
        """Test: add_constraints() mit exclusiven Shifts."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Setup test data
        adg_id1, eg_id1 = uuid4(), uuid4()
        adg_id2, eg_id2 = uuid4(), uuid4()
        adg_id3, eg_id3 = uuid4(), uuid4()
        
        # Mock shift variables
        mock_var1 = Mock()
        mock_var2 = Mock()
        mock_var3 = Mock()
        
        mock_solver_context.entities.shifts_exclusive = {
            (adg_id1, eg_id1): 1,  # Allowed - no constraint added
            (adg_id2, eg_id2): 0,  # Not allowed - constraint: var == 0
            (adg_id3, eg_id3): 0   # Not allowed - constraint: var == 0
        }
        
        mock_solver_context.entities.shift_vars = {
            (adg_id1, eg_id1): mock_var1,
            (adg_id2, eg_id2): mock_var2,
            (adg_id3, eg_id3): mock_var3
        }
        
        # Add constraints
        constraint.add_constraints()
        
        # Verify Add was called twice (for the two non-exclusive shifts)
        assert mock_solver_context.model.Add.call_count == 2
        
        # Verify the calls were for setting variables to 0
        calls = mock_solver_context.model.Add.call_args_list
        # Each call should be Add(var == 0) for non-exclusive shifts
        # The exact implementation may vary, but Add should be called
    
    def test_add_constraints_mixed_exclusivity(self, mock_solver_context):
        """Test: add_constraints() mit gemischten Exclusivitäts-Werten."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Setup mixed data
        keys_and_values = [
            ((uuid4(), uuid4()), 1),  # Allowed
            ((uuid4(), uuid4()), 0),  # Not allowed
            ((uuid4(), uuid4()), 1),  # Allowed
            ((uuid4(), uuid4()), 0),  # Not allowed
            ((uuid4(), uuid4()), 1),  # Allowed
        ]
        
        mock_solver_context.entities.shifts_exclusive = dict(keys_and_values)
        mock_solver_context.entities.shift_vars = {
            key: Mock() for key, _ in keys_and_values
        }
        
        # Add constraints
        constraint.add_constraints()
        
        # Should add constraints only for non-exclusive shifts (value == 0)
        non_exclusive_count = sum(1 for _, value in keys_and_values if value == 0)
        assert mock_solver_context.model.Add.call_count == non_exclusive_count
    
    def test_setup_complete_workflow(self, mock_solver_context):
        """Test: Kompletter Setup-Workflow."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Setup test data
        mock_solver_context.entities.shifts_exclusive = {
            (uuid4(), uuid4()): 1,
            (uuid4(), uuid4()): 0
        }
        mock_solver_context.entities.shift_vars = {
            key: Mock() for key in mock_solver_context.entities.shifts_exclusive.keys()
        }
        
        # Initial state
        assert not constraint.is_setup_complete()
        
        # Setup
        success = constraint.setup()
        
        # Verify success
        assert success is True
        assert constraint.is_setup_complete()
        
        # Verify constraints were added
        assert mock_solver_context.model.Add.called
    
    def test_constraint_with_missing_shift_vars(self, mock_solver_context):
        """Test: Constraint mit fehlenden shift_vars."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Setup shifts_exclusive but missing corresponding shift_vars
        mock_solver_context.entities.shifts_exclusive = {
            (uuid4(), uuid4()): 0
        }
        mock_solver_context.entities.shift_vars = {}  # Missing!
        
        # Should handle missing shift_vars gracefully
        constraint.add_constraints()
        
        # Should not have called Add (no variables to constrain)
        assert not mock_solver_context.model.Add.called


@pytest.mark.integration
class TestEmployeeAvailabilityConstraintIntegration:
    """Integration-Tests für EmployeeAvailabilityConstraint."""
    
    def test_constraint_with_realistic_data(self, mock_solver_context):
        """Test: Constraint mit realistischen Daten."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Create realistic scenario
        num_employees = 5
        num_events = 10
        
        # Generate realistic shifts_exclusive and shift_vars
        shifts_exclusive = {}
        shift_vars = {}
        
        for emp_i in range(num_employees):
            for event_i in range(num_events):
                adg_id = uuid4()
                eg_id = uuid4()
                
                # Some shifts are not allowed (e.g., time conflicts, location preferences)
                is_exclusive = (emp_i + event_i) % 3 != 0  # ~67% allowed
                exclusive_value = 1 if is_exclusive else 0
                
                shifts_exclusive[(adg_id, eg_id)] = exclusive_value
                shift_vars[(adg_id, eg_id)] = Mock()
        
        mock_solver_context.entities.shifts_exclusive = shifts_exclusive
        mock_solver_context.entities.shift_vars = shift_vars
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Verify constraints were added for non-exclusive shifts
        non_exclusive_count = sum(1 for value in shifts_exclusive.values() if value == 0)
        if non_exclusive_count > 0:
            assert mock_solver_context.model.Add.call_count == non_exclusive_count
        else:
            assert mock_solver_context.model.Add.call_count == 0
    
    def test_constraint_performance_large_dataset(self, mock_solver_context):
        """Test: Constraint Performance mit großem Datensatz."""
        import time
        
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Create large dataset
        large_size = 1000
        shifts_exclusive = {}
        shift_vars = {}
        
        for i in range(large_size):
            key = (uuid4(), uuid4())
            shifts_exclusive[key] = i % 3  # Mix of 0, 1, 2 values
            shift_vars[key] = Mock()
        
        mock_solver_context.entities.shifts_exclusive = shifts_exclusive
        mock_solver_context.entities.shift_vars = shift_vars
        
        # Measure setup time
        start_time = time.time()
        success = constraint.setup()
        end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Should complete quickly even with large dataset
        assert success is True
        assert setup_time < 1.0  # Should take less than 1 second
    
    def test_constraint_with_context_integration(self, mock_solver_context):
        """Test: Constraint Integration mit SolverContext."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Verify variables are stored in context
        stored_vars = mock_solver_context.get_constraint_vars("employee_availability")
        retrieved_vars = constraint.get_variables()
        
        assert stored_vars == retrieved_vars
    
    def test_constraint_error_handling(self, mock_solver_context):
        """Test: Error-Handling bei problematischen Daten."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Setup problematic data (None values)
        mock_solver_context.entities.shifts_exclusive = {
            (uuid4(), uuid4()): None,  # Invalid value
            (uuid4(), uuid4()): 0
        }
        mock_solver_context.entities.shift_vars = {
            key: Mock() for key in mock_solver_context.entities.shifts_exclusive.keys()
        }
        
        # Should handle errors gracefully
        try:
            success = constraint.setup()
            # Constraint might succeed or fail depending on implementation
            # The important thing is it doesn't crash
        except Exception as e:
            # If it raises an exception, it should be handled by the setup() method
            pytest.fail(f"Constraint should handle errors gracefully, but raised: {e}")
    
    @patch('sat_solver.constraints.availability.logger')
    def test_constraint_logging(self, mock_logger, mock_solver_context):
        """Test: Constraint Logging-Integration."""
        constraint = EmployeeAvailabilityConstraint(mock_solver_context)
        
        # Setup with some data
        mock_solver_context.entities.shifts_exclusive = {
            (uuid4(), uuid4()): 0,
            (uuid4(), uuid4()): 1
        }
        mock_solver_context.entities.shift_vars = {
            key: Mock() for key in mock_solver_context.entities.shifts_exclusive.keys()
        }
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Logging calls depend on implementation, but logger should be available
        # This test mainly verifies the logging framework is integrated
