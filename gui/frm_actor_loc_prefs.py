import datetime
from functools import partial
from typing import Callable
from uuid import UUID

from PySide6.QtGui import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QSlider, QGridLayout, QLabel, \
    QDialogButtonBox, QPushButton, QDateEdit, QHBoxLayout

from database import schemas, db_services
from database.special_schema_requests import get_curr_locations_of_team, get_locations_of_team_at_date, \
    get_curr_assignment_of_person
from gui.tools.slider_with_press_event import SliderWithPressEvent


class DlgActorLocPref(QDialog):
    def __init__(self, parent: QWidget, curr_model: schemas.ModelWithActorLocPrefs,
                 parent_model: schemas.ModelWithActorLocPrefs | None,
                 team_at_date_factory: Callable[[datetime.date], schemas.Team] | None):
        super().__init__(parent)

        self.setWindowTitle('Einrichtungspräferenzen')

        self.curr_model: schemas.ModelWithActorLocPrefs = curr_model.copy(deep=True)
        self.parent_model = parent_model
        self.team_at_date_factory = team_at_date_factory
        self.curr_team: schemas.Team | None = None
        self.locations_of_work: list[schemas.LocationOfWork] = []
        self.locations_of_team__defaults: dict[UUID, int] = {}
        self.loc_prefs: list[schemas.ActorLocationPref] = []

        self.locations_of_prefs__score = {}

        '''Die folgenden 3 Dictionaries werden zur Auswehrtung benutzt.'''
        self.location_id__location = {}
        self.loc_id__prefs = {}
        self.loc_id__results = self.locations_of_team__defaults | self.locations_of_prefs__score

        self.val2text = {0: 'nicht einsetzen', 1: 'notfalls einsetzen', 2: 'gerne einsetzen',
                         3: 'bevorzugt einsetzen', 4: 'unbedingt einsetzen'}

        self.layout = QVBoxLayout(self)
        self.layout_date = QHBoxLayout()
        self.layout_data = QGridLayout()

        self.lb_info = QLabel()
        self.layout.addWidget(self.lb_info)
        self.layout.addLayout(self.layout_date)
        self.layout.addLayout(self.layout_data)

        self.lb_date = QLabel('Datum')
        self.de_date = QDateEdit()
        self.de_date.dateChanged.connect(self.date_changed)
        self.layout_date.addWidget(self.lb_date)
        self.layout_date.addWidget(self.de_date)

        self.lb_sliders: list[QWidget] = []
        self.sliders: dict[UUID, QSlider] = {}

        self.de_date.setMinimumDate(datetime.date.today())

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.bt_reset = QPushButton('Reset', clicked=self.reset)
        self.button_box.addButton(self.bt_reset, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def date_changed(self):
        self.set_new__locations()
        self.setup_sliders()
        self.autoload_data()

    def set_new__locations(self):
        self.curr_team = self.team_at_date_factory(self.de_date.date().toPython())
        if isinstance(self.curr_model, schemas.ActorPlanPeriod):
            self.union_locations_of_work()
        elif not self.curr_team:
            self.locations_of_work = []
        else:
            self.locations_of_work = get_locations_of_team_at_date(self.curr_team.id, self.de_date.date().toPython())

        self.locations_of_work.sort(key=lambda x: x.name + x.address.city)
        self.locations_of_team__defaults = {loc.id: 2 for loc in self.locations_of_work}
        self.loc_prefs = [p for p in self.curr_model.actor_location_prefs_defaults
                          if (not p.prep_delete) and (p.location_of_work.id in self.locations_of_team__defaults)]
        self.locations_of_prefs__score = {p.location_of_work.id: p.score for p in self.loc_prefs}

        self.location_id__location = {loc.id: loc for loc in self.locations_of_work}
        self.loc_id__prefs = {loc_pref.location_of_work.id: loc_pref for loc_pref in self.loc_prefs}

    def union_locations_of_work(self):
        """Vereinigung aus allen möglichen Locations an den Tagen der Planungsperiode werden gebildet"""
        person: schemas.PersonShow = self.parent_model
        days_of_plan_period = [self.curr_model.plan_period.start + datetime.timedelta(delta) for delta in
                               range((self.curr_model.plan_period.end - self.curr_model.plan_period.start).days + 1)]
        valid_days_of_actor = [date for date in days_of_plan_period
                               if get_curr_assignment_of_person(person, date).team.id == self.curr_team.id]

        curr_loc_of_work_ids = {loc.id for loc in
                                get_locations_of_team_at_date(self.curr_team.id, valid_days_of_actor[0])}

        self.lb_info.setText('An allen Tagen des Zeitraums gehören dem Team die gleichen Einrichtungen zu.')
        for date in valid_days_of_actor[1:]:
            location_ids = {loc.id for loc in get_locations_of_team_at_date(self.curr_team.id, date)}
            if location_ids != curr_loc_of_work_ids:
                self.lb_info.setText(
                    'Nicht an allen Tagen des Zeitraums gehören dem Team die gleichen Einrichtungen zu.')

            curr_loc_of_work_ids |= location_ids

        self.locations_of_work = [db_services.LocationOfWork.get(loc_id) for loc_id in curr_loc_of_work_ids]


    def delete_sliders_labels(self):
        for slider in self.sliders.values():
            slider.setParent(None)
            slider.deleteLater()
        self.sliders = {}
        for label in self.lb_sliders:
            label.setParent(None)
            label.deleteLater()
        self.lb_sliders = []

    def setup_sliders(self):
        self.delete_sliders_labels()
        for row, loc in enumerate(self.locations_of_work):
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
            self.lb_sliders.extend([lb_loc, lb_val])

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
                if not pref.prep_delete and self.sliders.get(pref.location_of_work.id):
                    self.sliders[pref.location_of_work.id].setValue(int(pref.score * 2))

    def show_text(self, label: QLabel, event):
        label.setText(self.val2text[event])
