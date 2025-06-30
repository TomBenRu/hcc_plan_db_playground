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


class MonatlicheErfuellung(BaseModel):
    """Monatliche Erfüllungsrate"""
    monat: str
    rate: float


class NetzwerkVerbindung(BaseModel):
    """Verbindung zwischen Clown und Einrichtung"""
    source: str
    target: str
    weight: int


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
        project_id: Optional[UUID] = None
    ) -> DashboardData:
        """
        Hauptmethode für Dashboard-Daten.
        
        Args:
            start_date: Startdatum für die Analyse
            end_date: Enddatum für die Analyse
            team_id: Optional - für team-spezifische Analyse
            project_id: Optional - für projekt-weite Analyse
            
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
        einrichtungen = cls._calculate_einrichtung_details(all_appointments, plan_periods)
        clowns = cls._calculate_clown_einsaetze(all_appointments)
        monatliche_rates = cls._calculate_monthly_fulfillment(plan_periods, latest_plans)
        netzwerk_nodes, netzwerk_links = cls._calculate_netzwerk_data(all_appointments)
        
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
        plan_periods: List[models.PlanPeriod]
    ) -> List[EinrichtungDetail]:
        """Berechnet Details für Einrichtungen basierend auf tatsächlich geplanten Events (via Appointments)"""
        
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
            
            # Events mit 0 geplanten Mitarbeitern überspringen (formal geplant aber nicht stattfindend)
            if planned_staff == 0:
                logger.debug(f"Appointment {appointment.id} für Event {event.date} in {location_name}: 0 geplante Mitarbeiter - übersprungen")
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
        appointments: List[models.Appointment]
    ) -> List[ClownEinsatz]:
        """Berechnet Einsätze pro Clown"""
        
        clown_counts = Counter()
        
        for appointment in appointments:
            for avail_day in appointment.avail_days:
                person = avail_day.actor_plan_period.person
                clown_counts[person.full_name] += 1
        
        clowns = [
            ClownEinsatz(name=name, einsaetze=count)
            for name, count in clown_counts.most_common()
        ]
        
        return clowns

    @classmethod
    def _calculate_monthly_fulfillment(
        cls,
        plan_periods: List[models.PlanPeriod],
        plans: List[models.Plan]
    ) -> List[MonatlicheErfuellung]:
        """Berechnet monatliche Erfüllungsraten"""
        
        monthly_data = defaultdict(lambda: {'geplant': 0, 'durchgefuehrt': 0})
        
        # Sammle Daten pro Monat
        for plan_period in plan_periods:
            plan = next((p for p in plans if p.plan_period == plan_period), None)
            if not plan:
                continue
                
            # Bestimme Monat (verwende Start-Datum der Planperiode)
            year_month = plan_period.start.strftime('%Y-%m')
            month_name = plan_period.start.strftime('%b %y')
            
            # Zähle geplante Events
            for location_plan_period in plan_period.location_plan_periods:
                events_count = len([e for e in location_plan_period.events if not e.prep_delete])
                monthly_data[year_month]['geplant'] += events_count
                monthly_data[year_month]['month_name'] = month_name
            
            # Zähle durchgeführte Appointments
            appointments = select(
                a for a in models.Appointment
                if a.plan == plan and not a.prep_delete
            )
            monthly_data[year_month]['durchgefuehrt'] += len(list(appointments))
        
        # Konvertiere zu MonatlicheErfuellung
        monthly_rates = []
        for year_month in sorted(monthly_data.keys()):
            data = monthly_data[year_month]
            rate = (data['durchgefuehrt'] / data['geplant'] * 100) if data['geplant'] > 0 else 0.0
            
            monthly_rates.append(MonatlicheErfuellung(
                monat=data['month_name'],
                rate=rate
            ))
        
        return monthly_rates

    @classmethod
    def _calculate_netzwerk_data(
        cls,
        appointments: List[models.Appointment]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Berechnet Netzwerk-Daten für D3.js Visualisierung"""
        
        # Sammle Clowns und Einrichtungen
        clowns = set()
        einrichtungen = set()
        connections = Counter()
        
        for appointment in appointments:
            location_name = appointment.event.location_plan_period.location_of_work.name_and_city
            einrichtungen.add(location_name)
            
            for avail_day in appointment.avail_days:
                person_name = avail_day.actor_plan_period.person.full_name
                clowns.add(person_name)
                
                # Zähle Verbindung
                connections[(person_name, location_name)] += 1
        
        # Erstelle Nodes
        nodes = []
        
        # Clown-Nodes
        clown_einsaetze = Counter()
        for appointment in appointments:
            for avail_day in appointment.avail_days:
                person_name = avail_day.actor_plan_period.person.full_name
                clown_einsaetze[person_name] += 1
        
        for clown in clowns:
            nodes.append({
                'id': clown,
                'type': 'clown',
                'einsaetze': clown_einsaetze.get(clown, 0)
            })
        
        # Einrichtung-Nodes
        for einrichtung in einrichtungen:
            nodes.append({
                'id': einrichtung,
                'type': 'einrichtung'
            })
        
        # Erstelle Links
        links = []
        for (clown, einrichtung), weight in connections.items():
            links.append({
                'source': clown,
                'target': einrichtung,
                'weight': weight
            })
        
        return nodes, links

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
            zeitraum_start=start_date.strftime('%d.%m.%Y'),
            zeitraum_ende=end_date.strftime('%d.%m.%Y'),
            team_name=team_name,
            project_name=project_name
        )
