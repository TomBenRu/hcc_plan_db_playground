from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, text

from web_api.rate_limit import limiter

from web_api.admin.router import router as admin_router
from web_api.auth.router import router as auth_router
from web_api.desktop_api.router import router as desktop_api_router
from web_api.cancellations.router import router as cancellations_router
from web_api.config import get_settings
from web_api.dashboard.router import router as dashboard_router
from web_api.dependencies import get_db_session
from web_api.availability.router import router as availability_router
from web_api.dispatcher.router import router as dispatcher_router
from web_api.employees.router import router as employees_router
from web_api.exceptions import LoginRequired
from web_api.inbox.router import router as inbox_router
from web_api.offers.router import router as offers_router
from web_api.scheduler.setup import create_scheduler
from web_api.settings.router import router as settings_router
from web_api.swap_requests.router import router as swap_requests_router
from web_api.user_settings.router import router as user_settings_router

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

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 mit HTMX-freundlichem Trigger-Header für Toast-Nachrichten."""
    response = JSONResponse(
        status_code=429,
        content={"detail": "Zu viele Anfragen — bitte warte einen Moment."},
    )
    if request.headers.get("HX-Request") == "true":
        response.headers["HX-Trigger"] = "rate-limited"
    return response


app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(desktop_api_router)
app.include_router(dashboard_router)
app.include_router(dispatcher_router)
app.include_router(employees_router)
app.include_router(availability_router)
app.include_router(cancellations_router)
app.include_router(inbox_router)
app.include_router(settings_router)
app.include_router(swap_requests_router)
app.include_router(offers_router)
app.include_router(user_settings_router)


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, exc: LoginRequired) -> RedirectResponse:
    """Leitet zu /auth/login?next=... weiter wenn eine geschützte Route ohne Token aufgerufen wird."""
    return RedirectResponse(url=f"/auth/login?next={quote(exc.next_url)}")


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """DB-Constraint-Verletzung → 409 Conflict statt 500 Internal Server Error.

    Fuer UNIQUE-Verletzungen liefert psycopg2 eine DETAIL-Zeile, die wir als
    User-Message weitergeben. Fallback: der allgemeine Exception-String.
    """
    orig = getattr(exc, "orig", None)
    if orig is not None:
        detail = getattr(orig, "diag", None)
        message = getattr(detail, "message_detail", None) if detail else None
        if not message:
            message = str(orig).strip().splitlines()[0] if str(orig).strip() else str(exc)
    else:
        message = str(exc)
    return JSONResponse(
        status_code=409,
        content={"detail": message},
    )


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
