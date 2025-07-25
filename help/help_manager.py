"""
Vereinfachter Help Manager für HCC Plan - Browser-only

Zeigt Hilfe-Inhalte direkt im Standard-Browser an.
Keine Kompilierung oder Qt Assistant erforderlich.

Autor: HCC Plan Development Team  
Version: 2.0.0 (Vereinfacht)
"""

import os
import webbrowser
from pathlib import Path
from typing import Optional


class HelpManager:
    """Vereinfachter Browser-basierter Help Manager."""
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialisiert den Help Manager.
        
        Args:
            project_root: Pfad zum Projekt-Root (optional)
        """
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Automatisch ermitteln (3 Ebenen höher von help/help_manager.py)
            self.project_root = Path(__file__).parent.parent
            
        self.help_content_dir = self.project_root / "help" / "content"
        self.current_language = "de"  # Standard: Deutsch
        
    def set_language(self, language: str) -> bool:
        """
        Setzt die Sprache für die Hilfe.
        
        Args:
            language: Sprachcode ("de" oder "en")
            
        Returns:
            bool: True wenn erfolgreich
        """
        if language in ["de", "en"]:
            self.current_language = language
            return True
        return False
    
    def get_help_url(self, page: str = "index.html") -> Optional[str]:
        """
        Gibt die URL für eine Hilfe-Seite zurück.
        
        Args:
            page: HTML-Dateiname (z.B. "index.html", "forms/plan.html")
            
        Returns:
            str: file:// URL oder None wenn nicht verfügbar
        """
        help_file = self.help_content_dir / self.current_language / page
        
        if help_file.exists():
            # Konvertiere zu file:// URL
            return help_file.as_uri()
        
        return None
    
    def show_main_help(self) -> bool:
        """
        Zeigt die Haupt-Hilfe im Browser.
        
        Returns:
            bool: True wenn erfolgreich geöffnet
        """
        url = self.get_help_url("index.html")
        if url:
            try:
                webbrowser.open(url)
                return True
            except Exception as e:
                print(f"Fehler beim Öffnen der Hilfe: {e}")
        
        return False
    
    def show_help_for_form(self, form_name: str) -> bool:
        """
        Zeigt spezifische Hilfe für ein Formular.
        
        Args:
            form_name: Name des Formulars (z.B. "plan", "masterdata")
            
        Returns:
            bool: True wenn erfolgreich geöffnet
        """
        # Versuche spezifische Form-Hilfe
        form_url = self.get_help_url(f"forms/{form_name}.html")
        if form_url:
            try:
                webbrowser.open(form_url)
                return True
            except Exception:
                pass
        
        # Fallback zur Haupt-Hilfe
        return self.show_main_help()
    
    def show_context_help(self, context: str) -> bool:
        """
        Zeigt kontextuelle Hilfe.
        
        Args:
            context: Kontext-Identifier
            
        Returns:
            bool: True wenn erfolgreich geöffnet
        """
        # Für Vereinfachung: Zeige Haupt-Hilfe
        return self.show_main_help()
    
    def get_help_status(self) -> dict:
        """
        Gibt Status-Informationen zurück.
        
        Returns:
            dict: Status-Informationen
        """
        content_dir = self.help_content_dir / self.current_language
        index_file = content_dir / "index.html"
        
        return {
            "help_available": index_file.exists(),
            "current_language": self.current_language,
            "content_dir": str(content_dir),
            "content_exists": content_dir.exists(),
            "index_exists": index_file.exists(),
            "mode": "browser-only"
        }
    
    def is_help_available(self) -> bool:
        """
        Prüft ob Hilfe verfügbar ist.
        
        Returns:
            bool: True wenn Hilfe verfügbar
        """
        return self.get_help_status()["help_available"]
