import datetime
from functools import partial
from typing import Literal, Callable
from uuid import UUID

from PySide6.QtCore import QTimer, QCoreApplication
from PySide6.QtGui import Qt, QResizeEvent
from PySide6.QtWidgets import QDialog, QVBoxLayout, QSlider, QGridLayout, QLabel, \
    QDialogButtonBox, QPushButton, QHBoxLayout, QGroupBox, QMenu, QDateEdit, \
    QApplication, QScrollArea, QWidget, QAbstractScrollArea

from database import schemas, db_services
from database.special_schema_requests import (get_locations_of_team_at_date, get_curr_assignment_of_person)
from database.db_services.person import get_persons_of_team_at_date
from tools.actions import MenuToolbarAction
from commands import command_base_classes
from commands.database_commands import actor_plan_period_commands, actor_partner_loc_pref_commands, person_commands, \
    avail_day_commands
from gui.custom_widgets.slider_with_press_event import SliderWithPressEvent
from gui.custom_widgets.team_selector import TeamSelectorWidget
from gui.widget_styles.buttons import PartnerLocPrefs


def factory_for_put_in_prefs(curr_model: schemas.ModelWithPartnerLocPrefs,
                             pref_to_put_i_id: UUID) -> command_base_classes.Command:
    curr_model_name = curr_model.__class__.__name__
    curr_model_name__put_in_command = {
        'PersonShow': person_commands.PutInActorPartnerLocationPref,
        'ActorPlanPeriodForMask': actor_plan_period_commands.PutInActorPartnerLocationPref,
        'AvailDay': avail_day_commands.PutInActorPartnerLocationPref,
        'AvailDayShow': avail_day_commands.PutInActorPartnerLocationPref}

    try:
        return curr_model_name__put_in_command[curr_model_name](curr_model.id, pref_to_put_i_id)
    except KeyError as e:
        raise KeyError(
            f'Für die Klasse {curr_model_name} ist noch kein Put-In-Command definiert.'
        ) from e


def factory_for_remove_prefs(curr_model: schemas.ModelWithPartnerLocPrefs,
                             pref_to_remove_id: UUID) -> command_base_classes.Command:
    curr_model_name = curr_model.__class__.__name__
    curr_model_name__remove_command = {
        'PersonShow': person_commands.RemoveActorPartnerLocationPref,
        'ActorPlanPeriodForMask': actor_plan_period_commands.RemoveActorPartnerLocationPref,
        'AvailDay': avail_day_commands.RemoveActorPartnerLocationPref,
        'AvailDayShow': avail_day_commands.RemoveActorPartnerLocationPref}
    try:
        command_to_remove = curr_model_name__remove_command[curr_model_name]
        return command_to_remove(curr_model.id, pref_to_remove_id)
    except KeyError as e:
        raise KeyError(
            f'Für die Klasse {curr_model_name} ist noch kein Remove-Command definiert.'
        ) from e


def factory_for_reload_curr_model(curr_model: schemas.ModelWithPartnerLocPrefs) -> Callable:
    curr_model_name = curr_model.__class__.__name__
    curr_model_get = {'PersonShow': db_services.Person.get,
                      'ActorPlanPeriodForMask': db_services.ActorPlanPeriod.get_for_mask,
                      'AvailDay': db_services.AvailDay.get,
                      'AvailDayShow': db_services.AvailDay.get}
    return curr_model_get[curr_model_name]


class SliderValToText:
    val_to_text = {
        0: QCoreApplication.translate('SliderValToText', 'do not assign'),
        1: QCoreApplication.translate('SliderValToText', 'assign if necessary'),
        2: QCoreApplication.translate('SliderValToText', 'assign gladly'),
        3: QCoreApplication.translate('SliderValToText', 'assign preferably'),
        4: QCoreApplication.translate('SliderValToText', 'assign mandatory')
    }

    @classmethod
    def get_text(cls, val: int) -> str:
        if not (0 <= val <= 4):
            raise ValueError(
                QCoreApplication.translate(
                    'SliderValToText', 'Value must be between 0-4 inclusive. Current: {val}').format(val=val)
            )


        return cls.val_to_text[val]


class DlgPartnerLocationPrefsLocs(QDialog):
    def __init__(self, parent, person: schemas.PersonShow, curr_model: schemas.ModelWithPartnerLocPrefs,
                 partner_id: UUID, all_locations: list[schemas.LocationOfWork]):
        super().__init__(parent)

        self.person = person.model_copy(deep=True)
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
        
        # Help-Integration
        from tools.helper_functions import setup_form_help
        setup_form_help(self, "partner_location_prefs_locs", add_help_button=True)

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def setup_data(self):
        self.apls_with_partner = [apl for apl in self.curr_model.actor_partner_location_prefs_defaults
                                  if not apl.prep_delete and apl.partner.id == self.partner_id]
        self.dict_location_id__apl = {apl.location_of_work.id: apl for apl in self.apls_with_partner}
        self.dict_location_id_score: dict[UUID, float] = {apl.location_of_work.id: apl.score
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

            self.show_slider_text(lb_slider_val, 0)  # für die Initialisierung der 0-Values notwendig
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
                new_apl = schemas.ActorPartnerLocationPrefCreate(**apl.model_dump())
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
                 location_id: UUID, all_partners: list[schemas.PersonForFixedCastCombo]):
        super().__init__(parent)

        self.person = person.model_copy(deep=True)
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
        
        # Help-Integration
        from tools.helper_functions import setup_form_help
        setup_form_help(self, "partner_location_prefs_partner", add_help_button=True)

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def setup_data(self):
        self.apls_with_location = [apl for apl in self.curr_model.actor_partner_location_prefs_defaults
                                   if not apl.prep_delete and apl.location_of_work.id == self.location_id]
        self.dict_partner_id__apl = {apl.partner.id: apl for apl in self.apls_with_location}
        self.dict_partner_id_score: dict[UUID, float] = {apl.partner.id: apl.score for apl in self.apls_with_location}

    def setup_option_field(self):
        for row, partner in enumerate(self.all_partners):
            lb_partner = QLabel(f'{partner.f_name} {partner.l_name}:')
            lb_slider_val = QLabel('Error')
            slider_partner = SliderWithPressEvent(Qt.Orientation.Horizontal)
            slider_partner.setMinimum(0)
            slider_partner.setMaximum(4)
            slider_partner.setFixedWidth(200)
            slider_partner.setTickPosition(QSlider.TickPosition.TicksBelow)

            self.show_slider_text(lb_slider_val, 0)  # für die Initialisierung der 0-Values notwendig
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
                new_apl = schemas.ActorPartnerLocationPrefCreate(**apl.model_dump())
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
    """Dialog for setting employee-facility preferences.
    If no preference exists for a specific combination, it is treated as a preference with score=1."""

    def __init__(self, parent, person: schemas.PersonShow, curr_model: schemas.ModelWithPartnerLocPrefs,
                 parent_model: schemas.ModelWithPartnerLocPrefs | None,
                 team_at_date_factory: Callable[[datetime.date], schemas.Team]):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Partner Preferences'))

        self.screen_geometry = QApplication.primaryScreen().geometry()

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.person = person
        self.curr_model: schemas.ModelWithPartnerLocPrefs = curr_model.model_copy(deep=True)
        self.parent_model = parent_model
        self.team_at_date_factory = team_at_date_factory
        self.curr_team: schemas.Team | None = None
        self.persons_at_date: list[schemas.PersonShow] = []
        self.locations_at_date: list[schemas.LocationOfWorkShow] = []
        self.partners: list[schemas.PersonForFixedCastCombo] | None = None
        self.locations: list[schemas.LocationOfWork] | None = None

        self.updating_sliders = False

        self.dict_location_id__bt_slider_lb: dict[UUID, dict[Literal['button', 'slider', 'label_location', 'label_val'],
                                                  QPushButton | SliderWithPressEvent | QLabel]] = {}
        self.dict_partner_id__bt_slider_lb:  dict[UUID, dict[Literal['button', 'slider', 'label_partner', 'label_val'],
                                                  QPushButton | SliderWithPressEvent | QLabel]] = {}

        # QTimer wird verwendet, damit bei schnellem Datumsdurchlauf nicht für jeden Tag das Layout neu aufgebaut wird.
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.date_changed)

        self._setup_ui()
        
        # Help-Integration
        from tools.helper_functions import setup_form_help
        setup_form_help(self, "partner_location_prefs", add_help_button=True)

        self.de_date.setMinimumDate(
            self.curr_model.date if isinstance(self.curr_model, schemas.AvailDay)
            else self.curr_model.plan_period.start if isinstance(self.curr_model, schemas.ActorPlanPeriod)
            else datetime.date.today()
        )  # Löst in einer Kaskade die Einrichtung der Slider aus.

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QHBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout_body = QHBoxLayout()
        self.layout.addLayout(self.layout_body)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_foot)

        self.group_date = QGroupBox(self.tr('Date'))
        self.layout_head.addWidget(self.group_date)
        self.layout_date = QHBoxLayout(self.group_date)

        # Layout für die Mitarbeiter-Gruppe
        self.group_partners = QGroupBox(self.tr('Employees'))
        self.layout_body.addWidget(self.group_partners)
        # Erstelle zunächst einen QScrollArea und mach ihn anpassbar
        self.scroll_area_partners = QScrollArea(self.group_partners)
        self.scroll_area_partners.setWidgetResizable(True)
        # Setze die horizontale Scrollbar-Policy auf "immer aus" und die vertikale auf "bei Bedarf"
        self.scroll_area_partners.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area_partners.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Erstelle ein Container-Widget, das in der Scroll-Area angezeigt wird
        self.scroll_widget_partners = QWidget()
        self.scroll_area_partners.setWidget(self.scroll_widget_partners)
        self.layout_options_partners = QGridLayout(self.scroll_widget_partners)
        self.layout_options_partners.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Hier erstellen wir ein neues Layout für self.group_partners und fügen die Scroll-Area hinzu:
        self.group_partners_layout = QVBoxLayout(self.group_partners)
        self.group_partners_layout.addWidget(self.scroll_area_partners)

        # Layout für die Einrichtungs-Gruppe
        self.group_locations = QGroupBox(self.tr('Facilities'))
        self.layout_body.addWidget(self.group_locations)
        # Erstelle zunächst einen QScrollArea und mach ihn anpassbar
        self.scroll_area_locations = QScrollArea(self.group_locations)
        self.scroll_area_locations.setWidgetResizable(True)
        # Setze die horizontale Scrollbar-Policy auf "immer aus" und die vertikale auf "bei Bedarf"
        self.scroll_area_locations.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area_locations.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Erstelle ein Container-Widget, das in der Scroll-Area angezeigt wird
        self.scroll_widget_locations = QWidget()
        self.scroll_area_locations.setWidget(self.scroll_widget_locations)
        self.layout_options_locations = QGridLayout(self.scroll_widget_locations)
        self.layout_options_locations.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Hier erstellen wir ein neues Layout für self.group_locations und fügen die Scroll-Area hinzu:
        self.group_locations_layout = QVBoxLayout(self.group_locations)
        self.group_locations_layout.addWidget(self.scroll_area_locations)

        self.lb_info = QLabel()
        self.layout_head.addWidget(self.lb_info)

        self.lb_date = QLabel(self.tr('The selection of employees and facilities may change at a later date.'))
        self.de_date = QDateEdit()
        self.de_date.dateChanged.connect(self.on_date_change)
        self.layout_date.addWidget(self.de_date)
        self.de_date.setFixedWidth(100)

        # Team-Selektor für Multi-Team-Personen (nur bei PersonShow)
        self.team_selector: TeamSelectorWidget | None = None
        if isinstance(self.curr_model, schemas.PersonShow):
            self.team_selector = TeamSelectorWidget(self)
            self.team_selector.teamChanged.connect(self._on_team_changed)
            self.layout_date.addWidget(self.team_selector)

        self.layout_date.addWidget(self.lb_date)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                           QDialogButtonBox.StandardButton.Cancel)
        self.bt_reset = QPushButton(self.tr('Reset'))
        self.reset_menu: QMenu | None = None
        self.configure_bt_reset()
        self.button_box.addButton(self.bt_reset, QDialogButtonBox.ButtonRole.ActionRole)
        self.layout_foot.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def resizeEvent(self, event: QResizeEvent) -> None:
        point_bottom_right = self.mapToGlobal(self.rect().bottomRight())
        if ((point_bottom_right.x() > self.screen_geometry.right())
                or (point_bottom_right.y() > self.screen_geometry.bottom())):
            self.move(self.screen_geometry.center() - self.rect().center())
        super().resizeEvent(event)

    def accept(self) -> None:
        self.controller.execute(actor_partner_loc_pref_commands.DeleteUnused(self.person.id))
        super().accept()

    def reject(self) -> None:
        self.controller.undo_all()
        db_services.ActorPartnerLocationPref.delete_prep_deletes(self.person.id)
        super().reject()

    def on_date_change(self):
        self.timer.start()

    def date_changed(self):
        self.updating_sliders = True

        # Bei Multi-Team: Team-Selektor aktualisieren
        if self.team_selector:
            self.team_selector.update_teams(self.curr_model.id, self.de_date.date().toPython())

        self.set_curr_team()
        self.lb_info.clear()
        self.set_new_locations()
        self.set_new_partners()
        self.clear_option_field()
        self.setup_option_field()
        self.setup_values()

        self.updating_sliders = False

    def _on_team_changed(self, team: schemas.TeamShow | None):
        """Wird aufgerufen wenn der Benutzer ein anderes Team auswählt."""
        self.updating_sliders = True

        self.set_curr_team()
        self.lb_info.clear()
        self.set_new_locations()
        self.set_new_partners()
        self.clear_option_field()
        self.setup_option_field()
        self.setup_values()

        self.updating_sliders = False

    def reset_to_ones(self):
        self.updating_sliders = True
        apls = [apl for apl in self.curr_model.actor_partner_location_prefs_defaults if not apl.prep_delete]
        for apl in apls:
            remove_command = factory_for_remove_prefs(self.curr_model, apl.id)
            self.controller.execute(remove_command)

        self.reload_curr_model()
        self.setup_values()
        self.updating_sliders = False

    def reset_to_parent_values(self):
        self.updating_sliders = True
        for apl in [pref for pref in self.curr_model.actor_partner_location_prefs_defaults if not pref.prep_delete]:
            remove_command = factory_for_remove_prefs(self.curr_model, apl.id)
            self.controller.execute(remove_command)
        for apl in [pref for pref in self.parent_model.actor_partner_location_prefs_defaults if not pref.prep_delete]:
            put_in_command = factory_for_put_in_prefs(self.curr_model, apl.id)
            self.controller.execute(put_in_command)

        self.reload_curr_model()
        self.setup_values()
        self.updating_sliders = False

    def configure_bt_reset(self):
        if not self.parent_model:
            self.bt_reset.clicked.connect(self.reset_to_ones)
        else:
            self.reset_menu = QMenu(self)
            self.reset_menu.addAction(
                MenuToolbarAction(self, None, self.tr('Reset to Normal'),
                                self.tr('Set all values to "Normal".'),
                                self.reset_to_ones))
            self.reset_menu.addAction(
                MenuToolbarAction(self, None, self.tr('Values from parent model'),
                                self.tr('All values will be taken from the parent model'),
                                self.reset_to_parent_values))
            self.bt_reset.setMenu(self.reset_menu)

    def set_curr_team(self):
        # Team vom Selektor oder von der Factory holen
        if self.team_selector and self.team_selector.get_current_team():
            self.curr_team = self.team_selector.get_current_team()
        else:
            self.curr_team = self.team_at_date_factory(self.de_date.date().toPython())

    def set_new_partners(self):
        if isinstance(self.curr_model, schemas.ActorPlanPeriod):  # wenn curr_model == ActorPlanPeriod, ist curr_team vorhanden
            self.partners = self.union_partners()
        elif not self.curr_team:
            self.partners = []
        else:  # betrifft Person und AvailDay
            self.partners = sorted(
                (p for p in get_persons_of_team_at_date(self.curr_team.id, self.de_date.date().toPython())
                 if p.id != self.person.id), key=lambda x: x.f_name+x.l_name)

    def set_new_locations(self):
        if isinstance(self.curr_model, schemas.ActorPlanPeriod):  # wenn curr_model == ActorPlanPeriod, ist curr_team vorhanden
            self.locations = self.union_locations_of_work()
        elif not self.curr_team:
            self.locations = []
        else:  # betrifft Person und AvailDay
            self.locations = sorted(get_locations_of_team_at_date(self.curr_team.id, self.de_date.date().toPython()),
                                    key=lambda x: x.name+x.address.city)

    def union_partners(self) -> list[schemas.PersonForFixedCastCombo]:
        """Vereinigung aus allen möglichen Partner an den Tagen der Planungsperiode werden gebildet"""
        #  todo: days_of_plan_period u. valid_days_of_actor können an Funktion ausgelagert werden
        days_of_plan_period = [self.curr_model.plan_period.start + datetime.timedelta(delta) for delta in
                               range((self.curr_model.plan_period.end - self.curr_model.plan_period.start).days + 1)]
        valid_days_of_actor = [date for date in days_of_plan_period
                               if (curr_team_assignment := get_curr_assignment_of_person(self.person, date))
                               and curr_team_assignment.team.id == self.curr_team.id]
        persons_by_id: dict = {}
        first_day_ids: set = set()
        info_text = self.tr('The same partners belong to the team on all days of the period.')
        for i, date in enumerate(valid_days_of_actor):
            persons_today = [p for p in get_persons_of_team_at_date(self.curr_team.id, date)
                             if p.id != self.person.id]
            ids_today = {p.id for p in persons_today}
            if i == 0:
                first_day_ids = ids_today
            elif ids_today != first_day_ids:
                info_text = self.tr('Not all days of the period have the same partners in the team.')
            for p in persons_today:
                persons_by_id[p.id] = p

        self.lb_info.setText(self.lb_info.text() + info_text)

        return sorted(persons_by_id.values(), key=lambda x: x.f_name+x.l_name)

    def union_locations_of_work(self) -> list[schemas.LocationOfWork]:
        """Vereinigung aus allen möglichen Locations an den Tagen der Planungsperiode werden gebildet"""
        #  todo: days_of_plan_period u. valid_days_of_actor können an Funktion ausgelagert werden
        days_of_plan_period = [self.curr_model.plan_period.start + datetime.timedelta(delta) for delta in
                               range((self.curr_model.plan_period.end - self.curr_model.plan_period.start).days + 1)]
        valid_days_of_actor = [date for date in days_of_plan_period
                               if (curr_team_assignment := get_curr_assignment_of_person(self.person, date))
                               and curr_team_assignment.team.id == self.curr_team.id]
        curr_loc_of_work_ids = {loc.id for loc in
                                get_locations_of_team_at_date(self.curr_team.id, valid_days_of_actor[0])}
        info_text = self.tr('The same facilities belong to the team on all days of the period.\n')
        for date in valid_days_of_actor[1:]:
            location_ids_at_date = {loc.id for loc in get_locations_of_team_at_date(self.curr_team.id, date)}
            if location_ids_at_date != curr_loc_of_work_ids:
                info_text = self.tr('Not all days of the period have the same facilities in the team.\n')
            curr_loc_of_work_ids |= location_ids_at_date

        self.lb_info.setText(self.lb_info.text() + info_text)

        return sorted((db_services.LocationOfWork.get(loc_id) for loc_id in curr_loc_of_work_ids),
                      key=lambda x: x.name+x.address.city)

    def clear_option_field(self):
        for widgets in self.dict_location_id__bt_slider_lb.values():
            for widget in widgets.values():
                widget.setParent(None)
                widget.deleteLater()

        self.dict_location_id__bt_slider_lb = {}
        for widgets in self.dict_partner_id__bt_slider_lb.values():
            for widget in widgets.values():
                widget.setParent(None)
                widget.deleteLater()
        self.dict_partner_id__bt_slider_lb = {}

    def setup_option_field(self):
        """Setup sliders and buttons for locations and partners"""

        '''setup locations group:'''
        for row, loc in enumerate(self.locations):
            lb_location = QLabel(self.tr('In {name} ({city}):').format(
                name=loc.name, city=loc.address.city))
            self.layout_options_locations.addWidget(lb_location, row, 0)
            bt_partners = QPushButton(self.tr('Employees'), clicked=partial(self.choice_partners, loc.id))
            self.layout_options_locations.addWidget(bt_partners, row, 1)

            lb_loc_val = QLabel('Error')
            self.layout_options_locations.addWidget(lb_loc_val, row, 3)

            slider_location = SliderWithPressEvent(Qt.Orientation.Horizontal, self)
            slider_location.setMinimum(0)
            slider_location.setMaximum(4)
            slider_location.setFixedWidth(200)
            slider_location.setTickPosition(QSlider.TickPosition.TicksBelow)

            slider_location.valueChanged.connect(partial(self.save_pref_loc, loc))
            self.layout_options_locations.addWidget(slider_location, row, 2)

            self.dict_location_id__bt_slider_lb[loc.id] = {
                'button': bt_partners,
                'slider': slider_location,
                'label_location': lb_location,
                'label_val': lb_loc_val,
            }
        '''setup partners group:'''
        for row, partner in enumerate(self.partners):
            lb_partner = QLabel(self.tr('With {first_name} {last_name}:').format(
                first_name=partner.f_name, last_name=partner.l_name))
            self.layout_options_partners.addWidget(lb_partner, row, 0)
            bt_locations = QPushButton(self.tr('Facilities'), clicked=partial(self.choice_locations, partner.id))
            self.layout_options_partners.addWidget(bt_locations, row, 1)

            lb_partner_val = QLabel('Error')
            self.layout_options_partners.addWidget(lb_partner_val, row, 3)

            slider_partner = SliderWithPressEvent(Qt.Orientation.Horizontal)
            slider_partner.setMinimum(0)
            slider_partner.setMaximum(4)
            slider_partner.setFixedWidth(200)
            slider_partner.setTickPosition(QSlider.TickPosition.TicksBelow)

            slider_partner.valueChanged.connect(partial(self.save_pref_partner, partner))
            self.layout_options_partners.addWidget(slider_partner, row, 2)

            self.dict_partner_id__bt_slider_lb[partner.id] = {
                'button': bt_locations,
                'slider': slider_partner,
                'label_partner': lb_partner,
                'label_val': lb_partner_val,
            }

    def setup_values_locations(self):
        """Regler und Buttons bekommen die korrekten Einstellungen."""

        for loc in self.locations:
            partner_vals_of_locations = [
                apl.score for apl in self.curr_model.actor_partner_location_prefs_defaults
                if not apl.prep_delete and apl.location_of_work.id == loc.id and
                   apl.partner.id in {p.id for p in self.partners}
            ]
            partner_vals_of_locations += [1 for _ in range(len(self.partners) - len(partner_vals_of_locations))]

            if len(set(partner_vals_of_locations)) == 1:
                self.set_bt__style_txt(self.dict_location_id__bt_slider_lb[loc.id]['button'], 'all', 'locs')
            elif len(set(partner_vals_of_locations)) > 1:
                self.set_bt__style_txt(self.dict_location_id__bt_slider_lb[loc.id]['button'], 'some', 'locs')
            else:
                raise Exception('Keine Werte in partner_vals_of_locations!')

            slider_value = max(int(2 * v) for v in partner_vals_of_locations)
            self.show_slider_text(self.dict_location_id__bt_slider_lb[loc.id]['label_val'], slider_value)
            self.dict_location_id__bt_slider_lb[loc.id]['slider'].setValue(slider_value)

    def setup_values_partners(self):
        """Regler und Buttons bekommen die korrekten Einstellungen."""

        for partner in self.partners:
            location_vals_of_partner = [
                apl.score for apl in self.curr_model.actor_partner_location_prefs_defaults
                if not apl.prep_delete and apl.partner.id == partner.id
                   and apl.location_of_work.id in {loc.id for loc in self.locations}
            ]
            location_vals_of_partner += [1 for _ in range(len(self.locations) - len(location_vals_of_partner))]

            if len(set(location_vals_of_partner)) == 1:
                self.set_bt__style_txt(self.dict_partner_id__bt_slider_lb[partner.id]['button'], 'all', 'partners')
            elif len(set(location_vals_of_partner)) > 1:
                self.set_bt__style_txt(self.dict_partner_id__bt_slider_lb[partner.id]['button'], 'some', 'partners')
            else:
                raise Exception('Keine Werte in location_vals_of_partner!')

            slider_value = max(int(2 * v) for v in location_vals_of_partner)
            self.show_slider_text(self.dict_partner_id__bt_slider_lb[partner.id]['label_val'], slider_value)
            self.dict_partner_id__bt_slider_lb[partner.id]['slider'].setValue(slider_value)

    def update_scroll_areas_geometry(self):
        # Nachdem alle Elemente zum Layout hinzugefügt wurden:
        QApplication.processEvents()
        min_width_partners = self.scroll_widget_partners.sizeHint().width()
        self.scroll_area_partners.setMinimumWidth(min_width_partners + 10)
        min_height_partners = self.scroll_widget_partners.sizeHint().height()
        self.scroll_area_partners.setMinimumHeight(min(self.screen_geometry.height() - 250, min_height_partners + 10))

        min_width_locations = self.scroll_widget_locations.sizeHint().width()
        self.scroll_area_locations.setMinimumWidth(min_width_locations + 10)
        min_height_locations = self.scroll_widget_locations.sizeHint().height()
        self.scroll_area_locations.setMinimumHeight(min(self.screen_geometry.height() - 200, min_height_locations + 10))

    def setup_values(self):
        """Regler und Buttons bekommen die korrekten Einstellungen."""

        try:
            self.setup_values_locations()
        except Exception:
            self.clear_option_field()
            return
        try:
            self.setup_values_partners()
        except Exception:
            self.clear_option_field()

        self.update_scroll_areas_geometry()

    def reload_curr_model(self):
        self.curr_model = factory_for_reload_curr_model(self.curr_model)(self.curr_model.id)

    def set_bt__style_txt(self, button: QPushButton, style: Literal['all', 'some'], group: Literal['locs', 'partners']):
        text, bg_color = PartnerLocPrefs.get_bg_color_text(style, group)
        button.setText(text)
        button.setStyleSheet(f'background-color: {bg_color}; color: black;')

    def show_slider_text(self, label: QLabel, value: int):
        label.setText(SliderValToText.get_text(value))

    def save_pref_loc(self, location: schemas.LocationOfWork, value: int):
        if self.updating_sliders:
            return
        self.updating_sliders = True
        score = value / 2
        apls_with_loc: dict[UUID, schemas.ActorPartnerLocationPref] = {
            apl.partner.id: apl for apl in self.curr_model.actor_partner_location_prefs_defaults
            if not apl.prep_delete and apl.location_of_work.id == location.id
               and apl.partner.id in {p.id for p in self.partners}
        }

        for partner in self.partners:
            if partner.id in apls_with_loc:
                apl = db_services.ActorPartnerLocationPref.get(apls_with_loc[partner.id].id)
                remove_command = factory_for_remove_prefs(self.curr_model, apl.id)
                self.controller.execute(remove_command)

            if score != 1:
                if partner.id in apls_with_loc:
                    new_apl_pref = schemas.ActorPartnerLocationPrefCreate(**apl.model_dump())
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
        self.updating_sliders = False

    def save_pref_partner(self, partner: schemas.Person, value: int):
        if self.updating_sliders:
            return
        self.updating_sliders = True
        score = value / 2
        apls_with_partner: dict[UUID, schemas.ActorPartnerLocationPref] = {
            apl.location_of_work.id: apl for apl in self.curr_model.actor_partner_location_prefs_defaults
            if not apl.prep_delete and apl.partner.id == partner.id
               and apl.location_of_work.id in {loc.id for loc in self.locations}
        }

        for location in self.locations:
            if location.id in apls_with_partner:
                apl = db_services.ActorPartnerLocationPref.get(apls_with_partner[location.id].id)
                remove_command = factory_for_remove_prefs(self.curr_model, apl.id)
                self.controller.execute(remove_command)

            if score != 1:
                if location.id in apls_with_partner:
                    new_apl_pref = schemas.ActorPartnerLocationPrefCreate(**apl.model_dump())
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
        self.updating_sliders = False

    def choice_partners(self, location_id: UUID, e):
        dlg = DlgPartnerLocationPrefsPartner(self, self.person, self.curr_model, location_id, self.partners)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.updating_sliders = True
            self.reload_curr_model()
            self.setup_values()
            self.updating_sliders = False

    def choice_locations(self, partner_id: UUID, e):
        dlg = DlgPartnerLocationPrefsLocs(self, self.person, self.curr_model, partner_id, self.locations)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.updating_sliders = True
            self.reload_curr_model()
            self.setup_values()
            self.updating_sliders = False
