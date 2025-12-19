# Command-Tooltips für Undo/Redo-Buttons

## Übersicht

Dieses Dokument beschreibt die Implementierung der Tooltip-Funktion für Undo/Redo-Buttons, die dem Nutzer beim Hover anzeigt, welche Aktion rückgängig gemacht oder wiederhergestellt wird.

## Architektur

### 1. Command-Beschreibungen (`__str__()` Methoden)

Jede Command-Klasse implementiert eine `__str__()` Methode, die eine menschenlesbare Beschreibung der Aktion zurückgibt.

#### Beispiel: UpdateAvailDays

```python
class UpdateAvailDays(Command):
    def __str__(self) -> str:
        try:
            event_date = self.appointment.event.date
            event_time_of_day = self.appointment.event.time_of_day.name
            event_location = self.appointment.event.location_plan_period.location_of_work.name_an_city
            cast_new = sorted(avd.actor_plan_period.person.full_name for avd in self.appointment.avail_days)
            cast_old = sorted(avd.actor_plan_period.person.full_name for avd in self.appointment.avail_days)

            return (f"Verfügbarkeitstage ändern für\n"
                    f"{event_location} - {date_to_string(event_date)} ({event_time_of_day}): {cast_old} → {cast_new}")
        except (AttributeError, TypeError):
            return "Verfügbarkeitstage ändern"
```

#### Design-Prinzipien

1. **Kontext-reich**: Zeigt Location, Datum, Uhrzeit
2. **Try-Except**: Verhindert Crashes bei fehlenden Daten
3. **Fallback**: Generische Beschreibung bei Fehler
4. **Mehrzeilig**: Nutzt `\n` für bessere Lesbarkeit
5. **Vorher → Nachher**: Zeigt alte und neue Werte

### 2. BatchCommand mit description-Parameter

`BatchCommand` erhält einen optionalen `description` Parameter für semantische Beschreibungen:

```python
class BatchCommand(Command):
    def __init__(self, parent_window: QWidget, commands: list[Command], description: str | None = None):
        super().__init__()
        self.parent_window = parent_window
        self.commands = commands
        self.description = description  # Optional

    def __str__(self) -> str:
        # 1. Explizite Beschreibung nutzen
        if self.description:
            return self.description

        # 2. Bei einem Command: dessen Beschreibung
        if len(self.commands) == 1:
            return str(self.commands[0])

        # 3. Fallback: Liste der ersten 3 Commands
        descriptions = [str(cmd) for cmd in self.commands[:3]]
        result = "\n".join(f"  • {desc}" for desc in descriptions)

        if len(self.commands) > 3:
            remaining = len(self.commands) - 3
            result += f"\n  ... +{remaining} weitere"

        return result
```

#### Verwendung mit description

```python
# MIT description (empfohlen für bekannte Muster)
event_location = appointment.event.location_plan_period.location_of_work.name_an_city
event_date = date_to_string(appointment.event.date)
event_time = appointment.event.time_of_day.name
description = f"Cast-Änderungen für\n{event_location} - {event_date} ({event_time})"
batch_command = BatchCommand(self, commands_to_batch, description=description)

# OHNE description (automatische Liste)
batch_command = BatchCommand(self, commands_to_batch)
# Tooltip würde zeigen:
#   • Verfügbarkeitstage ändern für...
#   • Gäste ändern für...
```

### 3. Controller mit Stack-Changed-Callback

`ContrExecUndoRedo` benachrichtigt die UI bei jeder Stack-Änderung:

```python
class ContrExecUndoRedo(Invoker):
    def __init__(self):
        self.undo_stack: list[Command] = []
        self.redo_stack: list[Command] = []
        self._on_stacks_changed_callback: Callable[[], None] | None = None

    def set_on_stacks_changed_callback(self, callback: Callable[[], None]):
        """Registriert Callback für Stack-Änderungen (z.B. für Tooltip-Updates)."""
        self._on_stacks_changed_callback = callback

    def _notify_stacks_changed(self):
        """Benachrichtigt über Stack-Änderungen."""
        if self._on_stacks_changed_callback:
            self._on_stacks_changed_callback()

    def execute(self, command: Command):
        command.execute()
        self.redo_stack.clear()
        self.undo_stack.append(command)
        self._notify_stacks_changed()  # Callback nach jedem execute

    def undo(self):
        if not self.undo_stack:
            return
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        self._notify_stacks_changed()  # Callback nach jedem undo

    def redo(self):
        if not self.redo_stack:
            return
        command = self.redo_stack.pop()
        command.redo()
        self.undo_stack.append(command)
        self._notify_stacks_changed()  # Callback nach jedem redo
```

### 4. UI-Integration

Die GUI-Formulare implementieren eine `_update_undo_redo_tooltips()` Methode:

```python
def _update_undo_redo_tooltips(self):
    """Aktualisiert Tooltips der Undo/Redo-Buttons basierend auf den Command-Stacks."""
    # Undo-Tooltip
    undo_command = self.controller.get_recent_undo_command()
    if undo_command:
        undo_text = f"Rückgängig:\n{str(undo_command)}"
        self.bt_undo.setToolTip(undo_text)
        self.bt_undo.setEnabled(True)
    else:
        self.bt_undo.setToolTip("Keine Aktion zum Rückgängigmachen")
        self.bt_undo.setEnabled(False)

    # Redo-Tooltip
    redo_command = self.controller.get_recent_redo_command()
    if redo_command:
        redo_text = f"Wiederholen:\n{str(redo_command)}"
        self.bt_redo.setToolTip(redo_text)
        self.bt_redo.setEnabled(True)
    else:
        self.bt_redo.setToolTip("Keine Aktion zum Wiederholen")
        self.bt_redo.setEnabled(False)
```

#### Registrierung im __init__

```python
# Nach Button-Erstellung
self.bt_undo = QPushButton('Undo')
self.bt_undo.clicked.connect(self._undo_shift_command)
self.bt_redo = QPushButton('Redo')
self.bt_redo.clicked.connect(self._redo_shift_command)

# Callback registrieren
self.controller.set_on_stacks_changed_callback(self._update_undo_redo_tooltips)
self._update_undo_redo_tooltips()  # Initial-Zustand setzen
```

## Implementierte Commands

Die folgenden Command-Klassen haben `__str__()` Methoden:

### appointment_commands.py

| Command | Format |
|---------|--------|
| `UpdateAvailDays` | `"Verfügbarkeitstage ändern für\n{location} - {date} ({time}): {old_cast} → {new_cast}"` |
| `UpdateCurrEvent` | `"Termin verschieben für\n{location} - {old_date} ({old_time}) → {new_date} ({new_time})"` |
| `UpdateGuests` | `"Gäste ändern für\n{location} - {date} ({time}): {old_guests} → {new_guests}"` |
| `UpdateNotes` | `"Notiz ändern für\n{location} - {date} ({time}): {note_preview}"` |

### plan_commands.py

| Command | Format |
|---------|--------|
| `UpdateLocationColumns` | `"Spaltenlayout aktualisieren: {num_locations} Standort(e)"` |

## Neue Command-Klasse hinzufügen

Beim Erstellen einer neuen Command-Klasse sollte eine `__str__()` Methode implementiert werden:

```python
class MyNewCommand(Command):
    def __init__(self, param1, param2):
        super().__init__()
        self.param1 = param1
        self.param2 = param2

    def execute(self):
        ...

    def _undo(self):
        ...

    def _redo(self):
        ...

    def __str__(self) -> str:
        try:
            # Menschenlesbare Beschreibung mit Kontext
            context = self.param1.some_property
            return f"Aktion ausführen für {context}: {self.param2}"
        except (AttributeError, TypeError):
            # Fallback bei fehlenden Daten
            return "Aktion ausführen"
```

### Best Practices für __str__()

1. **Immer Try-Except**: Verhindert Crashes bei lazy loading oder fehlenden Daten
2. **Kontext einbeziehen**: Location, Datum, Zeit wenn verfügbar
3. **Vorher → Nachher**: Zeigt alte und neue Werte
4. **Mehrzeilig bei viel Info**: Nutzt `\n` für bessere Lesbarkeit
5. **Kürzen bei langen Texten**: Preview für Notizen (max. 30 Zeichen)
6. **Generischer Fallback**: Einfache Beschreibung ohne Kontext

### Template

```python
def __str__(self) -> str:
    try:
        # Kontext sammeln
        context_info = self.entity.context_property
        old_value = self.entity.old_value
        new_value = self.new_value

        # Format: "[Aktion] für [Kontext]: [Details]"
        return (f"Aktion für\n"
                f"{context_info}: {old_value} → {new_value}")
    except (AttributeError, TypeError):
        return "Aktion"  # Generischer Fallback
```

## Neue GUI mit Undo/Redo-Buttons

Wenn ein neues Formular Undo/Redo-Buttons hat:

1. **Controller vorhanden?** Prüfen ob `self.controller` existiert
2. **Methode hinzufügen**: `_update_undo_redo_tooltips()` (siehe oben)
3. **Callback registrieren**: Nach Button-Erstellung im `__init__`
4. **Initial aufrufen**: `self._update_undo_redo_tooltips()` nach Registrierung

```python
# Im __init__ nach Button-Erstellung
self.controller.set_on_stacks_changed_callback(self._update_undo_redo_tooltips)
self._update_undo_redo_tooltips()
```

## Aktuelle Implementierungen

Die Tooltip-Funktion ist in folgenden Formularen aktiv:

- **`gui/frm_plan.py`**: Plan-Ansicht mit Undo/Redo für Cast-Änderungen und Termin-Verschiebungen
- **`gui/frm_fixed_cast.py`**: Fixed-Cast-Dialog mit Undo/Redo

## Tooltip-Verhalten

### Button-Status

| Stack-Status | Button-Status | Tooltip-Text |
|--------------|---------------|--------------|
| Stack leer | `disabled` | "Keine Aktion zum Rückgängigmachen" / "Keine Aktion zum Wiederholen" |
| Command vorhanden | `enabled` | "Rückgängig:\n{command description}" / "Wiederholen:\n{command description}" |

### Update-Trigger

Tooltips werden automatisch aktualisiert nach:

- ✅ `controller.execute()` - Nach Ausführung eines Commands
- ✅ `controller.undo()` - Nach Undo
- ✅ `controller.redo()` - Nach Redo

### Beispiel-Tooltips

**Undo-Button bei Cast-Änderung:**
```
Rückgängig:
Cast-Änderungen für
Berlin Mitte - 15.12.2025 (Vormittag)
```

**Redo-Button bei Termin-Verschiebung:**
```
Wiederholen:
Termin verschieben für
Hamburg Nord - 10.12.2025 (Nachmittag) → 12.12.2025 (Vormittag)
```

**Undo-Button ohne Command:**
```
Keine Aktion zum Rückgängigmachen
```

## Mehrsprachigkeit (Zukünftig)

Aktuell sind die `__str__()` Methoden **nicht** lokalisiert. Für zukünftige Mehrsprachigkeit:

### Option 1: `get_description()` Methode

```python
class Command(ABC):
    def get_description(self) -> str:
        """Überschreibbar für lokalisierte Beschreibungen."""
        return str(self)
```

Dann in Subklassen:

```python
def get_description(self) -> str:
    try:
        return self.tr(f"Verfügbarkeitstage ändern für\n{self.context}")
    except:
        return self.tr("Verfügbarkeitstage ändern")
```

### Option 2: Separate Translation-Funktion

```python
def __str__(self) -> str:
    # Englisch (oder ID)
    return "update_avail_days"

def get_localized_description(self, tr_func) -> str:
    try:
        return tr_func(f"Verfügbarkeitstage ändern für\n{self.context}")
    except:
        return tr_func("Verfügbarkeitstage ändern")
```

## Debugging

### Tooltip erscheint nicht?

1. **Callback registriert?** `controller.set_on_stacks_changed_callback(...)` aufgerufen?
2. **Initial aufgerufen?** `_update_undo_redo_tooltips()` nach Registrierung?
3. **Command hat __str__()?** Prüfen ob `str(command)` funktioniert

### Tooltip zeigt generische Beschreibung?

1. **Try-Block failed?** Attribut fehlt oder ist None?
2. **Lazy Loading?** Daten noch nicht geladen?
3. **Exception im __str__()?** Log prüfen

### Button bleibt disabled?

1. **Stack leer?** `controller.get_undo_stack()` / `controller.redo_stack` prüfen
2. **Command wurde nicht hinzugefügt?** `controller.execute()` aufgerufen?

## Performance

Die Tooltip-Updates haben **minimalen Overhead**:

- Callback wird nur bei tatsächlichen Stack-Änderungen ausgeführt
- Nur das Top-Command wird abgefragt (nicht der ganze Stack)
- `__str__()` wird nur bei Hover berechnet (Qt cached Tooltips)
- Keine Datenbank-Abfragen in `__str__()` (nur auf bereits geladene Daten)

## Zusammenfassung

Die Tooltip-Implementierung besteht aus 4 Komponenten:

1. **`__str__()` in Command-Klassen**: Menschenlesbare Beschreibungen
2. **`description` in BatchCommand**: Optional für semantische Beschreibungen
3. **Stack-Changed-Callback in Controller**: Benachrichtigung bei Änderungen
4. **`_update_undo_redo_tooltips()` in GUI**: Button-Tooltips aktualisieren

Alle Komponenten arbeiten zusammen, um dem Nutzer aussagekräftige Informationen über die anstehenden Undo/Redo-Aktionen zu geben.
