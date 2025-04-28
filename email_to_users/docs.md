# E-Mail-Funktionalität - Technische Dokumentation

## Architektur

Die E-Mail-Funktionalität ist in mehrere Module unterteilt, die jeweils spezifische Verantwortlichkeiten haben:

### 1. Konfiguration (config.py)

Das Konfigurationsmodul definiert ein `EmailConfig`-Modell mit Einstellungen für den SMTP-Server, Absenderinformationen, TLS/SSL-Konfiguration und Debug-Optionen. Die Konfiguration kann über Umgebungsvariablen, programmatisch oder über eine Konfigurationsdatei erfolgen.

### 2. E-Mail-Sender (sender.py)

Der `EmailSender` ist für den eigentlichen Versand von E-Mails verantwortlich. Er bietet Methoden zum Senden einzelner E-Mails sowie zum Massenversand. Die wichtigsten Funktionen sind:

- `send_email()`: Sendet eine einzelne E-Mail an einen oder mehrere Empfänger
- `send_bulk_email()`: Sendet personalisierte E-Mails an mehrere Empfänger

### 3. Templates (templates/)

Das Template-System bietet eine abstrakte Basisklasse `EmailTemplate` und spezialisierte Template-Klassen für verschiedene E-Mail-Typen:

- `PlanNotificationTemplate`: Für Benachrichtigungen über neue Einsatzpläne
- `AvailabilityRequestTemplate`: Für Anfragen zur Verfügbarkeitseingabe

Jedes Template rendert drei Komponenten: Betreff, Plaintext-Inhalt und HTML-Inhalt.

### 4. Service-Schicht (service.py)

Der `EmailService` integriert das E-Mail-System mit dem Datenmodell der Anwendung und bietet kontextbezogene Funktionen:

- `send_plan_notification()`: Sendet Benachrichtigungen über neue Einsatzpläne
- `send_availability_request()`: Sendet Anfragen zur Verfügbarkeitseingabe
- `send_custom_email()`: Sendet benutzerdefinierte E-Mails an Mitarbeiter

### 5. Hilfsfunktionen (utils.py)

Das `utils`-Modul enthält Hilfsfunktionen für die E-Mail-Erstellung und -Validierung.

## Datenbankintegration

Die Service-Schicht arbeitet mit dem Pony ORM-Datenmodell des Projekts. Folgende Entitäten werden verwendet:

- `Person`: Für Empfängerinformationen (Name, E-Mail)
- `Team`: Für Gruppenzuordnungen
- `Plan`, `PlanPeriod`: Für Einsatzplan-Informationen
- `Event`, `LocationOfWork`: Für Einsatzdetails

Alle Datenbankoperationen werden mit dem `@db_session`-Dekorator von Pony ORM umgeben.

## E-Mail-Templates

Die Templates verwenden einen einfachen Format-String-Mechanismus für die Personalisierung. HTML-Templates enthalten grundlegendes CSS-Styling für eine ansprechende Darstellung.

### PlanNotificationTemplate

Dieses Template erstellt E-Mails mit einer Tabelle der geplanten Einsätze eines Mitarbeiters, formatiert mit Datum, Uhrzeit und Einsatzort.

### AvailabilityRequestTemplate

Dieses Template erstellt E-Mails mit Informationen zu einem Planungszeitraum und einem optionalen Button zum Aufrufen der Eingabeseite für Verfügbarkeiten.

## Fehlerbehandlung

Das Paket verwendet Python's `logging`-Modul für die Protokollierung von Fehlern und wichtigen Ereignissen. Alle Funktionen sind mit Try-Except-Blöcken versehen, um robustes Fehlerverhalten zu gewährleisten.

## Rate-Limiting

Um Server-Überlastung zu vermeiden, implementiert der `EmailSender` ein einfaches Rate-Limiting-System, das die Anzahl der gesendeten E-Mails pro Stunde begrenzt.

## Debug-Modus

Im Debug-Modus werden E-Mails nicht tatsächlich gesendet, sondern auf der Konsole ausgegeben. Dies ist nützlich für Entwicklungs- und Testzwecke.

## Erweiterbarkeit

Das System ist so konzipiert, dass es leicht erweitert werden kann:

- Neue Template-Klassen können erstellt werden, indem `EmailTemplate` erweitert wird
- Die Service-Schicht kann um weitere kontextbezogene Funktionen erweitert werden

## Sicherheitsüberlegungen

- Passwörter werden nie im Code gespeichert, sondern über Umgebungsvariablen oder Konfigurationsdateien bereitgestellt
- TLS wird standardmäßig für SMTP-Verbindungen verwendet
- E-Mail-Adressen werden validiert, um ungültige Eingaben zu vermeiden
- Rate-Limiting schützt vor übermäßiger Serverbelastung

## Zukunftsperspektiven

Mögliche zukünftige Erweiterungen:

1. **Asynchroner E-Mail-Versand**: Implementierung eines Queue-Systems für großvolumigen E-Mail-Versand, um die Hauptanwendung nicht zu blockieren.

2. **Erweiterte Template-Engine**: Integration von Jinja2 oder einer anderen leistungsstarken Template-Engine für komplexere E-Mail-Personalisierung.

3. **E-Mail-Tracking**: Einführung von Tracking-Links, um festzustellen, ob E-Mails geöffnet wurden.

4. **E-Mail-Anhänge**: Verbesserte Unterstützung für verschiedene Typen von Anhängen, insbesondere dynamisch generierte Excel- oder PDF-Dateien mit Einsatzplänen.

5. **Internationalisierung**: Mehrsprachige Unterstützung für E-Mail-Templates.

6. **E-Mail-Warteschlange**: Implementierung einer Warteschlange zur Wiederholung fehlgeschlagener E-Mail-Sendungen.

7. **Admin-Dashboard**: Eine Benutzeroberfläche zur Überwachung gesendeter E-Mails und zum Erstellen von benutzerdefinierten E-Mail-Kampagnen.

## Implementierungsdetails

### SMTP-Integration

Die SMTP-Integration verwendet das Standard-`smtplib`-Modul von Python. Die Verbindung wird für jede E-Mail neu hergestellt und nach dem Senden geschlossen, um sicherzustellen, dass Verbindungsprobleme die Anwendung nicht blockieren.

### E-Mail-Aufbau

E-Mails werden mit dem `email`-Modul von Python erstellt. Jede E-Mail ist ein `MIMEMultipart`-Objekt, das Teile für Plaintext und HTML (falls verfügbar) enthält. Anhänge werden als zusätzliche MIME-Teile hinzugefügt.

### Personalisierung

Die Personalisierung von E-Mails erfolgt über Python's Format-String-Syntax. Templates definieren Platzhalter wie `{name}`, die durch die entsprechenden Werte ersetzt werden.

### Empfänger-Validierung

E-Mail-Adressen werden validiert, um sicherzustellen, dass nur gültige Adressen verwendet werden. Die Validierung verwendet die Funktionalität von Pydantic.

## Testing

Das Test-Framework verwendet Python's Standard-`unittest`-Modul und deckt folgende Bereiche ab:

1. **Unit-Tests für Utilities**: Testen der Hilfsfunktionen für E-Mail-Validierung und -Formatierung.

2. **Tests für den E-Mail-Sender**: Testen der E-Mail-Sende-Funktionalität mit Mock-Objekten.

3. **Template-Tests**: Überprüfen, ob die Templates korrekt gerendert werden.

## Integration mit der GUI

Die E-Mail-Funktionalität kann in der GUI-Oberfläche des Projekts über folgende Einstiegspunkte integriert werden:

1. **Plan-Detailansicht**: Button "Plan per E-Mail versenden" für das Senden von Einsatzplan-Benachrichtigungen.

2. **Planungszeitraum-Ansicht**: Button "Verfügbarkeitsanfrage senden" für das Senden von Anfragen zur Verfügbarkeitseingabe.

3. **Mitarbeiter-Liste**: Kontextmenü "E-Mail senden" für das Senden benutzerdefinierter E-Mails an ausgewählte Mitarbeiter.

4. **Einstellungen**: Konfigurationsbereich für E-Mail-Einstellungen (SMTP-Server, Absenderadresse, etc.).
