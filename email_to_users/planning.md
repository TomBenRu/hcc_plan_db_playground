# Implementierungsplan für E-Mail-Funktionalität

## Überblick
Ziel ist die Implementierung eines Systems zum Versenden von E-Mails an Mitarbeiter im HCC Plan DB Playground-Projekt. Das `email_to_users` Package wurde bereits angelegt und soll entsprechend implementiert werden.

## Anforderungen

1. **Grundlegende Funktionalität**
   - E-Mails an einzelne Mitarbeiter senden
   - E-Mails an Gruppen von Mitarbeitern senden (z.B. ein ganzes Team, alle Mitarbeiter einer Location)
   - Templates für verschiedene E-Mail-Typen (z.B. Einsatzplan-Benachrichtigung, Freigabe-Anfragen, Bestätigungen)

2. **Technische Anforderungen**
   - Sichere SMTP-Authentifizierung
   - E-Mail-Inhalte mit HTML und Plaintext
   - Anhänge unterstützen (z.B. für Einsatzpläne)
   - Fehlerbehandlung beim E-Mail-Versand
   - Konfigurierbarkeit (SMTP-Server, Absender-Adresse etc.)

3. **Integration**
   - Nahtlose Integration in das bestehende Datenmodell (Person, Team, etc.)
   - Möglichkeit zur Anbindung an bestehende Services

## Architektur

### Paket-Struktur (email_to_users)
```
email_to_users/
├── __init__.py
├── config.py           # Konfiguration für SMTP und allgemeine E-Mail-Einstellungen
├── sender.py           # Hauptklasse für den E-Mail-Versand
├── templates/          # Verzeichnis für E-Mail-Templates
│   ├── __init__.py
│   ├── base.py         # Basisklasse für Templates
│   ├── plan_notify.py  # Template für Einsatzplan-Benachrichtigungen
│   └── request.py      # Template für Anfragen an Mitarbeiter
├── utils.py            # Hilfsfunktionen für E-Mail-Erstellung
└── service.py          # Höhere Service-Ebene für die Integration in die Anwendung
```

### Komponenten

1. **Config (config.py)**
   - Einstellungen für SMTP-Server, Port, Timeout, etc.
   - Möglichkeit zur Konfiguration über Umgebungsvariablen oder Konfigurationsdatei
   - Sicherheitseinstellungen (TLS/SSL)

2. **E-Mail-Sender (sender.py)**
   - `EmailSender` Klasse für den Versand von E-Mails via SMTP
   - Methoden für Einzel- und Massen-E-Mails
   - Unterstützung für Anhänge und HTML/Plaintext-Inhalte
   - Fehlerbehandlung und Logging

3. **Templates (templates/)**
   - Abstrakte Basisklasse für alle E-Mail-Templates
   - Spezifische Template-Klassen für verschiedene E-Mail-Typen
   - Methoden zur Personalisierung von E-Mails basierend auf Empfängerdaten

4. **Service (service.py)**
   - High-Level-Schnittstelle für andere Anwendungsteile
   - Methoden wie `send_plan_notification`, `send_availability_request` etc.
   - Integration mit der Datenbank und bestehenden Services

5. **Utilities (utils.py)**
   - Hilfsfunktionen für E-Mail-Validierung
   - Formatierung von Empfängerlisten
   - Erzeugen von Anhängen (z.B. PDF-Dateien aus Einsatzplänen)

## Implementierungsplan

### Phase 1: Grundstruktur und Konfiguration
1. ✅ Package-Struktur erstellen (bereits erfolgt)
2. Konfigurationsdatei implementieren (config.py)
3. Basisklasse für den E-Mail-Versand erstellen (sender.py)
4. Grundlegende Tests schreiben

### Phase 2: Templates und Personalisierung
1. Template-System implementieren
2. Basis-Templates erstellen (HTML + Plaintext)
3. Personalisierung von Templates ermöglichen
4. Tests für Templates hinzufügen

### Phase 3: Integration und Service-Layer
1. Service-Layer implementieren (service.py)
2. Integration mit dem Datenmodell (Person, Team, etc.)
3. Methoden zum Versenden von E-Mails an spezifische Gruppen
4. Fehlerbehandlung und Logging verfeinern

### Phase 4: Erweiterungen und Optimierungen
1. Anhang-Unterstützung hinzufügen
2. Asynchronen E-Mail-Versand implementieren (optional)
3. Überwachung und Berichterstattung für gesendete E-Mails
4. Umfassende Dokumentation

## Technologie-Stack
- Standard-Bibliothek: `smtplib`, `email`, `mimetypes`
- Vorhandene Abhängigkeiten: Pydantic für E-Mail-Validierung
- Optional: Jinja2 für fortgeschrittene Template-Funktionen (falls benötigt)

## Sicherheitsüberlegungen
- Keine Anmeldedaten im Code, nur in Konfigurationsdateien oder Umgebungsvariablen
- TLS/SSL für SMTP-Verbindungen
- Schutz vor E-Mail-Injektion
- Validierung von E-Mail-Adressen
- Rate-Limiting für Massen-E-Mails

## Nächste Schritte
1. Implementierung von config.py und sender.py
2. Erstellen eines einfachen CLI-Tools zum Testen des E-Mail-Versands
3. Entwicklung der ersten Template-Klasse
4. Integration mit dem vorhandenen Datenmodell