"""
Unit-Tests für AbstractConstraint Basisklasse

Testet die gemeinsame Basis aller Constraint-Implementierungen.
"""

import pytest
from unittest.mock import Mock, patch
from abc import ABC, abstractmethod

from sat_solver.constraints.base import AbstractConstraint


class TestableConstraint(AbstractConstraint):
    """Konkrete Implementierung für Tests."""
    
    def __init__(self, context, should_fail_setup=False):
        super().__init__(context)
        self.should_fail_setup = should_fail_setup
        self.variables_created = []
        self.constraints_added = []
    
    @property
    def constraint_name(self) -> str:
        return "testable_constraint"
    
    def create_variables(self):
        if self.should_fail_setup:
            raise ValueError("Simulated variable creation failure")
        
        # Simulate creating some variables
        var1 = Mock()
        var1.name = "test_var_1"
        var2 = Mock()
        var2.name = "test_var_2"
        
        self.variables_created = [var1, var2]
        return self.variables_created
    
    def add_constraints(self):
        if self.should_fail_setup:
            raise ValueError("Simulated constraint addition failure")
        
        # Simulate adding constraints
        constraint1 = Mock()
        constraint1.name = "test_constraint_1"
        constraint2 = Mock()
        constraint2.name = "test_constraint_2"
        
        self.constraints_added = [constraint1, constraint2]


class IncompleteConstraint(AbstractConstraint):
    """Constraint der nicht alle abstrakte Methoden implementiert."""
    
    @property
    def constraint_name(self) -> str:
        return "incomplete_constraint"
    
    def create_variables(self):
        return []
    
    # Missing add_constraints method


@pytest.mark.unit
class TestAbstractConstraint:
    """Test-Klasse für AbstractConstraint."""
    
    def test_abstract_constraint_cannot_be_instantiated(self, mock_solver_context):
        """Test: AbstractConstraint kann nicht direkt instanziiert werden."""
        with pytest.raises(TypeError):
            AbstractConstraint(mock_solver_context)
    
    def test_concrete_constraint_initialization(self, mock_solver_context):
        """Test: Konkrete Constraint-Implementierung kann instanziiert werden."""
        constraint = TestableConstraint(mock_solver_context)
        
        assert constraint.context == mock_solver_context
        assert constraint.constraint_name == "testable_constraint"
        assert not constraint.is_setup_complete()
        assert constraint.variables_created == []
        assert constraint.constraints_added == []
    
    def test_constraint_setup_success(self, mock_solver_context):
        """Test: Erfolgreiches Constraint-Setup."""
        constraint = TestableConstraint(mock_solver_context)
        
        # Initially not setup
        assert not constraint.is_setup_complete()
        
        # Setup
        success = constraint.setup()
        
        # Verify success
        assert success is True
        assert constraint.is_setup_complete()
        assert len(constraint.variables_created) == 2
        assert len(constraint.constraints_added) == 2
        assert constraint.variables_created[0].name == "test_var_1"
        assert constraint.constraints_added[0].name == "test_constraint_1"
    
    def test_constraint_setup_failure_in_create_variables(self, mock_solver_context):
        """Test: Setup-Fehler bei Variable-Erstellung."""
        constraint = TestableConstraint(mock_solver_context, should_fail_setup=True)
        
        # Setup should fail
        success = constraint.setup()
        
        # Verify failure
        assert success is False
        assert not constraint.is_setup_complete()
        assert constraint.variables_created == []  # Should remain empty
    
    @patch('sat_solver.constraints.base.logger')
    def test_constraint_setup_logging(self, mock_logger, mock_solver_context):
        """Test: Logging während Constraint-Setup."""
        constraint = TestableConstraint(mock_solver_context)
        
        # Setup
        success = constraint.setup()
        
        # Verify logging occurred
        assert mock_logger.debug.called or mock_logger.info.called
        assert success is True
    
    def test_constraint_setup_idempotent(self, mock_solver_context):
        """Test: Setup ist idempotent (mehrfache Aufrufe sicher)."""
        constraint = TestableConstraint(mock_solver_context)
        
        # First setup
        success1 = constraint.setup()
        variables_after_first = len(constraint.variables_created)
        constraints_after_first = len(constraint.constraints_added)
        
        # Second setup should not change anything
        success2 = constraint.setup()
        variables_after_second = len(constraint.variables_created)
        constraints_after_second = len(constraint.constraints_added)
        
        # Verify idempotent behavior
        assert success1 is True
        assert success2 is True
        assert variables_after_first == variables_after_second
        assert constraints_after_first == constraints_after_second
        assert constraint.is_setup_complete()
    
    def test_constraint_name_property(self, mock_solver_context):
        """Test: constraint_name Property."""
        constraint = TestableConstraint(mock_solver_context)
        
        assert constraint.constraint_name == "testable_constraint"
        assert isinstance(constraint.constraint_name, str)
        assert len(constraint.constraint_name) > 0
    
    def test_constraint_context_access(self, mock_solver_context):
        """Test: Zugriff auf SolverContext."""
        constraint = TestableConstraint(mock_solver_context)
        
        assert constraint.context == mock_solver_context
        assert hasattr(constraint.context, 'model')
        assert hasattr(constraint.context, 'entities')
        assert hasattr(constraint.context, 'config')
    
    def test_constraint_setup_with_context_validation(self, mock_solver_context):
        """Test: Setup mit Context-Validierung."""
        # Mock context validation
        mock_solver_context.is_valid.return_value = True
        
        constraint = TestableConstraint(mock_solver_context)
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()
    
    def test_constraint_setup_with_invalid_context(self, mock_solver_context):
        """Test: Setup mit ungültigem Context."""
        # Mock invalid context
        mock_solver_context.is_valid.return_value = False
        
        constraint = TestableConstraint(mock_solver_context)
        success = constraint.setup()
        
        # Should still try to setup (context validation is not enforced in base class)
        assert success is True  # TestableConstraint doesn't check context validity
    
    def test_constraint_error_handling_in_setup(self, mock_solver_context):
        """Test: Error-Handling während Setup."""
        constraint = TestableConstraint(mock_solver_context, should_fail_setup=True)
        
        # Setup should handle errors gracefully
        success = constraint.setup()
        
        assert success is False
        assert not constraint.is_setup_complete()
    
    def test_constraint_inheritance_hierarchy(self, mock_solver_context):
        """Test: Vererbungshierarchie ist korrekt."""
        constraint = TestableConstraint(mock_solver_context)
        
        assert isinstance(constraint, AbstractConstraint)
        assert isinstance(constraint, ABC)
        assert hasattr(constraint, 'setup')
        assert hasattr(constraint, 'is_setup_complete')
        assert hasattr(constraint, 'constraint_name')
        assert hasattr(constraint, 'create_variables')
        assert hasattr(constraint, 'add_constraints')


@pytest.mark.integration
class TestAbstractConstraintIntegration:
    """Integration-Tests für AbstractConstraint."""
    
    def test_constraint_with_real_solver_context(self, mock_solver_context):
        """Test: Constraint mit realistischem SolverContext."""
        # Enhance mock context with more realistic behavior
        mock_solver_context.model.NewBoolVar = Mock(return_value=Mock())
        mock_solver_context.entities.actor_plan_periods = {
            'actor1': Mock(),
            'actor2': Mock()
        }
        mock_solver_context.config.max_time_seconds = 30
        
        constraint = TestableConstraint(mock_solver_context)
        success = constraint.setup()
        
        assert success is True
        assert constraint.context.model.NewBoolVar is not None
        assert len(constraint.context.entities.actor_plan_periods) == 2
        assert constraint.context.config.max_time_seconds == 30
    
    def test_multiple_constraints_sharing_context(self, mock_solver_context):
        """Test: Mehrere Constraints teilen sich einen Context."""
        constraint1 = TestableConstraint(mock_solver_context)
        constraint2 = TestableConstraint(mock_solver_context)
        
        # Setup both
        success1 = constraint1.setup()
        success2 = constraint2.setup()
        
        # Verify both use same context
        assert success1 is True
        assert success2 is True
        assert constraint1.context is constraint2.context
        assert constraint1.is_setup_complete()
        assert constraint2.is_setup_complete()
    
    def test_constraint_performance_with_large_context(self, mock_solver_context):
        """Test: Constraint-Performance mit großem Context."""
        import time
        
        # Simulate large context
        large_entities = {}
        for i in range(1000):
            large_entities[f'actor_{i}'] = Mock()
        
        mock_solver_context.entities.actor_plan_periods = large_entities
        
        constraint = TestableConstraint(mock_solver_context)
        
        # Measure setup time
        start_time = time.time()
        success = constraint.setup()
        end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Verify performance and success
        assert success is True
        assert setup_time < 1.0  # Should be fast even with large context
        assert constraint.is_setup_complete()
    
    def test_constraint_lifecycle_management(self, mock_solver_context):
        """Test: Constraint Lifecycle Management."""
        constraint = TestableConstraint(mock_solver_context)
        
        # Initial state
        assert not constraint.is_setup_complete()
        assert constraint.variables_created == []
        assert constraint.constraints_added == []
        
        # Setup phase
        success = constraint.setup()
        assert success is True
        assert constraint.is_setup_complete()
        assert len(constraint.variables_created) > 0
        assert len(constraint.constraints_added) > 0
        
        # Constraint should remain setup
        assert constraint.is_setup_complete()
    
    def test_constraint_error_recovery(self, mock_solver_context):
        """Test: Constraint Error Recovery."""
        # First attempt fails
        failing_constraint = TestableConstraint(mock_solver_context, should_fail_setup=True)
        success = failing_constraint.setup()
        assert success is False
        assert not failing_constraint.is_setup_complete()
        
        # Fix the constraint and try again
        failing_constraint.should_fail_setup = False
        success = failing_constraint.setup()
        assert success is True
        assert failing_constraint.is_setup_complete()
    
    @patch('sat_solver.constraints.base.logger')
    def test_constraint_comprehensive_logging(self, mock_logger, mock_solver_context):
        """Test: Umfassendes Constraint-Logging."""
        constraint = TestableConstraint(mock_solver_context)
        
        # Success case
        success = constraint.setup()
        assert success is True
        
        # Verify some form of logging occurred
        assert (mock_logger.debug.called or 
                mock_logger.info.called or 
                mock_logger.warning.called or 
                mock_logger.error.called)
        
        # Test failure case
        failing_constraint = TestableConstraint(mock_solver_context, should_fail_setup=True)
        success = failing_constraint.setup()
        assert success is False
        
        # Error should be logged
        assert mock_logger.error.called or mock_logger.warning.called
    
    def test_constraint_memory_management(self, mock_solver_context):
        """Test: Constraint Memory Management."""
        import gc
        import sys
        
        initial_count = len(gc.get_objects())
        
        # Create multiple constraints
        constraints = []
        for i in range(100):
            constraint = TestableConstraint(mock_solver_context)
            constraint.setup()
            constraints.append(constraint)
        
        # Verify all are setup
        for constraint in constraints:
            assert constraint.is_setup_complete()
        
        # Clear references
        del constraints
        gc.collect()
        
        final_count = len(gc.get_objects())
        
        # Memory should be reasonable (exact values depend on Python implementation)
        # Just verify we didn't leak massive amounts
        assert final_count < initial_count + 1000  # Allow some growth but not excessive
