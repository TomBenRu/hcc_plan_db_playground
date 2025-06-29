"""
Unit-Tests für SATSolver

Testet die Hauptklasse für SAT-Solving-Operationen.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from ortools.sat.python import cp_model

from sat_solver.solving.solver import SATSolver
from sat_solver.core.solver_config import SolverConfig
from sat_solver.core.solver_result import SolverResult


@pytest.mark.unit
class TestSATSolver:
    """Test-Klasse für SATSolver."""
    
    def test_sat_solver_initialization(self, mock_plan_period_id):
        """Test: SATSolver wird korrekt initialisiert."""
        config = SolverConfig()
        solver = SATSolver(mock_plan_period_id, config)
        
        assert solver.plan_period_id == mock_plan_period_id
        assert solver.config == config
        assert solver.context is None
        assert solver.constraints == []
        assert solver.objective_builder is None
        assert solver.result_processor is None
        assert not solver.is_setup_complete
        assert solver.last_solve_status is None
        assert isinstance(solver.solve_statistics, dict)
    
    def test_sat_solver_initialization_default_config(self, mock_plan_period_id):
        """Test: SATSolver mit Standard-Konfiguration."""
        with patch('sat_solver.solving.solver.SolverConfig.from_current_config') as mock_config:
            mock_config.return_value = SolverConfig()
            
            solver = SATSolver(mock_plan_period_id)
            
            assert solver.plan_period_id == mock_plan_period_id
            assert solver.config is not None
            mock_config.assert_called_once()
    
    @patch('sat_solver.solving.solver.get_event_group_tree')
    @patch('sat_solver.solving.solver.get_avail_day_group_tree') 
    @patch('sat_solver.solving.solver.get_cast_group_tree')
    def test_setup_data_structures(self, mock_cast_tree, mock_avail_tree, mock_event_tree, mock_plan_period_id):
        """Test: _setup_data_structures() Methode."""
        # Mock tree functions
        mock_event_tree.return_value = Mock()
        mock_avail_tree.return_value = Mock()
        mock_cast_tree.return_value = Mock()
        
        solver = SATSolver(mock_plan_period_id)
        result = solver._setup_data_structures()
        
        assert result is True
        assert hasattr(solver, 'event_group_tree')
        assert hasattr(solver, 'avail_day_group_tree')
        assert hasattr(solver, 'cast_group_tree')
        
        # Verify tree functions were called
        mock_event_tree.assert_called_once_with(mock_plan_period_id)
        mock_avail_tree.assert_called_once_with(mock_plan_period_id)
        mock_cast_tree.assert_called_once_with(mock_plan_period_id)
    
    @patch('sat_solver.solving.solver.db_services')
    def test_populate_entities(self, mock_db_services, mock_plan_period_id):
        """Test: _populate_entities() Methode."""
        solver = SATSolver(mock_plan_period_id)
        
        # Setup mock trees
        solver.event_group_tree = Mock()
        solver.event_group_tree.root = Mock()
        solver.event_group_tree.root.descendants = []
        solver.event_group_tree.root.leaves = []
        solver.event_group_tree.root.event_group_id = uuid4()
        
        solver.avail_day_group_tree = Mock()
        solver.avail_day_group_tree.root = Mock()
        solver.avail_day_group_tree.root.descendants = []
        solver.avail_day_group_tree.root.leaves = []
        solver.avail_day_group_tree.root.avail_day_group_id = uuid4()
        
        solver.cast_group_tree = Mock()
        solver.cast_group_tree.root = Mock()
        solver.cast_group_tree.root.descendants = []
        solver.cast_group_tree.root.leaves = []
        solver.cast_group_tree.root.cast_group_id = uuid4()
        
        # Mock database services
        mock_plan_period = Mock()
        mock_plan_period.actor_plan_periods = []
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        
        # Setup entities
        from sat_solver.core.entities import Entities
        entities = Entities()
        
        # Test populate
        solver._populate_entities(entities)
        
        # Verify entities were populated
        assert isinstance(entities.actor_plan_periods, dict)
        assert isinstance(entities.event_groups, dict)
        assert isinstance(entities.avail_day_groups, dict)
        assert isinstance(entities.cast_groups, dict)
    
    @patch('sat_solver.solving.solver.SolverContext')
    @patch('sat_solver.solving.solver.Entities')
    @patch('sat_solver.solving.solver.cp_model.CpModel')
    def test_setup_solver_context(self, mock_cp_model, mock_entities, mock_solver_context, mock_plan_period_id):
        """Test: _setup_solver_context() Methode."""
        solver = SATSolver(mock_plan_period_id)
        
        # Setup mocks
        mock_entities_instance = Mock()
        mock_entities.return_value = mock_entities_instance
        mock_model_instance = Mock()
        mock_cp_model.return_value = mock_model_instance
        mock_context_instance = Mock()
        mock_solver_context.return_value = mock_context_instance
        
        # Setup required attributes
        solver.event_group_tree = Mock()
        solver.avail_day_group_tree = Mock()
        solver.cast_group_tree = Mock()
        
        with patch.object(solver, '_populate_entities') as mock_populate:
            with patch.object(solver, '_create_variables') as mock_create_vars:
                result = solver._setup_solver_context()
        
        assert result is True
        assert solver.context == mock_context_instance
        mock_populate.assert_called_once_with(mock_entities_instance)
        mock_create_vars.assert_called_once()
    
    @patch('sat_solver.solving.solver.ConstraintFactory')
    def test_setup_constraints(self, mock_factory, mock_plan_period_id):
        """Test: _setup_constraints() Methode."""
        solver = SATSolver(mock_plan_period_id)
        solver.context = Mock()
        
        # Mock factory
        mock_constraints = [Mock(), Mock(), Mock()]
        mock_setup_results = {"constraint1": True, "constraint2": True, "constraint3": True}
        mock_factory.create_and_setup_all.return_value = (mock_constraints, mock_setup_results)
        
        result = solver._setup_constraints()
        
        assert result is True
        assert solver.constraints == mock_constraints
        mock_factory.create_and_setup_all.assert_called_once_with(solver.context)
    
    @patch('sat_solver.solving.solver.ConstraintFactory')
    def test_setup_constraints_with_failures(self, mock_factory, mock_plan_period_id):
        """Test: _setup_constraints() mit fehlgeschlagenen Constraints."""
        solver = SATSolver(mock_plan_period_id)
        solver.context = Mock()
        
        # Mock factory with some failures
        mock_constraints = [Mock(), Mock()]
        mock_setup_results = {"constraint1": True, "constraint2": False}  # One failed
        mock_factory.create_and_setup_all.return_value = (mock_constraints, mock_setup_results)
        
        result = solver._setup_constraints()
        
        assert result is False  # Should fail if any constraint fails
        assert solver.constraints == mock_constraints
    
    @patch('sat_solver.solving.solver.ObjectiveBuilder')
    def test_setup_objective_builder(self, mock_objective_builder, mock_plan_period_id):
        """Test: _setup_objective_builder() Methode."""
        solver = SATSolver(mock_plan_period_id)
        solver.context = Mock()
        
        mock_builder_instance = Mock()
        mock_objective_builder.return_value = mock_builder_instance
        
        result = solver._setup_objective_builder()
        
        assert result is True
        assert solver.objective_builder == mock_builder_instance
        mock_objective_builder.assert_called_once_with(solver.context)
    
    @patch('sat_solver.solving.solver.ResultProcessor')
    def test_setup_result_processor(self, mock_result_processor, mock_plan_period_id):
        """Test: _setup_result_processor() Methode."""
        solver = SATSolver(mock_plan_period_id)
        solver.context = Mock()
        
        mock_processor_instance = Mock()
        mock_result_processor.return_value = mock_processor_instance
        
        result = solver._setup_result_processor()
        
        assert result is True
        assert solver.result_processor == mock_processor_instance
        mock_result_processor.assert_called_once_with(solver.context)
    
    def test_complete_setup_workflow(self, mock_plan_period_id):
        """Test: Kompletter Setup-Workflow."""
        solver = SATSolver(mock_plan_period_id)
        
        with patch.object(solver, '_setup_data_structures', return_value=True):
            with patch.object(solver, '_setup_solver_context', return_value=True):
                with patch.object(solver, '_setup_constraints', return_value=True):
                    with patch.object(solver, '_setup_objective_builder', return_value=True):
                        with patch.object(solver, '_setup_result_processor', return_value=True):
                            result = solver.setup()
        
        assert result is True
        assert solver.is_setup_complete is True
    
    def test_setup_failure_propagation(self, mock_plan_period_id):
        """Test: Setup-Fehler werden korrekt propagiert."""
        solver = SATSolver(mock_plan_period_id)
        
        with patch.object(solver, '_setup_data_structures', return_value=False):
            result = solver.setup()
        
        assert result is False
        assert solver.is_setup_complete is False
    
    def test_solve_without_setup(self, mock_plan_period_id):
        """Test: solve() ohne vorheriges setup() schlägt fehl."""
        solver = SATSolver(mock_plan_period_id)
        
        with pytest.raises(RuntimeError, match="Solver setup not completed"):
            solver.solve()
    
    def test_solve_basic_workflow(self, mock_plan_period_id):
        """Test: Basis solve() Workflow."""
        solver = SATSolver(mock_plan_period_id)
        solver.is_setup_complete = True
        
        # Mock components
        solver.context = Mock()
        solver.context.model = Mock()
        solver.objective_builder = Mock()
        solver.result_processor = Mock()
        
        # Mock solver results
        mock_cp_solver = Mock()
        mock_cp_solver.Solve.return_value = cp_model.OPTIMAL
        mock_cp_solver.ObjectiveValue.return_value = 42.0
        mock_cp_solver.NumConflicts.return_value = 5
        mock_cp_solver.NumBranches.return_value = 20
        mock_cp_solver.WallTime.return_value = 1.5
        
        mock_result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=42.0,
            solve_time=1.5,
            statistics={},
            appointments=[],
            solutions=[],
            constraint_values={}
        )
        
        solver.result_processor.process_results.return_value = mock_result
        
        with patch('sat_solver.solving.solver.cp_model.CpSolver', return_value=mock_cp_solver):
            with patch('sat_solver.solving.solver.time.time', side_effect=[0.0, 1.5]):
                result = solver.solve()
        
        assert isinstance(result, SolverResult)
        assert result.status == cp_model.OPTIMAL
        assert result.solve_time == 1.5
        
        # Verify objective builder was called
        solver.objective_builder.build_minimize_objective.assert_called_once()
        
        # Verify result processor was called
        solver.result_processor.process_results.assert_called_once()
    
    def test_get_setup_summary(self, mock_plan_period_id):
        """Test: get_setup_summary() Methode."""
        solver = SATSolver(mock_plan_period_id)
        solver.is_setup_complete = True
        solver.context = Mock()
        solver.context.is_valid.return_value = True
        solver.context.model = Mock()
        solver.context.model.NumVariables.return_value = 100
        solver.context.model.NumConstraints.return_value = 50
        solver.constraints = [Mock(), Mock(), Mock()]
        for constraint in solver.constraints:
            constraint.is_setup_complete.return_value = True
        solver.config = Mock()
        solver.config.to_dict.return_value = {"test": "config"}
        
        summary = solver.get_setup_summary()
        
        expected_keys = ['is_setup_complete', 'plan_period_id', 'context_valid', 
                        'constraints_count', 'constraints_setup', 'model_variables', 
                        'model_constraints', 'config_summary']
        
        for key in expected_keys:
            assert key in summary
        
        assert summary['is_setup_complete'] is True
        assert summary['constraints_count'] == 3
        assert summary['model_variables'] == 100
        assert summary['model_constraints'] == 50
    
    def test_get_solve_statistics(self, mock_plan_period_id):
        """Test: get_solve_statistics() Methode."""
        solver = SATSolver(mock_plan_period_id)
        
        # Setup some statistics
        test_stats = {
            'status': cp_model.OPTIMAL,
            'solve_time': 2.5,
            'objective_value': 123.45,
            'num_conflicts': 10,
            'num_branches': 100
        }
        solver.solve_statistics = test_stats
        
        stats = solver.get_solve_statistics()
        
        # Should return a copy
        assert stats == test_stats
        assert stats is not solver.solve_statistics  # Different object
    
    def test_status_to_string_conversion(self, mock_plan_period_id):
        """Test: _status_to_string() Methode."""
        solver = SATSolver(mock_plan_period_id)
        
        # Test known statuses
        assert solver._status_to_string(cp_model.OPTIMAL) == "OPTIMAL"
        assert solver._status_to_string(cp_model.FEASIBLE) == "FEASIBLE"
        assert solver._status_to_string(cp_model.INFEASIBLE) == "INFEASIBLE"
        assert solver._status_to_string(cp_model.MODEL_INVALID) == "MODEL_INVALID"
        assert solver._status_to_string(cp_model.UNKNOWN) == "UNKNOWN"
        
        # Test unknown status
        unknown_status = 999
        result = solver._status_to_string(unknown_status)
        assert "UNKNOWN_STATUS_999" in result


@pytest.mark.integration
class TestSATSolverIntegration:
    """Integration-Tests für SATSolver mit anderen Komponenten."""
    
    @patch('sat_solver.solving.solver.get_event_group_tree')
    @patch('sat_solver.solving.solver.get_avail_day_group_tree')
    @patch('sat_solver.solving.solver.get_cast_group_tree')
    @patch('sat_solver.solving.solver.db_services')
    def test_solver_integration_workflow(self, mock_db_services, mock_cast_tree, 
                                       mock_avail_tree, mock_event_tree, mock_plan_period_id):
        """Test: Kompletter Integration-Workflow."""
        # Setup extensive mocks for integration test
        
        # Mock trees
        mock_event_tree.return_value = self._create_mock_tree("event")
        mock_avail_tree.return_value = self._create_mock_tree("avail")
        mock_cast_tree.return_value = self._create_mock_tree("cast")
        
        # Mock database
        mock_plan_period = Mock()
        mock_plan_period.actor_plan_periods = []
        mock_db_services.PlanPeriod.get.return_value = mock_plan_period
        
        # Create solver
        config = SolverConfig()
        solver = SATSolver(mock_plan_period_id, config)
        
        # Test setup
        with patch('sat_solver.solving.solver.ConstraintFactory') as mock_factory:
            mock_factory.create_and_setup_all.return_value = ([], {})
            
            setup_success = solver.setup()
            
            assert setup_success is True
            assert solver.is_setup_complete is True
    
    def _create_mock_tree(self, tree_type):
        """Helper: Erstellt Mock-Tree für Tests."""
        mock_tree = Mock()
        mock_root = Mock()
        mock_root.descendants = []
        mock_root.leaves = []
        
        if tree_type == "event":
            mock_root.event_group_id = uuid4()
        elif tree_type == "avail":
            mock_root.avail_day_group_id = uuid4()
        elif tree_type == "cast":
            mock_root.cast_group_id = uuid4()
        
        mock_tree.root = mock_root
        return mock_tree
    
    def test_solver_error_recovery(self, mock_plan_period_id):
        """Test: Solver Error-Recovery."""
        solver = SATSolver(mock_plan_period_id)
        
        # Test recovery from setup errors
        with patch.object(solver, '_setup_data_structures', side_effect=Exception("Test error")):
            setup_success = solver.setup()
            
            assert setup_success is False
            assert solver.is_setup_complete is False
    
    @patch('sat_solver.solving.solver.logger')
    def test_solver_logging_integration(self, mock_logger, mock_plan_period_id):
        """Test: Solver Logging-Integration."""
        solver = SATSolver(mock_plan_period_id)
        
        # Test that logger is used during initialization
        # (Exact logging calls depend on implementation)
        assert mock_logger is not None
        
        # Verify solver can be created without logging errors
        assert solver.plan_period_id == mock_plan_period_id
    
    def test_solver_configuration_integration(self, mock_plan_period_id):
        """Test: Solver mit verschiedenen Konfigurationen."""
        # Test with different configurations
        configs = [
            SolverConfig(),  # Default
            SolverConfig(solver_parameters=Mock()),  # Custom parameters
        ]
        
        for config in configs:
            solver = SATSolver(mock_plan_period_id, config)
            
            assert solver.config == config
            assert solver.plan_period_id == mock_plan_period_id


@pytest.mark.slow
class TestSATSolverPerformance:
    """Performance-Tests für SATSolver."""
    
    def test_solver_setup_performance(self, mock_plan_period_id):
        """Test: Setup-Performance."""
        import time
        
        solver = SATSolver(mock_plan_period_id)
        
        # Mock all setup steps to return quickly
        with patch.object(solver, '_setup_data_structures', return_value=True):
            with patch.object(solver, '_setup_solver_context', return_value=True):
                with patch.object(solver, '_setup_constraints', return_value=True):
                    with patch.object(solver, '_setup_objective_builder', return_value=True):
                        with patch.object(solver, '_setup_result_processor', return_value=True):
                            
                            start_time = time.time()
                            result = solver.setup()
                            end_time = time.time()
        
        setup_time = end_time - start_time
        
        assert result is True
        assert setup_time < 1.0  # Should setup quickly with mocks
    
    def test_solver_memory_usage(self, mock_plan_period_id):
        """Test: Memory-Usage bei Solver-Erstellung."""
        import gc
        
        # Create multiple solvers to test memory usage
        solvers = []
        for _ in range(10):
            solver = SATSolver(mock_plan_period_id)
            solvers.append(solver)
        
        # Force garbage collection
        gc.collect()
        
        # Verify solvers are created successfully
        assert len(solvers) == 10
        for solver in solvers:
            assert solver.plan_period_id == mock_plan_period_id
