"""
Workload Heat-Map Calculator für HCC Plan DB Playground

Berechnet Mitarbeiter-Auslastung basierend auf Appointments und requested_assignments
für visuelle Heat-Map-Darstellung in der Planansicht.

Erstellt: 31. August 2025
Teil von: Workload Heat-Maps Feature Implementation
"""

from typing import Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta, UTC
from collections import defaultdict
from functools import lru_cache
import logging

from pony.orm import db_session, select
from database.models import Person, PlanPeriod, Appointment, Event

logger = logging.getLogger(__name__)


class WorkloadCalculator:
    """
    Zentrale Klasse für Workload-Berechnungen und Heat-Map-Visualisierung
    
    Berechnet Auslastungsprozente basierend auf:
    - Tatsächliche Appointments vs. requested_assignments
    - Berücksichtigt Event-Dauer und Planperioden-Kontext
    - Unterstützt verschiedene Berechnungsmodi
    """
    
    @staticmethod
    def calculate_person_workload_percentage(person: Person, plan_period: PlanPeriod) -> float:
        """
        Berechnet Auslastung einer Person in % für gegebene Planperiode
        
        Args:
            person: Person-Entity aus der Datenbank
            plan_period: PlanPeriod-Entity für Zeitraum-Abgrenzung
            
        Returns:
            float: Auslastung in Prozent (0.0-100.0+, kann über 100% gehen bei Überlastung)
            
        Raises:
            ValueError: Bei ungültigen Input-Parametern
        """
        if not person or not plan_period:
            logger.warning("Ungültige Parameter für Workload-Berechnung")
            return 0.0
            
        try:
            with db_session:
                # Person und PlanPeriod IDs verwenden um Session-Probleme zu vermeiden
                person_id = person.id if hasattr(person, 'id') else person
                plan_period_id = plan_period.id if hasattr(plan_period, 'id') else plan_period
                
                # Korrekte Schema-Beziehung: Appointment → avail_days → actor_plan_period → person
                # Erst alle AvailDays der Person in dieser Planperiode finden
                from database.models import AvailDay
                
                avail_days = select(
                    ad for ad in AvailDay 
                    if ad.actor_plan_period.person.id == person_id 
                    and ad.actor_plan_period.plan_period.id == plan_period_id
                )
                
                # Dann alle Appointments sammeln, die diese AvailDays verwenden
                appointments = []
                for avail_day in avail_days:
                    appointments.extend(avail_day.appointments)
                
                # Gesamtstunden berechnen
                total_hours = 0.0
                appointment_count = 0
                
                for appointment in appointments:
                    if appointment.event and appointment.event.start_time and appointment.event.end_time:
                        # Berechnung der Event-Dauer in Stunden
                        duration = appointment.event.end_time - appointment.event.start_time
                        total_hours += duration.total_seconds() / 3600  # Sekunden zu Stunden
                        appointment_count += 1
                
                # Person-Daten aus der aktuellen db_session laden um Session-Konflikte zu vermeiden
                current_person = Person.get(id=person_id)
                if not current_person:
                    logger.warning(f"Person mit ID {person_id} nicht gefunden")
                    return 0.0
                
                # Maximale verfügbare Stunden basierend auf requested_assignments
                requested_assignments = current_person.requested_assignments or 0
                if requested_assignments <= 0:
                    logger.debug(f"Person {current_person.f_name} {current_person.l_name} hat keine requested_assignments")
                    return 0.0
                
                # Annahme: Ein Assignment = 8 Stunden Standardarbeitstag
                # TODO: Könnte später konfigurierbar gemacht werden
                hours_per_assignment = 8.0
                max_possible_hours = requested_assignments * hours_per_assignment
                
                # Prozentsatz berechnen
                workload_percentage = (total_hours / max_possible_hours) * 100.0
                
                logger.debug(
                    f"Workload für {current_person.f_name} {current_person.l_name}: "
                    f"{total_hours:.1f}h/{max_possible_hours:.1f}h = {workload_percentage:.1f}% "
                    f"({appointment_count} Termine)"
                )
                
                return round(workload_percentage, 1)
                
        except Exception as e:
            logger.error(f"Fehler bei Workload-Berechnung für Person {person.id if hasattr(person, 'id') else person}: {e}")
            return 0.0
    
    @staticmethod
    def calculate_bulk_workload(persons: List[Person], plan_period: PlanPeriod) -> Dict[UUID, float]:
        """
        Performance-optimierte Batch-Berechnung für mehrere Personen
        
        Args:
            persons: Liste von Person-Entities
            plan_period: PlanPeriod für Zeitraum-Abgrenzung
            
        Returns:
            Dict[UUID, float]: Person-ID -> Workload-Prozent Mapping
        """
        if not persons or not plan_period:
            return {}
            
        workload_results = {}
        
        try:
            with db_session:
                # Alle relevanten Appointments in einem Query holen
                person_ids = [p.id for p in persons]
                appointments = select(
                    a for a in Appointment 
                    if a.person.id in person_ids and a.event.plan_period == plan_period
                )
                
                # Gruppierung der Appointments nach Person
                person_hours = defaultdict(float)
                person_appointment_counts = defaultdict(int)
                
                for appointment in appointments:
                    if appointment.event and appointment.event.start_time and appointment.event.end_time:
                        duration = appointment.event.end_time - appointment.event.start_time
                        hours = duration.total_seconds() / 3600
                        person_hours[appointment.person.id] += hours
                        person_appointment_counts[appointment.person.id] += 1
                
                # Workload für jede Person berechnen
                for person in persons:
                    total_hours = person_hours.get(person.id, 0.0)
                    requested_assignments = person.requested_assignments or 0
                    
                    if requested_assignments > 0:
                        max_hours = requested_assignments * 8.0
                        workload_percent = (total_hours / max_hours) * 100.0
                        workload_results[person.id] = round(workload_percent, 1)
                    else:
                        workload_results[person.id] = 0.0
                
                logger.info(f"Bulk-Workload berechnet für {len(persons)} Personen")
                
        except Exception as e:
            logger.error(f"Fehler bei Bulk-Workload-Berechnung: {e}")
            
        return workload_results
    
    @staticmethod
    def get_workload_color(workload_percentage: float) -> Tuple[int, int, int]:
        """
        Konvertiert Workload-Prozent zu RGB-Farbwerten für Heat-Map-Darstellung
        
        Args:
            workload_percentage: Auslastung in Prozent (0.0-200.0+)
            
        Returns:
            Tuple[int, int, int]: RGB-Farbwerte (0-255 je Kanal)
            
        Farbschema:
        - 0-50%: Blau-Töne (verfügbar)
        - 50-90%: Grün→Gelb (optimal→voll) 
        - 90-110%: Gelb→Orange (überlastet)
        - 110%+: Orange→Rot (kritisch überlastet)
        """
        # Input-Validation und Extremwerte abfangen
        workload_percentage = max(0.0, min(workload_percentage, 200.0))
        
        if workload_percentage <= 50:
            # Blau-Bereich: (70, 130, 180) bis (100, 200, 100)
            # Verfügbare Kapazität - ruhige, kühle Farben
            factor = workload_percentage / 50.0
            red = int(70 + (30 * factor))
            green = int(130 + (70 * factor)) 
            blue = int(180 - (80 * factor))
            return (red, green, blue)
        
        elif workload_percentage <= 90:
            # Grün zu Gelb: (100, 200, 100) bis (255, 255, 50)
            # Optimale bis volle Auslastung - warme, positive Farben
            factor = (workload_percentage - 50) / 40.0
            red = int(100 + (155 * factor))
            green = int(200 + (55 * factor))
            blue = int(100 - (50 * factor))
            return (red, green, blue)
        
        elif workload_percentage <= 110:
            # Gelb zu Orange: (255, 255, 50) bis (255, 165, 0)
            # Überlastung - Warnsignale
            factor = (workload_percentage - 90) / 20.0
            red = 255
            green = int(255 - (90 * factor))
            blue = int(50 - (50 * factor))
            return (red, green, blue)
        
        else:
            # Orange zu Rot: (255, 165, 0) bis (220, 20, 60)
            # Kritische Überlastung - Alarmsignale
            factor = min((workload_percentage - 110) / 40.0, 1.0)
            red = int(255 - (35 * factor))
            green = int(165 - (145 * factor))
            blue = int(0 + (60 * factor))
            return (red, green, blue)
    
    @staticmethod
    def get_workload_status_text(workload_percentage: float) -> str:
        """
        Konvertiert Workload-Prozent zu lesbarem Status-Text
        
        Args:
            workload_percentage: Auslastung in Prozent
            
        Returns:
            str: Beschreibender Status-Text
        """
        if workload_percentage < 25:
            return "Sehr verfügbar"
        elif workload_percentage < 50:
            return "Verfügbar"
        elif workload_percentage < 75:
            return "Gut ausgelastet"
        elif workload_percentage < 90:
            return "Voll ausgelastet"
        elif workload_percentage < 110:
            return "Überlastet"
        else:
            return "⚠️ Kritisch überlastet"
    
    @staticmethod
    def calculate_location_workload_summary(location_id: UUID, plan_period: PlanPeriod) -> Dict:
        """
        Berechnet aggregierte Workload-Statistiken für einen Standort
        
        Args:
            location_id: ID des Arbeitsorts
            plan_period: Planperiode für Berechnung
            
        Returns:
            Dict: Zusammenfassung der Standort-Auslastung
        """
        try:
            with db_session:
                # Alle Events am Standort in der Planperiode
                events = select(
                    e for e in Event 
                    if e.location_of_work and e.location_of_work.id == location_id 
                    and e.plan_period == plan_period
                )
                
                # Alle zugeordneten Personen sammeln
                persons_at_location = set()
                total_appointments = 0
                total_hours = 0.0
                
                for event in events:
                    appointments = select(a for a in Appointment if a.event == event)
                    for appointment in appointments:
                        persons_at_location.add(appointment.person)
                        total_appointments += 1
                        
                        if event.start_time and event.end_time:
                            duration = event.end_time - event.start_time
                            total_hours += duration.total_seconds() / 3600
                
                # Durchschnitts-Auslastung berechnen
                if persons_at_location:
                    individual_workloads = []
                    for person in persons_at_location:
                        workload = WorkloadCalculator.calculate_person_workload_percentage(
                            person, plan_period
                        )
                        individual_workloads.append(workload)
                    
                    avg_workload = sum(individual_workloads) / len(individual_workloads)
                else:
                    avg_workload = 0.0
                
                return {
                    'location_id': location_id,
                    'person_count': len(persons_at_location),
                    'total_appointments': total_appointments,
                    'total_hours': round(total_hours, 1),
                    'average_workload_percent': round(avg_workload, 1),
                    'individual_workloads': individual_workloads
                }
                
        except Exception as e:
            logger.error(f"Fehler bei Location-Workload-Berechnung für {location_id}: {e}")
            return {
                'location_id': location_id,
                'person_count': 0,
                'total_appointments': 0,
                'total_hours': 0.0,
                'average_workload_percent': 0.0,
                'individual_workloads': []
            }


class WorkloadCache:
    """
    Performance-Cache für Workload-Berechnungen
    
    Implementiert LRU-Cache mit automatischer Invalidation bei Datenänderungen
    """
    
    def __init__(self, max_cache_age_seconds: int = 300):  # 5 Minuten Standard
        self.max_cache_age_seconds = max_cache_age_seconds
        self._workload_cache: Dict[Tuple[UUID, UUID], Tuple[float, datetime]] = {}
        self._bulk_cache: Dict[UUID, Tuple[Dict[UUID, float], datetime]] = {}
        self._last_cleanup: datetime = datetime.now(UTC)
    
    def get_cached_workload(self, person_id: UUID, plan_period_id: UUID) -> Optional[float]:
        """
        Holt Workload aus Cache wenn noch aktuell
        
        Args:
            person_id: ID der Person
            plan_period_id: ID der Planperiode
            
        Returns:
            Optional[float]: Cached Workload oder None wenn veraltet/nicht vorhanden
        """
        key = (person_id, plan_period_id)
        
        if key in self._workload_cache:
            workload_value, cached_at = self._workload_cache[key]
            
            # Prüfen ob Cache noch aktuell
            age_seconds = (datetime.now(UTC) - cached_at).total_seconds()
            if age_seconds < self.max_cache_age_seconds:
                logger.debug(f"Workload Cache-Hit für {person_id}")
                return workload_value
            else:
                # Veralteter Cache-Eintrag entfernen
                del self._workload_cache[key]
        
        return None
    
    def cache_workload(self, person_id: UUID, plan_period_id: UUID, workload: float):
        """
        Speichert Workload-Berechnung im Cache
        
        Args:
            person_id: ID der Person
            plan_period_id: ID der Planperiode  
            workload: Berechneter Workload-Wert
        """
        key = (person_id, plan_period_id)
        self._workload_cache[key] = (workload, datetime.now(UTC))
        
        # Periodische Cache-Bereinigung
        self._cleanup_if_needed()
    
    def get_cached_bulk_workload(self, plan_period_id: UUID) -> Optional[Dict[UUID, float]]:
        """
        Holt Bulk-Workload-Daten aus Cache
        
        Args:
            plan_period_id: ID der Planperiode
            
        Returns:
            Optional[Dict[UUID, float]]: Cached Bulk-Daten oder None
        """
        if plan_period_id in self._bulk_cache:
            bulk_data, cached_at = self._bulk_cache[plan_period_id]
            
            age_seconds = (datetime.now(UTC) - cached_at).total_seconds()
            if age_seconds < self.max_cache_age_seconds:
                logger.debug(f"Bulk Workload Cache-Hit für PlanPeriod {plan_period_id}")
                return bulk_data
            else:
                del self._bulk_cache[plan_period_id]
        
        return None
    
    def cache_bulk_workload(self, plan_period_id: UUID, bulk_data: Dict[UUID, float]):
        """
        Speichert Bulk-Workload-Daten im Cache
        """
        self._bulk_cache[plan_period_id] = (bulk_data, datetime.now(UTC))
        self._cleanup_if_needed()
    
    def clear_cache(self):
        """
        Leert kompletten Cache - wird bei Datenänderungen aufgerufen
        """
        self._workload_cache.clear()
        self._bulk_cache.clear()
        logger.info("Workload-Cache geleert")
    
    def invalidate_person(self, person_id: UUID):
        """
        Invalidiert Cache für spezifische Person
        """
        keys_to_remove = [
            key for key in self._workload_cache.keys() 
            if key[0] == person_id
        ]
        
        for key in keys_to_remove:
            del self._workload_cache[key]
            
        logger.debug(f"Cache invalidiert für Person {person_id}")
    
    def invalidate_plan_period(self, plan_period_id: UUID):
        """
        Invalidiert Cache für spezifische Planperiode
        """
        # Individual Cache
        keys_to_remove = [
            key for key in self._workload_cache.keys() 
            if key[1] == plan_period_id
        ]
        
        for key in keys_to_remove:
            del self._workload_cache[key]
        
        # Bulk Cache
        if plan_period_id in self._bulk_cache:
            del self._bulk_cache[plan_period_id]
            
        logger.debug(f"Cache invalidiert für PlanPeriod {plan_period_id}")
    
    def _cleanup_if_needed(self):
        """
        Periodische Cache-Bereinigung veralteter Einträge
        """
        now = datetime.now(UTC)
        
        # Cleanup alle 10 Minuten
        if (now - self._last_cleanup).total_seconds() > 600:
            self._cleanup_expired_entries(now)
            self._last_cleanup = now
    
    def _cleanup_expired_entries(self, current_time: datetime):
        """
        Entfernt veraltete Cache-Einträge
        """
        # Individual Cache cleanup
        expired_keys = [
            key for key, (value, cached_at) in self._workload_cache.items()
            if (current_time - cached_at).total_seconds() > self.max_cache_age_seconds
        ]
        
        for key in expired_keys:
            del self._workload_cache[key]
        
        # Bulk Cache cleanup
        expired_bulk_keys = [
            key for key, (value, cached_at) in self._bulk_cache.items()
            if (current_time - cached_at).total_seconds() > self.max_cache_age_seconds
        ]
        
        for key in expired_bulk_keys:
            del self._bulk_cache[key]
        
        if expired_keys or expired_bulk_keys:
            logger.debug(f"Cache cleanup: {len(expired_keys)} individual, {len(expired_bulk_keys)} bulk entries entfernt")
    
    def get_cache_stats(self) -> Dict:
        """
        Cache-Statistiken für Debugging und Monitoring
        """
        return {
            'individual_entries': len(self._workload_cache),
            'bulk_entries': len(self._bulk_cache),
            'max_age_seconds': self.max_cache_age_seconds,
            'last_cleanup': self._last_cleanup.isoformat() if self._last_cleanup else None
        }
