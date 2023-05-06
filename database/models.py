from datetime import date
from datetime import datetime, time
from typing import runtime_checkable, Protocol
from uuid import UUID
from pony.orm import Database, PrimaryKey, Required, Optional, Set, Json, composite_key

from database.enums import Gender

db = Database()


class CustomError(Exception):
    pass


@runtime_checkable
class ModelWithCombLocPossible(Protocol):
    id: UUID
    combination_locations_possibles: Set('CombinationLocationsPossible')


class Person(db.Entity):
    """Um die Konsistenz zurückliegender Pläne zu erhalten, sollten Instanzen von Personen nicht aus der Datenbank
    gelöscht werden, sondern nur der Wert prep_delete gesetzt werden."""
    id = PrimaryKey(UUID, auto=True)
    f_name = Required(str, 50)
    l_name = Required(str, 50)
    gender = Required(Gender, 20)
    email = Required(str, 50)
    phone_nr = Optional(str, 50)
    username = Required(str, 50, unique=True)
    password = Required(str)
    requested_assignments = Optional(int, size=16, default=8, unsigned=True)
    notes = Optional(str, nullable=True)  # Allgemeine Anmerkungen zum Mitarbeiter.
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
    time_of_day_standards = Set('TimeOfDay', reverse='persons_standard')
    # Wenn ein time_of_day_standard upgedatet wird, welcher auch Standart des Projektes ist wird er als neues
    # time_of_date_standard ohne Relation zum Projekt gespeichert.
    actor_partner_location_prefs = Set('ActorPartnerLocationPref', reverse='person')  # Es müssen nicht zu allen Kombinationen von Actor u. Location Präferenzen vorhanden sein. Fehlende Präferenzen bedeuten das gleiche, wie: score = 1
    actor_partner_location_prefs__as_partner = Set('ActorPartnerLocationPref', reverse='partner')
    actor_partner_location_prefs_defaults = Set('ActorPartnerLocationPref', reverse='person_default')
    actor_location_prefs = Set('ActorLocationPref')
    actor_location_prefs_defaults = Set('ActorLocationPref', reverse='person_default')
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
        if self.team_of_actor:
            self.combination_locations_possibles.add(self.team_of_actor.combination_locations_possibles)

    def before_insert(self):
        self.time_of_days.add(self.project.time_of_days)
        self.time_of_day_standards.add(self.project.time_of_day_standards)


class Project(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 50, unique=True)
    active = Required(bool, default=False)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    teams = Set('Team')
    persons = Set(Person, reverse='project')
    admin = Optional(Person, reverse='project_of_admin')
    addresses = Set('Address')
    locations_of_work = Set('LocationOfWork')
    time_of_days_all = Set('TimeOfDay', reverse='project')
    time_of_days = Set('TimeOfDay', reverse='project_defaults')
    time_of_day_standards = Set('TimeOfDay', reverse='project_standard')
    # Hier wird festgelegt,
    # weche konkreten Tageszeiten für die jeweiligen Enums als Standard für das Projekt gelten sollen.
    # Diese Standards werden von nachfolgenden Models übernommen,
    # können da aber durch zuweisen der Enums zu anderen Tageszeiten
    # oder Entfernen des Standards verändert werden.
    excel_export_settings = Optional('ExcelExportSettings')
    time_of_day_enums = Set('TimeOfDayEnum')
    combination_locations_possibles = Set('CombinationLocationsPossible')
    actor_location_prefs = Set('ActorLocationPref')

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
    combination_locations_possibles = Set('CombinationLocationsPossible')
    excel_export_settings = Optional('ExcelExportSettings')

    composite_key(project, name)

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
    notes = Optional(str, nullable=True)  # Anmerkungen des Dispatchers.
    closed = Required(bool, default=False)
    remainder = Required(bool, default=True)
    team = Required(Team)
    actor_plan_periods = Set('ActorPlanPeriod')
    location_plan_periods = Set('LocationPlanPeriod')
    plans = Set('Plan')

    @property
    def project(self):
        return self.team.project

    def before_update(self):
        self.last_modified = datetime.utcnow()


class ActorPlanPeriod(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    notes = Optional(str, nullable=True)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    plan_period = Required(PlanPeriod)
    person = Required(Person)
    avail_day_group = Optional('AvailDayGroup')
    time_of_days = Set('TimeOfDay')
    requested_assignments = Required(int, size=16, default=8, unsigned=True)
    combination_locations_possibles = Set('CombinationLocationsPossible')
    actor_partner_location_prefs_defaults = Set('ActorPartnerLocationPref')
    actor_location_prefs_defaults = Set('ActorLocationPref')
    avail_days = Set('AvailDay')
    time_of_day_standards = Set('TimeOfDay', reverse='actor_plan_periods_standard')

    @property
    def team(self):
        return self.plan_period.team

    @property
    def project(self):
        return self.team.project

    def before_insert(self):
        self.combination_locations_possibles.add(self.person.combination_locations_possibles)
        self.actor_partner_location_prefs_defaults.add(self.person.actor_partner_location_prefs_defaults)
        self.time_of_days.add(self.person.time_of_days)
        self.time_of_day_standards.add(self.person.time_of_day_standards)
        self.actor_location_prefs_defaults.add(self.person.actor_location_prefs_defaults)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class AvailDayGroup(db.Entity):
    """AvailDayGroups können entweder genau 1 AvailDay beinhalten, oder 1 oder mehrere AvailDayGroups.
       Jede AvailDayGroup ist entweder genau 1 AvailDayGroup zugeordnet oder genau einerActorPlanPeriod."""
    id = PrimaryKey(UUID, auto=True)
    actor_plan_period = Optional(ActorPlanPeriod)
    nr_avail_day_groups = Optional(int, unsigned=True)
    # Falls alle AvailDayGroups innerhalb der AvailDayGroup stattfinden können, entspricht der Wert genau dieser Anzahl
    # (alternativ: None).
    # Optional kann der Wert von nr_avail_day_groups auch geringer sein.
    avail_day_group = Optional('AvailDayGroup', reverse='avail_day_groups')
    avail_day_groups = Set('AvailDayGroup', reverse='avail_day_group')
    avail_day = Optional('AvailDay')
    variation_weight = Required(int, size=8, default=1, unsigned=True)
    # Falls weniger AvailDayGroups in einer AvailDayGroup als nr_avail_day_groups der AvailDayGroup, können den Groups
    # unterschiedliche Gewichtungen verliehen werden.
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())

    @property
    def actor_plan_period_getter(self):
        return self.actor_plan_period if self.actor_plan_period else self.avail_day_group.actor_plan_period_getter

    def before_update(self):
        self.last_modified = datetime.utcnow()

    def after_update(self):
        if not self.avail_day_groups and not self.actor_plan_period:
            self.delete()


class AvailDay(db.Entity):
    """Kann mehreren Appointments des gleichen Plans zugeteilt werden, falls Events kombinierbar sind.
Immer auch Appointments in unterschiedelichen Plänen zuteilbar."""
    id = PrimaryKey(UUID, auto=True)
    day = Required(date)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    actor_plan_period = Required(ActorPlanPeriod)
    avail_day_group = Required('AvailDayGroup')
    time_of_day = Required('TimeOfDay', reverse='avail_days')
    time_of_days = Set('TimeOfDay', reverse='avail_days_defaults')  # kann weg!!!!!!!!
    appointments = Set('Appointment')
    combination_locations_possibles = Set('CombinationLocationsPossible')
    actor_partner_location_prefs_defaults = Set('ActorPartnerLocationPref')
    actor_location_prefs_defaults = Set('ActorLocationPref')

    @property
    def project(self):
        return self.actor_plan_period.project

    @property
    def team(self):
        return self.actor_plan_period.team

    def before_insert(self):
        self.combination_locations_possibles.add(self.actor_plan_period.combination_locations_possibles)
        self.time_of_days.add(self.actor_plan_period.time_of_days)
        self.actor_partner_location_prefs_defaults.add(self.actor_plan_period.actor_partner_location_prefs_defaults)
        self.actor_location_prefs_defaults.add(self.actor_plan_period.actor_location_prefs_defaults)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class TimeOfDay(db.Entity):
    """TimeOfDays werden beim Anlegen einer Person von den TimeOfDaysDefaults übernommen (nicht dupliziert).
Beim Anlegen einer ActorPlanPeriod werden sie von Person übernommen. Beim Anlegen eines AvailDay werden sie von ActorPlanPeriod übernommen.
Wird ein TimeOfDay einer Instanz verändert, wird eine Neue Instanz von AvailDay erzeugt und die Instanz mit gleichem Namen aus TimeOfDays entfernt.
Für LocationOfWork... gilt das gleiche Schema."""
    id = PrimaryKey(UUID, auto=True)
    name = Optional(str, 50)
    start = Required(time)
    end = Required(time)
    time_of_day_enum = Required('TimeOfDayEnum')
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    project = Required(Project, reverse='time_of_days_all')
    avail_days = Set(AvailDay, reverse='time_of_day')
    events = Set('Event', reverse='time_of_day')
    project_standard = Optional(Project, reverse='time_of_day_standards')
    persons_standard = Set(Person, reverse='time_of_day_standards')
    actor_plan_periods_standard = Set(ActorPlanPeriod, reverse='time_of_day_standards')
    locations_of_work_standard = Set('LocationOfWork', reverse='time_of_day_standards')
    location_plan_periods_standard = Set('LocationPlanPeriod', reverse='time_of_day_standards')
    project_defaults = Optional(Project, reverse='time_of_days')
    persons_defaults = Set(Person)
    actor_plan_periods_defaults = Set(ActorPlanPeriod)
    location_plan_periods_defaults = Set('LocationPlanPeriod')
    avail_days_defaults = Set(AvailDay, reverse='time_of_days')
    locations_of_work_defaults = Set('LocationOfWork')
    events_defaults = Set('Event', reverse='time_of_days')

    def before_update(self):
        """Falls diese Instanz keine Verwendung mehr hat, wird sie zum Löschen markiert."""
        self.last_modified = datetime.utcnow()


class TimeOfDayEnum(db.Entity):
    """Zeigt durch den Index die Position im Tagesablauf an."""
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 50)
    abbreviation = Required(str, 10)
    time_index = Required(int, size=8, unsigned=True)  # Einordnung im Tagesverlauf
    time_of_days = Set(TimeOfDay)
    project = Required(Project)

    composite_key(name, project)
    composite_key(abbreviation, project)
    composite_key(time_index, project)


class LocationOfWork(db.Entity):
    """Um die Konsistenz zurückliegender Pläne zu erhalten, sollten Instanzen von LocationOfWork nicht aus der Datenbank
    gelöscht werden, sondern nur der Wert prep_delete gesetzt werden.
    Einsatzort des Mitarbeiters, z.B. Klinik o. Filiale...
    nr_actors wird von neuer Instanz von LocationPlanPeriod übernommen."""
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 50)
    notes = Optional(str)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    address = Optional('Address')
    project = Required(Project)
    team = Optional(Team)
    nr_actors = Required(int, size=8, default=2, unsigned=True)
    fixed_cast = Optional(str, nullable=True)  # Form: Person[1] and (Person[2] or Person[3] or Person[4]), (Person[1] or Person[2]) and (Person[3] or Person[4]), (Person[1] and Person[2]) or (Person[3] and Person[4])
    location_plan_periods = Set('LocationPlanPeriod')
    time_of_days = Set(TimeOfDay)
    time_of_day_standards = Set(TimeOfDay, reverse='locations_of_work_standard')
    actor_partner_location_prefs = Set('ActorPartnerLocationPref')
    actor_location_prefs = Set('ActorLocationPref')
    combination_locations_possibles = Set('CombinationLocationsPossible')

    composite_key(project, name)

    def before_update(self):
        self.last_modified = datetime.utcnow()

    def before_insert(self):
        self.time_of_days.add(self.project.time_of_days)
        self.time_of_day_standards.add(self.project.time_of_day_standards)


class Address(db.Entity):
    """Adressen ohne Zugehörigkeit können in regelmäßigen Abständen gelöscht werden."""
    id = PrimaryKey(UUID, auto=True)
    street = Required(str, 50)
    postal_code = Required(str, 20)
    city = Required(str, 40)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    project = Required(Project)
    prep_delete = Optional(datetime)
    persons = Set(Person)
    location_of_work = Optional(LocationOfWork)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class Event(db.Entity):
    """Kann eine Veranstaltung, eine Arbeitsschicht o.Ä. sein.
       Ein Event muss immer genau einer Eventgroup zugeordnet sein."""
    id = PrimaryKey(UUID, auto=True)
    name = Optional(str, 50)
    notes = Optional(str, nullable=True)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    date = Required(date)
    time_of_day = Required(TimeOfDay, reverse='events')
    time_of_days = Set(TimeOfDay, reverse='events_defaults')
    nr_actors = Required(int, size=8, unsigned=True)
    fixed_cast = Optional(str, nullable=True)  # Form: (Person[1] and (Person[2] or Person[3] or Person[4]), (Person[1] or Person[2]) and (Person[3] or Person[4]), (Person[1] and Person[2]) or (Person[3] and Person[4])
    appointment = Set('Appointment')  # unterschiedliche Appointments in unterschiedlichen Plänen.
    flags = Set('Flag')  # auch um Event als Urlaub zu markieren.
    event_group = Required('EventGroup')

    @property
    def location_plan_period(self):
        return self.event_group.location_plan_period_getter

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
            if not t_o_d.prep_delete:
                self.time_of_days.add(t_o_d)
        self.fixed_cast = self.location_plan_period.fixed_cast

    def before_update(self):
        self.last_modified = datetime.utcnow()


class EventGroup(db.Entity):
    """Eventgroups können entweder genau 1 Event beinhalten, oden 1 oder mehrere Eventgroups.
       Jede Eventgroup ist entweder genau 1 Eventgroup zugeordnet oder genau einer Location PlanPeriod."""
    id = PrimaryKey(UUID, auto=True)
    location_plan_period = Optional('LocationPlanPeriod')
    same_day_cast_pref = Required(int, size=8, default=2, unsigned=True)
    # Wenn am gleichen Tag mehrere Events der gleichen Location stattfinden bedeuten:
    # 0: beliebige Besetzungen, 1: möglichsts die gleiche Besetzung, 2 unbedingt die gleiche Besetzung.
    same_group_cast_pref = Required(int, size=8, default=0, unsigned=True)
    # Gibt an, ob innerhalb einer Eventgroup die gleiche Besetzung präferiert werden soll.
    # Gewichtungen wie same_day_cast_pref
    nr_eventgroups = Optional(int, unsigned=True)
    # Falls alle Eventgroups innerhalbEventgroup stattfinden sollen, entspricht der Wert genau dieser Anzahl
    # (alternativ: None).
    # Optional kann der Wert von nr_eventgroups auch geringer sein.
    event_group = Optional('EventGroup', reverse='event_groups')
    event_groups = Set('EventGroup', reverse='event_group')
    event = Optional(Event)
    variation_weight = Required(int, size=8, default=1, unsigned=True)  # Falls weniger Eventgroups in einer Eventgroup als nr_events der Eventgroup können den Events unterschiedliche Gewichtungen verliehen werden.
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Optional(datetime)

    @property
    def location_plan_period_getter(self):
        return self.location_plan_period if self.location_plan_period else self.event_group.location_plan_period_getter

    def before_update(self):
        self.last_modified = datetime.utcnow()

    def before_insert(self):
        if not (self.location_plan_period or self.event_group) or (self.location_plan_period and self.event_group):
            raise CustomError('Eine Eventgroup muss entweder genau 1 Eventgroup '
                              'oder genau einer Location PlanPeriod zugeordnet sein.')


class LocationPlanPeriod(db.Entity):
    """nr_actors wird von neuer Instanz von Event übernommen.
       Jede LocationPlanPeriod enthält genau 1 Eventgroup."""
    id = PrimaryKey(UUID, auto=True)
    notes = Optional(str, nullable=True)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    time_of_days = Set(TimeOfDay)
    time_of_day_standards = Set(TimeOfDay, reverse='location_plan_periods_standard')
    plan_period = Required(PlanPeriod)
    location_of_work = Required(LocationOfWork)
    nr_actors = Optional(int, size=8, default=2, unsigned=True)
    fixed_cast = Optional(str, nullable=True)  # Form: Person[1] and (Person[2] or Person[3] or Person[4]), (Person[1] or Person[2]) and (Person[3] or Person[4]), (Person[1] and Person[2]) or (Person[3] and Person[4])
    event_group = Optional('EventGroup')

    @property
    def team(self):
        return self.plan_period.team

    def before_insert(self):
        self.nr_actors = self.location_of_work.nr_actors
        self.time_of_days.add(self.location_of_work.time_of_days)
        self.time_of_day_standards.add(self.location_of_work.time_of_day_standards)
        self.fixed_cast = self.location_of_work.fixed_cast

    def before_update(self):
        self.last_modified = datetime.utcnow()


class Appointment(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    notes = Optional(str, nullable=True)
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
    """score: 2 - volle Zustimmung, 1 - normale Zustimmung, 0 - volle Ablehnung.
    Präferenz-Instanz kann direkt von nächster Planungsebene übernommen werden, oder abgeändert als neue Instanz
    gespeichert werden.
    ActorPlanPeriod übernimmt automatisch von Person, AvailDay übernimmt automatisch von ActorPlanPeriod."""
    id = PrimaryKey(UUID, auto=True)
    score = Required(float, default=1)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    person = Required(Person, reverse='actor_partner_location_prefs')
    partner = Required(Person, reverse='actor_partner_location_prefs__as_partner')
    location_of_work = Required(LocationOfWork)
    person_default = Optional(Person, reverse='actor_partner_location_prefs_defaults')
    actor_plan_periods_defaults = Set(ActorPlanPeriod)
    avail_days_dafaults = Set(AvailDay)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class Flag(db.Entity):
    """category bestimmt, welcher Klasse die Flag-Instanz zugehört."""
    id = PrimaryKey(UUID, auto=True)
    category = Optional(str, nullable=True)
    name = Required(str, 30)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    persons = Set(Person)
    events = Set(Event)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class CombinationLocationsPossible(db.Entity):
    """Verschiedene Personen können die gleiche Instanz einer Combination verwenden.
    Falls eine neue Instanz angelegt werden soll wird zuerst überprüft, ob es schon eine Instanz mit der gleichen
    Kombination von Locations gibt. Falls ja, sollte diese Instanz verwendet werden.
    Eine neue Instanz von ActoPlanPeriod übernimmt die Combinations von Person,
    eine neue Instanz von AvailDay übernimmt die Combinations von ActorPlanPeriod."""
    id = PrimaryKey(UUID, auto=True)
    project = Required(Project)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    locations_of_work = Set(LocationOfWork)
    team = Optional(Team)
    persons = Set(Person)
    actor_plan_periods = Set(ActorPlanPeriod)
    avail_days = Set(AvailDay)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class ActorLocationPref(db.Entity):
    """Score 0: Person möchte keinen Einsatz in dieser Einrichtung.
    Score 1: Gerne in dieser Einrichtung.
    Score 1-2 bevorzugt in dieser Einrichtung."""
    id = PrimaryKey(UUID, auto=True)
    score = Required(float, default=1)
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    last_modified = Required(datetime, default=lambda: datetime.utcnow())
    prep_delete = Optional(datetime)
    project = Required(Project)
    person = Required(Person)
    location_of_work = Required(LocationOfWork)
    person_default = Optional(Person, reverse='actor_location_prefs_defaults')
    actor_plan_periods_defaults = Set(ActorPlanPeriod)
    avail_days_defaults = Set(AvailDay)

    def before_update(self):
        self.last_modified = datetime.utcnow()


class Plan(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 50, unique=True)
    notes = Optional(str, nullable=True)
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
    color_head_weekdays_2 = Optional(str, 15, default="#FFFFFF")
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


#  noch zu implementieren
"""class APSchedulerJob(db.Entity):
    id = PrimaryKey(int, auto=True)
    plan_period = Required(PlanPeriod)
    job = Required(bytes)"""
