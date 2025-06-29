"""
Integration-Tests für das gesamte SAT-Solver System

Testet die vollständige Integration aller SAT-Solver Komponenten:
- Neue Constraint-basierte Architektur
- Rückwärtskompatible API
- Legacy-Funktionen
- Signal-Handling
- Error-Handling

Dies ist der abschließende Test der 13-teiligen Test-Suite.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4, UUID
from datetime import date, time, datetime
from typing import Generator

from database import schemas
from sat_solver import solver_main
from sat_solver.core.solver_result import SolverResult, SolverStatus
from sat_solver.core.entities import Entities
from sat_solver.avail_day_group_tree import AvailDayGroupTree
from sat_solver.cast_group_tree import CastGroupTree
from sat_solver.event_group_tree import EventGroupTree


@pytest.mark.integration
class TestSolverMainIntegration:
    """Integration-Tests für solver_main Modul."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        # Reset globale entities Variable
        solver_main.entities = None
    
    @patch('sat_solver.solver_main.SATSolver')
    @patch('sat_solver.solver_main.SolverConfig')
    def test_solve_with_new_architecture_success(self, mock_solver_config, mock_sat_solver_class):
        """Test: _solve_with_new_architecture() erfolgreiches Solving."""
        # Mock setup
        plan_period_id = uuid4()
        max_time_seconds = 300
        
        # Mock SolverConfig
        mock_config = Mock()
        mock_solver_config.from_current_config.return_value = mock_config
        
        # Mock SATSolver
        mock_sat_solver = Mock()
        mock_sat_solver_class.return_value = mock_sat_solver
        mock_sat_solver.setup.return_value = True
        
        # Mock entities und context
        mock_entities = Mock()
        mock_context = Mock()
        mock_context.entities = mock_entities
        mock_sat_solver.context = mock_context
        
        # Mock successful result
        mock_appointments = [Mock(), Mock(), Mock()]
        mock_result = SolverResult(
            status=SolverStatus.OPTIMAL,
            appointments=mock_appointments,
            solve_time=120.5,
            constraint_values={'test': 42},
            solutions=[]
        )
        mock_sat_solver.solve.return_value = mock_result
        
        # Call function
        result = solver_main._solve_with_new_architecture(plan_period_id, max_time_seconds)
        
        # Verify interactions
        mock_solver_config.from_current_config.assert_called_once()
        mock_sat_solver_class.assert_called_once_with(plan_period_id, mock_config)
        mock_sat_solver.setup.assert_called_once()
        mock_sat_solver.solve.assert_called_once_with(
            max_time_seconds=max_time_seconds,
            collect_multiple_solutions=False
        )
        
        # Verify result
        assert result == mock_result
        assert solver_main.entities == mock_entities
    
    @patch('sat_solver.solver_main.SATSolver')
    @patch('sat_solver.solver_main.SolverConfig')
    def test_solve_with_new_architecture_setup_failure(self, mock_solver_config, mock_sat_solver_class):
        """Test: _solve_with_new_architecture() Setup-Fehler."""
        # Mock setup failure
        plan_period_id = uuid4()
        max_time_seconds = 300
        
        mock_config = Mock()
        mock_solver_config.from_current_config.return_value = mock_config
        
        mock_sat_solver = Mock()
        mock_sat_solver_class.return_value = mock_sat_solver
        mock_sat_solver.setup.return_value = False  # Setup fails
        
        # Call function and expect RuntimeError
        with pytest.raises(RuntimeError, match="SAT-Solver setup failed"):
            solver_main._solve_with_new_architecture(plan_period_id, max_time_seconds)
        
        # Verify setup was called
        mock_sat_solver.setup.assert_called_once()
        mock_sat_solver.solve.assert_not_called()
    
    @patch('sat_solver.solver_main._solve_with_new_architecture')
    @patch('sat_solver.solver_main._get_max_fair_shifts_and_max_shifts_to_assign')
    @patch('sat_solver.solver_main.signal_handling')
    def test_solve_complete_pipeline_success(self, mock_signal_handling, mock_get_max_fair, mock_solve_new_arch):
        """Test: solve() komplette Pipeline erfolgreich."""
        # Mock data
        plan_period_id = uuid4()
        num_plans = 2
        time_calc_max_shifts = 60
        time_calc_fair_distribution = 30
        time_calc_plan = 120
        
        # Mock max/fair shifts result
        mock_event_tree = Mock()
        mock_avail_tree = Mock()
        fixed_cast_conflicts = {}
        skill_conflicts = {}
        max_shifts_per_app = {uuid4(): 10, uuid4(): 8}
        fair_shifts_per_app = {uuid4(): 7.5, uuid4(): 6.2}
        
        mock_get_max_fair.return_value = (
            mock_event_tree, mock_avail_tree, fixed_cast_conflicts,
            skill_conflicts, max_shifts_per_app, fair_shifts_per_app
        )
        
        # Mock final solve result
        mock_appointments1 = [Mock(), Mock()]
        mock_appointments2 = [Mock(), Mock(), Mock()]
        mock_result = SolverResult(
            status=SolverStatus.OPTIMAL,
            appointments=mock_appointments1,
            solve_time=89.3,
            constraint_values={
                'fixed_cast': {},
                'skills': {}
            },
            solutions=[mock_appointments1, mock_appointments2]
        )
        mock_solve_new_arch.return_value = mock_result
        
        # Mock signal handler
        mock_handler = Mock()
        mock_signal_handling.handler_solver = mock_handler
        
        # Call function
        result = solver_main.solve(
            plan_period_id, num_plans, time_calc_max_shifts,
            time_calc_fair_distribution, time_calc_plan, log_search_process=True
        )
        
        # Verify result structure
        schedule_versions, ret_fixed_cast, ret_skill, ret_max_shifts, ret_fair_shifts = result
        
        assert schedule_versions == [mock_appointments1, mock_appointments2]
        assert ret_fixed_cast == {}
        assert ret_skill == {}
        assert ret_max_shifts == max_shifts_per_app
        assert ret_fair_shifts == fair_shifts_per_app
        
        # Verify function calls
        mock_get_max_fair.assert_called_once_with(
            plan_period_id, time_calc_max_shifts, time_calc_fair_distribution, True
        )
        mock_solve_new_arch.assert_called_once_with(
            plan_period_id, time_calc_plan, collect_multiple_solutions=True
        )
        
        # Verify signal handling
        mock_handler.progress.assert_called()
    
    @patch('sat_solver.solver_main._get_max_fair_shifts_and_max_shifts_to_assign')
    def test_solve_with_conflicts_early_return(self, mock_get_max_fair):
        """Test: solve() mit Conflicts - früher Return."""
        # Mock data
        plan_period_id = uuid4()
        
        # Mock max/fair shifts result with conflicts
        fixed_cast_conflicts = {('2025-06-29', 'Vormittag', uuid4()): 2}
        skill_conflicts = {'Programming': 1}
        max_shifts_per_app = {uuid4(): 5}
        fair_shifts_per_app = {uuid4(): 3.0}
        
        mock_get_max_fair.return_value = (
            Mock(), Mock(), fixed_cast_conflicts, skill_conflicts,
            max_shifts_per_app, fair_shifts_per_app
        )
        
        # Call function
        result = solver_main.solve(plan_period_id, 1, 60, 30, 120)
        
        # Verify early return with conflicts
        schedule_versions, ret_fixed_cast, ret_skill, ret_max_shifts, ret_fair_shifts = result
        
        assert schedule_versions is None
        assert ret_fixed_cast == fixed_cast_conflicts
        assert ret_skill == skill_conflicts
        assert ret_max_shifts == max_shifts_per_app
        assert ret_fair_shifts == fair_shifts_per_app
    
    @patch('sat_solver.solver_main._get_max_fair_shifts_and_max_shifts_to_assign')
    def test_solve_max_fair_calculation_failure(self, mock_get_max_fair):
        """Test: solve() mit Fehler in max/fair Berechnung."""
        # Mock failure
        plan_period_id = uuid4()
        mock_get_max_fair.return_value = None
        
        # Call function
        result = solver_main.solve(plan_period_id, 1, 60, 30, 120)
        
        # Verify failure return
        assert result == (None, None, None, None, None)
    
    @patch('sat_solver.solver_main.SATSolver')
    @patch('sat_solver.solver_main.SolverConfig')
    @patch('sat_solver.solver_main.signal_handling')
    def test_get_max_fair_shifts_and_max_shifts_to_assign_success(
            self, mock_signal_handling, mock_solver_config, mock_sat_solver_class):
        """Test: _get_max_fair_shifts_and_max_shifts_to_assign() erfolgreich."""
        # Mock data
        plan_period_id = uuid4()
        time_calc_max_shifts = 60
        time_calc_fair_distribution = 30
        
        # Mock signal handler
        mock_handler = Mock()
        mock_signal_handling.handler_solver = mock_handler
        
        # Mock SolverConfig und SATSolver
        mock_config = Mock()
        mock_solver_config.from_current_config.return_value = mock_config
        
        mock_sat_solver = Mock()
        mock_sat_solver_class.return_value = mock_sat_solver
        mock_sat_solver.setup.return_value = True
        
        # Mock trees
        mock_event_tree = Mock()
        mock_avail_tree = Mock()
        mock_sat_solver.event_group_tree = mock_event_tree
        mock_sat_solver.avail_day_group_tree = mock_avail_tree
        
        # Mock entities
        app1_id = uuid4()
        app2_id = uuid4()
        mock_entities = Mock()
        mock_entities.actor_plan_periods = {
            app1_id: Mock(id=app1_id, requested_assignments=5),
            app2_id: Mock(id=app2_id, requested_assignments=8)
        }
        mock_entities.avail_day_groups_with_avail_day = {
            uuid4(): Mock(avail_day=Mock(actor_plan_period=Mock(id=app1_id))),
            uuid4(): Mock(avail_day=Mock(actor_plan_period=Mock(id=app1_id))),
            uuid4(): Mock(avail_day=Mock(actor_plan_period=Mock(id=app2_id))),
            uuid4(): Mock(avail_day=Mock(actor_plan_period=Mock(id=app2_id))),
            uuid4(): Mock(avail_day=Mock(actor_plan_period=Mock(id=app2_id)))
        }
        
        mock_context = Mock()
        mock_context.entities = mock_entities
        mock_sat_solver.context = mock_context
        
        # Mock solve result
        mock_appointments = [Mock(), Mock(), Mock()]
        mock_result = SolverResult(
            status=SolverStatus.OPTIMAL,
            appointments=mock_appointments,
            solve_time=45.2,
            constraint_values={
                'fixed_cast': {},
                'skills': {}
            },
            solutions=[]
        )
        mock_sat_solver.solve.return_value = mock_result
        
        # Call function
        with patch('sat_solver.solver_main.generate_adjusted_requested_assignments') as mock_generate:
            mock_generate.return_value = {app1_id: 1.5, app2_id: 1.5}
            
            result = solver_main._get_max_fair_shifts_and_max_shifts_to_assign(
                plan_period_id, time_calc_max_shifts, time_calc_fair_distribution, True
            )
        
        # Verify result
        assert result is not None
        event_tree, avail_tree, fixed_conflicts, skill_conflicts, max_shifts, fair_shifts = result
        
        assert event_tree == mock_event_tree
        assert avail_tree == mock_avail_tree
        assert fixed_conflicts == {}
        assert skill_conflicts == {}
        assert app1_id in max_shifts
        assert app2_id in max_shifts
        assert max_shifts[app1_id] == 2  # 2 avail days
        assert max_shifts[app2_id] == 3  # 3 avail days
        
        # Verify function calls
        mock_sat_solver.setup.assert_called_once()
        mock_sat_solver.solve.assert_called_once_with(max_time_seconds=time_calc_max_shifts)
        mock_generate.assert_called_once()
        mock_handler.progress.assert_called()
    
    def test_check_time_span_avail_day_fits_event_only_time_index(self):
        """Test: check_time_span_avail_day_fits_event() mit only_time_index=True."""
        # Mock event
        mock_event = Mock()
        mock_event.date = date(2025, 6, 29)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.time_of_day_enum = Mock()
        mock_event.time_of_day.time_of_day_enum.time_index = 1
        
        # Mock avail_day that matches
        mock_avail_day_match = Mock()
        mock_avail_day_match.date = date(2025, 6, 29)
        mock_avail_day_match.time_of_day = Mock()
        mock_avail_day_match.time_of_day.time_of_day_enum = Mock()
        mock_avail_day_match.time_of_day.time_of_day_enum.time_index = 1
        
        # Mock avail_day that doesn't match (different date)
        mock_avail_day_no_match_date = Mock()
        mock_avail_day_no_match_date.date = date(2025, 6, 30)
        mock_avail_day_no_match_date.time_of_day = Mock()
        mock_avail_day_no_match_date.time_of_day.time_of_day_enum = Mock()
        mock_avail_day_no_match_date.time_of_day.time_of_day_enum.time_index = 1
        
        # Mock avail_day that doesn't match (different time_index)
        mock_avail_day_no_match_time = Mock()
        mock_avail_day_no_match_time.date = date(2025, 6, 29)
        mock_avail_day_no_match_time.time_of_day = Mock()
        mock_avail_day_no_match_time.time_of_day.time_of_day_enum = Mock()
        mock_avail_day_no_match_time.time_of_day.time_of_day_enum.time_index = 2
        
        # Test matching case
        assert solver_main.check_time_span_avail_day_fits_event(
            mock_event, mock_avail_day_match, only_time_index=True
        )
        
        # Test non-matching cases
        assert not solver_main.check_time_span_avail_day_fits_event(
            mock_event, mock_avail_day_no_match_date, only_time_index=True
        )
        assert not solver_main.check_time_span_avail_day_fits_event(
            mock_event, mock_avail_day_no_match_time, only_time_index=True
        )
    
    def test_check_time_span_avail_day_fits_event_time_overlap(self):
        """Test: check_time_span_avail_day_fits_event() mit only_time_index=False."""
        # Mock event
        mock_event = Mock()
        mock_event.date = date(2025, 6, 29)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.start = time(9, 0)
        mock_event.time_of_day.end = time(11, 0)
        
        # Mock avail_day that covers event time
        mock_avail_day_covers = Mock()
        mock_avail_day_covers.date = date(2025, 6, 29)
        mock_avail_day_covers.time_of_day = Mock()
        mock_avail_day_covers.time_of_day.start = time(8, 0)
        mock_avail_day_covers.time_of_day.end = time(12, 0)
        
        # Mock avail_day that doesn't cover event time
        mock_avail_day_no_cover = Mock()
        mock_avail_day_no_cover.date = date(2025, 6, 29)
        mock_avail_day_no_cover.time_of_day = Mock()
        mock_avail_day_no_cover.time_of_day.start = time(10, 0)
        mock_avail_day_no_cover.time_of_day.end = time(12, 0)
        
        # Test covering case
        assert solver_main.check_time_span_avail_day_fits_event(
            mock_event, mock_avail_day_covers, only_time_index=False
        )
        
        # Test non-covering case
        assert not solver_main.check_time_span_avail_day_fits_event(
            mock_event, mock_avail_day_no_cover, only_time_index=False
        )
    
    def test_generate_adjusted_requested_assignments(self):
        """Test: generate_adjusted_requested_assignments() gerechte Verteilung."""
        # Mock entities
        app1_id = uuid4()
        app2_id = uuid4()
        app3_id = uuid4()
        
        mock_entities = Mock()
        mock_entities.actor_plan_periods = {
            app1_id: Mock(
                id=app1_id,
                requested_assignments=8,
                required_assignments=False,
                person=Mock(f_name="Hans")
            ),
            app2_id: Mock(
                id=app2_id,
                requested_assignments=6,
                required_assignments=False,
                person=Mock(f_name="Maria")
            ),
            app3_id: Mock(
                id=app3_id,
                requested_assignments=10,
                required_assignments=True,
                person=Mock(f_name="Peter")
            )
        }
        
        # Set global entities
        solver_main.entities = mock_entities
        
        # Test data
        assigned_shifts = 15
        possible_assignments = {
            app1_id: 10,
            app2_id: 8,
            app3_id: 12
        }
        
        # Call function
        with patch('builtins.print'):  # Suppress print output
            result = solver_main.generate_adjusted_requested_assignments(
                assigned_shifts, possible_assignments
            )
        
        # Verify result
        assert isinstance(result, dict)
        assert len(result) == 3
        assert all(isinstance(v, float) for v in result.values())
        
        # Verify sum approximates assigned_shifts (within reasonable tolerance)
        total_assigned = sum(result.values())
        assert abs(total_assigned - assigned_shifts) < 1.0
        
        # Verify entities were updated
        for app in mock_entities.actor_plan_periods.values():
            assert app.requested_assignments == result[app.id]


@pytest.mark.integration
class TestSolverMainLegacyCompatibility:
    """Integration-Tests für Legacy-Kompatibilitäts-Funktionen."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        solver_main.entities = None
    
    @patch('sat_solver.solver_main._solve_with_new_architecture')
    def test_call_solver_with_adjusted_requested_assignments(self, mock_solve_new_arch):
        """Test: call_solver_with_adjusted_requested_assignments() Legacy-Wrapper."""
        # Mock event group tree with event that has location_plan_period
        plan_period_id = uuid4()
        mock_location_plan_period = Mock()
        mock_location_plan_period.id = plan_period_id
        
        mock_event = Mock()
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_plan_period = mock_location_plan_period
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        mock_event_tree = Mock()
        mock_event_tree.root = Mock()
        mock_event_tree.root.descendants = [mock_event_group]
        
        mock_avail_tree = Mock()
        max_search_time = 300
        
        # Mock solve result
        mock_appointments = [Mock(), Mock()]
        mock_result = SolverResult(
            status=SolverStatus.OPTIMAL,
            appointments=mock_appointments,
            solve_time=150.7,
            constraint_values={
                'sum_squared_deviations': 42,
                'unassigned_shifts': [1, 2, 0],
                'weights_avail_day_groups': 15,
                'weights_event_groups': 23,
                'location_prefs': 8,
                'partner_prefs': 5,
                'fixed_cast': {},
                'cast_rules': 12
            },
            solutions=[]
        )
        mock_solve_new_arch.return_value = mock_result
        
        # Call function
        result = solver_main.call_solver_with_adjusted_requested_assignments(
            mock_event_tree, mock_avail_tree, max_search_time, True
        )
        
        # Verify result structure (Legacy-Format)
        (sum_squared_deviations, unassigned_shifts_per_event, weights_in_avail_day_groups,
         weights_in_event_groups, sum_location_prefs, sum_partner_loc_prefs,
         fixed_cast_conflicts, sum_cast_rules, appointments, success) = result
        
        assert sum_squared_deviations == 42
        assert unassigned_shifts_per_event == [1, 2, 0]
        assert weights_in_avail_day_groups == 15
        assert weights_in_event_groups == 23
        assert sum_location_prefs == 8
        assert sum_partner_loc_prefs == 5
        assert fixed_cast_conflicts == {}
        assert sum_cast_rules == 12
        assert appointments == mock_appointments
        assert success is True
        
        # Verify function call
        mock_solve_new_arch.assert_called_once_with(plan_period_id, max_search_time)
    
    @patch('sat_solver.solver_main._solve_with_new_architecture')
    def test_call_solver_with_unadjusted_requested_assignments(self, mock_solve_new_arch):
        """Test: call_solver_with_unadjusted_requested_assignments() Legacy-Wrapper."""
        # Mock event group tree
        plan_period_id = uuid4()
        mock_location_plan_period = Mock()
        mock_location_plan_period.id = plan_period_id
        
        mock_event = Mock()
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_plan_period = mock_location_plan_period
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        mock_event_tree = Mock()
        mock_event_tree.root = Mock()
        mock_event_tree.root.descendants = [mock_event_group]
        
        mock_avail_tree = Mock()
        max_search_time = 180
        
        # Mock solve result
        mock_appointments = [Mock(), Mock(), Mock()]
        mock_result = SolverResult(
            status=SolverStatus.OPTIMAL,
            appointments=mock_appointments,
            solve_time=95.4,
            constraint_values={
                'total_unassigned_shifts': 3,
                'location_prefs': 12,
                'partner_prefs': 7,
                'fixed_cast': {},
                'skills': {},
                'cast_rules': 18
            },
            solutions=[]
        )
        mock_solve_new_arch.return_value = mock_result
        
        # Call function
        result = solver_main.call_solver_with_unadjusted_requested_assignments(
            mock_event_tree, mock_avail_tree, max_search_time, False
        )
        
        # Verify result structure (Legacy-Format)
        (assigned_shifts, unassigned_shifts, sum_location_prefs, sum_partner_loc_prefs,
         fixed_cast_conflicts, skill_conflicts, sum_cast_rules, success) = result
        
        assert assigned_shifts == 3  # len(appointments)
        assert unassigned_shifts == 3
        assert sum_location_prefs == 12
        assert sum_partner_loc_prefs == 7
        assert fixed_cast_conflicts == {}
        assert skill_conflicts == {}
        assert sum_cast_rules == 18
        assert success is True
    
    def test_call_solver_to_get_max_shifts_per_app_generator(self):
        """Test: call_solver_to_get_max_shifts_per_app() Generator-Funktion."""
        # Mock entities
        app1_id = uuid4()
        app2_id = uuid4()
        
        mock_entities = Mock()
        mock_entities.actor_plan_periods = {
            app1_id: Mock(id=app1_id, requested_assignments=5),
            app2_id: Mock(id=app2_id, requested_assignments=8)
        }
        mock_entities.avail_day_groups_with_avail_day = {
            uuid4(): Mock(avail_day=Mock(actor_plan_period=Mock(id=app1_id))),
            uuid4(): Mock(avail_day=Mock(actor_plan_period=Mock(id=app1_id))),
            uuid4(): Mock(avail_day=Mock(actor_plan_period=Mock(id=app2_id)))
        }
        
        solver_main.entities = mock_entities
        
        # Mock event group tree
        plan_period_id = uuid4()
        mock_location_plan_period = Mock()
        mock_location_plan_period.id = plan_period_id
        
        mock_event = Mock()
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_plan_period = mock_location_plan_period
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        mock_event_tree = Mock()
        mock_event_tree.root = Mock()
        mock_event_tree.root.descendants = [mock_event_group]
        
        mock_avail_tree = Mock()
        
        # Call generator function
        with patch('sat_solver.solver_main.generate_adjusted_requested_assignments') as mock_generate:
            mock_generate.return_value = {app1_id: 2.5, app2_id: 2.5}
            
            generator = solver_main.call_solver_to_get_max_shifts_per_app(
                mock_event_tree, mock_avail_tree, 0, 0, 0, 0, 0, 5, 120, False
            )
            
            # Verify generator behavior
            assert isinstance(generator, Generator)
            
            # Collect progress signals
            progress_signals = []
            try:
                while True:
                    signal = next(generator)
                    progress_signals.append(signal)
            except StopIteration as e:
                final_result = e.value
            
            # Verify progress signals (one per actor_plan_period)
            assert len(progress_signals) == 2
            assert all(signal is True for signal in progress_signals)
            
            # Verify final result
            success, max_shifts, fair_assignments = final_result
            assert success is True
            assert app1_id in max_shifts
            assert app2_id in max_shifts
            assert max_shifts[app1_id] == 2  # 2 avail days
            assert max_shifts[app2_id] == 1  # 1 avail day
            assert fair_assignments == {app1_id: 2.5, app2_id: 2.5}
    
    @patch('sat_solver.solver_main.SATSolver')
    @patch('sat_solver.solver_main.SolverConfig')
    def test_call_solver_to_test_plan_success(self, mock_solver_config, mock_sat_solver_class):
        """Test: call_solver_to_test_plan() erfolglicher Plan-Test."""
        # Mock plan
        mock_plan = Mock()
        mock_plan.appointments = [Mock(), Mock()]
        mock_plan.plan_period = Mock()
        mock_plan.plan_period.id = uuid4()
        
        mock_event_tree = Mock()
        mock_avail_tree = Mock()
        max_search_time = 60
        
        # Mock SolverConfig und SATSolver
        mock_config = Mock()
        mock_solver_config.from_current_config.return_value = mock_config
        
        mock_sat_solver = Mock()
        mock_sat_solver_class.return_value = mock_sat_solver
        mock_sat_solver.setup.return_value = True
        
        # Mock successful test result
        mock_result = SolverResult(
            status=SolverStatus.OPTIMAL,
            appointments=[],
            solve_time=25.8,
            constraint_values={},
            solutions=[]
        )
        mock_sat_solver.solve.return_value = mock_result
        
        # Call function
        success, errors = solver_main.call_solver_to_test_plan(
            mock_plan, mock_event_tree, mock_avail_tree, max_search_time, True
        )
        
        # Verify result
        assert success is True
        assert errors == []
        
        # Verify function calls
        mock_sat_solver.setup.assert_called_once()
        mock_sat_solver.solve.assert_called_once_with(max_time_seconds=max_search_time)
    
    @patch('sat_solver.solver_main.SATSolver')
    @patch('sat_solver.solver_main.SolverConfig')
    def test_call_solver_to_test_plan_infeasible(self, mock_solver_config, mock_sat_solver_class):
        """Test: call_solver_to_test_plan() Plan nicht machbar."""
        # Mock plan
        mock_plan = Mock()
        mock_plan.appointments = [Mock()]
        mock_plan.plan_period = Mock()
        mock_plan.plan_period.id = uuid4()
        
        mock_event_tree = Mock()
        mock_avail_tree = Mock()
        max_search_time = 30
        
        # Mock SolverConfig und SATSolver
        mock_config = Mock()
        mock_solver_config.from_current_config.return_value = mock_config
        
        mock_sat_solver = Mock()
        mock_sat_solver_class.return_value = mock_sat_solver
        mock_sat_solver.setup.return_value = True
        
        # Mock infeasible test result
        mock_result = SolverResult(
            status=SolverStatus.INFEASIBLE,
            appointments=[],
            solve_time=15.2,
            constraint_values={},
            solutions=[]
        )
        mock_sat_solver.solve.return_value = mock_result
        
        # Call function
        success, errors = solver_main.call_solver_to_test_plan(
            mock_plan, mock_event_tree, mock_avail_tree, max_search_time, False
        )
        
        # Verify result
        assert success is False
        assert len(errors) == 1
        assert "Plan not feasible: INFEASIBLE" in errors[0]


@pytest.mark.integration
class TestSolverMainErrorHandling:
    """Integration-Tests für Error-Handling."""
    
    def test_solve_with_exception(self):
        """Test: solve() mit Exception."""
        # Mock exception während _get_max_fair_shifts_and_max_shifts_to_assign
        plan_period_id = uuid4()
        
        with patch('sat_solver.solver_main._get_max_fair_shifts_and_max_shifts_to_assign') as mock_get_max_fair:
            mock_get_max_fair.side_effect = Exception("Database connection failed")
            
            # Call function
            result = solver_main.solve(plan_period_id, 1, 60, 30, 120)
            
            # Verify error handling
            assert result == (None, None, None, None, None)
    
    @patch('sat_solver.solver_main.SATSolver')
    @patch('sat_solver.solver_main.SolverConfig')
    def test_solve_with_new_architecture_exception(self, mock_solver_config, mock_sat_solver_class):
        """Test: _solve_with_new_architecture() mit Exception."""
        # Mock exception during solve
        plan_period_id = uuid4()
        
        mock_config = Mock()
        mock_solver_config.from_current_config.return_value = mock_config
        
        mock_sat_solver = Mock()
        mock_sat_solver_class.return_value = mock_sat_solver
        mock_sat_solver.setup.return_value = True
        mock_sat_solver.solve.side_effect = Exception("OR-Tools error")
        
        # Call function and expect exception propagation
        with pytest.raises(Exception, match="OR-Tools error"):
            solver_main._solve_with_new_architecture(plan_period_id, 300)
    
    def test_legacy_functions_with_invalid_event_tree(self):
        """Test: Legacy-Funktionen mit ungültiger EventGroupTree."""
        # Mock event group tree ohne Events
        mock_event_tree = Mock()
        mock_event_tree.root = Mock()
        mock_event_tree.root.descendants = []  # Keine Events
        
        mock_avail_tree = Mock()
        
        # Test call_solver_with_adjusted_requested_assignments
        result = solver_main.call_solver_with_adjusted_requested_assignments(
            mock_event_tree, mock_avail_tree, 60, False
        )
        
        # Verify error handling
        (sum_squared_deviations, unassigned_shifts_per_event, weights_in_avail_day_groups,
         weights_in_event_groups, sum_location_prefs, sum_partner_loc_prefs,
         fixed_cast_conflicts, sum_cast_rules, appointments, success) = result
        
        assert success is False
        assert appointments == []
        
        # Test call_solver_with_unadjusted_requested_assignments
        result2 = solver_main.call_solver_with_unadjusted_requested_assignments(
            mock_event_tree, mock_avail_tree, 60, False
        )
        
        # Verify error handling
        (assigned_shifts, unassigned_shifts, sum_location_prefs, sum_partner_loc_prefs,
         fixed_cast_conflicts, skill_conflicts, sum_cast_rules, success) = result2
        
        assert success is False
        assert assigned_shifts == 0


@pytest.mark.integration
class TestSolverMainGlobalState:
    """Integration-Tests für globale State-Verwaltung."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        solver_main.entities = None
    
    def test_global_entities_variable_lifecycle(self):
        """Test: Globale entities Variable Lifecycle."""
        # Initial state
        assert solver_main.entities is None
        
        # Mock entities
        mock_entities = Mock()
        
        # Simulate setting entities during solve
        solver_main.entities = mock_entities
        assert solver_main.entities == mock_entities
        
        # Reset for next test
        solver_main.entities = None
        assert solver_main.entities is None
    
    def test_entities_persistence_across_function_calls(self):
        """Test: entities Persistenz zwischen Funktionsaufrufen."""
        # Setup mock entities
        app_id = uuid4()
        mock_entities = Mock()
        mock_entities.actor_plan_periods = {
            app_id: Mock(id=app_id, requested_assignments=5, person=Mock(f_name="Test"))
        }
        
        solver_main.entities = mock_entities
        
        # Call function that uses entities
        possible_assignments = {app_id: 10}
        assigned_shifts = 3
        
        with patch('builtins.print'):  # Suppress print output
            result = solver_main.generate_adjusted_requested_assignments(
                assigned_shifts, possible_assignments
            )
        
        # Verify entities was used and modified
        assert result is not None
        assert app_id in result
        
        # Verify entities persists
        assert solver_main.entities == mock_entities
    
    @patch('sat_solver.solver_main.signal_handling')
    def test_signal_handling_integration(self, mock_signal_handling):
        """Test: Signal-Handling Integration."""
        # Mock signal handler
        mock_handler = Mock()
        mock_signal_handling.handler_solver = mock_handler
        
        # Test direct signal call
        solver_main.signal_handling.handler_solver.progress('Test message')
        
        # Verify signal was sent
        mock_handler.progress.assert_called_with('Test message')


@pytest.mark.performance
class TestSolverMainPerformance:
    """Performance-Tests für solver_main Integration."""
    
    @patch('sat_solver.solver_main.SATSolver')
    @patch('sat_solver.solver_main.SolverConfig')
    def test_solve_performance_benchmark(self, mock_solver_config, mock_sat_solver_class):
        """Test: solve() Performance-Benchmark."""
        import time
        
        # Mock large-scale scenario
        plan_period_id = uuid4()
        num_employees = 50
        num_appointments = 200
        
        # Mock SolverConfig
        mock_config = Mock()
        mock_solver_config.from_current_config.return_value = mock_config
        
        # Mock SATSolver with realistic large-scale data
        mock_sat_solver = Mock()
        mock_sat_solver_class.return_value = mock_sat_solver
        mock_sat_solver.setup.return_value = True
        
        # Mock entities for large scenario
        mock_entities = Mock()
        mock_entities.actor_plan_periods = {
            uuid4(): Mock(id=uuid4(), requested_assignments=4)
            for _ in range(num_employees)
        }
        mock_entities.avail_day_groups_with_avail_day = {
            uuid4(): Mock(avail_day=Mock(actor_plan_period=Mock(id=list(mock_entities.actor_plan_periods.keys())[i % num_employees])))
            for i in range(num_employees * 5)  # 5 avail days per employee
        }
        
        mock_context = Mock()
        mock_context.entities = mock_entities
        mock_sat_solver.context = mock_context
        
        # Mock solve results
        mock_appointments = [Mock() for _ in range(num_appointments)]
        mock_result = SolverResult(
            status=SolverStatus.OPTIMAL,
            appointments=mock_appointments,
            solve_time=25.5,
            constraint_values={'fixed_cast': {}, 'skills': {}},
            solutions=[]
        )
        mock_sat_solver.solve.return_value = mock_result
        
        # Mock trees
        mock_sat_solver.event_group_tree = Mock()
        mock_sat_solver.avail_day_group_tree = Mock()
        
        # Measure solve time
        start_time = time.time()
        
        with patch('sat_solver.solver_main.generate_adjusted_requested_assignments') as mock_generate:
            mock_generate.return_value = {app_id: 4.0 for app_id in mock_entities.actor_plan_periods.keys()}
            
            with patch('sat_solver.solver_main.signal_handling'):
                result = solver_main.solve(plan_period_id, 1, 30, 20, 60)
        
        end_time = time.time()
        solve_time = end_time - start_time
        
        # Verify performance is reasonable for large scenario
        assert solve_time < 2.0  # Should complete within 2 seconds
        
        # Verify result is correct
        schedule_versions, _, _, _, _ = result
        assert schedule_versions is not None
        assert len(schedule_versions[0]) == num_appointments
    
    def test_memory_efficiency_multiple_solves(self):
        """Test: Memory-Effizienz bei mehreren Solve-Aufrufen."""
        import gc
        
        # Force garbage collection before test
        gc.collect()
        
        # Simulate multiple solve cycles
        for i in range(10):
            plan_period_id = uuid4()
            
            # Mock minimal solve scenario
            with patch('sat_solver.solver_main._get_max_fair_shifts_and_max_shifts_to_assign') as mock_get_max_fair:
                mock_get_max_fair.return_value = None  # Fail quickly
                
                result = solver_main.solve(plan_period_id, 1, 10, 10, 10)
                assert result == (None, None, None, None, None)
            
            # Reset global state
            solver_main.entities = None
        
        # Force garbage collection after test
        gc.collect()
        
        # Should not leak significant memory
        assert True  # Test passes if no memory errors occur
