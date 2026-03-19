"""db_services — SQLModel/SQLAlchemy 2.x Service Layer

Jede Klasse aus dem alten db_services.py ist nun ein eigenes Modul.
Die Import-Aliase unten stellen vollständige Rückwärtskompatibilität sicher:
    db_services.Person.get(...)  →  person.get(...)
    from database.db_services import Person, Team  →  funktioniert unverändert
"""

from ._common import log_function_info, LOGGING_ENABLED

from . import entities_api_to_db as EntitiesApiToDB
from . import project as Project
from . import team as Team
from . import person as Person
from . import location_of_work as LocationOfWork
from . import team_actor_assign as TeamActorAssign
from . import team_location_assign as TeamLocationAssign
from . import time_of_day as TimeOfDay
from . import time_of_day_enum as TimeOfDayEnum
from . import excel_export_settings as ExcelExportSettings
from . import address as Address
from . import max_fair_shifts_of_app as MaxFairShiftsOfApp
from . import cast_rule as CastRule
from . import plan_period as PlanPeriod
from . import location_plan_period as LocationPlanPeriod
from . import event_group as EventGroup
from . import cast_group as CastGroup
from . import event as Event
from . import actor_plan_period as ActorPlanPeriod
from . import avail_day_group as AvailDayGroup
from . import required_avail_day_groups as RequiredAvailDayGroups
from . import avail_day as AvailDay
from . import combination_locations_possible as CombinationLocationsPossible
from . import actor_location_pref as ActorLocationPref
from . import actor_partner_location_pref as ActorPartnerLocationPref
from . import skill as Skill
from . import skill_group as SkillGroup
from . import plan as Plan
from . import appointment as Appointment
