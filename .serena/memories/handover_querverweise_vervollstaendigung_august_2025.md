# HANDOVER: HILFE-SYSTEM QUERVERWEISE VERVOLLSTÄNDIGUNG - AUGUST 2025

## 🎯 **AUFGABE FÜR NÄCHSTE KONVERSATION:**

Vervollständigung der **Querverweise** im HCC Plan Hilfe-System. **ALLE F1-Integrationen sind bereits 100% funktional** - es geht NUR um bessere Navigation zwischen den Hilfe-Seiten.

## 📋 **SOFORTIGE AUFGABE:**

### **START MIT: help/content/de/index.html**
**Problem:** Startseite hat nur 4 Links zu plan.html, masterdata.html, team.html, calendar.html  
**Ziel:** Alle 44 verfügbaren Hilfe-Seiten in logischen Kategorien organisieren

### **VERFÜGBARE 44 HTML-DATEIEN (alle vollständig):**
```
actor_plan_period.html, address_edit.html, assign_to_team.html, avail_at_day.html,
calculate_plan.html, calendar.html, cast_groups.html, cast_group_properties.html,
cast_rule.html, cast_rules.html, comb_loc_possible_edit_list.html, 
create_google_calendar.html, create_project.html, edit_appointment.html,
employee_event_categories.html, employee_event_details.html, employee_event_main.html,
event_planning_rules.html, excel_export.html, first_day.html, fixed_cast.html,
general_settings.html, google_calendar.html, group_mode.html, group_properties.html,
group_properties_avail_day.html, guest.html, location_plan_period.html,
masterdata.html, move_appointment.html, new_comb_loc_possible.html, notes.html,
num_actors_app.html, participant_selection.html, partner_location_prefs.html,
partner_location_prefs_locs.html, partner_location_prefs_partner.html, plan.html,
plan_period_create.html, project_settings.html, requested_assignments.html,
skills.html, skill_groups.html, team.html, time_of_day.html
```

## 🏗️ **VORGESCHLAGENE KATEGORIEN FÜR INDEX.HTML:**

### **1. 📊 Hauptplanung**
- plan.html, calculate_plan.html, actor_plan_period.html, location_plan_period.html

### **2. 👥 Stammdaten & Teams**  
- masterdata.html, address_edit.html, team.html, skills.html, skill_groups.html, assign_to_team.html

### **3. 📅 Event-Management**
- employee_event_main.html, employee_event_details.html, employee_event_categories.html, participant_selection.html

### **4. ⚙️ Konfiguration & Einstellungen**
- project_settings.html, general_settings.html, time_of_day.html, requested_assignments.html

### **5. 🎭 Cast-Management** 
- fixed_cast.html, cast_groups.html, cast_group_properties.html, cast_rule.html, cast_rules.html

### **6. 📋 Planungs-Tools**
- edit_appointment.html, move_appointment.html, avail_at_day.html, guest.html, notes.html

### **7. 📤 Export & Integration**
- excel_export.html, google_calendar.html, create_google_calendar.html

### **8. 🚀 Erweiterte Funktionen**
- event_planning_rules.html, first_day.html, partner_location_prefs.html, group_mode.html

## 📖 **STYLE-GUIDELINES:**

**Verwende:** help_system_content_guidelines_august_2025.md Memory für korrekte Formatierung
- `<ul class="feature-list">` für Listen  
- Beschreibende Texte zu jeder Kategorie
- Visuelle Icons/Emojis für bessere Übersichtlichkeit
- Breadcrumb-Navigation korrekt setzen

## 🔄 **NACH INDEX.HTML - WEITERE QUERVERWEISE:**

### **Priorität 2: plan.html erweitern**
- Aktuelle Links: 5, sollte haben: 12+
- Fehlen: edit_appointment.html, move_appointment.html, avail_at_day.html, guest.html, notes.html, assign_to_team.html, requested_assignments.html

### **Priorität 3: masterdata.html erweitern** 
- Aktuelle Links: 4, sollte haben: 10+
- Fehlen: skills.html, assign_to_team.html, address_edit.html, requested_assignments.html, time_of_day.html, excel_export.html

## 🛠️ **SETUP FÜR NEUE KONVERSATION:**

### **Projekt aktivieren:**
```bash
serena:activate_project hcc_plan_db_playground
```

### **Relevante Memories lesen:**
- help_system_content_guidelines_august_2025 (für Formatierung)
- help_system_documentation_completion_august_2025 (für Kontext)

### **Aktuellen Stand prüfen:**
```bash
serena:read_file help/content/de/index.html
```

## ✅ **ERFOLGSKRITERIEN:**

1. **Index.html:** Alle 44 Seiten sinnvoll kategorisiert und verlinkt
2. **Navigation:** Benutzer findet schnell relevante Hilfe-Seiten  
3. **Konsistenz:** Gleicher Stil wie vorhandene vollständige HTML-Dateien
4. **Vollständigkeit:** Keine wichtigen Funktionen vergessen

## ⚡ **ZEITSCHÄTZUNG:**
- Index.html Überarbeitung: 45-60 Min
- plan.html Querverweise: 20 Min  
- masterdata.html Querverweise: 20 Min
- **Gesamt:** 1,5-2 Stunden für deutliche Verbesserung der Navigation

## 🎉 **WICHTIGER HINWEIS:**
Das Hilfe-System ist **funktional vollständig** - alle F1-Integrationen arbeiten perfekt! Es geht nur um Benutzerfreundlichkeit durch bessere Querverweise.

**NÄCHSTER BEFEHL:**
"Erweitere help/content/de/index.html um alle 44 verfügbaren Hilfe-Seiten in den vorgeschlagenen Kategorien zu organisieren."