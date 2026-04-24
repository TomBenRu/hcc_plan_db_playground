"""Zentraler Jinja2Templates-Singleton für die gesamte Web-API."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from web_api.palette import LOCATION_PALETTE, OKABE_ITO_PALETTE

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Paletten für alle Templates global verfügbar machen (vorher 3-fach dupliziert:
# _calendar_base.html, availability/index.html, employees/service.py).
templates.env.globals["location_palette"] = LOCATION_PALETTE
templates.env.globals["cb_palette"] = OKABE_ITO_PALETTE
