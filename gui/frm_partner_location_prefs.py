from dataclasses import dataclass
from functools import partial
from typing import Literal, Callable
from uuid import UUID

from PySide6.QtGui import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QSlider, QGridLayout, QLabel, \
    QDialogButtonBox, QPushButton, QHBoxLayout, QCheckBox, QBoxLayout, QGroupBox
from line_profiler_pycharm import profile

from database import schemas, db_services
from gui.commands import command_base_classes, actor_partner_loc_pref_commands, person_commands, \
    actor_plan_period_commands, avail_day_commands
from gui.tools.slider_with_press_event import SliderWithPressEvent


class SliderValToText:

    val2text: dict[int, str] = {0: 'nicht einsetzen', 1: 'notfalls einsetzen', 2: 'gerne einsetzen',
                                3: 'bevorzugt einsetzen', 4: 'unbedingt einsetzen'}

    @classmethod
    def get_text(cls, val: int) -> str:
        if not (0 <= val <= 4):
            raise ValueError(f'Der Wert muss zwischen einschließlich 0-4 liegen. Aktuell: {val=}')
        else:
            return cls.val2text[val]


class ButtonStyles:

    dict_style_buttons: dict[
        Literal['all', 'some', 'none'], dict[Literal['color', 'text'], dict[Literal['partners', 'locs'], str]]] = {
        'all': {'color': {'locs': 'lightgreen', 'partners': 'lightgreen'},
                'text': {'locs': 'mit allen Mitarbeitern', 'partners': 'in allen Einrichtungen'}},
        'some': {'color': {'locs': 'lightorange', 'partners': 'lightorange'},
                 'text': {'locs': 'mit einigen Mitarbeitern', 'partners': 'in einigen Einrichtungen'}},
        'none': {'color': {'locs': 'lightred', 'partners': 'lightred'},
                 'text': {'locs': 'mit keinen Mitarbeitern', 'partners': 'in keinen Einrichtungen'}}
    }

    @classmethod
    def get_bg_color_text(cls, style: Literal['all', 'some', 'none'],
                          group: Literal['locs', 'partners']) -> tuple[str, str]:
        """Returns a tuple (button text, bg color)"""
        return cls.dict_style_buttons[style]['text'][group], cls.dict_style_buttons[style]["color"][group]


class DlgPartnerLocationPrefsLocs(QDialog):
    def __init__(self, parent, person: schemas.PersonShow, apl_with_partner: list[schemas.ActorPartnerLocationPref],
                 all_locations: list[schemas.LocationOfWork], controller: command_base_classes.ContrExecUndoRedo):
        super().__init__(parent)

        self.person = person.copy(deep=True)
        self.apl_with_partner = apl_with_partner
        self.all_locations = all_locations
        self.controller = controller
        self.dict_loc_id__slider: dict[UUID, SliderWithPressEvent] = {}
        self.dict_loc_id_score: dict[UUID, int] = {apl.location_of_work.id: apl.score for apl in apl_with_partner}

        self.layout = QVBoxLayout(self)
        self.layout_head = QHBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout_options = QGridLayout()
        self.layout.addLayout(self.layout_options)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_foot)

        self.setup_option_field()
        self.setup_values()

    def setup_option_field(self):
        for row, loc in enumerate(self.all_locations):
            lb_location = QLabel(f'{loc.name} ({loc.address.city}):')
            lb_loc_val = QLabel('Error')
            slider_location = SliderWithPressEvent(Qt.Orientation.Horizontal)
            slider_location.setMinimum(0)
            slider_location.setMaximum(4)
            slider_location.setFixedWidth(200)
            slider_location.setTickPosition(QSlider.TickPosition.TicksBelow)

            slider_location.valueChanged.connect(partial(self.save_pref_loc, loc))
            slider_location.valueChanged.connect(partial(self.show_slider_text, lb_loc_val))

            self.layout_options.addWidget(lb_location, row, 0)
            self.layout_options.addWidget(slider_location, row, 1)
            self.layout_options.addWidget(lb_loc_val, row, 2)

            self.dict_loc_id__slider[loc.id] = slider_location

    def setup_values(self):
        for loc in self.all_locations:
            if loc.id in self.dict_loc_id_score:
                self.dict_loc_id__slider[loc.id].setValue(int(self.dict_loc_id_score[loc.id]*2))
            else:
                self.dict_loc_id__slider[loc.id].setValue(2)

    def show_slider_text(self, lb_loc_val: QLabel, val: int):
        lb_loc_val.setText(SliderValToText.get_text(val))

    def save_pref_loc(self, location: schemas.LocationOfWork, value: int):
        ...


class DlgPartnerLocationPrefsPartner(QDialog):
    def __init__(self, parent, person: schemas.PersonShow, apl_with_location: list[schemas.ActorPartnerLocationPref],
                 all_partners: list[schemas.Person], controller: command_base_classes.ContrExecUndoRedo):
        super().__init__(parent)

        self.person = person.copy(deep=True)
        self.apl_with_location = apl_with_location
        self.all_partners = all_partners
        self.controller = controller
        self.dict_partner_id__slider: dict[UUID, SliderWithPressEvent] = {}
        self.dict_partner_id_score: dict[UUID, int] = {apl.partner.id: apl.score for apl in apl_with_location}

        self.layout = QVBoxLayout(self)
        self.layout_head = QHBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout_options = QGridLayout()
        self.layout.addLayout(self.layout_options)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_foot)

        self.setup_option_field()
        self.setup_values()

    def setup_option_field(self):
        for row, partner in enumerate(self.all_partners):
            lb_partner = QLabel(f'{partner.f_name} {partner.l_name}:')
            lb_slider_val = QLabel('Error')
            slider_partner = SliderWithPressEvent(Qt.Orientation.Horizontal)
            slider_partner.setMinimum(0)
            slider_partner.setMaximum(4)
            slider_partner.setFixedWidth(200)
            slider_partner.setTickPosition(QSlider.TickPosition.TicksBelow)

            slider_partner.valueChanged.connect(partial(self.save_pref_loc, partner))
            slider_partner.valueChanged.connect(partial(self.show_slider_text, lb_slider_val))

            self.layout_options.addWidget(lb_partner, row, 0)
            self.layout_options.addWidget(slider_partner, row, 1)
            self.layout_options.addWidget(lb_slider_val, row, 2)

            self.dict_partner_id__slider[partner.id] = slider_partner

    def setup_values(self):
        for partner in self.all_partners:
            if partner.id in self.dict_partner_id_score:
                self.dict_partner_id__slider[partner.id].setValue(int(self.dict_partner_id_score[partner.id]*2))
            else:
                self.dict_partner_id__slider[partner.id].setValue(2)

    def show_slider_text(self, lb_loc_val: QLabel, val: int):
        lb_loc_val.setText(SliderValToText.get_text(val))

    def save_pref_loc(self, location: schemas.LocationOfWork, value: int):
        ...


class DlgPartnerLocationPrefs(QDialog):
    """Hier werden die Mitarbeiter-Einrichtungs-Präferenzen festgelegt.
    Fall keine Präferenz einer besimmten Kombination vorhanden ist, wird sie als Präferenz mit Score=1 gewertet."""

    def __init__(self, parent, person: schemas.PersonShow, curr_model: schemas.ModelWithPartnerLocPrefs,
                 parent_model: schemas.ModelWithPartnerLocPrefs | None, team: schemas.TeamShow):
        super().__init__(parent)
        self.setWindowTitle('Partner-Präferenzen')

        self.layout = QVBoxLayout(self)
        self.layout_head = QHBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout_body = QHBoxLayout()
        self.layout.addLayout(self.layout_body)
        self.group_locations = QGroupBox('Einrichtungen')
        self.group_partners = QGroupBox('Mitarbeiter')
        self.layout_body.addWidget(self.group_locations)
        self.layout_body.addWidget(self.group_partners)
        self.layout_options_locs = QGridLayout(self.group_locations)
        self.layout_options_locs.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.layout_options_partners = QGridLayout(self.group_partners)
        self.layout_options_partners.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_foot)

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.person = person
        self.curr_model: schemas.ModelWithPartnerLocPrefs = curr_model.copy(deep=True)
        self.parent_model = parent_model
        self.team = team
        self.partners: list[schemas.Person] | None = None
        self.locations: list[schemas.LocationOfWork] | None = None

        self.dict_location_id__bt_slider: dict[UUID, dict[Literal['button', 'slider'], QPushButton | SliderWithPressEvent]] = {}
        self.dict_partner_id__bt_slider: dict[UUID, dict[Literal['button', 'slider'], QPushButton | SliderWithPressEvent]] = {}

        self.setup_data()
        self.setup_option_field()
        self.setup_values()

    def setup_data(self):
        self.partners = sorted([p for p in self.team.persons if not p.prep_delete and p.id != self.person.id],
                               key=lambda x: x.f_name)
        self.locations = sorted([loc for loc in self.team.locations_of_work if not loc.prep_delete],
                                key=lambda x: x.name)

    def setup_option_field(self):
        """Regler und Buttons für Locations und Partners werden hinzugefügt"""

        '''setup locations group:'''
        for row, loc in enumerate(self.locations):
            lb_location = QLabel(f'In {loc.name} ({loc.address.city}):')
            self.layout_options_locs.addWidget(lb_location, row, 0)
            bt_partners = QPushButton('Mitarbeiter', clicked=partial(self.choice_partners, loc.id))
            self.layout_options_locs.addWidget(bt_partners, row, 1)

            lb_loc_val = QLabel('Error')
            self.layout_options_locs.addWidget(lb_loc_val, row, 3)

            slider_location = SliderWithPressEvent(Qt.Orientation.Horizontal)
            slider_location.setMinimum(0)
            slider_location.setMaximum(4)
            slider_location.setFixedWidth(200)
            slider_location.setTickPosition(QSlider.TickPosition.TicksBelow)

            slider_location.valueChanged.connect(partial(self.save_pref_loc, loc))
            slider_location.valueChanged.connect(partial(self.show_slider_text, lb_loc_val))
            self.layout_options_locs.addWidget(slider_location, row, 2)

            self.dict_location_id__bt_slider[loc.id] = {}
            self.dict_location_id__bt_slider[loc.id]['button'] = bt_partners
            self.dict_location_id__bt_slider[loc.id]['slider'] = slider_location

        '''setup partners group:'''
        for row, partner in enumerate(self.partners):
            lb_partner = QLabel(f'Mit {partner.f_name} {partner.l_name}:')
            self.layout_options_partners.addWidget(lb_partner, row, 0)
            bt_locations = QPushButton('Einrichtungen', clicked=partial(self.choice_locations, partner.id))
            self.layout_options_partners.addWidget(bt_locations, row, 1)

            lb_partner_val = QLabel('Error')
            self.layout_options_partners.addWidget(lb_partner_val, row, 3)

            slider_partner = SliderWithPressEvent(Qt.Orientation.Horizontal)
            slider_partner.setMinimum(0)
            slider_partner.setMaximum(4)
            slider_partner.setFixedWidth(200)
            slider_partner.setTickPosition(QSlider.TickPosition.TicksBelow)

            slider_partner.valueChanged.connect(partial(self.save_pref_partner, partner))
            slider_partner.valueChanged.connect(partial(self.show_slider_text, lb_partner_val))
            self.layout_options_partners.addWidget(slider_partner, row, 2)

            self.dict_partner_id__bt_slider[partner.id] = {}
            self.dict_partner_id__bt_slider[partner.id]['button'] = bt_locations
            self.dict_partner_id__bt_slider[partner.id]['slider'] = slider_partner

    def setup_values(self):
        """Regler und Buttons bekommen die korrekten Einstellungen."""

        '''Einstellungen für Locations:'''
        for loc in self.locations:
            partner_vals_of_locations = [apl.score for apl in self.curr_model.actor_partner_location_prefs_defaults
                                         if not apl.prep_delete and apl.location_of_work.id == loc.id]

            if all(partner_vals_of_locations):  # all([]) is True
                self.set_bt__style_txt(self.dict_location_id__bt_slider[loc.id]['button'], 'all', 'locs')
                if not partner_vals_of_locations:
                    self.dict_location_id__bt_slider[loc.id]['slider'].setValue(2)
                else:
                    self.dict_location_id__bt_slider[loc.id]['slider'].setValue(int(max(partner_vals_of_locations)*2))
            elif any(partner_vals_of_locations):  # any([]) is True
                self.set_bt__style_txt(self.dict_location_id__bt_slider[loc.id]['button'], 'some', 'locs')
                if not partner_vals_of_locations:
                    self.dict_location_id__bt_slider[loc.id]['slider'].setValue(2)
                else:
                    self.dict_location_id__bt_slider[loc.id]['slider'].setValue(int(max(partner_vals_of_locations)*2))
            else:
                self.set_bt__style_txt(self.dict_location_id__bt_slider[loc.id]['button'], 'none', 'locs')
                self.dict_location_id__bt_slider[loc.id]['slider'].setValue(0)

        '''Einstellungen für Partner:'''
        for partner in self.partners:
            location_vals_of_partner = [apl.score for apl in self.curr_model.actor_partner_location_prefs_defaults
                                        if not apl.prep_delete and apl.partner.id == partner.id]

            if all(location_vals_of_partner):  # all([]) is True
                self.set_bt__style_txt(self.dict_partner_id__bt_slider[partner.id]['button'], 'all', 'partners')
                if not location_vals_of_partner:
                    self.dict_partner_id__bt_slider[partner.id]['slider'].setValue(2)
                else:
                    self.dict_partner_id__bt_slider[partner.id]['slider'].setValue(int(max(location_vals_of_partner)*2))
            elif any(location_vals_of_partner):  # any([]) is True
                self.set_bt__style_txt(self.dict_partner_id__bt_slider[partner.id]['button'], 'some', 'partners')
                if not location_vals_of_partner:
                    self.dict_partner_id__bt_slider[partner.id]['slider'].setValue(2)
                else:
                    self.dict_partner_id__bt_slider[partner.id]['slider'].setValue(int(max(location_vals_of_partner)*2))
            else:
                self.set_bt__style_txt(self.dict_partner_id__bt_slider[partner.id]['button'], 'none', 'partners')
                self.dict_partner_id__bt_slider[partner.id]['slider'].setValue(0)

    def reload_curr_model(self):
        self.curr_model = self.factory_for_reload_curr_model(self.curr_model)(self.curr_model.id)
        self.setup_values()

    def set_bt__style_txt(self, button: QPushButton, style: Literal['all', 'some', 'none'], group: Literal['locs', 'partners']):
        text, bg_color = ButtonStyles.get_bg_color_text(style, group)
        button.setText(text)
        button.setStyleSheet(f'background-color: {bg_color}')

    def show_slider_text(self, label: QLabel, value: int):
        label.setText(SliderValToText.get_text(value))

    def save_pref_loc(self, location: schemas.LocationOfWork, value: int):
        score = value / 2
        apls_with_loc: dict[UUID, schemas.ActorPartnerLocationPref] = {
            apl.partner.id: apl for apl in self.curr_model.actor_partner_location_prefs_defaults
            if not apl.prep_delete and apl.location_of_work.id == location.id}

        for partner in self.partners:
            if partner.id in apls_with_loc:
                apl = db_services.ActorPartnerLocationPref.get(apls_with_loc[partner.id].id)
                remove_command = self.factory_for_remove_prefs(self.curr_model, apl.id)
                self.controller.execute(remove_command)
                if score != 1:
                    new_apl_pref = schemas.ActorPartnerLocationPrefCreate(**apl.dict())
                    new_apl_pref.score = score
                    create_command = actor_partner_loc_pref_commands.Create(new_apl_pref)
                    self.controller.execute(create_command)
                    created_apl = create_command.get_created_actor_partner_loc_pref()
                    put_in_command = self.factory_for_put_in_prefs(self.curr_model, created_apl.id)
                    self.controller.execute(put_in_command)

                self.reload_curr_model()

            elif score != 1:
                new_apl_pref = schemas.ActorPartnerLocationPrefCreate(score=score, person=self.person, partner=partner,
                                                                      location_of_work=location)
                create_command = actor_partner_loc_pref_commands.Create(new_apl_pref)
                self.controller.execute(create_command)
                created_apl = create_command.get_created_actor_partner_loc_pref()
                put_in_command = self.factory_for_put_in_prefs(self.curr_model, created_apl.id)
                self.controller.execute(put_in_command)

                self.reload_curr_model()

    def save_pref_partner(self, partner: schemas.Person, value: int):
        ...

    def choice_partners(self, location_id: UUID):
        apl_with_partners = [apl for apl in self.curr_model.actor_partner_location_prefs_defaults
                             if not apl.prep_delete and apl.location_of_work.id == location_id]
        dlg = DlgPartnerLocationPrefsPartner(self, self.person, apl_with_partners, self.partners, self.controller)
        if dlg.exec():
            ...

    def choice_locations(self, partner_id: UUID):
        apl_with_location = [apl for apl in self.curr_model.actor_partner_location_prefs_defaults
                             if not apl.prep_delete and apl.partner.id == partner_id]
        dlg = DlgPartnerLocationPrefsLocs(self, self.person, apl_with_location, self.locations, self.controller)
        if dlg.exec():
            ...

    def factory_for_put_in_prefs(self, curr_model: schemas.ModelWithPartnerLocPrefs,
                                 pref_to_put_i_id: UUID) -> command_base_classes.Command:
        curr_model_name = curr_model.__class__.__name__
        curr_model_name__put_in_command = {
            'PersonShow': person_commands.PutInActorPartnerLocationPref,
            'ActorPlanPeriodShow': actor_plan_period_commands.PutInActorPartnerLocationPref,
            'AvailDay': avail_day_commands.PutInActorPartnerLocationPref,
            'AvailDayShow': avail_day_commands.PutInActorPartnerLocationPref}

        try:
            return curr_model_name__put_in_command[curr_model_name](curr_model.id, pref_to_put_i_id)
        except KeyError:
            raise KeyError(f'Für die Klasse {curr_model_name} ist noch kein Put-In-Command definiert.')

    def factory_for_remove_prefs(self, curr_model: schemas.ModelWithPartnerLocPrefs,
                                 pref_to_remove_id: UUID) -> command_base_classes.Command:
        curr_model_name = curr_model.__class__.__name__
        curr_model_name__remove_command = {
            'PersonShow': person_commands.RemoveActorPartnerLocationPref,
            'ActorPlanPeriodShow': actor_plan_period_commands.RemoveActorPartnerLocationPref,
            'AvailDay': avail_day_commands.RemoveActorPartnerLocationPref,
            'AvailDayShow': avail_day_commands.RemoveActorPartnerLocationPref}
        try:
            command_to_remove = curr_model_name__remove_command[curr_model_name]
            return command_to_remove(curr_model.id, pref_to_remove_id)
        except KeyError:
            raise KeyError(f'Für die Klasse {curr_model_name} ist noch kein Put-In-Command definiert.')

    def factory_for_reload_curr_model(self, curr_model: schemas.ModelWithPartnerLocPrefs) -> Callable:
        curr_model_name = curr_model.__class__.__name__
        curr_model_get = {'PersonShow': db_services.Person.get,
                          'ActorPlanPeriodShow': db_services.ActorPlanPeriod.get,
                          'AvailDay': db_services.AvailDay.get,
                          'AvailDayShow': db_services.AvailDay.get}
        return curr_model_get[curr_model_name]
