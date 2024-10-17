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

cell_backgrounds_statistics = {
            'requested': [QColor(40, 130, 160, 190), QColor(40, 150, 180, 190)],
            'able': [QColor(70, 130, 160, 190), QColor(70, 150, 180, 190)],
            'fair': [QColor(100, 130, 160, 190), QColor(100, 150, 180, 190)],
            'current': [QColor(130, 130, 160, 190), QColor(130, 150, 180, 190)]
        }
