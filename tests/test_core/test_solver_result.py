"""
Unit-Tests für SolverResult-Datenklasse

Testet die strukturierte Datenklasse für SAT-Solver Ergebnisse.
"""

import pytest
from datetime import datetime
from ortools.sat.python import cp_model

from sat_solver.core.solver_result import SolverResult


@pytest.mark.unit
class TestSolverResult:
    """Test-Klasse für SolverResult."""
    
    def test_solver_result_initialization_optimal(self):
        """Test: SolverResult initialisiert korrekt für optimale Lösung."""
        result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=42.5,
            solve_time=1.23,
            statistics={'conflicts': 5, 'branches': 100},
            appointments=[],
            solutions=[],
            constraint_values={'unassigned_shifts': 0}
        )
        
        assert result.status == cp_model.OPTIMAL
        assert result.is_optimal is True
        assert result.is_feasible is True
        assert result.objective_value == 42.5
        assert result.solve_time == 1.23
        assert result.statistics == {'conflicts': 5, 'branches': 100}
        assert result.appointments == []
        assert result.solutions == []
        assert result.constraint_values == {'unassigned_shifts': 0}
    
    def test_solver_result_initialization_infeasible(self):
        """Test: SolverResult für unlösbare Probleme."""
        result = SolverResult(
            status=cp_model.INFEASIBLE,
            is_optimal=False,
            is_feasible=False,
            objective_value=None,
            solve_time=0.5,
            statistics={'conflicts': 100, 'branches': 0},
            appointments=[],
            solutions=[],
            constraint_values={}
        )
        
        assert result.status == cp_model.INFEASIBLE
        assert result.is_optimal is False
        assert result.is_feasible is False
        assert result.objective_value is None
        assert result.solve_time == 0.5
        assert result.appointments == []
        assert result.solutions == []
        assert result.constraint_values == {}
    
    def test_solver_result_initialization_feasible_not_optimal(self):
        """Test: SolverResult für machbare aber nicht optimale Lösung."""
        result = SolverResult(
            status=cp_model.FEASIBLE,
            is_optimal=False,
            is_feasible=True,
            objective_value=100.0,
            solve_time=30.0,  # Hit time limit
            statistics={'conflicts': 1000, 'branches': 50000},
            appointments=[{'actor_id': 'test', 'event_id': 'test_event'}],
            solutions=[],
            constraint_values={'unassigned_shifts': 2}
        )
        
        assert result.status == cp_model.FEASIBLE
        assert result.is_optimal is False
        assert result.is_feasible is True
        assert result.objective_value == 100.0
        assert result.solve_time == 30.0
        assert len(result.appointments) == 1
        assert result.constraint_values['unassigned_shifts'] == 2
    
    def test_solver_result_with_appointments(self):
        """Test: SolverResult mit Appointment-Daten."""
        appointments = [
            {
                'actor_plan_period_id': 'actor1',
                'event_id': 'event1',
                'date': '2025-06-28',
                'time_of_day': 'morning'
            },
            {
                'actor_plan_period_id': 'actor2',
                'event_id': 'event2',
                'date': '2025-06-28',
                'time_of_day': 'afternoon'
            }
        ]
        
        result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=0.0,
            solve_time=2.1,
            statistics={},
            appointments=appointments,
            solutions=[],
            constraint_values={}
        )
        
        assert len(result.appointments) == 2
        assert result.appointments[0]['actor_plan_period_id'] == 'actor1'
        assert result.appointments[1]['event_id'] == 'event2'
    
    def test_solver_result_with_multiple_solutions(self):
        """Test: SolverResult mit mehreren Lösungen."""
        solutions = [
            {
                'solution_id': 1,
                'objective_value': 10.0,
                'appointments': [{'actor': 'A', 'event': 'E1'}]
            },
            {
                'solution_id': 2,
                'objective_value': 12.0,
                'appointments': [{'actor': 'B', 'event': 'E2'}]
            }
        ]
        
        result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=10.0,  # Best solution
            solve_time=5.0,
            statistics={},
            appointments=[],
            solutions=solutions,
            constraint_values={}
        )
        
        assert len(result.solutions) == 2
        assert result.solutions[0]['objective_value'] == 10.0
        assert result.solutions[1]['solution_id'] == 2
    
    def test_solver_result_with_constraint_values(self):
        """Test: SolverResult mit detaillierten Constraint-Werten."""
        constraint_values = {
            'unassigned_shifts': 0,
            'location_preference_violations': 3,
            'skill_mismatches': 1,
            'partner_preference_violations': 0,
            'max_shifts_violations': 2,
            'event_group_activations': 15,
            'avail_day_group_activations': 20
        }
        
        result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=6.0,  # Sum of violations
            solve_time=3.5,
            statistics={},
            appointments=[],
            solutions=[],
            constraint_values=constraint_values
        )
        
        assert result.constraint_values['unassigned_shifts'] == 0
        assert result.constraint_values['location_preference_violations'] == 3
        assert result.constraint_values['skill_mismatches'] == 1
        assert result.constraint_values['max_shifts_violations'] == 2
    
    def test_solver_result_with_comprehensive_statistics(self):
        """Test: SolverResult mit umfassenden Statistiken."""
        statistics = {
            'conflicts': 500,
            'branches': 10000,
            'wall_time': 10.5,
            'user_time': 9.8,
            'deterministic_time': 12345,
            'primal_integral': 100.5,
            'gap_integral': 50.25,
            'solution_fingerprint': 'abc123',
            'num_restarts': 5,
            'num_lp_iterations': 1000
        }
        
        result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=25.0,
            solve_time=10.5,
            statistics=statistics,
            appointments=[],
            solutions=[],
            constraint_values={}
        )
        
        assert result.statistics['conflicts'] == 500
        assert result.statistics['branches'] == 10000
        assert result.statistics['wall_time'] == 10.5
        assert result.statistics['num_restarts'] == 5
    
    def test_solver_result_status_properties(self):
        """Test: SolverResult Status-Eigenschaften."""
        # Test optimal result
        optimal_result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=0.0,
            solve_time=1.0,
            statistics={},
            appointments=[],
            solutions=[],
            constraint_values={}
        )
        
        assert optimal_result.is_optimal is True
        assert optimal_result.is_feasible is True
        
        # Test infeasible result
        infeasible_result = SolverResult(
            status=cp_model.INFEASIBLE,
            is_optimal=False,
            is_feasible=False,
            objective_value=None,
            solve_time=1.0,
            statistics={},
            appointments=[],
            solutions=[],
            constraint_values={}
        )
        
        assert infeasible_result.is_optimal is False
        assert infeasible_result.is_feasible is False
    
    def test_solver_result_data_types(self):
        """Test: SolverResult Datentypen."""
        result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=42.5,
            solve_time=1.23,
            statistics={'key': 'value'},
            appointments=[{'test': 'data'}],
            solutions=[{'solution': 1}],
            constraint_values={'constraint': 5}
        )
        
        # Test types
        assert isinstance(result.status, int)  # cp_model status is int
        assert isinstance(result.is_optimal, bool)
        assert isinstance(result.is_feasible, bool)
        assert isinstance(result.objective_value, (int, float))
        assert isinstance(result.solve_time, (int, float))
        assert isinstance(result.statistics, dict)
        assert isinstance(result.appointments, list)
        assert isinstance(result.solutions, list)
        assert isinstance(result.constraint_values, dict)
    
    def test_solver_result_empty_collections(self):
        """Test: SolverResult mit leeren Collections."""
        result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=0.0,
            solve_time=0.1,
            statistics={},
            appointments=[],
            solutions=[],
            constraint_values={}
        )
        
        assert len(result.statistics) == 0
        assert len(result.appointments) == 0
        assert len(result.solutions) == 0
        assert len(result.constraint_values) == 0
    
    def test_solver_result_none_values(self):
        """Test: SolverResult mit None-Werten wo erlaubt."""
        result = SolverResult(
            status=cp_model.INFEASIBLE,
            is_optimal=False,
            is_feasible=False,
            objective_value=None,  # Allowed for infeasible
            solve_time=0.5,
            statistics={},
            appointments=[],
            solutions=[],
            constraint_values={}
        )
        
        assert result.objective_value is None
        assert result.status == cp_model.INFEASIBLE


@pytest.mark.integration
class TestSolverResultIntegration:
    """Integration-Tests für SolverResult."""
    
    def test_solver_result_realistic_optimal_scenario(self):
        """Test: Realistisches optimales Szenario."""
        # Simulate realistic optimal solving result
        appointments = []
        for i in range(10):
            appointments.append({
                'actor_plan_period_id': f'actor_{i}',
                'event_id': f'event_{i}',
                'date': '2025-06-28',
                'time_of_day': 'morning',
                'location_id': f'location_{i % 3}'
            })
        
        constraint_values = {
            'unassigned_shifts': 0,
            'location_preference_violations': 2,
            'skill_mismatches': 0,
            'partner_preference_violations': 1,
            'max_shifts_violations': 0,
            'event_group_activations': 8,
            'avail_day_group_activations': 12
        }
        
        statistics = {
            'conflicts': 250,
            'branches': 5000,
            'wall_time': 5.2,
            'solution_fingerprint': 'optimal_solution_123'
        }
        
        result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=3.0,  # Sum of violations
            solve_time=5.2,
            statistics=statistics,
            appointments=appointments,
            solutions=[],
            constraint_values=constraint_values
        )
        
        # Verify comprehensive result
        assert result.is_optimal
        assert result.is_feasible
        assert len(result.appointments) == 10
        assert result.objective_value == 3.0
        assert result.constraint_values['unassigned_shifts'] == 0
        assert result.statistics['conflicts'] == 250
    
    def test_solver_result_realistic_timeout_scenario(self):
        """Test: Realistisches Timeout-Szenario."""
        # Simulate timeout with partial solution
        appointments = []
        for i in range(7):  # Only partial assignments
            appointments.append({
                'actor_plan_period_id': f'actor_{i}',
                'event_id': f'event_{i}',
                'date': '2025-06-28'
            })
        
        constraint_values = {
            'unassigned_shifts': 3,  # Some unassigned due to timeout
            'location_preference_violations': 5,
            'skill_mismatches': 2
        }
        
        statistics = {
            'conflicts': 10000,
            'branches': 100000,
            'wall_time': 30.0,  # Hit time limit
            'num_restarts': 10
        }
        
        result = SolverResult(
            status=cp_model.FEASIBLE,
            is_optimal=False,
            is_feasible=True,
            objective_value=50.0,  # Higher due to violations
            solve_time=30.0,
            statistics=statistics,
            appointments=appointments,
            solutions=[],
            constraint_values=constraint_values
        )
        
        # Verify timeout scenario
        assert not result.is_optimal
        assert result.is_feasible
        assert len(result.appointments) == 7
        assert result.constraint_values['unassigned_shifts'] == 3
        assert result.solve_time == 30.0
    
    def test_solver_result_realistic_infeasible_scenario(self):
        """Test: Realistisches unlösbares Szenario."""
        statistics = {
            'conflicts': 50000,
            'branches': 200000,
            'wall_time': 15.5,
            'primal_integral': float('inf')
        }
        
        result = SolverResult(
            status=cp_model.INFEASIBLE,
            is_optimal=False,
            is_feasible=False,
            objective_value=None,
            solve_time=15.5,
            statistics=statistics,
            appointments=[],
            solutions=[],
            constraint_values={}
        )
        
        # Verify infeasible scenario
        assert not result.is_optimal
        assert not result.is_feasible
        assert result.objective_value is None
        assert len(result.appointments) == 0
        assert len(result.constraint_values) == 0
        assert result.statistics['conflicts'] == 50000
    
    def test_solver_result_multi_solution_scenario(self):
        """Test: Multi-Solution Szenario."""
        solutions = []
        for i in range(5):
            solution_appointments = []
            for j in range(8):
                solution_appointments.append({
                    'actor_plan_period_id': f'actor_{j}',
                    'event_id': f'event_{(j + i) % 8}',  # Different assignments
                    'date': '2025-06-28'
                })
            
            solutions.append({
                'solution_id': i + 1,
                'objective_value': 5.0 + i,  # Slightly different objectives
                'appointments': solution_appointments,
                'constraint_values': {
                    'unassigned_shifts': 0,
                    'location_preference_violations': 2 + i,
                    'skill_mismatches': 3 - i if i < 3 else 0
                }
            })
        
        result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=5.0,  # Best solution
            solve_time=8.5,
            statistics={'solutions_found': 5},
            appointments=solutions[0]['appointments'],  # Best solution appointments
            solutions=solutions,
            constraint_values=solutions[0]['constraint_values']
        )
        
        # Verify multi-solution result
        assert result.is_optimal
        assert len(result.solutions) == 5
        assert result.solutions[0]['objective_value'] == 5.0
        assert result.solutions[4]['objective_value'] == 9.0
        assert len(result.appointments) == 8
        assert result.statistics['solutions_found'] == 5
    
    def test_solver_result_performance_with_large_data(self):
        """Test: Performance mit großen Datenmengen."""
        import time
        
        # Create large dataset
        large_appointments = []
        for i in range(1000):
            large_appointments.append({
                'actor_plan_period_id': f'actor_{i}',
                'event_id': f'event_{i}',
                'date': '2025-06-28',
                'additional_data': f'data_{i}'
            })
        
        large_constraint_values = {}
        for i in range(100):
            large_constraint_values[f'constraint_{i}'] = i
        
        large_statistics = {}
        for i in range(50):
            large_statistics[f'stat_{i}'] = i * 1.5
        
        # Measure creation time
        start_time = time.time()
        
        result = SolverResult(
            status=cp_model.OPTIMAL,
            is_optimal=True,
            is_feasible=True,
            objective_value=0.0,
            solve_time=20.0,
            statistics=large_statistics,
            appointments=large_appointments,
            solutions=[],
            constraint_values=large_constraint_values
        )
        
        end_time = time.time()
        creation_time = end_time - start_time
        
        # Verify performance and data integrity
        assert creation_time < 0.1  # Should be very fast
        assert len(result.appointments) == 1000
        assert len(result.constraint_values) == 100
        assert len(result.statistics) == 50
        assert result.appointments[999]['actor_plan_period_id'] == 'actor_999'
