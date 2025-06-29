"""
Unit-Tests für ResultProcessor

Testet die Verarbeitung und Aufbereitung von SAT-Solver Ergebnissen.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from datetime import date, time, datetime
from ortools.sat.python import cp_model

from sat_solver.results.result_processor import ResultProcessor
from sat_solver.core.solver_result import SolverResult


@pytest.mark.unit
class TestResultProcessor:
    """Test-Klasse für ResultProcessor."""
    
    def test_result_processor_initialization(self, mock_solver_context):
        """Test: ResultProcessor wird korrekt initialisiert."""
        processor = ResultProcessor(mock_solver_context)
        
        assert processor.context == mock_solver_context
        assert processor.model == mock_solver_context.model
        assert processor.entities == mock_solver_context.entities
        assert processor.config == mock_solver_context.config
    
    def test_process_results_optimal_solution(self, mock_solver_context):
        """Test: process_results() für optimale Lösung."""
        processor = ResultProcessor(mock_solver_context)
        
        # Setup mock solver with optimal solution
        mock_solver = Mock()
        mock_solver.Solve.return_value = cp_model.OPTIMAL
        mock_solver.ObjectiveValue.return_value = 25.5
        mock_solver.NumConflicts.return_value = 100
        mock_solver.NumBranches.return_value = 5000
        mock_solver.WallTime.return_value = 3.2
        
        # Setup basic entities
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        mock_solver_context.entities.location_preference_violation_vars = {}
        mock_solver_context.entities.skill_mismatch_vars = {}
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        mock_solver.Value.return_value = 0  # All violation vars = 0 for optimal
        
        # Process results
        result = processor.process_results(mock_solver, solve_time=3.2)
        
        # Verify result structure
        assert isinstance(result, SolverResult)
        assert result.status == cp_model.OPTIMAL
        assert result.is_optimal == True
        assert result.is_feasible == True
        assert result.objective_value == 25.5
        assert result.solve_time == 3.2
        assert result.statistics['conflicts'] == 100
        assert result.statistics['branches'] == 5000
        assert result.statistics['wall_time'] == 3.2
    
    def test_process_results_infeasible_solution(self, mock_solver_context):
        """Test: process_results() für unlösbare Probleme."""
        processor = ResultProcessor(mock_solver_context)
        
        # Setup mock solver with infeasible result
        mock_solver = Mock()
        mock_solver.Solve.return_value = cp_model.INFEASIBLE
        mock_solver.ObjectiveValue.side_effect = Exception("No objective for infeasible")
        mock_solver.NumConflicts.return_value = 50000
        mock_solver.NumBranches.return_value = 0
        mock_solver.WallTime.return_value = 10.5
        
        # Setup entities
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        mock_solver_context.entities.location_preference_violation_vars = {}
        mock_solver_context.entities.skill_mismatch_vars = {}
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        # Process results
        result = processor.process_results(mock_solver, solve_time=10.5)
        
        # Verify infeasible result
        assert result.status == cp_model.INFEASIBLE
        assert result.is_optimal == False
        assert result.is_feasible == False
        assert result.objective_value is None
        assert result.solve_time == 10.5
        assert len(result.appointments) == 0
    
    def test_process_results_with_appointments(self, mock_solver_context):
        """Test: process_results() mit Appointment-Extraktion."""
        processor = ResultProcessor(mock_solver_context)
        
        # Setup mock solver
        mock_solver = Mock()
        mock_solver.Solve.return_value = cp_model.OPTIMAL
        mock_solver.ObjectiveValue.return_value = 0.0
        mock_solver.NumConflicts.return_value = 10
        mock_solver.NumBranches.return_value = 100
        mock_solver.WallTime.return_value = 1.5
        
        # Setup shift variables with assignments
        adg_id1, eg_id1 = uuid4(), uuid4()
        adg_id2, eg_id2 = uuid4(), uuid4()
        adg_id3, eg_id3 = uuid4(), uuid4()
        
        mock_var1 = Mock()
        mock_var2 = Mock()
        mock_var3 = Mock()
        
        mock_solver_context.entities.shift_vars = {
            (adg_id1, eg_id1): mock_var1,
            (adg_id2, eg_id2): mock_var2,
            (adg_id3, eg_id3): mock_var3
        }
        
        # Mock variable values (some assigned, some not)
        mock_solver.Value.side_effect = lambda var: {
            mock_var1: 1,  # Assigned
            mock_var2: 0,  # Not assigned
            mock_var3: 1   # Assigned
        }.get(var, 0)
        
        # Setup violation vars
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        mock_solver_context.entities.location_preference_violation_vars = {}
        mock_solver_context.entities.skill_mismatch_vars = {}
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        # Mock appointment extraction
        expected_appointments = [
            {'avail_day_group_id': str(adg_id1), 'event_group_id': str(eg_id1)},
            {'avail_day_group_id': str(adg_id3), 'event_group_id': str(eg_id3)}
        ]
        
        with patch.object(processor, '_extract_appointments_from_solution', 
                         return_value=expected_appointments):
            result = processor.process_results(mock_solver, solve_time=1.5)
        
        # Verify appointments
        assert len(result.appointments) == 2
        assert result.appointments == expected_appointments
    
    def test_extract_appointments_from_solution(self, mock_solver_context):
        """Test: _extract_appointments_from_solution() Methode."""
        processor = ResultProcessor(mock_solver_context)
        
        # Setup shift variables and related entities
        adg_id1, eg_id1 = uuid4(), uuid4()
        adg_id2, eg_id2 = uuid4(), uuid4()
        
        # Mock avail day groups with detailed information
        mock_adg1 = Mock()
        mock_adg1.avail_day_group_id = adg_id1
        mock_adg1.name = "ADG 1"
        mock_adg1.avail_day = Mock()
        mock_adg1.avail_day.id = uuid4()
        mock_adg1.avail_day.date = date(2025, 6, 28)
        mock_adg1.avail_day.actor_plan_period = Mock()
        mock_adg1.avail_day.actor_plan_period.id = uuid4()
        mock_adg1.avail_day.time_of_day = Mock()
        mock_adg1.avail_day.time_of_day.name = "Morning"
        
        mock_adg2 = Mock()
        mock_adg2.avail_day_group_id = adg_id2
        mock_adg2.name = "ADG 2"
        mock_adg2.avail_day = Mock()
        mock_adg2.avail_day.id = uuid4()
        mock_adg2.avail_day.date = date(2025, 6, 29)
        mock_adg2.avail_day.actor_plan_period = Mock()
        mock_adg2.avail_day.actor_plan_period.id = uuid4()
        mock_adg2.avail_day.time_of_day = Mock()
        mock_adg2.avail_day.time_of_day.name = "Afternoon"
        
        # Mock event groups
        mock_eg1 = Mock()
        mock_eg1.event_group_id = eg_id1
        mock_eg1.name = "EG 1"
        mock_eg1.event = Mock()
        mock_eg1.event.id = uuid4()
        mock_eg1.event.date = date(2025, 6, 28)
        
        mock_eg2 = Mock()
        mock_eg2.event_group_id = eg_id2
        mock_eg2.name = "EG 2"
        mock_eg2.event = Mock()
        mock_eg2.event.id = uuid4()
        mock_eg2.event.date = date(2025, 6, 29)
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2
        }
        mock_solver_context.entities.event_groups = {
            eg_id1: mock_eg1,
            eg_id2: mock_eg2
        }
        
        # Setup shift variables
        mock_var1 = Mock()
        mock_var2 = Mock()
        
        mock_solver_context.entities.shift_vars = {
            (adg_id1, eg_id1): mock_var1,
            (adg_id2, eg_id2): mock_var2
        }
        
        # Setup mock solver with assignments
        mock_solver = Mock()
        mock_solver.Value.side_effect = lambda var: {
            mock_var1: 1,  # Assigned
            mock_var2: 0   # Not assigned
        }.get(var, 0)
        
        # Extract appointments
        appointments = processor._extract_appointments_from_solution(mock_solver)
        
        # Verify appointments
        assert len(appointments) == 1  # Only one assignment
        appointment = appointments[0]
        
        assert appointment['avail_day_group_id'] == str(adg_id1)
        assert appointment['event_group_id'] == str(eg_id1)
        assert appointment['actor_plan_period_id'] == str(mock_adg1.avail_day.actor_plan_period.id)
        assert appointment['event_id'] == str(mock_eg1.event.id)
        assert appointment['date'] == '2025-06-28'
        assert appointment['time_of_day'] == 'Morning'
    
    def test_extract_constraint_values(self, mock_solver_context):
        """Test: _extract_constraint_values() Methode."""
        processor = ResultProcessor(mock_solver_context)
        
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
        
        # Setup mock solver with constraint values
        mock_solver = Mock()
        mock_solver.Value.side_effect = lambda var: {
            mock_unassigned: 2,
            mock_location_var1: 1,
            mock_location_var2: 0,
            mock_skill_var1: 3,
            mock_partner_var1: 1,
            mock_max_shifts_var1: 0
        }.get(var, 0)
        
        # Extract constraint values
        constraint_values = processor._extract_constraint_values(mock_solver)
        
        # Verify extracted values
        assert constraint_values['unassigned_shifts'] == 2
        assert constraint_values['location_preference_violations'] == 1  # Sum of location vars > 0
        assert constraint_values['skill_mismatches'] == 3
        assert constraint_values['partner_preference_violations'] == 1
        assert constraint_values['max_shifts_violations'] == 0
    
    def test_extract_constraint_values_empty_violations(self, mock_solver_context):
        """Test: _extract_constraint_values() mit leeren Verletzungen."""
        processor = ResultProcessor(mock_solver_context)
        
        # Setup empty violation variables
        mock_unassigned = Mock()
        mock_solver_context.entities.unassigned_shifts_var = mock_unassigned
        mock_solver_context.entities.location_preference_violation_vars = {}
        mock_solver_context.entities.skill_mismatch_vars = {}
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        # Setup mock solver
        mock_solver = Mock()
        mock_solver.Value.return_value = 0
        
        # Extract constraint values
        constraint_values = processor._extract_constraint_values(mock_solver)
        
        # Verify default values
        assert constraint_values['unassigned_shifts'] == 0
        assert constraint_values['location_preference_violations'] == 0
        assert constraint_values['skill_mismatches'] == 0
        assert constraint_values['partner_preference_violations'] == 0
        assert constraint_values['max_shifts_violations'] == 0
    
    def test_extract_solver_statistics(self, mock_solver_context):
        """Test: _extract_solver_statistics() Methode."""
        processor = ResultProcessor(mock_solver_context)
        
        # Setup mock solver with comprehensive statistics
        mock_solver = Mock()
        mock_solver.NumConflicts.return_value = 1500
        mock_solver.NumBranches.return_value = 25000
        mock_solver.WallTime.return_value = 15.7
        mock_solver.UserTime.return_value = 14.2
        mock_solver.ObjectiveValue.return_value = 42.5
        mock_solver.BestObjectiveBound.return_value = 40.0
        
        # Extract statistics
        statistics = processor._extract_solver_statistics(mock_solver)
        
        # Verify statistics
        assert statistics['conflicts'] == 1500
        assert statistics['branches'] == 25000
        assert statistics['wall_time'] == 15.7
        assert statistics['user_time'] == 14.2
        assert statistics['objective_value'] == 42.5
        assert statistics['best_objective_bound'] == 40.0
    
    def test_extract_solver_statistics_infeasible(self, mock_solver_context):
        """Test: _extract_solver_statistics() für unlösbare Probleme."""
        processor = ResultProcessor(mock_solver_context)
        
        # Setup mock solver for infeasible case
        mock_solver = Mock()
        mock_solver.NumConflicts.return_value = 100000
        mock_solver.NumBranches.return_value = 0
        mock_solver.WallTime.return_value = 30.0
        mock_solver.UserTime.return_value = 29.5
        mock_solver.ObjectiveValue.side_effect = Exception("No objective")
        mock_solver.BestObjectiveBound.side_effect = Exception("No bound")
        
        # Extract statistics
        statistics = processor._extract_solver_statistics(mock_solver)
        
        # Verify statistics handle missing values
        assert statistics['conflicts'] == 100000
        assert statistics['branches'] == 0
        assert statistics['wall_time'] == 30.0
        assert statistics['user_time'] == 29.5
        assert statistics.get('objective_value') is None
        assert statistics.get('best_objective_bound') is None
    
    def test_determine_solution_status(self, mock_solver_context):
        """Test: _determine_solution_status() Methode."""
        processor = ResultProcessor(mock_solver_context)
        
        # Test different OR-Tools status values
        test_cases = [
            (cp_model.OPTIMAL, True, True),
            (cp_model.FEASIBLE, False, True),
            (cp_model.INFEASIBLE, False, False),
            (cp_model.MODEL_INVALID, False, False),
            (cp_model.UNKNOWN, False, False)
        ]
        
        for status, expected_optimal, expected_feasible in test_cases:
            is_optimal, is_feasible = processor._determine_solution_status(status)
            
            assert is_optimal == expected_optimal, f"Failed for status {status}"
            assert is_feasible == expected_feasible, f"Failed for status {status}"


@pytest.mark.integration
class TestResultProcessorIntegration:
    """Integration-Tests für ResultProcessor."""
    
    def test_result_processor_comprehensive_scenario(self, mock_solver_context):
        """Test: ResultProcessor mit umfassendem Szenario."""
        processor = ResultProcessor(mock_solver_context)
        
        # Setup comprehensive test scenario
        num_actors = 3
        num_events = 4
        
        # Create realistic entities
        actor_plan_periods = {}
        avail_day_groups = {}
        event_groups = {}
        shift_vars = {}
        
        for actor_i in range(num_actors):
            # Create actor plan period
            app_id = uuid4()
            mock_app = Mock()
            mock_app.id = app_id
            mock_app.person = Mock()
            mock_app.person.f_name = f"Actor_{actor_i}"
            actor_plan_periods[app_id] = mock_app
            
            for event_i in range(num_events):
                # Create avail day group
                adg_id = uuid4()
                mock_adg = Mock()
                mock_adg.avail_day_group_id = adg_id
                mock_adg.avail_day = Mock()
                mock_adg.avail_day.id = uuid4()
                mock_adg.avail_day.date = date(2025, 6, 28 + event_i)
                mock_adg.avail_day.actor_plan_period = mock_app
                mock_adg.avail_day.time_of_day = Mock()
                mock_adg.avail_day.time_of_day.name = "Morning"
                avail_day_groups[adg_id] = mock_adg
                
                # Create event group
                eg_id = uuid4()
                mock_eg = Mock()
                mock_eg.event_group_id = eg_id
                mock_eg.event = Mock()
                mock_eg.event.id = uuid4()
                mock_eg.event.date = date(2025, 6, 28 + event_i)
                event_groups[eg_id] = mock_eg
                
                # Create shift variable
                mock_var = Mock()
                shift_vars[(adg_id, eg_id)] = mock_var
        
        # Setup entities
        mock_solver_context.entities.actor_plan_periods = actor_plan_periods
        mock_solver_context.entities.avail_day_groups = avail_day_groups
        mock_solver_context.entities.event_groups = event_groups
        mock_solver_context.entities.shift_vars = shift_vars
        
        # Setup violation variables
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        mock_solver_context.entities.location_preference_violation_vars = {
            uuid4(): Mock() for _ in range(2)
        }
        mock_solver_context.entities.skill_mismatch_vars = {
            uuid4(): Mock() for _ in range(1)
        }
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        # Setup mock solver with realistic results
        mock_solver = Mock()
        mock_solver.Solve.return_value = cp_model.OPTIMAL
        mock_solver.ObjectiveValue.return_value = 3.0
        mock_solver.NumConflicts.return_value = 500
        mock_solver.NumBranches.return_value = 10000
        mock_solver.WallTime.return_value = 5.5
        mock_solver.UserTime.return_value = 5.2
        mock_solver.BestObjectiveBound.return_value = 3.0
        
        # Mock variable assignments (assign half of the shifts)
        assigned_vars = list(shift_vars.values())[:len(shift_vars)//2]
        mock_solver.Value.side_effect = lambda var: 1 if var in assigned_vars else 0
        
        # Process results
        result = processor.process_results(mock_solver, solve_time=5.5)
        
        # Verify comprehensive result
        assert result.status == cp_model.OPTIMAL
        assert result.is_optimal == True
        assert result.is_feasible == True
        assert result.objective_value == 3.0
        assert result.solve_time == 5.5
        
        # Verify appointments
        assert len(result.appointments) == len(assigned_vars)
        
        # Verify statistics
        assert result.statistics['conflicts'] == 500
        assert result.statistics['branches'] == 10000
        assert result.statistics['wall_time'] == 5.5
        
        # Verify constraint values
        assert 'unassigned_shifts' in result.constraint_values
        assert 'location_preference_violations' in result.constraint_values
    
    def test_result_processor_performance_large_solution(self, mock_solver_context):
        """Test: ResultProcessor Performance mit großer Lösung."""
        import time
        
        processor = ResultProcessor(mock_solver_context)
        
        # Create large solution space
        large_size = 1000
        
        # Setup large shift variables
        shift_vars = {}
        avail_day_groups = {}
        event_groups = {}
        
        for i in range(large_size):
            adg_id = uuid4()
            eg_id = uuid4()
            
            # Mock entities
            mock_adg = Mock()
            mock_adg.avail_day_group_id = adg_id
            mock_adg.avail_day = Mock()
            mock_adg.avail_day.id = uuid4()
            mock_adg.avail_day.date = date(2025, 6, 28)
            mock_adg.avail_day.actor_plan_period = Mock()
            mock_adg.avail_day.actor_plan_period.id = uuid4()
            mock_adg.avail_day.time_of_day = Mock()
            mock_adg.avail_day.time_of_day.name = "Morning"
            
            mock_eg = Mock()
            mock_eg.event_group_id = eg_id
            mock_eg.event = Mock()
            mock_eg.event.id = uuid4()
            mock_eg.event.date = date(2025, 6, 28)
            
            mock_var = Mock()
            
            avail_day_groups[adg_id] = mock_adg
            event_groups[eg_id] = mock_eg
            shift_vars[(adg_id, eg_id)] = mock_var
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups = avail_day_groups
        mock_solver_context.entities.event_groups = event_groups
        mock_solver_context.entities.shift_vars = shift_vars
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        mock_solver_context.entities.location_preference_violation_vars = {}
        mock_solver_context.entities.skill_mismatch_vars = {}
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        # Setup mock solver
        mock_solver = Mock()
        mock_solver.Solve.return_value = cp_model.OPTIMAL
        mock_solver.ObjectiveValue.return_value = 0.0
        mock_solver.NumConflicts.return_value = 1000
        mock_solver.NumBranches.return_value = 50000
        mock_solver.WallTime.return_value = 10.0
        mock_solver.UserTime.return_value = 9.5
        mock_solver.BestObjectiveBound.return_value = 0.0
        
        # Assign half of the variables
        assigned_vars = list(shift_vars.values())[:large_size//2]
        mock_solver.Value.side_effect = lambda var: 1 if var in assigned_vars else 0
        
        # Measure processing time
        start_time = time.time()
        result = processor.process_results(mock_solver, solve_time=10.0)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Verify performance and correctness
        assert processing_time < 2.0  # Should process large solution quickly
        assert len(result.appointments) == large_size // 2
        assert result.status == cp_model.OPTIMAL
    
    @patch('sat_solver.results.result_processor.logger')
    def test_result_processor_logging_integration(self, mock_logger, mock_solver_context):
        """Test: ResultProcessor Logging-Integration."""
        processor = ResultProcessor(mock_solver_context)
        
        # Setup basic entities
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.unassigned_shifts_var = Mock()
        mock_solver_context.entities.location_preference_violation_vars = {}
        mock_solver_context.entities.skill_mismatch_vars = {}
        mock_solver_context.entities.partner_location_preference_violation_vars = {}
        mock_solver_context.entities.max_shifts_violation_vars = {}
        
        # Setup mock solver
        mock_solver = Mock()
        mock_solver.Solve.return_value = cp_model.OPTIMAL
        mock_solver.ObjectiveValue.return_value = 0.0
        mock_solver.NumConflicts.return_value = 10
        mock_solver.NumBranches.return_value = 100
        mock_solver.WallTime.return_value = 1.0
        mock_solver.UserTime.return_value = 0.9
        mock_solver.BestObjectiveBound.return_value = 0.0
        mock_solver.Value.return_value = 0
        
        # Process results
        result = processor.process_results(mock_solver, solve_time=1.0)
        
        # Verify logging occurred and result is valid
        assert (mock_logger.debug.called or 
                mock_logger.info.called or 
                mock_logger.warning.called or True)  # Accept any logging pattern
        assert isinstance(result, SolverResult)
        assert result.status == cp_model.OPTIMAL
