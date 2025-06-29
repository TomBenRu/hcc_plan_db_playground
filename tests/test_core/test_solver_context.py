"""
Unit-Tests für SolverContext

Testet die zentrale Datenverwaltung und Konfiguration des SAT-Solvers.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

from sat_solver.core.solver_context import SolverContext
from sat_solver.core.entities import Entities
from sat_solver.core.solver_config import SolverConfig


@pytest.mark.unit
class TestSolverContext:
    """Test-Klasse für SolverContext."""
    
    def test_solver_context_initialization(self, mock_solver_context):
        """Test: SolverContext wird korrekt initialisiert."""
        context = mock_solver_context
        
        assert context.entities is not None
        assert context.model is not None
        assert context.config is not None
        assert context.plan_period_id is not None
        assert isinstance(context.constraint_vars, dict)
    
    def test_add_constraint_vars(self, mock_solver_context):
        """Test: Constraint-Variablen können hinzugefügt werden."""
        context = mock_solver_context
        
        # Mock constraint variables
        mock_vars = [Mock(), Mock(), Mock()]
        
        # Add constraint vars
        context.add_constraint_vars("test_constraint", mock_vars)
        
        # Verify
        assert "test_constraint" in context.constraint_vars
        assert context.constraint_vars["test_constraint"] == mock_vars
    
    def test_get_constraint_vars(self, mock_solver_context):
        """Test: Constraint-Variablen können abgerufen werden."""
        context = mock_solver_context
        
        # Setup
        mock_vars = [Mock(), Mock()]
        context.add_constraint_vars("availability", mock_vars)
        
        # Test
        retrieved_vars = context.get_constraint_vars("availability")
        
        # Verify
        assert retrieved_vars == mock_vars
    
    def test_get_constraint_vars_nonexistent(self, mock_solver_context):
        """Test: Abrufen nicht existierender Constraint-Variablen."""
        context = mock_solver_context
        
        # Test
        retrieved_vars = context.get_constraint_vars("nonexistent")
        
        # Verify - sollte leere Liste zurückgeben
        assert retrieved_vars == []
    
    def test_is_valid_basic(self, mock_solver_context):
        """Test: Basis-Validierung des SolverContext."""
        context = mock_solver_context
        
        # Valid context should return True
        assert context.is_valid() is True
    
    def test_is_valid_missing_entities(self, mock_plan_period_id, mock_model, sample_solver_config):
        """Test: Validierung schlägt fehl bei fehlenden Entities."""
        context = SolverContext(
            entities=None,
            model=mock_model,
            config=sample_solver_config,
            plan_period_id=mock_plan_period_id
        )
        
        assert context.is_valid() is False
    
    def test_is_valid_missing_model(self, mock_plan_period_id, sample_entities, sample_solver_config):
        """Test: Validierung schlägt fehl bei fehlendem Model."""
        context = SolverContext(
            entities=sample_entities,
            model=None,
            config=sample_solver_config,
            plan_period_id=mock_plan_period_id
        )
        
        assert context.is_valid() is False
    
    def test_constraint_vars_multiple_constraints(self, mock_solver_context):
        """Test: Mehrere Constraint-Typen können verwaltet werden."""
        context = mock_solver_context
        
        # Add multiple constraint types
        availability_vars = [Mock(), Mock()]
        location_vars = [Mock(), Mock(), Mock()]
        skills_vars = [Mock()]
        
        context.add_constraint_vars("availability", availability_vars)
        context.add_constraint_vars("location_prefs", location_vars)
        context.add_constraint_vars("skills", skills_vars)
        
        # Verify all are stored correctly
        assert len(context.constraint_vars) == 3
        assert context.get_constraint_vars("availability") == availability_vars
        assert context.get_constraint_vars("location_prefs") == location_vars
        assert context.get_constraint_vars("skills") == skills_vars
    
    def test_constraint_vars_overwrite(self, mock_solver_context):
        """Test: Constraint-Variablen können überschrieben werden."""
        context = mock_solver_context
        
        # Add initial vars
        initial_vars = [Mock(), Mock()]
        context.add_constraint_vars("test", initial_vars)
        
        # Overwrite with new vars
        new_vars = [Mock(), Mock(), Mock()]
        context.add_constraint_vars("test", new_vars)
        
        # Verify overwrite
        assert context.get_constraint_vars("test") == new_vars
        assert len(context.get_constraint_vars("test")) == 3
    
    def test_get_summary(self, mock_solver_context):
        """Test: Context-Summary kann erstellt werden."""
        context = mock_solver_context
        
        # Add some constraint vars for testing
        context.add_constraint_vars("test_constraint", [Mock(), Mock()])
        
        # Get summary
        summary = context.get_summary()
        
        # Verify summary contains expected keys
        expected_keys = ['plan_period_id', 'entities_valid', 'model_valid', 'config_valid', 
                        'constraint_vars_count', 'total_constraint_vars']
        
        for key in expected_keys:
            assert key in summary
        
        # Verify some values
        assert summary['constraint_vars_count'] == 1
        assert summary['total_constraint_vars'] == 2
        assert summary['entities_valid'] is True
        assert summary['model_valid'] is True


@pytest.mark.integration
class TestSolverContextIntegration:
    """Integration-Tests für SolverContext mit anderen Komponenten."""
    
    def test_context_with_real_config(self, mock_plan_period_id, mock_model, sample_entities):
        """Test: SolverContext mit echter Konfiguration."""
        # Create real config
        config = SolverConfig.from_current_config()
        
        # Create context
        context = SolverContext(
            entities=sample_entities,
            model=mock_model,
            config=config,
            plan_period_id=mock_plan_period_id
        )
        
        # Verify
        assert context.is_valid() is True
        assert context.config.solver_parameters.max_time_in_seconds > 0
    
    @patch('sat_solver.core.solver_context.logger')
    def test_context_logging(self, mock_logger, mock_solver_context):
        """Test: SolverContext Logging-Integration."""
        context = mock_solver_context
        
        # Add constraint vars (should trigger logging)
        context.add_constraint_vars("test", [Mock()])
        
        # Verify is_valid method works (may use logging)
        assert context.is_valid() is True
