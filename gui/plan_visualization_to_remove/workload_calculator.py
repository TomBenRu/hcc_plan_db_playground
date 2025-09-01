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


def calculate_delta_from_time_objects(start_time, end_time) -> float:
    """
    Berechnet Dauer in Stunden aus Zeit-Objekten (String oder datetime.time)

    Args:
        start_time: Zeit-Objekt (String oder datetime.time) für Start
        end_time: Zeit-Objekt (String oder datetime.time) für Ende

    Returns:
        float: Dauer in Stunden
    """
    try:
        logger.debug(f"Zeit-Berechnung: {start_time} bis {end_time} (Typen: {type(start_time)}, {type(end_time)})")
        
        # Konvertierung zu datetime.time falls nötig
        if isinstance(start_time, str):
            start_time_obj = datetime.strptime(start_time, '%H:%M:%S').time()
        else:
            start_time_obj = start_time
            
        if isinstance(end_time, str):
            end_time_obj = datetime.strptime(end_time, '%H:%M:%S').time()
        else:
            end_time_obj = end_time
        
        # datetime.time Objekte zu datetime.datetime konvertieren für Berechnung
        today = datetime.now().date()
        start_dt = datetime.combine(today, start_time_obj)
        end_dt = datetime.combine(today, end_time_obj)
        
        # Berechnung der Dauer
        duration = end_dt - start_dt
        
        # Falls End-Zeit vor Start-Zeit liegt (über Mitternacht), einen Tag addieren
        if duration.total_seconds() < 0:
            end_dt = end_dt + timedelta(days=1)
            duration = end_dt - start_dt
            logger.debug(f"Über-Mitternacht-Korrektur angewendet")
        
        hours = duration.total_seconds() / 3600  # Sekunden zu Stunden
        logger.debug(f"✅ Berechnete Stunden: {hours}")
        
        # Plausibilitätsprüfung: Ereignisse sollten normalerweise nicht länger als 24h sein
        if hours > 24:
            logger.warning(f"⚠️ Ungewöhnlich lange Event-Dauer: {hours}h ({start_time} - {end_time})")
        
        return hours
    except Exception as e:
        logger.error(f"❌ Fehler bei Zeit-Berechnung: {start_time} - {end_time}: {e}")
        return 0.0


# Legacy-Funktion für Rückwärtskompatibilität
def calculate_delta_from_time_strings(start_str: str, end_str: str) -> float:
    """
    DEPRECATED: Berechnet Dauer in Stunden aus Start- und End-Zeichenketten
    Verwende stattdessen calculate_delta_from_time_objects()
    """
    try:
        start_time = datetime.strptime(start_str, '%H:%M:%S').time()
        end_time = datetime.strptime(end_str, '%H:%M:%S').time()
        return calculate_delta_from_time_objects(start_time, end_time)
    except ValueError as e:
        logger.warning(f"Fehler bei Zeit-String-Parsing: {start_str} - {end_str}: {e}")
        return 0.0


class WorkloadCalculator:
    """
    Zentrale Klasse für Workload-Berechnungen und Heat-Map-Visualisierung
    
    Berechnet Auslastungsprozente basierend auf:
    - Tatsächliche Appointments vs. requested_assignments
    - Berücksichtigt Event-Dauer und Planperioden-Kontext
    - Unterstützt verschiedene Berechnungsmodi
    """
    
    @staticmethod
    def calculate_actor_plan_period_workload_percentage(actor_plan_period) -> float:
        """
        Berechnet Auslastung einer ActorPlanPeriod in % für gegebene Planperiode
        
        Args:
            actor_plan_period: ActorPlanPeriod-Entity aus der Datenbank
            
        Returns:
            float: Auslastung in Prozent (0.0-100.0+, kann über 100% gehen bei Überlastung)
            
        Raises:
            ValueError: Bei ungültigen Input-Parametern
        """
        if not actor_plan_period:
            logger.warning("Ungültige Parameter für Workload-Berechnung")
            return 0.0
            
        try:
            with db_session:
                # ActorPlanPeriod ID verwenden um Session-Probleme zu vermeiden
                app_id = actor_plan_period.id if hasattr(actor_plan_period, 'id') else actor_plan_period
                
                # Korrekte Schema-Beziehung: AvailDay → Appointment
                from database.models import AvailDay, Appointment
                
                # Alle AvailDays dieser ActorPlanPeriod finden
                avail_days = select(
                    ad for ad in AvailDay 
                    if ad.actor_plan_period.id == app_id
                )
                
                # Alle Appointments sammeln, die diese AvailDays verwenden
                total_hours = 0.0
                appointment_count = 0
                unique_appointments = set()  # 🔥 KRITISCHER FIX: Verhindert Doppelzählung
                
                logger.debug(f"Gefundene AvailDays für ActorPlanPeriod {app_id}: {len(list(avail_days))}")
                
                for avail_day in avail_days:
                    # Jeder AvailDay kann in mehreren Appointments verwendet werden
                    appointments_for_this_avail_day = list(avail_day.appointments)
                    logger.debug(f"AvailDay {avail_day.id}: {len(appointments_for_this_avail_day)} Appointments")
                    
                    for appointment in appointments_for_this_avail_day:
                        # 🔥 KRITISCHER FIX: Nur einmalige Zählung pro Appointment
                        if appointment.id not in unique_appointments:
                            unique_appointments.add(appointment.id)
                            appointment_count += 1
                            
                            if appointment.event and appointment.event.time_of_day:
                                # Zeit-Attribute korrekt abrufen (datetime.time Objekte)
                                start_time = appointment.event.time_of_day.start
                                end_time = appointment.event.time_of_day.end
                                
                                if start_time and end_time:
                                    # Berechnung der Event-Dauer in Stunden
                                    event_hours = calculate_delta_from_time_objects(start_time, end_time)
                                    total_hours += event_hours
                                    logger.debug(f"✅ UNIQUE Appointment {appointment.id}: {event_hours} Stunden")
                                else:
                                    logger.warning(f"Appointment {appointment.id}: Fehlende Zeit-Daten")
                            else:
                                logger.warning(f"Appointment {appointment.id}: Fehlendes Event oder TimeOfDay")
                        else:
                            logger.debug(f"⏭️ SKIP: Appointment {appointment.id} bereits gezählt")
        except Exception as e:
            logger.error(f"❌ Fehler bei Workload-Berechnung für ActorPlanPeriod {app_id}: {e}")
            return 0.0
