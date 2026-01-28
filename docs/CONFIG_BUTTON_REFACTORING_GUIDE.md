# Config-Button Refactoring Guide

**Erstellt:** 2026-01-25
**Anwendbar auf:** Button-Klassen die von `BaseConfigButton` erben
**Referenz-Implementierung:** `gui/frm_actor_plan_period.py`

---

## Übersicht

Dieses Dokument beschreibt das Refactoring-Pattern für Config-Button-Klassen, die das `BaseConfigButton` Template Method Pattern verwenden. Es dient als Anleitung für das Refactoring ähnlicher Button-Klassen in anderen Modulen (z.B. `frm_location_plan_period.py`).

### Ziele des Refactorings

1. **CQS-Prinzip einhalten**: Check-Methoden sind reine Queries ohne Seiteneffekte
2. **Einheitliche Event-Handler**: `clicked.connect()` statt `mouseReleaseEvent()`
3. **Klarere Methodennamen**: Beschreibende Namen statt Abkürzungen
4. **Automatische Klassennamen**: Kein manuelles Überschreiben von `_get_class_name()`

---

## Architektur: BaseConfigButton

```
BaseConfigButton (QPushButton)
├── Template Methods (abstrakt - MÜSSEN implementiert werden)
│   └── _check_matches_defaults() -> bool | None
│
├── Hooks (optional - können überschrieben werden)
│   ├── _ensure_consistency()      # Konsistenz vor Check herstellen
│   ├── _connect_signals()         # Zusätzliche Signal-Verbindungen
│   ├── _setup_tooltip()           # Tooltip initialisieren
│   └── _on_stylesheet_updated()   # Nach Stylesheet-Aktualisierung
│
└── Gemeinsame Implementierungen
    ├── set_stylesheet()           # 3-Zustands-Logik (gelb/grün/rot)
    ├── refresh()                  # Daten laden + Stylesheet aktualisieren
    └── avail_days_at_date()       # Query für AvailDays am Datum
```

### 3-Zustands-Stylesheet-Logik

| Rückgabewert | Farbe | Bedeutung |
|--------------|-------|-----------|
| `None` | Gelb | Keine Daten vorhanden |
| `True` | Grün | Alle Werte entsprechen Defaults |
| `False` | Rot | Abweichungen von Defaults |

---

## Refactoring-Schritte

### Phase 1: CQS-Trennung

**Problem:** Check-Methoden führen Seiteneffekte aus (DB-Writes, MessageBox)

**Lösung:** Trennung in drei Methoden:

```python
# VORHER (CQS-Verletzung)
def _check_something(self) -> bool | None:
    if self._has_problem():
        self._fix_problem()  # ← Seiteneffekt!
        QMessageBox.critical(...)  # ← Seiteneffekt!
        return True
    return self._matches_defaults()

# NACHHER (CQS-konform)
def _ensure_consistency(self) -> None:
    """Hook: Stellt Konsistenz her BEVOR Check läuft."""
    if self._has_internal_inconsistency(self.avail_days_at_date()):
        self._reset_to_defaults()
        QMessageBox.critical(...)

def _has_internal_inconsistency(self, avail_days: list) -> bool:
    """Reine Query: Prüft ob Daten inkonsistent sind."""
    # Nur prüfen, KEINE Änderungen
    return ...

def _check_matches_defaults(self) -> bool | None:
    """Reine Query: Prüft ob Daten den Defaults entsprechen."""
    # Nur prüfen, KEINE Änderungen
    return ...
```

#### Implementierungsdetails

1. **`_ensure_consistency()`** in Unterklasse implementieren:
```python
def _ensure_consistency(self) -> None:
    avail_days_at_date = self.avail_days_at_date()
    if not avail_days_at_date:
        return

    if self._has_internal_inconsistency(avail_days_at_date):
        self._reset_to_defaults(avail_days_at_date)
        QMessageBox.critical(
            self, self.tr('Titel'),
            self.tr('Die Einstellungen wurden zurückgesetzt.')
        )
```

2. **`_has_internal_inconsistency()`** hinzufügen:
```python
def _has_internal_inconsistency(self, avail_days: list) -> bool:
    """Prüft ob AvailDays am Tag untereinander inkonsistent sind."""
    if len(avail_days) <= 1:
        return False
    first_values = {x.id for x in avail_days[0].some_property}
    for avd in avail_days[1:]:
        if {x.id for x in avd.some_property} != first_values:
            return True
    return False
```

3. **`_reset_to_defaults()`** implementieren:
```python
def _reset_to_defaults(self, avail_days: list | None = None) -> None:
    """Setzt alle AvailDays auf Defaults zurück."""
    if not avail_days:
        avail_days = self.avail_days_at_date()

    for avd in avail_days:
        # Alte Werte entfernen
        for item in avd.some_property:
            db_services.AvailDay.remove_something(avd.id, item.id)
        # Default-Werte setzen
        for default in self.actor_plan_period.default_property:
            db_services.AvailDay.add_something(avd.id, default.id)
```

---

### Phase 2: Methodenumbenennung

| Alt | Neu | Begründung |
|-----|-----|------------|
| `_get_check_result()` | `_check_matches_defaults()` | Klarere Semantik |
| `_get_class_name()` | **ENTFERNEN** | `self.__class__.__name__` in Basis |
| `reload_actor_plan_period()` | `refresh()` | Beschreibt die Aktion besser |

#### Änderung 1: `_get_class_name()` eliminieren

**VORHER:**
```python
def _get_class_name(self) -> str:
    return "ButtonCombLocPossible"  # Hardcoded, fehleranfällig
```

**NACHHER:**
```python
# In BaseConfigButton.set_stylesheet():
class_name = self.__class__.__name__  # Automatisch!

# In Unterklasse: Methode komplett ENTFERNEN
```

#### Änderung 2: `reload_actor_plan_period()` → `refresh()`

Die Basisklasse bietet jetzt `refresh()` an. Falls eine Unterklasse
spezielle Logik benötigt:

```python
@Slot(signal_handling.DataActorPPWithDate)
def refresh(self, data: signal_handling.DataActorPPWithDate | None = None) -> None:
    """Überschrieben für spezielle Logik."""
    if data is None:
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
        self.set_stylesheet_and_tooltip()  # Spezielle Methode
    elif data.actor_plan_period.id == self.actor_plan_period.id:
        if data.date is None or data.date == self.date:
            self.actor_plan_period = data.actor_plan_period
            self.set_stylesheet_and_tooltip()
```

---

### Phase 3: Event-Handler vereinheitlichen

**Problem:** `mouseReleaseEvent()` reagiert auf JEDEN Mausklick

**Lösung:** `clicked.connect()` im Konstruktor

**VORHER:**
```python
def __init__(self, ...):
    super().__init__(...)
    # Kein expliziter Klick-Handler

def mouseReleaseEvent(self, e) -> None:
    """Öffnet Dialog..."""
    # Dialog-Logik
```

**NACHHER:**
```python
def __init__(self, ...):
    super().__init__(...)

    # Klick-Handler für Dialog-Öffnung
    self.clicked.connect(self._open_edit_dialog)

def _open_edit_dialog(self) -> None:
    """Öffnet Dialog..."""
    # Dialog-Logik (identisch, nur umbenannt)
```

---

### Phase 4: Klassennamen-Umbenennung

Empfohlene Namenskonventionen:

| Alt (Abkürzungen) | Neu (Klar) |
|-------------------|------------|
| `ButtonCombLocPossible` | `ButtonLocationCombinations` |
| `ButtonActorLocationPref` | `ButtonLocationPreferences` |
| `ButtonActorPartnerLocationPref` | `ButtonPartnerPreferences` |
| `ButtonLocPlanPeriodXxx` | `ButtonXxxSettings` |

**Wichtig:** Da `self.__class__.__name__` verwendet wird, werden
CSS-Selektoren automatisch aktualisiert!

---

## Checkliste für Refactoring

### Vor dem Start
- [ ] Aktuelle Klassen identifizieren die refaktoriert werden sollen
- [ ] Bestehende Tests (falls vorhanden) sicherstellen

### Phase 1: CQS-Trennung
- [ ] `_ensure_consistency()` implementieren
- [ ] `_has_internal_inconsistency()` implementieren
- [ ] `_reset_to_defaults()` implementieren (oder umbenennen)
- [ ] Seiteneffekte aus `_check_*()` Methoden entfernen
- [ ] `_check_*()` als reine Query verifizieren

### Phase 2: Methodenumbenennung
- [ ] `_get_check_result()` → `_check_matches_defaults()` umbenennen
- [ ] `_get_class_name()` komplett entfernen
- [ ] `reload_*()` → `refresh()` umbenennen (falls überschrieben)
- [ ] Redundante `set_stylesheet()` Aufrufe nach `refresh()` entfernen

### Phase 3: Event-Handler
- [ ] `mouseReleaseEvent()` → `_open_edit_dialog()` umbenennen
- [ ] `self.clicked.connect(self._open_edit_dialog)` im `__init__` hinzufügen

### Phase 4: Klassennamen
- [ ] Klasse umbenennen (klarerer Name)
- [ ] Alle Referenzen aktualisieren (`findChildren()`, Typ-Hints, etc.)
- [ ] Dokumentation aktualisieren

### Nach dem Refactoring
- [ ] Syntax-Prüfung: `python -m py_compile <datei>`
- [ ] Manueller Test: Buttons anklicken, Stylesheet-Farben prüfen
- [ ] Auto-Reset bei Inkonsistenzen testen (falls zutreffend)

---

## Beispiel: Vollständige Button-Klasse nach Refactoring

```python
class ButtonLocationCombinations(BaseConfigButton):
    """Button für Standort-Kombinationen pro Tag.

    Zeigt an, ob die Standort-Kombinationen am jeweiligen Tag den Defaults
    der ActorPlanPeriod entsprechen.
    """

    def __init__(self, parent, date: datetime.date, width_height: int,
                 actor_plan_period: schemas.ActorPlanPeriodShow):
        self.person: schemas.PersonShow | None = None

        super().__init__(parent, date, width_height, actor_plan_period)
        self.setObjectName(f'comb_loc_poss: {date}')

        # Klick-Handler für Dialog-Öffnung
        self.clicked.connect(self._open_edit_dialog)

    # === Template Method Implementierungen ===

    def _check_matches_defaults(self) -> bool | None:
        """Prüft ob Standort-Kombinationen den Defaults entsprechen (reine Query)."""
        return self._check_combinations_match_defaults()

    def _setup_tooltip(self) -> None:
        self.setToolTip(self.tr('Location combinations on %s') % date_to_string(self.date))

    # === CQS-konforme Methoden ===

    def _ensure_consistency(self) -> None:
        """Prüft auf Inkonsistenzen und resettet bei Bedarf."""
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            return

        if self._has_internal_inconsistency(avail_days_at_date):
            self._reset_to_defaults(avail_days_at_date)
            QMessageBox.critical(
                self, self.tr('Location Combinations'),
                self.tr('Settings have been reset to defaults.')
            )

    def _has_internal_inconsistency(self, avail_days: list) -> bool:
        """Prüft ob AvailDays untereinander inkonsistent sind (reine Query)."""
        if len(avail_days) <= 1:
            return False
        first = {c.id for c in avail_days[0].combination_locations_possibles}
        return any(
            {c.id for c in avd.combination_locations_possibles} != first
            for avd in avail_days[1:]
        )

    def _check_combinations_match_defaults(self) -> bool | None:
        """Prüft ob Kombinationen den Defaults entsprechen (reine Query)."""
        avail_days = self.avail_days_at_date()
        if not avail_days:
            return None
        current = {c.id for c in avail_days[0].combination_locations_possibles}
        defaults = {c.id for c in self.actor_plan_period.combination_locations_possibles}
        return current == defaults

    def _reset_to_defaults(self, avail_days: list | None = None) -> None:
        """Setzt Kombinationen auf Defaults zurück."""
        if not avail_days:
            avail_days = self.avail_days_at_date()

        for avd in avail_days:
            for comb in avd.combination_locations_possibles:
                db_services.AvailDay.remove_comb_loc_possible(avd.id, comb.id)
            for comb in self.actor_plan_period.combination_locations_possibles:
                db_services.AvailDay.put_in_comb_loc_possible(avd.id, comb.id)

    # === Dialog-Handler ===

    def _open_edit_dialog(self) -> None:
        """Öffnet den Bearbeitungsdialog."""
        avail_days = self.avail_days_at_date()
        if not avail_days:
            QMessageBox.critical(self, self.tr('Error'),
                                 self.tr('No availability selected.'))
            return

        # Dialog-Logik...
        dlg = SomeDialog(self, avail_days[0])
        if dlg.exec():
            # Änderungen verarbeiten...
            self.refresh()
```

---

## Bekannte Pyright-Warnungen

Die folgenden Warnungen sind **bestehende Probleme** im Codebase und
werden **nicht** durch dieses Refactoring verursacht:

- `Cannot access attribute "tr" for class "*Button*"` - Qt's `tr()` wird
  von Pyright nicht erkannt
- `"date" is not assignable to "QDate"` - Typ-Inkompatibilität zwischen
  Python `date` und Qt `QDate`

Diese können ignoriert werden, da sie zur Laufzeit funktionieren.

---

## Referenzen

- **Refaktorierte Dateien:**
  - `gui/custom_widgets/base_config_button.py`
  - `gui/frm_actor_plan_period.py`

- **Button-Klassen (nach Refactoring):**
  - `ButtonLocationCombinations`
  - `ButtonLocationPreferences`
  - `ButtonPartnerPreferences`
  - `ButtonSkills`
