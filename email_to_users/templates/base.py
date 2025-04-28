"""
Basisklasse für E-Mail-Templates.

Dieses Modul enthält die abstrakte Basisklasse, die von allen spezifischen
E-Mail-Template-Klassen erweitert werden soll.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple


class EmailTemplate(ABC):
    """Abstrakte Basisklasse für E-Mail-Templates."""
    
    def __init__(self, subject_template: str):
        """
        Initialisiert das Template.
        
        Args:
            subject_template: Template für den Betreff der E-Mail
        """
        self.subject_template = subject_template
        
    @abstractmethod
    def render(self, **kwargs) -> Tuple[str, str, str]:
        """
        Rendert das Template mit den angegebenen Parametern.
        
        Args:
            **kwargs: Schlüsselwortargumente für das Template
            
        Returns:
            Ein Tupel mit (Betreff, Plaintext-Inhalt, HTML-Inhalt)
        """
        pass
        
    def _render_subject(self, params: Dict[str, Any]) -> str:
        """
        Rendert den Betreff mit den angegebenen Parametern.
        
        Args:
            params: Dictionary mit Parametern für das Template
            
        Returns:
            Der gerenderte Betreff
        """
        try:
            return self.subject_template.format(**params)
        except KeyError:
            # Fallback, wenn Parameter fehlen
            return self.subject_template
            
    def _format_template(self, template: str, params: Dict[str, Any]) -> str:
        """
        Formatiert ein Template mit den angegebenen Parametern.
        
        Args:
            template: Das Template mit Platzhaltern
            params: Dictionary mit Parametern für die Personalisierung
            
        Returns:
            Das formatierte Template
        """
        try:
            return template.format(**params)
        except KeyError:
            # Fallback, wenn Parameter fehlen
            return template
