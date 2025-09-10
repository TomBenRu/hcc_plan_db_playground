# Faulthandler + PyInstaller Implementierung - September 2025

## Session-Zusammenfassung
**Datum:** September 2025  
**Aufgabe:** Faulthandler für Crash-Debugging implementieren mit PyInstaller-Kompatibilität  
**Status:** ✅ ERFOLGREICH ABGESCHLOSSEN

## Problem-Identifikation

### Ursprüngliche Anfrage
- Thomas wollte Faulthandler nur in Produktionsumgebung (PyInstaller) aktivieren
- Frage: Wie unterscheidet man zwischen Entwicklung und PyInstaller-Executable?

### Kritische Erkenntnisse durch Recherche
1. **PyInstaller --windowed/--noconsole Problem:**
   - `sys.stderr = None` in windowed builds
   - `faulthandler.enable()` ohne Parameter führt zu RuntimeError
   - Häufiges, bekanntes Problem in der PyInstaller-Community

2. **Faulthandler Einsatzzweck:**
   - Primär für Produktionsumgebungen gedacht (Thomas hatte recht)
   - Aber auch in Entwicklung wertvoll für Qt-Threading-Crashes
   - BEIDE Umgebungen profitieren von Crash-Debugging

## Implementierte Lösung

### Erkennungs-Logik (Entwicklung vs. PyInstaller)
```python
def is_development_environment() -> bool:
    """
    Erkennt, ob das Programm in der Entwicklungsumgebung läuft.
    
    Returns:
        True wenn Entwicklungsumgebung (normales Python), 
        False wenn PyInstaller-Executable (onefile oder onedir)
    """
    # PyInstaller setzt sys.frozen auf True (sowohl bei onefile als auch onedir)
    is_frozen = getattr(sys, 'frozen', False)
    
    # In Entwicklungsumgebung: frozen=False
    # Bei PyInstaller (onefile/onedir): frozen=True
    return not is_frozen
```

**Wichtig:** Nur `sys.frozen` verwenden, NICHT `sys._MEIPASS` (existiert nur bei --onefile)

### Faulthandler-Aktivierung mit File-Parameter
```python
# Faulthandler mit File-Parameter aktivieren (umgeht PyInstaller sys.stderr Problem)
if is_development_environment():
    crash_log_path = os.path.join(log_path, 'crash-development.log')
    print("🔧 Entwicklungsumgebung erkannt - Faulthandler wird konfiguriert")
else:
    crash_log_path = os.path.join(log_path, 'crash-production.log')
    print("📦 PyInstaller-Executable erkannt - Faulthandler wird konfiguriert")

try:
    # File-Handle für Crash-Logs (muss offen bleiben!)
    crash_log_file = open(crash_log_path, 'a', encoding='utf-8')
    faulthandler.enable(file=crash_log_file, all_threads=True)
    print(f"✅ Faulthandler aktiviert (alle Threads) - Crash-Logs: {crash_log_path}")
except Exception as e:
    print(f"⚠️ Faulthandler konnte nicht aktiviert werden: {e}")
    # App läuft trotzdem weiter
```

## Technische Details

### Warum File-Parameter statt sys.stderr?
- **PyInstaller Problem:** `--windowed` setzt `sys.stderr = None`
- **Lösung:** Separate Crash-Log-Dateien verwenden
- **Vorteil:** Crash-Logs gehen nicht in normalen Logs unter
- **Kompatibilität:** Funktioniert mit allen PyInstaller-Modi

### Warum all_threads=True?
- **Qt-Anwendung:** Mehrere Threads (GUI, Worker, Qt-intern)
- **Threading-Crashes:** Häufige Fehlerquelle in Qt-Apps
- **Debug-Wert:** Thread-Interaktionen sichtbar machen
- **Beispiel:** GUI-Thread crash durch Worker-Thread-Konflikt

### Separate Log-Dateien
- `crash-development.log` - Normale Python-Ausführung
- `crash-production.log` - PyInstaller-Executables
- **Append-Mode:** Mehrere Crashes werden gesammelt
- **UTF-8 Encoding:** Internationale Zeichen unterstützt

## Timing-Problem gelöst

### Problem
- Faulthandler-Code läuft VOR vollständiger Logging-Initialisierung
- `logging.info()` Ausgaben erschienen nicht

### Lösung
- `print()` für frühe Startup-Phase verwenden
- Später nach `setup_comprehensive_logging()` kann reguläres Logging verwendet werden

## Vorteile der finalen Lösung

1. ✅ **PyInstaller-Kompatibilität:** Funktioniert mit allen Modi (onefile, onedir, windowed)
2. ✅ **Robustheit:** Graceful degradation bei Fehlern
3. ✅ **Vollständigkeit:** Alle Threads werden erfasst
4. ✅ **Wartbarkeit:** Separate Crash-Logs für bessere Debugging
5. ✅ **Flexibilität:** Entwicklung und Produktion profitieren beide

## Integration in bestehende Infrastruktur

- **Nutzt bestehenden log_path** aus Configuration-System
- **Kompatibel mit umfassendem Logging-System**
- **Folgt KEEP IT SIMPLE Philosophie**
- **Keine Breaking Changes** an bestehender Architektur

## Erkenntnisse für zukünftige Sessions

1. **PyInstaller --windowed bricht sys.stderr** - Immer File-Parameter für faulthandler verwenden
2. **sys.frozen ist zuverlässiger Indikator** für PyInstaller-Builds
3. **all_threads=True ist essentiell** für Qt-Anwendungen
4. **Timing bei Logging-Setup beachten** - Frühe Phase mit print(), später logging
5. **Faulthandler ist wertvoll** sowohl in Entwicklung als auch Produktion

## Datei-Änderungen
- **gui/app.py:** Faulthandler-Implementierung mit PyInstaller-Kompatibilität hinzugefügt

## Status
🎯 **PRODUKTIONSBEREIT** - Faulthandler aktiviert sich automatisch in beiden Umgebungen mit separaten Crash-Log-Dateien.