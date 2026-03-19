"""Zentrale Eager-Loading-Optionen für db_services.

Verhindert N+1-Queries beim Laden von Plan- und verwandten Objekten,
indem alle für schemas.PlanShow.model_validate() benötigten Relationships
in einer minimalen Anzahl von Queries vorgeladen werden.

Verwendung::

    stmt = select(models.Plan).where(...).options(*plan_show_options())
    plan = session.exec(stmt).unique().one()  # .unique() ist bei joinedload Pflicht

Erwartete Reduktion: ~1000 Queries → ~15–20 Queries pro Plan.get().
"""
from sqlalchemy.orm import selectinload, joinedload

from .. import models


def plan_show_options() -> list:
    """Gibt SQLAlchemy Loader-Optionen für vollständige PlanShow-Objekte zurück.

    Abdeckt alle Relationship-Pfade, die schemas.PlanShow.model_validate()
    und die referenzierten Schema-Properties traversieren.
    .unique() auf dem Query-Result ist Pflicht (JOIN-Deduplizierung).
    """
    # ── Plan → PlanPeriod → Team → Project (→ ExcelExportSettings) ────────
    plan_period_chain = (
        joinedload(models.Plan.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
        .joinedload(models.Project.excel_export_settings)
    )

    # ── Plan → ExcelExportSettings ─────────────────────────────────────────
    excel_settings = joinedload(models.Plan.excel_export_settings)

    # ── Basis-Chain für alle Appointment-Pfade ─────────────────────────────
    appts = selectinload(models.Plan.appointments)

    # ── Event-Ketten (joinedload, da 1:1 pro Appointment) ──────────────────
    # Event → TimeOfDay → TimeOfDayEnum  (für Zeitanzeige)
    event_time_of_day = (
        appts.joinedload(models.Appointment.event)
        .joinedload(models.Event.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    # Event → LocationPlanPeriod → LocationOfWork → Address  (für Ortsanzeige)
    event_location_chain = (
        appts.joinedload(models.Appointment.event)
        .joinedload(models.Event.location_plan_period)
        .joinedload(models.LocationPlanPeriod.location_of_work)
        .joinedload(models.LocationOfWork.address)
    )
    # Event → Flags  (Collection → selectinload)
    event_flags = (
        appts.joinedload(models.Appointment.event)
        .selectinload(models.Event.flags)
    )

    # ── AvailDay-Basis-Chain ───────────────────────────────────────────────
    avd = appts.selectinload(models.Appointment.avail_days)

    # ActorPlanPeriod → Person  (für Namensanzeige im Plan)
    avd_person = (
        avd.joinedload(models.AvailDay.actor_plan_period)
        .joinedload(models.ActorPlanPeriod.person)
    )
    # ActorPlanPeriod → PlanPeriod → Team → Project
    # Benötigt für AvailDay.project Property-Kette (4 Ebenen tief)
    avd_project = (
        avd.joinedload(models.AvailDay.actor_plan_period)
        .joinedload(models.ActorPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
    )
    # TimeOfDay → TimeOfDayEnum  (für Sortierung und Anzeige)
    avd_time_of_day = (
        avd.joinedload(models.AvailDay.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    # AvailDayGroup  (für Schema-Validierung)
    avd_avail_day_group = avd.joinedload(models.AvailDay.avail_day_group)

    # time_of_days[] M:N  (Verfügbarkeits-Tageszeiten)
    avd_time_of_days = avd.selectinload(models.AvailDay.time_of_days)

    # CombinationLocationsPossible[] → LocationsOfWork[]
    avd_comb_locs = (
        avd.selectinload(models.AvailDay.combination_locations_possibles)
        .selectinload(models.CombinationLocationsPossible.locations_of_work)
    )
    # ActorLocationPref[]  (Orts-Präferenzen)
    avd_loc_prefs = avd.selectinload(models.AvailDay.actor_location_prefs_defaults)

    # ActorPartnerLocationPref[]  (Partner-Präferenzen)
    avd_partner_prefs = avd.selectinload(models.AvailDay.actor_partner_location_prefs_defaults)

    return [
        plan_period_chain,
        excel_settings,
        event_time_of_day,
        event_location_chain,
        event_flags,
        avd_person,
        avd_project,
        avd_time_of_day,
        avd_avail_day_group,
        avd_time_of_days,
        avd_comb_locs,
        avd_loc_prefs,
        avd_partner_prefs,
    ]
