import logging
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import Depends, FastAPI, Request, Response, status

# Root-Logger auf INFO setzen, damit Application-Logger (Scheduler-Lock,
# Reminder-Job-Stats, Mail-Versand) in den Render-/Uvicorn-Logs sichtbar
# sind. Pythons Default ist WARNING, was alle `logger.info(...)`-Calls
# unsichtbar macht.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlmodel import Session, text

from web_api.rate_limit import limiter

from web_api.account.router import router as account_router
from web_api.admin.router import router as admin_router
from web_api.auth.router import router as auth_router
from web_api.desktop_api.router import router as desktop_api_router
from web_api.cancellations.router import router as cancellations_router
from web_api.config import get_settings
from web_api.dashboard.router import router as dashboard_router
from web_api.dependencies import get_db_session
from web_api.availability.router import router as availability_router
from web_api.dispatcher.router import router as dispatcher_router
from web_api.dispatcher_periods.router import router as dispatcher_periods_router
from web_api.employees.router import router as employees_router
from web_api.exceptions import LoginRequired
from web_api.help.router import router as help_router
from web_api.inbox.router import router as inbox_router
from web_api.dispatcher.notification_circles.router import router as notification_circles_router
from web_api.notification_groups.router import router as notification_groups_router
from web_api.offers.router import router as offers_router
from web_api.scheduler.advisory_lock import (
    acquire_scheduler_lock,
    release_scheduler_lock,
)
from web_api.scheduler.setup import create_scheduler
from web_api.settings.router import router as settings_router
from web_api.swap_requests.router import router as swap_requests_router
from web_api.user_settings.router import router as user_settings_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startet den APScheduler beim App-Start, aber nur in einem einzigen
    Worker pro DB. Die Singleton-Garantie kommt von einem PG-Advisory-Lock
    (siehe `web_api.scheduler.advisory_lock`).

    Workers ohne Lock laufen als reine HTTP-Worker — `create_scheduler` wird
    dort nicht aufgerufen, sodass `setup.get_scheduler()` `None` liefert
    und db_services-Hooks Reminder-Job-Registration sauber skippen.
    """
    settings = get_settings()
    lock_handle = acquire_scheduler_lock(settings.DATABASE_URL)
    scheduler = None
    if lock_handle.acquired:
        scheduler = create_scheduler(settings.DATABASE_URL)
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        release_scheduler_lock(lock_handle)


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


app.include_router(account_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(desktop_api_router)
app.include_router(dashboard_router)
app.include_router(dispatcher_router)
app.include_router(dispatcher_periods_router)
app.include_router(employees_router)
app.include_router(availability_router)
app.include_router(cancellations_router)
app.include_router(help_router)
app.include_router(inbox_router)
app.include_router(notification_groups_router)
app.include_router(notification_circles_router)
app.include_router(settings_router)
app.include_router(swap_requests_router)
app.include_router(offers_router)
app.include_router(user_settings_router)


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, exc: LoginRequired) -> Response:
    """Leitet zu /auth/login?next=... weiter wenn eine geschützte Route ohne Token aufgerufen wird.

    HTMX-Requests bekommen einen `HX-Redirect`-Header (Top-Level-Navigation
    statt Fragment-Swap). Klassische Browser-Forms bekommen einen 303 — damit
    POST/PATCH/DELETE bei der Weiterleitung zum Login-GET zwingen (nicht 307,
    das die Methode erhalten würde).
    """
    redirect_url = f"/auth/login?next={quote(exc.next_url)}"
    if request.headers.get("HX-Request") == "true":
        response = Response(status_code=status.HTTP_200_OK)
        response.headers["HX-Redirect"] = redirect_url
        return response
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@app.exception_handler(NoResultFound)
async def no_result_found_handler(request: Request, exc: NoResultFound) -> JSONResponse:
    """SQLAlchemy `.one()` ohne Ergebnis → 404 Not Found statt 500.

    Tritt typisch auf, wenn ein direkter ID-Lookup (z. B. `Team.get(uuid)`) ins Leere
    läuft — entweder weil die ID nicht existiert oder weil der Datensatz soft-deleted
    ist und der Service-Layer ihn ausfiltert. In beiden Fällen ist 404 die
    semantisch korrekte Antwort.
    """
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Resource not found or has been deleted."},
    )


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


@app.head("/", include_in_schema=False)
def root_head() -> Response:
    return Response(status_code=status.HTTP_200_OK)


@app.get("/health")
def health_check(session: Session = Depends(get_db_session)):
    try:
        session.exec(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "ok", "database": db_status}


@app.head("/health", include_in_schema=False)
def health_check_head() -> Response:
    """Lightweight Health-Probe ohne DB-Touch — fuer Render/Uptime-Monitore,
    die haeufig pingen und keine Body-Antwort brauchen."""
    return Response(status_code=status.HTTP_200_OK)
