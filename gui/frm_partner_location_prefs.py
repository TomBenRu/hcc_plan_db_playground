from functools import partial
from typing import Literal
from uuid import UUID

from PySide6.QtGui import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QSlider, QGridLayout, QLabel, \
    QDialogButtonBox, QPushButton, QHBoxLayout, QCheckBox
from line_profiler_pycharm import profile

from database import schemas, db_services
from gui.commands import command_base_classes
from gui.tools.slider_with_press_event import SliderWithPressEvent


class DlgPartnerLocationPrefsLocs(QDialog):
    def __init__(self, parent, person: schemas.PersonShow, apl_with_partner: list[schemas.ActorPartnerLocationPref],
                 all_locations: schemas.LocationOfWork, controller: command_base_classes.ContrExecUndoRedo):
        super().__init__(parent)

        self.layout = QVBoxLayout(self)
        self.layout_head = QHBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout_options = QGridLayout()
        self.layout.addLayout(self.layout_options)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_foot)


class DlgPartnerLocationPrefsPartner(QDialog):
    """Hier werden die Mitarbeiter-Einrichtungs-Präferenzen festgelegt.
    Fall keine Präferenz einer besimmten Kombination vorhanden ist, wird sie als Präferenz mit Score=1 gewertet."""

    def __init__(self, parent, person: schemas.PersonShow, curr_model: schemas.ModelWithPartnerLocPrefs,
                 parent_model: schemas.ModelWithPartnerLocPrefs | None, team: schemas.TeamShow):
        super().__init__(parent)
        self.setWindowTitle('Partner-Präferenzen')

        self.layout = QVBoxLayout(self)
        self.layout_head = QHBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout_options = QGridLayout()
        self.layout.addLayout(self.layout_options)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_foot)

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.person = person
        self.curr_model: schemas.ModelWithPartnerLocPrefs = curr_model.copy(deep=True)
        print(f'{self.curr_model.actor_partner_location_prefs_defaults=}')
        self.parent_model = parent_model
        self.team = team
        self.partners: list[schemas.Person] | None = None
        self.locations: list[schemas.LocationOfWork] | None = None

        self.dict_partner_id__bt_chk: dict[UUID, dict[Literal['button', 'check'], QPushButton | QCheckBox]] = {}
        self.dict_style: dict[
            Literal['all_locations', 'some_locations', 'no_locations'], dict[Literal['color', 'text'], str]] = {
            'all_locations': {'color': 'lightgreen', 'text': 'alle Einrichtungen'},
            'some_locations': {'color': 'orange', 'text': 'einige Einrichtungen'},
            'no_locations': {'color': 'red', 'text': 'keine Einrichtungen'}
        }

        self.setup_data()
        self.setup_option_field()
        self.setup_values()

    def setup_data(self):
        self.partners = sorted([p for p in self.team.persons if not p.prep_delete and p.id != self.person.id],
                               key=lambda x: x.f_name)
        self.locations = sorted([loc for loc in self.team.locations_of_work if not loc.prep_delete],
                                key=lambda x: x.name)

    def setup_option_field(self):
        for row, p in enumerate(self.partners):
            bt_locations = QPushButton('Einrichtungen', clicked=partial(self.choice_locations, p.id))
            self.layout_options.addWidget(bt_locations, row, 0)
            chk_all_locs = QCheckBox(f'{p.f_name} {p.l_name}')
            chk_all_locs.toggled.connect(partial(self.change_all_loc_vals, p.id))
            self.layout_options.addWidget(chk_all_locs, row, 1)

            self.dict_partner_id__bt_chk[p.id] = {}
            self.dict_partner_id__bt_chk[p.id]['button'] = bt_locations
            self.dict_partner_id__bt_chk[p.id]['check'] = chk_all_locs

    def setup_values(self):
        for partner in self.partners:
            loc_vals_of_partner = [apl.score for apl in self.curr_model.actor_partner_location_prefs_defaults
                                   if not apl.prep_delete and apl.partner.id == partner.id]

            if all(loc_vals_of_partner):  # all([]) is True
                self.set_bt__style_txt(self.dict_partner_id__bt_chk[partner.id]['button'], 'all_locations')
                self.dict_partner_id__bt_chk[partner.id]['check'].setChecked(True)
            elif any(loc_vals_of_partner):  # any([]) is True
                self.set_bt__style_txt(self.dict_partner_id__bt_chk[partner.id]['button'], 'some_locations')
                self.dict_partner_id__bt_chk[partner.id]['check'].setChecked(True)
            else:
                self.set_bt__style_txt(self.dict_partner_id__bt_chk[partner.id]['button'], 'no_locations')
                self.dict_partner_id__bt_chk[partner.id]['check'].setChecked(False)

    def set_bt__style_txt(self, button: QPushButton, style: Literal['all_locations', 'some_locations', 'no_locations']):
        button.setText(self.dict_style[style]['text'])
        button.setStyleSheet(f'background-color: {self.dict_style[style]["color"]}')

    def save_preferenz(self, partner: schemas.Person, value: int):
        ...

    def change_all_loc_vals(self, partner_id: UUID, toggled):
        print(partner_id, toggled)

    def choice_locations(self, partner_id: UUID):
        print(partner_id)
        apl_with_partner = [apl for apl in self.curr_model.actor_partner_location_prefs_defaults
                          if not apl.prep_delete and apl.partner.id == partner_id]
        dlg = DlgPartnerLocationPrefsLocs(self, self.person, apl_with_partner, self.locations, self.controller)
        if dlg.exec():
            ...
