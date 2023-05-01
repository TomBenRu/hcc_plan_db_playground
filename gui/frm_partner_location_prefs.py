from functools import partial

from PySide6.QtGui import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QSlider, QGridLayout, QLabel, \
    QDialogButtonBox, QPushButton, QHBoxLayout
from line_profiler_pycharm import profile

from database import schemas, db_services
from gui.tools.slider_with_press_event import SliderWithPressEvent


class DlgPartnerLocationPrefsLocs(QDialog):
    def __init__(self, parent, person: schemas.PersonShow):
        super().__init__(parent)


class DlgPartnerLocationPrefsPartner(QDialog):
    def __init__(self, parent, person: schemas.PersonShow, curr_model: schemas.ModelWithPartnerLocPrefs,
                 parent_model: schemas.ModelWithPartnerLocPrefs | None, team: schemas.TeamShow):
        super().__init__(parent)
        self.setWindowTitle('Partner-Präferenzen')

        self.layout = QVBoxLayout(self)
        self.layout_head = QHBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout_options = QGridLayout()
        self.layout.addLayout(self.layout_options)
        self.layout_foot = QHBoxLayout()
        self.layout.addLayout(self.layout_foot)

        self.person = person
        self.curr_model = curr_model
        self.parent_model = parent_model
        self.team = team
        self.partners: schemas.Person | None = None
        self.locations: schemas.LocationOfWork | None = None

    def setup_data(self):
        self.partners = sorted([p for p in self.team.persons if not p.prep_delete and p.id != self.person.id],
                               key=lambda x: x.name)
        self.locations = sorted([loc for loc in self.team.locations_of_work if not loc.prep_delete],
                                key=lambda x: x.name)

    def setup_option_field(self):
        for row, p in enumerate(self.partners):
            bt_locations = QPushButton('Einrichtungen', clicked=self.choice_locations)
            self.layout_options.addWidget(bt_locations, row, 0)

            lb_value = QLabel()
            self.layout_options.addWidget(lb_value, row, 2)

            slider = SliderWithPressEvent(Qt.Orientation.Horizontal, self)
            slider.setMinimum(0)
            slider.setMaximum(4)
            slider.setFixedWidth(200)
            slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            slider.valueChanged.connect(partial(self.save_preferenz, p))
            slider.valueChanged.connect(partial(self.show_text, lb_value))
            self.layout_options.addWidget(slider, row, 1)

    def save_preferenz(self, partner: schemas.Person, value: int):
        ...

    def show_text(self, label: QLabel, value: int):
        ...

    def choice_locations(self):
        ...
