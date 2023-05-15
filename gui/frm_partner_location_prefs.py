import time
from functools import partial
from typing import Literal, Callable
from uuid import UUID

from PySide6.QtGui import Qt
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QSlider, QGridLayout, QLabel, \
    QDialogButtonBox, QPushButton, QHBoxLayout, QCheckBox, QBoxLayout, QGroupBox, QMenu, QStatusBar
from line_profiler_pycharm import profile

from database import schemas, db_services
from database.special_schema_requests import get_curr_persons_of_team, get_curr_locations_of_team
from gui.actions import Action
from gui.commands import command_base_classes, actor_partner_loc_pref_commands, person_commands, \
    actor_plan_period_commands, avail_day_commands
from gui.tools.slider_with_press_event import SliderWithPressEvent


def factory_for_put_in_prefs(curr_model: schemas.ModelWithPartnerLocPrefs,
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


def factory_for_remove_prefs(curr_model: schemas.ModelWithPartnerLocPrefs,
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


def factory_for_reload_curr_model(curr_model: schemas.ModelWithPartnerLocPrefs) -> Callable:
    curr_model_name = curr_model.__class__.__name__
    curr_model_get = {'PersonShow': db_services.Person.get,
                      'ActorPlanPeriodShow': db_services.ActorPlanPeriod.get,
                      'AvailDay': db_services.AvailDay.get,
                      'AvailDayShow': db_services.AvailDay.get}
    return curr_model_get[curr_model_name]


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
        'some': {'color': {'locs': 'orange', 'partners': 'orange'},
                 'text': {'locs': 'mit einigen Mitarbeitern', 'partners': 'in einigen Einrichtungen'}}
    }

    @classmethod
    def get_bg_color_text(cls, style: Literal['all', 'some', 'none'],
                          group: Literal['locs', 'partners']) -> tuple[str, str]:
        """Returns a tuple (button text, bg color)"""
        return cls.dict_style_buttons[style]['text'][group], cls.dict_style_buttons[style]["color"][group]


class DlgPartnerLocationPrefsLocs(QDialog):
    def __init__(self, parent, person: schemas.PersonShow, curr_model: schemas.ModelWithPartnerLocPrefs,
                 partner_id: UUID, all_locations: list[schemas.LocationOfWork]):
        super().__init__(parent)

        self.person = person.copy(deep=True)
        self.curr_model = curr_model
        self.partner_id = partner_id
        self.all_locations = all_locations

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.apls_with_partner: list[schemas.ActorPartnerLocationPref] = []
        self.dict_location_id__apl: dict[UUID, schemas.ActorPartnerLocationPref] = {}
        self.dict_location_id__slider: dict[UUID, SliderWithPressEvent] = {}
        self.dict_location_id_score: dict[UUID, int] = {}

        self.layout = QVBoxLayout(self)
        self.layout_head = QHBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout_options = QGridLayout()
        self.layout.addLayout(self.layout_options)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_foot)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

        self.setup_data()
        self.setup_option_field()
        self.setup_values()
        self.connect_sliders_to_save()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def setup_data(self):
        self.apls_with_partner = [apl for apl in self.curr_model.actor_partner_location_prefs_defaults
                                  if not apl.prep_delete and apl.partner.id == self.partner_id]
        self.dict_location_id__apl = {apl.location_of_work.id: apl for apl in self.apls_with_partner}
        self.dict_location_id_score: dict[UUID, int] = {apl.location_of_work.id: apl.score
                                                        for apl in self.apls_with_partner}

    def setup_option_field(self):
        for row, location in enumerate(self.all_locations):
            lb_location = QLabel(f'{location.name} ({location.address.city}):')
            lb_slider_val = QLabel('Error')
            slider_location = SliderWithPressEvent(Qt.Orientation.Horizontal)
            slider_location.setMinimum(0)
            slider_location.setMaximum(4)
            slider_location.setFixedWidth(200)
            slider_location.setTickPosition(QSlider.TickPosition.TicksBelow)

            slider_location.valueChanged.connect(partial(self.show_slider_text, lb_slider_val))

            self.layout_options.addWidget(lb_location, row, 0)
            self.layout_options.addWidget(slider_location, row, 1)
            self.layout_options.addWidget(lb_slider_val, row, 2)

            self.dict_location_id__slider[location.id] = slider_location

    def connect_sliders_to_save(self):
        for location_id, slider in self.dict_location_id__slider.items():
            location = db_services.LocationOfWork.get(location_id)
            slider.valueChanged.connect(partial(self.save_pref_loc, location))

    def setup_values(self):
        for location in self.all_locations:
            if location.id in self.dict_location_id_score:
                self.dict_location_id__slider[location.id].setValue(int(self.dict_location_id_score[location.id]*2))
            else:
                self.dict_location_id__slider[location.id].setValue(2)

    def show_slider_text(self, lb_loc_val: QLabel, val: int):
        lb_loc_val.setText(SliderValToText.get_text(val))

    def save_pref_loc(self, location: schemas.LocationOfWork, value: int):
        if location.id in self.dict_location_id__apl:
            apl = self.dict_location_id__apl[location.id]
            remove_command = factory_for_remove_prefs(self.curr_model, apl.id)
            self.controller.execute(remove_command)

        if value != 2:
            if location.id in self.dict_location_id__apl:
                new_apl = schemas.ActorPartnerLocationPrefCreate(**apl.dict())
                new_apl.score = value / 2
            else:
                partner = db_services.Person.get(self.partner_id)
                new_apl = schemas.ActorPartnerLocationPrefCreate(
                    score=value/2, person=self.person, partner=partner, location_of_work=location)

            create_command = actor_partner_loc_pref_commands.Create(new_apl)
            self.controller.execute(create_command)

            created_apl = create_command.get_created_actor_partner_loc_pref()
            put_in_command = factory_for_put_in_prefs(self.curr_model, created_apl.id)
            self.controller.execute(put_in_command)

        self.curr_model = factory_for_reload_curr_model(self.curr_model)(self.curr_model.id)
        self.setup_data()


class DlgPartnerLocationPrefsPartner(QDialog):
    def __init__(self, parent, person: schemas.PersonShow, curr_model: schemas.ModelWithPartnerLocPrefs,
                 location_id: UUID, all_partners: list[schemas.Person]):
        super().__init__(parent)

        self.person = person.copy(deep=True)
        self.curr_model = curr_model
        self.location_id = location_id
        self.all_partners = all_partners

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.apls_with_location: list[schemas.ActorPartnerLocationPref] = []
        self.dict_partner_id__apl: dict[UUID, schemas.ActorPartnerLocationPref] = {}
        self.dict_partner_id__slider: dict[UUID, SliderWithPressEvent] = {}
        self.dict_partner_id_score: dict[UUID, int] = {}

        self.layout = QVBoxLayout(self)
        self.layout_head = QHBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout_options = QGridLayout()
        self.layout.addLayout(self.layout_options)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_foot)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

        self.setup_data()
        self.setup_option_field()
        self.setup_values()
        self.connect_sliders_to_save()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def setup_data(self):
        self.apls_with_location = [apl for apl in self.curr_model.actor_partner_location_prefs_defaults
                                   if not apl.prep_delete and apl.location_of_work.id == self.location_id]
        self.dict_partner_id__apl = {apl.partner.id: apl for apl in self.apls_with_location}
        self.dict_partner_id_score: dict[UUID, int] = {apl.partner.id: apl.score for apl in self.apls_with_location}

    def setup_option_field(self):
        for row, partner in enumerate(self.all_partners):
            lb_partner = QLabel(f'{partner.f_name} {partner.l_name}:')
            lb_slider_val = QLabel('Error')
            slider_partner = SliderWithPressEvent(Qt.Orientation.Horizontal)
            slider_partner.setMinimum(0)
            slider_partner.setMaximum(4)
            slider_partner.setFixedWidth(200)
            slider_partner.setTickPosition(QSlider.TickPosition.TicksBelow)

            # slider_partner.valueChanged.connect(partial(self.save_pref_loc, partner))
            slider_partner.valueChanged.connect(partial(self.show_slider_text, lb_slider_val))

            self.layout_options.addWidget(lb_partner, row, 0)
            self.layout_options.addWidget(slider_partner, row, 1)
            self.layout_options.addWidget(lb_slider_val, row, 2)

            self.dict_partner_id__slider[partner.id] = slider_partner

    def connect_sliders_to_save(self):
        for partner_id, slider in self.dict_partner_id__slider.items():
            partner = db_services.Person.get(partner_id)
            slider.valueChanged.connect(partial(self.save_pref_loc, partner))

    def setup_values(self):
        for partner in self.all_partners:
            if partner.id in self.dict_partner_id_score:
                self.dict_partner_id__slider[partner.id].setValue(int(self.dict_partner_id_score[partner.id]*2))
            else:
                self.dict_partner_id__slider[partner.id].setValue(2)

    def show_slider_text(self, lb_loc_val: QLabel, val: int):
        lb_loc_val.setText(SliderValToText.get_text(val))

    def save_pref_loc(self, partner: schemas.Person, value: int):
        if partner.id in self.dict_partner_id__apl:
            apl = self.dict_partner_id__apl[partner.id]
            remove_command = factory_for_remove_prefs(self.curr_model, apl.id)
            self.controller.execute(remove_command)

        if value != 2:
            if partner.id in self.dict_partner_id__apl:
                new_apl = schemas.ActorPartnerLocationPrefCreate(**apl.dict())
                new_apl.score = value / 2
            else:
                location = db_services.LocationOfWork.get(self.location_id)
                new_apl = schemas.ActorPartnerLocationPrefCreate(
                    score=value/2, person=self.person, partner=partner, location_of_work=location)

            create_command = actor_partner_loc_pref_commands.Create(new_apl)
            self.controller.execute(create_command)

            created_apl = create_command.get_created_actor_partner_loc_pref()
            put_in_command = factory_for_put_in_prefs(self.curr_model, created_apl.id)
            self.controller.execute(put_in_command)

        self.curr_model = factory_for_reload_curr_model(self.curr_model)(self.curr_model.id)
        self.setup_data()


class DlgPartnerLocationPrefs(QDialog):
    """Hier werden die Mitarbeiter-Einrichtungs-Präferenzen festgelegt.
    Fall keine Präferenz einer besimmten Kombination vorhanden ist, wird sie als Präferenz mit Score=1 gewertet."""

    def __init__(self, parent, person: schemas.PersonShow, curr_model: schemas.ModelWithPartnerLocPrefs,
                 parent_model: schemas.ModelWithPartnerLocPrefs | None,
                 persons_at_date: list[schemas.Person], locations_at_date: list[schemas.LocationOfWork]):
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
        self.persons_at_date = persons_at_date
        self.locations_at_date = locations_at_date
        self.partners: list[schemas.Person] | None = None
        self.locations: list[schemas.LocationOfWork] | None = None

        self.dict_location_id__bt_slider_lb: dict[UUID, dict[Literal['button', 'slider', 'label'], QPushButton | SliderWithPressEvent | QLabel]] = {}
        self.dict_partner_id__bt_slider_lb:  dict[UUID, dict[Literal['button', 'slider', 'label'], QPushButton | SliderWithPressEvent | QLabel]] = {}

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.bt_reset = QPushButton('reset')
        self.configure_bt_reset()
        self.button_box.addButton(self.bt_reset, QDialogButtonBox.ButtonRole.ActionRole)
        self.layout_foot.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.setup_data()
        self.setup_option_field()
        self.setup_values()

    def accept(self) -> None:
        self.controller.execute(actor_partner_loc_pref_commands.DeleteUnused(self.person.id))
        super().accept()

    def reject(self) -> None:
        self.controller.undo_all()
        db_services.ActorPartnerLocationPref.delete_prep_deletes(self.person.id)
        super().reject()

    def reset_to_ones(self):
        apls = [apl for apl in self.curr_model.actor_partner_location_prefs_defaults if not apl.prep_delete]
        for apl in apls:
            remove_command = factory_for_remove_prefs(self.curr_model, apl.id)
            self.controller.execute(remove_command)

        self.reload_curr_model()
        self.setup_values()

    def reset_to_parent_values(self):
        for apl in [pref for pref in self.curr_model.actor_partner_location_prefs_defaults if not pref.prep_delete]:
            remove_command = factory_for_remove_prefs(self.curr_model, apl.id)
            self.controller.execute(remove_command)
        for apl in [pref for pref in self.parent_model.actor_partner_location_prefs_defaults if not pref.prep_delete]:
            put_in_command = factory_for_put_in_prefs(self.curr_model, apl.id)
            self.controller.execute(put_in_command)

        self.reload_curr_model()
        self.setup_values()

    def configure_bt_reset(self):
        if not self.parent_model:
            self.bt_reset.clicked.connect(self.reset_to_ones)
        else:
            menu = QMenu(self)
            menu.addAction(Action(self, None, 'alles auf Normal', 'Alle Werte auf "Normal" setzen.',
                                  self.reset_to_ones))
            menu.addAction(Action(self, None, 'Werte von übergeordnetem Modell',
                                  'Alle Werte werden vom übergeordnten Modell übernommen',
                                  self.reset_to_parent_values))
            self.bt_reset.setMenu(menu)

    def setup_data(self):
        self.partners = [p for p in self.persons_at_date if p.id != self.person.id]
        self.locations = self.locations_at_date

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

            slider_location = SliderWithPressEvent(Qt.Orientation.Horizontal, self)
            slider_location.setMinimum(0)
            slider_location.setMaximum(4)
            slider_location.setFixedWidth(200)
            slider_location.setTickPosition(QSlider.TickPosition.TicksBelow)

            slider_location.sliderReleased.connect(partial(self.save_pref_loc, loc, slider_location.value()))
            # slider_location.valueChanged.connect(partial(self.show_slider_text, lb_loc_val))
            self.layout_options_locs.addWidget(slider_location, row, 2)

            self.dict_location_id__bt_slider_lb[loc.id] = {}
            self.dict_location_id__bt_slider_lb[loc.id]['button'] = bt_partners
            self.dict_location_id__bt_slider_lb[loc.id]['slider'] = slider_location
            self.dict_location_id__bt_slider_lb[loc.id]['label'] = lb_loc_val

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

            slider_partner.sliderReleased.connect(partial(self.save_pref_partner, partner, slider_partner.value()))
            slider_partner.valueChanged.connect(partial(self.show_slider_text, lb_partner_val))
            self.layout_options_partners.addWidget(slider_partner, row, 2)

            self.dict_partner_id__bt_slider_lb[partner.id] = {}
            self.dict_partner_id__bt_slider_lb[partner.id]['button'] = bt_locations
            self.dict_partner_id__bt_slider_lb[partner.id]['slider'] = slider_partner
            self.dict_partner_id__bt_slider_lb[partner.id]['label'] = lb_partner_val

    def setup_values_locations(self):
        """Regler und Buttons bekommen die korrekten Einstellungen."""

        for loc in self.locations:
            partner_vals_of_locations = [apl.score for apl in self.curr_model.actor_partner_location_prefs_defaults
                                         if not apl.prep_delete and apl.location_of_work.id == loc.id]
            partner_vals_of_locations += [1 for _ in range(len(self.partners) - len(partner_vals_of_locations))]

            if len(set(partner_vals_of_locations)) == 1:
                self.set_bt__style_txt(self.dict_location_id__bt_slider_lb[loc.id]['button'], 'all', 'locs')
            elif len(set(partner_vals_of_locations)) > 1:
                self.set_bt__style_txt(self.dict_location_id__bt_slider_lb[loc.id]['button'], 'some', 'locs')
            else:
                raise Exception('Keine Werte in partner_vals_of_locations!')

            slider_value = max([int(2 * v) for v in partner_vals_of_locations])
            self.show_slider_text(self.dict_location_id__bt_slider_lb[loc.id]['label'], slider_value)
            self.dict_location_id__bt_slider_lb[loc.id]['slider'].setValue(slider_value)

    def setup_values_parters(self):
        """Regler und Buttons bekommen die korrekten Einstellungen."""

        for partner in self.partners:
            location_vals_of_partner = [apl.score for apl in self.curr_model.actor_partner_location_prefs_defaults
                                        if not apl.prep_delete and apl.partner.id == partner.id]
            location_vals_of_partner += [1 for _ in range(len(self.locations) - len(location_vals_of_partner))]

            if len(set(location_vals_of_partner)) == 1:
                self.set_bt__style_txt(self.dict_partner_id__bt_slider_lb[partner.id]['button'], 'all', 'partners')
            elif len(set(location_vals_of_partner)) > 1:
                self.set_bt__style_txt(self.dict_partner_id__bt_slider_lb[partner.id]['button'], 'some', 'partners')
            else:
                raise Exception('Keine Werte in location_vals_of_partner!')

            slider_value = max([int(2 * v) for v in location_vals_of_partner])
            self.show_slider_text(self.dict_partner_id__bt_slider_lb[partner.id]['label'], slider_value)
            self.dict_partner_id__bt_slider_lb[partner.id]['slider'].setValue(slider_value)

    def setup_values(self):
        """Regler und Buttons bekommen die korrekten Einstellungen."""

        self.setup_values_locations()
        self.setup_values_parters()

    def reload_curr_model(self):
        self.curr_model = factory_for_reload_curr_model(self.curr_model)(self.curr_model.id)

    def set_bt__style_txt(self, button: QPushButton, style: Literal['all', 'some'], group: Literal['locs', 'partners']):
        text, bg_color = ButtonStyles.get_bg_color_text(style, group)
        button.setText(text)
        button.setStyleSheet(f'background-color: {bg_color}')

    def show_slider_text(self, label: QLabel, value: int):
        label.setText(SliderValToText.get_text(value))

    def save_pref_loc(self, location: schemas.LocationOfWork, value: int):
        value = self.dict_location_id__bt_slider_lb[location.id]['slider'].value()
        time.sleep(1)
        score = value / 2
        apls_with_loc: dict[UUID, schemas.ActorPartnerLocationPref] = {
            apl.partner.id: apl for apl in self.curr_model.actor_partner_location_prefs_defaults
            if not apl.prep_delete and apl.location_of_work.id == location.id}

        for partner in self.partners:
            if partner.id in apls_with_loc:
                apl = db_services.ActorPartnerLocationPref.get(apls_with_loc[partner.id].id)
                remove_command = factory_for_remove_prefs(self.curr_model, apl.id)
                self.controller.execute(remove_command)

            if score != 1:
                if partner.id in apls_with_loc:
                    new_apl_pref = schemas.ActorPartnerLocationPrefCreate(**apl.dict())
                    new_apl_pref.score = score
                else:
                    new_apl_pref = schemas.ActorPartnerLocationPrefCreate(score=score, person=self.person,
                                                                          partner=partner,
                                                                          location_of_work=location)

                create_command = actor_partner_loc_pref_commands.Create(new_apl_pref)
                self.controller.execute(create_command)
                created_apl = create_command.get_created_actor_partner_loc_pref()
                put_in_command = factory_for_put_in_prefs(self.curr_model, created_apl.id)
                self.controller.execute(put_in_command)

        self.reload_curr_model()
        self.setup_values()

    def save_pref_partner(self, partner: schemas.Person, value: int):
        value = self.dict_partner_id__bt_slider_lb[partner.id]['slider'].value()
        time.sleep(1)
        score = value / 2
        apls_with_partner: dict[UUID, schemas.ActorPartnerLocationPref] = {
            apl.location_of_work.id: apl for apl in self.curr_model.actor_partner_location_prefs_defaults
            if not apl.prep_delete and apl.partner.id == partner.id}

        for location in self.locations:
            if location.id in apls_with_partner:
                apl = db_services.ActorPartnerLocationPref.get(apls_with_partner[location.id].id)
                remove_command = factory_for_remove_prefs(self.curr_model, apl.id)
                self.controller.execute(remove_command)

            if score != 1:
                if location.id in apls_with_partner:
                    new_apl_pref = schemas.ActorPartnerLocationPrefCreate(**apl.dict())
                    new_apl_pref.score = score
                else:
                    new_apl_pref = schemas.ActorPartnerLocationPrefCreate(score=score, person=self.person,
                                                                          partner=partner,
                                                                          location_of_work=location)

                create_command = actor_partner_loc_pref_commands.Create(new_apl_pref)
                self.controller.execute(create_command)
                created_apl = create_command.get_created_actor_partner_loc_pref()
                put_in_command = factory_for_put_in_prefs(self.curr_model, created_apl.id)
                self.controller.execute(put_in_command)

        self.reload_curr_model()
        self.setup_values()

    def choice_partners(self, location_id: UUID):
        dlg = DlgPartnerLocationPrefsPartner(self, self.person, self.curr_model, location_id, self.partners)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.reload_curr_model()
            self.setup_values()

    def choice_locations(self, partner_id: UUID):
        dlg = DlgPartnerLocationPrefsLocs(self, self.person, self.curr_model, partner_id, self.locations)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.reload_curr_model()
            self.setup_values()
