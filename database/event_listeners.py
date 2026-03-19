"""SQLAlchemy Event Listeners — Ersatz für PonyORM before_insert Hooks.

Verwendet Session-Level `before_flush` statt Mapper-Level `before_insert`,
weil M:N-Collections zu diesem Zeitpunkt sicher modifizierbar sind.

last_modified-Updates werden NICHT hier behandelt
→ erledigt durch `onupdate=func.now()` in der Column-Definition (models.py).

Registrierung: `register_listeners()` einmalig beim App-Start aufrufen.
"""

from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.orm import Session

from database.models import (
    ActorPlanPeriod,
    Appointment,
    AvailDay,
    EmployeeEvent,
    Event,
    EventGroup,
    ExcelExportSettings,
    LocationOfWork,
    LocationPlanPeriod,
    Person,
    Plan,
    Project,
    Team,
)


class InsertValidationError(Exception):
    """Wird bei fehlgeschlagener Validierung in before_insert-Logik geworfen."""


# ═══════════════════════════════════════════════════════════════════════════════
# Registrierung
# ═══════════════════════════════════════════════════════════════════════════════


def register_listeners() -> None:
    """Registriert den zentralen before_flush Handler. Einmalig beim App-Start aufrufen."""
    event.listen(Session, "before_flush", _before_flush_handler)


# ═══════════════════════════════════════════════════════════════════════════════
# Zentraler Handler
# ═══════════════════════════════════════════════════════════════════════════════


def _before_flush_handler(session: Session, _flush_context, _instances) -> None:
    """Iteriert über alle neuen Objekte und ruft den passenden Insert-Handler auf."""
    for obj in list(session.new):
        if isinstance(obj, Project):
            _on_insert_project(session, obj)
        elif isinstance(obj, Person):
            _on_insert_person(obj)
        elif isinstance(obj, Team):
            _on_insert_team(obj)
        elif isinstance(obj, LocationOfWork):
            _on_insert_location_of_work(obj)
        elif isinstance(obj, ActorPlanPeriod):
            _on_insert_actor_plan_period(obj)
        elif isinstance(obj, LocationPlanPeriod):
            _on_insert_location_plan_period(obj)
        elif isinstance(obj, AvailDay):
            _on_insert_avail_day(obj)
        elif isinstance(obj, Event):
            _on_insert_event(obj)
        elif isinstance(obj, EventGroup):
            _on_insert_event_group(obj)
        elif isinstance(obj, Appointment):
            _on_insert_appointment(obj)
        elif isinstance(obj, Plan):
            _on_insert_plan(obj)
        elif isinstance(obj, EmployeeEvent):
            _on_insert_employee_event(obj)


# ═══════════════════════════════════════════════════════════════════════════════
# Hilfsfunktion
# ═══════════════════════════════════════════════════════════════════════════════


def _copy_m2m(target_collection: list, source_collection: list) -> None:
    """Kopiert alle Elemente aus source in target, ohne Duplikate."""
    existing = set(id(item) for item in target_collection)
    for item in source_collection:
        if id(item) not in existing:
            target_collection.append(item)


# ═══════════════════════════════════════════════════════════════════════════════
# Insert-Handler (1 pro Entity mit before_insert-Logik)
# ═══════════════════════════════════════════════════════════════════════════════


# ── Project ──────────────────────────────────────────────────────────────────
# PonyORM: self.excel_export_settings = ExcelExportSettings()

def _on_insert_project(session: Session, project: Project) -> None:
    if project.excel_export_settings is None:
        settings = ExcelExportSettings()
        session.add(settings)
        project.excel_export_settings = settings


# ── Person ───────────────────────────────────────────────────────────────────
# PonyORM:
#   self.time_of_days.add(self.project.time_of_days)
#   self.time_of_day_standards.add(self.project.time_of_day_standards)
#   if self.team_actor_assigns → combination_locations_possibles vom Team

def _on_insert_person(person: Person) -> None:
    if person.project:
        _copy_m2m(person.time_of_days, person.project.time_of_days)
        _copy_m2m(person.time_of_day_standards, person.project.time_of_day_standards)

    if person.team_actor_assigns:
        latest_taa = max(person.team_actor_assigns, key=lambda x: x.start)
        if latest_taa.end is None and latest_taa.team:
            _copy_m2m(
                person.combination_locations_possibles,
                latest_taa.team.combination_locations_possibles,
            )


# ── Team ─────────────────────────────────────────────────────────────────────
# PonyORM: self.excel_export_settings = self.project.excel_export_settings

def _on_insert_team(team: Team) -> None:
    if team.project and team.excel_export_settings is None:
        team.excel_export_settings = team.project.excel_export_settings


# ── LocationOfWork ───────────────────────────────────────────────────────────
# PonyORM:
#   self.time_of_days.add(self.project.time_of_days)
#   self.time_of_day_standards.add(self.project.time_of_day_standards)

def _on_insert_location_of_work(loc: LocationOfWork) -> None:
    if loc.project:
        _copy_m2m(loc.time_of_days, loc.project.time_of_days)
        _copy_m2m(loc.time_of_day_standards, loc.project.time_of_day_standards)


# ── ActorPlanPeriod ──────────────────────────────────────────────────────────
# PonyORM:
#   self.combination_locations_possibles.add(self.person.combination_locations_possibles)
#   self.actor_partner_location_prefs_defaults.add(self.person.actor_partner_location_prefs_defaults)
#   self.time_of_days.add(self.person.time_of_days)
#   self.time_of_day_standards.add(self.person.time_of_day_standards)
#   self.actor_location_prefs_defaults.add(self.person.actor_location_prefs_defaults)

def _on_insert_actor_plan_period(app: ActorPlanPeriod) -> None:
    if app.person:
        _copy_m2m(app.combination_locations_possibles, app.person.combination_locations_possibles)
        _copy_m2m(app.actor_partner_location_prefs_defaults, app.person.actor_partner_location_prefs_defaults)
        _copy_m2m(app.time_of_days, app.person.time_of_days)
        _copy_m2m(app.time_of_day_standards, app.person.time_of_day_standards)
        _copy_m2m(app.actor_location_prefs_defaults, app.person.actor_location_prefs_defaults)


# ── LocationPlanPeriod ───────────────────────────────────────────────────────
# PonyORM:
#   self.nr_actors = self.location_of_work.nr_actors
#   self.time_of_days.add(self.location_of_work.time_of_days)
#   self.time_of_day_standards.add(self.location_of_work.time_of_day_standards)
#   self.fixed_cast = self.location_of_work.fixed_cast
#   self.fixed_cast_only_if_available = self.location_of_work.fixed_cast_only_if_available

def _on_insert_location_plan_period(lpp: LocationPlanPeriod) -> None:
    if lpp.location_of_work:
        lpp.nr_actors = lpp.location_of_work.nr_actors
        lpp.fixed_cast = lpp.location_of_work.fixed_cast
        lpp.fixed_cast_only_if_available = lpp.location_of_work.fixed_cast_only_if_available
        _copy_m2m(lpp.time_of_days, lpp.location_of_work.time_of_days)
        _copy_m2m(lpp.time_of_day_standards, lpp.location_of_work.time_of_day_standards)


# ── AvailDay ─────────────────────────────────────────────────────────────────
# PonyORM:
#   self.combination_locations_possibles.add(self.actor_plan_period.combination_locations_possibles)
#   self.time_of_days.add(self.actor_plan_period.time_of_days)
#   self.actor_partner_location_prefs_defaults.add(self.actor_plan_period.actor_partner_location_prefs_defaults)
#   self.actor_location_prefs_defaults.add(self.actor_plan_period.actor_location_prefs_defaults)
#   self.skills.add(self.actor_plan_period.person.skills)

def _on_insert_avail_day(ad: AvailDay) -> None:
    if ad.actor_plan_period:
        _copy_m2m(ad.combination_locations_possibles, ad.actor_plan_period.combination_locations_possibles)
        _copy_m2m(ad.time_of_days, ad.actor_plan_period.time_of_days)
        _copy_m2m(ad.actor_partner_location_prefs_defaults, ad.actor_plan_period.actor_partner_location_prefs_defaults)
        _copy_m2m(ad.actor_location_prefs_defaults, ad.actor_plan_period.actor_location_prefs_defaults)

        if ad.actor_plan_period.person:
            _copy_m2m(ad.skills, ad.actor_plan_period.person.skills)


# ── Event ────────────────────────────────────────────────────────────────────
# PonyORM:
#   for t_o_d in self.location_plan_period.time_of_days:
#       if not t_o_d.prep_delete:
#           self.time_of_days.add(t_o_d)

def _on_insert_event(event_obj: Event) -> None:
    if event_obj.location_plan_period:
        active_tods = [
            tod for tod in event_obj.location_plan_period.time_of_days
            if tod.prep_delete is None
        ]
        _copy_m2m(event_obj.time_of_days, active_tods)


# ── EventGroup ───────────────────────────────────────────────────────────────
# PonyORM: Validierung — genau eins von location_plan_period oder event_group muss gesetzt sein.

def _on_insert_event_group(eg: EventGroup) -> None:
    has_lpp = eg.location_plan_period_id is not None or eg.location_plan_period is not None
    has_parent = eg.event_group_id is not None or eg.event_group is not None

    if not (has_lpp ^ has_parent):
        raise InsertValidationError(
            "Eine EventGroup muss entweder genau einer LocationPlanPeriod "
            "oder genau einer übergeordneten EventGroup zugeordnet sein."
        )


# ── Appointment ──────────────────────────────────────────────────────────────
# PonyORM: self.notes = self.event.notes

def _on_insert_appointment(appointment: Appointment) -> None:
    if appointment.event and appointment.notes is None:
        appointment.notes = appointment.event.notes


# ── Plan ─────────────────────────────────────────────────────────────────────
# PonyORM:
#   self.excel_export_settings = self.team.excel_export_settings  (team ist @property → plan_period.team)
#   self.notes = self.plan_period.notes

def _on_insert_plan(plan: Plan) -> None:
    if plan.plan_period:
        if plan.notes is None:
            plan.notes = plan.plan_period.notes

        team = plan.plan_period.team
        if team and plan.excel_export_settings is None:
            plan.excel_export_settings = team.excel_export_settings


# ── EmployeeEvent ────────────────────────────────────────────────────────────
# PonyORM: self.google_calendar_event_id = str(uuid4())

def _on_insert_employee_event(ee: EmployeeEvent) -> None:
    if ee.google_calendar_event_id is None:
        ee.google_calendar_event_id = str(uuid4())
