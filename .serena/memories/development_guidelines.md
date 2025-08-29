# Entwicklungsrichtlinien und Task-Completion

## Wichtige Entwicklungsrichtlinien

### 0. KEEP IT SIMPLE - Philosophie (Oberste Priorität)
**Motto**: *"Besser simpel und funktionabel als kompliziert und verbugged"*

- **Einfachheit vor Features** - Funktionalität ist wichtiger als Perfektion
- **Radikale Vereinfachung bevorzugen** - Weniger Code = weniger Bugs
- **Komplexe Lösungen hinterfragen** - Oft gibt es einfachere Wege
- **Bewährte Patterns nutzen** - Keine Neuerfindung des Rades
- **Minimale Änderungen bevorzugen** - Bestehende Strukturen erweitern statt neu bauen
- **Zero-Configuration** - System soll automatisch funktionieren
- **Standards befolgen** - RFC-Standards und API-Best-Practices nutzen

**Praktische Anwendung:**
- Vor komplexer Implementierung: "Geht es auch einfacher?"
- Bei Bugs: "Können wir das Problem vereinfachen statt erweitern?"
- Bei Features: "Brauchen wir wirklich alle diese Optionen?"
- Bei Architektur: "Ist das die einfachste Lösung die funktioniert?"

**Erfolgsbeispiel:** Employee Events Refactoring (August 2025)
- Problem: Komplexe Sync-Integration in Kalendererstellung
- Lösung: Radikale Trennung + iCalUID Standard + Zero-Configuration
- Ergebnis: Fehlerfreie, wartbare, benutzerfreundliche Lösung

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
- **KRITISCH: self.tr() in QWidgets** - In QWidget-Klassen IMMER self.tr() für Übersetzungen verwenden, NIEMALS QCoreApplication.translate()

### 5. String-Verarbeitung in Code-Änderungen
- **WARNUNG: Newline-Problem** - Bei regex-Ersetzungen '\n' NIEMALS durch echte Zeilenwechsel ersetzen
- **String-Literals bewahren** - Backslash-Escaping in Code-Strings beibehalten 
- **Vorsicht bei multiline-Strings** - Besonders bei Fehlermeldungen und GUI-Texten

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

## Architektur-Prinzipien (basierend auf Erfolgsbeispielen)

### Single Responsibility Principle
- **Eine Funktion = Ein Zweck** - Keine Vermischung von Verantwortlichkeiten
- **Klare Trennung** - Kalendererstellung ≠ Synchronisation
- **Modular aufbauen** - Funktionen sollen einzeln testbar sein

### User Experience Prioritäten
- **Performance vor Features** - Schnelle Response-Zeiten wichtiger als viele Optionen
- **Intuitive Bedienung** - Menü-Integration vor neuen Dialogen
- **Fehlervergebend** - System soll auch bei unvollständigen Eingaben funktionieren
- **Selbsterklärend** - Weniger Dokumentation durch bessere UX

### Maintenance-Friendly Code
- **Verständlicher Code** - Bevorzugung vor "cleveren" Lösungen
- **Standardkonformität** - RFC5545 iCalUID statt eigene ID-Systeme  
- **Konsistente Patterns** - Neue Features folgen bestehenden Strukturen
- **Minimal Dependencies** - Weniger externe Abhängigkeiten = stabiler

## Entscheidungshilfen

### Feature-Implementierung Checklist:
1. **Ist das wirklich nötig?** - Oft reichen 20% der Features für 80% der Nutzung
2. **Gibt es einen einfacheren Weg?** - Standards und bewährte Patterns prüfen
3. **Kann ich bestehende Strukturen nutzen?** - Erweitern statt neu bauen
4. **Ist es wartbar?** - Code soll in 6 Monaten noch verständlich sein
5. **Funktioniert es zuverlässig?** - Stabilität vor Perfektion

### Problem-Solving Approach:
1. **Problem verstehen** - Was ist wirklich das Problem?
2. **Einfachste Lösung suchen** - Was ist der minimale Fix?
3. **Standards prüfen** - Gibt es bewährte Patterns?
4. **Mit Thomas abstimmen** - Bei strukturellen Änderungen
5. **Implementieren und testen** - Keep it simple