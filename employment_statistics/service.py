"""
Employment Statistics Service

Service-Layer für die Berechnung und Bereitstellung von Einsatzstatistiken.
"""

import datetime
import logging
from typing import Optional, Dict, List, Tuple
from uuid import UUID
from collections import defaultdict, Counter

from pony.orm import db_session, select, desc
from pydantic import BaseModel

from database import models
from database.db_services import log_function_info, LOGGING_ENABLED

logger = logging.getLogger(__name__)


class EmployeeStatistics(BaseModel):
    """Statistiken für einen einzelnen Mitarbeiter"""
    person_id: UUID
    person_name: str
    total_assignments: int
    assignments_by_location: Dict[str, int]  # location_name -> count
    assignments_by_period: Dict[str, int]    # period_name -> count


class LocationStatistics(BaseModel):
    """Statistiken für einen Standort"""
    location_id: UUID
    location_name: str
    total_assignments: int
    employees_count: int
    average_assignments_per_employee: float


class PeriodStatistics(BaseModel):
    """Statistiken für einen Zeitraum"""
    period_name: str
    period_start: datetime.date
    period_end: datetime.date
    total_assignments: int
    employees_count: int
    locations_count: int


class EmploymentStatistics(BaseModel):
    """Gesamtstatistiken für den gewählten Zeitraum"""
    team_name: Optional[str]
    project_name: str
    start_date: datetime.date
    end_date: datetime.date
    total_assignments: int
    total_employees: int
    total_locations: int
    employee_statistics: List[EmployeeStatistics]
    location_statistics: List[LocationStatistics]
    period_statistics: List[PeriodStatistics]
    average_assignments_per_employee: float
    average_assignments_per_period: float


class EmploymentStatisticsService:
    """Service für Einsatzstatistiken"""

    @classmethod
    @db_session(sql_debug=LOGGING_ENABLED, show_values=LOGGING_ENABLED)
    def get_employment_statistics(
        cls,
        start_date: datetime.date,
        end_date: datetime.date,
        team_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None
    ) -> EmploymentStatistics:
        """
        Hauptmethode für Einsatzstatistiken.
        
        Args:
            start_date: Startdatum für die Statistik
            end_date: Enddatum für die Statistik
            team_id: Optional - für team-spezifische Statistiken
            project_id: Optional - für projekt-weite Statistiken (wenn kein team_id)
            
        Returns:
            EmploymentStatistics: Komplette Statistiken für den Zeitraum
        """
        log_function_info(cls)
        
        if not team_id and not project_id:
            raise ValueError("Entweder team_id oder project_id muss angegeben werden")
            
        # Bestimme Kontext (Team oder Projekt)
        if team_id:
            team_db = models.Team.get(id=team_id)
            project_db = team_db.project
            team_name = team_db.name
            context_name = f"Team: {team_name}"
        else:
            project_db = models.Project.get(id=project_id)
            team_name = None
            context_name = f"Projekt: {project_db.name}"
            
        # Hole relevante Planperioden
        plan_periods = cls._get_plan_periods_in_range(
            start_date, end_date, team_id, project_id
        )
        
        if not plan_periods:
            return cls._create_empty_statistics(
                team_name, project_db.name, start_date, end_date
            )
            
        # Hole aktuellste Pläne pro Planperiode
        latest_plans = cls._get_latest_plans_per_period(plan_periods)
        
        # Sammle alle Appointments aus den aktuellsten Plänen
        all_appointments = cls._get_appointments_from_plans(latest_plans)
        
        # Berechne Statistiken
        employee_stats = cls._calculate_employee_statistics(all_appointments, plan_periods)
        location_stats = cls._calculate_location_statistics(all_appointments)
        period_stats = cls._calculate_period_statistics(plan_periods, latest_plans)
        
        # Gesamtstatistiken
        total_assignments = len(all_appointments)
        total_employees = len(employee_stats)
        total_locations = len(location_stats)
        
        avg_assignments_per_employee = (
            total_assignments / total_employees if total_employees > 0 else 0
        )
        avg_assignments_per_period = (
            total_assignments / len(period_stats) if period_stats else 0
        )
        
        return EmploymentStatistics(
            team_name=team_name,
            project_name=project_db.name,
            start_date=start_date,
            end_date=end_date,
            total_assignments=total_assignments,
            total_employees=total_employees,
            total_locations=total_locations,
            employee_statistics=employee_stats,
            location_statistics=location_stats,
            period_statistics=period_stats,
            average_assignments_per_employee=avg_assignments_per_employee,
            average_assignments_per_period=avg_assignments_per_period
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
            # Team-spezifische Planperioden
            plan_periods = select(
                pp for pp in models.PlanPeriod
                if pp.team.id == team_id
                and pp.start <= end_date
                and pp.end >= start_date
                and not pp.prep_delete
            ).order_by(models.PlanPeriod.start)
        else:
            # Projekt-weite Planperioden
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
            # Suche den aktuellsten Plan (nach created_at) für diese Planperiode
            latest_plan = select(
                p for p in models.Plan
                if p.plan_period == plan_period
                and not p.prep_delete
            ).order_by(desc(models.Plan.created_at)).first()
            
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
    def _calculate_employee_statistics(
        cls,
        appointments: List[models.Appointment],
        plan_periods: List[models.PlanPeriod]
    ) -> List[EmployeeStatistics]:
        """Berechnet Statistiken pro Mitarbeiter"""
        
        # Gruppiere Appointments nach Mitarbeitern
        employee_appointments = defaultdict(list)
        
        for appointment in appointments:
            for avail_day in appointment.avail_days:
                person = avail_day.actor_plan_period.person
                employee_appointments[person.id].append({
                    'appointment': appointment,
                    'person': person,
                    'location': appointment.event.location_plan_period.location_of_work,
                    'plan_period': appointment.event.location_plan_period.plan_period
                })
        
        employee_stats = []
        
        for person_id, person_appointments in employee_appointments.items():
            if not person_appointments:
                continue
                
            person = person_appointments[0]['person']
            
            # Zähle Einsätze nach Standorten
            location_counts = Counter()
            for pa in person_appointments:
                location_name = pa['location'].name_and_city
                location_counts[location_name] += 1
            
            # Zähle Einsätze nach Planperioden
            period_counts = Counter()
            for pa in person_appointments:
                period_name = f"{pa['plan_period'].start} - {pa['plan_period'].end}"
                period_counts[period_name] += 1
            
            employee_stats.append(EmployeeStatistics(
                person_id=person.id,
                person_name=person.full_name,
                total_assignments=len(person_appointments),
                assignments_by_location=dict(location_counts),
                assignments_by_period=dict(period_counts)
            ))
            
        # Sortiere nach Anzahl Einsätze (absteigend)
        employee_stats.sort(key=lambda x: x.total_assignments, reverse=True)
        return employee_stats

    @classmethod
    def _calculate_location_statistics(
        cls,
        appointments: List[models.Appointment]
    ) -> List[LocationStatistics]:
        """Berechnet Statistiken pro Standort"""
        
        # Gruppiere nach Standorten
        location_data = defaultdict(lambda: {'appointments': [], 'employees': set()})
        
        for appointment in appointments:
            location = appointment.event.location_plan_period.location_of_work
            location_data[location.id]['appointments'].append(appointment)
            location_data[location.id]['location'] = location
            
            # Sammle eindeutige Mitarbeiter für diesen Standort
            for avail_day in appointment.avail_days:
                person = avail_day.actor_plan_period.person
                location_data[location.id]['employees'].add(person.id)
        
        location_stats = []
        
        for location_id, data in location_data.items():
            location = data['location']
            assignments_count = len(data['appointments'])
            employees_count = len(data['employees'])
            
            avg_assignments = (
                assignments_count / employees_count if employees_count > 0 else 0
            )
            
            location_stats.append(LocationStatistics(
                location_id=location.id,
                location_name=location.name_and_city,
                total_assignments=assignments_count,
                employees_count=employees_count,
                average_assignments_per_employee=avg_assignments
            ))
            
        # Sortiere nach Anzahl Einsätze (absteigend)
        location_stats.sort(key=lambda x: x.total_assignments, reverse=True)
        return location_stats

    @classmethod
    def _calculate_period_statistics(
        cls,
        plan_periods: List[models.PlanPeriod],
        plans: List[models.Plan]
    ) -> List[PeriodStatistics]:
        """Berechnet Statistiken pro Planperiode"""
        
        period_stats = []
        
        for plan_period in plan_periods:
            # Finde den entsprechenden Plan
            plan = next((p for p in plans if p.plan_period == plan_period), None)
            if not plan:
                continue
                
            # Zähle Appointments in diesem Plan
            appointments = select(
                a for a in models.Appointment
                if a.plan == plan and not a.prep_delete
            )
            
            # Sammle eindeutige Mitarbeiter und Standorte
            employees = set()
            locations = set()
            
            for appointment in appointments:
                for avail_day in appointment.avail_days:
                    employees.add(avail_day.actor_plan_period.person.id)
                locations.add(appointment.event.location_plan_period.location_of_work.id)
            
            period_stats.append(PeriodStatistics(
                period_name=f"{plan_period.start} - {plan_period.end}",
                period_start=plan_period.start,
                period_end=plan_period.end,
                total_assignments=len(list(appointments)),
                employees_count=len(employees),
                locations_count=len(locations)
            ))
            
        # Sortiere nach Startdatum
        period_stats.sort(key=lambda x: x.period_start)
        return period_stats

    @classmethod
    def _create_empty_statistics(
        cls,
        team_name: Optional[str],
        project_name: str,
        start_date: datetime.date,
        end_date: datetime.date
    ) -> EmploymentStatistics:
        """Erstellt leere Statistiken wenn keine Daten vorhanden"""
        
        return EmploymentStatistics(
            team_name=team_name,
            project_name=project_name,
            start_date=start_date,
            end_date=end_date,
            total_assignments=0,
            total_employees=0,
            total_locations=0,
            employee_statistics=[],
            location_statistics=[],
            period_statistics=[],
            average_assignments_per_employee=0.0,
            average_assignments_per_period=0.0
        )

    @classmethod
    @db_session
    def get_available_teams_for_project(cls, project_id: UUID) -> List[Tuple[UUID, str]]:
        """Liefert verfügbare Teams für ein Projekt"""
        teams = select(
            t for t in models.Team
            if t.project.id == project_id and not t.prep_delete
        ).order_by(models.Team.name)
        
        return [(team.id, team.name) for team in teams]

    @classmethod
    @db_session
    def get_date_range_for_context(
        cls,
        team_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None
    ) -> Tuple[Optional[datetime.date], Optional[datetime.date]]:
        """Ermittelt den verfügbaren Datumsbereich für Team oder Projekt"""
        
        if team_id:
            plan_periods = select(
                pp for pp in models.PlanPeriod
                if pp.team.id == team_id and not pp.prep_delete
            )
        elif project_id:
            plan_periods = select(
                pp for pp in models.PlanPeriod
                if pp.team.project.id == project_id and not pp.prep_delete
            )
        else:
            return None, None
            
        if not plan_periods:
            return None, None
            
        min_date = min(pp.start for pp in plan_periods)
        max_date = max(pp.end for pp in plan_periods)
        
        return min_date, max_date
