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
    # Summary Cards
    aktive_clowns: int
    einrichtungen_count: int
    gesamteinsaetze: int
    durchschnittliche_erfuellung: float
    
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
        all_appointments = cls._get_appointments_from_plans(latest_plans)
        
        # Berechne Dashboard-Komponenten
        einrichtungen = cls._calculate_einrichtung_details(all_appointments, plan_periods)
        clowns = cls._calculate_clown_einsaetze(all_appointments)
        monatliche_rates = cls._calculate_monthly_fulfillment(plan_periods, latest_plans)
        netzwerk_nodes, netzwerk_links = cls._calculate_netzwerk_data(all_appointments)
        
        # Summary-Daten
        aktive_clowns = len(clowns)
        einrichtungen_count = len(einrichtungen)
        gesamteinsaetze = len(all_appointments)
        durchschnitt_erfuellung = (
            sum(e.erfuellungsrate for e in einrichtungen) / len(einrichtungen)
            if einrichtungen else 0.0
        )
        
        return DashboardData(
            aktive_clowns=aktive_clowns,
            einrichtungen_count=einrichtungen_count,
            gesamteinsaetze=gesamteinsaetze,
            durchschnittliche_erfuellung=durchschnitt_erfuellung,
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
        plans: List[models.Plan]
    ) -> List[models.Appointment]:
        """Sammelt alle Appointments aus den gegebenen Plänen"""
        all_appointments = []
        
        for plan in plans:
            appointments = select(
                a for a in models.Appointment
                if a.plan == plan
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
        """Berechnet Details für Einrichtungen"""
        
        # Sammle geplante Events pro Einrichtung
        planned_events = defaultdict(int)
        actual_appointments = defaultdict(int)
        
        # Zähle geplante Events aus allen Planperioden
        for plan_period in plan_periods:
            for location_plan_period in plan_period.location_plan_periods:
                location_name = location_plan_period.location_of_work.name_and_city
                # Zähle Events in dieser LocationPlanPeriod
                events_count = len([e for e in location_plan_period.events if not e.prep_delete])
                planned_events[location_name] += events_count
        
        # Zähle tatsächliche Appointments pro Einrichtung
        for appointment in appointments:
            location_name = appointment.event.location_plan_period.location_of_work.name_and_city
            actual_appointments[location_name] += 1
        
        # Kombiniere zu Einrichtung-Details
        einrichtungen = []
        for location_name in planned_events.keys():
            geplant = planned_events[location_name]
            durchgefuehrt = actual_appointments.get(location_name, 0)
            ausfaelle = geplant - durchgefuehrt
            erfuellungsrate = (durchgefuehrt / geplant * 100) if geplant > 0 else 0.0
            
            einrichtungen.append(EinrichtungDetail(
                name=location_name,
                geplant=geplant,
                durchgefuehrt=durchgefuehrt,
                ausfaelle=max(0, ausfaelle),  # Negative Ausfälle vermeiden
                erfuellungsrate=erfuellungsrate
            ))
        
        # Sortiere nach Erfüllungsrate (absteigend)
        einrichtungen.sort(key=lambda x: x.erfuellungsrate, reverse=True)
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
            gesamteinsaetze=0,
            durchschnittliche_erfuellung=0.0,
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
