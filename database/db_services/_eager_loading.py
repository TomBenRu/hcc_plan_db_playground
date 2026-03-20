"""Zentrale Eager-Loading-Optionen für db_services.

Verhindert N+1-Queries beim Laden von Plan- und verwandten Objekten,
indem alle für schemas.PlanShow.model_validate() benötigten Relationships
in einer minimalen Anzahl von Queries vorgeladen werden.

Verwendung::

    stmt = select(models.Plan).where(...).options(*plan_show_options())
    plan = session.exec(stmt).unique().one()  # .unique() ist bei joinedload Pflicht

Erwartete Reduktion: ~1000 Queries → ~15–20 Queries pro Plan.get().

    stmt = select(models.AvailDay).where(...).options(*avail_day_show_options())
    ads = session.exec(stmt).unique().all()

Erwartete Reduktion: ~2200 Queries → ~10 Queries pro get_all_from__actor_plan_period().
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


def avail_day_show_options() -> list:
    """Gibt SQLAlchemy Loader-Optionen für AvailDayShow-Objekte zurück.

    Abdeckt alle Relationship-Pfade, die schemas.AvailDayShow.model_validate()
    traversiert – einschließlich der @property-Kette AvailDay.project
    (actor_plan_period → plan_period → team → project).

    Ersetzt ~2200 Lazy-Load-Queries durch ~10 Batch-Queries pro Aufruf.
    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    # ── actor_plan_period (M:1) → person + plan_period → team → project ──────
    # Deckt: ActorPlanPeriod.person, ActorPlanPeriod.plan_period (inkl. team),
    # und AvailDay.project @property (actor_plan_period.plan_period.team.project)
    app = joinedload(models.AvailDay.actor_plan_period)
    app_person = app.joinedload(models.ActorPlanPeriod.person)
    app_project = (
        app.joinedload(models.ActorPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
    )

    # ── avail_day_group (M:1) ─────────────────────────────────────────────────
    avd_group = joinedload(models.AvailDay.avail_day_group)

    # ── time_of_day (M:1) → time_of_day_enum ─────────────────────────────────
    tod = (
        joinedload(models.AvailDay.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )

    # ── time_of_days (M:N) → time_of_day_enum ────────────────────────────────
    time_of_days = (
        selectinload(models.AvailDay.time_of_days)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )

    # ── combination_locations_possibles (M:N) → project + locations_of_work ──
    comb_locs_project = (
        selectinload(models.AvailDay.combination_locations_possibles)
        .joinedload(models.CombinationLocationsPossible.project)
    )
    comb_locs_low = (
        selectinload(models.AvailDay.combination_locations_possibles)
        .selectinload(models.CombinationLocationsPossible.locations_of_work)
    )

    # ── actor_location_prefs_defaults (M:N) → person + location_of_work + project
    loc_prefs_person = (
        selectinload(models.AvailDay.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.person)
    )
    loc_prefs_low = (
        selectinload(models.AvailDay.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.location_of_work)
    )
    loc_prefs_project = (
        selectinload(models.AvailDay.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.project)
    )

    # ── actor_partner_location_prefs_defaults (M:N) → person + partner + location_of_work
    partner_prefs_person = (
        selectinload(models.AvailDay.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.person)
    )
    partner_prefs_partner = (
        selectinload(models.AvailDay.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.partner)
    )
    partner_prefs_low = (
        selectinload(models.AvailDay.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.location_of_work)
    )

    # ── skills (M:N) ──────────────────────────────────────────────────────────
    skills = selectinload(models.AvailDay.skills)

    return [
        app_person, app_project,
        avd_group, tod,
        time_of_days,
        comb_locs_project, comb_locs_low,
        loc_prefs_person, loc_prefs_low, loc_prefs_project,
        partner_prefs_person, partner_prefs_partner, partner_prefs_low,
        skills,
    ]
