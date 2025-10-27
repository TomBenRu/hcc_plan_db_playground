from PySide6.QtGui import QColor

horizontal_header_colors = [QColor('#006d6d'), QColor('teal')]
vertical_header_colors = [QColor('#005757'), QColor('#005050')]
locations_bg_color = '#003f57'
appointment_field_marked_bg = '#006016'
appointment_field_default = "background-color: #393939;"
appointment_field_marked = "background-color: #054C00;"
label_day_num_marked_bg = '#b7833f'
label_day_num_marked_fg = '#2b2b2b'
label_day_num_marked = "background-color: #b7833f; color: #2b2b2b"

horizontal_header_statistics_color = QColor('#00212f')
horizontal_header_statistics_color_guest = QColor('#262626')
vertical_header_statistics_color = QColor('#002a2a')
cell_backgrounds_statistics = {
            'requested': [QColor(40, 130, 160, 190), QColor(40, 150, 180, 190)],
            'able': [QColor(70, 130, 160, 190), QColor(70, 150, 180, 190)],
            'fair': [QColor(100, 130, 160, 190), QColor(100, 150, 180, 190)],
            'current': [QColor(130, 130, 160, 190), QColor(130, 150, 180, 190)]
        }

# Notiz-Icon Style für AppointmentField
appointment_field_note_icon_style = """
    QLabel#note_icon {
        background-color: rgba(0, 64, 64, 64);
        color: white;
        border-radius: 3px;
        padding: 2px 4px;
        font-size: 10pt;
    }
    QLabel#note_icon:hover {
        background-color: rgba(0, 128, 128, 220);
    }
"""

# ========================================
# Plan Table Styles
# ========================================

# Basis-Style für die Plan-Tabelle
plan_table_base_style = """
    QTableView {
        background-color: #2d2d2d; 
        color: white;
    }
"""

# Plan-Notizen Icon Style (OHNE Notizen - grauer Hintergrund)
plan_note_icon_default_style = """
    QLabel#plan_note_icon {
        background-color: rgba(37, 37, 37, 180);
        color: white;
        border-radius: 3px;
        padding: 3px 6px;
        font-size: 22pt;
    }
    QLabel#plan_note_icon:hover {
        background-color: rgba(53, 53, 53, 220);
    }
"""

# Plan-Notizen Icon Style (MIT Notizen - türkiser Hintergrund)
plan_note_icon_with_notes_style = """
    QLabel#plan_note_icon {
        background-color: rgba(0, 109, 109, 180);
        color: white;
        border-radius: 3px;
        padding: 3px 6px;
        font-size: 22pt;
    }
    QLabel#plan_note_icon:hover {
        background-color: rgba(0, 109, 109, 220);
    }
"""
