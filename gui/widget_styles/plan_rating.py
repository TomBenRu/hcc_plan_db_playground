"""
Styles für die Planbewertungs-Widgets.

Definiert das visuelle Erscheinungsbild des Score-Rings,
der Objective-Cards und des Gesamt-Layouts.
Passend zum türkisen Design des Slide-In-Menus.
"""

# Farben für Ampel-System
SCORE_COLORS = {
    'green': '#28a745',      # Bootstrap success green
    'yellow': '#ffc107',     # Bootstrap warning yellow
    'red': '#dc3545',        # Bootstrap danger red
    'background': 'rgba(255, 255, 255, 0.95)',
    'track': '#e9ecef',      # Hellgrau für Ring-Hintergrund
    'text': '#1a3333',       # Dunkles Türkis für Text
}

# Header-Stil für "Planbewertung" Titel
HEADER_STYLE = """
    QLabel {
        font-size: 14px;
        font-weight: bold;
        color: #1a3333;
        padding: 5px 0;
    }
"""

# Score-Ring Container
SCORE_RING_CONTAINER_STYLE = """
    QWidget {
        background-color: transparent;
        padding: 10px;
    }
"""

# Objective Card Stil
OBJECTIVE_CARD_STYLE = """
    QFrame {
        background-color: rgba(255, 255, 255, 0.95);
        border: 1px solid rgba(0, 109, 109, 0.2);
        border-radius: 8px;
        padding: 2px;
    }
    QFrame:hover {
        border: 1px solid rgba(0, 109, 109, 0.5);
        background-color: rgba(245, 252, 251, 0.98);
    }
"""

# Card Header (Icon + Name)
CARD_HEADER_STYLE = """
    QLabel {
        font-size: 11px;
        font-weight: bold;
        color: #1a3333;
        padding: 0;
    }
"""

# Card Score (große Prozentzahl)
def get_card_score_style(color: str) -> str:
    """Generiert Stil für Score-Label mit dynamischer Farbe."""
    hex_color = SCORE_COLORS.get(color, SCORE_COLORS['text'])
    return f"""
        QLabel {{
            font-size: 16px;
            font-weight: bold;
            color: {hex_color};
            padding: 2px 0;
        }}
    """

# "Keine Bewertung" Platzhalter
NO_RATING_STYLE = """
    QLabel {
        color: #888888;
        font-style: italic;
        font-size: 12px;
        padding: 20px;
    }
"""

# Timestamp-Anzeige
TIMESTAMP_STYLE = """
    QLabel {
        color: #888888;
        font-size: 9px;
        padding: 2px 0;
    }
"""

# Container für das gesamte Rating-Widget
RATING_CONTAINER_STYLE = """
    QWidget {
        background-color: transparent;
    }
"""

# Stil für den Aktualisieren-Button (verwendet BUTTON_STYLE aus slide_menu)
# Hier für Referenz:
REFRESH_BUTTON_STYLE = """
    QPushButton {
        background-color: rgba(230, 245, 243, 0.88);
        color: #1a3333;
        border: 1px solid rgba(0, 109, 109, 0.3);
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 600;
    }
    QPushButton:hover {
        background-color: rgba(245, 252, 251, 0.95);
        border: 1px solid #006d6d;
    }
    QPushButton:pressed {
        background-color: #006d6d;
        color: white;
    }
    QPushButton:disabled {
        background-color: rgba(150, 150, 150, 0.5);
        color: #666666;
        border: 1px solid rgba(100, 100, 100, 0.3);
    }
"""

# Separator-Linie zwischen Sections
SEPARATOR_STYLE = """
    QFrame {
        background-color: rgba(0, 109, 109, 0.2);
        max-height: 1px;
        margin: 5px 0;
    }
"""
