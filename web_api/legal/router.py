"""Legal-Router: Impressum und Datenschutzerklaerung.

Beide Routen sind bewusst **public** — kein `LoggedInUser`-Dependency, kein
Cookie noetig. Das ist Pflicht: der DDG/§5 verlangt, dass das Impressum von
jeder Seite aus erreichbar ist, und das schliesst die Login-Seite ein.

Wuerde hier `LoggedInUser` erzwungen, geriete ein nicht-angemeldeter Besucher
ueber den Footer-Link in eine Endlosschleife: Login -> Footer -> Impressum ->
LoginRequired -> Login.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import HTMLResponse

from web_api.templating import templates

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/impressum", response_class=HTMLResponse)
def impressum(request: Request):
    return templates.TemplateResponse("legal/impressum.html", {"request": request})


@router.get("/datenschutz", response_class=HTMLResponse)
def datenschutz(request: Request):
    return templates.TemplateResponse("legal/datenschutz.html", {"request": request})