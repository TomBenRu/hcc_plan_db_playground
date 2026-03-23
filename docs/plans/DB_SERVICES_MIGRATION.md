# Migrationsplan: `db_services.py` → `db_services/` Paket

## Kontext

Die Datei `database/db_services.py` (~3110 Zeilen, 28 Klassen, ~250 Methoden) ist ein monolithisches
Service-Layer-Modul. Alle Klassen bestehen ausschließlich aus `@classmethod`-Methoden ohne OOP-Semantik
(keine Instanzen, keine Vererbung, kein `isinstance`). Klassen werden rein als Namespaces missbraucht —
dafür sind Python-Module besser geeignet.

**Ziel:** Jede Klasse wird ein eigenes Modul (snake_case), Methoden werden zu Funktionen.
Rückwärtskompatibilität wird durch `from . import person as Person` in `__init__.py` sichergestellt —
**kein einziger Aufrufer muss geändert werden**.

**Arbeitsverzeichnis:** `.claude/worktrees/sqlmodel-migration/database/`

---

## Schritt 1: `_common.py` erstellen

Gemeinsame Infrastruktur für alle Submodule.

**Datei:** `database/db_services/_common.py`

Enthält:
- `LOGGING_ENABLED = False`
- `logger = logging.getLogger(__name__)`
- `log_function_info()` — **ohne Parameter** (statt `cls`), ermittelt Modul/Funktion via `inspect`

```python
def log_function_info():
    if not LOGGING_ENABLED:
        return
    frame = inspect.currentframe().f_back
    module_name = frame.f_globals.get('__name__', '?')
    func_name = frame.f_code.co_name
    logger.info(f'function: {module_name}.{func_name}\n'
                f'args: {frame.f_locals}')
```

**Änderung:** ~200 Aufrufstellen wechseln von `log_function_info(cls)` → `log_function_info()`.

---

## Schritt 2: Module extrahieren (28 Dateien)

Für jede Klasse eine Datei erstellen. Transformation pro Methode:
1. `@classmethod` entfernen
2. `cls` aus Parameterliste entfernen
3. `log_function_info(cls)` → `log_function_info()`

### Klasse → Modul Mapping

| Klasse | Moduldatei | Spezial-Imports |
|---|---|---|
| `EntitiesApiToDB` | `entities_api_to_db.py` | `schemas_plan_api`, `Gender` |
| `Project` | `project.py` | — |
| `Team` | `team.py` | — |
| `Person` | `person.py` | `pandas`, `hash_psw`, `Gender`, `or_` |
| `LocationOfWork` | `location_of_work.py` | `or_` |
| `TeamActorAssign` | `team_actor_assign.py` | `or_` |
| `TeamLocationAssign` | `team_location_assign.py` | `or_` |
| `TimeOfDay` | `time_of_day.py` | — |
| `TimeOfDayEnum` | `time_of_day_enum.py` | — |
| `ExcelExportSettings` | `excel_export_settings.py` | — |
| `Address` | `address.py` | — |
| `MaxFairShiftsOfApp` | `max_fair_shifts_of_app.py` | — |
| `CastRule` | `cast_rule.py` | — |
| `PlanPeriod` | `plan_period.py` | — |
| `LocationPlanPeriod` | `location_plan_period.py` | — |
| `EventGroup` | `event_group.py` | `Optional` |
| `CastGroup` | `cast_group.py` | — |
| `Event` | `event.py` | — |
| `ActorPlanPeriod` | `actor_plan_period.py` | — |
| `AvailDayGroup` | `avail_day_group.py` | `Optional` |
| `RequiredAvailDayGroups` | `required_avail_day_groups.py` | — |
| `AvailDay` | `avail_day.py` | — |
| `CombinationLocationsPossible` | `combination_locations_possible.py` | — |
| `ActorLocationPref` | `actor_location_pref.py` | — |
| `ActorPartnerLocationPref` | `actor_partner_location_pref.py` | — |
| `Skill` | `skill.py` | — |
| `SkillGroup` | `skill_group.py` | — |
| `Plan` | `plan.py` | — |
| `Appointment` | `appointment.py` | `json` |

### Standard-Imports pro Modul

```python
import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
```

Module, die `or_` brauchen, ergänzen `from sqlalchemy import or_`.

### Reihenfolge der Extraktion

1. **Batch 1** (klein, zum Validieren): `Project`, `Team`, `Address`, `ExcelExportSettings`
2. **Batch 2** (mit `or_`): `LocationOfWork`, `TeamActorAssign`, `TeamLocationAssign`
3. **Batch 3** (Spezial-Imports): `EntitiesApiToDB`, `Person`, `Appointment`
4. **Batch 4** (Rest): alle verbleibenden 18 Module

---

## Schritt 3: `__init__.py` erstellen

**Datei:** `database/db_services/__init__.py`

```python
"""db_services — SQLModel/SQLAlchemy 2.x Service Layer"""

from ._common import log_function_info, LOGGING_ENABLED

from . import entities_api_to_db as EntitiesApiToDB
from . import project as Project
from . import team as Team
from . import person as Person
from . import location_of_work as LocationOfWork
from . import team_actor_assign as TeamActorAssign
from . import team_location_assign as TeamLocationAssign
from . import time_of_day as TimeOfDay
from . import time_of_day_enum as TimeOfDayEnum
from . import excel_export_settings as ExcelExportSettings
from . import address as Address
from . import max_fair_shifts_of_app as MaxFairShiftsOfApp
from . import cast_rule as CastRule
from . import plan_period as PlanPeriod
from . import location_plan_period as LocationPlanPeriod
from . import event_group as EventGroup
from . import cast_group as CastGroup
from . import event as Event
from . import actor_plan_period as ActorPlanPeriod
from . import avail_day_group as AvailDayGroup
from . import required_avail_day_groups as RequiredAvailDayGroups
from . import avail_day as AvailDay
from . import combination_locations_possible as CombinationLocationsPossible
from . import actor_location_pref as ActorLocationPref
from . import actor_partner_location_pref as ActorPartnerLocationPref
from . import skill as Skill
from . import skill_group as SkillGroup
from . import plan as Plan
from . import appointment as Appointment
```

**Warum das funktioniert:**
- `db_services.Person.get(...)` → `Person` ist das Modul, `get` die Funktion darin
- `from database.db_services import Person, Team` → funktioniert (Module sind Objekte)
- `from database.db_services import log_function_info, LOGGING_ENABLED` → funktioniert (re-exportiert)

---

## Schritt 4: Altes Modul ersetzen

1. `database/db_services.py` löschen
2. Python löst `database.db_services` nun als Paket (Verzeichnis) auf
3. **Wichtig:** `.py`-Datei und gleichnamiges Verzeichnis können NICHT koexistieren

---

## Schritt 5: Externe Imports prüfen (3 Dateien)

| Datei | Import | Anpassung nötig? |
|---|---|---|
| `employment_statistics/service.py` | `from database.db_services import log_function_info, LOGGING_ENABLED` | **Nein** (re-exportiert) |
| `employment_statistics/dashboard/service.py` | `from database.db_services import log_function_info, LOGGING_ENABLED` | **Nein** (re-exportiert) |
| `gui/employment_statistics/date_range_widget.py` | `from database.db_services import Project, Team` | **Nein** (Aliase in `__init__.py`) |

**Einzige Anpassung extern:** Die 2 `employment_statistics` Service-Dateien rufen
`log_function_info(cls)` auf — dort muss `(cls)` → `()` geändert werden.

---

## Schritt 6: Verifikation

### A. Import-Smoke-Test
```python
from database import db_services
assert hasattr(db_services.Person, 'get')
assert hasattr(db_services.Person, 'create')
assert callable(db_services.log_function_info)
```

### B. Test Suite
```bash
python -m pytest tests/test_rule_data_model.py -v
```

### C. Grep-Check — alle Aufrufmuster validieren
```bash
grep -rn "db_services\.\w\+\.\w\+" --include="*.py" | head -20
```

Für jedes gefundene `db_services.ClassName.method` prüfen, dass die Funktion im Modul existiert.

---

## Risiken

| Risiko | Mitigation |
|---|---|
| `.py` und gleichnamiges Verzeichnis können nicht koexistieren | Datei löschen, bevor Paket aktiv wird (ein atomarer Commit) |
| Log-Format ändert sich (`Person.create` → `database.db_services.person.create`) | Bewusste Verbesserung — mehr Kontext im Log |
| Zirkuläre Imports zwischen Modulen | Ausgeschlossen: keine Cross-Class-Aufrufe im aktuellen Code |
| Eager-Loading aller Module bei `import db_services` | Identisch zum Status quo (monolithische Datei lud auch alles) |

---

## Kritische Dateien

- **Quelle:** `.claude/worktrees/sqlmodel-migration/database/db_services.py` (wird zerlegt)
- **Prüfen:** `database/__init__.py` (importiert `db_services` nicht direkt — kein Handlungsbedarf)
- **Externe Anpassung:** `employment_statistics/service.py`, `employment_statistics/dashboard/service.py`
  (nur `log_function_info(cls)` → `log_function_info()`)
