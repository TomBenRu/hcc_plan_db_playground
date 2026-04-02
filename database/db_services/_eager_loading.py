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


def team_show_options() -> list:
    """Loader-Optionen für vollständige TeamShow-Objekte.

    Deckt alle Relationship-Pfade ab, die schemas.TeamShow.model_validate()
    traversiert — inkl. team_actor_assigns (→ person), team_location_assigns
    (→ location_of_work), plan_periods (Basis) und combination_locations_possibles.

    Ersetzt ~50+ Lazy-Load-Queries durch ~10 Batch-Queries.
    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    # ── Team-Basis (M:1) → project + dispatcher + excel ──────────────────────
    project = joinedload(models.Team.project)
    dispatcher = joinedload(models.Team.dispatcher)
    excel = joinedload(models.Team.excel_export_settings)

    # ── team_actor_assigns (1:N) → person (+ team → identity map) ────────────
    taa_person = (
        selectinload(models.Team.team_actor_assigns)
        .joinedload(models.TeamActorAssign.person)
    )
    # TeamActorAssign.team → back-ref, identity map; benötigt aber Team-Basis:
    # project, dispatcher — bereits geladen über den Haupt-Team-Join

    # ── team_location_assigns (1:N) → location_of_work ───────────────────────
    tla_low = (
        selectinload(models.Team.team_location_assigns)
        .joinedload(models.TeamLocationAssign.location_of_work)
    )

    # ── plan_periods (1:N) — Basis-PlanPeriod-Schema (team → identity map) ───
    plan_periods = selectinload(models.Team.plan_periods)

    # ── combination_locations_possibles (M:N) → project + locations_of_work ──
    clp_project = (
        selectinload(models.Team.combination_locations_possibles)
        .joinedload(models.CombinationLocationsPossible.project)
    )
    clp_low = (
        selectinload(models.Team.combination_locations_possibles)
        .selectinload(models.CombinationLocationsPossible.locations_of_work)
    )

    return [
        project, dispatcher, excel,
        taa_person, tla_low,
        plan_periods,
        clp_project, clp_low,
    ]


def person_show_options() -> list:
    """Loader-Optionen für vollständige PersonShow-Objekte.

    Deckt alle Relationship-Pfade ab, die schemas.PersonShow.model_validate()
    traversiert — inkl. team_actor_assigns, time_of_days, skills,
    combination_locations_possibles, actor_location_prefs und flags.

    Ersetzt ~100+ Lazy-Load-Queries durch ~15 Batch-Queries.
    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    # ── Person-Basis (M:1) → project + address ───────────────────────────────
    project = joinedload(models.Person.project)
    address = joinedload(models.Person.address)

    # ── team_actor_assigns (1:N) → team → project + dispatcher + excel ────────
    taa_team_project = (
        selectinload(models.Person.team_actor_assigns)
        .joinedload(models.TeamActorAssign.team)
        .joinedload(models.Team.project)
    )
    taa_team_dispatcher = (
        selectinload(models.Person.team_actor_assigns)
        .joinedload(models.TeamActorAssign.team)
        .joinedload(models.Team.dispatcher)
    )
    taa_team_excel = (
        selectinload(models.Person.team_actor_assigns)
        .joinedload(models.TeamActorAssign.team)
        .joinedload(models.Team.excel_export_settings)
    )

    # ── teams_of_dispatcher (M:N) → project + dispatcher + excel ─────────────
    tod_project = (
        selectinload(models.Person.teams_of_dispatcher)
        .joinedload(models.Team.project)
    )
    tod_dispatcher = (
        selectinload(models.Person.teams_of_dispatcher)
        .joinedload(models.Team.dispatcher)
    )

    # ── time_of_day_standards + time_of_days (M:N) → time_of_day_enum ─────────
    tod_standards = (
        selectinload(models.Person.time_of_day_standards)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    time_of_days = (
        selectinload(models.Person.time_of_days)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )

    # ── skills (M:N) ──────────────────────────────────────────────────────────
    skills = selectinload(models.Person.skills)

    # ── combination_locations_possibles (M:N) → project + locations_of_work ──
    clp_project = (
        selectinload(models.Person.combination_locations_possibles)
        .joinedload(models.CombinationLocationsPossible.project)
    )
    clp_low = (
        selectinload(models.Person.combination_locations_possibles)
        .selectinload(models.CombinationLocationsPossible.locations_of_work)
    )

    # ── actor_location_prefs_defaults (M:N) → person + location_of_work + project
    loc_prefs_person = (
        selectinload(models.Person.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.person)
    )
    loc_prefs_low = (
        selectinload(models.Person.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.location_of_work)
    )
    loc_prefs_project = (
        selectinload(models.Person.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.project)
    )

    # ── actor_partner_location_prefs_defaults (M:N) → person + partner + low ─
    partner_person = (
        selectinload(models.Person.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.person)
    )
    partner_partner = (
        selectinload(models.Person.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.partner)
    )
    partner_low = (
        selectinload(models.Person.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.location_of_work)
    )

    # ── flags (M:N) ───────────────────────────────────────────────────────────
    flags = selectinload(models.Person.flags)

    return [
        project, address,
        taa_team_project, taa_team_dispatcher, taa_team_excel,
        tod_project, tod_dispatcher,
        tod_standards, time_of_days,
        skills,
        clp_project, clp_low,
        loc_prefs_person, loc_prefs_low, loc_prefs_project,
        partner_person, partner_partner, partner_low,
        flags,
    ]


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


def actor_plan_period_show_options() -> list:
    """Loader-Optionen für vollständige ActorPlanPeriodShow-Objekte.

    Deckt alle Relationship-Pfade ab, die schemas.ActorPlanPeriodShow.model_validate()
    traversiert — inkl. @property-Ketten team und project
    (plan_period → team → project).

    Ersetzt hunderte Lazy-Load-Queries durch ~20 Batch-Queries.
    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    # ── plan_period (M:1) → team → project + dispatcher + excel ──────────────
    pp_team_project = (
        joinedload(models.ActorPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
    )
    pp_team_dispatcher = (
        joinedload(models.ActorPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.dispatcher)
    )
    pp_team_excel = (
        joinedload(models.ActorPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.excel_export_settings)
    )

    # ── person (M:1) ──────────────────────────────────────────────────────────
    person = joinedload(models.ActorPlanPeriod.person)

    # ── time_of_days (M:N) → time_of_day_enum ────────────────────────────────
    time_of_days = (
        selectinload(models.ActorPlanPeriod.time_of_days)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    tod_standards = (
        selectinload(models.ActorPlanPeriod.time_of_day_standards)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )

    # ── combination_locations_possibles (M:N) → locations_of_work ────────────
    comb_locs = (
        selectinload(models.ActorPlanPeriod.combination_locations_possibles)
        .selectinload(models.CombinationLocationsPossible.locations_of_work)
    )

    # ── actor_location_prefs_defaults (M:N) → person + location_of_work + project
    loc_prefs_person = (
        selectinload(models.ActorPlanPeriod.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.person)
    )
    loc_prefs_low = (
        selectinload(models.ActorPlanPeriod.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.location_of_work)
    )
    loc_prefs_project = (
        selectinload(models.ActorPlanPeriod.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.project)
    )

    # ── actor_partner_location_prefs_defaults (M:N) → person + partner + low ─
    partner_person = (
        selectinload(models.ActorPlanPeriod.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.person)
    )
    partner_partner = (
        selectinload(models.ActorPlanPeriod.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.partner)
    )
    partner_low = (
        selectinload(models.ActorPlanPeriod.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.location_of_work)
    )

    # ── avail_days (1:N) — Basis-AvailDay-Schema ──────────────────────────────
    avd = selectinload(models.ActorPlanPeriod.avail_days)

    avd_group = avd.joinedload(models.AvailDay.avail_day_group)
    avd_tod = (
        avd.joinedload(models.AvailDay.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    avd_time_of_days = (
        avd.selectinload(models.AvailDay.time_of_days)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    avd_comb_locs_project = (
        avd.selectinload(models.AvailDay.combination_locations_possibles)
        .joinedload(models.CombinationLocationsPossible.project)
    )
    avd_comb_locs_low = (
        avd.selectinload(models.AvailDay.combination_locations_possibles)
        .selectinload(models.CombinationLocationsPossible.locations_of_work)
    )
    avd_loc_prefs_person = (
        avd.selectinload(models.AvailDay.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.person)
    )
    avd_loc_prefs_low = (
        avd.selectinload(models.AvailDay.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.location_of_work)
    )
    avd_loc_prefs_project = (
        avd.selectinload(models.AvailDay.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.project)
    )
    avd_partner_person = (
        avd.selectinload(models.AvailDay.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.person)
    )
    avd_partner_partner = (
        avd.selectinload(models.AvailDay.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.partner)
    )
    avd_partner_low = (
        avd.selectinload(models.AvailDay.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.location_of_work)
    )

    return [
        pp_team_project, pp_team_dispatcher, pp_team_excel,
        person, time_of_days, tod_standards, comb_locs,
        loc_prefs_person, loc_prefs_low, loc_prefs_project,
        partner_person, partner_partner, partner_low,
        avd_group, avd_tod, avd_time_of_days,
        avd_comb_locs_project, avd_comb_locs_low,
        avd_loc_prefs_person, avd_loc_prefs_low, avd_loc_prefs_project,
        avd_partner_person, avd_partner_partner, avd_partner_low,
    ]


def actor_plan_period_mask_options() -> list:
    """Loader-Optionen für ActorPlanPeriodForMask — reduzierte Ketten für Masken-Anzeige.

    Entfernt vs. actor_plan_period_show_options():
    - avd_group, avd_tod, avd_time_of_days (nicht in Button-Checks genutzt)
    - avd_comb_locs_project (project nicht benötigt)
    - avd_loc_prefs_person, avd_loc_prefs_project (nicht in Button-Checks genutzt)
    - avd_partner_person (nur .partner.id/.location_of_work.id benötigt)
    - loc_prefs_person, loc_prefs_project, partner_person (ActorPlanPeriod-Ebene)

    Beibehaltene AvailDay-Ketten:
    - avd (Basis)
    - avd_comb_locs (inkl. locations_of_work — für DlgCombLocPossibleEditList)
    - avd_loc_prefs_low (location_of_work.id für ButtonLocationPreferences)
    - avd_partner_partner (partner.id für ButtonPartnerPreferences)
    - avd_partner_low (location_of_work.id für ButtonPartnerPreferences)
    """
    # ── plan_period (M:1) → team → project + dispatcher + excel ──────────────
    pp_team_project = (
        joinedload(models.ActorPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
    )
    pp_team_dispatcher = (
        joinedload(models.ActorPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.dispatcher)
    )
    pp_team_excel = (
        joinedload(models.ActorPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.excel_export_settings)
    )

    # ── person (M:1) ──────────────────────────────────────────────────────────
    person = joinedload(models.ActorPlanPeriod.person)

    # ── time_of_days (M:N) → time_of_day_enum ────────────────────────────────
    time_of_days = (
        selectinload(models.ActorPlanPeriod.time_of_days)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    tod_standards = (
        selectinload(models.ActorPlanPeriod.time_of_day_standards)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )

    # ── combination_locations_possibles: voll (Dialog-Anzeige braucht locations_of_work)
    comb_locs = (
        selectinload(models.ActorPlanPeriod.combination_locations_possibles)
        .selectinload(models.CombinationLocationsPossible.locations_of_work)
    )

    # ── loc_prefs: nur location_of_work (ohne person, ohne project) ──────────
    loc_prefs_low = (
        selectinload(models.ActorPlanPeriod.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.location_of_work)
    )

    # ── partner_prefs: nur partner + location_of_work (ohne person) ──────────
    partner_partner = (
        selectinload(models.ActorPlanPeriod.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.partner)
    )
    partner_low = (
        selectinload(models.ActorPlanPeriod.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.location_of_work)
    )

    # ── avail_days: nur die für Masken-Anzeige + Button-Checks nötigen Ketten ─
    avd = selectinload(models.ActorPlanPeriod.avail_days)

    # time_of_day: benötigt für get_avail_days() und API-Sync
    avd_tod = (
        avd.joinedload(models.AvailDay.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )

    # combination_locations_possibles: inkl. locations_of_work (für Dialog-Anzeige)
    avd_comb_locs = (
        avd.selectinload(models.AvailDay.combination_locations_possibles)
        .selectinload(models.CombinationLocationsPossible.locations_of_work)
    )

    # actor_location_prefs_defaults: nur location_of_work (ohne person/project)
    avd_loc_prefs_low = (
        avd.selectinload(models.AvailDay.actor_location_prefs_defaults)
        .joinedload(models.ActorLocationPref.location_of_work)
    )

    # actor_partner_location_prefs_defaults: nur partner + location_of_work (ohne person)
    avd_partner_partner = (
        avd.selectinload(models.AvailDay.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.partner)
    )
    avd_partner_low = (
        avd.selectinload(models.AvailDay.actor_partner_location_prefs_defaults)
        .joinedload(models.ActorPartnerLocationPref.location_of_work)
    )

    return [
        pp_team_project, pp_team_dispatcher, pp_team_excel,
        person, time_of_days, tod_standards, comb_locs,
        loc_prefs_low,
        partner_partner, partner_low,
        avd_tod,
        avd_comb_locs,
        avd_loc_prefs_low,
        avd_partner_partner, avd_partner_low,
    ]


def plan_period_show_options() -> list:
    """Loader-Optionen für vollständige PlanPeriodShow-Objekte.

    Deckt alle Relationship-Pfade ab, die schemas.PlanPeriodShow.model_validate()
    traversiert — inkl. actor_plan_periods (Basis), location_plan_periods (Basis),
    cast_groups (Basis) und @property project (team → project).

    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    # ── team (M:1) → project + dispatcher + excel ─────────────────────────────
    # Deckt: PlanPeriodShow.team und PlanPeriodShow.project (@property team.project)
    team_project = (
        joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
    )
    team_dispatcher = (
        joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.dispatcher)
    )
    team_excel = (
        joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.excel_export_settings)
    )
    # ── team.team_actor_assigns (1:N) → person ────────────────────────────────
    # Für PlanPeriodShow.team = TeamWithAssigns (Planungsmasken)
    team_taa_person = (
        joinedload(models.PlanPeriod.team)
        .selectinload(models.Team.team_actor_assigns)
        .joinedload(models.TeamActorAssign.person)
    )
    # ── team.team_location_assigns (1:N) → location_of_work ───────────────────
    team_tla_low = (
        joinedload(models.PlanPeriod.team)
        .selectinload(models.Team.team_location_assigns)
        .joinedload(models.TeamLocationAssign.location_of_work)
    )

    # ── actor_plan_periods (1:N) — Basis-ActorPlanPeriod-Schema ──────────────
    # ActorPlanPeriod-Basis braucht: plan_period (→ identity map) + person
    app_person = (
        selectinload(models.PlanPeriod.actor_plan_periods)
        .joinedload(models.ActorPlanPeriod.person)
    )

    # ── location_plan_periods (1:N) — Basis-LocationPlanPeriod-Schema ─────────
    # LocationPlanPeriod-Basis braucht: plan_period (→ identity map) + location_of_work + address + project
    lpp_low = (
        selectinload(models.PlanPeriod.location_plan_periods)
        .joinedload(models.LocationPlanPeriod.location_of_work)
    )
    lpp_low_addr = (
        selectinload(models.PlanPeriod.location_plan_periods)
        .joinedload(models.LocationPlanPeriod.location_of_work)
        .joinedload(models.LocationOfWork.address)
    )
    lpp_low_project = (
        selectinload(models.PlanPeriod.location_plan_periods)
        .joinedload(models.LocationPlanPeriod.location_of_work)
        .joinedload(models.LocationOfWork.project)
    )

    # ── cast_groups (1:N) — Basis-CastGroup-Schema ────────────────────────────
    # CastGroup-Basis braucht: plan_period (→ identity map) + event (optional)
    cg = selectinload(models.PlanPeriod.cast_groups)

    # event → time_of_day → time_of_day_enum
    cg_ev_tod = (
        cg.joinedload(models.CastGroup.event)
        .joinedload(models.Event.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    # event → flags (M:N)
    cg_ev_flags = (
        cg.joinedload(models.CastGroup.event)
        .selectinload(models.Event.flags)
    )
    # event → location_plan_period → location_of_work (plan_period → identity map)
    cg_ev_lpp_low = (
        cg.joinedload(models.CastGroup.event)
        .joinedload(models.Event.location_plan_period)
        .joinedload(models.LocationPlanPeriod.location_of_work)
    )

    return [
        team_project, team_dispatcher, team_excel,
        team_taa_person, team_tla_low,
        app_person,
        lpp_low, lpp_low_addr, lpp_low_project,
        cg_ev_tod, cg_ev_flags, cg_ev_lpp_low,
    ]


def cast_group_show_options() -> list:
    """Gibt SQLAlchemy Loader-Optionen für CastGroupShow-Objekte zurück.

    Abdeckt alle Relationship-Pfade, die schemas.CastGroupShow.model_validate()
    traversiert:
    - plan_period → team → project + dispatcher
    - event → location_plan_period → plan_period → team, location_of_work → address + project
    - event → time_of_day → time_of_day_enum
    - event → flags
    - parent_groups + child_groups → plan_period → team
    - cast_rule → project

    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    # ── plan_period (M:1) → team → project + dispatcher ──────────────────────
    pp_team = (
        joinedload(models.CastGroup.plan_period)
        .joinedload(models.PlanPeriod.team)
    )
    pp_team_project = (
        joinedload(models.CastGroup.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
    )
    pp_team_dispatcher = (
        joinedload(models.CastGroup.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.dispatcher)
    )

    # ── event (1:1, optional) ─────────────────────────────────────────────────
    ev = joinedload(models.CastGroup.event)

    # event → location_plan_period → plan_period → team → project
    ev_lpp_pp_team = (
        ev.joinedload(models.Event.location_plan_period)
        .joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
    )
    # event → location_plan_period → location_of_work → address + project
    ev_lpp_low_address = (
        ev.joinedload(models.Event.location_plan_period)
        .joinedload(models.LocationPlanPeriod.location_of_work)
        .joinedload(models.LocationOfWork.address)
    )
    ev_lpp_low_project = (
        ev.joinedload(models.Event.location_plan_period)
        .joinedload(models.LocationPlanPeriod.location_of_work)
        .joinedload(models.LocationOfWork.project)
    )
    # event → time_of_day → time_of_day_enum
    ev_tod = (
        ev.joinedload(models.Event.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    # event → flags (M:N)
    ev_flags = ev.selectinload(models.Event.flags)

    # ── parent_groups + child_groups (M:N) → plan_period → team ──────────────
    parent_pp_team = (
        selectinload(models.CastGroup.parent_groups)
        .joinedload(models.CastGroup.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
    )
    child_pp_team = (
        selectinload(models.CastGroup.child_groups)
        .joinedload(models.CastGroup.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
    )

    # ── cast_rule (M:1, optional) → project ───────────────────────────────────
    cast_rule_project = (
        joinedload(models.CastGroup.cast_rule)
        .joinedload(models.CastRule.project)
    )

    return [
        pp_team, pp_team_project, pp_team_dispatcher,
        ev_lpp_pp_team, ev_lpp_low_address, ev_lpp_low_project,
        ev_tod, ev_flags,
        parent_pp_team, child_pp_team,
        cast_rule_project,
    ]


def location_plan_period_show_options() -> list:
    """Loader-Optionen für vollständige LocationPlanPeriodShow-Objekte.

    Deckt alle Relationship-Pfade ab, die schemas.LocationPlanPeriodShow.model_validate()
    traversiert — inkl. @property-Ketten team (plan_period.team) und project
    (plan_period.team.project), time_of_days/standards und Events mit Basis-Daten.

    Ersetzt N+1-Lazy-Load-Queries durch ~8 Batch-Queries.
    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    # ── plan_period (M:1) → team → project ──────────────────────────────────
    # Deckt: LocationPlanPeriod.team (@property) + .project (@property)
    pp_team_project = (
        joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
    )

    # ── location_of_work (M:1) + address + project ───────────────────────────
    low_address = (
        joinedload(models.LocationPlanPeriod.location_of_work)
        .joinedload(models.LocationOfWork.address)
    )
    low_project = (
        joinedload(models.LocationPlanPeriod.location_of_work)
        .joinedload(models.LocationOfWork.project)
    )

    # ── time_of_days + time_of_day_standards (M:N) → time_of_day_enum ────────
    time_of_days = (
        selectinload(models.LocationPlanPeriod.time_of_days)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    tod_standards = (
        selectinload(models.LocationPlanPeriod.time_of_day_standards)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )

    # ── events (1:N) → time_of_day + flags ───────────────────────────────────
    # Basis-Event-Schema braucht: time_of_day (für .time_of_day_enum), flags
    ev_tod = (
        selectinload(models.LocationPlanPeriod.events)
        .joinedload(models.Event.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    ev_flags = (
        selectinload(models.LocationPlanPeriod.events)
        .selectinload(models.Event.flags)
    )

    return [
        pp_team_project,
        low_address, low_project,
        time_of_days, tod_standards,
        ev_tod, ev_flags,
    ]


def location_plan_period_for_dialog_options() -> list:
    """Minimale Loader-Optionen für LocationPlanPeriodForDialog.model_validate().

    Lädt nur plan_period → team — kein location_of_work, time_of_days, events, project.
    Wird in get_for_dialog() verwendet (reload_object_with_groups im EventGroup-Dialog).
    """
    return [
        joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
    ]


def location_mask_lpp_options() -> list:
    """Loader-Optionen für Standort-Masken-Startup (ohne events).

    Wie location_plan_period_show_options(), aber ohne ev_tod und ev_flags.
    Lädt team vollständig (project, dispatcher, excel) — nötig für schemas.Team-Validierung
    via LocationPlanPeriod.team @property (→ plan_period.team).
    Integriert TeamLocationAssigns via selectinload-Kette (ersetzt separaten Q2-Query).
    Nach dem Aufruf sind TLAs aus lpps[0].plan_period.team.team_location_assigns abrufbar.
    """
    # plan_period → team (vollständig für schemas.Team)
    pp_team_project = (
        joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.project)
    )
    pp_team_dispatcher = (
        joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.dispatcher)
    )
    pp_team_excel = (
        joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .joinedload(models.Team.excel_export_settings)
    )

    # plan_period → team → team_location_assigns (nur start/end/location_of_work_id)
    # selectinload generiert 1 SQL WHERE team_id IN (...) statt separatem Q2-Query.
    # Kein joinedload auf location_of_work nötig — TeamLocationAssignForMask nutzt FK direkt.
    pp_team_tlas = (
        joinedload(models.LocationPlanPeriod.plan_period)
        .joinedload(models.PlanPeriod.team)
        .selectinload(models.Team.team_location_assigns)
    )

    # location_of_work + address + project (für schemas.LocationOfWork)
    low_address = (
        joinedload(models.LocationPlanPeriod.location_of_work)
        .joinedload(models.LocationOfWork.address)
    )
    low_project = (
        joinedload(models.LocationPlanPeriod.location_of_work)
        .joinedload(models.LocationOfWork.project)
    )

    # time_of_days + standards → time_of_day_enum
    time_of_days = (
        selectinload(models.LocationPlanPeriod.time_of_days)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    tod_standards = (
        selectinload(models.LocationPlanPeriod.time_of_day_standards)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )

    return [
        pp_team_project, pp_team_dispatcher, pp_team_excel,
        pp_team_tlas,
        low_address, low_project,
        time_of_days, tod_standards,
    ]


def location_of_work_show_options() -> list:
    """Loader-Optionen für vollständige LocationOfWorkShow-Objekte.

    Deckt alle Relationship-Pfade ab, die schemas.LocationOfWorkShow.model_validate()
    traversiert — inkl. team_location_assigns (→ team → project/dispatcher/excel),
    time_of_days/standards (→ time_of_day_enum + project), skill_groups (→ skill)
    sowie address und project der Location selbst.

    Ersetzt ~50+ Lazy-Load-Queries pro Objekt durch ~10 Batch-Queries.
    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    # ── LocationOfWork-Basis (M:1) → address + project ───────────────────────
    address = joinedload(models.LocationOfWork.address)
    project = joinedload(models.LocationOfWork.project)

    # ── team_location_assigns (1:N) → team → project + dispatcher + excel ────
    tla_team_project = (
        selectinload(models.LocationOfWork.team_location_assigns)
        .joinedload(models.TeamLocationAssign.team)
        .joinedload(models.Team.project)
    )
    tla_team_dispatcher = (
        selectinload(models.LocationOfWork.team_location_assigns)
        .joinedload(models.TeamLocationAssign.team)
        .joinedload(models.Team.dispatcher)
    )
    tla_team_excel = (
        selectinload(models.LocationOfWork.team_location_assigns)
        .joinedload(models.TeamLocationAssign.team)
        .joinedload(models.Team.excel_export_settings)
    )

    # ── time_of_days (M:N) → time_of_day_enum + project ──────────────────────
    tod_enum = (
        selectinload(models.LocationOfWork.time_of_days)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    tod_project = (
        selectinload(models.LocationOfWork.time_of_days)
        .joinedload(models.TimeOfDay.project)
    )

    # ── time_of_day_standards (M:N) → time_of_day_enum + project ─────────────
    tod_std_enum = (
        selectinload(models.LocationOfWork.time_of_day_standards)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    tod_std_project = (
        selectinload(models.LocationOfWork.time_of_day_standards)
        .joinedload(models.TimeOfDay.project)
    )

    # ── skill_groups (1:N) → skill ────────────────────────────────────────────
    skill_groups_skill = (
        selectinload(models.LocationOfWork.skill_groups)
        .joinedload(models.SkillGroup.skill)
    )

    return [
        address, project,
        tla_team_project, tla_team_dispatcher, tla_team_excel,
        tod_enum, tod_project,
        tod_std_enum, tod_std_project,
        skill_groups_skill,
    ]


def project_show_options() -> list:
    """Loader-Optionen für vollständige ProjectShow-Objekte.

    Deckt alle Relationship-Pfade ab, die schemas.ProjectShow.model_validate()
    traversiert — inkl. teams (mit vollständiger team_show_options()-Kette),
    persons (→ address), time_of_days/standards/enums und einfacher Collections.

    Ersetzt mehrere hundert Lazy-Load-Queries durch ~20 Batch-Queries.
    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    # ── Project-Basis (M:1) → excel_export_settings ──────────────────────────
    excel = joinedload(models.Project.excel_export_settings)

    # ── admin → Person (M:1, optional) → address ─────────────────────────────
    admin = joinedload(models.Project.admin)
    admin_address = admin.joinedload(models.Person.address)

    # ── teams (1:N) — vollständige team_show_options()-Kette ─────────────────
    teams = selectinload(models.Project.teams)
    teams_dispatcher = teams.joinedload(models.Team.dispatcher)
    teams_excel = teams.joinedload(models.Team.excel_export_settings)
    teams_taa_person = (
        teams.selectinload(models.Team.team_actor_assigns)
        .joinedload(models.TeamActorAssign.person)
    )
    teams_tla_low = (
        teams.selectinload(models.Team.team_location_assigns)
        .joinedload(models.TeamLocationAssign.location_of_work)
    )
    teams_plan_periods = teams.selectinload(models.Team.plan_periods)
    teams_clp_project = (
        teams.selectinload(models.Team.combination_locations_possibles)
        .joinedload(models.CombinationLocationsPossible.project)
    )
    teams_clp_low = (
        teams.selectinload(models.Team.combination_locations_possibles)
        .selectinload(models.CombinationLocationsPossible.locations_of_work)
    )

    # ── persons (1:N, FK Person.project_id) → address ────────────────────────
    persons = selectinload(models.Project.persons)
    persons_address = persons.joinedload(models.Person.address)

    # ── time_of_days (M:N via FK project_defaults_id) → time_of_day_enum ─────
    time_of_days = selectinload(models.Project.time_of_days)
    tod_enum = time_of_days.joinedload(models.TimeOfDay.time_of_day_enum)

    # ── time_of_day_standards (M:N via FK project_standard_id) → enum ────────
    tod_standards = selectinload(models.Project.time_of_day_standards)
    tod_std_enum = tod_standards.joinedload(models.TimeOfDay.time_of_day_enum)

    # ── time_of_day_enums + time_of_day_enum_standards (1:N / M:N) ───────────
    time_of_day_enums = selectinload(models.Project.time_of_day_enums)
    tod_enum_standards = selectinload(models.Project.time_of_day_enum_standards)

    # ── einfache Collections (keine Sub-Relationen im Schema nötig) ───────────
    skills = selectinload(models.Project.skills)
    flags = selectinload(models.Project.flags)
    cast_rules = selectinload(models.Project.cast_rules)

    return [
        excel,
        admin, admin_address,
        teams, teams_dispatcher, teams_excel,
        teams_taa_person, teams_tla_low,
        teams_plan_periods,
        teams_clp_project, teams_clp_low,
        persons, persons_address,
        time_of_days, tod_enum,
        tod_standards, tod_std_enum,
        time_of_day_enums,
        tod_enum_standards,
        skills, flags, cast_rules,
    ]


def event_group_dialog_options() -> list:
    """Loader-Optionen für den EventGroup-Dialog-Batch-Load (minimale Variante).

    Verwendet, wenn ALLE EventGroups einer LocationPlanPeriod in einer einzigen
    Session geladen werden (get_flat_tree_for_dialog__location_plan_period).

    EventGroupForDialog benötigt nur:
      - event → time_of_day → time_of_day_enum

    Wegfall gegenüber der alten Variante:
      - event_groups (Kinder): kommen aus dem parent__children-Dict
      - event → location_plan_period → ...: nur location_plan_period_id (FK) genutzt
      - event → flags: EventForDialogTree hat kein flags-Feld
      - location_plan_period → plan_period → team: Master-Knoten braucht das nicht

    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    ev_tod = (
        joinedload(models.EventGroup.event)
        .joinedload(models.Event.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    return [ev_tod]


def avail_day_group_dialog_options() -> list:
    """Loader-Optionen für den AvailDayGroup-Dialog-Batch-Load (minimale Variante).

    Verwendet, wenn ALLE AvailDayGroups eines ActorPlanPeriods in einer einzigen
    Session geladen werden (get_flat_tree_for_dialog__actor_plan_period).

    AvailDayGroupForDialog benötigt nur:
      - avail_day → time_of_day → time_of_day_enum

    Wegfall gegenüber AvailDayGroupShow:
      - avail_day_groups (Kinder): kommen aus dem parent__children-Dict
      - avail_day → actor_plan_period → ...: nur actor_plan_period_id (FK) genutzt
      - actor_plan_period / avail_day_group (Parent-Chain): nicht benötigt

    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    ad_tod = (
        joinedload(models.AvailDayGroup.avail_day)
        .joinedload(models.AvailDay.time_of_day)
        .joinedload(models.TimeOfDay.time_of_day_enum)
    )
    return [ad_tod]


def event_button_update_options() -> list:
    """Loader-Optionen für ButtonEvent.on_appointment_moved (minimale Variante).

    Benötigt nur:
      - time_of_day → time_of_day_enum (für time_index)
      - time_of_day → project (für schemas.TimeOfDay Pflichtfeld)
      - time_of_day → project_standard (optional)
      - cast_group → nr_actors (für add_spin_box_num_employees + set_tooltip)

    Wegfall gegenüber EventShow:
      - event_group (rekursive Eltern-Kette): nicht benötigt
      - location_plan_period → ...: nicht benötigt
      - flags: nicht benötigt
      - skill_groups: nicht benötigt

    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    tod = (
        joinedload(models.Event.time_of_day).options(
            joinedload(models.TimeOfDay.time_of_day_enum),
            joinedload(models.TimeOfDay.project),
            joinedload(models.TimeOfDay.project_standard),
        )
    )
    cast = joinedload(models.Event.cast_group)
    return [tod, cast]


def event_for_button_options() -> list:
    """Loader-Optionen für EventForButton — für get_from__location_pp_date.

    Benötigt:
      - time_of_day → time_of_day_enum, project, project_standard (Pflichtfelder des Schemas)
      - skill_groups → skill (für _check_skill_groups_all_equal)
      - notes: skalares Feld, kein Load nötig

    Wegfall gegenüber EventShow:
      - event_group (rekursive Eltern-Kette): nicht benötigt
      - cast_group: nicht benötigt
      - flags: nicht benötigt
      - location_plan_period → ...: nicht benötigt (nur location_plan_period_id als FK)

    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    tod = (
        joinedload(models.Event.time_of_day).options(
            joinedload(models.TimeOfDay.time_of_day_enum),
            joinedload(models.TimeOfDay.project),
            joinedload(models.TimeOfDay.project_standard),
        )
    )
    skills = selectinload(models.Event.skill_groups).joinedload(models.SkillGroup.skill)
    return [tod, skills]


def team_location_assign_with_location_options() -> list:
    """Loader-Optionen für TeamLocationAssign → location_of_work + address.

    Für Queries, die TeamLocationAssign-Zeilen laden und anschließend
    schemas.LocationOfWork.model_validate() aufrufen — verhindert N Lazy-Loads
    für location_of_work.address.

    .unique() auf dem Query-Result ist Pflicht (joinedload-Deduplizierung).
    """
    return [
        joinedload(models.TeamLocationAssign.location_of_work)
        .joinedload(models.LocationOfWork.address)
    ]
