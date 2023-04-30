from functools import partial

from PySide6.QtGui import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QSlider, QGridLayout, QLabel, \
    QDialogButtonBox, QPushButton
from line_profiler_pycharm import profile

from database import schemas


class SliderWithPressEvent(QSlider):
    """only works for horizontal orientation"""

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            e.accept()
            x = e.pos().x()
            value = (self.maximum() - self.minimum()) * x / self.width() + self.minimum()
            value = round(value)
            if value == self.value():
                super().mousePressEvent(e)
            self.setValue(value)
        else:
            return super().mousePressEvent(e)


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
        self.loc_id__prefs = {loc_pref.location_of_work.id: loc_pref for loc_pref in self.loc_prefs}
        self.loc_id__results = self.locations_of_team__defaults | self.locations_of_prefs__score

        self.val2text = {0: 'nicht einsetzen', 1: 'notfalls einsetzen', 2: 'gerne einsetzen',
                         3: 'bevorzugt einsetzen', 4: 'unbedingt einsetzen'}

        self.layout = QVBoxLayout(self)
        self.layout_data = QGridLayout()
        self.layout.addLayout(self.layout_data)

        self.sliders = {}

        self.setup_sliders()

        self.autoload_data()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.bt_reset = QPushButton('Reset', clicked=self.reset)
        self.button_box.addButton(self.bt_reset, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def setup_sliders(self):
        for row, loc in enumerate(self.locations_of_team):
            lb_loc = QLabel(f'{loc.name} ({loc.address.city})')
            lb_val = QLabel()
            slider = SliderWithPressEvent(Qt.Orientation.Horizontal)
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

    def save_pref(self, location: schemas.LocationOfWork, value):
        self.loc_id__results[location.id] = value / 2

    def reset(self):
        for slider in self.sliders.values():
            slider.setValue(2)
        if self.parent_model:
            for pref in self.parent_model.actor_location_prefs_defaults:
                self.sliders[pref.location_of_work.id].setValue(int(pref.score * 2))

    def show_text(self, label: QLabel, event):
        label.setText(self.val2text[event])
