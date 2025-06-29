"""
ResultProcessor - Verarbeitung von SAT-Solver Ergebnissen

Diese Klasse verarbeitet die Ergebnisse des SAT-Solvers und konvertiert
sie in verwendbare Datenstrukturen.
"""

import logging
from typing import List, Dict, Optional, Any
from uuid import UUID

from ortools.sat.python import cp_model
from ortools.sat.cp_model_pb2 import CpSolverStatus

from sat_solver.core.solver_context import SolverContext
from sat_solver.solving.callbacks import PartialSolutionCallback
from sat_solver.core.solver_result import SolverResult
from database import schemas


logger = logging.getLogger(__name__)


class ResultProcessor:
    """
    Processor für SAT-Solver Ergebnisse.
    
    Diese Klasse konvertiert die Solver-Ergebnisse in strukturierte
    Datenformate und extrahiert relevante Informationen.
    """
    
    def __init__(self, context: SolverContext):
        """
        Initialisiert den ResultProcessor.
        
        Args:
            context: Der SolverContext mit allen Daten
        """
        self.context = context
        self.entities = context.entities
        
        logger.debug("ResultProcessor initialized")
    
    def process_results(self, 
                       solver: cp_model.CpSolver,
                       callback: Optional[PartialSolutionCallback],
                       status: CpSolverStatus,
                       statistics: Dict[str, Any]) -> SolverResult:
        """
        Verarbeitet die Solver-Ergebnisse zu einem SolverResult.
        
        Args:
            solver: Der CP-SAT Solver nach dem Solving
            callback: Optional Solution Callback mit Zwischenergebnissen
            status: Status des Solving-Prozesses
            statistics: Solving-Statistiken
            
        Returns:
            SolverResult mit allen Ergebnissen
        """
        try:
            logger.debug("Processing solver results...")
            
            # Grundlegende Status-Informationen
            is_optimal = status == cp_model.OPTIMAL
            is_feasible = status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
            
            # Objective Value
            objective_value = None
            if is_feasible:
                objective_value = solver.ObjectiveValue()
            
            # Haupt-Lösung extrahieren
            appointments = []
            if is_feasible:
                appointments = self._extract_appointments(solver)
            
            # Mehrere Lösungen von Callback
            solutions = []
            if callback and callback.get_schedule_versions():
                solutions = callback.get_schedule_versions()
            
            # Constraint-Werte extrahieren
            constraint_values = self._extract_constraint_values(solver) if is_feasible else {}
            
            result = SolverResult(
                status=status,
                is_optimal=is_optimal,
                is_feasible=is_feasible,
                objective_value=objective_value,
                solve_time=statistics.get('solve_time', 0.0),
                statistics=statistics,
                appointments=appointments,
                solutions=solutions,
                constraint_values=constraint_values
            )
            
            logger.info(f"Results processed: {len(appointments)} appointments, "
                       f"status={self._status_to_string(status)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process results: {e}")
            # Return error result
            return SolverResult(
                status=status,
                is_optimal=False,
                is_feasible=False,
                objective_value=None,
                solve_time=statistics.get('solve_time', 0.0),
                statistics=statistics,
                appointments=[],
                solutions=[],
                constraint_values={}
            )
    
    def _extract_appointments(self, solver: cp_model.CpSolver) -> List[schemas.AppointmentCreate]:
        """
        Extrahiert Appointments aus der Solver-Lösung.
        
        Args:
            solver: Der gelöste CP-SAT Solver
            
        Returns:
            Liste der AppointmentCreate-Objekte
        """
        appointments = []
        
        try:
            # Gruppiere Shifts nach Event Groups
            event_group_assignments = {}
            
            for (adg_id, eg_id), shift_var in self.entities.shift_vars.items():
                # Prüfe ob Event Group aktiv ist
                if eg_id in self.entities.event_group_vars:
                    event_active = solver.Value(self.entities.event_group_vars[eg_id])
                    if not event_active:
                        continue
                
                # Prüfe ob Shift zugewiesen ist
                shift_assigned = solver.Value(shift_var)
                if not shift_assigned:
                    continue
                
                # Sammle Zuweisungen pro Event Group
                if eg_id not in event_group_assignments:
                    event_group_assignments[eg_id] = []
                event_group_assignments[eg_id].append(adg_id)
            
            # Erstelle Appointments
            for eg_id, assigned_adg_ids in event_group_assignments.items():
                if eg_id not in self.entities.event_groups_with_event:
                    continue
                
                event_group = self.entities.event_groups_with_event[eg_id]
                event = event_group.event
                
                # Sammle AvailDays
                avail_days = []
                for adg_id in assigned_adg_ids:
                    if adg_id in self.entities.avail_day_groups_with_avail_day:
                        adg = self.entities.avail_day_groups_with_avail_day[adg_id]
                        avail_days.append(adg.avail_day)
                
                if avail_days:
                    appointment = schemas.AppointmentCreate(
                        avail_days=avail_days,
                        event=event
                    )
                    appointments.append(appointment)
            
            logger.debug(f"Extracted {len(appointments)} appointments")
            
        except Exception as e:
            logger.error(f"Failed to extract appointments: {e}")
        
        return appointments
    
    def _extract_constraint_values(self, solver: cp_model.CpSolver) -> Dict[str, Any]:
        """
        Extrahiert Werte aller Constraint-Variablen.
        
        Args:
            solver: Der gelöste CP-SAT Solver
            
        Returns:
            Dictionary mit Constraint-Werten
        """
        constraint_values = {}
        
        try:
            # Iteriere über alle registrierten Constraints
            for constraint_name in self.context.get_all_constraint_names():
                constraint_vars = self.context.get_constraint_vars(constraint_name)
                
                if not constraint_vars:
                    continue
                
                # Extrahiere Werte
                if len(constraint_vars) == 1:
                    # Einzelner Wert
                    constraint_values[constraint_name] = solver.Value(constraint_vars[0])
                else:
                    # Liste von Werten
                    constraint_values[constraint_name] = [
                        solver.Value(var) for var in constraint_vars
                    ]
                    
                    # Zusätzliche Aggregationen
                    values = constraint_values[constraint_name]
                    constraint_values[f"{constraint_name}_sum"] = sum(values)
                    constraint_values[f"{constraint_name}_count"] = len(values)
                    if values:
                        constraint_values[f"{constraint_name}_avg"] = sum(values) / len(values)
                        constraint_values[f"{constraint_name}_max"] = max(values)
                        constraint_values[f"{constraint_name}_min"] = min(values)
            
            logger.debug(f"Extracted values for {len(constraint_values)} constraint types")
            
        except Exception as e:
            logger.error(f"Failed to extract constraint values: {e}")
        
        return constraint_values
    
    def extract_employee_assignments(self, solver: cp_model.CpSolver) -> Dict[UUID, List[Dict]]:
        """
        Extrahiert Zuweisungen pro Mitarbeiter.
        
        Args:
            solver: Der gelöste CP-SAT Solver
            
        Returns:
            Dictionary {app_id: [assignment_details]}
        """
        employee_assignments = {}
        
        try:
            for app_id, app in self.entities.actor_plan_periods.items():
                assignments = []
                
                # Finde alle Zuweisungen für diesen Mitarbeiter
                for (adg_id, eg_id), shift_var in self.entities.shift_vars.items():
                    # Prüfe ob dies der richtige Mitarbeiter ist
                    if adg_id not in self.entities.avail_day_groups_with_avail_day:
                        continue
                    
                    adg = self.entities.avail_day_groups_with_avail_day[adg_id]
                    if adg.avail_day.actor_plan_period.id != app_id:
                        continue
                    
                    # Prüfe ob zugewiesen
                    if not solver.Value(shift_var):
                        continue
                    
                    # Prüfe ob Event aktiv
                    if eg_id in self.entities.event_group_vars:
                        if not solver.Value(self.entities.event_group_vars[eg_id]):
                            continue
                    
                    # Sammle Assignment-Details
                    if eg_id in self.entities.event_groups_with_event:
                        event_group = self.entities.event_groups_with_event[eg_id]
                        event = event_group.event
                        
                        assignment = {
                            'date': event.date,
                            'time': event.time_of_day.name,
                            'location': event.location_plan_period.location_of_work.name,
                            'event_id': str(event.id),
                            'adg_id': str(adg_id),
                            'eg_id': str(eg_id)
                        }
                        assignments.append(assignment)
                
                employee_assignments[app_id] = assignments
            
            logger.debug(f"Extracted assignments for {len(employee_assignments)} employees")
            
        except Exception as e:
            logger.error(f"Failed to extract employee assignments: {e}")
        
        return employee_assignments
    
    def extract_location_utilization(self, solver: cp_model.CpSolver) -> Dict[str, Dict]:
        """
        Extrahiert Auslastung pro Location.
        
        Args:
            solver: Der gelöste CP-SAT Solver
            
        Returns:
            Dictionary mit Location-Auslastungs-Daten
        """
        location_utilization = {}
        
        try:
            # Sammle Events pro Location
            for eg_id, event_group in self.entities.event_groups_with_event.items():
                event = event_group.event
                location_name = event.location_plan_period.location_of_work.name
                
                # Prüfe ob Event aktiv
                is_active = False
                if eg_id in self.entities.event_group_vars:
                    is_active = solver.Value(self.entities.event_group_vars[eg_id])
                
                if location_name not in location_utilization:
                    location_utilization[location_name] = {
                        'total_events': 0,
                        'active_events': 0,
                        'total_assignments': 0,
                        'event_details': []
                    }
                
                location_data = location_utilization[location_name]
                location_data['total_events'] += 1
                
                if is_active:
                    location_data['active_events'] += 1
                    
                    # Zähle Zuweisungen für dieses Event
                    assignments_count = 0
                    assigned_employees = []
                    
                    for (adg_id, check_eg_id), shift_var in self.entities.shift_vars.items():
                        if check_eg_id == eg_id and solver.Value(shift_var):
                            assignments_count += 1
                            
                            if adg_id in self.entities.avail_day_groups_with_avail_day:
                                adg = self.entities.avail_day_groups_with_avail_day[adg_id]
                                assigned_employees.append(adg.avail_day.actor_plan_period.person.f_name)
                    
                    location_data['total_assignments'] += assignments_count
                    location_data['event_details'].append({
                        'date': event.date.strftime('%Y-%m-%d'),
                        'time': event.time_of_day.name,
                        'assignments_count': assignments_count,
                        'assigned_employees': assigned_employees
                    })
            
            logger.debug(f"Extracted utilization for {len(location_utilization)} locations")
            
        except Exception as e:
            logger.error(f"Failed to extract location utilization: {e}")
        
        return location_utilization
    
    def _status_to_string(self, status: CpSolverStatus) -> str:
        """Konvertiert Solver-Status zu String."""
        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE", 
            cp_model.MODEL_INVALID: "MODEL_INVALID",
            cp_model.UNKNOWN: "UNKNOWN"
        }
        return status_map.get(status, f"UNKNOWN_STATUS_{status}")
    
    def create_summary_report(self, result: SolverResult) -> Dict[str, Any]:
        """
        Erstellt einen umfassenden Summary-Report.
        
        Args:
            result: Das SolverResult-Objekt
            
        Returns:
            Dictionary mit Summary-Report
        """
        try:
            report = {
                'solving_summary': {
                    'status': self._status_to_string(result.status),
                    'success': result.success,
                    'is_optimal': result.is_optimal,
                    'objective_value': result.objective_value,
                    'solve_time_seconds': result.solve_time,
                    'total_appointments': len(result.appointments),
                    'total_solutions': len(result.solutions)
                },
                'constraint_summary': {},
                'entity_summary': self.context.entities.get_summary(),
                'model_summary': {
                    'variables': self.context.model.NumVariables(),
                    'constraints': self.context.model.NumConstraints()
                },
                'performance_summary': result.statistics
            }
            
            # Constraint-spezifische Summaries
            if result.constraint_values:
                for constraint_name, values in result.constraint_values.items():
                    if not constraint_name.endswith(('_sum', '_count', '_avg', '_max', '_min')):
                        if isinstance(values, list):
                            report['constraint_summary'][constraint_name] = {
                                'total': len(values),
                                'sum': sum(values),
                                'nonzero': sum(1 for v in values if v != 0)
                            }
                        else:
                            report['constraint_summary'][constraint_name] = values
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to create summary report: {e}")
            return {'error': str(e)}
