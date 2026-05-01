"""Dashboard-Service: Domain-Logik fuer die Kachel-Anzeige.

Mapping URL → callable(session, user) → int liefert die Badge-Counts pro
Tile. Tiles ohne Eintrag zeigen keinen Badge.
"""

from typing import Callable

from sqlmodel import Session

from web_api.cancellations.service import (
    count_open_cancellations_for_dispatcher,
    count_open_cancellations_for_user,
)
from web_api.models.web_models import WebUser
from web_api.offers.service import (
    count_pending_offers_for_dispatcher,
    count_pending_offers_for_user,
)
from web_api.swap_requests.service import (
    count_active_swap_requests_for_user,
    count_swap_requests_pending_confirm_for_dispatcher,
)


# ── Badge-Count-Adapter je Tile-URL ──────────────────────────────────────────

_COUNT_FNS: dict[str, Callable[[Session, WebUser], int]] = {
    # Mitarbeiter
    "/cancellations/":             lambda s, u: count_open_cancellations_for_user(s, u.id),
    "/swap-requests":              lambda s, u: count_active_swap_requests_for_user(s, u.id),
    "/offers/mine":                lambda s, u: count_pending_offers_for_user(s, u.id),
    # Dispatcher
    "/dispatcher/cancellations":   lambda s, u: count_open_cancellations_for_dispatcher(s, u),
    "/dispatcher/swap-requests":   lambda s, u: count_swap_requests_pending_confirm_for_dispatcher(s, u),
    "/offers/dispatcher":          lambda s, u: count_pending_offers_for_dispatcher(s, u),
}


def resolve_tile_count(tile_url: str, session: Session, user: WebUser) -> int | None:
    """Ruft die Count-Funktion einer Kachel, wenn registriert. None heisst: kein Badge.

    Exceptions werden **nicht** verschluckt — eine fehlende DB-Spalte (z.B.
    ungelaufene Migration) soll einen lauten Dashboard-500 ausloesen statt
    still den Badge verschwinden zu lassen, was den User auf die falsche
    Faehrte fuehren wuerde.
    """
    fn = _COUNT_FNS.get(tile_url)
    if fn is None:
        return None
    return fn(session, user)