# BaseConfigButton Migration

Dokumentation der Refactoring-Migration zur Extraktion einer gemeinsamen Basisklasse für Config-Buttons in `gui/frm_actor_plan_period.py`.

**Datum:** Januar 2026
**Status:** Abgeschlossen

---

## Inhaltsverzeichnis

1. [Übersicht](#übersicht)
2. [Motivation](#motivation)
3. [Architektur](#architektur)
4. [Migrierte Klassen](#migrierte-klassen)
5. [Eliminierte Duplizierung](#eliminierte-duplizierung)
6. [Verwendung der Basisklasse](#verwendung-der-basisklasse)
7. [Empfehlungen für zukünftige Arbeit](#empfehlungen-für-zukünftige-arbeit)

---

## Übersicht

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `gui/custom_widgets/base_config_button.py` | **NEU** - 217 Zeilen |
| `gui/custom_widgets/__init__.py` | Export von `BaseConfigButton` hinzugefügt |
| `gui/frm_actor_plan_period.py` | 4 Klassen auf `BaseConfigButton` migriert |

### Migrierte Klassen

| Klasse | Basisklasse vorher | Basisklasse nachher |
|--------|-------------------|---------------------|
| `ButtonCombLocPossible` | `QPushButton` | `BaseConfigButton` |
| `ButtonActorLocationPref` | `QPushButton` | `BaseConfigButton` |
| `ButtonActorPartnerLocationPref` | `QPushButton` | `BaseConfigButton` |
| `ButtonSkills` | `QPushButton` | `BaseConfigButton` |
| `ButtonAvailDay` | `QPushButton` | `QPushButton` (unverändert) |

---

## Motivation

### Problem: Code-Duplizierung

Die 4 Config-Button-Klassen in `frm_actor_plan_period.py` hatten erhebliche Code-Duplizierung:

- **Konstruktor-Code:** Größen-Einstellungen (4 Zeilen × 4 Klassen)
- **`set_stylesheet()`:** 3-Zustands-Logik (20 Zeilen × 4 Klassen)
- **`reload_actor_plan_period()`:** Identisch in allen 4 Klassen (11 Zeilen × 4)
- **`avail_days_at_date()`:** Identisch in 3 Klassen (2 Zeilen × 3)

### Lösung: Template Method Pattern

Eine gemeinsame Basisklasse `BaseConfigButton` implementiert das **Template Method Pattern**:
- Gemeinsame Logik in der Basisklasse
- Unterklassen implementieren nur die spezifischen Teile
- Hooks für optionale Erweiterungen

---

## Architektur

### Klassendiagramm

```
QPushButton
    │
    └── BaseConfigButton (gui/custom_widgets/base_config_button.py)
        │
        │   Template Methods (abstrakt):
        │   ├── _get_check_result() -> bool | None
        │   └── _get_class_name() -> str
        │
        │   Optionale Hooks:
        │   ├── _connect_signals()
        │   ├── _setup_tooltip()
        │   └── _on_stylesheet_updated()
        │
        │   Gemeinsame Implementierungen:
        │   ├── set_stylesheet()
        │   ├── avail_days_at_date()
        │   └── reload_actor_plan_period()
        │
        ├── ButtonCombLocPossible
        ├── ButtonActorLocationPref
        ├── ButtonActorPartnerLocationPref
        └── ButtonSkills
```

### 3-Zustands-Stylesheet-Logik

Die Basisklasse implementiert eine einheitliche 3-Zustands-Logik für das Styling:

| `_get_check_result()` | Farbe | Bedeutung |
|-----------------------|-------|-----------|
| `None` | Gelb (`#fff4d6`) | Keine Daten vorhanden |
| `True` | Grün (`#acf49f`) | Alle Werte entsprechen Defaults |
| `False` | Rot (`#f4b2a5`) | Abweichungen von Defaults |

---

## Migrierte Klassen

### ButtonCombLocPossible

**Funktion:** Button für Standort-Kombinationen pro Tag

**Template-Implementierungen:**
```python
def _get_check_result(self) -> bool | None:
    return self._check_comb_of_day__eq__comb_of_actor_pp()

def _get_class_name(self) -> str:
    return "ButtonCombLocPossible"

def _setup_tooltip(self) -> None:
    self.setToolTip(self.tr('Location combinations on %s') % date_to_string(self.date))
```

---

### ButtonActorLocationPref

**Funktion:** Button für Standort-Präferenzen pro Tag

**Besonderheit:** Hat zusätzliches `team`-Attribut

**Template-Implementierungen:**
```python
def _get_check_result(self) -> bool | None:
    return self._check_loc_pref_of_day__eq__loc_pref_of_actor_pp()

def _get_class_name(self) -> str:
    return "ButtonActorLocationPref"
```

---

### ButtonActorPartnerLocationPref

**Funktion:** Button für Mitarbeiter/Standort-Präferenzen pro Tag

**Besonderheit:** Hat zusätzliches `team`-Attribut

**Template-Implementierungen:**
```python
def _get_check_result(self) -> bool | None:
    return self._check_pref_of_day__eq__pref_of_actor_pp()

def _get_class_name(self) -> str:
    return "ButtonActorPartnerLocationPref"
```

---

### ButtonSkills

**Funktion:** Button für Skills pro Tag

**Besonderheiten:**
- Verwendet `set_stylesheet_and_tooltip()` statt nur `set_stylesheet()`
- Hat eigenes Signal `signal_reset_styling_skills_configs`
- Verwendet `clicked.connect()` statt `mouseReleaseEvent()`
- Cached `avail_days_at_day` vor dem Check

**Template-Implementierungen:**
```python
def _get_check_result(self) -> bool | None:
    all_equal = self._check_skills_all_equal()
    if all_equal is None:
        return None
    if all_equal and self._check_skills_all_equal_to_person_skills():
        return True
    return False

def _get_class_name(self) -> str:
    return "ButtonSkills"

def _connect_signals(self) -> None:
    signal_handling.handler_actor_plan_period.signal_reset_styling_skills_configs.connect(
        self._reset_stylesheet_and_tooltip)

def _on_stylesheet_updated(self) -> None:
    self._update_tooltip()
```

**Überschriebene Methoden:**
```python
def set_stylesheet(self) -> None:
    self._load_avail_days_at_day()  # Caching vor Check
    super().set_stylesheet()

def reload_actor_plan_period(self, data=None) -> None:
    # Ruft set_stylesheet_and_tooltip() statt nur set_stylesheet()
```

---

## Eliminierte Duplizierung

### Quantitative Übersicht

| Code-Block | Vorher (Zeilen) | Nachher (Zeilen) | Ersparnis |
|------------|-----------------|------------------|-----------|
| `setMaximum/MinimumWidth/Height` | 4 × 4 = 16 | 4 (in Basis) | 12 |
| `setAttribute(WA_DeleteOnClose)` | 4 × 1 = 4 | 1 (in Basis) | 3 |
| Signal-Verbindung | 4 × 2 = 8 | 2 (in Basis) | 6 |
| `set_stylesheet()` | 4 × 20 = 80 | 15 (in Basis) | 65 |
| `avail_days_at_date()` | 3 × 2 = 6 | 3 (in Basis) | 3 |
| `reload_actor_plan_period()` | 4 × 11 = 44 | 10 (in Basis) | 34 |
| **Gesamt** | **158** | **35** | **~123** |

### Qualitative Verbesserungen

1. **Single Point of Change:** Stylesheet-Logik nur noch an einer Stelle
2. **Konsistenz:** Alle 4 Klassen folgen exakt dem gleichen Muster
3. **Erweiterbarkeit:** Neue Config-Buttons brauchen nur 3 Template-Methods
4. **Testbarkeit:** Basisklasse kann unabhängig getestet werden

---

## Verwendung der Basisklasse

### Minimale Implementierung

```python
from gui.custom_widgets import BaseConfigButton

class ButtonMyConfig(BaseConfigButton):
    def __init__(self, parent, date, width_height, actor_plan_period):
        super().__init__(parent, date, width_height, actor_plan_period)
        self.setObjectName(f'my_config: {date}')

    def _get_check_result(self) -> bool | None:
        # Implementiere deine Check-Logik
        # Return: None (keine Daten), True (default), False (abweichend)
        pass

    def _get_class_name(self) -> str:
        return "ButtonMyConfig"

    def _setup_tooltip(self) -> None:
        self.setToolTip(f'My config on {self.date}')
```

### Mit zusätzlichen Features

```python
class ButtonMyAdvancedConfig(BaseConfigButton):
    def __init__(self, parent, date, width_height, actor_plan_period, extra_data):
        # Eigene Attribute VOR super().__init__() setzen!
        self.extra_data = extra_data

        super().__init__(parent, date, width_height, actor_plan_period)
        self.setObjectName(f'advanced_config: {date}')

    def _connect_signals(self) -> None:
        # Zusätzliche Signal-Verbindungen
        signal_handling.my_signal.connect(self.my_handler)

    def _on_stylesheet_updated(self) -> None:
        # Wird nach jedem set_stylesheet() aufgerufen
        self._update_my_tooltip()
```

### Konstruktor-Parameter

| Parameter | Typ | Beschreibung |
|-----------|-----|--------------|
| `parent` | `QWidget` | Parent-Widget |
| `date` | `datetime.date` | Datum für diesen Button |
| `width_height` | `int` | Größe des quadratischen Buttons |
| `actor_plan_period` | `ActorPlanPeriodShow` | ActorPlanPeriod-Daten |
| `connect_to_avail_configs_signal` | `bool` (default: `True`) | Ob Standard-Signal verbunden werden soll |

---

## Empfehlungen für zukünftige Arbeit

### 1. Manuelle Tests

Die GUI sollte nach der Migration manuell getestet werden:

- [ ] ButtonCombLocPossible: Klick öffnet Dialog, Farben korrekt
- [ ] ButtonActorLocationPref: Klick öffnet Dialog, Farben korrekt
- [ ] ButtonActorPartnerLocationPref: Klick öffnet Dialog, Farben korrekt
- [ ] ButtonSkills: Klick öffnet Dialog, Tooltip aktualisiert sich

### 2. Weitere Migration: frm_location_plan_period.py

Die Datei `gui/frm_location_plan_period.py` enthält ähnliche Button-Klassen:

- `ButtonFixedCast`
- `ButtonNotes`
- `ButtonSkillGroups`

Diese könnten mit einer analogen Basisklasse `BaseLocationConfigButton` migriert werden, die `location_plan_period` statt `actor_plan_period` verwendet.

### 3. Performance-Optimierung

Bei Bedarf könnte die Basisklasse um Caching erweitert werden:

```python
# Mögliche Erweiterung für Caching
def set_stylesheet(self) -> None:
    if self._cached_check_result is not None:
        check_result = self._cached_check_result
    else:
        check_result = self._get_check_result()
    # ...
```

### 4. Unit Tests

Die Basisklasse könnte mit Unit Tests abgedeckt werden:

```python
# tests/test_base_config_button.py
def test_stylesheet_none_state():
    """Test dass None-Ergebnis standard_colors verwendet."""
    pass

def test_stylesheet_true_state():
    """Test dass True-Ergebnis all_properties_are_default verwendet."""
    pass

def test_stylesheet_false_state():
    """Test dass False-Ergebnis any_properties_are_different verwendet."""
    pass
```

---

## Änderungshistorie

| Datum | Änderung |
|-------|----------|
| 2026-01-24 | Initiale Migration abgeschlossen |

---

## Referenzen

- **Template Method Pattern:** [Design Patterns - GoF](https://refactoring.guru/design-patterns/template-method)
- **Qt Stylesheets:** [Qt Documentation](https://doc.qt.io/qt-6/stylesheet.html)
