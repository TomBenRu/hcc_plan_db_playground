# Entwicklungsrichtlinien und Task-Completion

## Wichtige Entwicklungsrichtlinien

### 1. Strukturelle Änderungen
- **NIEMALS eigenständige Änderungen** an grundlegenden Architekturkomponenten ohne Rücksprache
- **Jede strukturelle Änderung** muss vorher mit Thomas abgesprochen und genehmigt werden
- **Erst fragen, dann implementieren** bei allen Architektur-relevanten Entscheidungen

### 2. Command Pattern Compliance
- **Alle schreibenden DB-Operationen** müssen als Commands implementiert werden
- **Undo/Redo-Funktionalität** ist essentiell für Production-Code
- **Service-Layer-Integration** nur temporär - Commands-Integration für Production erforderlich

### 3. Code-Qualität
- **Over-Engineering vermeiden** - Bevorzugung von einfachen, wartbaren Lösungen
- **Deutsche Kommentare** und Dokumentation verwenden
- **Type Hints** konsequent einsetzen
- **Pydantic-Schemas** für alle API-Contracts

### 4. GUI-Entwicklung
- **Konsistentes Dark Theme** mit #006d6d Akzentfarbe
- **Modulare Struktur** - Separate Packages für verschiedene Funktionsbereiche
- **Qt-Translations** für alle Benutzer-sichtbaren Texte

## Task-Completion Checklist

### Nach Implementierung neuer Features:
1. **Funktionalitätstests** - Manuelle Überprüfung aller neuen Features
2. **Integration testen** - Sicherstellen dass bestehende Funktionen weiterhin arbeiten
3. **Command Pattern** - Prüfen ob Commands korrekt implementiert sind
4. **Error Handling** - Robuste Fehlerbehandlung implementiert
5. **Dokumentation** - Code-Kommentare und Docstrings aktualisiert

### Vor Deployment/Release:
1. **pytest ausführen** - Alle Tests müssen erfolgreich sein
2. **mypy Type-Checking** - Keine Typfehler
3. **Performance-Test** - Besonders bei GUI-Änderungen
4. **PyInstaller-Build** - Executable funktioniert ordnungsgemäß

### Spezifische Qualitätschecks:
- **Thread-Safety** - Besonders bei GUI/Worker-Thread-Kommunikation
- **Speicher-Leaks** - Bei längeren GUI-Sessions
- **Exception-Handling** - Comprehensive try-catch in kritischen Bereichen
- **Logging** - Ausreichende Debug-Informationen ohne Spam

## Kommunikation mit Thomas
- **Vor strukturellen Änderungen**: Immer um Erlaubnis fragen
- **Nach Implementierung**: Status-Update und Test-Ergebnisse mitteilen
- **Bei Problemen**: Sofort kommunizieren, nicht versuchen selbst zu lösen
- **Architektur-Entscheidungen**: Gemeinsam treffen, nicht unilateral