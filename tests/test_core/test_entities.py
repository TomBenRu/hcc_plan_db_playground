"""
Unit-Tests für Entities-Datenklasse

Testet die zentrale Datenstruktur für alle SAT-Solver Entitäten.
"""

import pytest
from unittest.mock import Mock
from uuid import uuid4
from collections import defaultdict

from sat_solver.core.entities import Entities


@pytest.mark.unit
class TestEntities:
    """Test-Klasse für Entities."""
    
    def test_entities_initialization(self):
        """Test: Entities wird korrekt initialisiert."""
        entities = Entities()
        
        # Verify all dictionaries are initialized
        assert isinstance(entities.actor_plan_periods, dict)
        assert isinstance(entities.event_groups, dict)
        assert isinstance(entities.avail_day_groups, dict)
        assert isinstance(entities.cast_groups, dict)
        assert isinstance(entities.events, dict)
        assert isinstance(entities.avail_days, dict)
        assert isinstance(entities.locations, dict)
        assert isinstance(entities.skills, dict)
        assert isinstance(entities.time_of_days, dict)
        
        # Verify all start empty
        assert len(entities.actor_plan_periods) == 0
        assert len(entities.event_groups) == 0
        assert len(entities.avail_day_groups) == 0
        assert len(entities.cast_groups) == 0
        assert len(entities.events) == 0
        assert len(entities.avail_days) == 0
        assert len(entities.locations) == 0
        assert len(entities.skills) == 0
        assert len(entities.time_of_days) == 0
    
    def test_entities_actor_plan_periods_management(self):
        """Test: Actor Plan Periods Management."""
        entities = Entities()
        
        # Create mock actor plan periods
        app1_id = uuid4()
        app2_id = uuid4()
        mock_app1 = Mock()
        mock_app1.id = app1_id
        mock_app2 = Mock()
        mock_app2.id = app2_id
        
        # Add actor plan periods
        entities.actor_plan_periods[app1_id] = mock_app1
        entities.actor_plan_periods[app2_id] = mock_app2
        
        # Verify
        assert len(entities.actor_plan_periods) == 2
        assert entities.actor_plan_periods[app1_id] == mock_app1
        assert entities.actor_plan_periods[app2_id] == mock_app2
    
    def test_entities_event_groups_management(self):
        """Test: Event Groups Management."""
        entities = Entities()
        
        # Create mock event groups
        eg1_id = uuid4()
        eg2_id = uuid4()
        mock_eg1 = Mock()
        mock_eg1.event_group_id = eg1_id
        mock_eg2 = Mock()
        mock_eg2.event_group_id = eg2_id
        
        # Add event groups
        entities.event_groups[eg1_id] = mock_eg1
        entities.event_groups[eg2_id] = mock_eg2
        
        # Verify
        assert len(entities.event_groups) == 2
        assert entities.event_groups[eg1_id] == mock_eg1
        assert entities.event_groups[eg2_id] == mock_eg2
    
    def test_entities_avail_day_groups_management(self):
        """Test: Avail Day Groups Management."""
        entities = Entities()
        
        # Create mock avail day groups
        adg1_id = uuid4()
        adg2_id = uuid4()
        mock_adg1 = Mock()
        mock_adg1.avail_day_group_id = adg1_id
        mock_adg2 = Mock()
        mock_adg2.avail_day_group_id = adg2_id
        
        # Add avail day groups
        entities.avail_day_groups[adg1_id] = mock_adg1
        entities.avail_day_groups[adg2_id] = mock_adg2
        
        # Verify
        assert len(entities.avail_day_groups) == 2
        assert entities.avail_day_groups[adg1_id] == mock_adg1
        assert entities.avail_day_groups[adg2_id] == mock_adg2
    
    def test_entities_cast_groups_management(self):
        """Test: Cast Groups Management."""
        entities = Entities()
        
        # Create mock cast groups
        cg1_id = uuid4()
        cg2_id = uuid4()
        mock_cg1 = Mock()
        mock_cg1.cast_group_id = cg1_id
        mock_cg2 = Mock()
        mock_cg2.cast_group_id = cg2_id
        
        # Add cast groups
        entities.cast_groups[cg1_id] = mock_cg1
        entities.cast_groups[cg2_id] = mock_cg2
        
        # Verify
        assert len(entities.cast_groups) == 2
        assert entities.cast_groups[cg1_id] == mock_cg1
        assert entities.cast_groups[cg2_id] == mock_cg2
    
    def test_entities_events_management(self):
        """Test: Events Management."""
        entities = Entities()
        
        # Create mock events
        event1_id = uuid4()
        event2_id = uuid4()
        mock_event1 = Mock()
        mock_event1.id = event1_id
        mock_event2 = Mock()
        mock_event2.id = event2_id
        
        # Add events
        entities.events[event1_id] = mock_event1
        entities.events[event2_id] = mock_event2
        
        # Verify
        assert len(entities.events) == 2
        assert entities.events[event1_id] == mock_event1
        assert entities.events[event2_id] == mock_event2
    
    def test_entities_avail_days_management(self):
        """Test: Avail Days Management."""
        entities = Entities()
        
        # Create mock avail days
        ad1_id = uuid4()
        ad2_id = uuid4()
        mock_ad1 = Mock()
        mock_ad1.id = ad1_id
        mock_ad2 = Mock()
        mock_ad2.id = ad2_id
        
        # Add avail days
        entities.avail_days[ad1_id] = mock_ad1
        entities.avail_days[ad2_id] = mock_ad2
        
        # Verify
        assert len(entities.avail_days) == 2
        assert entities.avail_days[ad1_id] == mock_ad1
        assert entities.avail_days[ad2_id] == mock_ad2
    
    def test_entities_locations_management(self):
        """Test: Locations Management."""
        entities = Entities()
        
        # Create mock locations
        loc1_id = uuid4()
        loc2_id = uuid4()
        mock_loc1 = Mock()
        mock_loc1.id = loc1_id
        mock_loc2 = Mock()
        mock_loc2.id = loc2_id
        
        # Add locations
        entities.locations[loc1_id] = mock_loc1
        entities.locations[loc2_id] = mock_loc2
        
        # Verify
        assert len(entities.locations) == 2
        assert entities.locations[loc1_id] == mock_loc1
        assert entities.locations[loc2_id] == mock_loc2
    
    def test_entities_skills_management(self):
        """Test: Skills Management."""
        entities = Entities()
        
        # Create mock skills
        skill1_id = uuid4()
        skill2_id = uuid4()
        mock_skill1 = Mock()
        mock_skill1.id = skill1_id
        mock_skill2 = Mock()
        mock_skill2.id = skill2_id
        
        # Add skills
        entities.skills[skill1_id] = mock_skill1
        entities.skills[skill2_id] = mock_skill2
        
        # Verify
        assert len(entities.skills) == 2
        assert entities.skills[skill1_id] == mock_skill1
        assert entities.skills[skill2_id] == mock_skill2
    
    def test_entities_time_of_days_management(self):
        """Test: Time of Days Management."""
        entities = Entities()
        
        # Create mock time of days
        tod1_id = uuid4()
        tod2_id = uuid4()
        mock_tod1 = Mock()
        mock_tod1.id = tod1_id
        mock_tod2 = Mock()
        mock_tod2.id = tod2_id
        
        # Add time of days
        entities.time_of_days[tod1_id] = mock_tod1
        entities.time_of_days[tod2_id] = mock_tod2
        
        # Verify
        assert len(entities.time_of_days) == 2
        assert entities.time_of_days[tod1_id] == mock_tod1
        assert entities.time_of_days[tod2_id] == mock_tod2
    
    def test_entities_mixed_operations(self):
        """Test: Gemischte Operationen auf verschiedenen Entity-Typen."""
        entities = Entities()
        
        # Add different types of entities
        app_id = uuid4()
        eg_id = uuid4()
        event_id = uuid4()
        
        mock_app = Mock()
        mock_eg = Mock()
        mock_event = Mock()
        
        entities.actor_plan_periods[app_id] = mock_app
        entities.event_groups[eg_id] = mock_eg
        entities.events[event_id] = mock_event
        
        # Verify isolation
        assert len(entities.actor_plan_periods) == 1
        assert len(entities.event_groups) == 1
        assert len(entities.events) == 1
        assert len(entities.avail_day_groups) == 0  # Should remain empty
        assert len(entities.cast_groups) == 0  # Should remain empty
    
    def test_entities_key_uniqueness(self):
        """Test: Eindeutigkeit der Schlüssel in den verschiedenen Dictionaries."""
        entities = Entities()
        
        # Use same UUID for different entity types (should be fine)
        same_id = uuid4()
        
        mock_app = Mock()
        mock_eg = Mock()
        mock_event = Mock()
        
        entities.actor_plan_periods[same_id] = mock_app
        entities.event_groups[same_id] = mock_eg
        entities.events[same_id] = mock_event
        
        # Should work fine - different dictionaries
        assert entities.actor_plan_periods[same_id] == mock_app
        assert entities.event_groups[same_id] == mock_eg
        assert entities.events[same_id] == mock_event
    
    def test_entities_overwriting(self):
        """Test: Überschreiben von Einträgen."""
        entities = Entities()
        
        app_id = uuid4()
        mock_app1 = Mock()
        mock_app1.name = "First App"
        mock_app2 = Mock()
        mock_app2.name = "Second App"
        
        # Add first
        entities.actor_plan_periods[app_id] = mock_app1
        assert entities.actor_plan_periods[app_id].name == "First App"
        
        # Overwrite
        entities.actor_plan_periods[app_id] = mock_app2
        assert entities.actor_plan_periods[app_id].name == "Second App"
        assert len(entities.actor_plan_periods) == 1  # Still only one entry
    
    def test_entities_empty_after_clear(self):
        """Test: Entities können geleert werden."""
        entities = Entities()
        
        # Add some data
        entities.actor_plan_periods[uuid4()] = Mock()
        entities.event_groups[uuid4()] = Mock()
        entities.events[uuid4()] = Mock()
        
        # Verify data exists
        assert len(entities.actor_plan_periods) == 1
        assert len(entities.event_groups) == 1
        assert len(entities.events) == 1
        
        # Clear
        entities.actor_plan_periods.clear()
        entities.event_groups.clear()
        entities.events.clear()
        
        # Verify empty
        assert len(entities.actor_plan_periods) == 0
        assert len(entities.event_groups) == 0
        assert len(entities.events) == 0


@pytest.mark.integration
class TestEntitiesIntegration:
    """Integration-Tests für Entities mit Mock-Daten."""
    
    def test_entities_with_realistic_data_structure(self):
        """Test: Entities mit realistischer Datenstruktur."""
        entities = Entities()
        
        # Create realistic mock structure
        plan_period_id = uuid4()
        
        # Actor Plan Period
        app = Mock()
        app.id = uuid4()
        app.plan_period_id = plan_period_id
        app.person = Mock()
        app.person.f_name = "John"
        app.person.l_name = "Doe"
        app.requested_assignments = 10
        entities.actor_plan_periods[app.id] = app
        
        # Event Group with Event
        event_group = Mock()
        event_group.event_group_id = uuid4()
        event_group.name = "Test Event Group"
        event_group.children = []
        
        event = Mock()
        event.id = uuid4()
        event.event_group = event_group
        event.date = "2025-06-28"
        
        entities.event_groups[event_group.event_group_id] = event_group
        entities.events[event.id] = event
        
        # Avail Day Group with Avail Day
        avail_day_group = Mock()
        avail_day_group.avail_day_group_id = uuid4()
        avail_day_group.name = "Test Avail Day Group"
        
        avail_day = Mock()
        avail_day.id = uuid4()
        avail_day.avail_day_group = avail_day_group
        avail_day.actor_plan_period = app
        avail_day.date = "2025-06-28"
        
        entities.avail_day_groups[avail_day_group.avail_day_group_id] = avail_day_group
        entities.avail_days[avail_day.id] = avail_day
        
        # Verify relationships
        assert len(entities.actor_plan_periods) == 1
        assert len(entities.event_groups) == 1
        assert len(entities.events) == 1
        assert len(entities.avail_day_groups) == 1
        assert len(entities.avail_days) == 1
        
        # Verify cross-references work
        assert entities.avail_days[avail_day.id].actor_plan_period == entities.actor_plan_periods[app.id]
        assert entities.events[event.id].event_group == entities.event_groups[event_group.event_group_id]
    
    def test_entities_large_dataset_simulation(self):
        """Test: Entities mit größerem simuliertem Dataset."""
        entities = Entities()
        
        # Simulate larger dataset
        num_actors = 50
        num_events = 100
        num_avail_days = 200
        
        # Create actors
        for i in range(num_actors):
            app = Mock()
            app.id = uuid4()
            app.person = Mock()
            app.person.f_name = f"Actor_{i}"
            entities.actor_plan_periods[app.id] = app
        
        # Create events
        for i in range(num_events):
            event = Mock()
            event.id = uuid4()
            event.name = f"Event_{i}"
            entities.events[event.id] = event
        
        # Create avail days
        for i in range(num_avail_days):
            avail_day = Mock()
            avail_day.id = uuid4()
            avail_day.name = f"AvailDay_{i}"
            entities.avail_days[avail_day.id] = avail_day
        
        # Verify counts
        assert len(entities.actor_plan_periods) == num_actors
        assert len(entities.events) == num_events
        assert len(entities.avail_days) == num_avail_days
        
        # Verify performance (should be fast with dictionaries)
        import time
        start_time = time.time()
        
        # Perform some lookups
        for app_id in list(entities.actor_plan_periods.keys())[:10]:
            assert entities.actor_plan_periods[app_id] is not None
        
        end_time = time.time()
        lookup_time = end_time - start_time
        
        # Should be very fast (under 0.1 seconds)
        assert lookup_time < 0.1
    
    def test_entities_memory_efficiency(self):
        """Test: Memory-Effizienz der Entities-Struktur."""
        import sys
        
        entities = Entities()
        
        # Measure initial size
        initial_size = sys.getsizeof(entities.__dict__)
        
        # Add some data
        for i in range(100):
            app = Mock()
            app.id = uuid4()
            entities.actor_plan_periods[app.id] = app
        
        # Measure size after adding data
        final_size = sys.getsizeof(entities.__dict__)
        
        # Verify structure doesn't grow excessively
        # (Exact values depend on Python implementation)
        assert final_size > initial_size  # Should grow
        assert len(entities.actor_plan_periods) == 100  # Verify data was added
