"""
Dashboard Service für Einsatzanalyse-Visualisierung

Service-Layer für die Aufbereitung der Daten für das interaktive HTML-Dashboard.
"""

import datetime
import logging
from typing import Optional, Dict, List, Any
from uuid import UUID
from collections import defaultdict, Counter
import calendar

from pony.orm import db_session, select, desc
from pydantic import BaseModel

from database import models
from database.db_services import log_function_info, LOGGING_ENABLED

logger = logging.getLogger(__name__)


class EinrichtungDetail(BaseModel):
    """Details einer Einrichtung für das Dashboard"""
    name: str
    geplant: int
    durchgefuehrt: int
    ausfaelle: int
    erfuellungsrate: float
    
    # Zusätzliche Termin-Metriken
    geplante_termine: int
    ausgefallene_termine: int
    termine_erfuellungsrate: float


class ClownEinsatz(BaseModel):
    """Einsätze eines Clowns"""
    name: str
    einsaetze: int
    is_guest: bool = False  # True für Gastmitarbeiter


class MonatlicheErfuellung(BaseModel):
    """Monatliche Erfüllungsraten (beide Metriken)"""
    monat: str
    mitarbeiter_rate: float
    termine_rate: float


class NetzwerkVerbindung(BaseModel):
    """Verbindung zwischen Clown und Einrichtung"""
    source: str
    target: str
    weight: int


class ClownTimeline(BaseModel):
    """Zeitlicher Verlauf der Einsätze eines Clowns/Gasts"""
    name: str
    is_guest: bool = False
    monthly_data: List[Dict[str, Any]]  # [{"monat": "Jan 25", "einsaetze": 5}, ...]


class MitarbeiterSegment(BaseModel):
    """Ein Segment in der gestapelten Balkengrafik (Mitarbeiter)"""
    name: str
    einsaetze: int
    is_guest: bool = False


class EinrichtungSegment(BaseModel):
    """Ein Segment in der gestapelten Balkengrafik (Einrichtung)"""
    name: str
    einsaetze: int


class EinrichtungStackedData(BaseModel):
    """Daten für einen Balken in 'Nach Einrichtung' Ansicht"""
    einrichtung: str
    total_einsaetze: int
    mitarbeiter_segmente: List[MitarbeiterSegment]


class MitarbeiterStackedData(BaseModel):
    """Daten für einen Balken in 'Nach Mitarbeiter' Ansicht"""
    mitarbeiter: str
    is_guest: bool
    total_einsaetze: int
    einrichtung_segmente: List[EinrichtungSegment]


class StackedBarChartData(BaseModel):
    """Komplette Daten für beide gestapelten Balkengrafiken"""
    einrichtung_view: List[EinrichtungStackedData]
    mitarbeiter_view: List[MitarbeiterStackedData]


class DashboardData(BaseModel):
    """Komplette Daten für das Dashboard"""
    # Summary Cards (erweitert)
    aktive_clowns: int
    einrichtungen_count: int
    
    # Mitarbeiter-Einsätze
    total_geplante_mitarbeiter: int
    total_durchgefuehrte_mitarbeiter: int
    mitarbeiter_erfuellung: float
    
    # Termine  
    total_geplante_termine: int
    total_durchgefuehrte_termine: int
    termine_erfuellung: float
    
    # Einrichtungsdetails
    einrichtungen: List[EinrichtungDetail]
    
    # Clown-Einsätze
    clowns: List[ClownEinsatz]
    
    # Monatliche Entwicklung
    monatliche_erfuellung: List[MonatlicheErfuellung]
    
    # Netzwerk-Daten
    netzwerk_nodes: List[Dict[str, Any]]
    netzwerk_links: List[Dict[str, Any]]
    
    # Clown-Timeline-Daten
    clown_timeline: List[ClownTimeline]

    
    # Gestapelte Balkengrafik-Daten
    stacked_bar_data: StackedBarChartData
    
    # Meta-Informationen
    zeitraum_start: str
    zeitraum_ende: str
    team_name: Optional[str]
    project_name: str


class DashboardService:
    """Service für Dashboard-Daten-Aufbereitung"""

    @classmethod
    @db_session(sql_debug=LOGGING_ENABLED, show_values=LOGGING_ENABLED)
    def get_dashboard_data(
        cls,
        start_date: datetime.date,
        end_date: datetime.date,
        team_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        include_zero_cast_events: bool = False,
        include_guests: bool = False
    ) -> DashboardData:
        """
        Hauptmethode für Dashboard-Daten.
        
        Args:
            start_date: Startdatum für die Analyse
            end_date: Enddatum für die Analyse
            team_id: Optional - für team-spezifische Analyse
            project_id: Optional - für projekt-weite Analyse
            include_zero_cast_events: Optional - True um Events mit Besetzungsstärke 0 einzubeziehen
            include_guests: Optional - True um Gastmitarbeiter in Clown-Statistiken einzubeziehen
            
        Returns:
            DashboardData: Komplette Daten für das Dashboard
        """
        log_function_info(cls)
        
        if not team_id and not project_id:
            raise ValueError("Entweder team_id oder project_id muss angegeben werden")
            
        # Bestimme Kontext
        if team_id:
            team_db = models.Team.get(id=team_id)
            project_db = team_db.project
            team_name = team_db.name
        else:
            project_db = models.Project.get(id=project_id)
            team_name = None
            
        # Hole relevante Planperioden
        plan_periods = cls._get_plan_periods_in_range(
            start_date, end_date, team_id, project_id
        )
        
        if not plan_periods:
            return cls._create_empty_dashboard_data(
                team_name, project_db.name, start_date, end_date
            )
            
        # Hole aktuellste Pläne
        latest_plans = cls._get_latest_plans_per_period(plan_periods)
        
        # Sammle alle Appointments
        all_appointments = cls._get_appointments_from_plans(latest_plans, start_date, end_date)
        
        # Berechne Dashboard-Komponenten
        einrichtungen = cls._calculate_einrichtung_details(all_appointments, plan_periods, include_zero_cast_events)
        clowns = cls._calculate_clown_einsaetze(all_appointments, include_guests)
        monatliche_rates = cls._calculate_monthly_fulfillment(plan_periods, latest_plans, include_zero_cast_events)
        netzwerk_nodes, netzwerk_links = cls._calculate_netzwerk_data(all_appointments, include_guests)
        clown_timeline = cls._calculate_clown_timeline(all_appointments, include_guests)
        stacked_bar_data = cls._calculate_stacked_bar_data(all_appointments, include_guests)
        
        # Summary-Daten (erweitert um detaillierte Metriken)
        aktive_clowns = len(clowns)
        einrichtungen_count = len(einrichtungen)
        
        # Berechne Gesamt-Metriken aus Einrichtungen
        total_geplante_mitarbeiter = sum(e.geplant for e in einrichtungen)
        total_durchgefuehrte_mitarbeiter = sum(e.durchgefuehrt for e in einrichtungen)
        total_geplante_termine = sum(e.geplante_termine for e in einrichtungen)
        total_ausgefallene_termine = sum(e.ausgefallene_termine for e in einrichtungen)
        total_durchgefuehrte_termine = total_geplante_termine - total_ausgefallene_termine
        
        # Erfüllungsraten
        mitarbeiter_erfuellung = (total_durchgefuehrte_mitarbeiter / total_geplante_mitarbeiter * 100) if total_geplante_mitarbeiter > 0 else 0.0
        termine_erfuellung = (total_durchgefuehrte_termine / total_geplante_termine * 100) if total_geplante_termine > 0 else 0.0
        
        return DashboardData(
            aktive_clowns=aktive_clowns,
            einrichtungen_count=einrichtungen_count,
            total_geplante_mitarbeiter=total_geplante_mitarbeiter,
            total_durchgefuehrte_mitarbeiter=total_durchgefuehrte_mitarbeiter,
            mitarbeiter_erfuellung=mitarbeiter_erfuellung,
            total_geplante_termine=total_geplante_termine,
            total_durchgefuehrte_termine=total_durchgefuehrte_termine,
            termine_erfuellung=termine_erfuellung,
            einrichtungen=einrichtungen,
            clowns=clowns,
            monatliche_erfuellung=monatliche_rates,
            netzwerk_nodes=netzwerk_nodes,
            netzwerk_links=netzwerk_links,
            clown_timeline=clown_timeline,
            stacked_bar_data=stacked_bar_data,
            zeitraum_start=start_date.strftime('%d.%m.%Y'),
            zeitraum_ende=end_date.strftime('%d.%m.%Y'),
            team_name=team_name,
            project_name=project_db.name
        )

    @classmethod
    @db_session
    def _get_plan_periods_in_range(
        cls,
        start_date: datetime.date,
        end_date: datetime.date,
        team_id: Optional[UUID],
        project_id: Optional[UUID]
    ) -> List[models.PlanPeriod]:
        """Ermittelt alle Planperioden im angegebenen Zeitraum"""
        
        if team_id:
            plan_periods = select(
                pp for pp in models.PlanPeriod
                if pp.team.id == team_id
                and pp.start <= end_date
                and pp.end >= start_date
                and not pp.prep_delete
            ).order_by(models.PlanPeriod.start)
        else:
            plan_periods = select(
                pp for pp in models.PlanPeriod
                if pp.team.project.id == project_id
                and pp.start <= end_date
                and pp.end >= start_date
                and not pp.prep_delete
            ).order_by(models.PlanPeriod.start)
            
        return list(plan_periods)

    @classmethod
    @db_session
    def _get_latest_plans_per_period(
        cls,
        plan_periods: List[models.PlanPeriod]
    ) -> List[models.Plan]:
        """Ermittelt den jeweils aktuellsten Plan pro Planperiode"""
        latest_plans = []
        
        for plan_period in plan_periods:
            latest_plan = select(
                p for p in models.Plan
                if p.plan_period == plan_period
                and not p.prep_delete
            ).order_by(desc(models.Plan.last_modified)).first()
            
            if latest_plan:
                latest_plans.append(latest_plan)
                
        return latest_plans

    @classmethod
    @db_session
    def _get_appointments_from_plans(
        cls,
        plans: List[models.Plan],
        start_date: datetime.date,
        end_date: datetime.date
    ) -> List[models.Appointment]:
        """Sammelt alle Appointments aus den gegebenen Plänen"""
        all_appointments = []
        
        for plan in plans:
            appointments = select(
                a for a in models.Appointment
                if a.plan == plan
                and a.event.date >= start_date
                and a.event.date <= end_date
                and not a.prep_delete
            )
            all_appointments.extend(appointments)
            
        return all_appointments

    @classmethod
    def _calculate_einrichtung_details(
        cls,
        appointments: List[models.Appointment],
        plan_periods: List[models.PlanPeriod],
        include_zero_cast_events: bool = False
    ) -> List[EinrichtungDetail]:
        """Berechnet Details für Einrichtungen basierend auf tatsächlich geplanten Events (via Appointments)
        
        Args:
            appointments: Liste aller Appointments
            plan_periods: Liste aller relevanten Planperioden
            include_zero_cast_events: True um Events mit 0 Besetzung einzubeziehen (Besetzung aus location_plan_period)
        
        Returns:
            Liste von EinrichtungDetail-Objekten
        """
        
        # Sammle geplante und tatsächliche Mitarbeiter-Einsätze + Termine pro Einrichtung
        planned_staff_assignments = defaultdict(int)
        actual_staff_assignments = defaultdict(int)
        planned_appointments = defaultdict(int)  # Termine mit >0 geplanten Mitarbeitern
        cancelled_appointments = defaultdict(int)  # Termine mit >0 geplant aber 0 durchgeführt
        
        logger.info(f"Berechne Einrichtungsdetails basierend auf {len(appointments)} Appointments")
        
        # Filtere Appointments: Nur nicht zum Löschen markierte
        active_appointments = [a for a in appointments if not a.prep_delete]
        deleted_appointments_count = len(appointments) - len(active_appointments)
        
        if deleted_appointments_count > 0:
            logger.info(f"Gefiltert: {deleted_appointments_count} zum Löschen markierte Appointments ignoriert")
        
        logger.info(f"Verarbeite {len(active_appointments)} aktive Appointments")
        
        # Iteriere über aktive Appointments (= tatsächlich geplante Events)
        for appointment in active_appointments:
            event = appointment.event
            location_name = event.location_plan_period.location_of_work.name_and_city
            
            # 1. GEPLANTE MITARBEITER: Aus CastGroup des Events
            planned_staff = 0
            staff_source = "unknown"
            
            if hasattr(event, 'cast_group') and event.cast_group:
                planned_staff = event.cast_group.nr_actors
                staff_source = f"event.cast_group.nr_actors (CastGroup ID: {event.cast_group.id})"
            else:
                # Fallback auf LocationPlanPeriod/LocationOfWork wenn keine CastGroup
                if event.location_plan_period.nr_actors is not None:
                    planned_staff = event.location_plan_period.nr_actors
                    staff_source = "location_plan_period.nr_actors (Fallback)"
                else:
                    planned_staff = event.location_plan_period.location_of_work.nr_actors
                    staff_source = "location_of_work.nr_actors (Fallback)"
            
            # Events mit 0 geplanten Mitarbeitern behandeln
            if planned_staff == 0:
                if not include_zero_cast_events:
                    logger.debug(f"Appointment {appointment.id} für Event {event.date} in {location_name}: 0 geplante Mitarbeiter - übersprungen")
                    continue
                else:
                    # Bei include_zero_cast_events: Verwende alternative Besetzungslogik
                    alternative_staff = 0
                    alt_source = "unknown"
                    
                    if event.location_plan_period.nr_actors is not None:
                        alternative_staff = event.location_plan_period.nr_actors
                        alt_source = f"location_plan_period.nr_actors (LocationPlanPeriod ID: {event.location_plan_period.id})"
                    elif event.location_plan_period.location_of_work.nr_actors is not None:
                        alternative_staff = event.location_plan_period.location_of_work.nr_actors
                        alt_source = f"location_of_work.nr_actors (LocationOfWork ID: {event.location_plan_period.location_of_work.id})"
                    
                    if alternative_staff > 0:
                        planned_staff = alternative_staff
                        staff_source = f"ZERO-CAST-FALLBACK: {alt_source}"
                        logger.debug(f"Zero-Cast Event {appointment.id}: Verwende alternative Besetzung {planned_staff} aus {alt_source}")
                    else:
                        # Auch alternative Quellen ergeben 0 - überspringe
                        logger.debug(f"Zero-Cast Event {appointment.id}: Auch alternative Quellen ergeben 0 Mitarbeiter - übersprungen")
                        continue
            
            # Das ist ein geplanter Termin (>0 Mitarbeiter geplant)
            planned_appointments[location_name] += 1
            planned_staff_assignments[location_name] += planned_staff
            
            # 2. TATSÄCHLICHE MITARBEITER: Aus Appointment (avail_days + guests)
            # Reguläre Mitarbeiter (avail_days)
            regular_staff_count = len(appointment.avail_days)
            
            # Gastmitarbeiter (guests JSON-Array)
            guest_staff_count = 0
            try:
                import json
                if appointment.guests:
                    guests_data = json.loads(appointment.guests) if isinstance(appointment.guests, str) else appointment.guests
                    guest_staff_count = len(guests_data) if guests_data else 0
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Fehler beim Parsen der Guests für Appointment {appointment.id}: {e}")
                guest_staff_count = 0
            
            # Gesamtzahl eingesetzter Mitarbeiter
            total_actual_staff = regular_staff_count + guest_staff_count
            actual_staff_assignments[location_name] += total_actual_staff
            
            # Prüfe ob der Termin ausgefallen ist (>0 geplant aber 0 durchgeführt)
            if total_actual_staff == 0:
                cancelled_appointments[location_name] += 1
                logger.debug(f"  → Termin ausgefallen (0 Mitarbeiter eingesetzt)")
            
            logger.debug(f"Appointment {appointment.id} - Event {event.date} in {location_name}:")
            logger.debug(f"  Geplante Mitarbeiter: {planned_staff} (Quelle: {staff_source})")
            logger.debug(f"  Reguläre Mitarbeiter: {regular_staff_count}")
            logger.debug(f"  Gastmitarbeiter: {guest_staff_count}")
            logger.debug(f"  Tatsächliche Mitarbeiter: {total_actual_staff}")
        
        logger.info(f"Geplante Mitarbeiter-Einsätze (aus tatsächlich geplanten Events): {dict(planned_staff_assignments)}")
        logger.info(f"Tatsächliche Mitarbeiter-Einsätze (inkl. Gäste): {dict(actual_staff_assignments)}")
        logger.info(f"Geplante Termine (Events mit >0 Mitarbeitern): {dict(planned_appointments)}")
        logger.info(f"Ausgefallene Termine (geplant aber 0 durchgeführt): {dict(cancelled_appointments)}")
        
        # Falls keine Daten vorhanden
        if not planned_staff_assignments and not actual_staff_assignments:
            logger.warning("Keine geplanten oder tatsächlichen Mitarbeiter-Einsätze gefunden")
            return []
        
        # Falls nur tatsächliche Einsätze vorhanden (alle Events hatten 0 geplante Mitarbeiter)
        if not planned_staff_assignments and actual_staff_assignments:
            logger.warning("Keine geplanten Mitarbeiter-Einsätze gefunden - verwende tatsächliche Einsätze als Basis")
            einrichtungen = []
            for location_name, actual_staff in actual_staff_assignments.items():
                einrichtungen.append(EinrichtungDetail(
                    name=location_name,
                    geplant=actual_staff,
                    durchgefuehrt=actual_staff,
                    ausfaelle=0,
                    erfuellungsrate=100.0,
                    geplante_termine=1,  # Annahme: mindestens 1 Termin
                    ausgefallene_termine=0,
                    termine_erfuellungsrate=100.0
                ))
            
            einrichtungen.sort(key=lambda x: x.durchgefuehrt, reverse=True)
            return einrichtungen
        
        # Kombiniere zu Einrichtung-Details
        einrichtungen = []
        all_locations = set(planned_staff_assignments.keys()) | set(actual_staff_assignments.keys())
        
        for location_name in all_locations:
            # Mitarbeiter-Einsätze
            geplant = planned_staff_assignments.get(location_name, 0)
            durchgefuehrt = actual_staff_assignments.get(location_name, 0)
            
            # Termine
            geplante_termine = planned_appointments.get(location_name, 0)
            ausgefallene_termine = cancelled_appointments.get(location_name, 0)
            
            # Falls geplant = 0 aber tatsächliche Einsätze vorhanden, setze geplant = durchgeführt
            if geplant == 0 and durchgefuehrt > 0:
                geplant = durchgefuehrt
                geplante_termine = 1  # Annahme: mindestens 1 Termin
                logger.debug(f"Korrigiere {location_name}: setze geplant={geplant} (keine Planungsdaten gefunden)")
            
            # Erfüllungsraten berechnen
            ausfaelle = geplant - durchgefuehrt
            erfuellungsrate = (durchgefuehrt / geplant * 100) if geplant > 0 else 0.0
            
            durchgefuehrte_termine = geplante_termine - ausgefallene_termine
            termine_erfuellungsrate = (durchgefuehrte_termine / geplante_termine * 100) if geplante_termine > 0 else 0.0
            
            einrichtungen.append(EinrichtungDetail(
                name=location_name,
                geplant=geplant,
                durchgefuehrt=durchgefuehrt,
                ausfaelle=max(0, ausfaelle),  # Negative Ausfälle vermeiden
                erfuellungsrate=erfuellungsrate,
                geplante_termine=geplante_termine,
                ausgefallene_termine=ausgefallene_termine,
                termine_erfuellungsrate=termine_erfuellungsrate
            ))
            
            logger.debug(f"Einrichtung: {location_name}")
            logger.debug(f"  Geplante Mitarbeiter-Einsätze: {geplant}")
            logger.debug(f"  Durchgeführte Mitarbeiter-Einsätze: {durchgefuehrt}")
            logger.debug(f"  Ausgefallene Mitarbeiter-Einsätze: {max(0, ausfaelle)}")
            logger.debug(f"  Erfüllungsrate Mitarbeiter: {erfuellungsrate:.1f}%")
            logger.debug(f"  Geplante Termine: {geplante_termine}")
            logger.debug(f"  Ausgefallene Termine: {ausgefallene_termine}")
            logger.debug(f"  Erfüllungsrate Termine: {termine_erfuellungsrate:.1f}%")
        
        # Sortiere nach Erfüllungsrate (absteigend)
        einrichtungen.sort(key=lambda x: x.erfuellungsrate, reverse=True)
        logger.info(f"Erstellt {len(einrichtungen)} Einrichtungsdetails (basierend auf tatsächlich geplanten Events)")
        
        # Log Gesamtstatistik
        total_geplant = sum(e.geplant for e in einrichtungen)
        total_durchgefuehrt = sum(e.durchgefuehrt for e in einrichtungen)
        total_ausfaelle = sum(e.ausfaelle for e in einrichtungen)
        gesamt_erfuellung = (total_durchgefuehrt / total_geplant * 100) if total_geplant > 0 else 0.0
        
        total_geplante_termine = sum(e.geplante_termine for e in einrichtungen)
        total_ausgefallene_termine = sum(e.ausgefallene_termine for e in einrichtungen)
        total_durchgefuehrte_termine = total_geplante_termine - total_ausgefallene_termine
        gesamt_termine_erfuellung = (total_durchgefuehrte_termine / total_geplante_termine * 100) if total_geplante_termine > 0 else 0.0
        
        logger.info(f"GESAMTSTATISTIK (korrigiert):")
        logger.info(f"  Mitarbeiter-Einsätze - Geplant: {total_geplant}, Durchgeführt: {total_durchgefuehrt}, Ausfälle: {total_ausfaelle}, Erfüllung: {gesamt_erfuellung:.1f}%")
        logger.info(f"  Termine - Geplant: {total_geplante_termine}, Durchgeführt: {total_durchgefuehrte_termine}, Ausgefallen: {total_ausgefallene_termine}, Erfüllung: {gesamt_termine_erfuellung:.1f}%")
        
        return einrichtungen

    @classmethod
    def _calculate_clown_einsaetze(
        cls,
        appointments: List[models.Appointment],
        include_guests: bool = False
    ) -> List[ClownEinsatz]:
        """Berechnet Einsätze pro Clown und optional auch für Gäste
        
        Args:
            appointments: Liste aller Appointments
            include_guests: True um Gastmitarbeiter einzubeziehen
            
        Returns:
            Liste von ClownEinsatz-Objekten (Stamm-Clowns und optional Gäste)
        """
        
        # Reguläre Clowns (Stamm-Mitarbeiter)
        regular_clown_counts = Counter()
        
        # Gäste (falls include_guests=True)
        guest_counts = Counter()
        
        for appointment in appointments:
            # Reguläre Mitarbeiter (avail_days)
            for avail_day in appointment.avail_days:
                person = avail_day.actor_plan_period.person
                regular_clown_counts[person.full_name] += 1
            
            # Gastmitarbeiter (guests JSON-Array)
            if include_guests:
                try:
                    import json
                    if appointment.guests:
                        guests_data = json.loads(appointment.guests) if isinstance(appointment.guests, str) else appointment.guests
                        if guests_data:
                            for guest_info in guests_data:
                                # guest_info kann ein Dict oder String sein
                                if isinstance(guest_info, dict):
                                    guest_name = guest_info.get('name', guest_info.get('full_name', 'Unbekannter Gast'))
                                else:
                                    guest_name = str(guest_info)
                                guest_counts[guest_name] += 1
                                
                except (json.JSONDecodeError, TypeError, AttributeError) as e:
                    logger.warning(f"Fehler beim Parsen der Guests für Appointment {appointment.id}: {e}")
                    continue
        
        # Kombiniere Ergebnisse
        clowns = []
        
        # Reguläre Clowns hinzufügen
        for name, count in regular_clown_counts.most_common():
            clowns.append(ClownEinsatz(name=name, einsaetze=count, is_guest=False))
        
        # Gäste hinzufügen (falls gewünscht)
        if include_guests:
            for name, count in guest_counts.most_common():
                clowns.append(ClownEinsatz(name=f"{name} (Gast)", einsaetze=count, is_guest=True))
        
        # Nach Einsätzen sortieren (absteigend)
        clowns.sort(key=lambda x: x.einsaetze, reverse=True)
        
        logger.debug(f"Clown-Einsätze berechnet: {len(regular_clown_counts)} Stamm-Clowns, {len(guest_counts) if include_guests else 0} Gäste")
        
        return clowns

    @classmethod
    def _calculate_monthly_fulfillment(
        cls,
        plan_periods: List[models.PlanPeriod],
        plans: List[models.Plan],
        include_zero_cast_events: bool = False
    ) -> List[MonatlicheErfuellung]:
        """Berechnet monatliche Erfüllungsraten für beide Metriken
        
        Args:
            plan_periods: Liste aller relevanten Planperioden
            plans: Liste aller relevanten Pläne
            include_zero_cast_events: True um Events mit 0 Besetzung einzubeziehen
        
        Returns:
            Liste von MonatlicheErfuellung-Objekten
        """
        
        monthly_data = defaultdict(lambda: {
            'geplante_mitarbeiter': 0, 'durchgefuehrte_mitarbeiter': 0,
            'geplante_termine': 0, 'ausgefallene_termine': 0,
            'month_name': ''
        })
        
        # Sammle Daten pro Monat basierend auf tatsächlichen Appointments
        for plan_period in plan_periods:
            plan = next((p for p in plans if p.plan_period == plan_period), None)
            if not plan:
                continue
                
            # Hole alle Appointments für diesen Plan
            appointments = select(
                a for a in models.Appointment
                if a.plan == plan and not a.prep_delete
            )
            
            # Gruppiere Appointments nach Monaten
            for appointment in appointments:
                event_date = appointment.event.date
                year_month = event_date.strftime('%Y-%m')
                month_name = event_date.strftime('%b %y')
                monthly_data[year_month]['month_name'] = month_name
                
                # Geplante Mitarbeiter aus CastGroup
                planned_staff = 0
                if hasattr(appointment.event, 'cast_group') and appointment.event.cast_group:
                    planned_staff = appointment.event.cast_group.nr_actors
                elif appointment.event.location_plan_period.nr_actors:
                    planned_staff = appointment.event.location_plan_period.nr_actors
                else:
                    planned_staff = appointment.event.location_plan_period.location_of_work.nr_actors
                
                # Events mit 0 geplanten Mitarbeitern behandeln
                if planned_staff == 0:
                    if not include_zero_cast_events:
                        continue
                    else:
                        # Bei include_zero_cast_events: Verwende alternative Besetzungslogik
                        alternative_staff = 0
                        
                        if appointment.event.location_plan_period.nr_actors is not None:
                            alternative_staff = appointment.event.location_plan_period.nr_actors
                        elif appointment.event.location_plan_period.location_of_work.nr_actors is not None:
                            alternative_staff = appointment.event.location_plan_period.location_of_work.nr_actors
                        
                        if alternative_staff > 0:
                            planned_staff = alternative_staff
                        else:
                            # Auch alternative Quellen ergeben 0 - überspringe
                            continue
                
                # Das ist ein geplanter Termin
                monthly_data[year_month]['geplante_termine'] += 1
                monthly_data[year_month]['geplante_mitarbeiter'] += planned_staff
                
                # Tatsächliche Mitarbeiter (reguläre + Gäste)
                regular_staff = len(appointment.avail_days)
                guest_staff = 0
                try:
                    import json
                    if appointment.guests:
                        guests_data = json.loads(appointment.guests) if isinstance(appointment.guests, str) else appointment.guests
                        guest_staff = len(guests_data) if guests_data else 0
                except:
                    guest_staff = 0
                
                total_actual_staff = regular_staff + guest_staff
                monthly_data[year_month]['durchgefuehrte_mitarbeiter'] += total_actual_staff
                
                # Prüfe ob Termin ausgefallen (geplant aber 0 durchgeführt)
                if total_actual_staff == 0:
                    monthly_data[year_month]['ausgefallene_termine'] += 1
        
        # Konvertiere zu MonatlicheErfuellung
        monthly_rates = []
        for year_month in sorted(monthly_data.keys()):
            data = monthly_data[year_month]
            
            # Mitarbeiter-Erfüllungsrate
            mitarbeiter_rate = (
                data['durchgefuehrte_mitarbeiter'] / data['geplante_mitarbeiter'] * 100
                if data['geplante_mitarbeiter'] > 0 else 0.0
            )
            
            # Termine-Erfüllungsrate
            durchgefuehrte_termine = data['geplante_termine'] - data['ausgefallene_termine']
            termine_rate = (
                durchgefuehrte_termine / data['geplante_termine'] * 100
                if data['geplante_termine'] > 0 else 0.0
            )
            
            monthly_rates.append(MonatlicheErfuellung(
                monat=data['month_name'],
                mitarbeiter_rate=mitarbeiter_rate,
                termine_rate=termine_rate
            ))
            
            logger.debug(f"Monat {data['month_name']}: Mitarbeiter {mitarbeiter_rate:.1f}%, Termine {termine_rate:.1f}%")
        
        return monthly_rates

    @classmethod
    def _calculate_netzwerk_data(
        cls,
        appointments: List[models.Appointment],
        include_guests: bool = False
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Berechnet Netzwerk-Daten für D3.js Visualisierung
        
        Args:
            appointments: Liste aller Appointments
            include_guests: True um Gastmitarbeiter als separate Nodes einzubeziehen
            
        Returns:
            Tuple von (nodes, links) für D3.js Netzwerk-Visualisierung
        """
        
        # Sammle Clowns, Gäste und Einrichtungen
        regular_clowns = set()
        guests = set()
        einrichtungen = set()
        regular_connections = Counter()
        guest_connections = Counter()
        
        for appointment in appointments:
            location_name = appointment.event.location_plan_period.location_of_work.name_and_city
            einrichtungen.add(location_name)
            
            # Reguläre Mitarbeiter (avail_days)
            for avail_day in appointment.avail_days:
                person_name = avail_day.actor_plan_period.person.full_name
                regular_clowns.add(person_name)
                
                # Zähle Verbindung (Clown -> Einrichtung)
                regular_connections[(person_name, location_name)] += 1
            
            # Gastmitarbeiter (guests JSON-Array)
            if include_guests:
                try:
                    import json
                    if appointment.guests:
                        guests_data = json.loads(appointment.guests) if isinstance(appointment.guests, str) else appointment.guests
                        if guests_data:
                            for guest_info in guests_data:
                                # guest_info kann ein Dict oder String sein
                                if isinstance(guest_info, dict):
                                    guest_name = guest_info.get('name', guest_info.get('full_name', 'Unbekannter Gast'))
                                else:
                                    guest_name = str(guest_info)
                                
                                guest_display_name = f"{guest_name} (Gast)"
                                guests.add(guest_display_name)
                                
                                # Zähle Verbindung (Gast -> Einrichtung)
                                guest_connections[(guest_display_name, location_name)] += 1
                                
                except (json.JSONDecodeError, TypeError, AttributeError) as e:
                    logger.warning(f"Fehler beim Parsen der Guests für Appointment {appointment.id}: {e}")
                    continue
        
        # Erstelle Nodes
        nodes = []
        
        # Reguläre Clown-Nodes
        regular_clown_einsaetze = Counter()
        for appointment in appointments:
            for avail_day in appointment.avail_days:
                person_name = avail_day.actor_plan_period.person.full_name
                regular_clown_einsaetze[person_name] += 1
        
        for clown in regular_clowns:
            nodes.append({
                'id': clown,
                'type': 'clown',
                'einsaetze': regular_clown_einsaetze.get(clown, 0)
            })
        
        # Gäste-Nodes (falls gewünscht)
        if include_guests:
            guest_einsaetze = Counter()
            for appointment in appointments:
                try:
                    import json
                    if appointment.guests:
                        guests_data = json.loads(appointment.guests) if isinstance(appointment.guests, str) else appointment.guests
                        if guests_data:
                            for guest_info in guests_data:
                                if isinstance(guest_info, dict):
                                    guest_name = guest_info.get('name', guest_info.get('full_name', 'Unbekannter Gast'))
                                else:
                                    guest_name = str(guest_info)
                                guest_display_name = f"{guest_name} (Gast)"
                                guest_einsaetze[guest_display_name] += 1
                except:
                    continue
            
            for guest in guests:
                nodes.append({
                    'id': guest,
                    'type': 'guest',
                    'einsaetze': guest_einsaetze.get(guest, 0)
                })
        
        # Einrichtung-Nodes
        for einrichtung in einrichtungen:
            nodes.append({
                'id': einrichtung,
                'type': 'einrichtung'
            })
        
        # Erstelle Links
        links = []
        
        # Reguläre Clown-Verbindungen
        for (clown, einrichtung), weight in regular_connections.items():
            links.append({
                'source': clown,
                'target': einrichtung,
                'weight': weight
            })
        
        # Gäste-Verbindungen (falls gewünscht)
        if include_guests:
            for (guest, einrichtung), weight in guest_connections.items():
                links.append({
                    'source': guest,
                    'target': einrichtung,
                    'weight': weight
                })
        
        logger.debug(f"Netzwerk-Daten berechnet: {len(regular_clowns)} Clowns, {len(guests) if include_guests else 0} Gäste, {len(einrichtungen)} Einrichtungen")
        
        return nodes, links

    @classmethod
    def _calculate_clown_timeline(
        cls,
        appointments: List[models.Appointment],
        include_guests: bool = False
    ) -> List[ClownTimeline]:
        """Berechnet zeitlichen Verlauf der Einsätze pro Clown und optional Gäste
        
        Args:
            appointments: Liste aller Appointments
            include_guests: True um Gastmitarbeiter einzubeziehen
            
        Returns:
            Liste von ClownTimeline-Objekten mit monatlichen Einsätzen
        """
        
        # Sammle Einsätze pro Clown und Monat
        regular_clown_monthly = defaultdict(lambda: defaultdict(lambda: {'month_name': '', 'count': 0}))
        guest_monthly = defaultdict(lambda: defaultdict(lambda: {'month_name': '', 'count': 0}))
        
        for appointment in appointments:
            event_date = appointment.event.date
            year_month = event_date.strftime('%Y-%m')
            month_name = event_date.strftime('%b %y')
            
            # Reguläre Mitarbeiter (avail_days)
            for avail_day in appointment.avail_days:
                person_name = avail_day.actor_plan_period.person.full_name
                regular_clown_monthly[person_name][year_month]['month_name'] = month_name
                regular_clown_monthly[person_name][year_month]['count'] += 1
            
            # Gastmitarbeiter (guests JSON-Array)
            if include_guests:
                try:
                    import json
                    if appointment.guests:
                        guests_data = json.loads(appointment.guests) if isinstance(appointment.guests, str) else appointment.guests
                        if guests_data:
                            for guest_info in guests_data:
                                # guest_info kann ein Dict oder String sein
                                if isinstance(guest_info, dict):
                                    guest_name = guest_info.get('name', guest_info.get('full_name', 'Unbekannter Gast'))
                                else:
                                    guest_name = str(guest_info)
                                
                                guest_display_name = f"{guest_name} (Gast)"
                                guest_monthly[guest_display_name][year_month]['month_name'] = month_name
                                guest_monthly[guest_display_name][year_month]['count'] += 1
                                
                except (json.JSONDecodeError, TypeError, AttributeError) as e:
                    logger.warning(f"Fehler beim Parsen der Guests für Appointment {appointment.id}: {e}")
                    continue
        
        # Erstelle Liste aller Monate im Zeitraum (sortiert)
        all_year_months = set()
        for clown_data in regular_clown_monthly.values():
            all_year_months.update(clown_data.keys())
        if include_guests:
            for guest_data in guest_monthly.values():
                all_year_months.update(guest_data.keys())
        
        sorted_year_months = sorted(all_year_months)
        
        # Konvertiere zu ClownTimeline-Objekten
        timelines = []
        
        # Reguläre Clowns
        for clown_name, monthly_data in regular_clown_monthly.items():
            monthly_list = []
            for year_month in sorted_year_months:
                if year_month in monthly_data:
                    monthly_list.append({
                        'monat': monthly_data[year_month]['month_name'],
                        'einsaetze': monthly_data[year_month]['count']
                    })
                else:
                    # Fülle fehlende Monate mit 0 auf
                    month_name = ""
                    if sorted_year_months:
                        # Extrahiere Monatsnamen von anderen Einträgen
                        try:
                            sample_date = datetime.datetime.strptime(year_month, '%Y-%m')
                            month_name = sample_date.strftime('%b %y')
                        except ValueError:
                            month_name = year_month  # Fallback
                    monthly_list.append({
                        'monat': month_name,
                        'einsaetze': 0
                    })
            
            timelines.append(ClownTimeline(
                name=clown_name,
                is_guest=False,
                monthly_data=monthly_list
            ))
        
        # Gäste (falls gewünscht)
        if include_guests:
            for guest_name, monthly_data in guest_monthly.items():
                monthly_list = []
                for year_month in sorted_year_months:
                    if year_month in monthly_data:
                        monthly_list.append({
                            'monat': monthly_data[year_month]['month_name'],
                            'einsaetze': monthly_data[year_month]['count']
                        })
                    else:
                        # Fülle fehlende Monate mit 0 auf
                        month_name = ""
                        if sorted_year_months:
                            try:
                                sample_date = datetime.datetime.strptime(year_month, '%Y-%m')
                                month_name = sample_date.strftime('%b %y')
                            except ValueError:
                                month_name = year_month  # Fallback
                        monthly_list.append({
                            'monat': month_name,
                            'einsaetze': 0
                        })
                
                timelines.append(ClownTimeline(
                    name=guest_name,
                    is_guest=True,
                    monthly_data=monthly_list
                ))
        
        # Sortiere nach Gesamteinsätzen (absteigend)
        timelines.sort(key=lambda x: sum(m['einsaetze'] for m in x.monthly_data), reverse=True)
        
        logger.debug(f"Clown-Timeline berechnet: {len(timelines)} Zeitreihen für {len(sorted_year_months)} Monate")
        
        return timelines


    @classmethod
    def _calculate_stacked_bar_data(
        cls,
        appointments: List[models.Appointment],
        include_guests: bool = False,
        top_n: int = 15
    ) -> StackedBarChartData:
        """
        Berechnet gestapelte Balken-Daten mit Top-N-Filterung
        
        Args:
            appointments: Liste aller Appointments
            include_guests: Gastmitarbeiter einbeziehen
            top_n: Anzahl Top-Einrichtungen/Mitarbeiter (Rest wird zu "Sonstige" aggregiert)
            
        Returns:
            StackedBarChartData mit beiden Ansichten (Einrichtung und Mitarbeiter)
        """
        
        # Matrix aufbauen: einrichtung -> mitarbeiter -> count
        einrichtung_mitarbeiter_map = defaultdict(lambda: defaultdict(int))
        mitarbeiter_einrichtung_map = defaultdict(lambda: defaultdict(int))
        
        # Track ob Mitarbeiter ein Gast ist
        mitarbeiter_is_guest = {}
        
        logger.debug(f"Berechne Stacked Bar Data für {len(appointments)} Appointments (include_guests={include_guests})")
        
        for appointment in appointments:
            if appointment.prep_delete:
                continue
                
            location_name = appointment.event.location_plan_period.location_of_work.name_and_city
            
            # Reguläre Mitarbeiter (avail_days)
            for avail_day in appointment.avail_days:
                person_name = avail_day.actor_plan_period.person.full_name
                einrichtung_mitarbeiter_map[location_name][person_name] += 1
                mitarbeiter_einrichtung_map[person_name][location_name] += 1
                mitarbeiter_is_guest[person_name] = False
            
            # Gastmitarbeiter (guests JSON-Array)
            if include_guests:
                try:
                    import json
                    if appointment.guests:
                        guests_data = json.loads(appointment.guests) if isinstance(appointment.guests, str) else appointment.guests
                        if guests_data:
                            for guest_info in guests_data:
                                # guest_info kann ein Dict oder String sein
                                if isinstance(guest_info, dict):
                                    guest_name = guest_info.get('name', guest_info.get('full_name', 'Unbekannter Gast'))
                                else:
                                    guest_name = str(guest_info)
                                
                                # Markiere als Gast mit "(Gast)" Suffix
                                guest_display_name = f"{guest_name} (Gast)"
                                einrichtung_mitarbeiter_map[location_name][guest_display_name] += 1
                                mitarbeiter_einrichtung_map[guest_display_name][location_name] += 1
                                mitarbeiter_is_guest[guest_display_name] = True
                                
                except (json.JSONDecodeError, TypeError, AttributeError) as e:
                    logger.warning(f"Fehler beim Parsen der Guests für Appointment {appointment.id}: {e}")
                    continue
        
        logger.debug(f"Matrix aufgebaut: {len(einrichtung_mitarbeiter_map)} Einrichtungen, {len(mitarbeiter_einrichtung_map)} Mitarbeiter")
        
        # ====================
        # ANSICHT 1: Nach Einrichtung
        # ====================
        
        # Berechne Total-Einsätze pro Einrichtung
        einrichtung_totals = {
            einrichtung: sum(counts.values())
            for einrichtung, counts in einrichtung_mitarbeiter_map.items()
        }
        
        # Sortiere Einrichtungen nach Total-Einsätzen (absteigend)
        sorted_einrichtungen = sorted(
            einrichtung_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Top N Einrichtungen + Rest als "Sonstige"
        top_einrichtungen = [e[0] for e in sorted_einrichtungen[:top_n]]
        
        if len(sorted_einrichtungen) > top_n:
            logger.debug(f"Filtere Einrichtungen: Top {top_n} von {len(sorted_einrichtungen)}, Rest wird zu 'Sonstige'")
            
            # Aggregiere Rest zu "Sonstige"
            sonstige_mitarbeiter_counts = defaultdict(int)
            for einrichtung, _ in sorted_einrichtungen[top_n:]:
                for mitarbeiter, count in einrichtung_mitarbeiter_map[einrichtung].items():
                    sonstige_mitarbeiter_counts[mitarbeiter] += count
            
            # Füge "Sonstige" hinzu
            if sonstige_mitarbeiter_counts:
                einrichtung_mitarbeiter_map['Sonstige Einrichtungen'] = dict(sonstige_mitarbeiter_counts)
                top_einrichtungen.append('Sonstige Einrichtungen')
        
        # Erstelle EinrichtungStackedData
        einrichtung_view = []
        for einrichtung_name in top_einrichtungen:
            mitarbeiter_counts = einrichtung_mitarbeiter_map[einrichtung_name]
            
            # Sortiere Mitarbeiter nach Einsätzen (absteigend)
            sorted_mitarbeiter = sorted(
                mitarbeiter_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            mitarbeiter_segmente = [
                MitarbeiterSegment(
                    name=name,
                    einsaetze=count,
                    is_guest=mitarbeiter_is_guest.get(name, False)
                )
                for name, count in sorted_mitarbeiter
            ]
            
            total = sum(seg.einsaetze for seg in mitarbeiter_segmente)
            
            einrichtung_view.append(EinrichtungStackedData(
                einrichtung=einrichtung_name,
                total_einsaetze=total,
                mitarbeiter_segmente=mitarbeiter_segmente
            ))
        
        logger.debug(f"Einrichtung-View erstellt: {len(einrichtung_view)} Balken")
        
        # ====================
        # ANSICHT 2: Nach Mitarbeiter
        # ====================
        
        # Berechne Total-Einsätze pro Mitarbeiter
        mitarbeiter_totals = {
            mitarbeiter: sum(counts.values())
            for mitarbeiter, counts in mitarbeiter_einrichtung_map.items()
        }
        
        # Sortiere Mitarbeiter nach Total-Einsätzen (absteigend)
        sorted_mitarbeiter = sorted(
            mitarbeiter_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Top N Mitarbeiter + Rest als "Sonstige"
        top_mitarbeiter = [m[0] for m in sorted_mitarbeiter[:top_n]]
        
        if len(sorted_mitarbeiter) > top_n:
            logger.debug(f"Filtere Mitarbeiter: Top {top_n} von {len(sorted_mitarbeiter)}, Rest wird zu 'Sonstige'")
            
            # Aggregiere Rest zu "Sonstige Mitarbeiter"
            sonstige_einrichtung_counts = defaultdict(int)
            for mitarbeiter, _ in sorted_mitarbeiter[top_n:]:
                for einrichtung, count in mitarbeiter_einrichtung_map[mitarbeiter].items():
                    sonstige_einrichtung_counts[einrichtung] += count
            
            # Füge "Sonstige Mitarbeiter" hinzu
            if sonstige_einrichtung_counts:
                mitarbeiter_einrichtung_map['Sonstige Mitarbeiter'] = dict(sonstige_einrichtung_counts)
                mitarbeiter_is_guest['Sonstige Mitarbeiter'] = False
                top_mitarbeiter.append('Sonstige Mitarbeiter')
        
        # Erstelle MitarbeiterStackedData
        mitarbeiter_view = []
        for mitarbeiter_name in top_mitarbeiter:
            einrichtung_counts = mitarbeiter_einrichtung_map[mitarbeiter_name]
            
            # Sortiere Einrichtungen nach Einsätzen (absteigend)
            sorted_einrichtungen_for_mitarbeiter = sorted(
                einrichtung_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            einrichtung_segmente = [
                EinrichtungSegment(
                    name=name,
                    einsaetze=count
                )
                for name, count in sorted_einrichtungen_for_mitarbeiter
            ]
            
            total = sum(seg.einsaetze for seg in einrichtung_segmente)
            
            mitarbeiter_view.append(MitarbeiterStackedData(
                mitarbeiter=mitarbeiter_name,
                is_guest=mitarbeiter_is_guest.get(mitarbeiter_name, False),
                total_einsaetze=total,
                einrichtung_segmente=einrichtung_segmente
            ))
        
        logger.debug(f"Mitarbeiter-View erstellt: {len(mitarbeiter_view)} Balken")
        
        return StackedBarChartData(
            einrichtung_view=einrichtung_view,
            mitarbeiter_view=mitarbeiter_view
        )

    @classmethod
    def _create_empty_dashboard_data(
        cls,
        team_name: Optional[str],
        project_name: str,
        start_date: datetime.date,
        end_date: datetime.date
    ) -> DashboardData:
        """Erstellt leere Dashboard-Daten wenn keine Daten vorhanden"""
        
        return DashboardData(
            aktive_clowns=0,
            einrichtungen_count=0,
            total_geplante_mitarbeiter=0,
            total_durchgefuehrte_mitarbeiter=0,
            mitarbeiter_erfuellung=0.0,
            total_geplante_termine=0,
            total_durchgefuehrte_termine=0,
            termine_erfuellung=0.0,
            einrichtungen=[],
            clowns=[],
            monatliche_erfuellung=[],
            netzwerk_nodes=[],
            netzwerk_links=[],
            clown_timeline=[],
            stacked_bar_data=StackedBarChartData(
                einrichtung_view=[],
                mitarbeiter_view=[]
            ),
            zeitraum_start=start_date.strftime('%d.%m.%Y'),
            zeitraum_ende=end_date.strftime('%d.%m.%Y'),
            team_name=team_name,
            project_name=project_name
        )
