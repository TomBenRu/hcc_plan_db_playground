from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, text

from web_api.auth.router import router as auth_router
from web_api.config import get_settings
from web_api.dashboard.router import router as dashboard_router
from web_api.dependencies import get_db_session
from web_api.availability.router import router as availability_router
from web_api.employees.router import router as employees_router
from web_api.exceptions import LoginRequired
from web_api.scheduler.setup import create_scheduler

scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    settings = get_settings()
    scheduler = create_scheduler(settings.DATABASE_URL)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="hcc_plan Web-API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(employees_router)
app.include_router(availability_router)


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, exc: LoginRequired) -> RedirectResponse:
    """Leitet zu /auth/login?next=... weiter wenn eine geschützte Route ohne Token aufgerufen wird."""
    return RedirectResponse(url=f"/auth/login?next={quote(exc.next_url)}")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/auth/login")


@app.get("/health")
def health_check(session: Session = Depends(get_db_session)):
    try:
        session.exec(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "ok", "database": db_status}
