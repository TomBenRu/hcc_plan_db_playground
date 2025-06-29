"""
SATSolver - Hauptklasse für SAT-Solving-Operationen

Diese Klasse orchestriert den gesamten Solving-Prozess mit der neuen
Constraint-basierten Architektur.
"""

import time
import logging
from typing import List, Dict, Optional, Tuple
from uuid import UUID

from ortools.sat.python import cp_model
from ortools.sat.cp_model_pb2 import CpSolverStatus

from sat_solver.core.solver_context import SolverContext
from sat_solver.core.entities import Entities
from sat_solver.core.solver_config import SolverConfig
from sat_solver.constraints.constraint_factory import ConstraintFactory
from sat_solver.solving.objectives import ObjectiveBuilder
from sat_solver.solving.callbacks import PartialSolutionCallback
from sat_solver.core.solver_result import SolverResult
from sat_solver.results.result_processor import ResultProcessor

from sat_solver.avail_day_group_tree import get_avail_day_group_tree
from sat_solver.event_group_tree import get_event_group_tree
from sat_solver.cast_group_tree import get_cast_group_tree
from database import db_services


logger = logging.getLogger(__name__)


class SATSolver:
    """
    Hauptklasse für SAT-Solving-Operationen.
    
    Diese Klasse orchestriert den gesamten Solving-Prozess:
    1. Setup des SolverContext
    2. Erstellung und Setup aller Constraints
    3. Definition der Zielfunktion
    4. Ausführung des Solving
    5. Verarbeitung der Ergebnisse
    """
    
    def __init__(self, plan_period_id: UUID, config: Optional[SolverConfig] = None):
        """
        Initialisiert den SAT-Solver.
        
        Args:
            plan_period_id: UUID der zu lösenden Plan-Periode
            config: Optionale Konfiguration (verwendet Standard falls None)
        """
        self.plan_period_id = plan_period_id
        self.config = config or SolverConfig.from_current_config()
        
        # Initialisiere Komponenten
        self.context: Optional[SolverContext] = None
        self.constraints: List = []
        self.objective_builder: Optional[ObjectiveBuilder] = None
        self.result_processor: Optional[ResultProcessor] = None
        
        # Solver-Status
        self.is_setup_complete = False
        self.last_solve_status: Optional[CpSolverStatus] = None
        self.solve_statistics: Dict = {}
        
        logger.info(f"SATSolver initialized for plan period {plan_period_id}")
    
    def setup(self) -> bool:
        """
        Führt das komplette Setup des Solvers durch.
        
        Returns:
            True wenn Setup erfolgreich, False bei Fehlern
        """
        try:
            logger.info("Starting SAT-Solver setup...")
            
            # 1. Erstelle und lade Datenstrukturen
            if not self._setup_data_structures():
                return False
            
            # 2. Erstelle SolverContext
            if not self._setup_solver_context():
                return False
            
            # 3. Erstelle und setup alle Constraints
            if not self._setup_constraints():
                return False
            
            # 4. Erstelle ObjectiveBuilder
            if not self._setup_objective_builder():
                return False
            
            # 5. Erstelle ResultProcessor
            if not self._setup_result_processor():
                return False
            
            self.is_setup_complete = True
            logger.info("SAT-Solver setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"SAT-Solver setup failed: {e}")
            self.is_setup_complete = False
            return False
    
    def solve(self, max_time_seconds: int = 60, 
              collect_multiple_solutions: bool = False,
              solution_limit: Optional[int] = None) -> 'SolverResult':
        """
        Führt das SAT-Solving durch.
        
        Args:
            max_time_seconds: Maximale Solving-Zeit in Sekunden
            collect_multiple_solutions: Ob mehrere Lösungen gesammelt werden sollen
            solution_limit: Maximale Anzahl Lösungen (None = unbegrenzt)
            
        Returns:
            SolverResult mit Ergebnissen und Statistiken
        """
        if not self.is_setup_complete:
            raise RuntimeError("Solver setup not completed. Call setup() first.")
        
        logger.info(f"Starting SAT-Solving (max_time={max_time_seconds}s)")
        
        # Update Solver-Parameter
        self.config.solver_parameters.max_time_in_seconds = max_time_seconds
        self.config.solver_parameters.solution_limit = solution_limit
        
        # Definiere Zielfunktion
        self.objective_builder.build_minimize_objective()
        
        # Erstelle CP-SAT Solver
        solver = cp_model.CpSolver()
        self._configure_solver(solver)
        
        start_time = time.time()
        
        if collect_multiple_solutions:
            # Solving mit Solution Callback für mehrere Lösungen
            callback = self._create_solution_callback()
            status = solver.Solve(self.context.model, callback)
            solutions = callback.get_schedule_versions() if callback else []
        else:
            # Einfaches Solving für eine optimale Lösung
            callback = None
            status = solver.Solve(self.context.model)
            solutions = []
        
        solve_time = time.time() - start_time
        
        # Speichere Solving-Statistiken
        self.last_solve_status = status
        self.solve_statistics = {
            'status': status,
            'solve_time': solve_time,
            'objective_value': solver.ObjectiveValue() if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else None,
            'num_conflicts': solver.NumConflicts(),
            'num_branches': solver.NumBranches(),
            'wall_time': solver.WallTime(),
            'solution_count': callback.solution_count() if callback else 1
        }
        
        logger.info(f"SAT-Solving completed in {solve_time:.2f}s with status: {self._status_to_string(status)}")
        
        # Verarbeite Ergebnisse
        return self.result_processor.process_results(solver, callback, status, self.solve_statistics)
    
    def get_setup_summary(self) -> Dict:
        """
        Gibt eine Zusammenfassung des Setup-Status zurück.
        
        Returns:
            Dictionary mit Setup-Informationen
        """
        return {
            'is_setup_complete': self.is_setup_complete,
            'plan_period_id': str(self.plan_period_id),
            'context_valid': self.context.is_valid() if self.context else False,
            'constraints_count': len(self.constraints),
            'constraints_setup': [c.is_setup_complete() for c in self.constraints],
            'model_variables': self.context.model.NumVariables() if self.context else 0,
            'model_constraints': self.context.model.NumConstraints() if self.context else 0,
            'config_summary': self.config.to_dict()
        }
    
    def get_solve_statistics(self) -> Dict:
        """
        Gibt die Statistiken des letzten Solve-Vorgangs zurück.
        
        Returns:
            Dictionary mit Solve-Statistiken
        """
        return self.solve_statistics.copy()
    
    def _setup_data_structures(self) -> bool:
        """Setup der Datenstrukturen (Trees und Entities)."""
        try:
            logger.debug("Setting up data structures...")
            
            # Lade Tree-Strukturen
            self.event_group_tree = get_event_group_tree(self.plan_period_id)
            self.avail_day_group_tree = get_avail_day_group_tree(self.plan_period_id)
            self.cast_group_tree = get_cast_group_tree(self.plan_period_id)
            
            logger.debug("Data structures loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup data structures: {e}")
            return False
    
    def _setup_solver_context(self) -> bool:
        """Setup des SolverContext."""
        try:
            logger.debug("Setting up solver context...")
            
            # Erstelle Entities und fülle mit Daten
            entities = Entities()
            self._populate_entities(entities)
            
            # Erstelle CP-Model
            model = cp_model.CpModel()
            
            # Erstelle SolverContext
            self.context = SolverContext(
                entities=entities,
                model=model,
                config=self.config,
                plan_period_id=self.plan_period_id
            )
            
            # Erstelle Variablen
            self._create_variables()
            
            logger.debug("Solver context setup completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup solver context: {e}")
            return False
    
    def _populate_entities(self, entities: Entities) -> None:
        """Füllt die Entities mit Daten aus den Tree-Strukturen."""
        # Plan Period und Actor Plan Periods laden
        plan_period = db_services.PlanPeriod.get(self.plan_period_id)
        entities.actor_plan_periods = {
            app.id: db_services.ActorPlanPeriod.get(app.id)
            for app in plan_period.actor_plan_periods
        }
        
        # Event Groups
        entities.event_groups = {
            eg.event_group_id: eg for eg in self.event_group_tree.root.descendants
            if eg.children or eg.event
        }
        entities.event_groups[self.event_group_tree.root.event_group_id] = self.event_group_tree.root
        
        entities.event_groups_with_event = {
            leaf.event_group_id: leaf for leaf in self.event_group_tree.root.leaves
            if leaf.event
        }
        
        # Avail Day Groups
        entities.avail_day_groups = {
            adg.avail_day_group_id: adg for adg in self.avail_day_group_tree.root.descendants
            if adg.children or adg.avail_day
        }
        entities.avail_day_groups[self.avail_day_group_tree.root.avail_day_group_id] = self.avail_day_group_tree.root
        
        entities.avail_day_groups_with_avail_day = {
            leaf.avail_day_group_id: leaf for leaf in self.avail_day_group_tree.root.leaves
            if leaf.avail_day
        }
        
        # Cast Groups
        entities.cast_groups = {
            self.cast_group_tree.root.cast_group_id: self.cast_group_tree.root
        }
        entities.cast_groups.update({
            cg.cast_group_id: cg for cg in self.cast_group_tree.root.descendants
        })
        
        entities.cast_groups_with_event = {
            cg.cast_group_id: cg for cg in self.cast_group_tree.root.leaves
            if cg.event
        }
    
    def _create_variables(self) -> None:
        """Erstellt alle Solver-Variablen."""
        entities = self.context.entities
        
        # Event Group Variables
        entities.event_group_vars = {
            eg.event_group_id: self.context.model.NewBoolVar(f'event_group_{eg.event_group_id}')
            for eg in self.event_group_tree.root.descendants
            if eg.children or eg.event
        }
        
        # Avail Day Group Variables
        entities.avail_day_group_vars = {
            adg.avail_day_group_id: self.context.model.NewBoolVar(f'avail_day_group_{adg.avail_day_group_id}')
            for adg in self.avail_day_group_tree.root.descendants
            if adg.children or adg.avail_day
        }
        
        # Shift Variables
        from solver_main import check_time_span_avail_day_fits_event  # Import der Helper-Funktion
        
        for adg_id, adg in entities.avail_day_groups_with_avail_day.items():
            for event_group_id, event_group in entities.event_groups_with_event.items():
                location_of_work = event_group.event.location_plan_period.location_of_work
                
                # Bestimme ob Shift möglich ist
                entities.shifts_exclusive[adg_id, event_group_id] = 1
                
                # Prüfe Actor-Location-Preference Score
                if found_alf := next((alf for alf in adg.avail_day.actor_location_prefs_defaults
                                     if alf.location_of_work.id == location_of_work.id), None):
                    if found_alf.score == 0:
                        entities.shifts_exclusive[adg_id, event_group_id] = 0
                
                # Prüfe Zeitfenster-Kompatibilität
                if not check_time_span_avail_day_fits_event(event_group.event, adg.avail_day):
                    entities.shifts_exclusive[adg_id, event_group_id] = 0
                
                # Erstelle Shift Variable
                var_name = (f'shift_{adg.avail_day.actor_plan_period.person.f_name}_'
                           f'{adg.avail_day.date:%d%m%y}_{event_group_id}')
                
                entities.shift_vars[(adg_id, event_group_id)] = self.context.model.NewBoolVar(var_name)
    
    def _setup_constraints(self) -> bool:
        """Setup aller Constraints."""
        try:
            logger.debug("Setting up constraints...")
            
            # Erstelle alle Constraints über Factory
            self.constraints, setup_results = ConstraintFactory.create_and_setup_all(self.context)
            
            # Prüfe Setup-Erfolg
            failed_constraints = [name for name, success in setup_results.items() if not success]
            if failed_constraints:
                logger.warning(f"Failed to setup constraints: {failed_constraints}")
                return False
            
            logger.debug(f"Successfully setup {len(self.constraints)} constraints")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup constraints: {e}")
            return False
    
    def _setup_objective_builder(self) -> bool:
        """Setup des ObjectiveBuilder."""
        try:
            self.objective_builder = ObjectiveBuilder(self.context)
            logger.debug("ObjectiveBuilder setup completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup ObjectiveBuilder: {e}")
            return False
    
    def _setup_result_processor(self) -> bool:
        """Setup des ResultProcessor."""
        try:
            self.result_processor = ResultProcessor(self.context)
            logger.debug("ResultProcessor setup completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup ResultProcessor: {e}")
            return False
    
    def _configure_solver(self, solver: cp_model.CpSolver) -> None:
        """Konfiguriert den CP-SAT Solver."""
        params = self.config.solver_parameters
        
        solver.parameters.max_time_in_seconds = params.max_time_in_seconds
        solver.parameters.log_search_progress = params.log_search_progress
        solver.parameters.randomize_search = params.randomize_search
        solver.parameters.linearization_level = params.linearization_level
        solver.parameters.enumerate_all_solutions = params.enumerate_all_solutions
    
    def _create_solution_callback(self) -> Optional[PartialSolutionCallback]:
        """Erstellt Solution Callback für mehrere Lösungen."""
        try:
            # Hole notwendige Constraint-Variablen
            unassigned_shifts = self.context.get_constraint_vars("unassigned_shifts")
            sum_assigned_shifts = self.context.get_constraint_vars("sum_assigned_shifts")
            sum_squared_deviations = self.context.get_constraint_vars("sum_squared_deviations")
            fixed_cast_conflicts = self.context.get_constraint_vars("fixed_cast")
            
            return PartialSolutionCallback(
                unassigned_shifts_per_event=unassigned_shifts,
                sum_assigned_shifts=sum_assigned_shifts,
                sum_squared_deviations=sum_squared_deviations[0] if sum_squared_deviations else None,
                fixed_cast_conflicts=fixed_cast_conflicts,
                limit=self.config.solver_parameters.solution_limit,
                print_results=self.config.solver_parameters.log_search_progress,
                collect_schedule_versions=True
            )
            
        except Exception as e:
            logger.error(f"Failed to create solution callback: {e}")
            return None
    
    def _status_to_string(self, status: CpSolverStatus) -> str:
        """Konvertiert Solver-Status zu lesbarem String."""
        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE", 
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
            cp_model.UNKNOWN: "UNKNOWN"
        }
        return status_map.get(status, f"UNKNOWN_STATUS_{status}")
