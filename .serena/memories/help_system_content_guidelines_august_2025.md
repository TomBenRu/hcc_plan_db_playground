# HCC Plan Help System - Content Guidelines (Session 5 - KORRIGIERT)

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
5. **Verwandte Funktionen** - Cross-Links zu 1-3 wichtigsten verwandten Formularen (VERSCHOBEN NACH VORNE)

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
- `<h4>` - Nur in Boxen für Überschriften

### EMOJI-VERWENDUNG (sparsam):
- 💡 - Tipps, Best Practices
- 🚀 - Effizienz, Performance
- 🎯 - Anwendungsbereich, Ziele
- ⚡ - Quick-Tipps
- 🏗️ - Komplexe Strukturen
- 🔄 - Workflows
- 📚 - Weiterführende Infos
- **Regel:** Max 1 Emoji pro h4 in Boxen, nie in h2/h3

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

## 🔗 CROSS-LINKING:
- Max 3-5 Links in "Verwandte Funktionen"
- Kurze Beschreibung warum Link relevant ist
- Von wichtigsten zu weniger wichtigen Links
- Quality over Quantity
- **JETZT WEITER VORNE** in der Content-Struktur für bessere User Experience

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
- [ ] Cross-Links funktional (jetzt weiter vorne!)
- [ ] Meta-Keywords relevant

## 🔄 STRUKTUR-ÄNDERUNG (Session 5):
**WICHTIG:** "Verwandte Funktionen" wurde VOR "Technische Details" verschoben für bessere User Experience - normale User brauchen Cross-Links wichtiger als technische Details.