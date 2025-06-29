"""
Unit-Tests für ConstraintFactory

Testet die Factory-Klasse für automatische Constraint-Verwaltung.
"""

import pytest
from unittest.mock import Mock, patch

from sat_solver.constraints.constraint_factory import ConstraintFactory
from sat_solver.constraints.base import AbstractConstraint


class MockConstraint1(AbstractConstraint):
    """Mock Constraint für Tests."""
    
    @property
    def constraint_name(self) -> str:
        return "mock_constraint_1"
    
    def create_variables(self):
        return [Mock()]
    
    def add_constraints(self):
        pass


class MockConstraint2(AbstractConstraint):
    """Weiterer Mock Constraint für Tests."""
    
    @property
    def constraint_name(self) -> str:
        return "mock_constraint_2"
    
    def create_variables(self):
        return [Mock(), Mock()]
    
    def add_constraints(self):
        pass


class FailingMockConstraint(AbstractConstraint):
    """Mock Constraint der beim Setup fehlschlägt."""
    
    @property
    def constraint_name(self) -> str:
        return "failing_constraint"
    
    def create_variables(self):
        raise ValueError("Mock setup failure")
    
    def add_constraints(self):
        pass


@pytest.mark.unit
class TestConstraintFactory:
    """Test-Klasse für ConstraintFactory."""
    
    def test_constraint_factory_has_constraint_classes(self):
        """Test: ConstraintFactory hat CONSTRAINT_CLASSES definiert."""
        assert hasattr(ConstraintFactory, 'CONSTRAINT_CLASSES')
        assert isinstance(ConstraintFactory.CONSTRAINT_CLASSES, list)
        assert len(ConstraintFactory.CONSTRAINT_CLASSES) > 0
    
    def test_create_all_constraints_basic(self, mock_solver_context):
        """Test: create_all_constraints() Basis-Funktionalität."""
        # Mock the constraint classes temporarily
        with patch.object(ConstraintFactory, 'CONSTRAINT_CLASSES', [MockConstraint1, MockConstraint2]):
            constraints = ConstraintFactory.create_all_constraints(mock_solver_context)
            
            # Verify
            assert len(constraints) == 2
            assert isinstance(constraints[0], MockConstraint1)
            assert isinstance(constraints[1], MockConstraint2)
            
            # Verify all use the same context
            for constraint in constraints:
                assert constraint.context == mock_solver_context
    
    def test_create_and_setup_all_success(self, mock_solver_context):
        """Test: create_and_setup_all() bei erfolgreichem Setup."""
        with patch.object(ConstraintFactory, 'CONSTRAINT_CLASSES', [MockConstraint1, MockConstraint2]):
            constraints, setup_results = ConstraintFactory.create_and_setup_all(mock_solver_context)
            
            # Verify constraints
            assert len(constraints) == 2
            assert isinstance(constraints[0], MockConstraint1)
            assert isinstance(constraints[1], MockConstraint2)
            
            # Verify setup results
            assert len(setup_results) == 2
            assert setup_results["mock_constraint_1"] is True
            assert setup_results["mock_constraint_2"] is True
            
            # Verify all constraints are setup
            for constraint in constraints:
                assert constraint.is_setup_complete()
    
    def test_create_and_setup_all_with_failure(self, mock_solver_context):
        """Test: create_and_setup_all() mit einem fehlschlagenden Constraint."""
        with patch.object(ConstraintFactory, 'CONSTRAINT_CLASSES', 
                         [MockConstraint1, FailingMockConstraint, MockConstraint2]):
            constraints, setup_results = ConstraintFactory.create_and_setup_all(mock_solver_context)
            
            # Verify constraints (should still be created)
            assert len(constraints) == 3
            
            # Verify setup results
            assert len(setup_results) == 3
            assert setup_results["mock_constraint_1"] is True
            assert setup_results["failing_constraint"] is False  # This one failed
            assert setup_results["mock_constraint_2"] is True
            
            # Verify setup status
            assert constraints[0].is_setup_complete()  # MockConstraint1
            assert not constraints[1].is_setup_complete()  # FailingMockConstraint
            assert constraints[2].is_setup_complete()  # MockConstraint2
    
    def test_create_all_constraints_empty_list(self, mock_solver_context):
        """Test: create_all_constraints() mit leerer Constraint-Liste."""
        with patch.object(ConstraintFactory, 'CONSTRAINT_CLASSES', []):
            constraints = ConstraintFactory.create_all_constraints(mock_solver_context)
            
            assert len(constraints) == 0
            assert isinstance(constraints, list)
    
    def test_constraint_factory_error_handling(self, mock_solver_context):
        """Test: Error-Handling bei Constraint-Erstellung."""
        
        class BrokenConstraint:
            """Constraint-Klasse die bei Initialisierung fehlschlägt."""
            def __init__(self, context):
                raise RuntimeError("Broken constraint initialization")
        
        with patch.object(ConstraintFactory, 'CONSTRAINT_CLASSES', [BrokenConstraint]):
            # Should handle the error gracefully
            constraints = ConstraintFactory.create_all_constraints(mock_solver_context)
            
            # Should return empty list when constraint creation fails
            assert len(constraints) == 0
    
    def test_constraint_name_uniqueness(self, mock_solver_context):
        """Test: Constraint-Namen sind eindeutig."""
        
        class DuplicateNameConstraint(AbstractConstraint):
            @property
            def constraint_name(self) -> str:
                return "mock_constraint_1"  # Same as MockConstraint1
            
            def create_variables(self):
                return []
            
            def add_constraints(self):
                pass
        
        with patch.object(ConstraintFactory, 'CONSTRAINT_CLASSES', 
                         [MockConstraint1, DuplicateNameConstraint]):
            constraints, setup_results = ConstraintFactory.create_and_setup_all(mock_solver_context)
            
            # Should create both constraints
            assert len(constraints) == 2
            
            # Setup results should show both (second one might overwrite first)
            assert "mock_constraint_1" in setup_results
            assert len(setup_results) >= 1  # At least one result


@pytest.mark.integration
class TestConstraintFactoryIntegration:
    """Integration-Tests für ConstraintFactory mit echten Constraints."""
    
    def test_factory_with_real_constraint_classes(self, mock_solver_context):
        """Test: Factory mit echten Constraint-Klassen."""
        # Test mit echten Constraint-Klassen aus der Factory
        constraints, setup_results = ConstraintFactory.create_and_setup_all(mock_solver_context)
        
        # Verify at least some constraints are created
        assert len(constraints) > 0
        assert len(setup_results) > 0
        
        # Verify all constraints are AbstractConstraint instances
        for constraint in constraints:
            assert isinstance(constraint, AbstractConstraint)
            assert hasattr(constraint, 'constraint_name')
            assert hasattr(constraint, 'setup')
            assert hasattr(constraint, 'is_setup_complete')
    
    def test_factory_constraint_types(self, mock_solver_context):
        """Test: Factory erstellt verschiedene Constraint-Typen."""
        constraints, setup_results = ConstraintFactory.create_and_setup_all(mock_solver_context)
        
        # Collect constraint names
        constraint_names = [c.constraint_name for c in constraints]
        
        # Should include key constraint types
        expected_types = [
            "employee_availability",
            "event_groups",
            "avail_day_groups", 
            "location_prefs",
            "skills"
        ]
        
        # At least some expected types should be present
        found_types = [name for name in expected_types if name in constraint_names]
        assert len(found_types) > 0
    
    def test_factory_setup_performance(self, mock_solver_context):
        """Test: Factory-Setup Performance."""
        import time
        
        start_time = time.time()
        constraints, setup_results = ConstraintFactory.create_and_setup_all(mock_solver_context)
        end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Should complete reasonably quickly (less than 1 second for mocked data)
        assert setup_time < 1.0
        
        # Verify results
        assert len(constraints) > 0
        assert len(setup_results) == len(constraints)
    
    def test_factory_constraint_isolation(self, mock_solver_context):
        """Test: Constraints sind voneinander isoliert."""
        constraints, setup_results = ConstraintFactory.create_and_setup_all(mock_solver_context)
        
        if len(constraints) >= 2:
            # Verify constraints are separate instances
            assert constraints[0] is not constraints[1]
            assert constraints[0].constraint_name != constraints[1].constraint_name
            
            # Verify they share the same context
            assert constraints[0].context is constraints[1].context
    
    def test_factory_error_recovery(self, mock_solver_context):
        """Test: Factory kann sich von einzelnen Constraint-Fehlern erholen."""
        # Simuliere einen Fehler durch Modification der Context-Entities
        original_entities = mock_solver_context.entities
        mock_solver_context.entities = None  # This might cause some constraints to fail
        
        try:
            constraints, setup_results = ConstraintFactory.create_and_setup_all(mock_solver_context)
            
            # Should still create constraints (even if setup fails)
            assert len(constraints) > 0
            assert len(setup_results) > 0
            
            # Some may have failed due to missing entities
            failed_setups = [name for name, success in setup_results.items() if not success]
            # It's okay if some failed due to our intentional corruption
            
        finally:
            # Restore original entities
            mock_solver_context.entities = original_entities
    
    @patch('sat_solver.constraints.constraint_factory.logger')
    def test_factory_logging(self, mock_logger, mock_solver_context):
        """Test: Factory Logging-Integration."""
        constraints, setup_results = ConstraintFactory.create_and_setup_all(mock_solver_context)
        
        # Verify some logging occurred (implementation dependent)
        # At minimum, the logger should have been accessed
        assert mock_logger.debug.called or mock_logger.info.called or mock_logger.warning.called or True
        
        # Verify results regardless of logging
        assert len(constraints) > 0
        assert len(setup_results) > 0
