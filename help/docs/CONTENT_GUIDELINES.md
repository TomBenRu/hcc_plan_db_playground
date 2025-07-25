# Content-Richtlinien für HCC Plan Hilfe-System

## Übersicht

Diese Richtlinien stellen sicher, dass alle Hilfe-Inhalte konsistent, benutzerfreundlich und wartbar sind.

## HTML-Struktur und Standards

### Basis-Template
Alle Hilfe-Seiten verwenden das folgende Template-System:

```html
<!DOCTYPE html>
<html lang="{{language}}">
<head>
    <meta charset="UTF-8">
    <title>{{title}} - HCC Plan Hilfe</title>
    <link rel="stylesheet" href="../styles/help.css">
</head>
<body>
    <div class="help-header">
        <h1>{{title}}</h1>
        <div class="breadcrumb">{{breadcrumb}}</div>
    </div>
    
    <div class="help-content">
        {{content}}
    </div>
    
    <div class="help-footer">
        <div class="related-links">{{related_links}}</div>
        <div class="help-info">Version {{version}} | {{language}}</div>
    </div>
</body>
</html>
```

### HTML-Konventionen

#### Überschriften
- `<h1>`: Haupttitel der Hilfe-Seite (nur einmal pro Seite)
- `<h2>`: Hauptabschnitte
- `<h3>`: Unterabschnitte
- `<h4>`: Detailabschnitte (sparsam verwenden)

#### Listen
- **Schrittweise Anleitungen**: Nummerierte Listen (`<ol>`)
- **Feature-Listen**: Bullet Points (`<ul>`)
- **Wichtige Punkte**: `<ul class="important">`

#### Hervorhebungen
- **Wichtige Begriffe**: `<strong>Begriffe</strong>`
- **UI-Elemente**: `<em class="ui-element">Schaltfläche</em>`
- **Tastenkombinationen**: `<kbd>F1</kbd>` oder `<kbd>Ctrl+S</kbd>`
- **Code/Pfade**: `<code>datei.py</code>`

#### Bilder und Screenshots
```html
<div class="screenshot">
    <img src="../images/frm_plan_overview.png" alt="Plan-Formular Übersicht">
    <p class="caption">Abbildung 1: Hauptbereich des Plan-Formulars</p>
</div>
```

## Content-Kategorien

### 1. Formular-Hilfen (z.B. frm_plan.py)

#### Struktur
1. **Übersicht**: Was macht dieses Formular?
2. **Hauptfunktionen**: Die wichtigsten Features
3. **Schritt-für-Schritt**: Typische Arbeitsabläufe
4. **Felder und Optionen**: Detaillierte Erklärungen
5. **Tipps und Tricks**: Effizienz-Verbesserungen
6. **Häufige Probleme**: Troubleshooting

#### Beispiel-Template (frm_plan.py)
```html
<h2>Plan-Formular Übersicht</h2>
<p>Das Plan-Formular ist das Herzstück der HCC Plan Anwendung...</p>

<h2>Hauptfunktionen</h2>
<ul class="feature-list">
    <li><strong>Plan erstellen</strong>: Neue Planungsperioden anlegen</li>
    <li><strong>Termine verwalten</strong>: Veranstaltungen planen und zuweisen</li>
    <li><strong>Personal zuordnen</strong>: Mitarbeiter zu Terminen zuweisen</li>
</ul>

<h2>Neuen Plan erstellen</h2>
<ol>
    <li>Klicken Sie auf <em class="ui-element">Neuer Plan</em></li>
    <li>Wählen Sie die Planungsperiode aus</li>
    <li>Geben Sie einen Namen ein</li>
    <li>Bestätigen Sie mit <kbd>Enter</kbd> oder <em class="ui-element">OK</em></li>
</ol>
```

### 2. Dialog-Hilfen

#### Struktur
1. **Zweck**: Wofür ist dieser Dialog?
2. **Felder**: Erklärung aller Eingabefelder
3. **Schaltflächen**: Was bewirken die verschiedenen Buttons?
4. **Validierung**: Welche Regeln gelten?

### 3. Allgemeine Hilfen

#### Struktur
1. **Konzepte**: Grundlegende Begriffe und Konzepte
2. **Arbeitsabläufe**: Übergreifende Prozesse
3. **Integration**: Wie arbeiten verschiedene Module zusammen?

## Sprach-Richtlinien

### Deutsch (Primärsprache)
- **Anrede**: Sie (formal)
- **Ton**: Professionell aber zugänglich
- **Fachbegriffe**: Einheitlich verwenden, beim ersten Auftreten erklären
- **Satzlänge**: Kurz und präzise

#### Beispiel-Formulierungen
- ✅ "Klicken Sie auf die Schaltfläche 'Speichern'"
- ❌ "Man klickt auf 'Speichern'"
- ✅ "Wählen Sie aus der Dropdown-Liste"
- ❌ "In der Combobox auswählen"

### Englisch (Übersetzung)
- **Anrede**: You (standard)
- **Ton**: Professional but approachable
- **Konsistenz**: UI-Begriffe exakt wie in der englischen Programmversion
- **Klarheit**: Simple, clear sentences

## Screenshot-Standards

### Anforderungen
- **Format**: PNG mit Transparenz wenn möglich
- **Auflösung**: Mindestens 150 DPI
- **Sprache**: Screenshots in der jeweiligen Hilfe-Sprache
- **Konsistenz**: Gleiche UI-Themes und Farben

### Datei-Namenskonvention
```
images/
├── de/
│   ├── frm_plan_overview.png
│   ├── frm_plan_new_dialog.png
│   └── frm_plan_context_menu.png
└── en/
    ├── frm_plan_overview.png
    └── ...
```

### Bearbeitung
- **Markierungen**: Rote Kreise/Pfeile für wichtige Bereiche
- **Unschärfe**: Sensible Daten unkenntlich machen
- **Konsistenz**: Gleicher Stil für alle Markierungen

## SEO und Suchbarkeit

### Keywords
- **Formular-Namen**: frm_plan, plan, planung
- **Funktionen**: erstellen, speichern, zuweisen, verwalten
- **UI-Elemente**: button, schaltfläche, dropdown, liste

### Metadaten
Jede HTML-Datei sollte relevante Meta-Keywords enthalten:
```html
<meta name="keywords" content="plan, planung, erstellen, hcc">
<meta name="description" content="Hilfe für das Plan-Formular in HCC Plan">
```

## Qualitätssicherung

### Review-Checkliste
- [ ] HTML-Validierung (W3C konform)
- [ ] Rechtschreibung und Grammatik
- [ ] Screenshot-Qualität und -Aktualität
- [ ] Links funktionieren (intern und extern)
- [ ] Konsistenz mit UI-Begriffen
- [ ] Barrierefreiheit (Alt-Texte, Kontraste)

### Test-Verfahren
1. **Funktionale Tests**: Hilfe aus der Anwendung heraus testen
2. **Cross-Language Tests**: DE/EN Konsistenz prüfen
3. **Benutzer-Tests**: Verständlichkeit validieren

## Wartung und Updates

### Versionskontrolle
- Hilfe-Content folgt der Anwendungsversion
- Änderungen werden im Git dokumentiert
- Screenshots bei UI-Änderungen aktualisieren

### Update-Zyklen
- **Bei neuen Features**: Sofortige Hilfe-Erstellung
- **Bei UI-Änderungen**: Screenshot- und Text-Updates
- **Regelmäßige Reviews**: Quartalsweise Qualitätsprüfung

---

**Letzte Aktualisierung**: 2025-07-25  
**Version**: 1.0  
**Nächste Review**: Bei erstem Content-Release
