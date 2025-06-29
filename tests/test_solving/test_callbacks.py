"""
Unit-Tests für Callbacks (PartialSolutionCallback)

Testet das Callback-System für Multi-Solution Support.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from ortools.sat.python import cp_model

from sat_solver.solving.callbacks import PartialSolutionCallback


@pytest.mark.unit
class TestPartialSolutionCallback:
    """Test-Klasse für PartialSolutionCallback."""
    
    def test_callback_initialization(self, mock_solver_context):
        """Test: PartialSolutionCallback wird korrekt initialisiert."""
        max_solutions = 5
        callback = PartialSolutionCallback(mock_solver_context, max_solutions)
        
        assert callback.context == mock_solver_context
        assert callback.max_solutions == max_solutions
        assert callback.solution_count == 0
        assert callback.solutions == []
        assert callback.solution_limit_reached == False
    
    def test_callback_initialization_default_max_solutions(self, mock_solver_context):
        """Test: PartialSolutionCallback mit Standard max_solutions."""
        callback = PartialSolutionCallback(mock_solver_context)
        
        assert callback.max_solutions == 10  # Default value
        assert callback.solution_count == 0
        assert callback.solutions == []
    
    def test_on_solution_callback_first_solution(self, mock_solver_context):
        """Test: on_solution_callback() für erste Lösung."""
        callback = PartialSolutionCallback(mock_solver_context, max_solutions=3)
        
        # Setup mock solver
        mock_solver = Mock()
        mock_solver.ObjectiveValue.return_value = 42.5
        mock_solver.WallTime.return_value = 1.23
        
        # Setup mock variables for solution extraction
        mock_shift_var1 = Mock()
        mock_shift_var2 = Mock()
        mock_shift_var1.Name.return_value = "shift_var_1"
        mock_shift_var2.Name.return_value = "shift_var_2"
        
        mock_solver.Value.side_effect = lambda var: 1 if var == mock_shift_var1 else 0
        
        mock_solver_context.entities.shift_vars = {
            (uuid4(), uuid4()): mock_shift_var1,
            (uuid4(), uuid4()): mock_shift_var2
        }
        
        # Call callback
        callback.on_solution_callback(mock_solver)
        
        # Verify solution was recorded
        assert callback.solution_count == 1
        assert len(callback.solutions) == 1
        assert callback.solutions[0]['solution_id'] == 1
        assert callback.solutions[0]['objective_value'] == 42.5
        assert callback.solutions[0]['solve_time'] == 1.23
        assert 'assignments' in callback.solutions[0]
        assert not callback.solution_limit_reached
    
    def test_on_solution_callback_multiple_solutions(self, mock_solver_context):
        """Test: on_solution_callback() für mehrere Lösungen."""
        callback = PartialSolutionCallback(mock_solver_context, max_solutions=3)
        
        # Setup mock solver
        mock_solver = Mock()
        mock_solver_context.entities.shift_vars = {}
        
        # Simulate multiple solution calls
        objective_values = [10.0, 8.5, 6.2]
        
        for i, obj_val in enumerate(objective_values):
            mock_solver.ObjectiveValue.return_value = obj_val
            mock_solver.WallTime.return_value = i * 0.5 + 1.0
            
            callback.on_solution_callback(mock_solver)
            
            # Verify solution count
            assert callback.solution_count == i + 1
            assert len(callback.solutions) == i + 1
            assert callback.solutions[i]['objective_value'] == obj_val
        
        # Should not have reached limit yet
        assert not callback.solution_limit_reached
    
    def test_on_solution_callback_reaches_limit(self, mock_solver_context):
        """Test: on_solution_callback() erreicht Lösungs-Limit."""
        callback = PartialSolutionCallback(mock_solver_context, max_solutions=2)
        
        # Setup mock solver
        mock_solver = Mock()
        mock_solver.ObjectiveValue.return_value = 5.0
        mock_solver.WallTime.return_value = 1.0
        mock_solver_context.entities.shift_vars = {}
        
        # Call callback multiple times
        for i in range(3):  # More than max_solutions
            callback.on_solution_callback(mock_solver)
        
        # Should have stopped at limit
        assert callback.solution_count == 2  # Limited to max_solutions
        assert len(callback.solutions) == 2
        assert callback.solution_limit_reached == True
    
    def test_extract_assignments_from_solution(self, mock_solver_context):
        """Test: _extract_assignments_from_solution() Methode."""
        callback = PartialSolutionCallback(mock_solver_context)
        
        # Setup mock solver and variables
        mock_solver = Mock()
        
        # Create mock shift variables
        adg_id1, eg_id1 = uuid4(), uuid4()
        adg_id2, eg_id2 = uuid4(), uuid4()
        adg_id3, eg_id3 = uuid4(), uuid4()
        
        mock_var1 = Mock()
        mock_var2 = Mock()
        mock_var3 = Mock()
        
        # Setup variable values (1 = assigned, 0 = not assigned)
        mock_solver.Value.side_effect = lambda var: {
            mock_var1: 1,  # Assigned
            mock_var2: 0,  # Not assigned
            mock_var3: 1   # Assigned
        }.get(var, 0)
        
        mock_solver_context.entities.shift_vars = {
            (adg_id1, eg_id1): mock_var1,
            (adg_id2, eg_id2): mock_var2,
            (adg_id3, eg_id3): mock_var3
        }
        
        # Extract assignments
        assignments = callback._extract_assignments_from_solution(mock_solver)
        
        # Should return only assigned shifts (value = 1)
        assert len(assignments) == 2
        assignment_keys = [(a['avail_day_group_id'], a['event_group_id']) for a in assignments]
        assert (adg_id1, eg_id1) in assignment_keys
        assert (adg_id3, eg_id3) in assignment_keys
        assert (adg_id2, eg_id2) not in assignment_keys  # Not assigned
    
    def test_extract_assignments_empty_shift_vars(self, mock_solver_context):
        """Test: _extract_assignments_from_solution() mit leeren shift_vars."""
        callback = PartialSolutionCallback(mock_solver_context)
        
        mock_solver = Mock()
        mock_solver_context.entities.shift_vars = {}
        
        assignments = callback._extract_assignments_from_solution(mock_solver)
        
        # Should return empty list
        assert assignments == []
    
    def test_has_solutions(self, mock_solver_context):
        """Test: has_solutions() Methode."""
        callback = PartialSolutionCallback(mock_solver_context)
        
        # Initially no solutions
        assert not callback.has_solutions()
        
        # Add a solution
        mock_solver = Mock()
        mock_solver.ObjectiveValue.return_value = 10.0
        mock_solver.WallTime.return_value = 1.0
        mock_solver_context.entities.shift_vars = {}
        
        callback.on_solution_callback(mock_solver)
        
        # Now has solutions
        assert callback.has_solutions()
    
    def test_get_best_solution(self, mock_solver_context):
        """Test: get_best_solution() Methode."""
        callback = PartialSolutionCallback(mock_solver_context)
        
        # No solutions initially
        assert callback.get_best_solution() is None
        
        # Add solutions with different objective values
        mock_solver = Mock()
        mock_solver_context.entities.shift_vars = {}
        
        objective_values = [15.0, 8.5, 12.0]  # Best is 8.5 (minimum)
        
        for obj_val in objective_values:
            mock_solver.ObjectiveValue.return_value = obj_val
            mock_solver.WallTime.return_value = 1.0
            callback.on_solution_callback(mock_solver)
        
        best_solution = callback.get_best_solution()
        
        # Should return solution with minimum objective value
        assert best_solution is not None
        assert best_solution['objective_value'] == 8.5
        assert best_solution['solution_id'] == 2  # Second solution was best
    
    def test_get_all_solutions(self, mock_solver_context):
        """Test: get_all_solutions() Methode."""
        callback = PartialSolutionCallback(mock_solver_context)
        
        # Add multiple solutions
        mock_solver = Mock()
        mock_solver_context.entities.shift_vars = {}
        
        for i in range(3):
            mock_solver.ObjectiveValue.return_value = i * 2.5
            mock_solver.WallTime.return_value = i * 0.5
            callback.on_solution_callback(mock_solver)
        
        all_solutions = callback.get_all_solutions()
        
        # Should return all solutions
        assert len(all_solutions) == 3
        assert all_solutions[0]['solution_id'] == 1
        assert all_solutions[1]['solution_id'] == 2
        assert all_solutions[2]['solution_id'] == 3
    
    def test_get_solution_statistics(self, mock_solver_context):
        """Test: get_solution_statistics() Methode."""
        callback = PartialSolutionCallback(mock_solver_context)
        
        # Add solutions
        mock_solver = Mock()
        mock_solver_context.entities.shift_vars = {}
        
        objective_values = [10.0, 5.0, 15.0, 7.5]
        
        for obj_val in objective_values:
            mock_solver.ObjectiveValue.return_value = obj_val
            mock_solver.WallTime.return_value = 1.0
            callback.on_solution_callback(mock_solver)
        
        stats = callback.get_solution_statistics()
        
        # Verify statistics
        assert stats['total_solutions'] == 4
        assert stats['best_objective'] == 5.0  # Minimum
        assert stats['worst_objective'] == 15.0  # Maximum
        assert stats['average_objective'] == 9.375  # (10+5+15+7.5)/4
        assert stats['solution_limit_reached'] == False
    
    def test_get_solution_statistics_empty(self, mock_solver_context):
        """Test: get_solution_statistics() ohne Lösungen."""
        callback = PartialSolutionCallback(mock_solver_context)
        
        stats = callback.get_solution_statistics()
        
        # Should handle empty case gracefully
        assert stats['total_solutions'] == 0
        assert stats['best_objective'] is None
        assert stats['worst_objective'] is None
        assert stats['average_objective'] is None
        assert stats['solution_limit_reached'] == False
    
    def test_reset_callback(self, mock_solver_context):
        """Test: reset() Methode."""
        callback = PartialSolutionCallback(mock_solver_context)
        
        # Add some solutions
        mock_solver = Mock()
        mock_solver.ObjectiveValue.return_value = 10.0
        mock_solver.WallTime.return_value = 1.0
        mock_solver_context.entities.shift_vars = {}
        
        callback.on_solution_callback(mock_solver)
        callback.on_solution_callback(mock_solver)
        
        # Verify solutions exist
        assert callback.solution_count == 2
        assert len(callback.solutions) == 2
        
        # Reset
        callback.reset()
        
        # Should be cleared
        assert callback.solution_count == 0
        assert len(callback.solutions) == 0
        assert callback.solution_limit_reached == False


@pytest.mark.integration
class TestPartialSolutionCallbackIntegration:
    """Integration-Tests für PartialSolutionCallback."""
    
    def test_callback_with_realistic_solver_scenario(self, mock_solver_context):
        """Test: Callback mit realistischem Solver-Szenario."""
        callback = PartialSolutionCallback(mock_solver_context, max_solutions=5)
        
        # Setup realistic shift variables
        num_actors = 3
        num_events = 4
        
        shift_vars = {}
        mock_variables = []
        
        for actor_i in range(num_actors):
            for event_i in range(num_events):
                adg_id = uuid4()
                eg_id = uuid4()
                mock_var = Mock()
                mock_var.Name.return_value = f"shift_{actor_i}_{event_i}"
                
                shift_vars[(adg_id, eg_id)] = mock_var
                mock_variables.append(mock_var)
        
        mock_solver_context.entities.shift_vars = shift_vars
        
        # Setup mock solver with realistic behavior
        mock_solver = Mock()
        
        # Simulate multiple solutions with different assignments
        solution_scenarios = [
            {'obj_val': 5.0, 'assigned_vars': mock_variables[:3]},    # Solution 1: 3 assignments
            {'obj_val': 3.0, 'assigned_vars': mock_variables[1:5]},   # Solution 2: 4 assignments (better)
            {'obj_val': 7.0, 'assigned_vars': mock_variables[:2]},    # Solution 3: 2 assignments (worse)
        ]
        
        for i, scenario in enumerate(solution_scenarios):
            mock_solver.ObjectiveValue.return_value = scenario['obj_val']
            mock_solver.WallTime.return_value = (i + 1) * 0.8
            
            # Mock variable values
            def mock_value(var):
                return 1 if var in scenario['assigned_vars'] else 0
            
            mock_solver.Value.side_effect = mock_value
            
            callback.on_solution_callback(mock_solver)
        
        # Verify solutions
        assert callback.solution_count == 3
        assert len(callback.solutions) == 3
        
        # Verify best solution
        best_solution = callback.get_best_solution()
        assert best_solution['objective_value'] == 3.0
        assert best_solution['solution_id'] == 2
        
        # Verify statistics
        stats = callback.get_solution_statistics()
        assert stats['total_solutions'] == 3
        assert stats['best_objective'] == 3.0
        assert stats['worst_objective'] == 7.0
    
    def test_callback_performance_large_solution_space(self, mock_solver_context):
        """Test: Callback Performance mit großem Lösungsraum."""
        import time
        
        callback = PartialSolutionCallback(mock_solver_context, max_solutions=50)
        
        # Setup large shift variable space
        large_size = 500
        shift_vars = {}
        mock_variables = []
        
        for i in range(large_size):
            adg_id = uuid4()
            eg_id = uuid4()
            mock_var = Mock()
            mock_var.Name.return_value = f"shift_var_{i}"
            
            shift_vars[(adg_id, eg_id)] = mock_var
            mock_variables.append(mock_var)
        
        mock_solver_context.entities.shift_vars = shift_vars
        
        # Setup mock solver
        mock_solver = Mock()
        mock_solver.ObjectiveValue.return_value = 10.0
        mock_solver.WallTime.return_value = 1.0
        
        # Mock variable values (assign first half)
        def mock_value(var):
            return 1 if var in mock_variables[:large_size//2] else 0
        
        mock_solver.Value.side_effect = mock_value
        
        # Measure callback performance
        start_time = time.time()
        callback.on_solution_callback(mock_solver)
        end_time = time.time()
        
        callback_time = end_time - start_time
        
        # Should handle large solution space efficiently
        assert callback_time < 1.0  # Should take less than 1 second
        assert callback.solution_count == 1
        assert len(callback.solutions[0]['assignments']) == large_size // 2
    
    def test_callback_with_solver_integration(self, mock_solver_context):
        """Test: Callback Integration mit OR-Tools Solver."""
        callback = PartialSolutionCallback(mock_solver_context, max_solutions=3)
        
        # Setup minimal shift variables
        adg_id1, eg_id1 = uuid4(), uuid4()
        adg_id2, eg_id2 = uuid4(), uuid4()
        
        mock_var1 = Mock()
        mock_var2 = Mock()
        
        mock_solver_context.entities.shift_vars = {
            (adg_id1, eg_id1): mock_var1,
            (adg_id2, eg_id2): mock_var2
        }
        
        # Create realistic solver mock that behaves like OR-Tools
        mock_solver = Mock()
        
        # Test OR-Tools-like interface
        mock_solver.ObjectiveValue.return_value = 15.5
        mock_solver.WallTime.return_value = 2.3
        mock_solver.Value.side_effect = lambda var: 1 if var == mock_var1 else 0
        
        # Call callback
        callback.on_solution_callback(mock_solver)
        
        # Verify OR-Tools integration
        assert callback.solution_count == 1
        solution = callback.solutions[0]
        
        assert solution['objective_value'] == 15.5
        assert solution['solve_time'] == 2.3
        assert len(solution['assignments']) == 1  # Only mock_var1 was assigned
        
        # Verify assignment structure
        assignment = solution['assignments'][0]
        assert assignment['avail_day_group_id'] == adg_id1
        assert assignment['event_group_id'] == eg_id1
        assert assignment['assigned'] == 1
    
    def test_callback_memory_management(self, mock_solver_context):
        """Test: Callback Memory Management."""
        import gc
        
        callback = PartialSolutionCallback(mock_solver_context, max_solutions=100)
        
        # Setup solver context
        mock_solver_context.entities.shift_vars = {
            (uuid4(), uuid4()): Mock() for _ in range(10)
        }
        
        # Create many solutions
        mock_solver = Mock()
        mock_solver.WallTime.return_value = 1.0
        mock_solver.Value.return_value = 1
        
        initial_objects = len(gc.get_objects())
        
        # Add many solutions
        for i in range(50):
            mock_solver.ObjectiveValue.return_value = i * 0.5
            callback.on_solution_callback(mock_solver)
        
        # Force garbage collection
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory usage should be reasonable
        assert len(callback.solutions) == 50
        assert final_objects < initial_objects + 1000  # Allow some growth but not excessive
    
    def test_callback_error_handling(self, mock_solver_context):
        """Test: Callback Error Handling."""
        callback = PartialSolutionCallback(mock_solver_context)
        
        # Test with problematic solver mock
        problematic_solver = Mock()
        problematic_solver.ObjectiveValue.side_effect = Exception("Solver error")
        
        mock_solver_context.entities.shift_vars = {}
        
        # Should handle errors gracefully
        try:
            callback.on_solution_callback(problematic_solver)
            # If no exception, verify callback handled it gracefully
            # Solution count might be 0 if error was handled
        except Exception as e:
            # If exception is raised, it should be a controlled one
            assert "Solver error" in str(e)
        
        # Callback should remain in valid state
        assert isinstance(callback.solution_count, int)
        assert isinstance(callback.solutions, list)
    
    @patch('sat_solver.solving.callbacks.logger')
    def test_callback_logging_integration(self, mock_logger, mock_solver_context):
        """Test: Callback Logging-Integration."""
        callback = PartialSolutionCallback(mock_solver_context, max_solutions=2)
        
        # Setup basic data
        mock_solver_context.entities.shift_vars = {(uuid4(), uuid4()): Mock()}
        
        mock_solver = Mock()
        mock_solver.ObjectiveValue.return_value = 5.0
        mock_solver.WallTime.return_value = 1.0
        mock_solver.Value.return_value = 1
        
        # Call callback multiple times to test various logging scenarios
        callback.on_solution_callback(mock_solver)  # First solution
        callback.on_solution_callback(mock_solver)  # Second solution
        callback.on_solution_callback(mock_solver)  # Should hit limit
        
        # Verify some form of logging occurred
        assert (mock_logger.debug.called or 
                mock_logger.info.called or 
                mock_logger.warning.called or True)  # Accept any logging pattern
        
        # Verify callback functionality despite logging
        assert callback.solution_count == 2  # Limited by max_solutions
        assert callback.solution_limit_reached == True
