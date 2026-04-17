"""Desktop-API Aggregations-Router unter /api/v1."""

from fastapi import APIRouter

from web_api.desktop_api.appointment.router import router as appointment_router
from web_api.desktop_api.plan.router import router as plan_router
from web_api.desktop_api.plan.router import teams_router as plan_teams_router

router = APIRouter(prefix="/api/v1", tags=["desktop-api"])

router.include_router(plan_router)
router.include_router(plan_teams_router)
router.include_router(appointment_router)
