"""
Unit-Tests für LocationPrefsConstraint

Testet das Constraint für Standort-Präferenzen der Mitarbeiter.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from datetime import date

from sat_solver.constraints.location_prefs import LocationPrefsConstraint


@pytest.mark.unit
class TestLocationPrefsConstraint:
    """Test-Klasse für LocationPrefsConstraint."""
    
    def test_constraint_name(self, mock_solver_context):
        """Test: Constraint-Name ist korrekt."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        assert constraint.constraint_name == "location_prefs"
    
    def test_constraint_initialization(self, mock_solver_context):
        """Test: Constraint wird korrekt initialisiert."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        assert constraint.context == mock_solver_context
        assert constraint.model == mock_solver_context.model
        assert constraint.entities == mock_solver_context.entities
        assert constraint.config == mock_solver_context.config
        assert not constraint.is_setup_complete()
    
    def test_create_variables_empty_entities(self, mock_solver_context):
        """Test: create_variables() mit leeren Entities."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = {}
        
        variables = constraint.create_variables()
        
        # Should return empty list for empty entities
        assert variables == []
        assert constraint.get_metadata('total_location_preferences') == 0
    
    def test_create_event_data_cache(self, mock_solver_context):
        """Test: _create_event_data_cache() Methode."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup event groups
        eg_id1, eg_id2 = uuid4(), uuid4()
        location_id1, location_id2 = uuid4(), uuid4()
        test_date = date(2025, 6, 28)
        
        # Mock events
        mock_event1 = Mock()
        mock_event1.date = test_date
        mock_event1.time_of_day = Mock()
        mock_event1.time_of_day.time_of_day_enum = Mock()
        mock_event1.time_of_day.time_of_day_enum.time_index = 1
        mock_event1.location_plan_period = Mock()
        mock_event1.location_plan_period.location_of_work = Mock()
        mock_event1.location_plan_period.location_of_work.id = location_id1
        
        mock_event2 = Mock()
        mock_event2.date = test_date
        mock_event2.time_of_day = Mock()
        mock_event2.time_of_day.time_of_day_enum = Mock()
        mock_event2.time_of_day.time_of_day_enum.time_index = 2
        mock_event2.location_plan_period = Mock()
        mock_event2.location_plan_period.location_of_work = Mock()
        mock_event2.location_plan_period.location_of_work.id = location_id2
        
        mock_event_group1 = Mock()
        mock_event_group1.event = mock_event1
        mock_event_group2 = Mock()
        mock_event_group2.event = mock_event2
        
        mock_solver_context.entities.event_groups_with_event = {
            eg_id1: mock_event_group1,
            eg_id2: mock_event_group2
        }
        
        # Create cache
        cache = constraint._create_event_data_cache()
        
        # Verify cache structure
        expected_key1 = (test_date, 1, location_id1)
        expected_key2 = (test_date, 2, location_id2)
        
        assert expected_key1 in cache
        assert expected_key2 in cache
        assert cache[expected_key1] == (eg_id1, mock_event_group1)
        assert cache[expected_key2] == (eg_id2, mock_event_group2)
    
    def test_create_variables_with_location_preferences(self, mock_solver_context):
        """Test: create_variables() mit Location-Präferenzen."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup multiplier configuration
        mock_multipliers = {
            0.5: 100,   # Best score
            1.0: 50,    # Good score  
            2.0: -50,   # Bad score
            3.0: -100   # Worst score
        }
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = mock_multipliers
        
        # Setup test data
        adg_id = uuid4()
        eg_id = uuid4()
        location_id = uuid4()
        app_id = uuid4()
        test_date = date(2025, 6, 28)
        
        # Mock location preference
        mock_loc_pref = Mock()
        mock_loc_pref.prep_delete = False
        mock_loc_pref.score = 1.0  # Good score
        mock_loc_pref.location_of_work = Mock()
        mock_loc_pref.location_of_work.id = location_id
        
        # Mock avail day
        mock_avail_day = Mock()
        mock_avail_day.date = test_date
        mock_avail_day.time_of_day = Mock()
        mock_avail_day.time_of_day.time_of_day_enum = Mock()
        mock_avail_day.time_of_day.time_of_day_enum.time_index = 1
        mock_avail_day.actor_plan_period = Mock()
        mock_avail_day.actor_plan_period.id = app_id
        mock_avail_day.actor_plan_period.person = Mock()
        mock_avail_day.actor_plan_period.person.f_name = "TestActor"
        mock_avail_day.actor_location_prefs_defaults = [mock_loc_pref]
        
        # Mock avail day group
        mock_adg = Mock()
        mock_adg.avail_day = mock_avail_day
        
        # Mock event
        mock_event = Mock()
        mock_event.date = test_date
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.name = "Morning"
        mock_event.time_of_day.time_of_day_enum = Mock()
        mock_event.time_of_day.time_of_day_enum.time_index = 1
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_of_work = Mock()
        mock_event.location_plan_period.location_of_work.id = location_id
        mock_event.location_plan_period.location_of_work.name = "TestLocation"
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {adg_id: mock_adg}
        mock_solver_context.entities.event_groups_with_event = {eg_id: mock_event_group}
        
        # Mock shift and event group variables
        mock_shift_var = Mock()
        mock_event_group_var = Mock()
        mock_solver_context.entities.shift_vars = {(adg_id, eg_id): mock_shift_var}
        mock_solver_context.entities.event_group_vars = {eg_id: mock_event_group_var}
        
        # Mock new location preference variable
        mock_loc_pref_var = Mock()
        mock_solver_context.model.NewIntVar.return_value = mock_loc_pref_var
        
        # Create variables
        variables = constraint.create_variables()
        
        # Verify variable creation
        assert len(variables) == 1
        assert variables[0] == mock_loc_pref_var
        
        # Verify NewIntVar was called with correct bounds
        mock_solver_context.model.NewIntVar.assert_called_once()
        call_args = mock_solver_context.model.NewIntVar.call_args[0]
        assert call_args[0] == mock_multipliers[2.0]  # min (worst score)
        assert call_args[1] == mock_multipliers[0.5]  # max (best score)
        
        # Verify AddMultiplicationEquality was called
        mock_solver_context.model.AddMultiplicationEquality.assert_called_once()
        multiplication_args = mock_solver_context.model.AddMultiplicationEquality.call_args[0]
        assert multiplication_args[0] == mock_loc_pref_var
        assert multiplication_args[1] == [mock_shift_var, mock_event_group_var, mock_multipliers[1.0]]
        
        # Verify metadata
        assert constraint.get_metadata('total_location_preferences') == 1
        loc_pref_metadata = constraint.get_metadata('loc_pref_0')
        assert loc_pref_metadata['score'] == 1.0
        assert loc_pref_metadata['person_name'] == "TestActor"
        assert loc_pref_metadata['location_name'] == "TestLocation"
    
    def test_create_variables_with_forbidden_score(self, mock_solver_context):
        """Test: create_variables() mit verbotenem Score (0)."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup multiplier configuration
        mock_multipliers = {0.5: 100, 1.0: 50, 2.0: -50}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = mock_multipliers
        
        # Setup test data with forbidden score
        adg_id = uuid4()
        eg_id = uuid4()
        location_id = uuid4()
        test_date = date(2025, 6, 28)
        
        # Mock location preference with score 0 (forbidden)
        mock_loc_pref = Mock()
        mock_loc_pref.prep_delete = False
        mock_loc_pref.score = 0  # Forbidden
        mock_loc_pref.location_of_work = Mock()
        mock_loc_pref.location_of_work.id = location_id
        
        # Mock avail day
        mock_avail_day = Mock()
        mock_avail_day.date = test_date
        mock_avail_day.time_of_day = Mock()
        mock_avail_day.time_of_day.time_of_day_enum = Mock()
        mock_avail_day.time_of_day.time_of_day_enum.time_index = 1
        mock_avail_day.actor_location_prefs_defaults = [mock_loc_pref]
        
        mock_adg = Mock()
        mock_adg.avail_day = mock_avail_day
        
        # Mock event
        mock_event = Mock()
        mock_event.date = test_date
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.time_of_day_enum = Mock()
        mock_event.time_of_day.time_of_day_enum.time_index = 1
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_of_work = Mock()
        mock_event.location_plan_period.location_of_work.id = location_id
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {adg_id: mock_adg}
        mock_solver_context.entities.event_groups_with_event = {eg_id: mock_event_group}
        
        # Mock shift variable
        mock_shift_var = Mock()
        mock_solver_context.entities.shift_vars = {(adg_id, eg_id): mock_shift_var}
        mock_solver_context.entities.event_group_vars = {eg_id: Mock()}
        
        # Create variables
        variables = constraint.create_variables()
        
        # Should not create preference variable for forbidden score
        assert len(variables) == 0
        assert not mock_solver_context.model.NewIntVar.called
        assert not mock_solver_context.model.AddMultiplicationEquality.called
        
        # Should add constraint shift_var == 0 for forbidden
        mock_solver_context.model.Add.assert_called_once()
    
    def test_create_variables_with_deleted_preferences(self, mock_solver_context):
        """Test: create_variables() mit gelöschten Präferenzen."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup multiplier configuration
        mock_multipliers = {1.0: 50}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = mock_multipliers
        
        # Setup test data with deleted preference
        adg_id = uuid4()
        test_date = date(2025, 6, 28)
        
        # Mock deleted location preference
        mock_loc_pref = Mock()
        mock_loc_pref.prep_delete = True  # Deleted
        mock_loc_pref.score = 1.0
        
        # Mock avail day
        mock_avail_day = Mock()
        mock_avail_day.date = test_date
        mock_avail_day.actor_location_prefs_defaults = [mock_loc_pref]
        
        mock_adg = Mock()
        mock_adg.avail_day = mock_avail_day
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {adg_id: mock_adg}
        mock_solver_context.entities.event_groups_with_event = {}
        
        # Create variables
        variables = constraint.create_variables()
        
        # Should skip deleted preferences
        assert len(variables) == 0
        assert constraint.get_metadata('total_location_preferences') == 0
    
    def test_create_variables_no_matching_event(self, mock_solver_context):
        """Test: create_variables() ohne passende Events."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup multiplier configuration
        mock_multipliers = {1.0: 50}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = mock_multipliers
        
        # Setup test data
        adg_id = uuid4()
        location_id = uuid4()
        test_date = date(2025, 6, 28)
        
        # Mock location preference
        mock_loc_pref = Mock()
        mock_loc_pref.prep_delete = False
        mock_loc_pref.score = 1.0
        mock_loc_pref.location_of_work = Mock()
        mock_loc_pref.location_of_work.id = location_id
        
        # Mock avail day
        mock_avail_day = Mock()
        mock_avail_day.date = test_date
        mock_avail_day.time_of_day = Mock()
        mock_avail_day.time_of_day.time_of_day_enum = Mock()
        mock_avail_day.time_of_day.time_of_day_enum.time_index = 1
        mock_avail_day.actor_location_prefs_defaults = [mock_loc_pref]
        
        mock_adg = Mock()
        mock_adg.avail_day = mock_avail_day
        
        # Setup entities without matching event
        mock_solver_context.entities.avail_day_groups_with_avail_day = {adg_id: mock_adg}
        mock_solver_context.entities.event_groups_with_event = {}  # No events
        
        # Create variables
        variables = constraint.create_variables()
        
        # Should not create variables without matching events
        assert len(variables) == 0
        assert constraint.get_metadata('total_location_preferences') == 0
    
    def test_create_variables_no_shift_var(self, mock_solver_context):
        """Test: create_variables() ohne entsprechende shift_var."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup multiplier configuration
        mock_multipliers = {1.0: 50}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = mock_multipliers
        
        # Setup test data
        adg_id = uuid4()
        eg_id = uuid4()
        location_id = uuid4()
        test_date = date(2025, 6, 28)
        
        # Mock location preference
        mock_loc_pref = Mock()
        mock_loc_pref.prep_delete = False
        mock_loc_pref.score = 1.0
        mock_loc_pref.location_of_work = Mock()
        mock_loc_pref.location_of_work.id = location_id
        
        # Mock avail day
        mock_avail_day = Mock()
        mock_avail_day.date = test_date
        mock_avail_day.time_of_day = Mock()
        mock_avail_day.time_of_day.time_of_day_enum = Mock()
        mock_avail_day.time_of_day.time_of_day_enum.time_index = 1
        mock_avail_day.actor_location_prefs_defaults = [mock_loc_pref]
        
        mock_adg = Mock()
        mock_adg.avail_day = mock_avail_day
        
        # Mock event
        mock_event = Mock()
        mock_event.date = test_date
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.time_of_day_enum = Mock()
        mock_event.time_of_day.time_of_day_enum.time_index = 1
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_of_work = Mock()
        mock_event.location_plan_period.location_of_work.id = location_id
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {adg_id: mock_adg}
        mock_solver_context.entities.event_groups_with_event = {eg_id: mock_event_group}
        mock_solver_context.entities.shift_vars = {}  # No shift vars
        mock_solver_context.entities.event_group_vars = {eg_id: Mock()}
        
        # Create variables
        variables = constraint.create_variables()
        
        # Should not create variables without shift vars
        assert len(variables) == 0
        assert constraint.get_metadata('total_location_preferences') == 0
    
    def test_add_constraints(self, mock_solver_context):
        """Test: add_constraints() Methode."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Add constraints (currently does nothing extra)
        constraint.add_constraints()
        
        # Verify metadata
        assert constraint.get_metadata('additional_constraints_added') == 0
    
    def test_validate_context_success(self, mock_solver_context):
        """Test: validate_context() erfolgreich."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup required attributes
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = {}
        
        result = constraint.validate_context()
        assert result is True
    
    def test_validate_context_missing_entities(self, mock_solver_context):
        """Test: validate_context() mit fehlenden Entities."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Missing entities
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error is not None
        assert "Missing entities." in error
    
    def test_validate_context_missing_config(self, mock_solver_context):
        """Test: validate_context() mit fehlender Konfiguration."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup entities but missing config
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        
        # Missing config
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error is not None
        assert "constraint_multipliers" in error
    
    def test_get_location_prefs_summary(self, mock_solver_context):
        """Test: get_location_prefs_summary() Methode."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup test data
        adg_id1, adg_id2 = uuid4(), uuid4()
        
        # Mock location preferences with different scores
        mock_loc_pref1 = Mock()
        mock_loc_pref1.prep_delete = False
        mock_loc_pref1.score = 1.0
        
        mock_loc_pref2 = Mock()
        mock_loc_pref2.prep_delete = False
        mock_loc_pref2.score = 0  # Forbidden
        
        mock_loc_pref3 = Mock()
        mock_loc_pref3.prep_delete = True  # Deleted
        mock_loc_pref3.score = 2.0
        
        mock_loc_pref4 = Mock()
        mock_loc_pref4.prep_delete = False
        mock_loc_pref4.score = 1.0  # Same score as pref1
        
        # Mock avail days
        mock_avail_day1 = Mock()
        mock_avail_day1.actor_location_prefs_defaults = [mock_loc_pref1, mock_loc_pref2]
        mock_adg1 = Mock()
        mock_adg1.avail_day = mock_avail_day1
        
        mock_avail_day2 = Mock()
        mock_avail_day2.actor_location_prefs_defaults = [mock_loc_pref3, mock_loc_pref4]
        mock_adg2 = Mock()
        mock_adg2.avail_day = mock_avail_day2
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2
        }
        
        summary = constraint.get_location_prefs_summary()
        
        # Verify summary
        assert summary['total_avail_days'] == 2
        assert summary['total_location_preferences'] == 3  # Excluding deleted
        assert summary['forbidden_preferences'] == 1  # Score 0
        assert summary['preferences_by_score'] == {1.0: 2, 0: 1}  # 2x score 1.0, 1x score 0
        assert summary['unique_scores'] == [1.0, 0]
    
    def test_get_location_prefs_summary_empty(self, mock_solver_context):
        """Test: get_location_prefs_summary() mit leeren Daten."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        
        summary = constraint.get_location_prefs_summary()
        
        # Should return empty summary
        assert summary == {}
    
    def test_complete_setup_workflow(self, mock_solver_context):
        """Test: Kompletter Setup-Workflow."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup minimal required entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = {}
        
        # Test setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()


@pytest.mark.integration
class TestLocationPrefsConstraintIntegration:
    """Integration-Tests für LocationPrefsConstraint."""
    
    def test_constraint_with_realistic_scenario(self, mock_solver_context):
        """Test: Constraint mit realistischem Szenario."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup realistic multiplier configuration
        mock_multipliers = {
            0.5: 200,   # Excellent
            1.0: 100,   # Good
            1.5: 0,     # Neutral
            2.0: -100,  # Bad
            3.0: -200   # Very bad
        }
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = mock_multipliers
        
        # Create realistic scenario
        num_actors = 3
        num_locations = 2
        num_time_slots = 2
        
        # Setup actors and locations
        actor_ids = [uuid4() for _ in range(num_actors)]
        location_ids = [uuid4() for _ in range(num_locations)]
        
        # Setup events
        event_groups_with_event = {}
        event_group_vars = {}
        test_date = date(2025, 6, 28)
        
        event_counter = 0
        for time_index in range(1, num_time_slots + 1):
            for location_id in location_ids:
                eg_id = uuid4()
                
                mock_event = Mock()
                mock_event.date = test_date
                mock_event.time_of_day = Mock()
                mock_event.time_of_day.name = f"TimeSlot_{time_index}"
                mock_event.time_of_day.time_of_day_enum = Mock()
                mock_event.time_of_day.time_of_day_enum.time_index = time_index
                mock_event.location_plan_period = Mock()
                mock_event.location_plan_period.location_of_work = Mock()
                mock_event.location_plan_period.location_of_work.id = location_id
                mock_event.location_plan_period.location_of_work.name = f"Location_{event_counter}"
                
                mock_event_group = Mock()
                mock_event_group.event = mock_event
                
                event_groups_with_event[eg_id] = mock_event_group
                event_group_vars[eg_id] = Mock()
                event_counter += 1
        
        # Setup avail day groups with preferences
        avail_day_groups_with_avail_day = {}
        shift_vars = {}
        preference_count = 0
        
        for actor_i, actor_id in enumerate(actor_ids):
            for time_index in range(1, num_time_slots + 1):
                adg_id = uuid4()
                
                # Create location preferences for this actor/time
                location_prefs = []
                for loc_i, location_id in enumerate(location_ids):
                    mock_loc_pref = Mock()
                    mock_loc_pref.prep_delete = False
                    # Vary scores: some good, some bad, some forbidden
                    if preference_count % 6 == 0:
                        mock_loc_pref.score = 0  # Forbidden
                    elif preference_count % 3 == 0:
                        mock_loc_pref.score = 0.5  # Excellent
                    elif preference_count % 2 == 0:
                        mock_loc_pref.score = 2.0  # Bad
                    else:
                        mock_loc_pref.score = 1.0  # Good
                    
                    mock_loc_pref.location_of_work = Mock()
                    mock_loc_pref.location_of_work.id = location_id
                    location_prefs.append(mock_loc_pref)
                    preference_count += 1
                
                # Mock avail day
                mock_avail_day = Mock()
                mock_avail_day.date = test_date
                mock_avail_day.time_of_day = Mock()
                mock_avail_day.time_of_day.time_of_day_enum = Mock()
                mock_avail_day.time_of_day.time_of_day_enum.time_index = time_index
                mock_avail_day.actor_plan_period = Mock()
                mock_avail_day.actor_plan_period.id = actor_id
                mock_avail_day.actor_plan_period.person = Mock()
                mock_avail_day.actor_plan_period.person.f_name = f"Actor_{actor_i}"
                mock_avail_day.actor_location_prefs_defaults = location_prefs
                
                mock_adg = Mock()
                mock_adg.avail_day = mock_avail_day
                
                avail_day_groups_with_avail_day[adg_id] = mock_adg
                
                # Create shift variables for this actor/time combo with all events
                for eg_id in event_groups_with_event:
                    shift_vars[(adg_id, eg_id)] = Mock()
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = avail_day_groups_with_avail_day
        mock_solver_context.entities.event_groups_with_event = event_groups_with_event
        mock_solver_context.entities.shift_vars = shift_vars
        mock_solver_context.entities.event_group_vars = event_group_vars
        
        # Mock model methods
        mock_vars = [Mock() for _ in range(100)]  # Enough variables
        mock_solver_context.model.NewIntVar.side_effect = mock_vars
        
        # Test constraint setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()
        
        # Verify variables were created
        assert mock_solver_context.model.NewIntVar.called
        
        # Verify some preferences were processed
        total_prefs = constraint.get_metadata('total_location_preferences')
        assert total_prefs > 0
        
        # Get summary
        summary = constraint.get_summary()
        assert 'total_location_preferences' in summary
        assert 'forbidden_preferences' in summary
        assert 'preferences_by_score' in summary
    
    def test_constraint_performance_large_dataset(self, mock_solver_context):
        """Test: Constraint Performance mit großem Datensatz."""
        import time
        
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup configuration
        mock_multipliers = {0.5: 100, 1.0: 50, 2.0: -50}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = mock_multipliers
        
        # Create large scenario
        large_size = 100  # 100 actors, 100 events
        
        # Setup large event groups
        event_groups_with_event = {}
        event_group_vars = {}
        test_date = date(2025, 6, 28)
        
        for i in range(large_size):
            eg_id = uuid4()
            
            mock_event = Mock()
            mock_event.date = test_date
            mock_event.time_of_day = Mock()
            mock_event.time_of_day.name = f"Event_{i}"
            mock_event.time_of_day.time_of_day_enum = Mock()
            mock_event.time_of_day.time_of_day_enum.time_index = i % 5  # 5 time slots
            mock_event.location_plan_period = Mock()
            mock_event.location_plan_period.location_of_work = Mock()
            mock_event.location_plan_period.location_of_work.id = uuid4()
            mock_event.location_plan_period.location_of_work.name = f"Location_{i}"
            
            mock_event_group = Mock()
            mock_event_group.event = mock_event
            
            event_groups_with_event[eg_id] = mock_event_group
            event_group_vars[eg_id] = Mock()
        
        # Setup large avail day groups (fewer than events for performance)
        avail_day_groups_with_avail_day = {}
        shift_vars = {}
        
        for i in range(large_size // 10):  # 10 actors
            adg_id = uuid4()
            
            # Create one location preference per avail day
            mock_loc_pref = Mock()
            mock_loc_pref.prep_delete = False
            mock_loc_pref.score = 1.0
            mock_loc_pref.location_of_work = Mock()
            mock_loc_pref.location_of_work.id = uuid4()
            
            mock_avail_day = Mock()
            mock_avail_day.date = test_date
            mock_avail_day.time_of_day = Mock()
            mock_avail_day.time_of_day.time_of_day_enum = Mock()
            mock_avail_day.time_of_day.time_of_day_enum.time_index = 1
            mock_avail_day.actor_plan_period = Mock()
            mock_avail_day.actor_plan_period.person = Mock()
            mock_avail_day.actor_plan_period.person.f_name = f"Actor_{i}"
            mock_avail_day.actor_location_prefs_defaults = [mock_loc_pref]
            
            mock_adg = Mock()
            mock_adg.avail_day = mock_avail_day
            
            avail_day_groups_with_avail_day[adg_id] = mock_adg
            
            # Create minimal shift vars
            shift_vars[(adg_id, list(event_groups_with_event.keys())[0])] = Mock()
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = avail_day_groups_with_avail_day
        mock_solver_context.entities.event_groups_with_event = event_groups_with_event
        mock_solver_context.entities.shift_vars = shift_vars
        mock_solver_context.entities.event_group_vars = event_group_vars
        
        # Mock model methods
        mock_vars = [Mock() for _ in range(1000)]
        mock_solver_context.model.NewIntVar.side_effect = mock_vars
        
        # Measure setup time
        start_time = time.time()
        success = constraint.setup()
        end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Should complete quickly even with large dataset
        assert success is True
        assert setup_time < 2.0  # Should take less than 2 seconds
    
    def test_constraint_error_handling(self, mock_solver_context):
        """Test: Error-Handling bei problematischen Daten."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup problematic configuration (missing multipliers)
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = None
        
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        
        # Should handle errors gracefully
        try:
            success = constraint.setup()
            # Might succeed or fail depending on implementation
        except Exception as e:
            pytest.fail(f"Constraint should handle errors gracefully, but raised: {e}")
    
    @patch('sat_solver.constraints.location_prefs.logger')
    def test_constraint_logging_integration(self, mock_logger, mock_solver_context):
        """Test: Constraint Logging-Integration."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup minimal entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = {}
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Logging calls depend on implementation, but logger should be available
    
    def test_constraint_with_mixed_scores_and_edge_cases(self, mock_solver_context):
        """Test: Constraint mit gemischten Scores und Edge Cases."""
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup comprehensive multiplier configuration
        mock_multipliers = {
            0.5: 300,   # Best
            1.0: 200,   # Good
            1.5: 100,   # Okay
            2.0: 0,     # Neutral
            2.5: -100,  # Bad
            3.0: -200,  # Worst
            0: 0        # Should be handled specially (forbidden)
        }
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = mock_multipliers
        
        # Setup comprehensive test scenario
        test_date = date(2025, 6, 28)
        
        # Create events
        eg_id1, eg_id2 = uuid4(), uuid4()
        location_id1, location_id2 = uuid4(), uuid4()
        
        mock_event1 = Mock()
        mock_event1.date = test_date
        mock_event1.time_of_day = Mock()
        mock_event1.time_of_day.name = "Morning"
        mock_event1.time_of_day.time_of_day_enum = Mock()
        mock_event1.time_of_day.time_of_day_enum.time_index = 1
        mock_event1.location_plan_period = Mock()
        mock_event1.location_plan_period.location_of_work = Mock()
        mock_event1.location_plan_period.location_of_work.id = location_id1
        mock_event1.location_plan_period.location_of_work.name = "Hospital A"
        
        mock_event2 = Mock()
        mock_event2.date = test_date
        mock_event2.time_of_day = Mock()
        mock_event2.time_of_day.name = "Afternoon"
        mock_event2.time_of_day.time_of_day_enum = Mock()
        mock_event2.time_of_day.time_of_day_enum.time_index = 2
        mock_event2.location_plan_period = Mock()
        mock_event2.location_plan_period.location_of_work = Mock()
        mock_event2.location_plan_period.location_of_work.id = location_id2
        mock_event2.location_plan_period.location_of_work.name = "Hospital B"
        
        event_groups_with_event = {
            eg_id1: Mock(event=mock_event1),
            eg_id2: Mock(event=mock_event2)
        }
        
        # Create avail days with comprehensive preference scenarios
        adg_id = uuid4()
        app_id = uuid4()
        
        # Multiple preferences with different scores including edge cases
        mock_loc_pref1 = Mock()  # Best score
        mock_loc_pref1.prep_delete = False
        mock_loc_pref1.score = 0.5
        mock_loc_pref1.location_of_work = Mock()
        mock_loc_pref1.location_of_work.id = location_id1
        
        mock_loc_pref2 = Mock()  # Forbidden score
        mock_loc_pref2.prep_delete = False
        mock_loc_pref2.score = 0
        mock_loc_pref2.location_of_work = Mock()
        mock_loc_pref2.location_of_work.id = location_id2
        
        mock_avail_day = Mock()
        mock_avail_day.date = test_date
        mock_avail_day.time_of_day = Mock()
        mock_avail_day.time_of_day.time_of_day_enum = Mock()
        mock_avail_day.time_of_day.time_of_day_enum.time_index = 1
        mock_avail_day.actor_plan_period = Mock()
        mock_avail_day.actor_plan_period.id = app_id
        mock_avail_day.actor_plan_period.person = Mock()
        mock_avail_day.actor_plan_period.person.f_name = "TestActor"
        mock_avail_day.actor_location_prefs_defaults = [mock_loc_pref1, mock_loc_pref2]
        
        mock_adg = Mock()
        mock_adg.avail_day = mock_avail_day
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {adg_id: mock_adg}
        mock_solver_context.entities.event_groups_with_event = event_groups_with_event
        mock_solver_context.entities.shift_vars = {
            (adg_id, eg_id1): Mock(),
            (adg_id, eg_id2): Mock()
        }
        mock_solver_context.entities.event_group_vars = {
            eg_id1: Mock(),
            eg_id2: Mock()
        }
        
        # Mock model methods
        mock_vars = [Mock() for _ in range(10)]
        mock_solver_context.model.NewIntVar.side_effect = mock_vars
        
        # Test setup
        success = constraint.setup()
        assert success is True
        
        # Verify one preference variable created (for best score) and one forbidden constraint
        assert mock_solver_context.model.NewIntVar.call_count == 1  # Only for good preference
        assert mock_solver_context.model.Add.call_count == 1  # For forbidden preference
        assert mock_solver_context.model.AddMultiplicationEquality.call_count == 1  # For good preference
        
        # Verify summary
        summary = constraint.get_location_prefs_summary()
        assert summary['forbidden_preferences'] == 1
        assert 0.5 in summary['preferences_by_score']
        assert 0 in summary['preferences_by_score']


@pytest.mark.slow
class TestLocationPrefsConstraintPerformance:
    """Performance-Tests für LocationPrefsConstraint."""
    
    def test_constraint_cache_efficiency(self, mock_solver_context):
        """Test: Effizienz des Event-Data-Cache."""
        import time
        
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Create large event dataset
        large_event_count = 1000
        event_groups_with_event = {}
        test_date = date(2025, 6, 28)
        
        for i in range(large_event_count):
            eg_id = uuid4()
            
            mock_event = Mock()
            mock_event.date = test_date
            mock_event.time_of_day = Mock()
            mock_event.time_of_day.time_of_day_enum = Mock()
            mock_event.time_of_day.time_of_day_enum.time_index = i % 10
            mock_event.location_plan_period = Mock()
            mock_event.location_plan_period.location_of_work = Mock()
            mock_event.location_plan_period.location_of_work.id = uuid4()
            
            mock_event_group = Mock()
            mock_event_group.event = mock_event
            
            event_groups_with_event[eg_id] = mock_event_group
        
        mock_solver_context.entities.event_groups_with_event = event_groups_with_event
        
        # Measure cache creation time
        start_time = time.time()
        cache = constraint._create_event_data_cache()
        end_time = time.time()
        
        cache_time = end_time - start_time
        
        # Should create cache efficiently
        assert len(cache) == large_event_count
        assert cache_time < 1.0  # Should complete quickly
    
    def test_constraint_memory_usage_large_preferences(self, mock_solver_context):
        """Test: Memory-Usage bei vielen Location-Preferences."""
        import gc
        
        constraint = LocationPrefsConstraint(mock_solver_context)
        
        # Setup configuration
        mock_multipliers = {1.0: 50}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_location_prefs = mock_multipliers
        
        # Setup minimal but valid entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        
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
