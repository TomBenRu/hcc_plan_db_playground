"""
Unit Tests für WorkloadCalculator - HCC Plan DB Playground

Testet alle Funktionen der Workload-Berechnung und Heat-Map-Visualisierung

Erstellt: 31. August 2025
Ausführung: pytest tests/unit/test_workload_calculator.py -v
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock, patch, MagicMock

from gui.plan_visualization_to_remove.workload_calculator import WorkloadCalculator, WorkloadCache


class TestWorkloadCalculator:
    """Test-Suite für WorkloadCalculator-Funktionalität"""
    
    def setup_method(self):
        """Setup für jeden Test"""
        self.calculator = WorkloadCalculator()
        
        # Mock-Person mit 5 requested_assignments (= 40h max)
        self.mock_person = Mock()
        self.mock_person.id = uuid4()
        self.mock_person.f_name = "Max"
        self.mock_person.l_name = "Mustermann"
        self.mock_person.requested_assignments = 5
        
        # Mock-PlanPeriod
        self.mock_plan_period = Mock()
        self.mock_plan_period.id = uuid4()
        
        # Mock-Events mit verschiedenen Dauern
        self.mock_event_4h = Mock()
        self.mock_event_4h.start_time = datetime(2025, 9, 1, 9, 0)
        self.mock_event_4h.end_time = datetime(2025, 9, 1, 13, 0)  # 4 Stunden
        self.mock_event_4h.plan_period = self.mock_plan_period
        
        self.mock_event_8h = Mock()
        self.mock_event_8h.start_time = datetime(2025, 9, 2, 8, 0)
        self.mock_event_8h.end_time = datetime(2025, 9, 2, 16, 0)  # 8 Stunden
        self.mock_event_8h.plan_period = self.mock_plan_period
    
    def test_calculate_person_workload_percentage_normal(self):
        """Test normale Workload-Berechnung"""
        
        # Mock Appointments - 12 Stunden von 40 möglichen = 30%
        mock_appointments = [
            Mock(person=self.mock_person, event=self.mock_event_4h),
            Mock(person=self.mock_person, event=self.mock_event_8h)
        ]
        
        with patch('gui.plan_visualization.workload_calculator.select') as mock_select:
            mock_select.return_value = mock_appointments
            
            result = self.calculator.calculate_person_workload_percentage(
                self.mock_person, self.mock_plan_period
            )
            
            assert result == 30.0  # 12h / 40h * 100
    
    def test_calculate_person_workload_percentage_overload(self):
        """Test Überlastung über 100%"""
        
        # 48 Stunden von 40 möglichen = 120%
        mock_event_16h = Mock()
        mock_event_16h.start_time = datetime(2025, 9, 3, 6, 0)
        mock_event_16h.end_time = datetime(2025, 9, 3, 22, 0)  # 16 Stunden
        mock_event_16h.plan_period = self.mock_plan_period
        
        mock_appointments = [
            Mock(person=self.mock_person, event=self.mock_event_4h),
            Mock(person=self.mock_person, event=self.mock_event_8h),
            Mock(person=self.mock_person, event=mock_event_16h),
            Mock(person=self.mock_person, event=self.mock_event_8h),  # Nochmal 8h
            Mock(person=self.mock_person, event=self.mock_event_4h),  # Nochmal 4h
            Mock(person=self.mock_person, event=self.mock_event_8h)   # Nochmal 8h = 48h total
        ]
        
        with patch('gui.plan_visualization.workload_calculator.select') as mock_select:
            mock_select.return_value = mock_appointments
            
            result = self.calculator.calculate_person_workload_percentage(
                self.mock_person, self.mock_plan_period
            )
            
            assert result == 120.0  # 48h / 40h * 100
    
    def test_calculate_person_workload_percentage_no_assignments(self):
        """Test Person ohne requested_assignments"""
        
        person_no_assignments = Mock()
        person_no_assignments.requested_assignments = 0
        person_no_assignments.f_name = "Test"
        person_no_assignments.l_name = "Person"
        
        result = self.calculator.calculate_person_workload_percentage(
            person_no_assignments, self.mock_plan_period
        )
        
        assert result == 0.0
    
    def test_calculate_person_workload_percentage_no_appointments(self):
        """Test Person ohne Appointments"""
        
        with patch('gui.plan_visualization.workload_calculator.select') as mock_select:
            mock_select.return_value = []  # Keine Appointments
            
            result = self.calculator.calculate_person_workload_percentage(
                self.mock_person, self.mock_plan_period
            )
            
            assert result == 0.0
    
    def test_calculate_person_workload_percentage_invalid_params(self):
        """Test mit ungültigen Parametern"""
        
        # None Person
        result1 = self.calculator.calculate_person_workload_percentage(
            None, self.mock_plan_period
        )
        assert result1 == 0.0
        
        # None PlanPeriod  
        result2 = self.calculator.calculate_person_workload_percentage(
            self.mock_person, None
        )
        assert result2 == 0.0
    
    def test_get_workload_color_ranges(self):
        """Test Farbberechnung für verschiedene Workload-Bereiche"""
        
        # Blau-Bereich (0-50%)
        color_25 = self.calculator.get_workload_color(25.0)
        assert len(color_25) == 3
        assert all(0 <= c <= 255 for c in color_25)
        # Blau sollte dominieren
        assert color_25[2] > color_25[0]  # Mehr blau als rot
        
        # Gelb-Bereich (50-90%)
        color_70 = self.calculator.get_workload_color(70.0)
        assert len(color_70) == 3
        # Rot und Grün sollten hoch sein, Blau niedrig (= gelb-ish)
        assert color_70[0] > 150  # Viel rot
        assert color_70[1] > 150  # Viel grün
        assert color_70[2] < 100  # Wenig blau
        
        # Orange-Bereich (90-110%)
        color_100 = self.calculator.get_workload_color(100.0)
        assert len(color_100) == 3
        # Orange = viel rot, mittleres grün, wenig blau
        assert color_100[0] == 255  # Max rot
        assert 100 < color_100[1] <= 255  # Mittleres bis hohes grün (Orange-Bereich)
        assert color_100[2] < 50  # Wenig blau
        
        # Rot-Bereich (110%+)
        color_150 = self.calculator.get_workload_color(150.0)
        assert len(color_150) == 3
        # Rot sollte dominieren
        assert color_150[0] > 200  # Viel rot
        assert color_150[1] < 100  # Wenig grün
        assert color_150[2] < 100  # Wenig blau
    
    def test_get_workload_color_edge_cases(self):
        """Test Extremwerte für Farbberechnung"""
        
        # Negativer Wert
        color_negative = self.calculator.get_workload_color(-10.0)
        color_zero = self.calculator.get_workload_color(0.0)
        assert color_negative == color_zero
        
        # Sehr hoher Wert
        color_high1 = self.calculator.get_workload_color(500.0)
        color_high2 = self.calculator.get_workload_color(200.0)
        assert color_high1 == color_high2  # Sollten geclampet werden
    
    def test_get_workload_status_text(self):
        """Test Status-Text-Generierung"""
        
        assert "verfügbar" in self.calculator.get_workload_status_text(10.0).lower()
        assert "verfügbar" in self.calculator.get_workload_status_text(40.0).lower()
        assert "gut" in self.calculator.get_workload_status_text(65.0).lower()
        assert "voll" in self.calculator.get_workload_status_text(85.0).lower()
        assert "überlastet" in self.calculator.get_workload_status_text(95.0).lower()
        assert "kritisch" in self.calculator.get_workload_status_text(120.0).lower()
    
    def test_calculate_bulk_workload(self):
        """Test Bulk-Workload-Berechnung"""
        
        # Zweite Mock-Person
        mock_person2 = Mock()
        mock_person2.id = uuid4()
        mock_person2.requested_assignments = 3  # 24h max
        
        persons_list = [self.mock_person, mock_person2]
        
        # Mock Appointments für beide Personen
        mock_appointments = [
            Mock(person=self.mock_person, event=self.mock_event_8h),      # 8h für Person 1
            Mock(person=mock_person2, event=self.mock_event_4h),          # 4h für Person 2
        ]
        
        with patch('gui.plan_visualization.workload_calculator.select') as mock_select:
            mock_select.return_value = mock_appointments
            
            result = self.calculator.calculate_bulk_workload(persons_list, self.mock_plan_period)
            
            # Person 1: 8h / 40h = 20%
            # Person 2: 4h / 24h = 16.7%
            assert result[self.mock_person.id] == 20.0
            assert result[mock_person2.id] == 16.7
    
    def test_calculate_bulk_workload_empty_input(self):
        """Test Bulk-Berechnung mit leeren Inputs"""
        
        result1 = self.calculator.calculate_bulk_workload([], self.mock_plan_period)
        assert result1 == {}
        
        result2 = self.calculator.calculate_bulk_workload([self.mock_person], None)
        assert result2 == {}


class TestWorkloadCache:
    """Test-Suite für WorkloadCache-Funktionalität"""
    
    def setup_method(self):
        """Setup für jeden Test"""
        self.cache = WorkloadCache(max_cache_age_seconds=10)  # Kurze Cache-Zeit für Tests
        self.person_id = uuid4()
        self.plan_period_id = uuid4()
    
    def test_cache_and_retrieve_workload(self):
        """Test Basis-Cache-Funktionalität"""
        
        # Noch nichts im Cache
        result = self.cache.get_cached_workload(self.person_id, self.plan_period_id)
        assert result is None
        
        # Wert cachen
        test_workload = 75.5
        self.cache.cache_workload(self.person_id, self.plan_period_id, test_workload)
        
        # Aus Cache holen
        cached_result = self.cache.get_cached_workload(self.person_id, self.plan_period_id)
        assert cached_result == test_workload
    
    def test_cache_expiry(self):
        """Test Cache-Ablauf"""
        import time
        
        # Cache mit sehr kurzer Ablaufzeit
        short_cache = WorkloadCache(max_cache_age_seconds=1)
        
        # Wert cachen
        short_cache.cache_workload(self.person_id, self.plan_period_id, 50.0)
        
        # Sofort abrufbar
        result1 = short_cache.get_cached_workload(self.person_id, self.plan_period_id)
        assert result1 == 50.0
        
        # Nach Ablaufzeit nicht mehr verfügbar
        time.sleep(1.1)
        result2 = short_cache.get_cached_workload(self.person_id, self.plan_period_id)
        assert result2 is None
    
    def test_bulk_cache_functionality(self):
        """Test Bulk-Cache-Funktionalität"""
        
        # Bulk-Daten
        bulk_data = {
            uuid4(): 25.0,
            uuid4(): 75.0,
            uuid4(): 125.0
        }
        
        # Noch nichts im Cache
        result = self.cache.get_cached_bulk_workload(self.plan_period_id)
        assert result is None
        
        # Bulk-Daten cachen
        self.cache.cache_bulk_workload(self.plan_period_id, bulk_data)
        
        # Aus Cache holen
        cached_bulk = self.cache.get_cached_bulk_workload(self.plan_period_id)
        assert cached_bulk == bulk_data
    
    def test_cache_clear(self):
        """Test Cache-Leerung"""
        
        # Daten cachen
        self.cache.cache_workload(self.person_id, self.plan_period_id, 60.0)
        bulk_data = {uuid4(): 80.0}
        self.cache.cache_bulk_workload(self.plan_period_id, bulk_data)
        
        # Daten sind verfügbar
        assert self.cache.get_cached_workload(self.person_id, self.plan_period_id) == 60.0
        assert self.cache.get_cached_bulk_workload(self.plan_period_id) == bulk_data
        
        # Cache leeren
        self.cache.clear_cache()
        
        # Daten sind weg
        assert self.cache.get_cached_workload(self.person_id, self.plan_period_id) is None
        assert self.cache.get_cached_bulk_workload(self.plan_period_id) is None
    
    def test_selective_invalidation(self):
        """Test selektive Cache-Invalidierung"""
        
        person_id_1 = uuid4()
        person_id_2 = uuid4()
        plan_period_id_1 = uuid4()
        plan_period_id_2 = uuid4()
        
        # Mehrere Einträge cachen
        self.cache.cache_workload(person_id_1, plan_period_id_1, 30.0)
        self.cache.cache_workload(person_id_2, plan_period_id_1, 60.0)
        self.cache.cache_workload(person_id_1, plan_period_id_2, 90.0)
        
        # Person 1 invalidieren
        self.cache.invalidate_person(person_id_1)
        
        # Person 1 Einträge sind weg, Person 2 noch da
        assert self.cache.get_cached_workload(person_id_1, plan_period_id_1) is None
        assert self.cache.get_cached_workload(person_id_1, plan_period_id_2) is None
        assert self.cache.get_cached_workload(person_id_2, plan_period_id_1) == 60.0
        
        # Plan Period invalidieren
        self.cache.invalidate_plan_period(plan_period_id_1)
        assert self.cache.get_cached_workload(person_id_2, plan_period_id_1) is None
    
    def test_cache_stats(self):
        """Test Cache-Statistiken"""
        
        # Initial leer
        stats = self.cache.get_cache_stats()
        assert stats['individual_entries'] == 0
        assert stats['bulk_entries'] == 0
        
        # Daten hinzufügen
        self.cache.cache_workload(self.person_id, self.plan_period_id, 50.0)
        self.cache.cache_bulk_workload(self.plan_period_id, {uuid4(): 25.0})
        
        # Stats prüfen
        stats = self.cache.get_cache_stats()
        assert stats['individual_entries'] == 1
        assert stats['bulk_entries'] == 1
        assert stats['max_age_seconds'] == 10


# Integration Test (benötigt echte DB-Verbindung - Optional)
class TestWorkloadCalculatorIntegration:
    """Integration Tests mit echter Datenbank (Optional)"""
    
    @pytest.mark.skipif(True, reason="Benötigt echte DB-Verbindung")
    def test_real_database_workload_calculation(self):
        """Test mit echter Datenbank (nur wenn verfügbar)"""
        # Hier würden echte DB-Tests stehen
        pass


if __name__ == "__main__":
    # Tests direkt ausführen
    pytest.main([__file__, "-v"])
