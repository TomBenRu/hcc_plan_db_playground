# Performance-Optimierung für Config-Button "Reset All" Operationen

## Übersicht

Diese Dokumentation beschreibt die Performance-Optimierungen, die für die `reset_all_partner_loc_prefs()`-Methode implementiert wurden. Die gleichen Patterns können auf andere "Reset All"-Operationen angewendet werden (z.B. `reset_all_loc_prefs()`, `reset_all_comb_loc_possible()`).

### Erzielte Performance-Verbesserung

| Phase | Methodenzeit | Verbesserung |
|---|---|---|
| Vor Optimierung | **12,84 Sekunden** | – |
| Nach Optimierung | **0,35 Sekunden** | **97% schneller** |

---

## Die 4 Hauptengpässe und ihre Lösungen

### Engpass 1: Einzelne `.add()`-Aufrufe in Schleife

**Problem:**
```python
# LANGSAM: N × M einzelne SQL-INSERT-Statements
for avail_day_db in actor_plan_period_db.avail_days:
    avail_day_db.actor_partner_location_prefs_defaults.clear()
    for partner_location_pref_db in actor_plan_period_db.actor_partner_location_prefs_defaults:
        avail_day_db.actor_partner_location_prefs_defaults.add(partner_location_pref_db)
```

**Lösung:** Pony ORMs `Set.add()` akzeptiert Collections – eine Operation statt N×M:
```python
# SCHNELL: Bulk-Add
defaults = actor_plan_period_db.actor_partner_location_prefs_defaults
for avail_day_db in actor_plan_period_db.avail_days:
    avail_day_db.actor_partner_location_prefs_defaults.clear()
    avail_day_db.actor_partner_location_prefs_defaults.add(defaults)  # Collection auf einmal
```

**Datei:** `database/db_services.py` → `AvailDay.reset_all_avail_days_partner_location_prefs_of_actor_plan_period_to_defaults()`

---

### Engpass 2: Teure Pydantic-Serialisierung für Undo-Daten

**Problem:**
```python
# LANGSAM: Vollständige Pydantic-Schemas nur um IDs zu extrahieren
for avail_day in db_services.AvailDay.get_all_from__actor_plan_period(actor_plan_period_id):
    self.existing_ids[avail_day.id] = [pref.id for pref in avail_day.actor_partner_location_prefs_defaults]
```

Die Methode `get_all_from__actor_plan_period()` erzeugt für **jeden AvailDay** ein vollständiges `AvailDayShow`-Pydantic-Schema mit allen verschachtelten Relationen (Skills, TimeOfDays, CombLocPossibles, etc.) – obwohl nur IDs benötigt werden.

**Lösung:** Dedizierte leichtgewichtige Methode, die nur IDs liefert:
```python
# SCHNELL: Nur IDs ohne Pydantic-Serialisierung
@classmethod
@db_session
def get_ids_per_avail_day_of_actor_plan_period(cls, actor_plan_period_id: UUID) -> dict[UUID, list[UUID]]:
    """Liefert nur die IDs der Partner-Location-Prefs pro AvailDay – ohne teure Pydantic-Serialisierung."""
    actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
    return {
        avail_day_db.id: [pref.id for pref in avail_day_db.actor_partner_location_prefs_defaults]
        for avail_day_db in actor_plan_period_db.avail_days
    }
```

**Datei:** `database/db_services.py` → Neue Methode in der entsprechenden Service-Klasse (z.B. `ActorPartnerLocationPref`)

---

### Engpass 3: Doppelter DB-Load nach `flush()`

**Problem:**
```python
flush()
actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)  # ÜBERFLÜSSIG!
return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)
```

Nach `flush()` ist das Objekt im Pony-ORM-Cache bereits aktualisiert (Identity-Map-Pattern).

**Lösung:** Zweiten Load eliminieren:
```python
flush()
# Kein erneutes get_for_update nötig – Cache ist aktuell
return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)
```

---

### Engpass 4: `model_validate()` am Ende der DB-Methode (GRÖSSTER EFFEKT: 96,5% der Zeit!)

**Problem:**
```python
def reset_all_...(cls, actor_plan_period_id: UUID) -> schemas.ActorPlanPeriodShow:
    # ... DB-Operationen ...
    flush()
    return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)  # 3,5 SEKUNDEN!
```

Die Pydantic-Serialisierung des gesamten Objektgraphen (ActorPlanPeriod → alle AvailDays → jeweils alle verschachtelten Sets) dauert extrem lange.

**Lösung:** DB-Methode gibt nichts zurück, GUI patcht bestehendes Schema in-place:

**db_services.py:**
```python
def reset_all_...(cls, actor_plan_period_id: UUID) -> None:  # Kein Return!
    # ... DB-Operationen ...
    flush()
    # KEIN model_validate!
```

**GUI-Schicht (frm_actor_plan_period.py):**
```python
def handle_reset():
    # In-place Patch: bestehende Pydantic-Schemas aktualisieren
    defaults = list(self.actor_plan_period.actor_partner_location_prefs_defaults)
    for avail_day in self.actor_plan_period.avail_days:
        if not avail_day.prep_delete:
            avail_day.actor_partner_location_prefs_defaults = list(defaults)
    refresh_ui()
```

**Wichtig:** Das funktioniert, weil die Reset-Operation **deterministisch** ist – alle AvailDay-Prefs werden auf die ActorPlanPeriod-Defaults gesetzt. Wir wissen genau, was sich ändert.

---

## Vollständige Architektur nach Optimierung

### 1. DB-Service-Schicht (`database/db_services.py`)

```python
class AvailDay:
    @classmethod
    @db_session(sql_debug=LOGGING_ENABLED, show_values=LOGGING_ENABLED)
    def reset_all_avail_days_partner_location_prefs_of_actor_plan_period_to_defaults(
            cls, actor_plan_period_id: UUID) -> None:  # ← Kein Return mehr!
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        defaults = actor_plan_period_db.actor_partner_location_prefs_defaults
        for avail_day_db in actor_plan_period_db.avail_days:
            avail_day_db.actor_partner_location_prefs_defaults.clear()
            avail_day_db.actor_partner_location_prefs_defaults.add(defaults)  # Bulk-Add!
        # Kein flush() nötig – passiert automatisch am Ende der db_session
        # Kein model_validate – GUI macht In-Place-Patch


class ActorPartnerLocationPref:
    @classmethod
    @db_session
    def get_ids_per_avail_day_of_actor_plan_period(cls, actor_plan_period_id: UUID) -> dict[UUID, list[UUID]]:
        """Liefert nur die IDs der Partner-Location-Prefs pro AvailDay – ohne teure Pydantic-Serialisierung."""
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        return {
            avail_day_db.id: [pref.id for pref in avail_day_db.actor_partner_location_prefs_defaults]
            for avail_day_db in actor_plan_period_db.avail_days
        }
```

### 2. Command-Schicht (`commands/database_commands/avail_day_commands.py`)

```python
class ResetAllAvailDaysActorPartnerLocationPrefsToDefaults(Command):
    def __init__(self, actor_plan_period_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        # Leichtgewichtige ID-Abfrage für Undo-Daten (keine Pydantic-Serialisierung!)
        self.existing_actor_partner_loc_pref_ids_per_avail_day: dict[UUID, list[UUID]] = (
            db_services.ActorPartnerLocationPref.get_ids_per_avail_day_of_actor_plan_period(
                self.actor_plan_period_id)
        )
        # KEIN actor_plan_period_new mehr – GUI macht In-Place-Patch

    def execute(self):
        # Nur DB-Mutation, kein Return-Wert
        db_services.AvailDay.reset_all_avail_days_partner_location_prefs_of_actor_plan_period_to_defaults(
            self.actor_plan_period_id)

    def _undo(self):
        for avail_day_id, actor_partner_loc_pref_ids in self.existing_actor_partner_loc_pref_ids_per_avail_day.items():
            db_services.AvailDay.clear_partner_location_prefs(avail_day_id)
            db_services.AvailDay.put_in_partner_location_prefs(avail_day_id, actor_partner_loc_pref_ids)

    def _redo(self):
        db_services.AvailDay.reset_all_avail_days_partner_location_prefs_of_actor_plan_period_to_defaults(
            self.actor_plan_period_id)
```

### 3. GUI-Schicht (`gui/frm_actor_plan_period.py`)

```python
def reset_all_partner_loc_prefs(self, e):
    """Setzt actor_partner_location_prefs aller AvailDays in dieser Planperiode auf die Werte der Planperiode zurück."""

    def refresh_ui():
        """Gemeinsamer UI-Refresh für Execute, Undo und Redo."""
        button_partner_location_prefs: list[ButtonPartnerPreferences] = self.findChildren(ButtonPartnerPreferences)
        for button_partner_location_pref in button_partner_location_prefs:
            if button_partner_location_pref.date in all_avail_dates:
                button_partner_location_pref.refresh(signal_handling.DataActorPPWithDate(self.actor_plan_period))
        self.set_instance_variables()
        signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)

    def handle_reset():
        """Callback für Execute und Redo – schnelles In-Place-Patching."""
        # In-place Patch: bestehende Pydantic-Schemas aktualisieren
        defaults = list(self.actor_plan_period.actor_partner_location_prefs_defaults)
        for avail_day in self.actor_plan_period.avail_days:
            if not avail_day.prep_delete:
                avail_day.actor_partner_location_prefs_defaults = list(defaults)
        # Undo/Redo-History geöffneter Pläne OHNE Warnung löschen
        warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end, show_warning=False)
        refresh_ui()

    def handle_undo():
        """Callback für Undo – muss aus DB laden (individuelle Original-Werte)."""
        # Bei Undo: DB-Reload nötig, da Original-Werte individuell pro AvailDay
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
        warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end, show_warning=False)
        refresh_ui()

    # --- User-Interaktion ---
    reply = QMessageBox.question(self, self.tr('Reset Partner Preferences'), ...)
    if reply != QMessageBox.StandardButton.Yes:
        return

    # Warnung für Undo/Redo VOR den Änderungen (MIT Dialog)
    plan_period = self.actor_plan_period.plan_period
    if not warn_and_clear_undo_redo_if_plans_open(
        self, plan_period.id, plan_period.start, plan_period.end
    ):
        return

    all_avail_dates = {avd.date for avd in self.actor_plan_period.avail_days if not avd.prep_delete}
    if not all_avail_dates:
        QMessageBox.critical(...)
        return

    # --- Ausführung ---
    self._reset_all_avail_days_partner_location_prefs_to_defaults(
        on_undo_callback=handle_undo, on_redo_callback=handle_reset)
    handle_reset()  # Initiales In-Place-Patching + UI-Refresh


def _reset_all_avail_days_partner_location_prefs_to_defaults(
        self, on_undo_callback=None, on_redo_callback=None) -> None:
    """Setzt Partner/Standort-Präferenzen für alle AvailDays der ActorPlanPeriod auf Defaults zurück."""
    command = avail_day_commands.ResetAllAvailDaysActorPartnerLocationPrefsToDefaults(self.actor_plan_period.id)
    self.controller.execute(command)
    command.on_undo_callback = on_undo_callback
    command.on_redo_callback = on_redo_callback
```

---

## Hilfsfunktion: `warn_and_clear_undo_redo_if_plans_open()`

Die Funktion wurde um den Parameter `show_warning=True` erweitert:

```python
def warn_and_clear_undo_redo_if_plans_open(
    parent_widget: QWidget,
    plan_period_id: UUID,
    plan_period_start: datetime.date,
    plan_period_end: datetime.date,
    on_cancel: Callable[[], None] | None = None,
    show_warning: bool = True  # NEU: Bei False wird ohne Dialog gelöscht
) -> bool:
```

**Verwendung:**
- `show_warning=True` (Default): Zeigt Dialog, User kann abbrechen → für initiales Execute
- `show_warning=False`: Löscht History still → für Undo/Redo-Callbacks

**Datei:** `tools/helper_functions.py`

---

## Checkliste für andere Config-Buttons

Wenn du eine andere "Reset All"-Operation optimieren willst (z.B. `reset_all_loc_prefs`, `reset_all_comb_loc_possible`), prüfe diese Punkte:

### 1. DB-Service-Methode
- [ ] Verwendet Bulk-`.add()` statt Schleife mit einzelnen `.add()`-Aufrufen?
- [ ] Kein redundanter zweiter `get_for_update()` nach `flush()`?
- [ ] Gibt `None` zurück statt `model_validate()` (wenn GUI In-Place-Patching macht)?

### 2. Command-Klasse
- [ ] Nutzt leichtgewichtige ID-Abfrage für Undo-Daten (keine vollständige Pydantic-Serialisierung)?
- [ ] Speichert kein `..._new`-Attribut (wenn GUI In-Place-Patching macht)?

### 3. GUI-Methode
- [ ] Hat `refresh_ui()` als gemeinsame Funktion für Execute/Undo/Redo?
- [ ] Hat `handle_reset()` für Execute + Redo mit In-Place-Patching?
- [ ] Hat `handle_undo()` für Undo mit DB-Reload (wenn Original-Werte individuell)?
- [ ] Übergibt Callbacks an Helper-Methode und setzt sie auf Command?
- [ ] Verwendet `show_warning=False` in Undo/Redo-Callbacks?

### 4. Leichtgewichtige ID-Abfrage
- [ ] Existiert eine Methode wie `get_ids_per_avail_day_of_...()` für die Undo-Daten?
- [ ] Greift direkt auf DB-Objekte zu (keine Pydantic-Schemas)?

---

## Wann ist In-Place-Patching möglich?

In-Place-Patching des Pydantic-Schemas ist nur möglich, wenn die Operation **deterministisch** ist – d.h. wir wissen genau, welche Werte nach der Operation im Schema stehen:

| Operation | In-Place-Patching möglich? | Grund |
|---|---|---|
| Reset all to defaults | ✅ Ja | Alle Werte = Defaults der übergeordneten Entität |
| Add single item | ✅ Ja | Neues Item ist bekannt |
| Remove single item | ✅ Ja | Entferntes Item ist bekannt |
| Complex update | ❌ Nein | Ergebnis hängt von DB-Logik ab |

Wenn In-Place-Patching nicht möglich ist, muss die DB-Methode weiterhin das aktualisierte Schema zurückgeben – aber die anderen Optimierungen (Bulk-Add, leichtgewichtige IDs) sind trotzdem anwendbar.

---

## Performance-Messung mit Line-Profiler

Um die Performance zu messen, verwende den `@line_profiler.profile`-Decorator:

```python
import line_profiler

@line_profiler.profile
def reset_all_partner_loc_prefs(self, e):
    ...
```

Starte die Anwendung mit:
```bash
kernprof -l -v main.py
```

Oder schreibe das Profil in eine Datei:
```bash
kernprof -l main.py
python -m line_profiler -rmt profile_output.lprof > profile_output.txt
```

---

## Zusammenfassung der geänderten Dateien

| Datei | Änderungen |
|---|---|
| `database/db_services.py` | Bulk-Add, kein model_validate, neue ID-Abfrage-Methode |
| `commands/database_commands/avail_day_commands.py` | Leichtgewichtige ID-Abfrage, kein `..._new`-Attribut |
| `gui/frm_actor_plan_period.py` | In-Place-Patching, Callbacks mit show_warning=False |
| `tools/helper_functions.py` | `show_warning`-Parameter für `warn_and_clear_undo_redo_if_plans_open()` |
