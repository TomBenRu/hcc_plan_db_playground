# Anforderungsdokument: Verbindlicher Plan (Binding Plan)

**Datum:** 2026-04-12  
**Status:** Anforderungen vollständig, Implementierung ausstehend  
**Bezug:** `database/models.py`, `gui/main_window.py`, `web_api/employees/`, `web_api/availability/`

---

## 1. Problem

Für eine Planperiode können mehrere Pläne existieren (Varianten zum Vergleich). Alle Pläne einer
Planperiode enthalten eigene `Appointment`-Einträge (je Plan ein vollständiger Satz). Da die
Web-API beim Abrufen von Appointments nicht nach Plan filtert, werden sämtliche Appointments
aller Pläne angezeigt — für einen Mitarbeiter mit mehreren Plan-Varianten erscheinen so
mehrfach dieselben Termine im Kalender.

### Konkrete Datenlage (Ausgangsbefund)

```
PlanPeriod Jun 2026
  ├── Plan A (Variante 1) → Appointment 764b8fe3 (Event 6833de2f, Uniklinik, 01.06.)
  └── Plan B (Variante 2) → Appointment bfc89645 (Event 6833de2f, Uniklinik, 01.06.)
```

Beide Appointments sind über `AvailDayAppointmentLink` mit demselben AvailDay verknüpft.
Die Web-API (und theoretisch auch der Desktop) zeigt beide → Mitarbeiter sieht 2× denselben
Termin.

---

## 2. Lösung: `Plan.is_binding`-Flag

### 2.1 Konzept

Genau ein Plan pro Planperiode kann als **verbindlich** markiert werden. Nur Appointments aus
verbindlichen Plänen werden in Mitarbeiter-Kalender und Verfügbarkeits-Ansicht angezeigt.
Existiert kein verbindlicher Plan, werden **keine** Appointments angezeigt (kein verwirrend
gemischter Zustand).

### 2.2 Datenmodell-Änderung

```python
# database/models.py — class Plan
is_binding: bool = Field(default=False)
```

Partial Unique Index auf DB-Ebene (erzwingt max. 1 verbindlicher Plan pro Planperiode):

```sql
CREATE UNIQUE INDEX uq_plan_one_binding_per_period
    ON plan (plan_period_id)
    WHERE is_binding = TRUE;
```

In SQLAlchemy/SQLModel wird der Index via `__table_args__` deklariert:

```python
__table_args__ = (
    UniqueConstraint("name", "plan_period_id"),
    Index("uq_plan_one_binding_per_period",
          "plan_period_id",
          unique=True,
          postgresql_where=text("is_binding = TRUE")),
)
```

### 2.3 Migration

Alembic-Migration:
1. Spalte `is_binding BOOLEAN NOT NULL DEFAULT FALSE` zur Tabelle `plan` hinzufügen
2. Partial Unique Index anlegen
3. Existing data: alle bestehenden Pläne erhalten `is_binding = False` (kein verbindlicher Plan)

---

## 3. Desktop-GUI-Änderungen

### 3.1 Neuer Menüpunkt / Toolbar-Button: „Als verbindlich festlegen"

**Empfohlener Ansatz:** Eigenständige Aktion, **nicht** automatisch in `plan_save` integriert.

**Begründung:** `plan_save` speichert/benennt einen Plan um — das ist ein separater Schritt
vom Entscheid „dieser Plan ist der finale". Ein Dispatcher speichert routinemäßig Varianten,
bevor er sich entscheidet.

**Platzierung:**
- Menü **Plan** → neuer Eintrag `„Als verbindlich festlegen"` (neben `plan_save`)
- Optional: Toolbar-Button, gleiches Icon wie `plan_save` aber mit Abzeichen/Badge

**Alternativ (einfacher):** Als Checkbox im Plan-Tab-Header oder im Plan-Kontextmenü im
Tab-Bar (Rechtsklick auf Tab → „Als verbindlich festlegen").

### 3.2 Aktion `plan_set_binding` (`MainWindow`)

```python
def plan_set_binding(self):
    active_widget = self.tab_manager.current_plan_widget
    if not active_widget:
        QMessageBox.critical(self, 'Verbindlichen Plan festlegen',
                             'Kein Plan aktiv.')
        return

    plan = active_widget.plan
    if plan.is_binding:
        QMessageBox.information(self, 'Verbindlichen Plan festlegen',
                                f'„{plan.name}" ist bereits verbindlich.')
        return

    # Warnung: vorheriger verbindlicher Plan wird abgelöst
    # (DB-Constraint verhindert doppeltes is_binding=True)
    confirmation = QMessageBox.question(
        self, 'Verbindlichen Plan festlegen',
        f'Plan „{plan.name}" als verbindlichen Plan für diese Periode festlegen?\n\n'
        f'Ein eventuell vorhandener anderer verbindlicher Plan wird damit abgelöst.',
    )
    if confirmation != QMessageBox.Yes:
        return

    self.controller.execute(plan_commands.SetBinding(plan.id))
    # Tab-Header / UI-Indikator aktualisieren
```

### 3.3 Neuer Command: `plan_commands.SetBinding`

```python
class SetBinding(Command):
    """Markiert einen Plan als verbindlich; hebt bei anderen Plänen der gleichen
    Planperiode is_binding auf."""

    def __init__(self, plan_id: UUID):
        self.plan_id = plan_id

    def execute(self, session: Session):
        plan = session.get(Plan, self.plan_id)
        # Vorherigen verbindlichen Plan derselben Periode zurücksetzen
        prev = session.exec(
            select(Plan)
            .where(Plan.plan_period_id == plan.plan_period_id)
            .where(Plan.is_binding == True)
            .where(Plan.id != self.plan_id)
        ).first()
        if prev:
            prev.is_binding = False
        plan.is_binding = True
        session.flush()
```

*(Alternativ: nur DB-Constraint vertrauen und `UPDATE plan SET is_binding=FALSE WHERE
plan_period_id=... AND is_binding=TRUE` vor dem SET TRUE ausführen.)*

### 3.4 Visuelle Kennzeichnung im Desktop

- Tab-Titel des verbindlichen Plans: **fett** oder mit `★`-Präfix
- Plan-Liste (sofern vorhanden): verbindlicher Plan hervorgehoben (Fettschrift, Farbe, Icon)

### 3.5 Integration in `plan_save` (optional, leichtgewichtig)

Falls gewünscht: `plan_save` könnte am Ende fragen:

> „Soll dieser Plan als verbindlich für die Periode festgelegt werden?"

als optionale `QCheckBox` im Dialog. Dies ist eine Konvenienz-Erweiterung, keine Voraussetzung.

---

## 4. Web-API-Änderungen

### 4.1 `web_api/employees/service.py` — `get_appointments_for_person`

Aktueller Join-Pfad:
```
Appointment → AvailDayAppointmentLink → AvailDay → ActorPlanPeriod → Person
```

Erweiterung — Plan-Filter:
```python
.join(Plan, Plan.id == Appointment.plan_id)
.where(Plan.is_binding.is_(True))
.where(Plan.prep_delete.is_(None))
```

**Fallback-Verhalten (kein verbindlicher Plan):** Der Query gibt 0 Zeilen zurück →
FullCalendar zeigt leeren Kalender. Kein Fallback auf „alle Pläne anzeigen".

### 4.2 `web_api/availability/service.py` — `has_appointment`-Subquery

Der EXISTS-Subquery in `get_markers_for_range` muss ebenfalls auf verbindliche Pläne filtern,
damit Lock-Icons (🔒) nur für Appointments aus dem verbindlichen Plan erscheinen:

```python
has_appt_sq = (
    sa_select(AvailDayAppointmentLink.avail_day_id)
    .join(Appointment, Appointment.id == AvailDayAppointmentLink.appointment_id)
    .join(Plan, Plan.id == Appointment.plan_id)
    .where(AvailDayAppointmentLink.avail_day_id == AvailDay.id)
    .where(Plan.is_binding.is_(True))
    .where(Plan.prep_delete.is_(None))
    .correlate(AvailDay)
    .exists()
    .label("has_appointment")
)
```

### 4.3 `web_api/availability/service.py` — `get_day_detail`

Der `has_appointment`-Check im Day-Panel (`DayTodOption.has_appointment`) muss gleichfalls
auf verbindliche Pläne filtern.

### 4.4 Schema-Erweiterung (optional)

Falls das `Plan`-Objekt in Web-API-Responses genutzt wird: `is_binding` ins Pydantic-Schema
aufnehmen. Für die bisherigen Mitarbeiter-Endpoints ist kein Plan-Schema exponiert, daher
zunächst nicht nötig.

---

## 5. Datenbank-Schema-Änderungen im Überblick

| Tabelle | Änderung |
|---|---|
| `plan` | Neue Spalte `is_binding BOOLEAN NOT NULL DEFAULT FALSE` |
| `plan` (Index) | `CREATE UNIQUE INDEX uq_plan_one_binding_per_period ON plan (plan_period_id) WHERE is_binding = TRUE` |

Keine weiteren Tabellen betroffen.

---

## 6. Betroffene Dateien

| Datei | Art der Änderung |
|---|---|
| `database/models.py` | `Plan.is_binding` Feld + `__table_args__` Index |
| `alembic/versions/XXXX_add_plan_is_binding.py` | Migration: Spalte + Partial Index |
| `schemas/plan.py` (o. Ä.) | `is_binding` in `PlanShow` / `PlanUpdate` |
| `database/db_services/plan.py` | Neue Funktion `set_binding(plan_id)` |
| `commands/database_commands/plan_commands.py` | Neuer Command `SetBinding` |
| `gui/main_window.py` | Neue Methode `plan_set_binding`, Menü-/Toolbar-Eintrag |
| `gui/frm_tab_plan.py` | Visuelle Kennzeichnung verbindlicher Plan (Tab-Titel / Header) |
| `web_api/employees/service.py` | Plan-Filter in `get_appointments_for_person` |
| `web_api/availability/service.py` | Plan-Filter in `has_appointment`-Subquery + `get_day_detail` |

---

## 7. Offene Entscheidungen

| # | Frage | Optionen | Empfehlung |
|---|---|---|---|
| 7.1 | Wo `plan_set_binding` auslösen? | (A) Eigenständiger Menüpunkt/Button, (B) In `plan_save` integriert (optional), (C) Kontextmenü Tab-Bar | (A) als Primär-Eintrag; (B) als optionale Erweiterung |
| 7.2 | Fallback wenn kein verbindlicher Plan? | (A) Keine Appointments zeigen, (B) Alle Appointments zeigen | (A) — klarer Zustand, kein verwirrtes Mixing |
| 7.3 | Partial Index DB-seitig oder App-seitig? | DB-seitig via Alembic | DB-seitig — härteste Garantie |
| 7.4 | `plan_save` + `set_binding` kombinieren? | Optional als Checkbox im `plan_save`-Dialog | Umsetzung nach Grundimplementierung |

---

## 8. Abgrenzung / Nicht im Scope

- **Dispatcher-Web-API:** Kein Web-Endpoint zum Setzen von `is_binding` geplant (bleibt Desktop-only)
- **Historische Daten:** Bestehende Pläne erhalten `is_binding=False` — kein automatisches
  Setzen für historische Perioden; Dispatcher muss manuell festlegen
- **Mehrere verbindliche Pläne gleichzeitig:** Explizit ausgeschlossen (Partial Unique Index)
- **Automatisches `is_binding` beim Solver-Run:** Kein automatisches Setzen, immer explizite
  Dispatcher-Entscheidung

---

## 9. Verifikation (End-to-End)

- Test-User: hanna@test.de, Test1234!
1. Plan A und Plan B für dieselbe Planperiode anlegen und solver laufen lassen
2. Plan A als verbindlich markieren → Mitarbeiter-Kalender und Availability-Kalender
   zeigen nur Appointments aus Plan A
3. Plan B als verbindlich markieren → Plan A verliert `is_binding`, Plan B wird angezeigt
4. DB-Constraint testen: direkter SQL-Versuch, zwei Pläne mit `is_binding=TRUE` in gleicher
   Periode → muss mit UNIQUE-Violation fehlschlagen
5. Kein verbindlicher Plan → leerer Kalender (keine Appointments)
6. `plan_save` für Plan A → `is_binding` wird dadurch **nicht** automatisch gesetzt
