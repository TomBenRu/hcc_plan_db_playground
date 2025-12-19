# Command Callbacks für UI-Updates bei Undo/Redo

## Übersicht

Das Command-Pattern unterstützt optionale Callbacks, die nach `undo()` und `redo()` ausgeführt werden. Dies ermöglicht kontextspezifische UI-Aktualisierungen, ohne die Command-Klassen selbst zu modifizieren.

## Architektur

### Command-Basisklasse

```python
class Command(ABC):
    def __init__(self):
        self.on_undo_callback: Callable[[], None] | None = None
        self.on_redo_callback: Callable[[], None] | None = None

    @abstractmethod
    def execute(self):
        ...

    @abstractmethod
    def _undo(self):
        """Interne Undo-Logik - wird von Subklassen implementiert."""
        ...

    @abstractmethod
    def _redo(self):
        """Interne Redo-Logik - wird von Subklassen implementiert."""
        ...

    def undo(self):
        """Führt Undo aus und ruft anschließend den Callback auf."""
        self._undo()
        if self.on_undo_callback:
            self.on_undo_callback()

    def redo(self):
        """Führt Redo aus und ruft anschließend den Callback auf."""
        self._redo()
        if self.on_redo_callback:
            self.on_redo_callback()
```

### Wichtige Punkte

- **`_undo()` und `_redo()`**: Interne Methoden, die von Subklassen implementiert werden
- **`undo()` und `redo()`**: Öffentliche Methoden, die die internen Methoden aufrufen und danach die Callbacks ausführen
- **Callbacks sind optional**: Wenn kein Callback gesetzt ist, wird nur die interne Logik ausgeführt

## Verwendung

### Einfaches Beispiel

```python
from commands.database_commands import appointment_commands

# Command erstellen
command = appointment_commands.UpdateNotes(appointment, "Neue Notiz")

# Callbacks setzen (optional)
command.on_undo_callback = lambda: self.refresh_ui()
command.on_redo_callback = lambda: self.refresh_ui()

# Command ausführen
controller.execute(command)
```

### Beispiel mit kontextspezifischen Parametern

Callbacks können Kontext in Closures erfassen:

```python
# Kontext speichern
old_date = appointment.event.date
new_date = dlg.new_date

# Hilfsfunktion für UI-Updates
def emit_ui_signals(from_date: datetime.date, to_date: datetime.date):
    signal_handling.handler_plan_tabs.invalidate_entities_cache(plan_period_id)
    signal_handling.handler_location_plan_period.appointment_moved(
        signal_handling.DataAppointmentMoved(
            event_id=event_id,
            old_date=from_date,
            new_date=to_date,
            ...
        )
    )

# Callbacks mit unterschiedlichen Parametern setzen
command.on_undo_callback = lambda: emit_ui_signals(new_date, old_date)  # Umgekehrte Richtung
command.on_redo_callback = lambda: emit_ui_signals(old_date, new_date)  # Original-Richtung

controller.execute(command)
emit_ui_signals(old_date, new_date)  # Initial ausführen
```

## BatchCommand

Bei `BatchCommand` werden die Callbacks der Kind-Commands **nicht** ausgeführt. Stattdessen:

1. `BatchCommand` ruft `_undo()`/`_redo()` direkt auf Kind-Commands auf
2. Nur der Callback des `BatchCommand` selbst wird ausgeführt

```python
command1 = SomeCommand(...)
command2 = AnotherCommand(...)
batch_command = BatchCommand(self, [command1, command2])

# Nur diesen Callback setzen - Kind-Callbacks werden ignoriert
batch_command.on_undo_callback = lambda: self.refresh_all()
batch_command.on_redo_callback = lambda: self.refresh_all()

controller.execute(batch_command)
```

## Neue Command-Subklasse erstellen

Beim Erstellen einer neuen Command-Subklasse:

1. **`super().__init__()` aufrufen** im Konstruktor
2. **`_undo()` implementieren** statt `undo()`
3. **`_redo()` implementieren** statt `redo()`

```python
class MyNewCommand(Command):
    def __init__(self, param1, param2):
        super().__init__()  # Wichtig!
        self.param1 = param1
        self.param2 = param2

    def execute(self):
        # Ausführungslogik
        ...

    def _undo(self):  # Nicht undo()!
        # Undo-Logik
        ...

    def _redo(self):  # Nicht redo()!
        # Redo-Logik
        ...
```

## Wann Callbacks verwenden?

Callbacks sind sinnvoll wenn:

- UI-Elemente nach Undo/Redo aktualisiert werden müssen
- Signale emittiert werden sollen
- Caches invalidiert werden müssen
- Die gleiche Command-Klasse in verschiedenen Kontexten unterschiedliche UI-Aktionen auslösen soll

Callbacks sind **nicht** nötig wenn:

- Nur Datenbank-Operationen ausgeführt werden
- Keine UI-Aktualisierung erforderlich ist
- Die UI sich automatisch über Observer/Signals aktualisiert

## Praxisbeispiel: `_move_appointment`

Siehe `gui/frm_plan.py:AppointmentField._move_appointment` für ein vollständiges Beispiel der Callback-Verwendung mit:

- Kontexterfassung in Closures
- Unterschiedliche Parameter für Undo vs. Redo
- Signal-Emission für UI-Updates
- Cache-Invalidierung
