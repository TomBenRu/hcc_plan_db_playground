# Refactoring Plan: SAT Solver Architektur-Verbesserung

## Analysierte Probleme

### 1. Monolithische Struktur
- `solver_main.py` hat über 1000 Zeilen Code
- Zu viele Verantwortlichkeiten in einer Datei
- Schwer wartbar und testbar

### 2. Parameter-Weitergabe (Parameter Passing)
- Funktionen wie `create_constraints()` geben Tupel mit 10+ Elementen zurück
- Viele Constraint-Funktionen nehmen `model` und mehrere andere Parameter entgegen
- Führt zu unlesbaren Funktionssignaturen

### 3. Globaler Zustand
- `entities` als globale Variable
- Macht Testing und Parallelisierung schwierig
- Unklare Abhängigkeiten zwischen Funktionen

### 4. Unstrukturierte Constraint-Logik
- Jeder Constraint-Typ hat eine eigene Funktion
- Keine einheitliche Schnittstelle
- Schwierig erweiterbar

## Vorgeschlagene Architektur

### 1. Neue Modulstruktur

```
sat_solver/
├── __init__.py
├── solver_main.py          # Vereinfacht, nur Hauptorchestration
├── core/
│   ├── __init__.py
│   ├── solver_context.py   # SolverContext-Klasse
│   ├── entities.py         # Entities-Datenklasse
│   └── solver_config.py    # Konfiguration
├── constraints/
│   ├── __init__.py
│   ├── base.py            # AbstractConstraint Basisklasse
│   ├── availability.py    # EmployeeAvailabilityConstraint
│   ├── event_groups.py    # EventGroupsConstraint
│   ├── avail_day_groups.py # AvailDayGroupsConstraint
│   ├── weights.py         # WeightsConstraint
│   ├── location_prefs.py  # LocationPrefsConstraint
│   ├── partner_prefs.py   # PartnerLocationPrefsConstraint
│   ├── cast_rules.py      # CastRulesConstraint
│   ├── fixed_cast.py      # FixedCastConstraint
│   ├── skills.py          # SkillsConstraint
│   ├── shifts.py          # ShiftsConstraint
│   └── constraint_factory.py # Factory für alle Constraints
├── solving/
│   ├── __init__.py
│   ├── solver.py          # Hauptsolver-Klasse
│   ├── objectives.py      # Zielfunktionen
│   └── callbacks.py       # Solution Callbacks
└── results/
    ├── __init__.py
    ├── result_processor.py # Ergebnisverarbeitung
    └── statistics.py      # Statistiken und Reporting
```

### 2. Kernklassen Design

#### 2.1 SolverContext
```python
@dataclass
class SolverContext:
    """Zentraler Kontext für alle Solver-Operationen"""
    entities: Entities
    model: cp_model.CpModel
    config: SolverConfig
    
    # Constraint-Results
    constraint_vars: Dict[str, List[IntVar]] = field(default_factory=dict)
    
    def add_constraint_vars(self, constraint_name: str, vars: List[IntVar]):
        """Fügt Constraint-Variablen hinzu"""
        
    def get_constraint_vars(self, constraint_name: str) -> List[IntVar]:
        """Holt Constraint-Variablen"""
```

#### 2.2 Abstract Constraint Base Class
```python
from abc import ABC, abstractmethod

class AbstractConstraint(ABC):
    """Basisklasse für alle Constraints"""
    
    def __init__(self, context: SolverContext):
        self.context = context
        self.model = context.model
        self.entities = context.entities
        self.config = context.config
    
    @abstractmethod
    def create_variables(self) -> List[IntVar]:
        """Erstellt die für diesen Constraint nötigen Variablen"""
        pass
    
    @abstractmethod
    def add_constraints(self) -> None:
        """Fügt die Constraints zum Modell hinzu"""
        pass
    
    @property
    @abstractmethod
    def constraint_name(self) -> str:
        """Name des Constraints für Referenzierung"""
        pass
```

#### 2.3 Beispiel Constraint-Implementierung
```python
class EmployeeAvailabilityConstraint(AbstractConstraint):
    """Constraint für Mitarbeiterverfügbarkeit"""
    
    @property
    def constraint_name(self) -> str:
        return "employee_availability"
    
    def create_variables(self) -> List[IntVar]:
        # Keine neuen Variablen nötig
        return []
    
    def add_constraints(self) -> None:
        for key, val in self.entities.shifts_exclusive.items():
            if not val:
                self.model.Add(self.entities.shift_vars[key] == 0)
```

#### 2.4 Hauptsolver-Klasse
```python
class SATSolver:
    """Hauptklasse für SAT-Solving-Operationen"""
    
    def __init__(self, plan_period_id: UUID, config: SolverConfig = None):
        self.plan_period_id = plan_period_id
        self.config = config or SolverConfig()
        self.context: SolverContext = None
        
    def setup_context(self) -> SolverContext:
        """Erstellt und konfiguriert den Solver-Kontext"""
        
    def create_all_constraints(self) -> None:
        """Erstellt alle Constraints über die Factory"""
        
    def solve(self) -> SolverResult:
        """Führt das Solving durch"""
```

### 3. Constraint Factory Pattern

```python
class ConstraintFactory:
    """Factory für die Erstellung aller Constraints"""
    
    CONSTRAINT_CLASSES = [
        EmployeeAvailabilityConstraint,
        EventGroupsConstraint,
        AvailDayGroupsConstraint,
        WeightsConstraint,
        LocationPrefsConstraint,
        PartnerLocationPrefsConstraint,
        CastRulesConstraint,
        FixedCastConstraint,
        SkillsConstraint,
        ShiftsConstraint,
    ]
    
    @classmethod
    def create_all_constraints(cls, context: SolverContext) -> List[AbstractConstraint]:
        """Erstellt alle Constraints"""
        constraints = []
        for constraint_class in cls.CONSTRAINT_CLASSES:
            constraints.append(constraint_class(context))
        return constraints
```

### 4. Vereinfachte Zielfunktionen

```python
class ObjectiveBuilder:
    """Builder für Zielfunktionen"""
    
    def __init__(self, context: SolverContext):
        self.context = context
        
    def build_minimize_objective(self) -> None:
        """Erstellt Standard-Minimierungs-Zielfunktion"""
        weights = self.context.config.minimization_weights
        
        objective_terms = []
        
        # Unassigned shifts
        if unassigned_vars := self.context.get_constraint_vars("unassigned_shifts"):
            objective_terms.append(weights.unassigned_shifts * sum(unassigned_vars))
            
        # Weitere Terme...
        
        self.context.model.Minimize(sum(objective_terms))
```

## Implementierungsplan

### Phase 1: Grundstruktur (Woche 1)
1. **Erstelle neue Modulstruktur**
   - Neue Verzeichnisse und `__init__.py` Dateien
   - SolverContext und Entities in separaten Dateien

2. **Implementiere Basis-Abstraktion**
   - AbstractConstraint Basisklasse
   - SolverContext Klasse
   - Grundlegende Konfigurationsklassen

### Phase 2: Constraint-Migration (Woche 2)
3. **Migriere einfache Constraints**
   - EmployeeAvailabilityConstraint
   - EventGroupsConstraint
   - AvailDayGroupsConstraint

4. **Migriere komplexe Constraints**
   - WeightsConstraint (Event/AvailDay)
   - LocationPrefsConstraint
   - PartnerLocationPrefsConstraint

### Phase 3: Erweiterte Features (Woche 3)
5. **Migriere spezialisierte Constraints**
   - CastRulesConstraint
   - FixedCastConstraint
   - SkillsConstraint
   - ShiftsConstraint

6. **Implementiere Solver und Objectives**
   - SATSolver Hauptklasse
   - ObjectiveBuilder
   - ResultProcessor

### Phase 4: Integration und Testing (Woche 4)
7. **Refactore solver_main.py**
   - Verwende neue Architektur
   - Behalte bestehende API bei
   - Umfassende Tests

8. **Performance-Optimierung**
   - Profiling der neuen Struktur
   - Vergleich mit alter Implementation

## Vorteile der neuen Architektur

### 1. Bessere Wartbarkeit
- Jeder Constraint in eigener Klasse
- Klare Verantwortlichkeiten
- Einfachere Unit-Tests

### 2. Erweiterbarkeit
- Neue Constraints durch Ableitung von AbstractConstraint
- Plugin-ähnliche Architektur über Factory
- Konfigurierbare Constraint-Sets

### 3. Bessere Testbarkeit
- Isolierte Constraint-Tests möglich
- Mockbare Dependencies
- Kein globaler Zustand

### 4. Performance
- Lazy Loading von Constraints
- Parallelisierungsmöglichkeiten
- Bessere Memory-Effizienz

### 5. Code-Qualität
- Kleinere, fokussierte Klassen
- Weniger Parameter-Passing
- Explizite Dependencies

## Rückwärtskompatibilität

Die Refactoring erfolgt so, dass:
- Bestehende API von `solver_main.py` erhalten bleibt
- Schrittweise Migration möglich ist
- Alte und neue Implementation parallel laufen können
- Tests kontinuierlich grün bleiben

## Nächste Schritte

1. **Diskussion der Architektur**
   - Review dieses Plans
   - Abstimmung der Details
   - Definition der finalen Modulstruktur

2. **Proof of Concept**
   - Implementierung eines Beispiel-Constraints
   - Validierung der Architektur-Ansätze

3. **Iterative Umsetzung**
   - Phase-by-Phase Implementierung
   - Kontinuierliche Integration und Tests

Möchtest du mit einem spezifischen Constraint beginnen oder soll ich zuerst die Grundstruktur implementieren?
