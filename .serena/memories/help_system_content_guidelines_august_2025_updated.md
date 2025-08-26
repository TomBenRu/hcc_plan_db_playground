# HCC Plan Help System - Content Guidelines (Session August 2025 - UPDATED)

## BASIERT AUF: help/content/de/forms/group_mode.html (EXCELLENT EXAMPLE)

## 🏗️ HTML-GRUNDGERÜST (Standard):
```html
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>[Formular-Name] - HCC Plan Hilfe</title>
    <link rel="stylesheet" href="../styles/help.css">
    <meta name="keywords" content="[relevante, schlüsselwörter]">
    <meta name="description" content="Hilfe für [Formular-Name] in HCC Plan">
</head>
<body>
    <div class="help-header">
        <h1>[Formular-Name]</h1>
        <div class="breadcrumb"><a href="../index.html">Hilfe</a> &gt; [Formular-Name]</div>
    </div>
    <div class="help-content">
        <!-- Content hier -->
    </div>
</body>
</html>
```

## 📋 CONTENT-STRUKTUR (12-Punkte Standard - KORRIGIERTE REIHENFOLGE):

### PFLICHT-SEKTIONEN (Minimum Viable):
1. **Übersicht** - Kurze Einführung (1-2 Sätze)
2. **Hauptfunktionen** - `<ul class="feature-list">` mit Features
3. **Grundbedienung** - `<ol>` Step-by-Step für Einsteiger
4. **Tastaturkürzel** - `<div class="keyboard-shortcuts">` mit F1 + weitere
5. **Verwandte Funktionen** - Cross-Links zu verwandten Formularen (VERSCHOBEN NACH VORNE)

### EMPFOHLENE SEKTIONEN (Professional Quality):
6. **Anwendungsbereich** - Wo/wofür verwendet
7. **Benutzeroberfläche** - UI-Komponenten im Detail
8. **Praktische Anwendungsfälle** - Real-world Beispiele
9. **Häufige Probleme & Lösungen** - `<div class="warning-box">`
10. **Best Practices** - `<div class="tip-box">`

### OPTIONALE SEKTIONEN (Komplexe Systeme):
11. **Erweiterte Funktionen** - Für Power-User
12. **Technische Details** - System-Integration (VERSCHOBEN NACH HINTEN - Power-User/Entwickler)

## 🎨 STYLING-STANDARDS:

### CSS-KLASSEN:
- `.feature-list` - Für alle Feature-Listen
- `.tip-box` - Für Tipps und Best Practices
- `.warning-box` - Für Probleme/Warnungen (Problem: → Ursache: → Lösung:)
- `.keyboard-shortcuts` - Für Tastaturkürzel-Listen

### TEXT-FORMATIERUNG:
- `<strong>` - UI-Elemente ("Button-Name"), Aktionen, wichtige Begriffe
- `<h2>` - Hauptsektionen
- `<h3>` - Subsektionen  
- `<h4>` - Kategorie-Überschriften in Boxen und Link-Kategorien

### EMOJI-VERWENDUNG (sparsam):
- 💡 - Tipps, Best Practices
- 🚀 - Effizienz, Performance
- 🎯 - Anwendungsbereich, Ziele
- ⚡ - Quick-Tipps
- 🏗️ - Grundlegende/Basis-Strukturen
- 🔄 - Workflows, Planungsperioden
- 📚 - Weiterführende Infos
- 📅 - Termin-Management, Events
- 👥 - Personal, Teams, Zuweisungen
- ⚙️ - Konfiguration, Einstellungen
- 📋 - Tools, Utilities
- 📤 - Export, Integration
- **Regel:** Max 1 Emoji pro h4, verwendet für Link-Kategorien und Boxen

## 📝 SCHREIBSTIL:

### TONALITÄT:
- Professionell aber zugänglich
- Direkt und präzise (keine Füllwörter)
- Handlungsorientiert (aktive Sprache)
- Konsistent (gleiche Begriffe für gleiche Konzepte)

### STANDARD-FORMULIERUNGEN:
- **Aktionen:** "Klicken Sie auf...", "Wählen Sie...", "Ziehen Sie..."
- **Features:** "Ermöglicht es...", "Bietet die Möglichkeit..."
- **Probleme:** "Problem:", "Ursache:", "Lösung:"
- **UI-Elemente:** `<strong>"Button-Name"</strong>`

## 🔗 CROSS-LINKING (ERWEITERT - Session August 2025):

### **NEUE KATEGORIE-STRUKTURIERUNG (BEST PRACTICE):**
Für Seiten mit vielen verwandten Funktionen (>6 Links): Strukturierung in logische Kategorien mit h4-Überschriften und thematischen Emojis:

```html
<h2>Verwandte Funktionen</h2>
<p>[Kurze Einleitung]</p>

<h4>🏗️ [Kategorie-Name]</h4>
<ul class="feature-list">
    <li><a href="link1.html">Funktion 1</a> - Beschreibung warum relevant</li>
    <li><a href="link2.html">Funktion 2</a> - Beschreibung warum relevant</li>
</ul>

<h4>📅 [Kategorie-Name 2]</h4>
<ul class="feature-list">
    <li><a href="link3.html">Funktion 3</a> - Beschreibung warum relevant</li>
    <li><a href="link4.html">Funktion 4</a> - Beschreibung warum relevant</li>
</ul>
```

### **KATEGORIEN-BEISPIELE:**
- 🏗️ **Grundlegende Funktionen** - Kern-Features und Basis-Tools
- 📅 **Termin-Management** - Alles rund um Termine und Events  
- 👥 **Personal & Zuweisungen** - Mitarbeiter- und Team-Funktionen
- ⚙️ **Konfiguration & Einstellungen** - Setup und Systemkonfiguration
- 🔄 **Planungsperioden** - Zeitraum-Management
- 📋 **Tools & Utilities** - Hilfsfunktionen und Werkzeuge
- 📤 **Export & Integration** - Datenexchange und Schnittstellen

### **KLASSISCHE REGELN (für wenige Links):**
- Max 3-5 Links in "Verwandte Funktionen" (ohne Kategorien)
- Kurze Beschreibung warum Link relevant ist
- Von wichtigsten zu weniger wichtigen Links
- Quality over Quantity
- **WEITER VORNE** in der Content-Struktur für bessere User Experience

## ⚡ QUICK-REFERENCE für Session 5:

### MINIMUM (30 Min pro Formular):
1. HTML-Grundgerüst (5 Min)
2. Übersicht + Hauptfunktionen (10 Min)  
3. Grundbedienung (10 Min)
4. Tastaturkürzel + Cross-Links (5 Min)

### PROFESSIONAL (+25 Min):
5. Anwendungsfälle (10 Min)
6. Probleme & Lösungen (10 Min)
7. Best Practices tip-box (5 Min)

## ✅ QUALITÄTS-CHECKLISTE:
- [ ] HTML-Grundgerüst vollständig
- [ ] Alle Pflicht-Sektionen vorhanden  
- [ ] `<strong>` für alle UI-Elemente
- [ ] feature-list für Feature-Listen
- [ ] tip-box/warning-box korrekt verwendet
- [ ] Cross-Links funktional und kategorisiert (falls >6 Links)
- [ ] Meta-Keywords relevant
- [ ] Link-Farben in CSS korrekt gesetzt (feature-list Links sichtbar)

## 🔄 STRUKTUR-ÄNDERUNG (Session August 2025):
**WICHTIG:** 
1. "Verwandte Funktionen" VOR "Technische Details" für bessere UX
2. **NEUE Kategorie-Strukturierung** für bessere Navigation bei vielen Links
3. **CSS-Fix** für feature-list Links: blau statt schwarz für bessere Erkennbarkeit