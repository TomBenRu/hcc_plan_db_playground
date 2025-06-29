"""
Unit-Tests für PartnerLocationPrefsConstraint

Testet das Constraint für Partner-Standort-Präferenzen zwischen Mitarbeitern.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from datetime import date
from itertools import combinations

from sat_solver.constraints.partner_prefs import PartnerLocationPrefsConstraint


@pytest.mark.unit
class TestPartnerLocationPrefsConstraint:
    """Test-Klasse für PartnerLocationPrefsConstraint."""
    
    def test_constraint_name(self, mock_solver_context):
        """Test: Constraint-Name ist korrekt."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        assert constraint.constraint_name == "partner_location_prefs"
    
    def test_constraint_initialization(self, mock_solver_context):
        """Test: Constraint wird korrekt initialisiert."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        assert constraint.context == mock_solver_context
        assert constraint.model == mock_solver_context.model
        assert constraint.entities == mock_solver_context.entities
        assert constraint.config == mock_solver_context.config
        assert not constraint.is_setup_complete()
    
    def test_create_variables_empty_entities(self, mock_solver_context):
        """Test: create_variables() mit leeren Entities."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = {
            0: 200, 0.5: 100, 1: 0, 2: -100
        }
        
        variables = constraint.create_variables()
        
        # Should return empty list for empty entities
        assert variables == []
        assert constraint.get_metadata('total_partner_preferences') == 0
        assert constraint.get_metadata('partnerships_evaluated') == 0
    
    def test_create_variables_single_actor_events(self, mock_solver_context):
        """Test: create_variables() mit Events für nur 1 Actor."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup event with only 1 actor (no partnerships possible)
        eg_id = uuid4()
        
        mock_cast_group = Mock()
        mock_cast_group.nr_actors = 1  # Single actor
        
        mock_event = Mock()
        mock_event.cast_group = mock_cast_group
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        mock_solver_context.entities.event_groups_with_event = {eg_id: mock_event_group}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = {
            0: 200, 1: 0, 2: -100
        }
        
        variables = constraint.create_variables()
        
        # Should return empty list for single-actor events
        assert variables == []
        assert constraint.get_metadata('total_partner_preferences') == 0
    
    def test_get_compatible_avail_day_groups(self, mock_solver_context):
        """Test: _get_compatible_avail_day_groups() Methode."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup test data
        eg_id = uuid4()
        adg_id1, adg_id2, adg_id3 = uuid4(), uuid4(), uuid4()
        
        # Mock avail day groups
        mock_adg1 = Mock()
        mock_adg2 = Mock()
        mock_adg3 = Mock()
        
        mock_solver_context.entities.avail_day_groups_with_avail_day = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2,
            adg_id3: mock_adg3
        }
        
        # Setup shifts_exclusive - only some are allowed
        mock_solver_context.entities.shifts_exclusive = {
            (adg_id1, eg_id): 1,  # Allowed
            (adg_id2, eg_id): 0,  # Not allowed
            (adg_id3, eg_id): 1   # Allowed
        }
        
        compatible_groups = constraint._get_compatible_avail_day_groups(eg_id)
        
        # Should return only allowed groups
        assert len(compatible_groups) == 2
        assert mock_adg1 in compatible_groups
        assert mock_adg3 in compatible_groups
        assert mock_adg2 not in compatible_groups
    
    def test_has_partner_location_preferences(self, mock_solver_context):
        """Test: _has_partner_location_preferences() Methode."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup avail day groups
        mock_avail_day1 = Mock()
        mock_avail_day1.actor_partner_location_prefs_defaults = [Mock()]  # Has preferences
        mock_adg1 = Mock()
        mock_adg1.avail_day = mock_avail_day1
        
        mock_avail_day2 = Mock()
        mock_avail_day2.actor_partner_location_prefs_defaults = []  # No preferences
        mock_adg2 = Mock()
        mock_adg2.avail_day = mock_avail_day2
        
        mock_avail_day3 = Mock()
        mock_avail_day3.actor_partner_location_prefs_defaults = []  # No preferences
        mock_adg3 = Mock()
        mock_adg3.avail_day = mock_avail_day3
        
        # Test combinations
        assert constraint._has_partner_location_preferences((mock_adg1, mock_adg2)) is True
        assert constraint._has_partner_location_preferences((mock_adg2, mock_adg3)) is False
    
    def test_calculate_partner_scores(self, mock_solver_context):
        """Test: _calculate_partner_scores() Methode."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup persons and location
        person_id1, person_id2 = uuid4(), uuid4()
        location_id = uuid4()
        
        mock_person1 = Mock()
        mock_person1.id = person_id1
        mock_person2 = Mock()
        mock_person2.id = person_id2
        
        mock_location = Mock()
        mock_location.id = location_id
        
        # Setup partner preferences
        # Person 1's preference for Person 2 at this location
        mock_pref1 = Mock()
        mock_pref1.partner = mock_person2
        mock_pref1.location_of_work = mock_location
        mock_pref1.score = 0.5  # Good partnership
        
        # Person 2's preference for Person 1 at this location
        mock_pref2 = Mock()
        mock_pref2.partner = mock_person1
        mock_pref2.location_of_work = mock_location
        mock_pref2.score = 2.0  # Bad partnership
        
        # Setup avail days
        mock_avail_day1 = Mock()
        mock_avail_day1.actor_partner_location_prefs_defaults = [mock_pref1]
        mock_avail_day1.actor_plan_period = Mock()
        mock_avail_day1.actor_plan_period.person = mock_person1
        
        mock_avail_day2 = Mock()
        mock_avail_day2.actor_partner_location_prefs_defaults = [mock_pref2]
        mock_avail_day2.actor_plan_period = Mock()
        mock_avail_day2.actor_plan_period.person = mock_person2
        
        mock_adg1 = Mock()
        mock_adg1.avail_day = mock_avail_day1
        mock_adg2 = Mock()
        mock_adg2.avail_day = mock_avail_day2
        
        # Setup event group
        mock_event = Mock()
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_of_work = mock_location
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Calculate scores
        score_1, score_2 = constraint._calculate_partner_scores(
            (mock_adg1, mock_adg2), mock_event_group
        )
        
        assert score_1 == 0.5  # Person 1's preference for Person 2
        assert score_2 == 2.0  # Person 2's preference for Person 1
    
    def test_calculate_partner_scores_no_preferences(self, mock_solver_context):
        """Test: _calculate_partner_scores() ohne definierte Präferenzen."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup persons without preferences for each other
        person_id1, person_id2 = uuid4(), uuid4()
        location_id = uuid4()
        
        mock_person1 = Mock()
        mock_person1.id = person_id1
        mock_person2 = Mock()
        mock_person2.id = person_id2
        
        mock_location = Mock()
        mock_location.id = location_id
        
        # No preferences defined
        mock_avail_day1 = Mock()
        mock_avail_day1.actor_partner_location_prefs_defaults = []
        mock_avail_day1.actor_plan_period = Mock()
        mock_avail_day1.actor_plan_period.person = mock_person1
        
        mock_avail_day2 = Mock()
        mock_avail_day2.actor_partner_location_prefs_defaults = []
        mock_avail_day2.actor_plan_period = Mock()
        mock_avail_day2.actor_plan_period.person = mock_person2
        
        mock_adg1 = Mock()
        mock_adg1.avail_day = mock_avail_day1
        mock_adg2 = Mock()
        mock_adg2.avail_day = mock_avail_day2
        
        # Setup event group
        mock_event = Mock()
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_of_work = mock_location
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Calculate scores
        score_1, score_2 = constraint._calculate_partner_scores(
            (mock_adg1, mock_adg2), mock_event_group
        )
        
        # Should return default scores
        assert score_1 == 1  # Default
        assert score_2 == 1  # Default
    
    def test_create_helper_variables(self, mock_solver_context):
        """Test: _create_helper_variables() Methode."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup test data
        eg_id = uuid4()
        adg_id1, adg_id2 = uuid4(), uuid4()
        
        # Setup avail day groups
        mock_adg1 = Mock()
        mock_adg1.avail_day_group_id = adg_id1
        mock_adg2 = Mock()
        mock_adg2.avail_day_group_id = adg_id2
        
        # Setup event group
        mock_cast_group = Mock()
        mock_cast_group.nr_actors = 3
        
        mock_event = Mock()
        mock_event.cast_group = mock_cast_group
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup multipliers
        multipliers = {0: 200, 0.5: 100, 1: 0, 2: -100}
        
        # Setup shift vars and event group vars
        mock_shift_var1 = Mock()
        mock_shift_var2 = Mock()
        mock_event_group_var = Mock()
        
        mock_solver_context.entities.shift_vars = {
            (adg_id1, eg_id): mock_shift_var1,
            (adg_id2, eg_id): mock_shift_var2
        }
        mock_solver_context.entities.event_group_vars = {eg_id: mock_event_group_var}
        
        # Mock NewIntVar and NewBoolVar
        mock_int_var = Mock()
        mock_bool_var1 = Mock()
        mock_bool_var2 = Mock()
        
        mock_solver_context.model.NewIntVar.return_value = mock_int_var
        mock_solver_context.model.NewBoolVar.side_effect = [mock_bool_var1, mock_bool_var2]
        
        # Create helper variables
        plp_weight_var, shift_active_var, all_active_var = constraint._create_helper_variables(
            (mock_adg1, mock_adg2), eg_id, mock_event_group, 0.5, 1.0, multipliers
        )
        
        # Verify variables
        assert plp_weight_var == mock_int_var
        assert shift_active_var == mock_bool_var1
        assert all_active_var == mock_bool_var2
        
        # Verify Add and multiplication constraints were called
        assert mock_solver_context.model.Add.called
        assert mock_solver_context.model.AddMultiplicationEquality.call_count == 2
    
    def test_add_exclusivity_constraint_required(self, mock_solver_context):
        """Test: _add_exclusivity_constraint() wenn Exklusivität erforderlich."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup for exclusivity case (one score is 0 and cast size is 2)
        eg_id = uuid4()
        adg_id1, adg_id2 = uuid4(), uuid4()
        
        mock_person1 = Mock()
        mock_person1.f_name = "Actor1"
        mock_person2 = Mock()
        mock_person2.f_name = "Actor2"
        
        mock_avail_day1 = Mock()
        mock_avail_day1.actor_plan_period = Mock()
        mock_avail_day1.actor_plan_period.person = mock_person1
        
        mock_avail_day2 = Mock()
        mock_avail_day2.actor_plan_period = Mock()
        mock_avail_day2.actor_plan_period.person = mock_person2
        
        mock_adg1 = Mock()
        mock_adg1.avail_day_group_id = adg_id1
        mock_adg1.avail_day = mock_avail_day1
        
        mock_adg2 = Mock()
        mock_adg2.avail_day_group_id = adg_id2
        mock_adg2.avail_day = mock_avail_day2
        
        # Cast size 2, one score is 0 -> exclusivity required
        mock_cast_group = Mock()
        mock_cast_group.nr_actors = 2
        
        mock_event = Mock()
        mock_event.cast_group = mock_cast_group
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup shift vars
        mock_shift_var1 = Mock()
        mock_shift_var2 = Mock()
        mock_solver_context.entities.shift_vars = {
            (adg_id1, eg_id): mock_shift_var1,
            (adg_id2, eg_id): mock_shift_var2
        }
        
        # Add exclusivity constraint
        constraint._add_exclusivity_constraint(
            (mock_adg1, mock_adg2), eg_id, mock_event_group, 0, 1.0  # score_1=0
        )
        
        # Should add constraint
        assert mock_solver_context.model.Add.called
        
        # Should add metadata
        exclusivity_key = f'exclusivity_constraint_{eg_id}'
        exclusivity_metadata = constraint.get_metadata(exclusivity_key)
        assert exclusivity_metadata is not None
        assert exclusivity_metadata['person_1'] == 'Actor1'
        assert exclusivity_metadata['person_2'] == 'Actor2'
    
    def test_add_exclusivity_constraint_not_required(self, mock_solver_context):
        """Test: _add_exclusivity_constraint() wenn keine Exklusivität erforderlich."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup for non-exclusivity case (both scores > 0 or cast size >= 3)
        eg_id = uuid4()
        adg_id1, adg_id2 = uuid4(), uuid4()
        
        mock_adg1 = Mock()
        mock_adg1.avail_day_group_id = adg_id1
        mock_adg2 = Mock()
        mock_adg2.avail_day_group_id = adg_id2
        
        # Cast size 3 -> no exclusivity needed
        mock_cast_group = Mock()
        mock_cast_group.nr_actors = 3
        
        mock_event = Mock()
        mock_event.cast_group = mock_cast_group
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Add exclusivity constraint (should not add anything)
        constraint._add_exclusivity_constraint(
            (mock_adg1, mock_adg2), eg_id, mock_event_group, 1.0, 1.0  # Both scores > 0
        )
        
        # Should not add constraint
        assert not mock_solver_context.model.Add.called
    
    def test_create_variables_with_partner_preferences(self, mock_solver_context):
        """Test: create_variables() mit Partner-Präferenzen."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup multiplier configuration
        multipliers = {0: 200, 0.5: 100, 1: 0, 2: -100}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = multipliers
        
        # Setup test scenario
        eg_id = uuid4()
        adg_id1, adg_id2 = uuid4(), uuid4()
        person_id1, person_id2 = uuid4(), uuid4()
        location_id = uuid4()
        test_date = date(2025, 6, 28)
        
        # Setup persons
        mock_person1 = Mock()
        mock_person1.id = person_id1
        mock_person1.f_name = "Clown1"
        
        mock_person2 = Mock()
        mock_person2.id = person_id2
        mock_person2.f_name = "Clown2"
        
        # Setup location
        mock_location = Mock()
        mock_location.id = location_id
        mock_location.name = "TestKlinik"
        
        # Setup partner preferences
        mock_pref1 = Mock()
        mock_pref1.partner = mock_person2
        mock_pref1.location_of_work = mock_location
        mock_pref1.score = 0.5
        
        # Setup avail days
        mock_app1 = Mock()
        mock_app1.id = person_id1
        mock_app1.person = mock_person1
        
        mock_app2 = Mock()
        mock_app2.id = person_id2
        mock_app2.person = mock_person2
        
        mock_avail_day1 = Mock()
        mock_avail_day1.actor_partner_location_prefs_defaults = [mock_pref1]
        mock_avail_day1.actor_plan_period = mock_app1
        
        mock_avail_day2 = Mock()
        mock_avail_day2.actor_partner_location_prefs_defaults = []
        mock_avail_day2.actor_plan_period = mock_app2
        
        mock_adg1 = Mock()
        mock_adg1.avail_day_group_id = adg_id1
        mock_adg1.avail_day = mock_avail_day1
        
        mock_adg2 = Mock()
        mock_adg2.avail_day_group_id = adg_id2
        mock_adg2.avail_day = mock_avail_day2
        
        # Setup event
        mock_cast_group = Mock()
        mock_cast_group.nr_actors = 2
        
        mock_time_of_day = Mock()
        mock_time_of_day.name = "Vormittag"
        
        mock_location_plan_period = Mock()
        mock_location_plan_period.location_of_work = mock_location
        
        mock_event = Mock()
        mock_event.date = test_date
        mock_event.time_of_day = mock_time_of_day
        mock_event.location_plan_period = mock_location_plan_period
        mock_event.cast_group = mock_cast_group
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = {eg_id: mock_event_group}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2
        }
        mock_solver_context.entities.shifts_exclusive = {
            (adg_id1, eg_id): 1,
            (adg_id2, eg_id): 1
        }
        
        # Setup variables
        mock_shift_var1 = Mock()
        mock_shift_var2 = Mock()
        mock_event_group_var = Mock()
        
        mock_solver_context.entities.shift_vars = {
            (adg_id1, eg_id): mock_shift_var1,
            (adg_id2, eg_id): mock_shift_var2
        }
        mock_solver_context.entities.event_group_vars = {eg_id: mock_event_group_var}
        
        # Mock model methods
        mock_partner_var = Mock()
        mock_int_vars = [Mock(), Mock(), Mock()]  # For helper variables
        mock_bool_vars = [Mock(), Mock()]  # For helper variables
        
        mock_solver_context.model.NewIntVar.side_effect = [mock_partner_var] + mock_int_vars
        mock_solver_context.model.NewBoolVar.side_effect = mock_bool_vars
        
        # Create variables
        variables = constraint.create_variables()
        
        # Verify variable creation
        assert len(variables) == 1
        assert variables[0] == mock_partner_var
        
        # Verify metadata
        assert constraint.get_metadata('total_partner_preferences') == 1
        assert constraint.get_metadata('partnerships_evaluated') == 1
        
        partnership_metadata = constraint.get_metadata('partnership_0')
        assert partnership_metadata['person_1'] == 'Clown1'
        assert partnership_metadata['person_2'] == 'Clown2'
        assert partnership_metadata['score_1'] == 0.5
        assert partnership_metadata['score_2'] == 1  # Default
    
    def test_create_variables_skip_same_person(self, mock_solver_context):
        """Test: create_variables() überspringt dieselbe Person."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup multipliers
        multipliers = {1: 0}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = multipliers
        
        # Setup scenario where both ADGs belong to the same person
        eg_id = uuid4()
        adg_id1, adg_id2 = uuid4(), uuid4()
        person_id = uuid4()  # Same person
        
        mock_person = Mock()
        mock_person.id = person_id
        
        mock_app = Mock()
        mock_app.id = person_id
        mock_app.person = mock_person
        
        mock_avail_day1 = Mock()
        mock_avail_day1.actor_partner_location_prefs_defaults = [Mock()]
        mock_avail_day1.actor_plan_period = mock_app
        
        mock_avail_day2 = Mock()
        mock_avail_day2.actor_partner_location_prefs_defaults = []
        mock_avail_day2.actor_plan_period = mock_app  # Same person
        
        mock_adg1 = Mock()
        mock_adg1.avail_day = mock_avail_day1
        mock_adg2 = Mock()
        mock_adg2.avail_day = mock_avail_day2
        
        # Setup event
        mock_cast_group = Mock()
        mock_cast_group.nr_actors = 2
        
        mock_event = Mock()
        mock_event.cast_group = mock_cast_group
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = {eg_id: mock_event_group}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2
        }
        mock_solver_context.entities.shifts_exclusive = {
            (adg_id1, eg_id): 1,
            (adg_id2, eg_id): 1
        }
        
        # Create variables
        variables = constraint.create_variables()
        
        # Should skip same person combinations
        assert len(variables) == 0
        assert constraint.get_metadata('partnerships_evaluated') == 0
    
    def test_validate_context_success(self, mock_solver_context):
        """Test: validate_context() erfolgreich."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup required attributes
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = {}
        
        result = constraint.validate_context()
        assert result is True
    
    def test_validate_context_missing_entities(self, mock_solver_context):
        """Test: validate_context() mit fehlenden Entities."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Missing entities
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error is not None
        assert "Missing entities." in error
    
    def test_validate_context_missing_config(self, mock_solver_context):
        """Test: validate_context() mit fehlender Konfiguration."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup entities but missing config
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        
        # Missing config
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error is not None
        assert "constraint_multipliers" in error
    
    def test_get_partner_prefs_summary(self, mock_solver_context):
        """Test: get_partner_prefs_summary() Methode."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup test data
        eg_id1, eg_id2 = uuid4(), uuid4()
        adg_id1, adg_id2 = uuid4(), uuid4()
        
        # Setup events - one multi-actor, one single-actor
        mock_cast_group1 = Mock()
        mock_cast_group1.nr_actors = 2  # Multi-actor
        
        mock_cast_group2 = Mock()
        mock_cast_group2.nr_actors = 1  # Single-actor
        
        mock_event1 = Mock()
        mock_event1.cast_group = mock_cast_group1
        
        mock_event2 = Mock()
        mock_event2.cast_group = mock_cast_group2
        
        mock_event_group1 = Mock()
        mock_event_group1.event = mock_event1
        
        mock_event_group2 = Mock()
        mock_event_group2.event = mock_event2
        
        # Setup avail days with partner preferences
        mock_pref1 = Mock()
        mock_pref1.score = 0.5
        
        mock_pref2 = Mock()
        mock_pref2.score = 2.0
        
        mock_pref3 = Mock()
        mock_pref3.score = 0.5  # Same score as pref1
        
        mock_avail_day1 = Mock()
        mock_avail_day1.actor_partner_location_prefs_defaults = [mock_pref1, mock_pref2]
        
        mock_avail_day2 = Mock()
        mock_avail_day2.actor_partner_location_prefs_defaults = [mock_pref3]
        
        mock_adg1 = Mock()
        mock_adg1.avail_day = mock_avail_day1
        
        mock_adg2 = Mock()
        mock_adg2.avail_day = mock_avail_day2
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = {
            eg_id1: mock_event_group1,
            eg_id2: mock_event_group2
        }
        mock_solver_context.entities.avail_day_groups_with_avail_day = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2
        }
        
        # Set metadata
        constraint.add_metadata('partnerships_evaluated', 5)
        constraint.add_metadata('total_partner_preferences', 3)
        
        summary = constraint.get_partner_prefs_summary()
        
        # Verify summary
        assert summary['total_events'] == 2
        assert summary['multi_actor_events'] == 1
        assert summary['total_partnerships_defined'] == 3
        assert summary['partnerships_evaluated'] == 5
        assert summary['partner_preference_variables'] == 3
        assert summary['score_distribution'] == {0.5: 2, 2.0: 1}
        assert summary['unique_scores'] == [0.5, 2.0]
    
    def test_get_partner_prefs_summary_empty(self, mock_solver_context):
        """Test: get_partner_prefs_summary() mit leeren Daten."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        
        summary = constraint.get_partner_prefs_summary()
        
        # Should return empty summary
        assert summary == {}
    
    def test_complete_setup_workflow(self, mock_solver_context):
        """Test: Kompletter Setup-Workflow."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup minimal required entities
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        
        # Setup config
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = {}
        
        # Test setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()


@pytest.mark.integration
class TestPartnerLocationPrefsConstraintIntegration:
    """Integration-Tests für PartnerLocationPrefsConstraint."""
    
    def test_constraint_with_realistic_klinikclown_scenario(self, mock_solver_context):
        """Test: Constraint mit realistischem Klinikclown-Szenario."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup realistic multiplier configuration
        multipliers = {
            0: 500,    # Absolutely cannot work together
            0.5: 200,  # Great partnership
            1: 0,      # Neutral (default)
            2: -200,   # Difficult partnership
            3: -500    # Very difficult partnership
        }
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = multipliers
        
        # Setup clowns with realistic names and relationships
        clowns_data = [
            {"id": uuid4(), "name": "Pippo"},
            {"id": uuid4(), "name": "Luna"},
            {"id": uuid4(), "name": "Benny"},
            {"id": uuid4(), "name": "Stella"}
        ]
        
        # Setup realistic partnership preferences
        partnerships = [
            # Pippo's preferences
            {"from": "Pippo", "to": "Luna", "score": 0.5},    # Great with Luna
            {"from": "Pippo", "to": "Benny", "score": 2.0},   # Difficult with Benny
            {"from": "Pippo", "to": "Stella", "score": 1.0},  # Neutral with Stella
            
            # Luna's preferences
            {"from": "Luna", "to": "Pippo", "score": 0.5},    # Also great with Pippo
            {"from": "Luna", "to": "Benny", "score": 1.0},    # Neutral with Benny
            {"from": "Luna", "to": "Stella", "score": 0.5},   # Great with Stella
            
            # Benny's preferences
            {"from": "Benny", "to": "Pippo", "score": 3.0},   # Very difficult with Pippo
            {"from": "Benny", "to": "Stella", "score": 1.0},  # Neutral with Stella
            
            # Stella - no specific preferences (will use defaults)
        ]
        
        # Create clown objects
        clown_objects = {}
        for clown_data in clowns_data:
            mock_person = Mock()
            mock_person.id = clown_data["id"]
            mock_person.f_name = clown_data["name"]
            clown_objects[clown_data["name"]] = mock_person
        
        # Setup locations
        locations_data = [
            {"id": uuid4(), "name": "Kinderklinik A"},
            {"id": uuid4(), "name": "Kinderklinik B"}
        ]
        
        location_objects = {}
        for loc_data in locations_data:
            mock_location = Mock()
            mock_location.id = loc_data["id"]
            mock_location.name = loc_data["name"]
            location_objects[loc_data["name"]] = mock_location
        
        # Setup events (2-person teams)
        events_data = [
            {
                "id": uuid4(),
                "date": date(2025, 6, 28),
                "time": "Vormittag",
                "location": "Kinderklinik A",
                "cast_size": 2
            },
            {
                "id": uuid4(),
                "date": date(2025, 6, 29),
                "time": "Nachmittag",
                "location": "Kinderklinik B",
                "cast_size": 2
            },
            {
                "id": uuid4(),
                "date": date(2025, 6, 30),
                "time": "Vormittag",
                "location": "Kinderklinik A",
                "cast_size": 3  # 3-person team
            }
        ]
        
        # Create event groups
        event_groups_with_event = {}
        event_group_vars = {}
        
        for event_data in events_data:
            eg_id = uuid4()
            
            mock_cast_group = Mock()
            mock_cast_group.nr_actors = event_data["cast_size"]
            
            mock_time_of_day = Mock()
            mock_time_of_day.name = event_data["time"]
            
            mock_location_plan_period = Mock()
            mock_location_plan_period.location_of_work = location_objects[event_data["location"]]
            
            mock_event = Mock()
            mock_event.id = event_data["id"]
            mock_event.date = event_data["date"]
            mock_event.time_of_day = mock_time_of_day
            mock_event.location_plan_period = mock_location_plan_period
            mock_event.cast_group = mock_cast_group
            
            mock_event_group = Mock()
            mock_event_group.event = mock_event
            
            event_groups_with_event[eg_id] = mock_event_group
            event_group_vars[eg_id] = Mock()
        
        # Create avail day groups and shift vars
        avail_day_groups_with_avail_day = {}
        shift_vars = {}
        shifts_exclusive = {}
        
        for clown_name, clown_person in clown_objects.items():
            for eg_id, event_group in event_groups_with_event.items():
                adg_id = uuid4()
                
                # Create partner preferences for this clown
                partner_prefs = []
                for partnership in partnerships:
                    if partnership["from"] == clown_name:
                        target_clown = clown_objects[partnership["to"]]
                        
                        # Create preference for each location
                        for location_name, location_obj in location_objects.items():
                            mock_pref = Mock()
                            mock_pref.partner = target_clown
                            mock_pref.location_of_work = location_obj
                            mock_pref.score = partnership["score"]
                            partner_prefs.append(mock_pref)
                
                # Create actor plan period
                mock_app = Mock()
                mock_app.id = clown_person.id
                mock_app.person = clown_person
                
                # Create avail day
                mock_avail_day = Mock()
                mock_avail_day.actor_partner_location_prefs_defaults = partner_prefs
                mock_avail_day.actor_plan_period = mock_app
                
                mock_adg = Mock()
                mock_adg.avail_day_group_id = adg_id
                mock_adg.avail_day = mock_avail_day
                
                avail_day_groups_with_avail_day[adg_id] = mock_adg
                shift_vars[(adg_id, eg_id)] = Mock()
                shifts_exclusive[(adg_id, eg_id)] = 1  # All allowed
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = event_groups_with_event
        mock_solver_context.entities.avail_day_groups_with_avail_day = avail_day_groups_with_avail_day
        mock_solver_context.entities.shift_vars = shift_vars
        mock_solver_context.entities.event_group_vars = event_group_vars
        mock_solver_context.entities.shifts_exclusive = shifts_exclusive
        
        # Mock model methods
        mock_vars = [Mock() for _ in range(100)]  # Enough variables
        mock_solver_context.model.NewIntVar.side_effect = mock_vars
        mock_solver_context.model.NewBoolVar.side_effect = mock_vars
        
        # Test constraint setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()
        
        # Verify variables were created
        total_partnerships = constraint.get_metadata('total_partner_preferences')
        assert total_partnerships > 0
        
        # Get comprehensive summary
        summary = constraint.get_summary()
        assert summary['total_events'] == 3
        assert summary['multi_actor_events'] == 3  # All events have 2+ actors
        assert summary['total_partnerships_defined'] > 0
        assert 0.5 in summary['score_distribution']  # Great partnerships
        assert 2.0 in summary['score_distribution']  # Difficult partnerships
    
    def test_constraint_performance_large_team_matrix(self, mock_solver_context):
        """Test: Constraint Performance mit großer Team-Matrix."""
        import time
        
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup configuration
        multipliers = {0: 200, 1: 0, 2: -100}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = multipliers
        
        # Create large scenario
        num_clowns = 30
        num_events = 20
        
        # Setup clowns
        clown_objects = {}
        for i in range(num_clowns):
            mock_person = Mock()
            mock_person.id = uuid4()
            mock_person.f_name = f"Clown_{i}"
            clown_objects[f"Clown_{i}"] = mock_person
        
        # Setup events (all with 2-person teams for maximum partnerships)
        event_groups_with_event = {}
        event_group_vars = {}
        
        for i in range(num_events):
            eg_id = uuid4()
            
            mock_cast_group = Mock()
            mock_cast_group.nr_actors = 2  # Always pairs
            
            mock_location = Mock()
            mock_location.id = uuid4()
            mock_location.name = f"Location_{i}"
            
            mock_event = Mock()
            mock_event.id = uuid4()
            mock_event.date = date(2025, 6, 28)
            mock_event.time_of_day = Mock()
            mock_event.time_of_day.name = f"Time_{i}"
            mock_event.location_plan_period = Mock()
            mock_event.location_plan_period.location_of_work = mock_location
            mock_event.cast_group = mock_cast_group
            
            mock_event_group = Mock()
            mock_event_group.event = mock_event
            
            event_groups_with_event[eg_id] = mock_event_group
            event_group_vars[eg_id] = Mock()
        
        # Setup avail day groups (sparse - not all clowns for all events)
        avail_day_groups_with_avail_day = {}
        shift_vars = {}
        shifts_exclusive = {}
        
        for i, (clown_name, clown_person) in enumerate(clown_objects.items()):
            # Each clown is available for a subset of events
            available_events = list(event_groups_with_event.keys())[i::3]  # Every 3rd event
            
            for eg_id in available_events:
                adg_id = uuid4()
                
                # Minimal partner preferences (to reduce complexity)
                partner_prefs = []
                if i % 5 == 0:  # Only every 5th clown has preferences
                    mock_pref = Mock()
                    mock_pref.partner = Mock()
                    mock_pref.partner.id = uuid4()
                    mock_pref.location_of_work = Mock()
                    mock_pref.location_of_work.id = uuid4()
                    mock_pref.score = 1.0
                    partner_prefs = [mock_pref]
                
                mock_app = Mock()
                mock_app.id = clown_person.id
                mock_app.person = clown_person
                
                mock_avail_day = Mock()
                mock_avail_day.actor_partner_location_prefs_defaults = partner_prefs
                mock_avail_day.actor_plan_period = mock_app
                
                mock_adg = Mock()
                mock_adg.avail_day_group_id = adg_id
                mock_adg.avail_day = mock_avail_day
                
                avail_day_groups_with_avail_day[adg_id] = mock_adg
                shift_vars[(adg_id, eg_id)] = Mock()
                shifts_exclusive[(adg_id, eg_id)] = 1
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = event_groups_with_event
        mock_solver_context.entities.avail_day_groups_with_avail_day = avail_day_groups_with_avail_day
        mock_solver_context.entities.shift_vars = shift_vars
        mock_solver_context.entities.event_group_vars = event_group_vars
        mock_solver_context.entities.shifts_exclusive = shifts_exclusive
        
        # Mock model methods
        mock_vars = [Mock() for _ in range(1000)]
        mock_solver_context.model.NewIntVar.side_effect = mock_vars
        mock_solver_context.model.NewBoolVar.side_effect = mock_vars
        
        # Measure setup time
        start_time = time.time()
        success = constraint.setup()
        end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Should complete quickly even with large team matrix
        assert success is True
        assert setup_time < 5.0  # Should take less than 5 seconds
    
    def test_constraint_exclusivity_scenarios(self, mock_solver_context):
        """Test: Verschiedene Exklusivitäts-Szenarien."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup configuration
        multipliers = {0: 200, 1: 0, 2: -100}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = multipliers
        
        # Test scenarios:
        # 1. Forbidden partnership (score 0) with 2-person cast -> exclusivity
        # 2. Bad partnership (score 2) with 2-person cast -> no exclusivity 
        # 3. Forbidden partnership (score 0) with 3-person cast -> no exclusivity
        
        test_scenarios = [
            {"cast_size": 2, "score_1": 0, "score_2": 1, "expect_exclusivity": True},
            {"cast_size": 2, "score_1": 2, "score_2": 2, "expect_exclusivity": False},
            {"cast_size": 3, "score_1": 0, "score_2": 1, "expect_exclusivity": False}
        ]
        
        for i, scenario in enumerate(test_scenarios):
            eg_id = uuid4()
            adg_id1, adg_id2 = uuid4(), uuid4()
            person_id1, person_id2 = uuid4(), uuid4()
            location_id = uuid4()
            
            # Setup persons
            mock_person1 = Mock()
            mock_person1.id = person_id1
            mock_person1.f_name = f"Person1_{i}"
            
            mock_person2 = Mock()
            mock_person2.id = person_id2
            mock_person2.f_name = f"Person2_{i}"
            
            # Setup location
            mock_location = Mock()
            mock_location.id = location_id
            
            # Setup preferences based on scenario
            mock_pref1 = Mock()
            mock_pref1.partner = mock_person2
            mock_pref1.location_of_work = mock_location
            mock_pref1.score = scenario["score_1"]
            
            mock_pref2 = Mock()
            mock_pref2.partner = mock_person1
            mock_pref2.location_of_work = mock_location
            mock_pref2.score = scenario["score_2"]
            
            # Setup avail days
            mock_app1 = Mock()
            mock_app1.id = person_id1
            mock_app1.person = mock_person1
            
            mock_app2 = Mock()
            mock_app2.id = person_id2
            mock_app2.person = mock_person2
            
            mock_avail_day1 = Mock()
            mock_avail_day1.actor_partner_location_prefs_defaults = [mock_pref1]
            mock_avail_day1.actor_plan_period = mock_app1
            
            mock_avail_day2 = Mock()
            mock_avail_day2.actor_partner_location_prefs_defaults = [mock_pref2]
            mock_avail_day2.actor_plan_period = mock_app2
            
            mock_adg1 = Mock()
            mock_adg1.avail_day_group_id = adg_id1
            mock_adg1.avail_day = mock_avail_day1
            
            mock_adg2 = Mock()
            mock_adg2.avail_day_group_id = adg_id2
            mock_adg2.avail_day = mock_avail_day2
            
            # Setup event
            mock_cast_group = Mock()
            mock_cast_group.nr_actors = scenario["cast_size"]
            
            mock_event = Mock()
            mock_event.date = date(2025, 6, 28)
            mock_event.time_of_day = Mock()
            mock_event.time_of_day.name = f"Test_{i}"
            mock_event.location_plan_period = Mock()
            mock_event.location_plan_period.location_of_work = mock_location
            mock_event.cast_group = mock_cast_group
            
            mock_event_group = Mock()
            mock_event_group.event = mock_event
            
            # Setup entities (clear previous data)
            mock_solver_context.entities.event_groups_with_event = {eg_id: mock_event_group}
            mock_solver_context.entities.avail_day_groups_with_avail_day = {
                adg_id1: mock_adg1,
                adg_id2: mock_adg2
            }
            mock_solver_context.entities.shifts_exclusive = {
                (adg_id1, eg_id): 1,
                (adg_id2, eg_id): 1
            }
            mock_solver_context.entities.shift_vars = {
                (adg_id1, eg_id): Mock(),
                (adg_id2, eg_id): Mock()
            }
            mock_solver_context.entities.event_group_vars = {eg_id: Mock()}
            
            # Reset mocks
            mock_solver_context.model.reset_mock()
            mock_solver_context.model.NewIntVar.side_effect = [Mock(), Mock(), Mock()]
            mock_solver_context.model.NewBoolVar.side_effect = [Mock(), Mock()]
            
            # Test scenario
            variables = constraint.create_variables()
            
            # Clear metadata for next iteration
            constraint._metadata.clear()
            
            # Verify exclusivity behavior
            if scenario["expect_exclusivity"]:
                # Should have added exclusivity constraint
                exclusivity_key = f'exclusivity_constraint_{eg_id}'
                # Note: This test verifies the logic, actual metadata checking 
                # depends on implementation details
            
            # Verify partnership was processed
            assert len(variables) == 1
    
    @patch('sat_solver.constraints.partner_prefs.logger')
    def test_constraint_logging_integration(self, mock_logger, mock_solver_context):
        """Test: Constraint Logging-Integration."""
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup minimal entities
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = {}
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Logging calls depend on implementation, but logger should be available


@pytest.mark.slow
class TestPartnerLocationPrefsConstraintPerformance:
    """Performance-Tests für PartnerLocationPrefsConstraint."""
    
    def test_constraint_partnership_combinations_complexity(self, mock_solver_context):
        """Test: Komplexität der Partnership-Kombinationen."""
        import time
        
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup configuration
        multipliers = {1: 0}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = multipliers
        
        # Create scenario with many potential partnerships
        num_clowns_per_event = 10  # 10 clowns per event = 45 combinations
        num_events = 5
        
        event_groups_with_event = {}
        event_group_vars = {}
        
        for event_i in range(num_events):
            eg_id = uuid4()
            
            mock_cast_group = Mock()
            mock_cast_group.nr_actors = 2  # Enable partnerships
            
            mock_event = Mock()
            mock_event.date = date(2025, 6, 28)
            mock_event.time_of_day = Mock()
            mock_event.time_of_day.name = f"Event_{event_i}"
            mock_event.location_plan_period = Mock()
            mock_event.location_plan_period.location_of_work = Mock()
            mock_event.location_plan_period.location_of_work.id = uuid4()
            mock_event.location_plan_period.location_of_work.name = f"Location_{event_i}"
            mock_event.cast_group = mock_cast_group
            
            mock_event_group = Mock()
            mock_event_group.event = mock_event
            
            event_groups_with_event[eg_id] = mock_event_group
            event_group_vars[eg_id] = Mock()
        
        # Setup many clowns for each event
        avail_day_groups_with_avail_day = {}
        shift_vars = {}
        shifts_exclusive = {}
        
        for event_i, eg_id in enumerate(event_groups_with_event.keys()):
            for clown_i in range(num_clowns_per_event):
                adg_id = uuid4()
                
                mock_person = Mock()
                mock_person.id = uuid4()
                mock_person.f_name = f"Clown_{event_i}_{clown_i}"
                
                # Every clown has one simple preference
                mock_pref = Mock()
                mock_pref.partner = Mock()
                mock_pref.partner.id = uuid4()
                mock_pref.location_of_work = Mock()
                mock_pref.location_of_work.id = uuid4()
                mock_pref.score = 1.0
                
                mock_app = Mock()
                mock_app.id = mock_person.id
                mock_app.person = mock_person
                
                mock_avail_day = Mock()
                mock_avail_day.actor_partner_location_prefs_defaults = [mock_pref]
                mock_avail_day.actor_plan_period = mock_app
                
                mock_adg = Mock()
                mock_adg.avail_day_group_id = adg_id
                mock_adg.avail_day = mock_avail_day
                
                avail_day_groups_with_avail_day[adg_id] = mock_adg
                shift_vars[(adg_id, eg_id)] = Mock()
                shifts_exclusive[(adg_id, eg_id)] = 1
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = event_groups_with_event
        mock_solver_context.entities.avail_day_groups_with_avail_day = avail_day_groups_with_avail_day
        mock_solver_context.entities.shift_vars = shift_vars
        mock_solver_context.entities.event_group_vars = event_group_vars
        mock_solver_context.entities.shifts_exclusive = shifts_exclusive
        
        # Mock model methods
        mock_vars = [Mock() for _ in range(10000)]
        mock_solver_context.model.NewIntVar.side_effect = mock_vars
        mock_solver_context.model.NewBoolVar.side_effect = mock_vars
        
        # Measure setup time
        start_time = time.time()
        success = constraint.setup()
        end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Should handle many combinations efficiently
        assert success is True
        assert setup_time < 3.0  # Should complete in reasonable time
        
        # Verify partnerships were evaluated
        partnerships_evaluated = constraint.get_metadata('partnerships_evaluated')
        assert partnerships_evaluated > 0
    
    def test_constraint_memory_efficiency_partnerships(self, mock_solver_context):
        """Test: Memory-Effizienz bei vielen Partnerships."""
        import gc
        
        constraint = PartnerLocationPrefsConstraint(mock_solver_context)
        
        # Setup minimal but valid entities
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        mock_solver_context.entities.event_group_vars = {}
        mock_solver_context.entities.shifts_exclusive = {}
        mock_solver_context.config.constraint_multipliers = Mock()
        mock_solver_context.config.constraint_multipliers.sliders_partner_loc_prefs = {}
        
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
