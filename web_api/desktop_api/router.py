"""Desktop-API Aggregations-Router unter /api/v1."""

from fastapi import APIRouter

from web_api.desktop_api.actor_plan_period.router import router as actor_plan_period_router
from web_api.desktop_api.address.router import router as address_router
from web_api.desktop_api.appointment.router import router as appointment_router
from web_api.desktop_api.avail_day.router import router as avail_day_router
from web_api.desktop_api.avail_day_group.router import router as avail_day_group_router
from web_api.desktop_api.cast_group.router import router as cast_group_router
from web_api.desktop_api.cast_rule.router import router as cast_rule_router
from web_api.desktop_api.event.router import router as event_router
from web_api.desktop_api.event_group.router import router as event_group_router
from web_api.desktop_api.location_plan_period.router import router as location_plan_period_router
from web_api.desktop_api.person.router import router as person_router
from web_api.desktop_api.plan.router import router as plan_router
from web_api.desktop_api.plan.router import teams_router as plan_teams_router
from web_api.desktop_api.plan_period.router import router as plan_period_router
from web_api.desktop_api.plan_period.router import teams_router as plan_period_teams_router
from web_api.desktop_api.project.router import router as project_router
from web_api.desktop_api.team.router import router as team_router
from web_api.desktop_api.team_actor_assign.router import router as team_actor_assign_router
from web_api.desktop_api.team_location_assign.router import router as team_location_assign_router

router = APIRouter(prefix="/api/v1", tags=["desktop-api"])

router.include_router(plan_router)
router.include_router(plan_teams_router)
router.include_router(appointment_router)
router.include_router(person_router)
router.include_router(team_router)
router.include_router(project_router)
router.include_router(address_router)
router.include_router(team_actor_assign_router)
router.include_router(team_location_assign_router)
router.include_router(plan_period_router)
router.include_router(plan_period_teams_router)
router.include_router(location_plan_period_router)
router.include_router(actor_plan_period_router)
router.include_router(avail_day_router)
router.include_router(event_router)
router.include_router(event_group_router)
router.include_router(cast_group_router)
router.include_router(cast_rule_router)
router.include_router(avail_day_group_router)
