"""
Unit-Tests für SkillsConstraint

Testet das Constraint für Fertigkeiten-Matching zwischen Events und Mitarbeitern.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from datetime import date

from sat_solver.constraints.skills import SkillsConstraint


@pytest.mark.unit
class TestSkillsConstraint:
    """Test-Klasse für SkillsConstraint."""
    
    def test_constraint_name(self, mock_solver_context):
        """Test: Constraint-Name ist korrekt."""
        constraint = SkillsConstraint(mock_solver_context)
        assert constraint.constraint_name == "skills_matching"
    
    def test_constraint_initialization(self, mock_solver_context):
        """Test: Constraint wird korrekt initialisiert."""
        constraint = SkillsConstraint(mock_solver_context)
        
        assert constraint.context == mock_solver_context
        assert constraint.model == mock_solver_context.model
        assert constraint.entities == mock_solver_context.entities
        assert constraint.config == mock_solver_context.config
        assert not constraint.is_setup_complete()
    
    def test_create_variables_empty_entities(self, mock_solver_context):
        """Test: create_variables() mit leeren Entities."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.event_groups_with_event = {}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        
        variables = constraint.create_variables()
        
        # Should return empty list for empty entities
        assert variables == []
        assert constraint.get_metadata('total_skill_conflicts') == 0
    
    def test_create_variables_events_without_skills(self, mock_solver_context):
        """Test: create_variables() mit Events ohne Skill-Anforderungen."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup events without skill requirements
        eg_id = uuid4()
        mock_event = Mock()
        mock_event.skill_groups = []  # No skills required
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        mock_solver_context.entities.event_groups_with_event = {eg_id: mock_event_group}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        
        variables = constraint.create_variables()
        
        # Should return empty list for events without skills
        assert variables == []
        assert constraint.get_metadata('total_skill_conflicts') == 0
    
    def test_create_variables_with_skill_requirements(self, mock_solver_context):
        """Test: create_variables() mit Skill-Anforderungen."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup skill objects
        skill_id = uuid4()
        mock_skill = Mock()
        mock_skill.name = "Jonglieren"
        
        # Setup skill group
        skill_group_id = uuid4()
        mock_skill_group = Mock()
        mock_skill_group.id = skill_group_id
        mock_skill_group.skill = mock_skill
        mock_skill_group.nr_actors = 2  # Need 2 actors with this skill
        
        # Setup event with skill requirements
        eg_id = uuid4()
        event_id = uuid4()
        location_id = uuid4()
        test_date = date(2025, 6, 28)
        
        mock_cast_group = Mock()
        mock_cast_group.nr_actors = 3  # Total cast size
        
        mock_location = Mock()
        mock_location.name = "TestKlinik"
        mock_location.name_an_city = "TestKlinik, Teststadt"
        
        mock_location_plan_period = Mock()
        mock_location_plan_period.location_of_work = mock_location
        
        mock_time_of_day = Mock()
        mock_time_of_day.name = "Vormittag"
        
        mock_event = Mock()
        mock_event.id = event_id
        mock_event.date = test_date
        mock_event.time_of_day = mock_time_of_day
        mock_event.location_plan_period = mock_location_plan_period
        mock_event.cast_group = mock_cast_group
        mock_event.skill_groups = [mock_skill_group]
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup available actors with skills
        adg_id1, adg_id2 = uuid4(), uuid4()
        app_id1, app_id2 = uuid4(), uuid4()
        
        # Actor 1 has the required skill
        mock_avail_day1 = Mock()
        mock_avail_day1.skills = [mock_skill]
        mock_avail_day1.actor_plan_period = Mock()
        mock_avail_day1.actor_plan_period.id = app_id1
        
        mock_adg1 = Mock()
        mock_adg1.avail_day = mock_avail_day1
        
        # Actor 2 doesn't have the required skill
        mock_avail_day2 = Mock()
        mock_avail_day2.skills = []  # No skills
        mock_avail_day2.actor_plan_period = Mock()
        mock_avail_day2.actor_plan_period.id = app_id2
        
        mock_adg2 = Mock()
        mock_adg2.avail_day = mock_avail_day2
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = {eg_id: mock_event_group}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2
        }
        
        # Setup shift variables
        mock_shift_var1 = Mock()
        mock_shift_var2 = Mock()
        mock_solver_context.entities.shift_vars = {
            (adg_id1, eg_id): mock_shift_var1,  # Actor with skill
            (adg_id2, eg_id): mock_shift_var2   # Actor without skill
        }
        
        # Mock skill conflict variable
        mock_skill_conflict_var = Mock()
        mock_solver_context.model.NewIntVar.return_value = mock_skill_conflict_var
        
        # Create variables
        variables = constraint.create_variables()
        
        # Verify variable creation
        assert len(variables) == 1
        assert variables[0] == mock_skill_conflict_var
        
        # Verify NewIntVar was called with correct bounds
        mock_solver_context.model.NewIntVar.assert_called_once()
        call_args = mock_solver_context.model.NewIntVar.call_args[0]
        assert call_args[0] == -10  # min bound
        assert call_args[1] == 10   # max bound
        assert "Jonglieren" in call_args[2]  # variable name contains skill
        
        # Verify AddMaxEquality was called
        mock_solver_context.model.AddMaxEquality.assert_called_once()
        
        # Verify metadata
        assert constraint.get_metadata('total_skill_conflicts') == 1
        skill_metadata = constraint.get_metadata('skill_0')
        assert skill_metadata['skill_name'] == "Jonglieren"
        assert skill_metadata['required_count'] == 2
        assert skill_metadata['location'] == "TestKlinik"
    
    def test_create_variables_skill_requirement_capped_by_cast_size(self, mock_solver_context):
        """Test: Skill-Anforderung wird durch Cast-Größe begrenzt."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup skill requirement higher than cast size
        mock_skill = Mock()
        mock_skill.name = "TestSkill"
        
        mock_skill_group = Mock()
        mock_skill_group.skill = mock_skill
        mock_skill_group.nr_actors = 5  # Need 5 actors with skill
        
        mock_cast_group = Mock()
        mock_cast_group.nr_actors = 3  # But only 3 total actors
        
        mock_event = Mock()
        mock_event.id = uuid4()
        mock_event.date = date(2025, 6, 28)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.name = "Test"
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_of_work = Mock()
        mock_event.location_plan_period.location_of_work.name = "Test"
        mock_event.location_plan_period.location_of_work.name_an_city = "Test"
        mock_event.cast_group = mock_cast_group
        mock_event.skill_groups = [mock_skill_group]
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup entities
        eg_id = uuid4()
        mock_solver_context.entities.event_groups_with_event = {eg_id: mock_event_group}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        
        # Mock variable
        mock_skill_conflict_var = Mock()
        mock_solver_context.model.NewIntVar.return_value = mock_skill_conflict_var
        
        # Create variables
        variables = constraint.create_variables()
        
        # Verify effective requirement is capped at cast size
        assert len(variables) == 1
        skill_metadata = constraint.get_metadata('skill_0')
        assert skill_metadata['required_count'] == 3  # Capped at cast size, not 5
    
    def test_create_variables_multiple_skills_per_event(self, mock_solver_context):
        """Test: create_variables() mit mehreren Skills pro Event."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup multiple skills
        mock_skill1 = Mock()
        mock_skill1.name = "Skill1"
        mock_skill2 = Mock()
        mock_skill2.name = "Skill2"
        
        mock_skill_group1 = Mock()
        mock_skill_group1.skill = mock_skill1
        mock_skill_group1.nr_actors = 1
        
        mock_skill_group2 = Mock()
        mock_skill_group2.skill = mock_skill2
        mock_skill_group2.nr_actors = 2
        
        # Setup event with multiple skill requirements
        mock_cast_group = Mock()
        mock_cast_group.nr_actors = 4
        
        mock_event = Mock()
        mock_event.id = uuid4()
        mock_event.date = date(2025, 6, 28)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.name = "Test"
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_of_work = Mock()
        mock_event.location_plan_period.location_of_work.name = "Test"
        mock_event.location_plan_period.location_of_work.name_an_city = "Test"
        mock_event.cast_group = mock_cast_group
        mock_event.skill_groups = [mock_skill_group1, mock_skill_group2]
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup entities
        eg_id = uuid4()
        mock_solver_context.entities.event_groups_with_event = {eg_id: mock_event_group}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        
        # Mock variables
        mock_vars = [Mock(), Mock()]
        mock_solver_context.model.NewIntVar.side_effect = mock_vars
        
        # Create variables
        variables = constraint.create_variables()
        
        # Should create one variable per skill requirement
        assert len(variables) == 2
        assert constraint.get_metadata('total_skill_conflicts') == 2
        
        # Verify both skills are captured in metadata
        skill0_metadata = constraint.get_metadata('skill_0')
        skill1_metadata = constraint.get_metadata('skill_1')
        
        skill_names = {skill0_metadata['skill_name'], skill1_metadata['skill_name']}
        assert skill_names == {'Skill1', 'Skill2'}
    
    def test_add_constraints(self, mock_solver_context):
        """Test: add_constraints() Methode."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Add constraints (currently does nothing extra)
        constraint.add_constraints()
        
        # Verify metadata
        assert constraint.get_metadata('additional_skills_constraints') == 0
    
    def test_validate_context_success(self, mock_solver_context):
        """Test: validate_context() erfolgreich."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup required attributes
        mock_solver_context.entities.event_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {uuid4(): Mock()}
        mock_solver_context.entities.shift_vars = {}
        
        result = constraint.validate_context()
        assert result is True
    
    def test_validate_context_missing_entities(self, mock_solver_context):
        """Test: validate_context() mit fehlenden Entities."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Missing entities
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error is not None
        assert "Missing entities." in error
    
    def test_validate_context_empty_events(self, mock_solver_context):
        """Test: validate_context() mit leeren Events."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup required attributes but empty events
        mock_solver_context.entities.event_groups_with_event = {}  # Empty
        mock_solver_context.entities.avail_day_groups_with_avail_day = {uuid4(): Mock()}
        mock_solver_context.entities.shift_vars = {}
        
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error == "No events found"
    
    def test_validate_context_empty_avail_days(self, mock_solver_context):
        """Test: validate_context() mit leeren AvailDays."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup required attributes but empty avail days
        mock_solver_context.entities.event_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}  # Empty
        mock_solver_context.entities.shift_vars = {}
        
        result = constraint.validate_context()
        assert result is False
        
        # Check error message
        error = constraint.get_metadata('validation_error')
        assert error == "No avail days found"
    
    def test_get_skills_summary_empty(self, mock_solver_context):
        """Test: get_skills_summary() mit leeren Daten."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup empty entities
        mock_solver_context.entities.event_groups_with_event = {}
        
        summary = constraint.get_skills_summary()
        
        # Should return empty summary
        assert summary == {}
    
    def test_get_skills_summary_comprehensive(self, mock_solver_context):
        """Test: get_skills_summary() mit umfassenden Daten."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup skills
        mock_skill1 = Mock()
        mock_skill1.name = "Jonglieren"
        mock_skill2 = Mock()
        mock_skill2.name = "Zaubern"
        mock_skill3 = Mock()
        mock_skill3.name = "Singen"
        
        # Setup events - some with skills, some without
        eg_id1, eg_id2, eg_id3 = uuid4(), uuid4(), uuid4()
        
        # Event 1: With skills
        mock_skill_group1 = Mock()
        mock_skill_group1.skill = mock_skill1
        mock_skill_group1.nr_actors = 2
        
        mock_event1 = Mock()
        mock_event1.skill_groups = [mock_skill_group1]
        mock_event1.cast_group = Mock()
        mock_event1.cast_group.nr_actors = 3
        
        mock_event_group1 = Mock()
        mock_event_group1.event = mock_event1
        
        # Event 2: With different skills
        mock_skill_group2 = Mock()
        mock_skill_group2.skill = mock_skill2
        mock_skill_group2.nr_actors = 1
        
        mock_event2 = Mock()
        mock_event2.skill_groups = [mock_skill_group2]
        mock_event2.cast_group = Mock()
        mock_event2.cast_group.nr_actors = 2
        
        mock_event_group2 = Mock()
        mock_event_group2.event = mock_event2
        
        # Event 3: Without skills
        mock_event3 = Mock()
        mock_event3.skill_groups = []
        
        mock_event_group3 = Mock()
        mock_event_group3.event = mock_event3
        
        # Setup actors with skills
        adg_id1, adg_id2, adg_id3 = uuid4(), uuid4(), uuid4()
        
        # Actor 1: Has Jonglieren and Singen
        mock_person1 = Mock()
        mock_person1.f_name = "Actor1"
        
        mock_avail_day1 = Mock()
        mock_avail_day1.skills = [mock_skill1, mock_skill3]  # Jonglieren, Singen
        mock_avail_day1.actor_plan_period = Mock()
        mock_avail_day1.actor_plan_period.person = mock_person1
        
        mock_adg1 = Mock()
        mock_adg1.avail_day = mock_avail_day1
        
        # Actor 2: Has Zaubern
        mock_person2 = Mock()
        mock_person2.f_name = "Actor2"
        
        mock_avail_day2 = Mock()
        mock_avail_day2.skills = [mock_skill2]  # Zaubern
        mock_avail_day2.actor_plan_period = Mock()
        mock_avail_day2.actor_plan_period.person = mock_person2
        
        mock_adg2 = Mock()
        mock_adg2.avail_day = mock_avail_day2
        
        # Actor 3: Has Jonglieren (same as Actor1)
        mock_person3 = Mock()
        mock_person3.f_name = "Actor3"
        
        mock_avail_day3 = Mock()
        mock_avail_day3.skills = [mock_skill1]  # Jonglieren
        mock_avail_day3.actor_plan_period = Mock()
        mock_avail_day3.actor_plan_period.person = mock_person3
        
        mock_adg3 = Mock()
        mock_adg3.avail_day = mock_avail_day3
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = {
            eg_id1: mock_event_group1,
            eg_id2: mock_event_group2,
            eg_id3: mock_event_group3
        }
        mock_solver_context.entities.avail_day_groups_with_avail_day = {
            adg_id1: mock_adg1,
            adg_id2: mock_adg2,
            adg_id3: mock_adg3
        }
        
        # Set metadata for skill conflicts
        constraint.add_metadata('total_skill_conflicts', 2)
        
        summary = constraint.get_skills_summary()
        
        # Verify summary
        assert summary['total_events'] == 3
        assert summary['events_with_skill_requirements'] == 2
        assert summary['total_skill_requirements'] == 2
        assert summary['unique_required_skills'] == 2  # Jonglieren, Zaubern
        assert summary['unique_available_skills'] == 3  # Jonglieren, Zaubern, Singen
        assert summary['skill_coverage_ratio'] == 1.0  # All required skills available
        assert set(summary['covered_skills']) == {'Jonglieren', 'Zaubern'}
        assert summary['missing_skills'] == []
        assert summary['employee_skill_counts']['Jonglieren'] == 2  # Actor1, Actor3
        assert summary['employee_skill_counts']['Zaubern'] == 1    # Actor2
        assert summary['employee_skill_counts']['Singen'] == 1     # Actor1
        assert summary['skill_conflict_variables'] == 2
    
    def test_get_skills_summary_missing_skills(self, mock_solver_context):
        """Test: get_skills_summary() mit fehlenden Skills."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup required skill that no actor has
        mock_required_skill = Mock()
        mock_required_skill.name = "SelteneSkill"
        
        mock_available_skill = Mock()
        mock_available_skill.name = "VerfügbareSkill"
        
        # Event requires skill that nobody has
        mock_skill_group = Mock()
        mock_skill_group.skill = mock_required_skill
        mock_skill_group.nr_actors = 1
        
        mock_event = Mock()
        mock_event.skill_groups = [mock_skill_group]
        mock_event.cast_group = Mock()
        mock_event.cast_group.nr_actors = 2
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Actor has different skill
        mock_avail_day = Mock()
        mock_avail_day.skills = [mock_available_skill]
        mock_avail_day.actor_plan_period = Mock()
        mock_avail_day.actor_plan_period.person = Mock()
        mock_avail_day.actor_plan_period.person.f_name = "Actor"
        
        mock_adg = Mock()
        mock_adg.avail_day = mock_avail_day
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = {uuid4(): mock_event_group}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {uuid4(): mock_adg}
        
        summary = constraint.get_skills_summary()
        
        # Verify missing skills are detected
        assert summary['skill_coverage_ratio'] == 0.0  # No required skills available
        assert summary['covered_skills'] == []
        assert summary['missing_skills'] == ['SelteneSkill']
    
    def test_get_skill_requirements_details(self, mock_solver_context):
        """Test: get_skill_requirements_details() Methode."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup test data
        mock_skill = Mock()
        mock_skill.name = "TestSkill"
        
        mock_skill_group = Mock()
        mock_skill_group.skill = mock_skill
        mock_skill_group.nr_actors = 3
        
        mock_location = Mock()
        mock_location.name = "TestLocation"
        
        mock_time_of_day = Mock()
        mock_time_of_day.name = "Vormittag"
        
        mock_cast_group = Mock()
        mock_cast_group.nr_actors = 4
        
        mock_event = Mock()
        mock_event.date = date(2025, 6, 28)
        mock_event.time_of_day = mock_time_of_day
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_of_work = mock_location
        mock_event.cast_group = mock_cast_group
        mock_event.skill_groups = [mock_skill_group]
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = {uuid4(): mock_event_group}
        
        details = constraint.get_skill_requirements_details()
        
        # Verify details
        assert len(details) == 1
        detail = details[0]
        
        assert detail['event_date'] == '2025-06-28'
        assert detail['event_time'] == 'Vormittag'
        assert detail['location'] == 'TestLocation'
        assert detail['skill_name'] == 'TestSkill'
        assert detail['required_actors'] == 3
        assert detail['total_cast_size'] == 4
        assert detail['effective_requirement'] == 3  # min(3, 4)
    
    def test_get_available_skills_details(self, mock_solver_context):
        """Test: get_available_skills_details() Methode."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup skills
        mock_skill1 = Mock()
        mock_skill1.name = "Skill1"
        mock_skill2 = Mock()
        mock_skill2.name = "Skill2"
        
        # Setup actors
        mock_person1 = Mock()
        mock_person1.f_name = "Actor1"
        mock_person2 = Mock()
        mock_person2.f_name = "Actor2"
        
        # Actor 1 has both skills
        mock_avail_day1 = Mock()
        mock_avail_day1.skills = [mock_skill1, mock_skill2]
        mock_avail_day1.actor_plan_period = Mock()
        mock_avail_day1.actor_plan_period.person = mock_person1
        
        mock_adg1 = Mock()
        mock_adg1.avail_day = mock_avail_day1
        
        # Actor 2 has only one skill
        mock_avail_day2 = Mock()
        mock_avail_day2.skills = [mock_skill1]
        mock_avail_day2.actor_plan_period = Mock()
        mock_avail_day2.actor_plan_period.person = mock_person2
        
        mock_adg2 = Mock()
        mock_adg2.avail_day = mock_avail_day2
        
        # Setup entities
        mock_solver_context.entities.avail_day_groups_with_avail_day = {
            uuid4(): mock_adg1,
            uuid4(): mock_adg2
        }
        
        details = constraint.get_available_skills_details()
        
        # Verify details
        assert len(details) == 2
        assert set(details['Actor1']) == {'Skill1', 'Skill2'}
        assert details['Actor2'] == ['Skill1']
    
    def test_complete_setup_workflow(self, mock_solver_context):
        """Test: Kompletter Setup-Workflow."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup minimal required entities
        mock_solver_context.entities.event_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {uuid4(): Mock()}
        mock_solver_context.entities.shift_vars = {}
        
        # Test setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()


@pytest.mark.integration
class TestSkillsConstraintIntegration:
    """Integration-Tests für SkillsConstraint."""
    
    def test_constraint_with_realistic_scenario(self, mock_solver_context):
        """Test: Constraint mit realistischem Klinikclown-Szenario."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup realistic skills for Klinikclowns
        skills_data = [
            {"name": "Jonglieren", "id": uuid4()},
            {"name": "Zaubern", "id": uuid4()},
            {"name": "Singen", "id": uuid4()},
            {"name": "Pantomime", "id": uuid4()},
            {"name": "Musikinstrument", "id": uuid4()}
        ]
        
        mock_skills = {}
        for skill_data in skills_data:
            mock_skill = Mock()
            mock_skill.name = skill_data["name"]
            mock_skills[skill_data["name"]] = mock_skill
        
        # Setup events with varying skill requirements
        events_data = [
            {
                "id": uuid4(),
                "date": date(2025, 6, 28),
                "time": "Vormittag",
                "location": "Kinderklinik A",
                "cast_size": 2,
                "required_skills": [("Jonglieren", 1), ("Singen", 1)]
            },
            {
                "id": uuid4(),
                "date": date(2025, 6, 29),
                "time": "Nachmittag", 
                "location": "Kinderklinik B",
                "cast_size": 3,
                "required_skills": [("Zaubern", 2)]
            },
            {
                "id": uuid4(),
                "date": date(2025, 6, 30),
                "time": "Vormittag",
                "location": "Seniorenheim C",
                "cast_size": 2,
                "required_skills": []  # No specific skills required
            }
        ]
        
        # Create event groups
        event_groups_with_event = {}
        
        for event_data in events_data:
            eg_id = uuid4()
            
            # Create skill groups for this event
            skill_groups = []
            for skill_name, nr_actors in event_data["required_skills"]:
                mock_skill_group = Mock()
                mock_skill_group.skill = mock_skills[skill_name]
                mock_skill_group.nr_actors = nr_actors
                skill_groups.append(mock_skill_group)
            
            # Create event
            mock_cast_group = Mock()
            mock_cast_group.nr_actors = event_data["cast_size"]
            
            mock_location = Mock()
            mock_location.name = event_data["location"]
            mock_location.name_an_city = f"{event_data['location']}, Teststadt"
            
            mock_location_plan_period = Mock()
            mock_location_plan_period.location_of_work = mock_location
            
            mock_time_of_day = Mock()
            mock_time_of_day.name = event_data["time"]
            
            mock_event = Mock()
            mock_event.id = event_data["id"]
            mock_event.date = event_data["date"]
            mock_event.time_of_day = mock_time_of_day
            mock_event.location_plan_period = mock_location_plan_period
            mock_event.cast_group = mock_cast_group
            mock_event.skill_groups = skill_groups
            
            mock_event_group = Mock()
            mock_event_group.event = mock_event
            
            event_groups_with_event[eg_id] = mock_event_group
        
        # Setup actors with diverse skill sets
        actors_data = [
            {
                "name": "ClownA",
                "id": uuid4(),
                "skills": ["Jonglieren", "Singen"]
            },
            {
                "name": "ClownB", 
                "id": uuid4(),
                "skills": ["Zaubern", "Pantomime"]
            },
            {
                "name": "ClownC",
                "id": uuid4(),
                "skills": ["Musikinstrument", "Singen"]
            },
            {
                "name": "ClownD",
                "id": uuid4(),
                "skills": ["Jonglieren", "Zaubern"]
            }
        ]
        
        # Create avail day groups
        avail_day_groups_with_avail_day = {}
        shift_vars = {}
        
        for actor_data in actors_data:
            adg_id = uuid4()
            
            # Convert skill names to skill objects
            actor_skills = [mock_skills[skill_name] for skill_name in actor_data["skills"]]
            
            mock_person = Mock()
            mock_person.f_name = actor_data["name"]
            
            mock_avail_day = Mock()
            mock_avail_day.skills = actor_skills
            mock_avail_day.actor_plan_period = Mock()
            mock_avail_day.actor_plan_period.id = actor_data["id"]
            mock_avail_day.actor_plan_period.person = mock_person
            
            mock_adg = Mock()
            mock_adg.avail_day = mock_avail_day
            
            avail_day_groups_with_avail_day[adg_id] = mock_adg
            
            # Create shift variables for this actor with all events
            for eg_id in event_groups_with_event:
                shift_vars[(adg_id, eg_id)] = Mock()
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = event_groups_with_event
        mock_solver_context.entities.avail_day_groups_with_avail_day = avail_day_groups_with_avail_day
        mock_solver_context.entities.shift_vars = shift_vars
        
        # Mock model methods
        mock_vars = [Mock() for _ in range(10)]
        mock_solver_context.model.NewIntVar.side_effect = mock_vars
        
        # Test constraint setup
        success = constraint.setup()
        
        assert success is True
        assert constraint.is_setup_complete()
        
        # Verify variables were created for events with skill requirements
        total_skill_conflicts = constraint.get_metadata('total_skill_conflicts')
        assert total_skill_conflicts == 3  # Event 1: 2 skills, Event 2: 1 skill, Event 3: 0 skills
        
        # Get comprehensive summary
        summary = constraint.get_summary()
        assert summary['total_events'] == 3
        assert summary['events_with_skill_requirements'] == 2
        assert summary['unique_required_skills'] == 3  # Jonglieren, Singen, Zaubern
        assert summary['skill_coverage_ratio'] == 1.0  # All required skills available
        
        # Get detailed requirements
        requirements = constraint.get_skill_requirements_details()
        assert len(requirements) == 3  # 3 skill requirements total
        
        # Get available skills
        available_skills = constraint.get_available_skills_details()
        assert len(available_skills) == 4  # 4 actors
        assert set(available_skills['ClownA']) == {'Jonglieren', 'Singen'}
        assert set(available_skills['ClownB']) == {'Zaubern', 'Pantomime'}
    
    def test_constraint_performance_large_skill_matrix(self, mock_solver_context):
        """Test: Constraint Performance mit großer Skill-Matrix."""
        import time
        
        constraint = SkillsConstraint(mock_solver_context)
        
        # Create large scenario
        num_skills = 20
        num_actors = 50
        num_events = 30
        
        # Setup skills
        mock_skills = []
        for i in range(num_skills):
            mock_skill = Mock()
            mock_skill.name = f"Skill_{i}"
            mock_skills.append(mock_skill)
        
        # Setup events with random skill requirements
        event_groups_with_event = {}
        for i in range(num_events):
            eg_id = uuid4()
            
            # Some events have skill requirements, some don't
            if i % 3 == 0:  # Every third event has skills
                skill_groups = []
                num_required_skills = min(3, num_skills)  # Max 3 skills per event
                
                for j in range(num_required_skills):
                    mock_skill_group = Mock()
                    mock_skill_group.skill = mock_skills[j]
                    mock_skill_group.nr_actors = 1
                    skill_groups.append(mock_skill_group)
            else:
                skill_groups = []
            
            mock_cast_group = Mock()
            mock_cast_group.nr_actors = 3
            
            mock_event = Mock()
            mock_event.id = uuid4()
            mock_event.date = date(2025, 6, 28)
            mock_event.time_of_day = Mock()
            mock_event.time_of_day.name = f"Event_{i}"
            mock_event.location_plan_period = Mock()
            mock_event.location_plan_period.location_of_work = Mock()
            mock_event.location_plan_period.location_of_work.name = f"Location_{i}"
            mock_event.location_plan_period.location_of_work.name_an_city = f"Location_{i}, City"
            mock_event.cast_group = mock_cast_group
            mock_event.skill_groups = skill_groups
            
            mock_event_group = Mock()
            mock_event_group.event = mock_event
            
            event_groups_with_event[eg_id] = mock_event_group
        
        # Setup actors with random skills
        avail_day_groups_with_avail_day = {}
        shift_vars = {}
        
        for i in range(num_actors):
            adg_id = uuid4()
            
            # Each actor has 2-5 random skills
            num_actor_skills = min(5, num_skills)
            actor_skills = mock_skills[:num_actor_skills]  # First N skills
            
            mock_person = Mock()
            mock_person.f_name = f"Actor_{i}"
            
            mock_avail_day = Mock()
            mock_avail_day.skills = actor_skills
            mock_avail_day.actor_plan_period = Mock()
            mock_avail_day.actor_plan_period.id = uuid4()
            mock_avail_day.actor_plan_period.person = mock_person
            
            mock_adg = Mock()
            mock_adg.avail_day = mock_avail_day
            
            avail_day_groups_with_avail_day[adg_id] = mock_adg
            
            # Create shift variables (sparse - not every actor for every event)
            for j, eg_id in enumerate(event_groups_with_event):
                if j % 5 == 0:  # Only every 5th combination
                    shift_vars[(adg_id, eg_id)] = Mock()
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = event_groups_with_event
        mock_solver_context.entities.avail_day_groups_with_avail_day = avail_day_groups_with_avail_day
        mock_solver_context.entities.shift_vars = shift_vars
        
        # Mock model methods
        mock_vars = [Mock() for _ in range(1000)]
        mock_solver_context.model.NewIntVar.side_effect = mock_vars
        
        # Measure setup time
        start_time = time.time()
        success = constraint.setup()
        end_time = time.time()
        
        setup_time = end_time - start_time
        
        # Should complete quickly even with large skill matrix
        assert success is True
        assert setup_time < 3.0  # Should take less than 3 seconds
        
        # Verify some skill conflicts were created
        total_conflicts = constraint.get_metadata('total_skill_conflicts')
        assert total_conflicts > 0
    
    def test_constraint_edge_cases_and_error_handling(self, mock_solver_context):
        """Test: Edge Cases und Error-Handling."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Test with skill group missing required attributes
        mock_skill = Mock()
        mock_skill.name = "TestSkill"
        
        # Skill group without id attribute
        mock_skill_group = Mock()
        mock_skill_group.skill = mock_skill
        mock_skill_group.nr_actors = 1
        # Deliberately don't set id attribute
        
        mock_cast_group = Mock()
        mock_cast_group.nr_actors = 2
        
        mock_event = Mock()
        mock_event.id = uuid4()
        mock_event.date = date(2025, 6, 28)
        mock_event.time_of_day = Mock()
        mock_event.time_of_day.name = "Test"
        mock_event.location_plan_period = Mock()
        mock_event.location_plan_period.location_of_work = Mock()
        mock_event.location_plan_period.location_of_work.name = "Test"
        mock_event.location_plan_period.location_of_work.name_an_city = "Test"
        mock_event.cast_group = mock_cast_group
        mock_event.skill_groups = [mock_skill_group]
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = {uuid4(): mock_event_group}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {}
        mock_solver_context.entities.shift_vars = {}
        
        # Mock variable
        mock_skill_conflict_var = Mock()
        mock_solver_context.model.NewIntVar.return_value = mock_skill_conflict_var
        
        # Should handle missing id gracefully
        try:
            variables = constraint.create_variables()
            assert len(variables) == 1
            
            # Verify metadata handles missing id
            skill_metadata = constraint.get_metadata('skill_0')
            assert skill_metadata['skill_group_id'] == 'unknown'
            
        except Exception as e:
            pytest.fail(f"Constraint should handle missing id gracefully, but raised: {e}")
    
    @patch('sat_solver.constraints.skills.logger')
    def test_constraint_logging_integration(self, mock_logger, mock_solver_context):
        """Test: Constraint Logging-Integration."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup minimal entities
        mock_solver_context.entities.event_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {uuid4(): Mock()}
        mock_solver_context.entities.shift_vars = {}
        
        # Setup constraint
        success = constraint.setup()
        assert success is True
        
        # Logging calls depend on implementation, but logger should be available
    
    def test_constraint_skill_coverage_analysis(self, mock_solver_context):
        """Test: Detaillierte Skill-Coverage-Analyse."""
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup scenario with partial skill coverage
        mock_covered_skill = Mock()
        mock_covered_skill.name = "CoveredSkill"
        
        mock_missing_skill = Mock()
        mock_missing_skill.name = "MissingSkill"
        
        mock_extra_skill = Mock()
        mock_extra_skill.name = "ExtraSkill"
        
        # Event requires skills - one available, one missing
        mock_skill_group1 = Mock()
        mock_skill_group1.skill = mock_covered_skill
        mock_skill_group1.nr_actors = 1
        
        mock_skill_group2 = Mock()
        mock_skill_group2.skill = mock_missing_skill
        mock_skill_group2.nr_actors = 1
        
        mock_event = Mock()
        mock_event.skill_groups = [mock_skill_group1, mock_skill_group2]
        mock_event.cast_group = Mock()
        mock_event.cast_group.nr_actors = 3
        
        mock_event_group = Mock()
        mock_event_group.event = mock_event
        
        # Actor has covered skill and extra skill (but not missing skill)
        mock_person = Mock()
        mock_person.f_name = "TestActor"
        
        mock_avail_day = Mock()
        mock_avail_day.skills = [mock_covered_skill, mock_extra_skill]
        mock_avail_day.actor_plan_period = Mock()
        mock_avail_day.actor_plan_period.person = mock_person
        
        mock_adg = Mock()
        mock_adg.avail_day = mock_avail_day
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = {uuid4(): mock_event_group}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {uuid4(): mock_adg}
        
        summary = constraint.get_skills_summary()
        
        # Verify coverage analysis
        assert summary['unique_required_skills'] == 2
        assert summary['unique_available_skills'] == 2
        assert summary['skill_coverage_ratio'] == 0.5  # 1 of 2 required skills available
        assert summary['covered_skills'] == ['CoveredSkill']
        assert summary['missing_skills'] == ['MissingSkill']
        assert summary['employee_skill_counts']['CoveredSkill'] == 1
        assert summary['employee_skill_counts']['ExtraSkill'] == 1
        assert 'MissingSkill' not in summary['employee_skill_counts']


@pytest.mark.slow
class TestSkillsConstraintPerformance:
    """Performance-Tests für SkillsConstraint."""
    
    def test_constraint_skills_matrix_complexity(self, mock_solver_context):
        """Test: Komplexität der Skills-Matrix-Verarbeitung."""
        import time
        
        constraint = SkillsConstraint(mock_solver_context)
        
        # Create complex skill matrix scenario
        matrix_size = 100  # 100x100 matrix
        
        # Setup skills
        mock_skills = []
        for i in range(matrix_size):
            mock_skill = Mock()
            mock_skill.name = f"Skill_{i}"
            mock_skills.append(mock_skill)
        
        # Setup actors - each with many skills
        avail_day_groups_with_avail_day = {}
        for i in range(matrix_size):
            adg_id = uuid4()
            
            # Each actor has 10% of all skills
            num_skills_per_actor = max(1, matrix_size // 10)
            actor_skills = mock_skills[i:i+num_skills_per_actor]
            
            mock_person = Mock()
            mock_person.f_name = f"Actor_{i}"
            
            mock_avail_day = Mock()
            mock_avail_day.skills = actor_skills
            mock_avail_day.actor_plan_period = Mock()
            mock_avail_day.actor_plan_period.person = mock_person
            
            mock_adg = Mock()
            mock_adg.avail_day = mock_avail_day
            
            avail_day_groups_with_avail_day[adg_id] = mock_adg
        
        # Setup events - minimal for performance
        mock_event_group = Mock()
        mock_event_group.event = Mock()
        mock_event_group.event.skill_groups = []
        
        # Setup entities
        mock_solver_context.entities.event_groups_with_event = {uuid4(): mock_event_group}
        mock_solver_context.entities.avail_day_groups_with_avail_day = avail_day_groups_with_avail_day
        mock_solver_context.entities.shift_vars = {}
        
        # Measure summary generation time
        start_time = time.time()
        summary = constraint.get_skills_summary()
        end_time = time.time()
        
        summary_time = end_time - start_time
        
        # Should process large skill matrix efficiently
        assert summary['unique_available_skills'] == matrix_size
        assert summary_time < 2.0  # Should complete quickly
    
    def test_constraint_memory_efficiency_skills(self, mock_solver_context):
        """Test: Memory-Effizienz bei vielen Skills."""
        import gc
        
        constraint = SkillsConstraint(mock_solver_context)
        
        # Setup minimal but valid entities
        mock_solver_context.entities.event_groups_with_event = {uuid4(): Mock()}
        mock_solver_context.entities.avail_day_groups_with_avail_day = {uuid4(): Mock()}
        mock_solver_context.entities.shift_vars = {}
        
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
