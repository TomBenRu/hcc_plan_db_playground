"""Styles for SlideInMenu buttons and checkboxes."""
import os

# Pfad zum tick-white Icon
_ICON_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'resources', 'toolbar_icons', 'icons', 'tick-white.png'
).replace('\\', '/')

BUTTON_STYLE = """
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

CHECKBOX_CONTAINER_STYLE = f"""
    QWidget {{
        background-color: rgba(230, 245, 243, 0.88);
        border: 1px solid rgba(0, 109, 109, 0.3);
        border-radius: 6px;
    }}
    QWidget:hover {{
        background-color: rgba(245, 252, 251, 0.95);
        border: 1px solid #006d6d;
    }}
    QCheckBox {{
        color: #1a3333;
        font-weight: 600;
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 2px solid rgba(0, 109, 109, 0.5);
        border-radius: 4px;
        background-color: rgba(255, 255, 255, 0.9);
    }}
    QCheckBox::indicator:hover {{
        border: 2px solid #006d6d;
        background-color: rgba(230, 245, 245, 0.95);
    }}
    QCheckBox::indicator:checked {{
        background-color: #006d6d;
        border: 2px solid #004d4d;
        image: url({_ICON_PATH});
    }}
    QCheckBox::indicator:checked:hover {{
        background-color: #008888;
        image: url({_ICON_PATH});
    }}
    QCheckBox:disabled {{
        color: #666666;
    }}
    QCheckBox::indicator:disabled {{
        background-color: rgba(150, 150, 150, 0.5);
        border: 2px solid rgba(100, 100, 100, 0.3);
    }}
"""

PIN_BUTTON_STYLE = """
    QPushButton {
        background-color: rgba(255, 255, 255, 150);
        border: 1px solid #ccc;
        border-radius: 3px;
        font-size: 10px;
    }
    QPushButton:hover {
        background-color: rgba(255, 255, 255, 200);
    }
    QPushButton:checked {
        background-color: #006d6d;
        color: white;
        border: 1px solid #004d4d;
    }
"""
