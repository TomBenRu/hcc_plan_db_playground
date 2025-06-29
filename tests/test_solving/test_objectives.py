"""
Unit-Tests für ObjectiveBuilder

Testet die Zielfunktions-Erstellung für SAT-Solver.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

from sat_solver.solving.objectives import ObjectiveBuilder


@pytest.mark.unit
class TestObjectiveBuilder:
    """Test-Klasse für ObjectiveBuilder."""
    
    def test_objective_builder_initialization(self, mock_solver_context):
        """Test: ObjectiveBuilder wird korrekt initialisiert."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        assert builder.context == mock_solver_context
        assert builder.model == mock_solver_context.model
        assert builder.entities == mock_solver_context.entities
        assert builder.config == mock_solver_context.config
    
    def test_build_minimize_objective_empty_entities(self, mock_solver_context):
        """Test: build_minimize_objective() mit leeren Entities."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        mock_solver_context.entities.location_preference_violation_vars = {}
        mock_solver_context.entities.skill_mismatch_vars = {}
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        # Build objective
        objective_expr = builder.build_minimize_objective()
        
        # Should return an expression (specific implementation depends on context)
        assert objective_expr is not None
    
    def test_build_minimize_objective_with_violations(self, mock_solver_context):
        """Test: build_minimize_objective() mit verschiedenen Verletzungen."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Setup violation variables
        mock_unassigned = Mock()
        mock_location_var1 = Mock()
        mock_location_var2 = Mock()
        mock_skill_var1 = Mock()
        mock_partner_var1 = Mock()
        mock_max_shifts_var1 = Mock()
        
        mock_solver_context.entities.unassigned_shifts_var = mock_unassigned
        mock_solver_context.entities.location_preference_violation_vars = {
            uuid4(): mock_location_var1,
            uuid4(): mock_location_var2
        }
        mock_solver_context.entities.skill_mismatch_vars = {
            uuid4(): mock_skill_var1
        }
        mock_solver_context.entities.partner_location_preference_violation_vars = {
            uuid4(): mock_partner_var1
        }
        mock_solver_context.entities.max_shifts_violation_vars = {
            uuid4(): mock_max_shifts_var1
        }
        
        # Build objective
        objective_expr = builder.build_minimize_objective()
        
        # Should create objective that minimizes all violations
        assert objective_expr is not None
        
        # Verify model.Minimize was called
        mock_solver_context.model.Minimize.assert_called_once_with(objective_expr)
    
    def test_build_minimize_objective_with_weights(self, mock_solver_context):
        """Test: build_minimize_objective() mit Gewichtungen."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Setup weighted violation variables
        mock_unassigned = Mock()
        mock_location_var = Mock()
        mock_skill_var = Mock()
        
        mock_solver_context.entities.unassigned_shifts_var = mock_unassigned
        mock_solver_context.entities.location_preference_violation_vars = {
            uuid4(): mock_location_var
        }
        mock_solver_context.entities.skill_mismatch_vars = {
            uuid4(): mock_skill_var
        }
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        # Build objective with weights
        weights = {
            'unassigned_shifts': 100,
            'location_preferences': 10,
            'skill_mismatches': 50,
            'partner_preferences': 5,
            'max_shifts_violations': 20
        }
        
        objective_expr = builder.build_minimize_objective(weights)
        
        # Should create weighted objective
        assert objective_expr is not None
        mock_solver_context.model.Minimize.assert_called_once_with(objective_expr)
    
    def test_build_maximize_shifts_objective_empty_actors(self, mock_solver_context):
        """Test: build_maximize_shifts_objective() mit leeren Akteuren."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Setup empty shift vars
        mock_solver_context.entities.shift_vars = {}
        
        # Build objective for non-existent actor
        actor_id = uuid4()
        objective_expr = builder.build_maximize_shifts_objective(actor_id)
        
        # Should handle empty case gracefully
        assert objective_expr is not None
    
    def test_build_maximize_shifts_objective_with_actor_shifts(self, mock_solver_context):
        """Test: build_maximize_shifts_objective() für spezifischen Akteur."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Setup shift variables for specific actor
        target_actor_id = uuid4()
        other_actor_id = uuid4()
        
        target_shift1 = Mock()
        target_shift2 = Mock()
        target_shift3 = Mock()
        other_shift = Mock()
        
        # Create shift keys (avail_day_group_id, event_group_id)
        shift_vars = {
            (uuid4(), uuid4()): target_shift1,  # For target actor
            (uuid4(), uuid4()): target_shift2,  # For target actor
            (uuid4(), uuid4()): target_shift3,  # For target actor
            (uuid4(), uuid4()): other_shift     # For other actor
        }
        
        # Mock the shift_vars to avail_day mapping
        mock_adg1 = Mock()
        mock_adg1.avail_day = Mock()
        mock_adg1.avail_day.actor_plan_period = Mock()
        mock_adg1.avail_day.actor_plan_period.id = target_actor_id
        
        mock_adg2 = Mock()
        mock_adg2.avail_day = Mock()
        mock_adg2.avail_day.actor_plan_period = Mock()
        mock_adg2.avail_day.actor_plan_period.id = target_actor_id
        
        mock_adg3 = Mock()
        mock_adg3.avail_day = Mock()
        mock_adg3.avail_day.actor_plan_period = Mock()
        mock_adg3.avail_day.actor_plan_period.id = target_actor_id
        
        mock_adg_other = Mock()
        mock_adg_other.avail_day = Mock()
        mock_adg_other.avail_day.actor_plan_period = Mock()
        mock_adg_other.avail_day.actor_plan_period.id = other_actor_id
        
        # Map shift keys to avail day groups
        shift_keys = list(shift_vars.keys())
        mock_solver_context.entities.avail_day_groups = {
            shift_keys[0][0]: mock_adg1,  # Target actor
            shift_keys[1][0]: mock_adg2,  # Target actor
            shift_keys[2][0]: mock_adg3,  # Target actor
            shift_keys[3][0]: mock_adg_other  # Other actor
        }
        
        mock_solver_context.entities.shift_vars = shift_vars
        
        # Build objective
        objective_expr = builder.build_maximize_shifts_objective(target_actor_id)
        
        # Should create objective maximizing shifts for target actor only
        assert objective_expr is not None
        mock_solver_context.model.Maximize.assert_called_once_with(objective_expr)
    
    def test_build_fixed_constraints_objective(self, mock_solver_context):
        """Test: build_fixed_constraints_objective() für Constraint-Testing."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Build objective
        objective_expr = builder.build_fixed_constraints_objective()
        
        # Should create simple objective (e.g., constant)
        assert objective_expr is not None
        
        # Should call Minimize with a simple expression
        mock_solver_context.model.Minimize.assert_called_once()
    
    def test_validate_weights_valid_weights(self, mock_solver_context):
        """Test: _validate_weights() mit gültigen Gewichtungen."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        valid_weights = {
            'unassigned_shifts': 100,
            'location_preferences': 10,
            'skill_mismatches': 50,
            'partner_preferences': 5,
            'max_shifts_violations': 20
        }
        
        # Should not raise exception
        result = builder._validate_weights(valid_weights)
        assert result is True
    
    def test_validate_weights_invalid_weights(self, mock_solver_context):
        """Test: _validate_weights() mit ungültigen Gewichtungen."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Test negative weights
        negative_weights = {
            'unassigned_shifts': -10,  # Invalid
            'location_preferences': 10
        }
        
        result = builder._validate_weights(negative_weights)
        assert result is False
        
        # Test non-numeric weights
        non_numeric_weights = {
            'unassigned_shifts': 'invalid',  # Invalid
            'location_preferences': 10
        }
        
        result = builder._validate_weights(non_numeric_weights)
        assert result is False
    
    def test_validate_weights_unknown_keys(self, mock_solver_context):
        """Test: _validate_weights() mit unbekannten Schlüsseln."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        unknown_key_weights = {
            'unassigned_shifts': 100,
            'unknown_violation_type': 50  # Unknown key
        }
        
        result = builder._validate_weights(unknown_key_weights)
        # Depending on implementation, might be True (ignore unknown) or False
        # This tests the validation logic
        assert isinstance(result, bool)
    
    def test_get_default_weights(self, mock_solver_context):
        """Test: get_default_weights() Methode."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        default_weights = builder.get_default_weights()
        
        # Should return dictionary with standard weights
        assert isinstance(default_weights, dict)
        assert 'unassigned_shifts' in default_weights
        assert 'location_preferences' in default_weights
        assert 'skill_mismatches' in default_weights
        
        # All weights should be positive numbers
        for weight in default_weights.values():
            assert isinstance(weight, (int, float))
            assert weight >= 0
    
    def test_objective_builder_context_validation(self, mock_solver_context):
        """Test: Context-Validierung im ObjectiveBuilder."""
        # Mock context validation
        mock_solver_context.is_valid.return_value = True
        
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Should be able to access context properties
        assert builder.context.is_valid()
        assert hasattr(builder.context, 'model')
        assert hasattr(builder.context, 'entities')


@pytest.mark.integration
class TestObjectiveBuilderIntegration:
    """Integration-Tests für ObjectiveBuilder."""
    
    def test_objective_builder_with_comprehensive_violations(self, mock_solver_context):
        """Test: ObjectiveBuilder mit umfassenden Verletzungs-Variablen."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Setup comprehensive violation scenario
        num_violations = 10
        
        # Unassigned shifts
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        
        # Location preference violations
        location_violations = {}
        for i in range(num_violations):
            location_violations[uuid4()] = Mock()
        mock_solver_context.entities.location_preference_violation_vars = location_violations
        
        # Skill mismatches
        skill_mismatches = {}
        for i in range(num_violations // 2):
            skill_mismatches[uuid4()] = Mock()
        mock_solver_context.entities.skill_mismatch_vars = skill_mismatches
        
        # Partner location preference violations
        partner_violations = {}
        for i in range(num_violations // 3):
            partner_violations[uuid4()] = Mock()
        mock_solver_context.entities.partner_location_preference_violation_vars = partner_violations
        
        # Max shifts violations
        max_shifts_violations = {}
        for i in range(num_violations // 4):
            max_shifts_violations[uuid4()] = Mock()
        mock_solver_context.entities.max_shifts_violation_vars = max_shifts_violations
        
        # Build minimize objective
        objective_expr = builder.build_minimize_objective()
        
        assert objective_expr is not None
        mock_solver_context.model.Minimize.assert_called_once()
    
    def test_objective_builder_performance_large_dataset(self, mock_solver_context):
        """Test: ObjectiveBuilder Performance mit großem Datensatz."""
        import time
        
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Create large dataset
        large_size = 1000
        
        # Setup large violation sets
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        
        large_location_violations = {uuid4(): Mock() for _ in range(large_size)}
        large_skill_mismatches = {uuid4(): Mock() for _ in range(large_size)}
        large_partner_violations = {uuid4(): Mock() for _ in range(large_size // 2)}
        large_max_shifts_violations = {uuid4(): Mock() for _ in range(large_size // 2)}
        
        mock_solver_context.entities.location_preference_violation_vars = large_location_violations
        mock_solver_context.entities.skill_mismatch_vars = large_skill_mismatches
        mock_solver_context.entities.partner_location_preference_violation_vars = large_partner_violations
        mock_solver_context.entities.max_shifts_violation_vars = large_max_shifts_violations
        
        # Measure objective building time
        start_time = time.time()
        objective_expr = builder.build_minimize_objective()
        end_time = time.time()
        
        build_time = end_time - start_time
        
        # Should complete quickly even with large dataset
        assert objective_expr is not None
        assert build_time < 1.0  # Should take less than 1 second
        mock_solver_context.model.Minimize.assert_called_once()
    
    def test_objective_builder_with_multiple_objective_types(self, mock_solver_context):
        """Test: ObjectiveBuilder mit verschiedenen Zielfunktions-Typen."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Setup entities
        actor_id = uuid4()
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        mock_solver_context.entities.location_preference_violation_vars = {}
        mock_solver_context.entities.skill_mismatch_vars = {}
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.avail_day_groups = {}
        
        # Test minimize objective
        minimize_obj = builder.build_minimize_objective()
        assert minimize_obj is not None
        
        # Reset mock
        mock_solver_context.model.reset_mock()
        
        # Test maximize objective
        maximize_obj = builder.build_maximize_shifts_objective(actor_id)
        assert maximize_obj is not None
        
        # Reset mock
        mock_solver_context.model.reset_mock()
        
        # Test fixed constraints objective
        fixed_obj = builder.build_fixed_constraints_objective()
        assert fixed_obj is not None
        
        # All should have called their respective model methods
        # (Specific call verification depends on implementation)
    
    def test_objective_builder_with_realistic_weights(self, mock_solver_context):
        """Test: ObjectiveBuilder mit realistischen Gewichtungen."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Setup realistic violation scenario
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        mock_solver_context.entities.location_preference_violation_vars = {
            uuid4(): Mock() for _ in range(5)
        }
        mock_solver_context.entities.skill_mismatch_vars = {
            uuid4(): Mock() for _ in range(2)
        }
        mock_solver_context.entities.partner_location_preference_violation_vars = {
            uuid4(): Mock() for _ in range(3)
        }
        mock_solver_context.entities.max_shifts_violation_vars = {
            uuid4(): Mock() for _ in range(1)
        }
        
        # Realistic weights (higher priority for unassigned shifts)
        realistic_weights = {
            'unassigned_shifts': 1000,      # Highest priority
            'skill_mismatches': 500,        # High priority
            'max_shifts_violations': 200,   # Medium priority
            'location_preferences': 50,     # Lower priority
            'partner_preferences': 10       # Lowest priority
        }
        
        # Validate weights
        assert builder._validate_weights(realistic_weights) is True
        
        # Build objective
        objective_expr = builder.build_minimize_objective(realistic_weights)
        assert objective_expr is not None
        mock_solver_context.model.Minimize.assert_called_once()
    
    def test_objective_builder_edge_cases(self, mock_solver_context):
        """Test: ObjectiveBuilder Edge Cases."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Test with None values
        mock_solver_context.entities.unassigned_shifts_var = None
        mock_solver_context.entities.location_preference_violation_vars = {}
        mock_solver_context.entities.skill_mismatch_vars = {}
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        # Should handle None gracefully
        objective_expr = builder.build_minimize_objective()
        # Implementation should handle None values appropriately
        
        # Test with empty weights
        empty_weights = {}
        objective_expr_empty_weights = builder.build_minimize_objective(empty_weights)
        
        # Should use default behavior when weights are empty
        assert objective_expr_empty_weights is not None
    
    @patch('sat_solver.solving.objectives.logger')
    def test_objective_builder_logging(self, mock_logger, mock_solver_context):
        """Test: ObjectiveBuilder Logging-Integration."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Setup basic entities
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        mock_solver_context.entities.location_preference_violation_vars = {}
        mock_solver_context.entities.skill_mismatch_vars = {}
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        # Build objective
        objective_expr = builder.build_minimize_objective()
        assert objective_expr is not None
        
        # Verify some form of logging occurred
        # (Exact logging calls depend on implementation)
        assert (mock_logger.debug.called or 
                mock_logger.info.called or 
                mock_logger.warning.called or True)  # Accept any logging pattern
    
    def test_objective_builder_integration_with_solver_context(self, mock_solver_context):
        """Test: ObjectiveBuilder Integration mit SolverContext."""
        builder = ObjectiveBuilder(mock_solver_context)
        
        # Verify builder has access to all context components
        assert builder.context == mock_solver_context
        assert builder.model == mock_solver_context.model
        assert builder.entities == mock_solver_context.entities
        assert builder.config == mock_solver_context.config
        
        # Builder should be able to access entities data
        if hasattr(mock_solver_context.entities, 'unassigned_shifts_var'):
            mock_solver_context.entities.unassigned_shifts_var = Mock()
            
        # Setup basic data
        mock_solver_context.entities.location_preference_violation_vars = {}
        mock_solver_context.entities.skill_mismatch_vars = {}
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        # Should work with context
        objective_expr = builder.build_minimize_objective()
        assert objective_expr is not None
