# Help-Integration Pattern - Development Guidelines Update

## 🎯 **Neues Pattern: Universal Help-Integration**

### **Standard-Pattern für alle Formulare:**
```python
# In jedem Formular __init__ hinzufügen:
from tools.helper_functions import setup_form_help

class SomeForm(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi()
        
        # Help-Integration (eine Zeile!)
        setup_form_help(self, "form_name")
```

### **Helper-Funktion (tools/helper_functions.py):**
```python
def setup_form_help(form_widget: QWidget, form_name: str):
    """Richtet standardmäßig Hilfe für ein Formular ein."""
    try:
        from help import get_help_manager, HelpIntegration
        help_manager = get_help_manager()
        if help_manager:
            help_integration = HelpIntegration(help_manager)
            help_integration.setup_f1_shortcut(form_widget, form_name)
            return True
    except Exception as e:
        logger.debug(f"Help-Integration für {form_name} fehlgeschlagen: {e}")
    return False
```

## 📋 **Implementation-Checklist**

### **Für jedes neue Formular:**
- [ ] `setup_form_help(self, "form_name")` in `__init__` hinzufügen
- [ ] Entsprechende HTML-Hilfe in `help/content/de/forms/form_name.html` erstellen
- [ ] F1-Funktionalität testen

### **Naming Convention:**
- Formular-Namen: lowercase mit underscores
- HTML-Dateien: exakt gleicher Name wie form_name Parameter
- Beispiele: "masterdata", "team", "calculate_plan", "actor_plan_period"

## 🛠️ **MainWindow Help-Pattern (Implementiert):**
```python
def open_help(self):
    """Öffnet das Hilfe-System im Browser mit robusten Fallbacks."""
    try:
        from help import get_help_manager, init_help_system
        help_manager = get_help_manager() or init_help_system()
        
        if help_manager and help_manager.is_help_available():
            if help_manager.show_main_help():
                return
        
        # Fallback mit benutzerfreundlicher Meldung
        QMessageBox.information(self, self.tr("Hilfe"), "...")
    except Exception as e:
        # Error-Handling mit Logging
        logger.error(f"Help-System Fehler: {e}")
```

## 🎯 **Best Practices:**

### **DO:**
- ✅ Eine Zeile pro Formular: `setup_form_help(self, "form_name")`
- ✅ Konsistente Namensgebung für form_name
- ✅ Graceful Error-Handling (keine Exceptions nach außen)
- ✅ Debug-Logging für Entwickler

### **DON'T:**
- ❌ Komplexe Help-Integration direkt in Formularen
- ❌ Hardcoded Help-URLs
- ❌ Exceptions bei fehlender Hilfe
- ❌ Unterschiedliche Integration-Patterns

## 🔄 **Migration-Strategy:**
1. Universal Helper implementieren
2. Top-Priority Formulare migrieren (masterdata, team, calculate_plan)
3. Content-Vervollständigung parallel
4. Weitere Formulare nach Bedarf

---
**Pattern Status:** Ready for Implementation  
**Next:** Universal Helper in tools/helper_functions.py erstellen
