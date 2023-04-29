from functools import partial

from PySide6.QtGui import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QSlider, QGridLayout, QLabel

from database import schemas


class DlgActorLocPref(QDialog):
    def __init__(self, parent: QWidget, curr_model: schemas.ModelWithActorLocPrefs,
                 parent_model: schemas.ModelWithActorLocPrefs | None, team: schemas.TeamShow):
        super().__init__(parent)

        self.setWindowTitle('Einrichtungspräferenzen')

        self.curr_model = curr_model.copy(deep=True)
        self.parent_model = parent_model
        self.team = team
        self.locations_of_team = sorted([loc for loc in self.team.locations_of_work if not loc.prep_delete],
                                        key=lambda x: x.name)
        self.locations_of_team__defaults = {loc.id: 2 for loc in self.locations_of_team}
        self.loc_prefs = [p for p in self.curr_model.actor_location_prefs_defaults if not p.prep_delete]

        self.locations_of_prefs__score = {p.location_of_work.id: p.score for p in self.loc_prefs}

        '''Die folgenden 3 Dictionaries werden zur Auswehrtung benutzt.'''
        self.location_id__location = {loc.id: loc for loc in self.locations_of_team}
        self.loc_id__prefs = {loc.location_of_work.id: loc for loc in self.loc_prefs}
        self.loc_id__results = self.locations_of_team__defaults | self.locations_of_prefs__score

        self.val2text = {0: 'nicht einsetzen', 1: 'notfalls einsetzen', 2: 'gerne einsetzen',
                         3: 'bevorzugt einsetzen', 4: 'unbedingt einsetzen'}

        self.layout = QVBoxLayout(self)
        self.layout_data = QGridLayout()
        self.layout.addLayout(self.layout_data)

        self.sliders = {}

        self.setup_sliders()

        self.autoload_data()

    def setup_sliders(self):
        for row, loc in enumerate(self.locations_of_team):
            lb_loc = QLabel(f'{loc.name} ({loc.address.city})')
            lb_val = QLabel()
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(4)
            slider.setFixedWidth(200)
            slider.setTickPosition(QSlider.TickPosition.TicksBelow)

            slider.valueChanged.connect(partial(self.save_pref, loc))
            slider.valueChanged.connect(partial(self.show_text, lb_val))
            self.layout_data.addWidget(lb_loc, row, 0)
            self.layout_data.addWidget(slider, row, 1)
            self.layout_data.addWidget(lb_val, row, 2)

            self.sliders[loc.id] = slider

    def autoload_data(self):
        for slider in self.sliders.values():
            slider.setValue(2)
        for pref in self.loc_prefs:
            self.sliders[pref.location_of_work.id].setValue(int(pref.score * 2))

    def save_pref(self, location: schemas.LocationOfWork, event):
        print(location.name, event)
        self.loc_id__results[location.id] = event / 2
        print(self.loc_id__results)

    def show_text(self, label: QLabel, event):
        label.setText(self.val2text[event])
