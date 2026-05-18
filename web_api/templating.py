"""Zentraler Jinja2Templates-Singleton für die gesamte Web-API."""

from datetime import datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from web_api.branding import role_branding
from web_api.palette import LOCATION_PALETTE, OKABE_ITO_PALETTE

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Paletten für alle Templates global verfügbar machen (vorher 3-fach dupliziert:
# _calendar_base.html, availability/index.html, employees/service.py).
templates.env.globals["location_palette"] = LOCATION_PALETTE
templates.env.globals["cb_palette"] = OKABE_ITO_PALETTE

# Rollen-Branding (Label + Farben) als Single Source of Truth fuer das
# role_kicker-Macro in templates/_macros/branding.html.
templates.env.globals["role_branding"] = role_branding

# Callable, damit der Wert je Request frisch ist (sonst friert das Jahr beim
# erstem Import ein und kippt erst beim naechsten Deploy auf das neue Jahr).
templates.env.globals["current_year"] = lambda: datetime.now().year
