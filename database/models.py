import datetime
from typing import runtime_checkable, Protocol
from uuid import UUID, uuid4
from pony.orm import Database, PrimaryKey, Required, Optional, Set, Json, composite_key

from database.enums import Gender, Role

db = Database()


def utcnow_naive():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)



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
    gender = Optional(Gender, 20)
    role = Optional(Role, 20, nullable=True)
    email = Required(str, 50)
    phone_nr = Optional(str, 50, nullable=True)
    username = Required(str, 50, unique=True)
    password = Required(str)
    requested_assignments = Optional(int, size=16, default=8, unsigned=True)
    notes = Optional(str, nullable=True)  # Allgemeine Anmerkungen zum Mitarbeiter.
    created_at = Optional(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    project = Required('Project', reverse='persons')
    team_actor_assigns = Set('TeamActorAssign')
    project_of_admin = Optional('Project', reverse='admin')
    teams_of_dispatcher = Set('Team', reverse='dispatcher', cascade_delete=False)
    actor_plan_periods = Set('ActorPlanPeriod')
    address = Optional('Address')
    time_of_days = Set('TimeOfDay')
    time_of_day_standards = Set('TimeOfDay', reverse='persons_standard')
    # Wenn ein time_of_day_standard upgedatet wird, welcher auch Standard des Projektes ist, wird er als neues
    # time_of_date_standard ohne Relation zum Projekt gespeichert.
    actor_partner_location_prefs = Set('ActorPartnerLocationPref', reverse='person')  # Es müssen nicht zu allen Kombinationen von Actor u. Location Präferenzen vorhanden sein. Fehlende Präferenzen bedeuten das gleiche, wie: score = 1
    actor_partner_location_prefs__as_partner = Set('ActorPartnerLocationPref', reverse='partner')
    actor_partner_location_prefs_defaults = Set('ActorPartnerLocationPref', reverse='person_default')
    actor_location_prefs = Set('ActorLocationPref')
    actor_location_prefs_defaults = Set('ActorLocationPref', reverse='person_default')
    flags = Set('Flag')
    skills = Set('Skill')
    combination_locations_possibles = Set('CombinationLocationsPossible')
    employee_events = Set('EmployeeEvent')

    composite_key(f_name, l_name, project)

    @property
    def full_name(self):
        return f'{self.f_name} {self.l_name}'

    def before_update(self):
        """Wenn sich der Wert von team_of_actor geändert hat, werden die aktuellen availables-Eiträge
        der Person gelöscht. die verbundenen avail_day-Einträge werden dann automatisch gelöscht."""
        self.last_modified = utcnow_naive()
        # old_val = self._dbvals_.get(Person.team_of_actor)
        # new_val = self.team_of_actor
        # if new_val != old_val:
        #     for actor_p_p in self.actor_plan_periods:
        #         if not actor_p_p.plan_period.closed:
        #             actor_p_p.delete()
        # self.last_modified = utcnow_naive()

    def before_insert(self):
        self.time_of_days.add(self.project.time_of_days)
        self.time_of_day_standards.add(self.project.time_of_day_standards)
        if self.team_actor_assigns:
            latest_taa = max(self.team_actor_assigns, key=lambda x: x.start)
            if not latest_taa.end:
                self.combination_locations_possibles.add(latest_taa.team.combination_locations_possibles)


class Project(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 50, unique=True)
    active = Required(bool, default=False)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    teams = Set('Team')
    persons = Set(Person, reverse='project')
    admin = Optional(Person, reverse='project_of_admin')
    addresses = Set('Address')
    locations_of_work = Set('LocationOfWork')
    time_of_days_all = Set('TimeOfDay', reverse='project')
    time_of_days = Set('TimeOfDay', reverse='project_defaults')
    time_of_day_standards = Set('TimeOfDay', reverse='project_standard')
    time_of_day_enums = Set('TimeOfDayEnum')
    time_of_day_enum_standards = Set('TimeOfDayEnum', reverse='project_standard')
    # Hier wird festgelegt,
    # welche konkreten Tageszeiten für die jeweiligen Enums als Standard für das Projekt gelten sollen.
    # Diese Standards werden von nachfolgenden Models übernommen,
    # können da aber durch Zuweisen der Enums zu anderen Tageszeiten
    # oder Entfernen des Standards verändert werden.
    excel_export_settings = Optional('ExcelExportSettings')
    combination_locations_possibles = Set('CombinationLocationsPossible')
    actor_location_prefs = Set('ActorLocationPref')
    skills = Set('Skill')
    flags = Set('Flag')
    cast_rules = Set('CastRule')
    # todo: different_cast_on_different_locations_at_same_day: bool (auch in Team PlanPeriod und ActorPlanPeriod)
    #  Kann aufgehoben werden durch entsprechendes CombinationLocationsPossible
    # todo: same_cast_on_same_location_at_same_day: bool (auch in Team PlanPeriod und ActorPlanPeriod)
    #  Kann aufgehoben werden durch eine entsprechende CastRule oder ein entsprechendes FixedCast
    employee_events = Set('EmployeeEvent')
    employee_event_categories = Set('EmployeeEventCategory')

    def before_insert(self):
        self.excel_export_settings = ExcelExportSettings()

    def before_update(self):
        self.last_modified = utcnow_naive()


class Team(db.Entity):
    # not_sure: time_of_days, time_of_day_standards auch hier?
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 50)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    notes = Optional(str, nullable=True, default=None)
    project = Required(Project)
    # locations_of_work = Set('LocationOfWork')  # wird entfernt
    # persons = Set(Person, reverse='team_of_actor')  # wird entfernt
    team_actor_assigns = Set('TeamActorAssign')
    team_location_assigns = Set('TeamLocationAssign')
    dispatcher = Optional(Person, reverse='teams_of_dispatcher')
    plan_periods = Set('PlanPeriod')
    combination_locations_possibles = Set('CombinationLocationsPossible')
    excel_export_settings = Optional('ExcelExportSettings')
    employee_events = Set('EmployeeEvent')

    composite_key(project, name)

    def before_insert(self):
        self.excel_export_settings = self.project.excel_export_settings

    def before_update(self):
        self.last_modified = utcnow_naive()


class PlanPeriod(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    start = Required(datetime.date)
    end = Required(datetime.date)
    deadline = Required(datetime.date)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    notes = Optional(str, nullable=True)
    notes_for_employees = Optional(str, nullable=True, default=None)  # Anmerkungen und Mitteilungen des Dispatchers.
    closed = Required(bool, default=False)
    remainder = Required(bool, default=True)
    team = Required(Team)
    actor_plan_periods = Set('ActorPlanPeriod')
    location_plan_periods = Set('LocationPlanPeriod')
    cast_groups = Set('CastGroup')
    plans = Set('Plan')

    @property
    def project(self):
        return self.team.project

    def before_update(self):
        self.last_modified = utcnow_naive()


class ActorPlanPeriod(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    notes = Optional(str, nullable=True)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    plan_period = Required(PlanPeriod)
    person = Required(Person)
    avail_day_group = Optional('AvailDayGroup')
    time_of_days = Set('TimeOfDay')
    requested_assignments = Required(int, size=16, default=8, unsigned=True)
    required_assignments = Required(bool, default=False)
    combination_locations_possibles = Set('CombinationLocationsPossible')
    actor_partner_location_prefs_defaults = Set('ActorPartnerLocationPref')
    actor_location_prefs_defaults = Set('ActorLocationPref')
    avail_days = Set('AvailDay')
    time_of_day_standards = Set('TimeOfDay', reverse='actor_plan_periods_standard')
    # Standard-Tageszeiten, die verwendet werden, um das Check-Field in der ActorPlanPeriod-View aufzubauen.
    # Beim ersten Setzen eines AvailDays wird die Standard-Tageszeit ausgewählt.
    max_fair_shifts_of_apps = Set('MaxFairShiftsOfApp')

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
        self.last_modified = utcnow_naive()


class AvailDayGroup(db.Entity):
    """AvailDayGroups können entweder genau 1 AvailDay beinhalten, oder 1 oder mehrere AvailDayGroups.
       Jede AvailDayGroup ist entweder genau 1 AvailDayGroup zugeordnet oder genau einerActorPlanPeriod.
       Jede ActorPlanPeriod enthält genau 1 AvailDayGroup. Jeder AvailDay ist genau 1 AvailDayGroup zugeordnet."""
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
    # Falls mehr AvailDayGroups in einer AvailDayGroup als nr_avail_day_groups der AvailDayGroup, können den Groups
    # durch variation_weight unterschiedliche Gewichtungen verliehen werden.
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    required_avail_day_groups = Optional('RequiredAvailDayGroups', cascade_delete=True)

    @property
    def actor_plan_period_getter(self):
        return self.actor_plan_period or self.avail_day_group.actor_plan_period_getter

    def before_update(self):
        self.last_modified = utcnow_naive()


class RequiredAvailDayGroups(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    num_avail_day_groups = Optional(int, size=8, unsigned=True)
    avail_day_group = Required('AvailDayGroup')
    locations_of_work = Set('LocationOfWork')
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    #not_sure: Boolean-Feld "separate_locations" hinzufügen, um zu steuern,
    # ob für jede Location separat num_avail_day_groups gelten soll.

    def before_update(self):
        self.last_modified = utcnow_naive()



class AvailDay(db.Entity):
    """Kann mehreren Appointments des gleichen Plans zugeteilt werden, falls Events kombinierbar sind.
    Immer auch Appointments in unterschiedlichen Plänen zuteilbar."""
    id = PrimaryKey(UUID, auto=True)
    date = Required(datetime.date)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    actor_plan_period = Required(ActorPlanPeriod)
    avail_day_group = Required('AvailDayGroup')
    time_of_day = Required('TimeOfDay', reverse='avail_days')
    time_of_days = Set('TimeOfDay', reverse='avail_days_defaults')  # not_sure: kann weg?
    skills = Set('Skill')
    appointments = Set('Appointment')
    combination_locations_possibles = Set('CombinationLocationsPossible')
    actor_partner_location_prefs_defaults = Set('ActorPartnerLocationPref')
    # actor_partner_location_prefs, die nicht im Set vorkommen werden mit Score=1 gewertet.
    actor_location_prefs_defaults = Set('ActorLocationPref')

    composite_key(actor_plan_period, date, time_of_day)

    @property
    def project(self):
        return self.actor_plan_period.project

    @property
    def plan_period(self):
        return self.actor_plan_period.plan_period

    @property
    def team(self):
        return self.actor_plan_period.team

    def before_insert(self):
        self.combination_locations_possibles.add(self.actor_plan_period.combination_locations_possibles)
        self.time_of_days.add(self.actor_plan_period.time_of_days)
        self.actor_partner_location_prefs_defaults.add(self.actor_plan_period.actor_partner_location_prefs_defaults)
        self.actor_location_prefs_defaults.add(self.actor_plan_period.actor_location_prefs_defaults)
        self.skills.add(self.actor_plan_period.person.skills)

    def before_update(self):
        self.last_modified = utcnow_naive()


class TimeOfDay(db.Entity):
    """TimeOfDays werden beim Anlegen einer Person von den TimeOfDaysDefaults übernommen (nicht dupliziert).
Beim Anlegen einer ActorPlanPeriod werden sie von Person übernommen. Beim Anlegen eines AvailDay werden sie von ActorPlanPeriod übernommen.
Wird ein TimeOfDay einer Instanz verändert, wird eine neue Instanz von AvailDay erzeugt und die Instanz mit gleichem Namen aus TimeOfDays entfernt.
Für LocationOfWork... gilt das gleiche Schema."""
    id = PrimaryKey(UUID, auto=True)
    name = Optional(str, 50)
    start = Required(datetime.time)
    end = Required(datetime.time)
    time_of_day_enum = Required('TimeOfDayEnum')
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
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
        self.last_modified = utcnow_naive()


class TimeOfDayEnum(db.Entity):
    """Zeigt durch den Index die Position im Tagesablauf an."""
    id = PrimaryKey(UUID, auto=True)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    name = Required(str, 50)
    abbreviation = Required(str, 10)
    time_index = Required(int, size=8, unsigned=True)  # Einordnung im Tagesverlauf
    time_of_days = Set(TimeOfDay)
    project = Required(Project)
    project_standard = Optional(Project, reverse='time_of_day_enum_standards')  # not_sure: Vielleicht unnötig!

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
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    address = Optional('Address')
    project = Required(Project)
    # team = Optional(Team)  # wird entfernt
    team_location_assigns = Set('TeamLocationAssign')
    nr_actors = Required(int, size=8, default=2, unsigned=True)
    fixed_cast = Optional(str, nullable=True)  # Form: Person[1] and (Person[2] or Person[3] or Person[4]), (Person[1] or Person[2]) and (Person[3] or Person[4]), (Person[1] and Person[2]) or (Person[3] and Person[4])
    fixed_cast_only_if_available = Required(bool, default=False)  # Form: Person[1] and (Person[2] or Person[3] or Person[4]), (Person[1] or Person[2]) and (Person[3] or Person[4]), (Person[1] and Person[2]) or (Person[3] and Person[4])
    skill_groups = Set('SkillGroup')
    location_plan_periods = Set('LocationPlanPeriod')
    time_of_days = Set(TimeOfDay)
    time_of_day_standards = Set(TimeOfDay, reverse='locations_of_work_standard')
    actor_partner_location_prefs = Set('ActorPartnerLocationPref')
    actor_location_prefs = Set('ActorLocationPref')
    combination_locations_possibles = Set('CombinationLocationsPossible')
    required_avail_day_groups = Set('RequiredAvailDayGroups')

    composite_key(project, name)

    @property
    def name_and_city(self):
        return f'{self.name} {self.address.city}' if self.address.city else self.name

    def before_update(self):
        self.last_modified = utcnow_naive()

    def before_insert(self):
        self.time_of_days.add(self.project.time_of_days)
        self.time_of_day_standards.add(self.project.time_of_day_standards)


class TeamActorAssign(db.Entity):
    """Gibt den Zeitabschnitt an, in welchem die Person einem bestimmten Team zugeordnet war/ist.
    start -> inclusive, end -> exclusive"""
    id = PrimaryKey(UUID, auto=True)
    start = Required(datetime.date, default=lambda: datetime.date.today())
    end = Optional(datetime.date)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    person = Required(Person)
    team = Required(Team)

    def before_update(self):
        self.last_modified = utcnow_naive()


class TeamLocationAssign(db.Entity):
    """Gibt den Zeitabschnitt an, in welchem die Location einem bestimmten Team zugeordnet war/ist.
    start -> inclusive, end -> exclusive"""
    id = PrimaryKey(UUID, auto=True)
    start = Required(datetime.date, default=lambda: datetime.date.today())
    end = Optional(datetime.date)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    location_of_work = Required(LocationOfWork)
    team = Required(Team)

    def before_update(self):
        self.last_modified = utcnow_naive()


class Address(db.Entity):
    """Adressen ohne Zugehörigkeit können in regelmäßigen Abständen gelöscht werden."""
    id = PrimaryKey(UUID, auto=True)
    name = Optional(str, 50, nullable=True)  # Optionaler Name für die Adresse, z.B. "Klinik XYZ"
    street = Optional(str, 50, nullable=True)
    postal_code = Optional(str, 20, nullable=True)
    city = Optional(str, 40, nullable=True)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    project = Required(Project)
    prep_delete = Optional(datetime.datetime)
    persons = Set(Person)
    location_of_work = Optional(LocationOfWork)
    employee_events = Set('EmployeeEvent')

    def before_update(self):
        self.last_modified = utcnow_naive()


class Event(db.Entity):
    """Kann eine Veranstaltung, eine Arbeitsschicht o.Ä. sein.
       Ein Event muss immer genau einer Eventgroup zugeordnet sein."""
    id = PrimaryKey(UUID, auto=True)
    name = Optional(str, 50)
    notes = Optional(str, nullable=True)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    date = Required(datetime.date)
    time_of_day = Required(TimeOfDay, reverse='events')
    time_of_days = Set(TimeOfDay, reverse='events_defaults')
    skill_groups = Set('SkillGroup')
    appointments = Set('Appointment')  # unterschiedliche Appointments in unterschiedlichen Plänen.
    flags = Set('Flag')  # auch um Event als Urlaub zu markieren.
    event_group = Required('EventGroup')
    cast_group = Required('CastGroup')
    location_plan_period = Required('LocationPlanPeriod')

    @property
    def plan_period(self):
        return self.location_plan_period.plan_period

    def before_insert(self):
        for t_o_d in self.location_plan_period.time_of_days:
            if not t_o_d.prep_delete:
                self.time_of_days.add(t_o_d)

    def before_update(self):
        self.last_modified = utcnow_naive()


class EventGroup(db.Entity):
    """Eventgroups können entweder genau 1 Event beinhalten, oder 1 oder mehrere Eventgroups.
       Jede Eventgroup ist entweder genau 1 Eventgroup zugeordnet oder genau 1 Location PlanPeriod."""
    id = PrimaryKey(UUID, auto=True)
    location_plan_period = Optional('LocationPlanPeriod')
    nr_event_groups = Optional(int, unsigned=True)
    # Falls alle Eventgroups innerhalb Eventgroup stattfinden sollen, entspricht der Wert genau dieser Anzahl
    # (alternativ: None).
    # Optional kann der Wert von nr_eventgroups auch geringer sein.
    event_group = Optional('EventGroup', reverse='event_groups')
    event_groups = Set('EventGroup', reverse='event_group')
    event = Optional(Event)
    variation_weight = Required(int, size=8, default=1, unsigned=True)
    # Falls mehr Eventgroups in einer Eventgroup als nr_events der Eventgroup können variation_weight
    # den Eventgroups unterschiedliche Gewichtungen verliehen werden.
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Optional(datetime.datetime)

    @property
    def location_plan_period_getter(self):
        return self.location_plan_period or self.event_group.location_plan_period_getter

    def before_update(self):
        self.last_modified = utcnow_naive()

    def before_insert(self):
        if not (self.location_plan_period or self.event_group) or (self.location_plan_period and self.event_group):
            raise CustomError('Eine Eventgroup muss entweder genau 1 Eventgroup '
                              'oder genau einer Location PlanPeriod zugeordnet sein.')


class CastGroup(db.Entity):
    """child_groups können mehr als 1 parent_group haben. Ein Grund dafür könnte z.B. sein:
    Die Besetzungen von 2 aufeinanderfolgenden Tage haben jeweils Regeln (1. Tag: gleiche Besetzung von Spät-
    und Nachtschicht, 2. Tag: ungleiche Besetzung von Früh- und Nachmittagsschicht). Außerdem soll die Nachtschicht und
    die Frühschicht ungleich besetzt sein."""
    id = PrimaryKey(UUID, auto=True)
    plan_period = Required(PlanPeriod)
    parent_groups = Set('CastGroup', reverse='child_groups')
    child_groups = Set('CastGroup', reverse='parent_groups')
    fixed_cast = Optional(str, nullable=True)
    fixed_cast_only_if_available = Required(bool, default=False)
    prefer_fixed_cast_events = Required(bool, default=False)
    nr_actors = Required(int, size=16, unsigned=True)
    event = Optional(Event)
    custom_rule = Optional(str, nullable=True)
    cast_rule = Optional('CastRule')
    strict_cast_pref = Required(int, size=8, default=2, unsigned=True)
    # 0: beliebige Besetzungen, 1: möglichst nah an Besetzungsregel, 2 unbedingt Besetzungsregel beachten.

    @property
    def project(self):
        return self.plan_period.team.project


class CastRule(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    project = Required(Project)
    name = Required(str, 50, unique=True)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    rule = Required(str)
    # Literale z.B. "ABAC": stehen für Besetzungen
    # *: beliebige Besetzung
    # ~: gleiche Besetzung
    # -: andere Besetzung
    # ... in Bezug auf den vorangegangenen Termin.
    # Die Sequenz wird automatisch so lange wiederholt, bis die Terminreihe gefüllt ist.
    cast_groups = Set(CastGroup)


class LocationPlanPeriod(db.Entity):
    """nr_actors wird von neuer Instanz von Event übernommen.
       Jede LocationPlanPeriod enthält genau 1 Eventgroup."""
    id = PrimaryKey(UUID, auto=True)
    notes = Optional(str, nullable=True)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    time_of_days = Set(TimeOfDay)
    time_of_day_standards = Set(TimeOfDay, reverse='location_plan_periods_standard')
    plan_period = Required(PlanPeriod)
    location_of_work = Required(LocationOfWork)
    nr_actors = Optional(int, size=8, default=2, unsigned=True)
    fixed_cast = Optional(str, nullable=True)  # Form: Person[1] and (Person[2] or Person[3] or Person[4]), (Person[1] or Person[2]) and (Person[3] or Person[4]), (Person[1] and Person[2]) or (Person[3] and Person[4])
    fixed_cast_only_if_available = Required(bool, default=False)  # Wenn aktiviert, werden nicht verfügbare Mitarbeiter aus der fixed_cast Liste entfernt.
    event_group = Optional('EventGroup')
    events = Set(Event)

    @property
    def team(self):
        return self.plan_period.team

    @property
    def project(self):
        return self.team.project

    def before_insert(self):
        self.nr_actors = self.location_of_work.nr_actors
        self.time_of_days.add(self.location_of_work.time_of_days)
        self.time_of_day_standards.add(self.location_of_work.time_of_day_standards)
        self.fixed_cast = self.location_of_work.fixed_cast
        self.fixed_cast_only_if_available = self.location_of_work.fixed_cast_only_if_available

    def before_update(self):
        self.last_modified = utcnow_naive()


class Appointment(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    notes = Optional(str, nullable=True)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    avail_days = Set(AvailDay)  # je nach Besetzung werden mehrere Inst. von AvailDay zugeordnet.
    guests = Required(Json, default="[]")  # Es können die Namen von temporären Gastmitarbeitern eingesetzt werden.
    event = Required(Event)
    plan = Required('Plan')

    @property
    def team(self):
        return self.event.team

    @property
    def location_of_work(self):
        return self.event.location_of_work

    def before_update(self):
        self.last_modified = utcnow_naive()

    def before_insert(self):
        self.notes = self.event.notes


class ActorPartnerLocationPref(db.Entity):
    """score: 2 - volle Zustimmung, 1 - normale Zustimmung, 0 - volle Ablehnung.
    Präferenz-Instanz kann direkt von nächster Planungsebene übernommen werden, oder abgeändert als neue Instanz
    gespeichert werden.
    ActorPlanPeriod übernimmt automatisch von Person, AvailDay übernimmt automatisch von ActorPlanPeriod.
    Spezialfall: Wenn der Actor in einer Einrichtung 0 bei allen Partnern hat, kann er trotzdem solo eingesetzt werden,
    und die Bewertung des Plans wird nicht schlechter. Einstellungen, die grundsätzlich die Einrichtungen betreffen,
    müssen in ActorLocationPref vorgenommen werden."""
    id = PrimaryKey(UUID, auto=True)
    score = Required(float, default=1)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)

    person = Required(Person, reverse='actor_partner_location_prefs')
    partner = Required(Person, reverse='actor_partner_location_prefs__as_partner')
    location_of_work = Required(LocationOfWork)

    person_default = Optional(Person, reverse='actor_partner_location_prefs_defaults')
    actor_plan_periods_defaults = Set(ActorPlanPeriod)
    avail_days_defaults = Set(AvailDay)

    def before_update(self):
        self.last_modified = utcnow_naive()


class Flag(db.Entity):
    """category bestimmt, welcher Klasse die Flag-Instanz zugehört."""
    id = PrimaryKey(UUID, auto=True)
    category = Optional(str, nullable=True)
    name = Required(str, 30)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    project = Required(Project)
    persons = Set(Person)
    events = Set(Event)

    composite_key(name, project)

    def before_update(self):
        self.last_modified = utcnow_naive()


class Skill(db.Entity):
    """Beschreibt eine bestimmte Fähigkeit...
...welche die Person (an einem bestimmten AvailDay) beherrscht.
...welche in der Einrichtung (an einem bestimmten Event) gebraucht wird.
"""
    id = PrimaryKey(UUID, auto=True)
    name = Required(str)
    notes = Optional(str, default='')
    # level = Required(int, size=8, default=2, unsigned=True)
    # # muss in eine gesonderte Tabelle (SkillLevel) aufgelöst werden.
    # # Beherrscht den Skill...
    # # 0: nicht, 1: etwas, 2: gut, 3: sehr gut, 4: hervorragend
    persons = Set(Person)
    avail_days = Set(AvailDay)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    project = Required(Project)
    skill_groups = Set('SkillGroup')

    composite_key(name, project)

    def before_update(self):
        self.last_modified = utcnow_naive()


class SkillGroup(db.Entity):
    """Legt fest, wie viele der eingesetzten Personen den Skill beherrschen müssen."""
    id = PrimaryKey(UUID, auto=True)
    skill = Required(Skill)
    nr_actors = Optional(int, size=16)  # Anzahl der Personen die den Skill beherrschen müssen. None: alle
    location_of_work = Optional(LocationOfWork)
    events = Set(Event)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)

    def before_update(self):
        self.last_modified = utcnow_naive()


class CombinationLocationsPossible(db.Entity):
    """Verschiedene Personen können die gleiche Instanz einer Combination verwenden.
    Falls eine neue Instanz angelegt werden soll, wird zuerst überprüft, ob es schon eine Instanz mit der gleichen
    Kombination von Locations gibt. Falls ja, sollte diese Instanz verwendet werden.
    Eine neue Instanz von ActorPlanPeriod übernimmt die Combinations von Person,
    eine neue Instanz von AvailDay übernimmt die Combinations von ActorPlanPeriod."""
    id = PrimaryKey(UUID, auto=True)
    project = Required(Project)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)

    # todo: Wenn sich Zusammensetzung vom Team ändert, sollten bei Bedarf Personen aus persons entfernt werden
    #  oder Locations aus locations of Work entfernt werden, wenn team is not None:
    locations_of_work = Set(LocationOfWork)
    time_span_between = Required(datetime.timedelta)

    team = Optional(Team)
    persons = Set(Person)
    actor_plan_periods = Set(ActorPlanPeriod)
    avail_days = Set(AvailDay)

    def before_update(self):  # sourcery skip: aware-datetime-for-utc
        self.last_modified = utcnow_naive()


class ActorLocationPref(db.Entity):
    """Score 0: Person möchte keinen Einsatz in dieser Einrichtung.
    Score 1: Gerne in dieser Einrichtung.
    Score 2: bevorzugt in dieser Einrichtung."""
    id = PrimaryKey(UUID, auto=True)
    score = Required(float, default=1)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    project = Required(Project)
    person = Required(Person)
    location_of_work = Required(LocationOfWork)
    person_default = Optional(Person, reverse='actor_location_prefs_defaults')
    actor_plan_periods_defaults = Set(ActorPlanPeriod)
    avail_days_defaults = Set(AvailDay)

    def before_update(self):
        self.last_modified = utcnow_naive()


class Plan(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 50)
    notes = Optional(str, nullable=True)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    appointments = Set(Appointment)
    plan_period = Required(PlanPeriod)
    location_columns = Required(Json, default="{}")  # type -> dict[int, list[UUID]] ({weekday_nr: [Institution.id]})
    excel_export_settings = Optional('ExcelExportSettings')

    composite_key(name, plan_period)

    @property
    def team(self):
        return self.plan_period.team

    def before_insert(self):
        self.excel_export_settings = self.team.excel_export_settings
        self.notes = self.plan_period.notes

    def before_update(self):
        self.last_modified = datetime.datetime.now(datetime.timezone.utc)


class MaxFairShiftsOfApp(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    max_shifts = Required(int, size=16, default=0, unsigned=True)
    fair_shifts = Required(float, default=0)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    actor_plan_period = Required(ActorPlanPeriod)


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
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    project = Optional(Project)
    teams = Set(Team)
    plans = Set(Plan)


class EmployeeEvent(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    title = Required(str, 40)
    description = Required(str)
    start = Required(datetime.datetime)
    end = Required(datetime.datetime)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    employee_event_categories = Set('EmployeeEventCategory')
    project = Required(Project)
    teams = Set(Team)
    participants = Set(Person)
    address = Optional(Address)
    google_calendar_event_id = Optional(str)

    def before_update(self):
        self.last_modified = utcnow_naive()

    def before_insert(self):
        # create new UUID for google_calendar_event_id
        self.google_calendar_event_id = str(uuid4())


class EmployeeEventCategory(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 40, unique=True)
    description = Optional(str)
    created_at = Required(datetime.datetime, default=utcnow_naive)
    last_modified = Required(datetime.datetime, default=utcnow_naive)
    prep_delete = Optional(datetime.datetime)
    employee_events = Set(EmployeeEvent)
    project = Required(Project)

    def before_update(self):
        self.last_modified = utcnow_naive()


#  noch zu implementieren
"""class APSchedulerJob(db.Entity):
    id = PrimaryKey(int, auto=True)
    plan_period = Required(PlanPeriod)
    job = Required(bytes)"""


# todo (done): Beibehaltung von Planungen nach Löschung bzw. Statusänderungen (z.B. Änderungen von Zugehörigkeiten zu einem Team).
# todo: Beim Wechsel des Teams von Person oder LocationOfWork sammeln sich in CombinationLocationsPossible viele nicht aktuelle Combinations an. Lösung?
# todo: Das Gleiche gilt für ActorLocationPref
# todo: Das Gleiche gilt für fixed_cast in LocationOfWork und Event
# todo (done): In FrameActorPlanPeriod dürfen nur die Termine der Tage des Teams gezeigt werden, an denen die Person dem Team zugeordnet ist.
# todo (done): Skills zu Person hinzufügen
