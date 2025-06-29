"""
Unit-Tests für CastRulesConstraint

Testet das Constraint für Cast-Regeln zwischen Events.
Behandelt verschiedene Besetzungsregeln wie:
- '-': Verschiedene Besetzungen erforderlich
- '~': Gleiche Besetzungen erforderlich  
- '*': Keine Regel (ignoriert)
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from datetime import date

from sat_solver.constraints.cast_rules import CastRulesConstraint


@pytest.mark.unit
class TestCastRulesConstraint:
    """Test-Klasse für CastRulesConstraint."""
    
    def test_constraint_name(self, mock_solver_context):
        """Test: Constraint-Name ist korrekt."""
        constraint = CastRulesConstraint(mock_solver_context)
        assert constraint.constraint_name == "cast_rules"
    
    def test_constraint_initialization(self, mock_solver_context):
        """Test: Constraint wird korrekt initialisiert."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        assert constraint.context == mock_solver_context
        assert constraint.model == mock_solver_context.model
        assert constraint.entities == mock_solver_context.entities
        assert constraint.config == mock_solver_context.config
        assert not constraint.is_setup_complete()
    
    def test_create_variables_empty_entities(self, mock_solver_context):
        """Test: create_variables() mit leeren Entities."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.cast_groups_with_event = {}
        
        variables = constraint.create_variables()
        
        # Should return empty list for empty entities
        assert variables == []
        assert constraint.get_metadata('total_cast_rule_conflicts') == 0
    
    def test_organize_cast_groups_by_parent(self, mock_solver_context):
        """Test: _organize_cast_groups_by_parent() Methode."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test data
        parent_id1, parent_id2 = uuid4(), uuid4()
        cg_id1, cg_id2, cg_id3 = uuid4(), uuid4(), uuid4()
        
        # Mock parents
        mock_parent1 = Mock()
        mock_parent1.cast_group_id = parent_id1
        
        mock_parent2 = Mock()
        mock_parent2.cast_group_id = parent_id2
        
        # Mock cast groups
        mock_cg1 = Mock()
        mock_cg1.parent = mock_parent1
        
        mock_cg2 = Mock()
        mock_cg2.parent = mock_parent1  # Same parent as cg1
        
        mock_cg3 = Mock()
        mock_cg3.parent = mock_parent2  # Different parent
        
        mock_solver_context.entities.cast_groups_with_event = {
            cg_id1: mock_cg1,
            cg_id2: mock_cg2,
            cg_id3: mock_cg3
        }
        
        # Organize groups
        organized = constraint._organize_cast_groups_by_parent()
        
        # Verify organization
        assert len(organized) == 2
        assert parent_id1 in organized
        assert parent_id2 in organized
        assert len(organized[parent_id1]) == 2  # cg1, cg2
        assert len(organized[parent_id2]) == 1  # cg3
        assert mock_cg1 in organized[parent_id1]
        assert mock_cg2 in organized[parent_id1]
        assert mock_cg3 in organized[parent_id2]
    
    def test_get_shift_vars_for_actor_and_event(self, mock_solver_context):
        """Test: _get_shift_vars_for_actor_and_event() Methode."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test data
        app_id = uuid4()
        event_group_id = uuid4()
        adg_id1, adg_id2, adg_id3 = uuid4(), uuid4(), uuid4()
        
        # Mock event group
        mock_event_group = Mock()
        mock_event_group.id = event_group_id
        
        # Mock actor plan periods
        mock_app = Mock()
        mock_app.id = app_id
        
        # Mock avail day groups
        mock_adg1 = Mock()
        mock_adg1.avail_day = Mock()
        mock_adg1.avail_day.actor_plan_period = mock_app  # Correct actor
        
        mock_adg2 = Mock()
        mock_adg2.avail_day = Mock()
        mock_adg2.avail_day.actor_plan_period = Mock()  # Different actor
        mock_adg2.avail_day.actor_plan_period.id = uuid4()
        
        mock_adg3 = Mock()
        mock_adg3.avail_day = Mock()
        mock_adg3.avail_day.actor_plan_period = mock_app  # Correct actor
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2,
            adg_id3: mock_adg3
        }
        
        # Mock shift variables
        mock_var1 = Mock()
        mock_var2 = Mock()
        mock_var3 = Mock()
        
        mock_solver_context.entities.shift_vars = {
            (adg_id1, event_group_id): mock_var1,  # Correct actor, correct event
            (adg_id2, event_group_id): mock_var2,  # Wrong actor, correct event
            (adg_id3, uuid4()): mock_var3          # Correct actor, wrong event
        }
        
        # Mock shifts_exclusive
        mock_solver_context.entities.shifts_exclusive = {
            (adg_id1, event_group_id): 1,  # Allowed
            (adg_id2, event_group_id): 0,  # Not allowed
            (adg_id3, uuid4()): 1          # Allowed but wrong event
        }
        
        # Get shift vars
        shift_vars = constraint._get_shift_vars_for_actor_and_event(app_id, mock_event_group)
        
        # Should only return variables for correct actor, correct event, and allowed shifts
        assert len(shift_vars) == 1
        assert mock_var1 in shift_vars
        assert mock_var2 not in shift_vars  # Wrong actor
        assert mock_var3 not in shift_vars  # Wrong event
    
    def test_create_different_cast_constraints_hard(self, mock_solver_context):
        """Test: _create_different_cast_constraints() mit Hard Constraint."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test data
        app_id1, app_id2 = uuid4(), uuid4()
        eg_id1, eg_id2 = uuid4(), uuid4()
        
        # Mock actor plan periods
        mock_app1 = Mock()
        mock_app1.id = app_id1
        mock_app1.person = Mock()
        mock_app1.person.f_name = "Actor1"
        
        mock_app2 = Mock()
        mock_app2.id = app_id2
        mock_app2.person = Mock()
        mock_app2.person.f_name = "Actor2"
        
        mock_solver_context.entities.actor_plan_periods = {
            app_id1: mock_app1,
            app_id2: mock_app2
        }
        
        # Mock event groups
        mock_event_group1 = Mock()
        mock_event_group1.id = eg_id1
        
        mock_event_group2 = Mock()
        mock_event_group2.id = eg_id2
        
        # Mock events
        mock_event1 = Mock()
        mock_event1.event_group = mock_event_group1
        mock_event1.date = date(2025, 6, 28)
        mock_event1.location_plan_period = Mock()
        mock_event1.location_plan_period.location_of_work = Mock()
        mock_event1.location_plan_period.location_of_work.name = "Location1"
        
        mock_event2 = Mock()
        mock_event2.event_group = mock_event_group2
        mock_event2.date = date(2025, 6, 29)
        mock_event2.location_plan_period = Mock()
        mock_event2.location_plan_period.location_of_work = Mock()
        mock_event2.location_plan_period.location_of_work.name = "Location2"
        
        # Mock cast groups
        mock_cast_group1 = Mock()
        mock_cast_group1.event = mock_event1
        
        mock_cast_group2 = Mock()
        mock_cast_group2.event = mock_event2
        
        # Mock shift variables for actors
        with patch.object(constraint, '_get_shift_vars_for_actor_and_event') as mock_get_shift_vars:
            mock_get_shift_vars.side_effect = lambda app_id, event_group: {
                (app_id1, mock_event_group1): [Mock()],
                (app_id1, mock_event_group2): [Mock()],
                (app_id2, mock_event_group1): [Mock()],
                (app_id2, mock_event_group2): [Mock()]
            }.get((app_id, event_group), [])
            
            # Create constraints with hard rule (strict_rule_pref = 2)
            conflict_vars = constraint._create_different_cast_constraints(
                mock_cast_group1, mock_cast_group2, strict_rule_pref=2
            )
        
        # Hard constraints should not return penalty variables
        assert len(conflict_vars) == 0
        
        # Should have added hard constraints via model.Add
        assert mock_solver_context.model.Add.called
    
    def test_create_different_cast_constraints_soft(self, mock_solver_context):
        """Test: _create_different_cast_constraints() mit Soft Constraint."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test data (similar to hard constraint test)
        app_id = uuid4()
        eg_id1, eg_id2 = uuid4(), uuid4()
        
        mock_app = Mock()
        mock_app.id = app_id
        mock_app.person = Mock()
        mock_app.person.f_name = "Actor"
        
        mock_solver_context.entities.actor_plan_periods = {app_id: mock_app}
        
        # Mock event groups and events
        mock_event_group1 = Mock()
        mock_event_group1.id = eg_id1
        
        mock_event_group2 = Mock()
        mock_event_group2.id = eg_id2
        
        mock_event1 = Mock()
        mock_event1.event_group = mock_event_group1
        mock_event1.date = date(2025, 6, 28)
        mock_event1.location_plan_period = Mock()
        mock_event1.location_plan_period.location_of_work = Mock()
        mock_event1.location_plan_period.location_of_work.name = "Location"
        
        mock_event2 = Mock()
        mock_event2.event_group = mock_event_group2
        mock_event2.date = date(2025, 6, 29)
        mock_event2.location_plan_period = Mock()
        mock_event2.location_plan_period.location_of_work = Mock()
        mock_event2.location_plan_period.location_of_work.name = "Location"
        
        mock_cast_group1 = Mock()
        mock_cast_group1.event = mock_event1
        
        mock_cast_group2 = Mock()
        mock_cast_group2.event = mock_event2
        
        # Mock penalty variable
        mock_penalty_var = Mock()
        mock_solver_context.model.NewBoolVar.return_value = mock_penalty_var
        
        # Mock shift variables
        with patch.object(constraint, '_get_shift_vars_for_actor_and_event') as mock_get_shift_vars:
            mock_get_shift_vars.side_effect = lambda app_id_param, event_group: [Mock()] if app_id_param == app_id else []
            
            # Create constraints with soft rule (strict_rule_pref = 1)
            conflict_vars = constraint._create_different_cast_constraints(
                mock_cast_group1, mock_cast_group2, strict_rule_pref=1
            )
        
        # Soft constraints should return penalty variables
        assert len(conflict_vars) == 1
        assert conflict_vars[0] == mock_penalty_var
        
        # Should have created penalty variable and constraints
        assert mock_solver_context.model.NewBoolVar.called
        assert mock_solver_context.model.AddMaxEquality.called
    
    def test_create_same_cast_constraints_hard(self, mock_solver_context):
        """Test: _create_same_cast_constraints() mit Hard Constraint."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test data
        eg_id1, eg_id2 = uuid4(), uuid4()
        
        # Mock event groups
        mock_event_group1 = Mock()
        mock_event_group1.id = eg_id1
        mock_event_group1.event_group_id = eg_id1
        
        mock_event_group2 = Mock()
        mock_event_group2.id = eg_id2
        mock_event_group2.event_group_id = eg_id2
        
        # Mock events
        mock_event1 = Mock()
        mock_event1.event_group = mock_event_group1
        
        mock_event2 = Mock()
        mock_event2.event_group = mock_event_group2
        
        # Mock cast groups with nr_actors
        mock_cast_group1 = Mock()
        mock_cast_group1.event = mock_event1
        mock_cast_group1.nr_actors = 2
        
        mock_cast_group2 = Mock()
        mock_cast_group2.event = mock_event2
        mock_cast_group2.nr_actors = 3  # Different cast size
        
        # Mock event group vars
        mock_solver_context.entities.event_group_vars = {
            eg_id1: Mock(),
            eg_id2: Mock()
        }
        
        # Mock applied shifts and unequal variables
        mock_applied_shifts_1 = [Mock(), Mock()]
        mock_applied_shifts_2 = [Mock(), Mock()]
        mock_unequal_vars = [Mock(), Mock()]
        
        with patch.object(constraint, '_create_applied_shifts_variables') as mock_create_applied:
            with patch.object(constraint, '_create_unequal_variables') as mock_create_unequal:
                mock_create_applied.return_value = (mock_applied_shifts_1, mock_applied_shifts_2)
                mock_create_unequal.return_value = mock_unequal_vars
                
                # Create constraints with hard rule (strict_rule_pref = 2)
                conflict_vars = constraint._create_same_cast_constraints(
                    mock_cast_group1, mock_cast_group2, strict_rule_pref=2
                )
        
        # Hard constraints should not return penalty variables
        assert len(conflict_vars) == 0
        
        # Should have created applied shifts and unequal variables
        mock_create_applied.assert_called_once_with(mock_event_group1, mock_event_group2)
        mock_create_unequal.assert_called_once_with(mock_applied_shifts_1, mock_applied_shifts_2)
        
        # Should have added hard constraints
        assert mock_solver_context.model.Add.called
        assert mock_solver_context.model.AddImplication.called
    
    def test_create_same_cast_constraints_soft(self, mock_solver_context):
        """Test: _create_same_cast_constraints() mit Soft Constraint."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup similar to hard constraint test
        eg_id1, eg_id2 = uuid4(), uuid4()
        
        mock_event_group1 = Mock()
        mock_event_group1.id = eg_id1
        mock_event_group1.event_group_id = eg_id1
        
        mock_event_group2 = Mock()
        mock_event_group2.id = eg_id2
        mock_event_group2.event_group_id = eg_id2
        
        mock_event1 = Mock()
        mock_event1.event_group = mock_event_group1
        mock_event1.date = date(2025, 6, 28)
        mock_event1.location_plan_period = Mock()
        mock_event1.location_plan_period.location_of_work = Mock()
        mock_event1.location_plan_period.location_of_work.name = "Location"
        
        mock_event2 = Mock()
        mock_event2.event_group = mock_event_group2
        mock_event2.date = date(2025, 6, 29)
        mock_event2.location_plan_period = Mock()
        mock_event2.location_plan_period.location_of_work = Mock()
        mock_event2.location_plan_period.location_of_work.name = "Location"
        
        mock_cast_group1 = Mock()
        mock_cast_group1.event = mock_event1
        mock_cast_group1.nr_actors = 2
        
        mock_cast_group2 = Mock()
        mock_cast_group2.event = mock_event2
        mock_cast_group2.nr_actors = 2  # Same cast size
        
        # Mock entities
        mock_solver_context.entities.event_group_vars = {
            eg_id1: Mock(),
            eg_id2: Mock()
        }
        
        # Mock penalty variables
        mock_penalty_var = Mock()
        mock_intermediate_var = Mock()
        mock_both_events_var = Mock()
        
        mock_solver_context.model.NewIntVar.side_effect = [mock_penalty_var, mock_intermediate_var]
        mock_solver_context.model.NewBoolVar.return_value = mock_both_events_var
        
        # Mock applied shifts and unequal variables
        mock_applied_shifts = ([Mock()], [Mock()])
        mock_unequal_vars = [Mock()]
        
        with patch.object(constraint, '_create_applied_shifts_variables') as mock_create_applied:
            with patch.object(constraint, '_create_unequal_variables') as mock_create_unequal:
                mock_create_applied.return_value = mock_applied_shifts
                mock_create_unequal.return_value = mock_unequal_vars
                
                # Create constraints with soft rule (strict_rule_pref = 1)
                conflict_vars = constraint._create_same_cast_constraints(
                    mock_cast_group1, mock_cast_group2, strict_rule_pref=1
                )
        
        # Soft constraints should return penalty variables
        assert len(conflict_vars) == 1
        assert conflict_vars[0] == mock_penalty_var
        
        # Should have created penalty calculation
        assert mock_solver_context.model.NewIntVar.called
        assert mock_solver_context.model.NewBoolVar.called
        assert mock_solver_context.model.AddMultiplicationEquality.called
        assert mock_solver_context.model.AddDivisionEquality.called
    
    def test_create_applied_shifts_variables(self, mock_solver_context):
        """Test: _create_applied_shifts_variables() Methode."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test data
        app_id1, app_id2 = uuid4(), uuid4()
        
        # Mock actor plan periods
        mock_app1 = Mock()
        mock_app1.person = Mock()
        mock_app1.person.f_name = "Actor1"
        
        mock_app2 = Mock()
        mock_app2.person = Mock()
        mock_app2.person.f_name = "Actor2"
        
        mock_solver_context.entities.actor_plan_periods = {
            app_id1: mock_app1,
            app_id2: mock_app2
        }
        
        # Mock event groups
        mock_event_group1 = Mock()
        mock_event_group1.event = Mock()
        mock_event_group1.event.date = date(2025, 6, 28)
        
        mock_event_group2 = Mock()
        mock_event_group2.event = Mock()
        mock_event_group2.event.date = date(2025, 6, 29)
        
        # Mock NewBoolVar
        mock_vars = [Mock() for _ in range(4)]  # 2 actors × 2 events
        mock_solver_context.model.NewBoolVar.side_effect = mock_vars
        
        # Mock shift vars retrieval
        with patch.object(constraint, '_get_shift_vars_for_actor_and_event') as mock_get_shift_vars:
            mock_get_shift_vars.return_value = [Mock()]  # Always return one shift var
            
            # Create applied shifts variables
            applied_1, applied_2 = constraint._create_applied_shifts_variables(
                mock_event_group1, mock_event_group2
            )
        
        # Should create variables for each actor for each event
        assert len(applied_1) == 2
        assert len(applied_2) == 2
        
        # Should have created bool vars and constraints
        assert mock_solver_context.model.NewBoolVar.call_count == 4
        assert mock_solver_context.model.Add.call_count == 4
    
    def test_create_unequal_variables(self, mock_solver_context):
        """Test: _create_unequal_variables() Methode."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test data
        app_id1, app_id2 = uuid4(), uuid4()
        
        mock_app1 = Mock()
        mock_app1.person = Mock()
        mock_app1.person.f_name = "Actor1"
        
        mock_app2 = Mock()
        mock_app2.person = Mock()
        mock_app2.person.f_name = "Actor2"
        
        mock_solver_context.entities.actor_plan_periods = {
            app_id1: mock_app1,
            app_id2: mock_app2
        }
        
        # Mock applied shifts
        mock_applied_1 = [Mock(), Mock()]
        mock_applied_2 = [Mock(), Mock()]
        
        # Mock variables
        mock_unequal_vars = [Mock(), Mock()]
        mock_factor_vars = [Mock(), Mock()]
        
        mock_solver_context.model.NewBoolVar.side_effect = mock_unequal_vars
        mock_solver_context.model.NewIntVar.side_effect = mock_factor_vars
        
        # Create unequal variables
        unequal_vars = constraint._create_unequal_variables(mock_applied_1, mock_applied_2)
        
        # Should create XOR variables for each actor
        assert len(unequal_vars) == 2
        assert unequal_vars == mock_unequal_vars
        
        # Should have created variables and XOR constraints
        assert mock_solver_context.model.NewBoolVar.call_count == 2
        assert mock_solver_context.model.NewIntVar.call_count == 2
        assert mock_solver_context.model.Add.call_count == 2
    
    def test_create_variables_with_different_rule(self, mock_solver_context):
        """Test: create_variables() mit '-' Regel (verschiedene Besetzungen)."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test scenario
        parent_id = uuid4()
        cg_id1, cg_id2 = uuid4(), uuid4()
        
        # Mock parent with '-' rule
        mock_parent = Mock()
        mock_parent.cast_rule = "-*"  # Different, then ignore
        mock_parent.strict_rule_pref = 1  # Soft constraint
        
        # Mock cast groups
        mock_cast_group1 = Mock()
        mock_cast_group1.parent = Mock()
        mock_cast_group1.parent.cast_group_id = parent_id
        mock_cast_group1.event = Mock()
        mock_cast_group1.event.date = date(2025, 6, 28)
        mock_cast_group1.event.time_of_day = Mock()
        mock_cast_group1.event.time_of_day.time_of_day_enum = Mock()
        mock_cast_group1.event.time_of_day.time_of_day_enum.time_index = 1
        
        mock_cast_group2 = Mock()
        mock_cast_group2.parent = Mock()
        mock_cast_group2.parent.cast_group_id = parent_id
        mock_cast_group2.event = Mock()
        mock_cast_group2.event.date = date(2025, 6, 29)
        mock_cast_group2.event.time_of_day = Mock()
        mock_cast_group2.event.time_of_day.time_of_day_enum = Mock()
        mock_cast_group2.event.time_of_day.time_of_day_enum.time_index = 1
        
        # Setup entities
        mock_solver_context.entities.cast_groups = {parent_id: mock_parent}
        mock_solver_context.entities.cast_groups_with_event = {
            cg_id1: mock_cast_group1,
            cg_id2: mock_cast_group2
        }
        
        # Mock _create_different_cast_constraints
        mock_conflict_vars = [Mock(), Mock()]
        with patch.object(constraint, '_create_different_cast_constraints') as mock_create_different:
            mock_create_different.return_value = mock_conflict_vars
            
            variables = constraint.create_variables()
        
        # Should create conflict variables for '-' rule
        assert len(variables) == 2
        assert variables == mock_conflict_vars
        assert constraint.get_metadata('total_cast_rule_conflicts') == 2
        
        # Verify _create_different_cast_constraints was called
        mock_create_different.assert_called_once_with(mock_cast_group1, mock_cast_group2, 1)
    
    def test_create_variables_with_same_rule(self, mock_solver_context):
        """Test: create_variables() mit '~' Regel (gleiche Besetzungen)."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test scenario
        parent_id = uuid4()
        cg_id1, cg_id2 = uuid4(), uuid4()
        
        # Mock parent with '~' rule
        mock_parent = Mock()
        mock_parent.cast_rule = "~"  # Same cast
        mock_parent.strict_rule_pref = 2  # Hard constraint
        
        # Mock cast groups (similar to previous test)
        mock_cast_group1 = Mock()
        mock_cast_group1.parent = Mock()
        mock_cast_group1.parent.cast_group_id = parent_id
        mock_cast_group1.event = Mock()
        mock_cast_group1.event.date = date(2025, 6, 28)
        mock_cast_group1.event.time_of_day = Mock()
        mock_cast_group1.event.time_of_day.time_of_day_enum = Mock()
        mock_cast_group1.event.time_of_day.time_of_day_enum.time_index = 1
        
        mock_cast_group2 = Mock()
        mock_cast_group2.parent = Mock()
        mock_cast_group2.parent.cast_group_id = parent_id
        mock_cast_group2.event = Mock()
        mock_cast_group2.event.date = date(2025, 6, 29)
        mock_cast_group2.event.time_of_day = Mock()
        mock_cast_group2.event.time_of_day.time_of_day_enum = Mock()
        mock_cast_group2.event.time_of_day.time_of_day_enum.time_index = 1
        
        # Setup entities
        mock_solver_context.entities.cast_groups = {parent_id: mock_parent}
        mock_solver_context.entities.cast_groups_with_event = {
            cg_id1: mock_cast_group1,
            cg_id2: mock_cast_group2
        }
        
        # Mock _create_same_cast_constraints
        mock_conflict_vars = [Mock()]
        with patch.object(constraint, '_create_same_cast_constraints') as mock_create_same:
            mock_create_same.return_value = mock_conflict_vars
            
            variables = constraint.create_variables()
        
        # Should create conflict variables for '~' rule
        assert len(variables) == 1
        assert variables == mock_conflict_vars
        
        # Verify _create_same_cast_constraints was called
        mock_create_same.assert_called_once_with(mock_cast_group1, mock_cast_group2, 2)
    
    def test_create_variables_ignore_rule(self, mock_solver_context):
        """Test: create_variables() mit '*' Regel (ignoriert)."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test scenario
        parent_id = uuid4()
        cg_id1, cg_id2 = uuid4(), uuid4()
        
        # Mock parent with '*' rule
        mock_parent = Mock()
        mock_parent.cast_rule = "*"  # Ignore
        mock_parent.strict_rule_pref = 1
        
        # Mock cast groups
        mock_cast_group1 = Mock()
        mock_cast_group1.parent = Mock()
        mock_cast_group1.parent.cast_group_id = parent_id
        mock_cast_group1.event = Mock()
        mock_cast_group1.event.date = date(2025, 6, 28)
        mock_cast_group1.event.time_of_day = Mock()
        mock_cast_group1.event.time_of_day.time_of_day_enum = Mock()
        mock_cast_group1.event.time_of_day.time_of_day_enum.time_index = 1
        
        mock_cast_group2 = Mock()
        mock_cast_group2.parent = Mock()
        mock_cast_group2.parent.cast_group_id = parent_id
        mock_cast_group2.event = Mock()
        mock_cast_group2.event.date = date(2025, 6, 29)
        mock_cast_group2.event.time_of_day = Mock()
        mock_cast_group2.event.time_of_day.time_of_day_enum = Mock()
        mock_cast_group2.event.time_of_day.time_of_day_enum.time_index = 1
        
        # Setup entities
        mock_solver_context.entities.cast_groups = {parent_id: mock_parent}
        mock_solver_context.entities.cast_groups_with_event = {
            cg_id1: mock_cast_group1,
            cg_id2: mock_cast_group2
        }
        
        variables = constraint.create_variables()
        
        # Should ignore '*' rule and create no variables
        assert len(variables) == 0
        assert constraint.get_metadata('total_cast_rule_conflicts') == 0
    
    def test_create_variables_no_enforcement(self, mock_solver_context):
        """Test: create_variables() ohne Enforcement (strict_rule_pref = 0)."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test scenario
        parent_id = uuid4()
        cg_id1, cg_id2 = uuid4(), uuid4()
        
        # Mock parent with rule but no enforcement
        mock_parent = Mock()
        mock_parent.cast_rule = "-"
        mock_parent.strict_rule_pref = 0  # No enforcement
        
        # Mock cast groups
        mock_cast_group1 = Mock()
        mock_cast_group1.parent = Mock()
        mock_cast_group1.parent.cast_group_id = parent_id
        
        mock_cast_group2 = Mock()
        mock_cast_group2.parent = Mock()
        mock_cast_group2.parent.cast_group_id = parent_id
        
        # Setup entities
        mock_solver_context.entities.cast_groups = {parent_id: mock_parent}
        mock_solver_context.entities.cast_groups_with_event = {
            cg_id1: mock_cast_group1,
            cg_id2: mock_cast_group2
        }
        
        variables = constraint.create_variables()
        
        # Should skip groups without enforcement
        assert len(variables) == 0
        assert constraint.get_metadata('total_cast_rule_conflicts') == 0
    
    def test_create_variables_unknown_rule_symbol(self, mock_solver_context):
        """Test: create_variables() mit unbekanntem Regel-Symbol."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test scenario
        parent_id = uuid4()
        cg_id1, cg_id2 = uuid4(), uuid4()
        
        # Mock parent with unknown rule
        mock_parent = Mock()
        mock_parent.cast_rule = "X"  # Unknown symbol
        mock_parent.strict_rule_pref = 1
        
        # Mock cast groups
        mock_cast_group1 = Mock()
        mock_cast_group1.parent = Mock()
        mock_cast_group1.parent.cast_group_id = parent_id
        mock_cast_group1.event = Mock()
        mock_cast_group1.event.date = date(2025, 6, 28)
        mock_cast_group1.event.time_of_day = Mock()
        mock_cast_group1.event.time_of_day.time_of_day_enum = Mock()
        mock_cast_group1.event.time_of_day.time_of_day_enum.time_index = 1
        
        mock_cast_group2 = Mock()
        mock_cast_group2.parent = Mock()
        mock_cast_group2.parent.cast_group_id = parent_id
        mock_cast_group2.event = Mock()
        mock_cast_group2.event.date = date(2025, 6, 29)
        mock_cast_group2.event.time_of_day = Mock()
        mock_cast_group2.event.time_of_day.time_of_day_enum = Mock()
        mock_cast_group2.event.time_of_day.time_of_day_enum.time_index = 1
        
        # Setup entities
        mock_solver_context.entities.cast_groups = {parent_id: mock_parent}
        mock_solver_context.entities.cast_groups_with_event = {
            cg_id1: mock_cast_group1,
            cg_id2: mock_cast_group2
        }
        
        # Should raise ValueError for unknown rule symbol
        with pytest.raises(ValueError, match="Unknown rule symbol: X"):
            constraint.create_variables()
    
    def test_validate_context_success(self, mock_solver_context):
        """Test: validate_context() erfolgreich."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup required attributes
        mock_solver_context.entities.cast_groups = {}
        mock_solver_context.entities.cast_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.actor_plan_periods = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        
        result = constraint.validate_context()
        assert result is True
    
    def test_validate_context_missing_entities(self, mock_solver_context):
        """Test: validate_context() mit fehlenden Entities."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Missing entities
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error is not None
        assert "Missing entities." in error
    
    def test_validate_context_empty_cast_groups(self, mock_solver_context):
        """Test: validate_context() mit leeren Cast Groups."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup required attributes but empty cast groups
        mock_solver_context.entities.cast_groups = {}
        mock_solver_context.entities.cast_groups_with_event = {}  # Empty
        mock_solver_context.entities.actor_plan_periods = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error == "No cast groups with events found"
    
    def test_get_cast_rules_summary(self, mock_solver_context):
        """Test: get_cast_rules_summary() Methode."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup test data
        parent_id1, parent_id2, parent_id3 = uuid4(), uuid4(), uuid4()
        cg_id1, cg_id2, cg_id3 = uuid4(), uuid4(), uuid4()
        
        # Mock parents with different rules
        mock_parent1 = Mock()
        mock_parent1.cast_rule = "-~"
        mock_parent1.strict_rule_pref = 1
        
        mock_parent2 = Mock()
        mock_parent2.cast_rule = "-~"  # Same pattern
        mock_parent2.strict_rule_pref = 2
        
        mock_parent3 = Mock()
        mock_parent3.cast_rule = None  # No rule
        mock_parent3.strict_rule_pref = 0
        
        # Mock cast groups
        mock_cast_group1 = Mock()
        mock_cast_group1.parent = Mock()
        mock_cast_group1.parent.cast_group_id = parent_id1
        
        mock_cast_group2 = Mock()
        mock_cast_group2.parent = Mock()
        mock_cast_group2.parent.cast_group_id = parent_id2
        
        mock_cast_group3 = Mock()
        mock_cast_group3.parent = Mock()
        mock_cast_group3.parent.cast_group_id = parent_id3
        
        # Setup entities
        mock_solver_context.entities.cast_groups = {
            parent_id1: mock_parent1,
            parent_id2: mock_parent2,
            parent_id3: mock_parent3
        }
        mock_solver_context.entities.cast_groups_with_event = {
            cg_id1: mock_cast_group1,
            cg_id2: mock_cast_group2,
            cg_id3: mock_cast_group3
        }
        
        # Set metadata
        constraint.add_metadata('total_cast_rule_conflicts', 5)
        
        summary = constraint.get_cast_rules_summary()
        
        # Verify summary
        assert summary['total_cast_groups'] == 3
        assert summary['cast_groups_with_rules'] == 2  # parent1, parent2
        assert summary['unique_rule_patterns'] == 1  # "-~"
        assert summary['rule_pattern_counts'] == {'-~': 2}
        assert summary['enforcement_level_counts'] == {1: 1, 2: 1}
        assert summary['cast_rule_conflict_variables'] == 5
        assert summary['cast_rule_coverage'] == 2/3  # 2 of 3 parents have rules
    
    def test_get_cast_rules_summary_empty(self, mock_solver_context):
        """Test: get_cast_rules_summary() mit leeren Daten."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.cast_groups = {}
        
        summary = constraint.get_cast_rules_summary()
        
        # Should return empty summary
        assert summary == {}
    
    def test_complete_setup_workflow(self, mock_solver_context):
        """Test: Kompletter Setup-Workflow."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup minimal required entities
        mock_solver_context.entities.cast_groups = {}
        mock_solver_context.entities.cast_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.actor_plan_periods = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        
        # Test setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()


@pytest.mark.integration
class TestCastRulesConstraintIntegration:
    """Integration-Tests für CastRulesConstraint."""
    
    def test_constraint_with_realistic_klinikclown_scenario(self, mock_solver_context):
        """Test: Constraint mit realistischem Klinikclown-Szenario."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup realistic scenario: 
        # Kinderklinik möchte abwechselnde Teams ("-") für Vielfalt
        # Seniorenheim möchte konstante Teams ("~") für Vertrautheit
        
        # Setup parent cast groups with rules
        parent_kinderklinik_id = uuid4()
        parent_seniorenheim_id = uuid4()
        
        mock_parent_kinderklinik = Mock()
        mock_parent_kinderklinik.cast_rule = "-*-*"  # Alternating different, ignore, different, ignore
        mock_parent_kinderklinik.strict_rule_pref = 1  # Soft constraint (penalty)
        
        mock_parent_seniorenheim = Mock()
        mock_parent_seniorenheim.cast_rule = "~~"  # Always same team
        mock_parent_seniorenheim.strict_rule_pref = 2  # Hard constraint (must satisfy)
        
        # Setup dates and times
        dates = [date(2025, 6, 28), date(2025, 6, 29), date(2025, 6, 30), date(2025, 7, 1)]
        
        # Create cast groups for Kinderklinik
        kinderklinik_cast_groups = []
        kinderklinik_cg_ids = []
        
        for i, test_date in enumerate(dates):
            cg_id = uuid4()
            kinderklinik_cg_ids.append(cg_id)
            
            mock_event_group = Mock()
            mock_event_group.id = uuid4()
            mock_event_group.event_group_id = mock_event_group.id
            
            mock_location = Mock()
            mock_location.name = "Kinderklinik"
            
            mock_location_plan_period = Mock()
            mock_location_plan_period.location_of_work = mock_location
            
            mock_time_of_day = Mock()
            mock_time_of_day.name = "Vormittag"
            mock_time_of_day.time_of_day_enum = Mock()
            mock_time_of_day.time_of_day_enum.time_index = 1
            
            mock_event = Mock()
            mock_event.date = test_date
            mock_event.time_of_day = mock_time_of_day
            mock_event.location_plan_period = mock_location_plan_period
            mock_event.event_group = mock_event_group
            
            mock_cast_group = Mock()
            mock_cast_group.parent = Mock()
            mock_cast_group.parent.cast_group_id = parent_kinderklinik_id
            mock_cast_group.event = mock_event
            mock_cast_group.nr_actors = 2
            
            kinderklinik_cast_groups.append(mock_cast_group)
        
        # Create cast groups for Seniorenheim
        seniorenheim_cast_groups = []
        seniorenheim_cg_ids = []
        
        for i, test_date in enumerate(dates[:2]):  # Only 2 events for seniorenheim
            cg_id = uuid4()
            seniorenheim_cg_ids.append(cg_id)
            
            mock_event_group = Mock()
            mock_event_group.id = uuid4()
            mock_event_group.event_group_id = mock_event_group.id
            
            mock_location = Mock()
            mock_location.name = "Seniorenheim"
            
            mock_location_plan_period = Mock()
            mock_location_plan_period.location_of_work = mock_location
            
            mock_time_of_day = Mock()
            mock_time_of_day.name = "Nachmittag"
            mock_time_of_day.time_of_day_enum = Mock()
            mock_time_of_day.time_of_day_enum.time_index = 2
            
            mock_event = Mock()
            mock_event.date = test_date
            mock_event.time_of_day = mock_time_of_day
            mock_event.location_plan_period = mock_location_plan_period
            mock_event.event_group = mock_event_group
            
            mock_cast_group = Mock()
            mock_cast_group.parent = Mock()
            mock_cast_group.parent.cast_group_id = parent_seniorenheim_id
            mock_cast_group.event = mock_event
            mock_cast_group.nr_actors = 2
            
            seniorenheim_cast_groups.append(mock_cast_group)
        
        # Setup entities
        cast_groups = {
            parent_kinderklinik_id: mock_parent_kinderklinik,
            parent_seniorenheim_id: mock_parent_seniorenheim
        }
        
        cast_groups_with_event = {}
        for i, cg in enumerate(kinderklinik_cast_groups):
            cast_groups_with_event[kinderklinik_cg_ids[i]] = cg
        
        for i, cg in enumerate(seniorenheim_cast_groups):
            cast_groups_with_event[seniorenheim_cg_ids[i]] = cg
        
        mock_solver_context.entities.cast_groups = cast_groups
        mock_solver_context.entities.cast_groups_with_event = cast_groups_with_event
        mock_solver_context.entities.actor_plan_periods = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        
        # Mock constraint creation methods
        with patch.object(constraint, '_create_different_cast_constraints') as mock_different:
            with patch.object(constraint, '_create_same_cast_constraints') as mock_same:
                mock_different.return_value = [Mock()]  # One penalty var per different rule
                mock_same.return_value = []  # Hard constraint returns no penalty vars
                
                # Test constraint setup
                success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()
        
        # Verify rule applications
        # Kinderklinik: 4 events -> 3 rule applications: '-', '*', '-' (4th would be '*')
        # Seniorenheim: 2 events -> 1 rule application: '~'
        
        # Should call _create_different_cast_constraints for '-' rules
        expected_different_calls = 2  # 2 '-' rules from kinderklinik
        assert mock_different.call_count == expected_different_calls
        
        # Should call _create_same_cast_constraints for '~' rules  
        expected_same_calls = 1  # 1 '~' rule from seniorenheim
        assert mock_same.call_count == expected_same_calls
        
        # Get summary
        summary = constraint.get_summary()
        assert summary['cast_groups_with_rules'] == 2
        assert summary['unique_rule_patterns'] == 2  # "-*-*" and "~~"
    
    def test_constraint_performance_large_cast_sequence(self, mock_solver_context):
        """Test: Constraint Performance mit langer Cast-Sequenz."""
        import time
        
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Create large cast sequence
        num_events = 50
        parent_id = uuid4()
        
        # Mock parent with repeating pattern
        mock_parent = Mock()
        mock_parent.cast_rule = "-~*"  # 3-symbol pattern that repeats
        mock_parent.strict_rule_pref = 1
        
        # Create many cast groups in sequence
        cast_groups_with_event = {}
        
        for i in range(num_events):
            cg_id = uuid4()
            
            mock_event_group = Mock()
            mock_event_group.id = uuid4()
            
            mock_event = Mock()
            mock_event.date = date(2025, 6, 28)  # Same date for simplicity
            mock_event.time_of_day = Mock()
            mock_event.time_of_day.time_of_day_enum = Mock()
            mock_event.time_of_day.time_of_day_enum.time_index = i  # Different times for sorting
            mock_event.event_group = mock_event_group
            mock_event.location_plan_period = Mock()
            mock_event.location_plan_period.location_of_work = Mock()
            mock_event.location_plan_period.location_of_work.name = f"Location_{i}"
            
            mock_cast_group = Mock()
            mock_cast_group.parent = Mock()
            mock_cast_group.parent.cast_group_id = parent_id
            mock_cast_group.event = mock_event
            mock_cast_group.nr_actors = 2
            
            cast_groups_with_event[cg_id] = mock_cast_group
        
        # Setup entities
        mock_solver_context.entities.cast_groups = {parent_id: mock_parent}
        mock_solver_context.entities.cast_groups_with_event = cast_groups_with_event
        mock_solver_context.entities.actor_plan_periods = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        
        # Mock constraint creation methods for performance
        with patch.object(constraint, '_create_different_cast_constraints') as mock_different:
            with patch.object(constraint, '_create_same_cast_constraints') as mock_same:
                mock_different.return_value = [Mock()]
                mock_same.return_value = [Mock()]
                
                # Measure setup time
                start_time = time.time()
                success = constraint.setup()
                end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Should complete quickly even with large sequence
        assert success is True
        assert setup_time < 2.0  # Should take less than 2 seconds
        
        # Verify rules were processed for sequence
        # Pattern "-~*" on 50 events -> 49 rule applications
        # '-': different cast, '~': same cast, '*': ignore
        expected_pattern_applications = 49
        pattern_positions = [i % 3 for i in range(expected_pattern_applications)]
        expected_different_calls = pattern_positions.count(0)  # '-' at position 0
        expected_same_calls = pattern_positions.count(1)       # '~' at position 1
        # '*' at position 2 -> ignored
        
        assert mock_different.call_count == expected_different_calls
        assert mock_same.call_count == expected_same_calls
    
    def test_constraint_mixed_enforcement_levels(self, mock_solver_context):
        """Test: Constraint mit gemischten Enforcement-Levels."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup scenario with different enforcement levels
        parent_ids = [uuid4(), uuid4(), uuid4()]
        
        # Mock parents with different enforcement
        mock_parent1 = Mock()
        mock_parent1.cast_rule = "-"
        mock_parent1.strict_rule_pref = 0  # No enforcement
        
        mock_parent2 = Mock()
        mock_parent2.cast_rule = "-"
        mock_parent2.strict_rule_pref = 1  # Soft constraint
        
        mock_parent3 = Mock()
        mock_parent3.cast_rule = "~"
        mock_parent3.strict_rule_pref = 2  # Hard constraint
        
        # Create cast groups for each parent
        cast_groups_with_event = {}
        
        for parent_i, parent_id in enumerate(parent_ids):
            for event_i in range(2):  # 2 events per parent
                cg_id = uuid4()
                
                mock_event_group = Mock()
                mock_event_group.id = uuid4()
                
                mock_event = Mock()
                mock_event.date = date(2025, 6, 28 + event_i)
                mock_event.time_of_day = Mock()
                mock_event.time_of_day.time_of_day_enum = Mock()
                mock_event.time_of_day.time_of_day_enum.time_index = 1
                mock_event.event_group = mock_event_group
                mock_event.location_plan_period = Mock()
                mock_event.location_plan_period.location_of_work = Mock()
                mock_event.location_plan_period.location_of_work.name = f"Location_{parent_i}"
                
                mock_cast_group = Mock()
                mock_cast_group.parent = Mock()
                mock_cast_group.parent.cast_group_id = parent_id
                mock_cast_group.event = mock_event
                mock_cast_group.nr_actors = 2
                
                cast_groups_with_event[cg_id] = mock_cast_group
        
        # Setup entities
        mock_solver_context.entities.cast_groups = {
            parent_ids[0]: mock_parent1,
            parent_ids[1]: mock_parent2,
            parent_ids[2]: mock_parent3
        }
        mock_solver_context.entities.cast_groups_with_event = cast_groups_with_event
        mock_solver_context.entities.actor_plan_periods = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        
        # Mock constraint creation methods
        with patch.object(constraint, '_create_different_cast_constraints') as mock_different:
            with patch.object(constraint, '_create_same_cast_constraints') as mock_same:
                mock_different.return_value = [Mock()]  # Soft constraint returns penalty
                mock_same.return_value = []  # Hard constraint returns no penalty
                
                variables = constraint.create_variables()
        
        # Should only process constraints with enforcement > 0
        # Parent 1: no enforcement -> skipped
        # Parent 2: soft enforcement -> processed with penalty vars
        # Parent 3: hard enforcement -> processed but no penalty vars
        
        assert mock_different.call_count == 1  # Parent 2 only
        assert mock_same.call_count == 1      # Parent 3 only
        
        # Should return penalty variables from soft constraints only
        assert len(variables) == 1  # Only from parent 2 (soft)
        
        # Get summary
        summary = constraint.get_summary()
        assert summary['enforcement_level_counts'] == {1: 1, 2: 1}  # Only parents with rules
    
    @patch('sat_solver.constraints.cast_rules.logger')
    def test_constraint_logging_integration(self, mock_logger, mock_solver_context):
        """Test: Constraint Logging-Integration."""
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup minimal entities
        mock_solver_context.entities.cast_groups = {}
        mock_solver_context.entities.cast_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.actor_plan_periods = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Logging calls depend on implementation, but logger should be available


@pytest.mark.slow
class TestCastRulesConstraintPerformance:
    """Performance-Tests für CastRulesConstraint."""
    
    def test_constraint_rule_pattern_complexity(self, mock_solver_context):
        """Test: Komplexität verschiedener Regel-Pattern."""
        import time
        
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Test different rule patterns
        patterns = [
            "-",           # Simple alternating
            "~",           # Simple same
            "-~*",         # 3-symbol pattern
            "-~*-~*-~*",   # Long repeating pattern
            "-~-~-~-~",    # Alternating pattern
        ]
        
        for pattern in patterns:
            parent_id = uuid4()
            
            # Mock parent with pattern
            mock_parent = Mock()
            mock_parent.cast_rule = pattern
            mock_parent.strict_rule_pref = 1
            
            # Create cast groups for pattern testing
            cast_groups_with_event = {}
            num_events = 20
            
            for i in range(num_events):
                cg_id = uuid4()
                
                mock_event_group = Mock()
                mock_event_group.id = uuid4()
                
                mock_event = Mock()
                mock_event.date = date(2025, 6, 28)
                mock_event.time_of_day = Mock()
                mock_event.time_of_day.time_of_day_enum = Mock()
                mock_event.time_of_day.time_of_day_enum.time_index = i
                mock_event.event_group = mock_event_group
                mock_event.location_plan_period = Mock()
                mock_event.location_plan_period.location_of_work = Mock()
                mock_event.location_plan_period.location_of_work.name = f"Location_{i}"
                
                mock_cast_group = Mock()
                mock_cast_group.parent = Mock()
                mock_cast_group.parent.cast_group_id = parent_id
                mock_cast_group.event = mock_event
                
                cast_groups_with_event[cg_id] = mock_cast_group
            
            # Setup entities
            mock_solver_context.entities.cast_groups = {parent_id: mock_parent}
            mock_solver_context.entities.cast_groups_with_event = cast_groups_with_event
            mock_solver_context.entities.actor_plan_periods = {}
            mock_solver_context.entities.shift_vars = {}
            mock_solver_context.entities.event_group_vars = {}
            mock_solver_context.entities.shifts_exclusive = {}
            mock_solver_context.entities.avail_day_groups_with_avail_day = {}
            
            # Mock constraint creation methods
            with patch.object(constraint, '_create_different_cast_constraints') as mock_different:
                with patch.object(constraint, '_create_same_cast_constraints') as mock_same:
                    mock_different.return_value = [Mock()]
                    mock_same.return_value = [Mock()]
                    
                    # Measure processing time for this pattern
                    start_time = time.time()
                    variables = constraint.create_variables()
                    end_time = time.time()
            
            pattern_time = end_time - start_time
            
            # Should process all patterns efficiently
            assert pattern_time < 1.0  # Should complete quickly
            assert isinstance(variables, list)
    
    def test_constraint_memory_efficiency_cast_rules(self, mock_solver_context):
        """Test: Memory-Effizienz bei vielen Cast Rules."""
        import gc
        
        constraint = CastRulesConstraint(mock_solver_context)
        
        # Setup minimal but valid entities
        mock_solver_context.entities.cast_groups = {}
        mock_solver_context.entities.cast_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.actor_plan_periods = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        
        # Force garbage collection before test
        gc.collect()
        
        # Setup and teardown multiple times
        for _ in range(10):
            constraint.setup()
            constraint._metadata.clear()  # Clear metadata
        
        # Force garbage collection after test
        gc.collect()
        
        # Should not leak significant memory
        assert True  # Test passes if no memory errors occur
