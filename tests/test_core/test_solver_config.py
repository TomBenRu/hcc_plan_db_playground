"""
Unit-Tests für SolverConfig

Testet die Konfigurationsklassen des SAT-Solvers.
"""

import pytest
from unittest.mock import Mock, patch

from sat_solver.core.solver_config import SolverConfig, SolverParameters, MinimizationWeights


@pytest.mark.unit
class TestSolverParameters:
    """Test-Klasse für SolverParameters."""
    
    def test_solver_parameters_default_initialization(self):
        """Test: SolverParameters Standard-Initialisierung."""
        params = SolverParameters()
        
        # Verify default values
        assert params.max_time_in_seconds == 60
        assert params.log_search_progress is False
        assert params.randomize_search is True
        assert params.linearization_level == 0
        assert params.enumerate_all_solutions is False
        assert params.solution_limit is None
    
    def test_solver_parameters_custom_initialization(self):
        """Test: SolverParameters mit benutzerdefinierten Werten."""
        params = SolverParameters(
            max_time_in_seconds=120,
            log_search_progress=True,
            randomize_search=False,
            linearization_level=2,
            enumerate_all_solutions=True,
            solution_limit=10
        )
        
        # Verify custom values
        assert params.max_time_in_seconds == 120
        assert params.log_search_progress is True
        assert params.randomize_search is False
        assert params.linearization_level == 2
        assert params.enumerate_all_solutions is True
        assert params.solution_limit == 10
    
    def test_solver_parameters_validation(self):
        """Test: SolverParameters Validierung."""
        # Valid parameters
        params = SolverParameters(max_time_in_seconds=30)
        assert params.max_time_in_seconds == 30
        
        # Test edge cases
        params_zero = SolverParameters(max_time_in_seconds=0)
        assert params_zero.max_time_in_seconds == 0
        
        params_large = SolverParameters(max_time_in_seconds=3600)
        assert params_large.max_time_in_seconds == 3600


@pytest.mark.unit 
class TestMinimizationWeights:
    """Test-Klasse für MinimizationWeights."""
    
    def test_minimization_weights_default_initialization(self):
        """Test: MinimizationWeights Standard-Initialisierung."""
        weights = MinimizationWeights()
        
        # Verify default values exist and are reasonable
        assert weights.unassigned_shifts > 0
        assert weights.sum_squared_deviations > 0
        assert weights.constraints_weights_in_avail_day_groups >= 0
        assert weights.constraints_weights_in_event_groups >= 0
        assert weights.constraints_location_prefs >= 0
        assert weights.constraints_partner_loc_prefs >= 0
        assert weights.constraints_fixed_casts_conflicts >= 0
        assert weights.constraints_skills_match >= 0
        assert weights.constraints_cast_rule >= 0
    
    def test_minimization_weights_custom_initialization(self):
        """Test: MinimizationWeights mit benutzerdefinierten Werten."""
        weights = MinimizationWeights(
            unassigned_shifts=1000,
            sum_squared_deviations=500,
            constraints_location_prefs=10,
            constraints_skills_match=50
        )
        
        # Verify custom values
        assert weights.unassigned_shifts == 1000
        assert weights.sum_squared_deviations == 500
        assert weights.constraints_location_prefs == 10
        assert weights.constraints_skills_match == 50
    
    def test_minimization_weights_zero_values(self):
        """Test: MinimizationWeights mit Null-Werten."""
        weights = MinimizationWeights(
            unassigned_shifts=0,
            constraints_location_prefs=0
        )
        
        # Zero values should be allowed
        assert weights.unassigned_shifts == 0
        assert weights.constraints_location_prefs == 0


@pytest.mark.unit
class TestSolverConfig:
    """Test-Klasse für SolverConfig."""
    
    def test_solver_config_default_initialization(self):
        """Test: SolverConfig Standard-Initialisierung."""
        config = SolverConfig()
        
        # Verify components are initialized
        assert config.solver_parameters is not None
        assert config.minimization_weights is not None
        assert isinstance(config.solver_parameters, SolverParameters)
        assert isinstance(config.minimization_weights, MinimizationWeights)
    
    def test_solver_config_custom_components(self):
        """Test: SolverConfig mit benutzerdefinierten Komponenten."""
        custom_params = SolverParameters(max_time_in_seconds=180)
        custom_weights = MinimizationWeights(unassigned_shifts=2000)
        
        config = SolverConfig(
            solver_parameters=custom_params,
            minimization_weights=custom_weights
        )
        
        # Verify custom components
        assert config.solver_parameters == custom_params
        assert config.minimization_weights == custom_weights
        assert config.solver_parameters.max_time_in_seconds == 180
        assert config.minimization_weights.unassigned_shifts == 2000
    
    @patch('sat_solver.core.solver_config.curr_config_handler')
    def test_solver_config_from_current_config(self, mock_config_handler):
        """Test: SolverConfig.from_current_config() Factory-Methode."""
        # Setup mock config handler
        mock_solver_config = Mock()
        mock_solver_config.solver_parameters = Mock()
        mock_solver_config.solver_parameters.max_time_in_seconds = 90
        mock_solver_config.minimization_weights = Mock()
        mock_solver_config.minimization_weights.unassigned_shifts = 1500
        
        mock_config_handler.get_solver_config.return_value = mock_solver_config
        
        # Create config from current
        config = SolverConfig.from_current_config()
        
        # Verify factory method was called
        mock_config_handler.get_solver_config.assert_called_once()
        
        # Verify config is created
        assert config is not None
        assert isinstance(config, SolverConfig)
    
    def test_solver_config_to_dict(self):
        """Test: SolverConfig to_dict() Methode."""
        config = SolverConfig()
        
        # Get dictionary representation
        config_dict = config.to_dict()
        
        # Verify dictionary structure
        assert isinstance(config_dict, dict)
        assert 'solver_parameters' in config_dict
        assert 'minimization_weights' in config_dict
        
        # Verify nested structure
        params_dict = config_dict['solver_parameters']
        weights_dict = config_dict['minimization_weights']
        
        assert isinstance(params_dict, dict)
        assert isinstance(weights_dict, dict)
        
        # Verify some key fields
        assert 'max_time_in_seconds' in params_dict
        assert 'log_search_progress' in params_dict
        assert 'unassigned_shifts' in weights_dict
        assert 'sum_squared_deviations' in weights_dict
    
    def test_solver_config_equality(self):
        """Test: SolverConfig Gleichheitsvergleich."""
        # Create identical configs
        config1 = SolverConfig()
        config2 = SolverConfig()
        
        # They should be equal if they have the same values
        assert config1.solver_parameters.max_time_in_seconds == config2.solver_parameters.max_time_in_seconds
        assert config1.minimization_weights.unassigned_shifts == config2.minimization_weights.unassigned_shifts
    
    def test_solver_config_modification(self):
        """Test: SolverConfig kann nach Erstellung modifiziert werden."""
        config = SolverConfig()
        
        # Modify parameters
        original_time = config.solver_parameters.max_time_in_seconds
        config.solver_parameters.max_time_in_seconds = 300
        
        # Verify modification
        assert config.solver_parameters.max_time_in_seconds == 300
        assert config.solver_parameters.max_time_in_seconds != original_time
        
        # Modify weights
        original_weight = config.minimization_weights.unassigned_shifts
        config.minimization_weights.unassigned_shifts = 5000
        
        # Verify modification
        assert config.minimization_weights.unassigned_shifts == 5000
        assert config.minimization_weights.unassigned_shifts != original_weight


@pytest.mark.integration
class TestSolverConfigIntegration:
    """Integration-Tests für SolverConfig mit anderen Komponenten."""
    
    def test_solver_config_with_solver_context(self, mock_solver_context):
        """Test: SolverConfig Integration mit SolverContext."""
        context = mock_solver_context
        config = context.config
        
        # Verify config is properly integrated
        assert config is not None
        assert isinstance(config, SolverConfig)
        assert config.solver_parameters is not None
        assert config.minimization_weights is not None
    
    @patch('sat_solver.core.solver_config.curr_config_handler')
    def test_config_loading_with_real_handler(self, mock_config_handler):
        """Test: Konfiguration laden mit echtem Handler."""
        # Setup realistic mock
        mock_solver_config = Mock()
        
        # Mock solver parameters
        mock_params = Mock()
        mock_params.max_time_in_seconds = 120
        mock_params.log_search_progress = True
        mock_params.randomize_search = True
        mock_solver_config.solver_parameters = mock_params
        
        # Mock minimization weights
        mock_weights = Mock()
        mock_weights.unassigned_shifts = 1000
        mock_weights.sum_squared_deviations = 100
        mock_solver_config.minimization_weights = mock_weights
        
        mock_config_handler.get_solver_config.return_value = mock_solver_config
        
        # Load config
        config = SolverConfig.from_current_config()
        
        # Verify loaded correctly
        assert config.solver_parameters.max_time_in_seconds == 120
        assert config.solver_parameters.log_search_progress is True
        assert config.minimization_weights.unassigned_shifts == 1000
    
    def test_config_performance_settings(self):
        """Test: Performance-orientierte Konfigurationen."""
        # Fast config for testing
        fast_config = SolverConfig(
            solver_parameters=SolverParameters(
                max_time_in_seconds=10,
                log_search_progress=False,
                randomize_search=False
            )
        )
        
        # Thorough config for production
        thorough_config = SolverConfig(
            solver_parameters=SolverParameters(
                max_time_in_seconds=300,
                log_search_progress=True,
                randomize_search=True,
                enumerate_all_solutions=False
            )
        )
        
        # Verify configurations
        assert fast_config.solver_parameters.max_time_in_seconds < thorough_config.solver_parameters.max_time_in_seconds
        assert fast_config.solver_parameters.log_search_progress != thorough_config.solver_parameters.log_search_progress
        
        # Both should be valid
        assert fast_config.solver_parameters.max_time_in_seconds > 0
        assert thorough_config.solver_parameters.max_time_in_seconds > 0
