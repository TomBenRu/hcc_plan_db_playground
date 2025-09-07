# Session Handover: Qt Threading Warning Fix - September 2025

## AUFGABE ÜBERNEHMEN
Es besteht ein hartnäckiges Qt-Threading-Problem, das systematische Analyse und Lösung benötigt.

## SOFORT ZU LESENDE MEMORIES:
1. `threading_crash_qt_warning_analysis_september_2025` - Vollständige Problem-Analyse
2. `code_style_conventions` - Qt-Namenskonventionen 
3. `development_guidelines` - KEEP IT SIMPLE Prinzip

## AKTUELLER STATUS:
- **Problem identifiziert aber NICHT gelöst**: Qt WARNING QWindowsContext::windowsProc
- **5 systematische Lösungsansätze FEHLGESCHLAGEN** (alle in threading_crash_qt_warning_analysis_september_2025 dokumentiert)
- **Exaktes Reproduktions-Szenario ermittelt**: Plan-Berechnung → _check_plan → Qt-Warnings
- **Wichtiger Isolationstest durchgeführt**: Problem tritt NUR nach Plan-Berechnung auf

## NÄCHSTE PRIORITÄRE ACTIONS:

### 1. Threading-Architektur-Vereinfachung (Empfohlen)
**ZIEL**: SolverThread/SaveThread (QThread) → WorkerSolver/WorkerSave (QRunnable)
- **Warum**: Mixed Threading-Architekturen sind problematisch
- **Files**: `gui/frm_calculate_plan.py` - SolverThread und SaveThread Klassen
- **Pattern**: Wie `WorkerCheckPlan` in `gui/concurrency/general_worker.py`

### 2. Solver-System Deep-Analysis
**ZIEL**: sat_solver/solver_main.py globale State-Probleme identifizieren
- **Fokus**: Globale `solver` Variable und Thread-Storage-Zustand
- **Test**: Solver-Zustand nach Plan-Berechnung prüfen

### 3. Progress-Dialog-System-Review
**ZIEL**: DlgProgressInfinite Constructor-Problem analysieren
- **File**: `gui/custom_widgets/progress_bars.py`
- **Problem**: `self.close()` im Constructor → problematische Window-States
- **Fix**: Alternative Progress-Dialog-Architektur

## ENTWICKLUNGSRICHTLINIEN BEACHTEN:
- **Strukturelle Änderungen**: NUR mit User-Zustimmung
- **KEEP IT SIMPLE**: Einfachste Lösung bevorzugen
- **Command Pattern**: Bei DB-schreibenden Operationen einhalten

## DEBUGGING-APPROACH:
1. **Problem isolieren**: Welcher spezifische Teil der Plan-Berechnung verursacht das Problem?
2. **Threading-Einheit**: Eine konsistente Threading-Architektur implementieren
3. **Window-Lifecycle**: Progress-Dialog und Widget-Management überprüfen

## ERWARTETE LÖSUNG:
Das Problem liegt wahrscheinlich in der **Mixed QThread/QRunnable-Architektur** oder **globalen Solver-State-Management**. Die systematische Vereinfachung auf einheitliche QRunnable-Architektur wird das Problem mit hoher Wahrscheinlichkeit lösen.

## WICHTIGER CONTEXT:
- User hat bereits processEvents() entfernt (keine Verbesserung)
- Alle Widget-Cleanup-Ansätze implementiert (keine Verbesserung)  
- Problem ist sehr spezifisch und reproduzierbar
- Threading-Crash-Problem wurde in früheren Sessions bereits erfolgreich gelöst (siehe andere threading_crash memories)

## TOOLS FÜR ANALYSE:
- `serena:search_for_pattern` für Threading-Code-Lokalisierung
- `serena:find_symbol` für spezifische Methoden-Analyse
- `serena:read_file` für Code-Review
- `sequential-thinking` für komplexe Threading-Analyse

**ZIEL**: Threading-sichere, konsistente Architektur ohne Qt-Window-Event-Corruption