"""Desktop-API Aggregations-Router unter /api/v1."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["desktop-api"])

# Sub-Router werden ab Phase 1 hier eingebunden:
# from web_api.desktop_api.plan.router import router as plan_router
# router.include_router(plan_router)
