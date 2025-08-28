# Handover: Team-Kalender Implementation - Nächste Session

## AKTUELLER ZUSTAND
✅ **Team-Kalender-Erstellung ist vollständig implementiert und funktioniert**
- Tab-basierte UI in `gui/frm_create_google_calendar.py` 
- Backend-Integration in `gui/main_window.py`
- Automatische Namensgebung: "{project_name} - Team {team_name}"
- Team-Mitglieder-Auswahl mit Checkboxes
- E-Mail-Zugriff aus Datenbank (Person.email)

## NÄCHSTE AUFGABE
🔄 **Manuelle E-Mail-Eingabe für Team-Mitglieder implementieren**

**Problem**: Nutzer möchten bei Team-Mitgliedern die E-Mail-Adresse für Google Calendar-Zugriff manuell bestimmen können (nicht nur aus DB).

**Lösung benötigt für**:
- Überschreibung der Datenbank-E-Mail mit Google-kompatiblen Adressen
- UI-Element für E-Mail-Bearbeitung pro Team-Mitglied
- Integration in bestehenden `_load_team_members()` Workflow

## WICHTIGE DATEIEN
- `gui/frm_create_google_calendar.py` - Hauptimplementierung
- `gui/main_window.py` - Backend-Integration  
- Memory: `team_calendar_implementation_complete_august_2025` - Vollständige Details

## IMPLEMENTIERUNGS-WARNUNG
⚠️ **Vorsicht bei String-Formatierungen und Regex-Ersetzungen**
- In dieser Session gab es massive Probleme mit f-String-Formatierung
- User musste mehrfach manuell korrigieren
- Kleine, schrittweise Änderungen bevorzugen

## EMPFOHLENER APPROACH
1. Design-Entscheidung mit User treffen (Dialog vs. Inline-Editing)  
2. Schrittweise Implementation der E-Mail-Eingabe-Funktionalität
3. Sorgfältige String-Validierung vor Code-Änderungen

## STATUS: BEREIT FÜR FORTSETZUNG
Grundfunktionalität steht, nur noch das E-Mail-Eingabe-Feature fehlt.
