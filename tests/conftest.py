"""
pytest Konfiguration und gemeinsame Fixtures für SAT-Solver Tests
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import date, time, datetime
import logging

# Test-Framework imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sat_solver.core.solver_context import SolverContext
from sat_solver.core.entities import Entities
from sat_solver.core.solver_config import SolverConfig
from sat_solver.core.solver_result import SolverResult
from database import schemas


class MockCpVariable:
    """Mock-Klasse für CP-Model Variablen mit Arithmetik-Support."""
    
    def __init__(self, name="mock_var", lb=0, ub=100):
        self.name = name
        self.lb = lb
        self.ub = ub
        self._value = None
    
    def __add__(self, other):
        if isinstance(other, (int, float)):
            result = MockCpVariable(f"({self.name} + {other})")
            return result
        elif isinstance(other, MockCpVariable):
            result = MockCpVariable(f"({self.name} + {other.name})")
            return result
        return MockCpExpression([self, '+', other])
    
    def __radd__(self, other):
        return self.__add__(other)
    
    def __sub__(self, other):
        if isinstance(other, (int, float)):
            result = MockCpVariable(f"({self.name} - {other})")
            return result
        elif isinstance(other, MockCpVariable):
            result = MockCpVariable(f"({self.name} - {other.name})")
            return result
        return MockCpExpression([self, '-', other])
    
    def __rsub__(self, other):
        if isinstance(other, (int, float)):
            result = MockCpVariable(f"({other} - {self.name})")
            return result
        return MockCpExpression([other, '-', self])
    
    def __mul__(self, other):
        if isinstance(other, (int, float)):
            result = MockCpVariable(f"({self.name} * {other})")
            return result
        elif isinstance(other, MockCpVariable):
            result = MockCpVariable(f"({self.name} * {other.name})")
            return result
        return MockCpExpression([self, '*', other])
    
    def __rmul__(self, other):
        return self.__mul__(other)
    
    def __eq__(self, other):
        return MockCpConstraint(f"{self.name} == {other}")
    
    def __le__(self, other):
        return MockCpConstraint(f"{self.name} <= {other}")
    
    def __ge__(self, other):
        return MockCpConstraint(f"{self.name} >= {other}")
    
    def __repr__(self):
        return f"MockCpVariable({self.name})"


class MockCpExpression:
    """Mock-Klasse für CP-Model Ausdrücke."""
    
    def __init__(self, expression):
        self.expression = expression
    
    def __add__(self, other):
        return MockCpExpression([self, '+', other])
    
    def __radd__(self, other):
        return MockCpExpression([other, '+', self])
    
    def __sub__(self, other):
        return MockCpExpression([self, '-', other])
    
    def __rsub__(self, other):
        return MockCpExpression([other, '-', self])
    
    def __mul__(self, other):
        return MockCpExpression([self, '*', other])
    
    def __rmul__(self, other):
        return MockCpExpression([other, '*', self])
    
    def __eq__(self, other):
        return MockCpConstraint(f"{self} == {other}")
    
    def __le__(self, other):
        return MockCpConstraint(f"{self} <= {other}")
    
    def __ge__(self, other):
        return MockCpConstraint(f"{self} >= {other}")
    
    def __repr__(self):
        return f"MockCpExpression({self.expression})"


class MockCpConstraint:
    """Mock-Klasse für CP-Model Constraints."""
    
    def __init__(self, constraint_str):
        self.constraint_str = constraint_str
    
    def __repr__(self):
        return f"MockCpConstraint({self.constraint_str})"


class MockCpModel:
    """Vollständige Mock-Klasse für CP-Model."""
    
    def __init__(self):
        self.variables = []
        self.constraints = []
        self.objectives = []
        self._var_counter = 0
        
        # Mock für alle wichtigen CP-Model Methoden
        self.NewIntVar = Mock(side_effect=self._create_new_int_var)
        self.NewBoolVar = Mock(side_effect=self._create_new_bool_var)
        self.Add = Mock(side_effect=self._add_constraint)
        self.AddAbsEquality = Mock(side_effect=self._add_constraint)
        self.AddDivisionEquality = Mock(side_effect=self._add_constraint)
        self.AddMultiplicationEquality = Mock(side_effect=self._add_constraint)
        self.Minimize = Mock(side_effect=self._add_objective)
        self.Maximize = Mock(side_effect=self._add_objective)
        
        # Sum-Methode für Variablen-Listen
        self.Sum = Mock(side_effect=self._sum_variables)
    
    def _create_new_int_var(self, lb, ub, name=""):
        """Erstellt eine neue Integer-Variable."""
        self._var_counter += 1
        var_name = name or f"var_{self._var_counter}"
        var = MockCpVariable(var_name, lb, ub)
        self.variables.append(var)
        return var
    
    def _create_new_bool_var(self, name=""):
        """Erstellt eine neue Boolean-Variable."""
        self._var_counter += 1
        var_name = name or f"bool_var_{self._var_counter}"
        var = MockCpVariable(var_name, 0, 1)
        self.variables.append(var)
        return var
    
    def _add_constraint(self, *args):
        """Fügt ein Constraint hinzu (flexible Parameter)."""
        constraint = args[0] if args else None
        self.constraints.append(constraint)
        return constraint
    
    def _add_objective(self, objective):
        """Fügt ein Objective hinzu."""
        self.objectives.append(objective)
        return objective
    
    def _sum_variables(self, variables):
        """Summiert eine Liste von Variablen."""
        if not variables:
            return MockCpExpression([])
        if len(variables) == 1:
            return variables[0]
        
        # Erstelle Summen-Expression
        sum_expr = variables[0]
        for var in variables[1:]:
            sum_expr = sum_expr + var
        return sum_expr
    
    def get_stats(self):
        """Gibt Statistiken über das Modell zurück."""
        return {
            'variables': len(self.variables),
            'constraints': len(self.constraints),
            'objectives': len(self.objectives)
        }


@pytest.fixture
def mock_plan_period_id():
    """Fixture für eine Test-Plan-Period-UUID."""
    return uuid4()


@pytest.fixture
def mock_model():
    """Fixture für ein vollständiges Mock CP-Model."""
    return MockCpModel()


@pytest.fixture
def sample_entities():
    """Fixture für Test-Entities mit Beispieldaten."""
    entities = Entities()
    
    # Mock Actor Plan Periods
    entities.actor_plan_periods = {
        uuid4(): create_mock_actor_plan_period("Alice", 10),
        uuid4(): create_mock_actor_plan_period("Bob", 8),
        uuid4(): create_mock_actor_plan_period("Charlie", 12)
    }
    
    # Mock Event Groups
    entities.event_groups = {
        uuid4(): create_mock_event_group("Event Group 1"),
        uuid4(): create_mock_event_group("Event Group 2")
    }
    
    # Mock Event Groups with Events
    entities.event_groups_with_event = {
        uuid4(): create_mock_event_group_with_event("Event Group 1"),
        uuid4(): create_mock_event_group_with_event("Event Group 2")
    }
    
    # Mock Avail Day Groups
    entities.avail_day_groups = {
        uuid4(): create_mock_avail_day_group("AvailDay Group 1"),
        uuid4(): create_mock_avail_day_group("AvailDay Group 2")
    }
    
    # Mock Avail Day Groups with Avail Days
    entities.avail_day_groups_with_avail_day = {
        uuid4(): create_mock_avail_day_group_with_avail_day("AvailDay Group 1"),
        uuid4(): create_mock_avail_day_group_with_avail_day("AvailDay Group 2")
    }
    
    # Initialize other required entities (required for validate_context)
    entities.shift_vars = {}
    entities.event_group_vars = {}
    entities.shifts_exclusive = {}
    entities.cast_groups = {}  # Für is_initialized()
    entities.location_plan_periods = {}  # Für is_initialized()
    entities.avail_days = {}  # Für is_initialized()
    entities.events = {}  # Für is_initialized()
    entities.projects = {}  # Für is_initialized()
    entities.plan_periods = {}  # Für is_initialized()
    entities.teams = {}  # Für is_initialized()
    entities.locations_of_work = {}  # Für is_initialized()
    entities.time_of_days = {}  # Für is_initialized()
    
    return entities


@pytest.fixture
def sample_solver_config():
    """Fixture für Test-SolverConfig."""
    from sat_solver.core.solver_config import SolverParameters
    
    # Erstelle SolverParameters mit korrekten Parameter-Namen
    solver_params = SolverParameters(
        max_time_in_seconds=30,
        log_search_progress=False,
        randomize_search=True
    )
    
    # Erstelle SolverConfig mit SolverParameters
    return SolverConfig(solver_parameters=solver_params)


@pytest.fixture
def mock_solver_context(mock_plan_period_id, mock_model, sample_entities, sample_solver_config):
    """Fixture für einen Mock SolverContext."""
    context = SolverContext(
        entities=sample_entities,
        model=mock_model,
        config=sample_solver_config,
        plan_period_id=mock_plan_period_id
    )
    
    # Mock logger falls benötigt
    if not hasattr(context, 'logger'):
        context.logger = logging.getLogger('test_logger')
    
    return context


@pytest.fixture
def sample_solver_result():
    """Fixture für ein Test-SolverResult."""
    # Import hier um zirkuläre Imports zu vermeiden
    from ortools.sat.python import cp_model
    
    return SolverResult(
        status=cp_model.OPTIMAL,
        is_optimal=True,
        is_feasible=True,
        objective_value=42.0,
        solve_time=1.5,
        statistics={'conflicts': 0, 'branches': 10},
        appointments=[],
        solutions=[],
        constraint_values={'unassigned_shifts': 0}
    )


# Helper-Funktionen für Mock-Objekte
def create_mock_actor_plan_period(name: str, requested_assignments: int):
    """Erstellt ein Mock ActorPlanPeriod."""
    mock_person = Mock()
    mock_person.f_name = name
    mock_person.full_name = f"Full {name}"
    
    mock_app = Mock()
    mock_app.id = uuid4()
    mock_app.person = mock_person
    mock_app.requested_assignments = requested_assignments
    mock_app.required_assignments = False
    
    return mock_app


def create_mock_event_group(name: str):
    """Erstellt ein Mock EventGroup."""
    mock_eg = Mock()
    mock_eg.event_group_id = uuid4()
    mock_eg.name = name
    mock_eg.children = []
    mock_eg.event = None
    mock_eg.nr_of_active_children = None
    mock_eg.is_root = False
    mock_eg.weight = 1
    
    return mock_eg


def create_mock_event_group_with_event(name: str):
    """Erstellt ein Mock EventGroup mit detailliertem Event."""
    mock_eg = Mock()
    mock_eg.event_group_id = uuid4()
    mock_eg.name = name
    mock_eg.children = []
    mock_eg.nr_of_active_children = None
    mock_eg.is_root = False
    mock_eg.weight = 1
    
    # Erstelle detailliertes Event
    mock_eg.event = create_mock_event_with_details()
    
    return mock_eg


def create_mock_avail_day_group(name: str):
    """Erstellt ein Mock AvailDayGroup."""
    mock_adg = Mock()
    mock_adg.avail_day_group_id = uuid4()
    mock_adg.name = name
    mock_adg.children = []
    mock_adg.avail_day = None
    mock_adg.nr_of_active_children = None
    mock_adg.weight = 1
    
    return mock_adg


def create_mock_avail_day_group_with_avail_day(name: str):
    """Erstellt ein Mock AvailDayGroup mit detailliertem AvailDay."""
    mock_adg = Mock()
    mock_adg.avail_day_group_id = uuid4()
    mock_adg.name = name
    mock_adg.children = []
    mock_adg.nr_of_active_children = None
    mock_adg.weight = 1
    
    # Erstelle detaillierten AvailDay
    mock_adg.avail_day = create_mock_avail_day_with_details()
    
    return mock_adg


def create_mock_event_with_details():
    """Erstellt ein detailliertes Mock Event für Tests."""
    mock_event = Mock()
    mock_event.id = uuid4()
    mock_event.date = date(2025, 6, 29)  # Heute
    
    # Time of Day
    mock_tod = Mock()
    mock_tod.name = "Morning"
    mock_tod.start = time(9, 0)
    mock_tod.end = time(12, 0)
    mock_tod.time_of_day_enum = Mock()
    mock_tod.time_of_day_enum.time_index = 1
    mock_event.time_of_day = mock_tod
    
    # Location
    mock_location = Mock()
    mock_location.id = uuid4()
    mock_location.name = "Test Location"
    mock_location.address = Mock()
    mock_location.address.city = "Test City"
    
    mock_lpp = Mock()
    mock_lpp.location_of_work = mock_location
    mock_event.location_plan_period = mock_lpp
    
    # Cast Group
    mock_cast_group = Mock()
    mock_cast_group.nr_actors = 2
    mock_event.cast_group = mock_cast_group
    
    return mock_event


def create_mock_avail_day_with_details():
    """Erstellt einen detaillierten Mock AvailDay für Tests."""
    mock_avail_day = Mock()
    mock_avail_day.date = date(2025, 6, 29)  # Heute
    
    # Time of Day (same as event for compatibility)
    mock_tod = Mock()
    mock_tod.name = "Morning"
    mock_tod.start = time(9, 0)
    mock_tod.end = time(12, 0)
    mock_tod.time_of_day_enum = Mock()
    mock_tod.time_of_day_enum.time_index = 1
    mock_avail_day.time_of_day = mock_tod
    
    # Actor Plan Period
    mock_app = create_mock_actor_plan_period("Test Actor", 10)
    mock_avail_day.actor_plan_period = mock_app
    
    # Location Preferences
    mock_avail_day.actor_location_prefs_defaults = []
    mock_avail_day.actor_partner_location_prefs_defaults = []
    mock_avail_day.combination_locations_possibles = []
    mock_avail_day.skills = []
    
    return mock_avail_day


@pytest.fixture
def mock_event_with_details():
    """Fixture für detailliertes Mock Event."""
    return create_mock_event_with_details()


@pytest.fixture
def mock_avail_day_with_details():
    """Fixture für detaillierten Mock AvailDay."""
    return create_mock_avail_day_with_details()


@pytest.fixture
def mock_logger():
    """Fixture für Mock Logger."""
    logger = Mock()
    logger.info = Mock()
    logger.debug = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


# Pytest Marker für verschiedene Testkategorien
def pytest_configure(config):
    """Konfiguriert pytest Marker."""
    config.addinivalue_line("markers", "unit: Unit-Tests für einzelne Komponenten")
    config.addinivalue_line("markers", "integration: Integration-Tests zwischen Komponenten")
    config.addinivalue_line("markers", "slow: Langsame Tests (z.B. vollständige Solver-Runs)")
    config.addinivalue_line("markers", "mock: Tests die hauptsächlich Mock-Objekte verwenden")


# Logger Mock - entfernt da shifts.py keinen Logger hat
# Falls später ein Logger benötigt wird, kann er spezifisch gepatcht werden
