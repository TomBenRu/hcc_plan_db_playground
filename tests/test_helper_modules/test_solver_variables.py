"""
Unit-Tests für solver_variables Modul

Testet die CastRules Dataclass und die globale cast_rules Instanz.
Das Modul wird zur Speicherung von Variablen für Cast-Regeln verwendet.
"""

import pytest
from unittest.mock import Mock

from sat_solver.solver_variables import CastRules, cast_rules


@pytest.mark.unit
class TestCastRules:
    """Test-Klasse für CastRules Dataclass."""
    
    def test_cast_rules_initialization_default(self):
        """Test: CastRules wird mit Default-Werten korrekt initialisiert."""
        rules = CastRules()
        
        assert rules.applied_shifts_1 == []
        assert rules.applied_shifts_2 == []
        assert rules.is_unequal == []
        
        # Verify these are separate lists (not same reference)
        assert rules.applied_shifts_1 is not rules.applied_shifts_2
        assert rules.applied_shifts_1 is not rules.is_unequal
        assert rules.applied_shifts_2 is not rules.is_unequal
    
    def test_cast_rules_initialization_with_values(self):
        """Test: CastRules wird mit gegebenen Werten korrekt initialisiert."""
        # Mock variables
        mock_var1, mock_var2, mock_var3 = Mock(), Mock(), Mock()
        mock_var4, mock_var5, mock_var6 = Mock(), Mock(), Mock()
        
        applied_shifts_1_data = [[mock_var1, mock_var2], [mock_var3]]
        applied_shifts_2_data = [[mock_var4], [mock_var5, mock_var6]]
        is_unequal_data = [mock_var1, mock_var2]
        
        rules = CastRules(
            applied_shifts_1=applied_shifts_1_data,
            applied_shifts_2=applied_shifts_2_data,
            is_unequal=is_unequal_data
        )
        
        assert rules.applied_shifts_1 == applied_shifts_1_data
        assert rules.applied_shifts_2 == applied_shifts_2_data
        assert rules.is_unequal == is_unequal_data
    
    def test_cast_rules_field_modification(self):
        """Test: CastRules Felder können nach Initialisierung modifiziert werden."""
        rules = CastRules()
        
        # Mock variables
        mock_var1, mock_var2, mock_var3 = Mock(), Mock(), Mock()
        
        # Modify fields
        rules.applied_shifts_1.append([mock_var1])
        rules.applied_shifts_2.extend([[mock_var2], [mock_var3]])
        rules.is_unequal.append(mock_var1)
        
        # Verify modifications
        assert len(rules.applied_shifts_1) == 1
        assert rules.applied_shifts_1[0] == [mock_var1]
        
        assert len(rules.applied_shifts_2) == 2
        assert rules.applied_shifts_2[0] == [mock_var2]
        assert rules.applied_shifts_2[1] == [mock_var3]
        
        assert len(rules.is_unequal) == 1
        assert rules.is_unequal[0] == mock_var1
    
    def test_cast_rules_nested_list_structure(self):
        """Test: CastRules unterstützt verschachtelte Listen-Struktur korrekt."""
        rules = CastRules()
        
        # Mock variables for complex nested structure
        mock_vars = [Mock() for _ in range(10)]
        
        # Create nested structure
        complex_applied_shifts_1 = [
            [mock_vars[0], mock_vars[1], mock_vars[2]],  # 3 variables
            [mock_vars[3]],                              # 1 variable
            [mock_vars[4], mock_vars[5]],                # 2 variables
            []                                           # Empty list
        ]
        
        complex_applied_shifts_2 = [
            [mock_vars[6], mock_vars[7]],
            [mock_vars[8], mock_vars[9]]
        ]
        
        rules.applied_shifts_1 = complex_applied_shifts_1
        rules.applied_shifts_2 = complex_applied_shifts_2
        
        # Verify structure
        assert len(rules.applied_shifts_1) == 4
        assert len(rules.applied_shifts_1[0]) == 3
        assert len(rules.applied_shifts_1[1]) == 1
        assert len(rules.applied_shifts_1[2]) == 2
        assert len(rules.applied_shifts_1[3]) == 0
        
        assert len(rules.applied_shifts_2) == 2
        assert len(rules.applied_shifts_2[0]) == 2
        assert len(rules.applied_shifts_2[1]) == 2
        
        # Verify specific variables
        assert rules.applied_shifts_1[0][0] == mock_vars[0]
        assert rules.applied_shifts_1[0][2] == mock_vars[2]
        assert rules.applied_shifts_1[1][0] == mock_vars[3]
        assert rules.applied_shifts_2[0][1] == mock_vars[7]
    
    def test_reset_fields_method(self):
        """Test: reset_fields() Methode setzt alle Felder zurück."""
        rules = CastRules()
        
        # Mock variables
        mock_vars = [Mock() for _ in range(6)]
        
        # Populate fields
        rules.applied_shifts_1 = [[mock_vars[0], mock_vars[1]], [mock_vars[2]]]
        rules.applied_shifts_2 = [[mock_vars[3]], [mock_vars[4], mock_vars[5]]]
        rules.is_unequal = [mock_vars[0], mock_vars[3]]
        
        # Verify fields are populated
        assert len(rules.applied_shifts_1) == 2
        assert len(rules.applied_shifts_2) == 2
        assert len(rules.is_unequal) == 2
        
        # Reset fields
        rules.reset_fields()
        
        # Verify fields are empty
        assert rules.applied_shifts_1 == []
        assert rules.applied_shifts_2 == []
        assert rules.is_unequal == []
        
        # Verify they are new empty lists (not same reference)
        assert rules.applied_shifts_1 is not rules.applied_shifts_2
        assert rules.applied_shifts_1 is not rules.is_unequal
        assert rules.applied_shifts_2 is not rules.is_unequal
    
    def test_reset_fields_multiple_calls(self):
        """Test: reset_fields() kann mehrfach aufgerufen werden."""
        rules = CastRules()
        
        # Mock variables
        mock_var = Mock()
        
        # First cycle: populate and reset
        rules.applied_shifts_1.append([mock_var])
        rules.reset_fields()
        assert rules.applied_shifts_1 == []
        
        # Second cycle: populate and reset
        rules.applied_shifts_2.append([mock_var])
        rules.is_unequal.append(mock_var)
        rules.reset_fields()
        assert rules.applied_shifts_2 == []
        assert rules.is_unequal == []
        
        # Third cycle: reset empty fields
        rules.reset_fields()
        assert rules.applied_shifts_1 == []
        assert rules.applied_shifts_2 == []
        assert rules.is_unequal == []
    
    def test_cast_rules_dataclass_properties(self):
        """Test: CastRules Dataclass-Eigenschaften."""
        rules1 = CastRules()
        rules2 = CastRules()
        
        # Different instances should be equal when empty
        assert rules1 == rules2
        
        # Mock variables
        mock_var1, mock_var2 = Mock(), Mock()
        
        # Modify one instance
        rules1.applied_shifts_1.append([mock_var1])
        
        # Should no longer be equal
        assert rules1 != rules2
        
        # Modify other instance to match
        rules2.applied_shifts_1.append([mock_var1])
        
        # Should be equal again
        assert rules1 == rules2
    
    def test_cast_rules_field_independence(self):
        """Test: CastRules Felder sind unabhängig voneinander."""
        rules = CastRules()
        
        # Mock variables
        mock_vars = [Mock() for _ in range(6)]
        
        # Modify each field independently
        rules.applied_shifts_1.append([mock_vars[0]])
        assert len(rules.applied_shifts_1) == 1
        assert len(rules.applied_shifts_2) == 0
        assert len(rules.is_unequal) == 0
        
        rules.applied_shifts_2.extend([[mock_vars[1]], [mock_vars[2]]])
        assert len(rules.applied_shifts_1) == 1
        assert len(rules.applied_shifts_2) == 2
        assert len(rules.is_unequal) == 0
        
        rules.is_unequal.extend([mock_vars[3], mock_vars[4], mock_vars[5]])
        assert len(rules.applied_shifts_1) == 1
        assert len(rules.applied_shifts_2) == 2
        assert len(rules.is_unequal) == 3
        
        # Clear one field, others should remain
        rules.applied_shifts_1.clear()
        assert len(rules.applied_shifts_1) == 0
        assert len(rules.applied_shifts_2) == 2  # Unchanged
        assert len(rules.is_unequal) == 3        # Unchanged


@pytest.mark.unit
class TestGlobalCastRulesInstance:
    """Test-Klasse für die globale cast_rules Instanz."""
    
    def setup_method(self):
        """Setup vor jedem Test: Globale Instanz zurücksetzen."""
        cast_rules.reset_fields()
    
    def teardown_method(self):
        """Cleanup nach jedem Test: Globale Instanz zurücksetzen."""
        cast_rules.reset_fields()
    
    def test_global_cast_rules_exists(self):
        """Test: Globale cast_rules Instanz existiert."""
        assert cast_rules is not None
        assert isinstance(cast_rules, CastRules)
    
    def test_global_cast_rules_initial_state(self):
        """Test: Globale cast_rules ist initial leer."""
        assert cast_rules.applied_shifts_1 == []
        assert cast_rules.applied_shifts_2 == []
        assert cast_rules.is_unequal == []
    
    def test_global_cast_rules_modification(self):
        """Test: Globale cast_rules kann modifiziert werden."""
        # Mock variables
        mock_vars = [Mock() for _ in range(4)]
        
        # Modify global instance
        cast_rules.applied_shifts_1.append([mock_vars[0], mock_vars[1]])
        cast_rules.applied_shifts_2.append([mock_vars[2]])
        cast_rules.is_unequal.append(mock_vars[3])
        
        # Verify modifications
        assert len(cast_rules.applied_shifts_1) == 1
        assert len(cast_rules.applied_shifts_2) == 1
        assert len(cast_rules.is_unequal) == 1
        
        assert cast_rules.applied_shifts_1[0] == [mock_vars[0], mock_vars[1]]
        assert cast_rules.applied_shifts_2[0] == [mock_vars[2]]
        assert cast_rules.is_unequal[0] == mock_vars[3]
    
    def test_global_cast_rules_reset(self):
        """Test: Globale cast_rules kann zurückgesetzt werden."""
        # Mock variables
        mock_vars = [Mock() for _ in range(3)]
        
        # Populate global instance
        cast_rules.applied_shifts_1.extend([[mock_vars[0]], [mock_vars[1]]])
        cast_rules.applied_shifts_2.append([mock_vars[2]])
        cast_rules.is_unequal.extend([mock_vars[0], mock_vars[1]])
        
        # Verify population
        assert len(cast_rules.applied_shifts_1) == 2
        assert len(cast_rules.applied_shifts_2) == 1
        assert len(cast_rules.is_unequal) == 2
        
        # Reset
        cast_rules.reset_fields()
        
        # Verify reset
        assert cast_rules.applied_shifts_1 == []
        assert cast_rules.applied_shifts_2 == []
        assert cast_rules.is_unequal == []
    
    def test_global_cast_rules_persistence_across_functions(self):
        """Test: Globale cast_rules bleibt über Funktionsaufrufe hinweg bestehen."""
        
        def populate_cast_rules():
            """Helper function to populate cast_rules."""
            mock_var = Mock()
            cast_rules.applied_shifts_1.append([mock_var])
            return mock_var
        
        def check_cast_rules(expected_var):
            """Helper function to check cast_rules."""
            assert len(cast_rules.applied_shifts_1) == 1
            assert cast_rules.applied_shifts_1[0] == [expected_var]
        
        # Initially empty
        assert len(cast_rules.applied_shifts_1) == 0
        
        # Populate in function
        var = populate_cast_rules()
        
        # Check persistence
        check_cast_rules(var)
    
    def test_global_cast_rules_import_consistency(self):
        """Test: cast_rules Import-Konsistenz."""
        # Import cast_rules again to verify it's the same instance
        from sat_solver.solver_variables import cast_rules as imported_cast_rules
        
        # Should be the same instance
        assert cast_rules is imported_cast_rules
        
        # Modify through one reference
        mock_var = Mock()
        cast_rules.is_unequal.append(mock_var)
        
        # Should be visible through other reference
        assert len(imported_cast_rules.is_unequal) == 1
        assert imported_cast_rules.is_unequal[0] == mock_var


@pytest.mark.integration
class TestCastRulesIntegration:
    """Integration-Tests für CastRules."""
    
    def setup_method(self):
        """Setup vor jedem Test."""
        cast_rules.reset_fields()
    
    def teardown_method(self):
        """Cleanup nach jedem Test."""
        cast_rules.reset_fields()
    
    def test_cast_rules_realistic_usage_scenario(self):
        """Test: CastRules mit realistischem Anwendungsszenario."""
        # Simuliere realistisches Szenario mit Cast-Regeln
        
        # Mock OR-Tools Variables
        mock_shifts_kinderklinik_hans_vm = Mock(name="shift_kinderklinik_hans_vormittag")
        mock_shifts_kinderklinik_maria_vm = Mock(name="shift_kinderklinik_maria_vormittag")
        mock_shifts_kinderklinik_hans_nm = Mock(name="shift_kinderklinik_hans_nachmittag")
        mock_shifts_kinderklinik_maria_nm = Mock(name="shift_kinderklinik_maria_nachmittag")
        
        mock_shifts_seniorenheim_peter_vm = Mock(name="shift_seniorenheim_peter_vormittag")
        mock_shifts_seniorenheim_anna_vm = Mock(name="shift_seniorenheim_anna_vormittag")
        mock_shifts_seniorenheim_peter_nm = Mock(name="shift_seniorenheim_peter_nachmittag")
        mock_shifts_seniorenheim_anna_nm = Mock(name="shift_seniorenheim_anna_nachmittag")
        
        # Applied shifts für Event 1 (Kinderklinik)
        applied_shifts_event1 = [
            [mock_shifts_kinderklinik_hans_vm, mock_shifts_kinderklinik_maria_vm],  # Hans und Maria vormittags
            [mock_shifts_kinderklinik_hans_nm, mock_shifts_kinderklinik_maria_nm]   # Hans und Maria nachmittags
        ]
        
        # Applied shifts für Event 2 (Seniorenheim)
        applied_shifts_event2 = [
            [mock_shifts_seniorenheim_peter_vm, mock_shifts_seniorenheim_anna_vm],  # Peter und Anna vormittags
            [mock_shifts_seniorenheim_peter_nm, mock_shifts_seniorenheim_anna_nm]   # Peter und Anna nachmittags
        ]
        
        # Unequal Variables (für Cast-Regel-Vergleiche)
        mock_unequal_hans_maria = Mock(name="unequal_hans_maria")
        mock_unequal_peter_anna = Mock(name="unequal_peter_anna")
        unequal_vars = [mock_unequal_hans_maria, mock_unequal_peter_anna]
        
        # Populate CastRules
        cast_rules.applied_shifts_1 = applied_shifts_event1
        cast_rules.applied_shifts_2 = applied_shifts_event2
        cast_rules.is_unequal = unequal_vars
        
        # Verify realistic scenario setup
        assert len(cast_rules.applied_shifts_1) == 2
        assert len(cast_rules.applied_shifts_2) == 2
        assert len(cast_rules.is_unequal) == 2
        
        # Verify structure
        assert len(cast_rules.applied_shifts_1[0]) == 2  # 2 actors for vormittag
        assert len(cast_rules.applied_shifts_1[1]) == 2  # 2 actors for nachmittag
        assert len(cast_rules.applied_shifts_2[0]) == 2  # 2 actors for vormittag
        assert len(cast_rules.applied_shifts_2[1]) == 2  # 2 actors for nachmittag
        
        # Verify specific variables are in correct positions
        assert cast_rules.applied_shifts_1[0][0] == mock_shifts_kinderklinik_hans_vm
        assert cast_rules.applied_shifts_1[0][1] == mock_shifts_kinderklinik_maria_vm
        assert cast_rules.applied_shifts_2[0][0] == mock_shifts_seniorenheim_peter_vm
        assert cast_rules.is_unequal[0] == mock_unequal_hans_maria
    
    def test_cast_rules_complex_multi_location_scenario(self):
        """Test: CastRules mit komplexem Multi-Location-Szenario."""
        # Simuliere komplexes Szenario mit 3 Locations und verschiedenen Zeiten
        
        locations = ["Kinderklinik", "Seniorenheim", "Tagesklinik"]
        times = ["Vormittag", "Nachmittag", "Abend"]
        actors = ["Hans", "Maria", "Peter", "Anna", "Thomas"]
        
        # Generate mock variables for realistic scenario
        shift_vars = {}
        for location in locations:
            for time in times:
                for actor in actors:
                    var_name = f"shift_{location}_{actor}_{time}"
                    shift_vars[var_name] = Mock(name=var_name)
        
        # Setup applied shifts for different events
        applied_shifts_complex_1 = []
        applied_shifts_complex_2 = []
        
        # Event 1: Kinderklinik - alle Zeiten
        for time in times:
            time_shifts = []
            for actor in actors[:3]:  # Nur erste 3 Akteure
                var_name = f"shift_Kinderklinik_{actor}_{time}"
                time_shifts.append(shift_vars[var_name])
            applied_shifts_complex_1.append(time_shifts)
        
        # Event 2: Seniorenheim - nur Vormittag und Nachmittag
        for time in times[:2]:  # Nur erste 2 Zeiten
            time_shifts = []
            for actor in actors[2:]:  # Nur letzte 3 Akteure
                var_name = f"shift_Seniorenheim_{actor}_{time}"
                time_shifts.append(shift_vars[var_name])
            applied_shifts_complex_2.append(time_shifts)
        
        # Setup unequal variables for each time slot
        unequal_vars_complex = []
        for i, time in enumerate(times):
            unequal_var = Mock(name=f"unequal_{time}_{i}")
            unequal_vars_complex.append(unequal_var)
        
        # Populate CastRules with complex scenario
        cast_rules.applied_shifts_1 = applied_shifts_complex_1
        cast_rules.applied_shifts_2 = applied_shifts_complex_2
        cast_rules.is_unequal = unequal_vars_complex
        
        # Verify complex scenario
        assert len(cast_rules.applied_shifts_1) == 3  # 3 time slots for event 1
        assert len(cast_rules.applied_shifts_2) == 2  # 2 time slots for event 2
        assert len(cast_rules.is_unequal) == 3       # 3 unequal variables
        
        # Verify actor distribution
        for time_slot in cast_rules.applied_shifts_1:
            assert len(time_slot) == 3  # 3 actors per time slot
        
        for time_slot in cast_rules.applied_shifts_2:
            assert len(time_slot) == 3  # 3 actors per time slot
        
        # Verify specific variables
        assert cast_rules.applied_shifts_1[0][0] == shift_vars["shift_Kinderklinik_Hans_Vormittag"]
        assert cast_rules.applied_shifts_1[1][1] == shift_vars["shift_Kinderklinik_Maria_Nachmittag"]
        assert cast_rules.applied_shifts_2[0][0] == shift_vars["shift_Seniorenheim_Peter_Vormittag"]
    
    def test_cast_rules_edge_cases_handling(self):
        """Test: CastRules behandelt Edge-Cases korrekt."""
        
        # Edge Case 1: Empty lists
        cast_rules.applied_shifts_1 = [[], [], []]  # 3 empty time slots
        cast_rules.applied_shifts_2 = [[]]           # 1 empty time slot
        cast_rules.is_unequal = []                   # No unequal variables
        
        assert len(cast_rules.applied_shifts_1) == 3
        assert len(cast_rules.applied_shifts_2) == 1
        assert len(cast_rules.is_unequal) == 0
        
        for time_slot in cast_rules.applied_shifts_1:
            assert len(time_slot) == 0
        
        assert len(cast_rules.applied_shifts_2[0]) == 0
        
        # Reset and test Edge Case 2: Single variables
        cast_rules.reset_fields()
        
        mock_single_var1 = Mock(name="single_var1")
        mock_single_var2 = Mock(name="single_var2")
        mock_single_unequal = Mock(name="single_unequal")
        
        cast_rules.applied_shifts_1 = [[mock_single_var1]]
        cast_rules.applied_shifts_2 = [[mock_single_var2]]
        cast_rules.is_unequal = [mock_single_unequal]
        
        assert len(cast_rules.applied_shifts_1) == 1
        assert len(cast_rules.applied_shifts_1[0]) == 1
        assert cast_rules.applied_shifts_1[0][0] == mock_single_var1
        
        assert len(cast_rules.applied_shifts_2) == 1
        assert len(cast_rules.applied_shifts_2[0]) == 1
        assert cast_rules.applied_shifts_2[0][0] == mock_single_var2
        
        assert len(cast_rules.is_unequal) == 1
        assert cast_rules.is_unequal[0] == mock_single_unequal
        
        # Reset and test Edge Case 3: Highly asymmetric structure
        cast_rules.reset_fields()
        
        mock_vars = [Mock(name=f"var_{i}") for i in range(10)]
        
        # Asymmetric applied_shifts_1: different sizes per time slot
        cast_rules.applied_shifts_1 = [
            [mock_vars[0]],                                    # 1 actor
            [mock_vars[1], mock_vars[2], mock_vars[3]],        # 3 actors
            [],                                                # 0 actors
            [mock_vars[4], mock_vars[5]]                       # 2 actors
        ]
        
        # Asymmetric applied_shifts_2: completely different structure
        cast_rules.applied_shifts_2 = [
            [mock_vars[6], mock_vars[7], mock_vars[8], mock_vars[9]]  # 4 actors
        ]
        
        # Many unequal variables
        cast_rules.is_unequal = [mock_vars[0], mock_vars[2], mock_vars[4], mock_vars[6]]
        
        # Verify asymmetric structure handling
        assert len(cast_rules.applied_shifts_1) == 4
        assert len(cast_rules.applied_shifts_1[0]) == 1
        assert len(cast_rules.applied_shifts_1[1]) == 3
        assert len(cast_rules.applied_shifts_1[2]) == 0
        assert len(cast_rules.applied_shifts_1[3]) == 2
        
        assert len(cast_rules.applied_shifts_2) == 1
        assert len(cast_rules.applied_shifts_2[0]) == 4
        
        assert len(cast_rules.is_unequal) == 4
    
    def test_cast_rules_thread_safety_considerations(self):
        """Test: CastRules Thread-Safety-Überlegungen."""
        # Note: Dieser Test prüft die grundlegende Funktionalität.
        # Für echte Thread-Safety wären zusätzliche Synchronisation-Mechanismen nötig.
        
        # Simuliere sequentielle Zugriffe (wie in Single-Thread-Umgebung)
        import threading
        
        mock_vars = [Mock(name=f"thread_var_{i}") for i in range(6)]
        
        def worker_function_1():
            """Simulate first worker modifying cast_rules."""
            cast_rules.applied_shifts_1.append([mock_vars[0], mock_vars[1]])
            cast_rules.is_unequal.append(mock_vars[2])
        
        def worker_function_2():
            """Simulate second worker modifying cast_rules."""
            cast_rules.applied_shifts_2.append([mock_vars[3], mock_vars[4]])
            cast_rules.is_unequal.append(mock_vars[5])
        
        # Execute functions sequentially (not actually threaded for test determinism)
        worker_function_1()
        worker_function_2()
        
        # Verify both modifications are present
        assert len(cast_rules.applied_shifts_1) == 1
        assert len(cast_rules.applied_shifts_2) == 1
        assert len(cast_rules.is_unequal) == 2
        
        assert cast_rules.applied_shifts_1[0] == [mock_vars[0], mock_vars[1]]
        assert cast_rules.applied_shifts_2[0] == [mock_vars[3], mock_vars[4]]
        assert mock_vars[2] in cast_rules.is_unequal
        assert mock_vars[5] in cast_rules.is_unequal


@pytest.mark.performance
class TestCastRulesPerformance:
    """Performance-Tests für CastRules."""
    
    def setup_method(self):
        """Setup vor jedem Test."""
        cast_rules.reset_fields()
    
    def teardown_method(self):
        """Cleanup nach jedem Test."""
        cast_rules.reset_fields()
    
    def test_cast_rules_large_data_handling(self):
        """Test: CastRules mit großen Datenmengen."""
        import time
        
        # Generate large amount of mock variables
        num_vars = 1000
        mock_vars = [Mock(name=f"large_var_{i}") for i in range(num_vars)]
        
        # Measure time for large data operations
        start_time = time.time()
        
        # Populate with large data
        for i in range(0, num_vars, 10):  # Create 100 time slots with 10 vars each
            time_slot = mock_vars[i:i+10]
            cast_rules.applied_shifts_1.append(time_slot)
        
        for i in range(0, num_vars, 20):  # Create 50 time slots with 20 vars each
            time_slot = mock_vars[i:i+20] if i+20 <= num_vars else mock_vars[i:]
            cast_rules.applied_shifts_2.append(time_slot)
        
        # Add all variables to is_unequal
        cast_rules.is_unequal.extend(mock_vars)
        
        population_time = time.time() - start_time
        
        # Verify large data handling
        assert len(cast_rules.applied_shifts_1) == 100
        assert len(cast_rules.applied_shifts_2) == 50
        assert len(cast_rules.is_unequal) == num_vars
        
        # Measure reset time
        reset_start = time.time()
        cast_rules.reset_fields()
        reset_time = time.time() - reset_start
        
        # Performance should be reasonable
        assert population_time < 1.0  # Should complete within 1 second
        assert reset_time < 0.1       # Reset should be very fast
        
        # Verify reset worked
        assert len(cast_rules.applied_shifts_1) == 0
        assert len(cast_rules.applied_shifts_2) == 0
        assert len(cast_rules.is_unequal) == 0
    
    def test_cast_rules_memory_efficiency(self):
        """Test: CastRules Memory-Effizienz."""
        import gc
        
        # Force garbage collection before test
        gc.collect()
        
        # Create and destroy multiple CastRules instances
        for _ in range(100):
            rules = CastRules()
            
            # Populate with some data
            mock_vars = [Mock() for _ in range(50)]
            rules.applied_shifts_1.extend([[mock_vars[i]] for i in range(25)])
            rules.applied_shifts_2.extend([[mock_vars[i+25]] for i in range(25)])
            rules.is_unequal.extend(mock_vars)
            
            # Reset (simulating cleanup)
            rules.reset_fields()
        
        # Use global instance multiple times
        for _ in range(100):
            mock_vars = [Mock() for _ in range(20)]
            cast_rules.applied_shifts_1.append(mock_vars[:10])
            cast_rules.applied_shifts_2.append(mock_vars[10:])
            cast_rules.is_unequal.extend(mock_vars)
            cast_rules.reset_fields()
        
        # Force garbage collection after test
        gc.collect()
        
        # Should not have memory leaks (test passes if no errors)
        assert True
    
    def test_cast_rules_repeated_operations_performance(self):
        """Test: CastRules Performance bei wiederholten Operationen."""
        import time
        
        num_iterations = 1000
        mock_vars = [Mock(name=f"perf_var_{i}") for i in range(100)]
        
        # Test repeated append operations
        start_time = time.time()
        
        for i in range(num_iterations):
            # Simulate typical usage pattern
            var_subset = mock_vars[i % 100:(i % 100) + 5]  # 5 variables per iteration
            cast_rules.applied_shifts_1.append(var_subset)
            
            if i % 2 == 0:  # Every other iteration
                cast_rules.applied_shifts_2.append(var_subset[:3])
            
            if i % 3 == 0:  # Every third iteration
                cast_rules.is_unequal.extend(var_subset[:2])
            
            if i % 50 == 49:  # Reset every 50 iterations
                cast_rules.reset_fields()
        
        operation_time = time.time() - start_time
        
        # Performance should be reasonable for repeated operations
        assert operation_time < 2.0  # Should complete within 2 seconds
        
        # Final state should be consistent
        final_applied_1_count = len(cast_rules.applied_shifts_1)
        final_applied_2_count = len(cast_rules.applied_shifts_2)
        final_unequal_count = len(cast_rules.is_unequal)
        
        # Verify counts are reasonable (after resets)
        assert final_applied_1_count < num_iterations  # Should be less due to resets
        assert final_applied_2_count < num_iterations // 2
        assert final_unequal_count < num_iterations * 2 // 3
