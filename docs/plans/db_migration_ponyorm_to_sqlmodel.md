# PonyORM → SQLModel Migration — Verbleibende Schritte

## Kontext

Die Desktop-App (PySide6) nutzt PonyORM als ORM mit SQLite. Die Migration zu SQLModel/SQLAlchemy 2.x ist nötig für bessere Typisierung, aktive Wartung und zukünftige PostgreSQL-Unterstützung.

**Bereits erledigt:**
- `database/models_sqlmodel.py` — 60 Tabellen (31 Entities + 29 Link-Tabellen), Mapper OK
- `database/event_listeners.py` — 12 before_insert Hooks
- `database/database.py` — Engine + Session-Factory + Listener-Registrierung
- `alembic/` — Konfiguriert, initiale Migration generiert + getestet

**Architektur:** GUI → Commands (Undo/Redo) → `db_services.py` → ORM. Commands/GUI greifen NIE direkt auf PonyORM zu.

---

## Phase 0: Infrastruktur-Vorbereitung

### 0.1 — `get_session()` um Auto-Commit erweitern
**Datei:** `database/database.py`

PonyORM's `@db_session` committed automatisch bei fehlerfreiem Verlassen. Um das nachzubilden:
```python
@contextmanager
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
```

### 0.2 — Verschachtelte Sessions lösen
PonyORM erlaubt verschachtelte `@db_session` (innere teilt äußere Transaktion). In db_services rufen manche Methoden andere Service-Methoden auf (z.B. `AvailDay.create` → `AvailDayGroup.create`).

**Lösung:** Methoden erhalten optionalen `_session`-Parameter. Wenn gesetzt, wird die übergebene Session benutzt statt eine neue zu öffnen:
```python
def create(cls, data, _session: Session | None = None):
    def _do(session):
        obj = Model(**data)
        session.add(obj)
        return schema.model_validate(obj)
    if _session:
        return _do(_session)
    with get_session() as session:
        return _do(session)
```

### 0.3 — Transformations-Referenz

| PonyORM | SQLModel |
|---------|---------|
| `@db_session` | `with get_session() as session:` |
| `Model.get_for_update(id=x)` | `session.get(Model, x)` |
| `Model[id]` | `session.get(Model, id)` |
| `Model.select(lambda x: ...)` | `session.exec(select(Model).where(...)).all()` |
| `.filter(lambda x: ...).first()` | `.where(...).limit(1)` → `session.exec(...).first()` |
| `collection.add(obj)` | `collection.append(obj)` |
| `collection.add(list_of_objs)` | `collection.extend(list_of_objs)` |
| `collection.remove(obj)` | `collection.remove(obj)` |
| `collection.clear()` | `collection.clear()` |
| `obj.set(**kwargs)` | `for k, v in kwargs.items(): setattr(obj, k, v)` |
| `obj.delete()` | `session.delete(obj)` |
| `commit()` | `session.flush()` (innerhalb Session) |

---

## Phase 1: db_services.py — Stamm-Entities (28 Methoden)

Leaf-Entities ohne gegenseitige Abhängigkeiten. Einfache CRUD-Operationen.

| Schritt | Klasse | Methoden | Besonderheiten |
|---------|--------|----------|----------------|
| 1.1 | `ExcelExportSettings` | 3 | `.set()` → `setattr`-Loop |
| 1.2 | `Address` | 6 | `.delete()` → `session.delete()` |
| 1.3 | `TimeOfDayEnum` | 8 | enthält `commit()` → `session.flush()` |
| 1.4 | `MaxFairShiftsOfApp` | 4 | einfache Lambdas |
| 1.5 | `CastRule` | 7 | keine Lambdas |

**Verifikation:** Smoke-Test pro Klasse (Create + Read + Update + Delete auf In-Memory-DB).

---

## Phase 2: db_services.py — Projekt-Kern (63 Methoden)

| Schritt | Klasse | Methoden | Besonderheiten |
|---------|--------|----------|----------------|
| 2.1 | `Project` | 11 | `.clear()` + `.add()` Zyklen, M:N TimeOfDay |
| 2.2 | `Team` | 9 | FK zu Dispatcher (Person) |
| 2.3 | `Person` | 26 | **Größte Klasse bisher.** 8x `.add()`, 8x `.remove()`, viele M:N |
| 2.4 | `Skill` | 10 | Standard-CRUD + M:N zu Person/AvailDay |
| 2.5 | `SkillGroup` | 6 | FK zu Skill + LocationOfWork |
| 2.6 | `Flag` | *(in Person/Event enthalten)* | M:N wird über Person/Event bedient |

**Verifikation:** Project → Team → Person Hierarchie mit M:N-Beziehungen testen.

---

## Phase 3: db_services.py — Zuweisungen (21 Methoden)

| Schritt | Klasse | Methoden | Besonderheiten |
|---------|--------|----------|----------------|
| 3.1 | `TeamActorAssign` | 9 | Komplexe Datums-Lambdas → `or_()`, `and_()` |
| 3.2 | `TeamLocationAssign` | 8 | Gleiche Muster wie 3.1 |
| 3.3 | `CombinationLocationsPossible` | 4 | M:N zu LocationOfWork, Person |

**Verifikation:** Datums-basierte Queries testen (start ≤ date, end > date OR end is None).

---

## Phase 4: db_services.py — Planungs-Entities (46 Methoden)

| Schritt | Klasse | Methoden | Besonderheiten |
|---------|--------|----------|----------------|
| 4.1 | `PlanPeriod` | 10 | FK zu Team, Soft-Delete |
| 4.2 | `TimeOfDay` | 10 | 3 FKs zu Project (Disambiguierung) |
| 4.3 | `LocationOfWork` | 16 | Viele M:N, `.clear()` + `.add()` Zyklen |
| 4.4 | `LocationPlanPeriod` | 10 | FK zu PlanPeriod + LocationOfWork |

**Verifikation:** Verschachtelte Queries (PlanPeriod → Team → Project) testen.

---

## Phase 5: db_services.py — Event/Cast (55 Methoden)

| Schritt | Klasse | Methoden | Besonderheiten |
|---------|--------|----------|----------------|
| 5.1 | `EventGroup` | 9 | Self-ref 1:N (parent/children) |
| 5.2 | `CastGroup` | 14 | Self-ref M:N, `commit()` → `flush()` |
| 5.3 | `Event` | 17 | Komplexe Lambda-Ketten, Kaskaden-Delete |
| 5.4 | `ActorLocationPref` | 6 | 2 FKs zu Person |
| 5.5 | `ActorPartnerLocationPref` | 9 | 3 FKs zu Person, `.add()` mit Listen |

**Verifikation:** CastGroup self-ref M:N, Event-Kaskaden-Delete.

---

## Phase 6: db_services.py — Größte Entities (70 Methoden)

| Schritt | Klasse | Methoden | Besonderheiten |
|---------|--------|----------|----------------|
| 6.1 | `ActorPlanPeriod` | 18 | Viele M:N-Operationen |
| 6.2 | `AvailDayGroup` | 11 | Self-ref 1:N, muss VOR AvailDay |
| 6.3 | `RequiredAvailDayGroups` | 5 | M:N zu LocationOfWork |
| 6.4 | `AvailDay` (**36 Methoden!**) | 36 | Batch-Ops, verschachtelte Sub-Queries |

**AvailDay in 4 Teilschritte:**
1. Read-Methoden (get, get_batch, get_all_from_*) — 12 Methoden
2. Create/Delete/Update — 4 Methoden
3. Collection-Operationen (put_in_*, remove_*) — 14 Methoden
4. Bulk-Reset-Operationen (reset_all_*) — 6 Methoden

**Verifikation:** AvailDay ist das Herzstück der Planungslogik — besonders gründlich testen.

---

## Phase 7: db_services.py — Plan & Appointment & API (33 Methoden)

| Schritt | Klasse | Methoden | Besonderheiten |
|---------|--------|----------|----------------|
| 7.1 | `Plan` | 16 | JOINs für `.sort_by()`, Solver-Integration |
| 7.2 | `Appointment` | 9 | M:N zu AvailDay |
| 7.3 | `EntitiesApiToDB` | 8 | Einfache CRUD, API-Schnittstelle |

**Verifikation:** Plan-Erstellung + Appointment-AvailDay M:N.

---

## Phase 8: Externe Services (4 Dateien)

| Schritt | Datei | Aufwand |
|---------|-------|---------|
| 8.1 | `employee_event/db_service.py` (681 Z.) | Mittel — 14x @db_session |
| 8.2 | `employment_statistics/service.py` (432 Z.) | Mittel — PonyORM select/desc |
| 8.3 | `employment_statistics/dashboard/service.py` (~600 Z.) | Mittel — gleiche Muster |
| 8.4 | `email_to_users/service.py` (324 Z.) | Klein — `Model[id]` → `session.get()` |

---

## Phase 9: GUI/Schema-Anpassungen & Aufräumen

| Schritt | Beschreibung |
|---------|-------------|
| 9.1 | `gui/frm_team.py`: `TransactionIntegrityError` → `sqlalchemy.exc.IntegrityError` |
| 9.2 | `database/schemas_plan_api.py`: `pony_set_to_list()` → kann bleiben (harmlos) oder entfernen |
| 9.3 | `database/schemas.py`: `set_to_list` Validatoren optional entfernen |
| 9.4 | Alte Dateien löschen: `models.py`, `enum_converter.py` |
| 9.5 | `models_sqlmodel.py` → `models.py` umbenennen + alle Importe anpassen |
| 9.6 | `pony` aus `pyproject.toml` Dependencies entfernen |

**Verifikation:**
```bash
grep -rn "from pony" --include="*.py" .  # Muss 0 Treffer ergeben
```

---

## Phase 10: Datenmigration

### 10.1 — Migrationsscript erstellen
Standalone-Python-Script das:
1. Alte PonyORM-DB öffnet (raw SQLite via sqlite3)
2. Neue DB mit SQLModel-Schema erstellt (via Alembic)
3. Daten tabellenweise überträgt (FK-Reihenfolge beachtend)
4. M:N-Link-Tabellen befüllt (alte PonyORM-Tabellennamen → neue Link-Tabellen)

### 10.2 — Schema-Unterschiede behandeln
- **Tabellennamen:** PonyORM `Person` → SQLModel `person` (Case-Mapping nötig)
- **DateTime:** naive → timezone-aware (UTC anhängen)
- **Enums:** Wertformat prüfen (name-basiert in beiden)
- **M:N-Tabellennamen:** PonyORM `Person_Skill` → SQLModel `person_skill`

### 10.3 — Testen
- Mit Kopie der Produktions-DB testen
- Datensatz-Anzahl pro Tabelle vergleichen
- Stichproben auf Beziehungen

---

## Phase 11: Abschluss-Verifikation

1. App starten mit migrierter DB
2. Neues Projekt anlegen → vollständigen Planungszyklus durchspielen
3. Alle GUI-Dialoge öffnen
4. Employment-Statistiken abrufen
5. Alembic-Migration finalisieren (`alembic stamp head` auf migrierter DB)

---

## Risiken

| Risiko | Gegenmassnahme |
|--------|---------------|
| **Lazy Loading nach Session-Ende** | Alle `model_validate()` innerhalb `with get_session()` |
| **N+1 Queries bei tiefen Schemas** | `selectinload()` / `joinedload()` bei Bedarf |
| **Verschachtelte Service-Aufrufe** | Optionaler `_session`-Parameter |
| **PonyORM `.add(list)` vs SQLModel `.append(obj)`** | Systematisch alle `.add()` prüfen |
| **Thread-Safety (Solver)** | Eigene Session pro Thread |

---

## Kritische Dateien

- `database/db_services.py` — 3305 Zeilen, 314 Methoden (Kern der Migration)
- `database/database.py` — Session-Factory erweitern
- `database/models_sqlmodel.py` — Referenz für Transformationen
- `database/schemas.py` — Pydantic Schemas (from_attributes=True bereits vorhanden)
- `employee_event/db_service.py` — Größter externer Service (681 Zeilen)
- `employment_statistics/service.py` — PonyORM select/desc Queries
- `employment_statistics/dashboard/service.py` — PonyORM select/desc Queries
- `email_to_users/service.py` — Einfache Model[id]-Zugriffe
- `gui/frm_team.py` — PonyORM Exception
