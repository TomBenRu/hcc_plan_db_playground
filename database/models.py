from datetime import date
from datetime import datetime
from datetime import timedelta
from uuid import UUID
from pony.orm import Database, PrimaryKey, Required, Optional, Set, Json, composite_key

db = Database()


class Person(db.Entity):
    """Um die Konsistenz zurückliegender Pläne zu erhalten, sollten Instanzen von Personen nicht aus der Datenbank
    gelöscht werden, sondern nur der Wert prep_delete gesetzt werden."""
    id = PrimaryKey(UUID, auto=True)
    f_name = Required(str, 50)
    l_name = Required(str, 50)
    email = Required(str, 50)
    phone_nr = Optional(str, 50)
    username = Required(str, 50, unique=True)
    passwort = Required(str)
    requested_assignments = Optional(int, size=16, unsigned=True, default=8)
    created_at = Optional(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    project = Required('Project', reverse='persons')
    team_of_actor = Optional('Team', reverse='persons')
    project_of_admin = Optional('Project', reverse='admin')
    teams_of_dispatcher = Set('Team', reverse='dispatcher', cascade_delete=False)
    actor_plan_periods = Set('ActorPlanPeriod')
    address = Optional('Address')
    time_of_days = Set('TimeOfDay')
    actor_partner_location_prefs = Set('ActorPartnerLocationPref', reverse='person')  # Es müssen nicht zu allen Kombinationen von Actor u. Location Präferenzen vorhanden sein. Fehlende Präferenzen bedeuten das gleiche, wie: score = 1
    actor_partner_location_prefs__as_partner = Set('ActorPartnerLocationPref', reverse='partner')
    flags = Set('Flag')
    combination_locations_possibles = Set('CombinationLocationsPossible')

    composite_key(f_name, l_name, project)

    def before_update(self):
        """Wenn sich der Wert von team_of_actor geändert hat, werden die aktuellen availables-Eiträge
        der Person gelöscht. die verbundenen avail_day-Einträge werden dann automatisch gelöscht."""
        self.last_modified = datetime.utcnow()
        old_val = self._dbvals_.get(Person.team_of_actor)
        new_val = self.team_of_actor
        if new_val != old_val:
            for actor_p_p in self.actor_plan_periods:
                if not actor_p_p.plan_period.closed:
                    actor_p_p.delete()
        self.last_modified = datetime.utcnow()

    def before_insert(self):
        for t_o_d in self.project.time_of_days:
            self.time_of_days.add(t_o_d)


class Project(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 50, unique=True)
    active = Required(bool, default=False)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    teams = Set('Team')
    persons = Set(Person, reverse='project')
    admin = Optional(Person, reverse='project_of_admin')
    time_of_days = Set('TimeOfDay')
    excel_export_settings = Optional('ExcelExportSettings')

    def before_insert(self):
        self.excel_export_settings = ExcelExportSettings()

    def before_update(self):
        self.last_modified = datetime.utcnow()


class Team(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 50)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    project = Required(Project)
    locations_of_work = Set('LocationOfWork')
    persons = Set(Person, reverse='team_of_actor')
    dispatcher = Optional(Person, reverse='teams_of_dispatcher')
    plan_periods = Set('PlanPeriod')
    excel_export_settings = Optional('ExcelExportSettings')

    def before_insert(self):
        self.excel_export_settings = self.project.excel_export_settings

    def before_update(self):
        self.last_modified = datetime.utcnow()


class PlanPeriod(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    start = Required(date)
    end = Required(date)
    deadline = Required(date)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    notes = Optional(str)
    closed = Required(bool, default=True)
    team = Required(Team)
    actor_plan_periods = Set('ActorPlanPeriod')
    location_plan_periods = Set('LocationPlanPeriod')
    plans = Set('Plan')

    def before_update(self):
        self.last_modified = datetime.utcnow()


class ActorPlanPeriod(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    notes = Optional(str)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    plan_period = Required(PlanPeriod)
    person = Required(Person)
    avail_days = Set('AvailDay')
    time_of_days = Set('TimeOfDay')
    combination_locations_possibles = Set('CombinationLocationsPossible')
    actor_partner_location_prefs = Set('ActorPartnerLocationPref')

    @property
    def team(self):
        return self.plan_period.team

    def before_insert(self):
        for c in self.person.combination_locations_possibles:
            self.combination_locations_possibles.add(c)
        for c in self.person.actor_partner_location_prefs:
            self.actor_partner_location_prefs.add(c)
        for t_o_d in self.person.time_of_days:
            self.time_of_days.add(t_o_d)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class AvailDay(db.Entity):
    """Kann mehreren Appointments des gleichen Plans zugeteilt werden, falls Events kombinierbar sind.
Immer auch Appointments in unterschiedelichen Plänen zuteilbar."""
    id = PrimaryKey(UUID, auto=True)
    day = Required(date)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    actor_plan_period = Required(ActorPlanPeriod)
    time_of_day = Required('TimeOfDay', reverse='avail_days')
    time_of_days = Set('TimeOfDay', reverse='avail_days_defaults')
    appointments = Set('Appointment')
    combination_locations_possibles = Set('CombinationLocationsPossible')

    @property
    def team(self):
        return self.actor_plan_period.team

    def before_insert(self):
        for c in self.actor_plan_period.combination_locations_possibles:
            self.combination_locations_possibles.add(c)
        for t_o_d in self.actor_plan_period.time_of_days:
            self.time_of_days.add(t_o_d)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class TimeOfDay(db.Entity):
    """TimeOfDays werden beim Anlegen einer Person von den TimeOfDaysDefaults übernommen (nicht dupliziert).
Beim Anlegen einer ActorPlanPeriod werden sie von Person übernommen. Beim Anlegen eines AvailDay werden sie von ActorPlanPeriod übernommen.
Wird ein TimeOfDay einer Instanz verändert, wird eine Neue Instanz von AvailDay erzeugt und die Instanz mit gleichem Namen aus TimeOfDays entfernt.
Für LocationOfWork... gilt das gleiche Schema."""
    id = PrimaryKey(UUID, auto=True)
    name = Optional(str, 50)
    start = Required(timedelta)
    end = Required(timedelta)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    avail_days = Set(AvailDay, reverse='time_of_day')
    events = Set('Event', reverse='time_of_day')
    persons_defaults = Set(Person)
    actor_plan_periods_defaults = Set(ActorPlanPeriod)
    location_plan_periods_defaults = Set('LocationPlanPeriod')
    avail_days_defaults = Set(AvailDay, reverse='time_of_days')
    locations_of_work_defaults = Set('LocationOfWork')
    events_defaults = Set('Event', reverse='time_of_days')
    project_defaults = Required(Project)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class LocationOfWork(db.Entity):
    """Um die Konsistenz zurückliegender Pläne zu erhalten, sollten Instanzen von LocationOfWork nicht aus der Datenbank
    gelöscht werden, sondern nur der Wert prep_delete gesetzt werden.
    Einsatzort des Mitarbeiters, z.B. Klinik o. Filiale...
    nr_actors wird von neuer Instanz von LocationPlanPeriod übernommen."""
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 50)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    address = Optional('Address')
    team = Required(Team)
    nr_actors = Required(int, size=8, default=2, unsigned=True)
    location_plan_periods = Set('LocationPlanPeriod')
    time_of_days = Set(TimeOfDay)
    actor_partner_location_prefs = Set('ActorPartnerLocationPref')
    combination_locations_possibles = Set('CombinationLocationsPossible')

    @property
    def project(self):
        return self.team.project

    def before_update(self):
        self.last_modified = datetime.utcnow()

    def before_insert(self):
        for t_o_d in self.project.time_of_days:
            self.time_of_days.add(t_o_d)


class Address(db.Entity):
    """Adressen ohne Zugehörigkeit können in regelmäßigen Abständen gelöscht werden."""
    id = PrimaryKey(UUID, auto=True)
    street = Required(str, 50)
    postal_code = Required(str, 20)
    city = Required(str, 40)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    persons = Set(Person)
    location_of_work = Optional(LocationOfWork)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class Event(db.Entity):
    """Kann eine Veranstaltung, eine Arbeitsschicht o.Ä. sein."""
    id = PrimaryKey(UUID, auto=True)
    name = Optional(str, 50)
    notes = Optional(str)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    location_plan_period = Required('LocationPlanPeriod')
    date = Required(date)
    time_of_day = Required(TimeOfDay, reverse='events')
    time_of_days = Set(TimeOfDay, reverse='events_defaults')
    nr_actors = Required(int, size=8, unsigned=True)
    fixed_cast = Optional(str)  # Form: Person[1] and (Person[2] or Person[3] or Person[4]), (Person[1] or Person[2]) and (Person[3] or Person[4]), (Person[1] and Person[2]) or (Person[3] and Person[4])
    appointment = Set('Appointment')  # unterschiedliche Appointments in unterschiedlichen Plänen.
    flags = Set('Flag')  # auch um Event als Urlaub zu markieren.
    variation_event_group = Optional('VariationEventGroup')  # Falls vorhanden, wird nur 1 Event aus der Eventgroup zu einem Appointment.
    variation_weight = Optional(int, size=8, unsigned=True)  # ist None, wenn Event nicht in einer Eventgroup

    @property
    def team(self):
        return self.location_plan_period.team

    @property
    def location_of_work(self):
        return self.location_plan_period.location_of_work

    @property
    def plan_period(self):
        return self.location_plan_period.plan_period

    def before_insert(self):
        self.nr_actors = self.location_plan_period.nr_actors
        for t_o_d in self.location_plan_period.time_of_days:
            self.time_of_days.add(t_o_d)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class LocationPlanPeriod(db.Entity):
    """nr_actors wird von neuer Instanz von Event übernommen."""
    id = PrimaryKey(UUID, auto=True)
    notes = Optional(str)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    time_of_days = Set(TimeOfDay)
    plan_period = Required(PlanPeriod)
    location_of_work = Required(LocationOfWork)
    nr_actors = Optional(int, size=8, default=2, unsigned=True)
    events = Set(Event)

    @property
    def team(self):
        return self.plan_period.team

    def before_insert(self):
        self.nr_actors = self.location_of_work.nr_actors
        for t_o_d in self.location_of_work.time_of_days:
            self.time_of_days.add(t_o_d)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class Appointment(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    notes = Optional(str)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    avail_days = Set(AvailDay)  # je nach Besetzung werden mehrere Inst. von AvailDay zugeordnet.
    event = Required(Event)
    plan = Required('Plan')

    @property
    def team(self):
        return self.event.team

    @property
    def location_of_work(self):
        return self.event.location_of_work

    @property
    def weekday(self):
        return self.event.date.isoweekday()

    def before_update(self):
        self.last_modified = datetime.utcnow()


class ActorPartnerLocationPref(db.Entity):
    """score: 1 - volle Zustimmung, 0 - volle Ablehnung.
Präferenz-Instanz kann direkt von nächster Planungsebene übernommen werden, oder abgeändert als neue Instanz gespeichert werden.
ActorPlanPeriod übernimmt automatisch von Person, AvailDay übernimmt automatisch von ActorPlanPeriod."""
    id = PrimaryKey(UUID, auto=True)
    score = Required(float, default=1)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    person = Required(Person, reverse='actor_partner_location_prefs')
    partner = Required(Person, reverse='actor_partner_location_prefs__as_partner')
    location_of_work = Required(LocationOfWork)
    actor_plan_periods = Set(ActorPlanPeriod)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class Flag(db.Entity):
    """category bestimmt, welcher Klasse die Flag-Instanz zugehört."""
    id = PrimaryKey(UUID, auto=True)
    category = Optional(str)
    name = Required(str, 30)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    persons = Set(Person)
    events = Set(Event)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class VariationEventGroup(db.Entity):
    """Instanzen von VariationEventGroup ohne Events können nach Beenden der Planperiode gelöscht werden."""
    id = PrimaryKey(UUID, auto=True)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    events = Set(Event)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class CombinationLocationsPossible(db.Entity):
    """Verschiedene Personen können die gleiche Instanz einer Combination verwenden. Falls eine neue Instanz angelegt werden soll wird zuerst überprüft, ob es schon eine Instanz mit der gleichen Kombination von Locations gibt. Falls ja, sollte diese Instanz verwendet werden.
Eine neue Instanz von ActoPlanPeriod übernimmt die Combinations von Person, eine neue Instanz von AvailDay übernimmt die Combinations von ActorPlanPeriod."""
    id = PrimaryKey(UUID, auto=True)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    locations_of_work = Set(LocationOfWork)
    persons = Set(Person)
    actor_plan_periods = Set(ActorPlanPeriod)
    avail_days = Set(AvailDay)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class Plan(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 50, unique=True)
    notes = Optional(str)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    appointments = Set(Appointment)
    plan_period = Required(PlanPeriod)
    location_columns = Required(Json, default="{}")  # type -> dict[int, list[int]] ({weekday_nr: [Institution.id]})
    excel_export_settings = Optional('ExcelExportSettings')

    @property
    def team(self):
        return self.plan_period.team

    @property
    def location_head_columns(self):
        weekdays = sorted(list(self.appointments.weekday))
        return {weekday: [ap.location_of_work for ap in self.appointments.select(lambda a: a.weekday == weekday)]
                for weekday in weekdays}

    def before_insert(self):
        self.excel_export_settings = self.team.excel_export_settings

    def before_update(self):
        self.last_modified = datetime.utcnow()


class ExcelExportSettings(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    color_head_weekdays_1 = Optional(str, 15, default="#FFFFFF")
    colo_head_weekdays_2 = Optional(str, 15, default="#FFFFFF")
    color_head_locations_1 = Optional(str, 15, default="#FFFFFF")
    color_head_locations_2 = Optional(str, 15, default="#FFFFFF")
    color_day_nrs_1 = Optional(str, 15, default="#FFFFFF")
    color_day_nrs_2 = Optional(str, 15, default="#FFFFFF")
    color_column_kw_1 = Optional(str, 15, default="#FFFFFF")
    color_column_kw_2 = Optional(str, 15, default="#FFFFFF")
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    project = Optional(Project)
    teams = Set(Team)
    plans = Set(Plan)
