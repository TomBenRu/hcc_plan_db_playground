"""Desktop-API Auth: DesktopUser-Dependency für Dispatcher/Admin-Zugriff."""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from web_api.auth.dependencies import get_current_user
from web_api.models.web_models import WebUser, WebUserRole


def _require_desktop_user(
    current_user: Annotated[WebUser, Depends(get_current_user)],
) -> WebUser:
    if not current_user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Keine Berechtigung")
    return current_user


DesktopUser = Annotated[WebUser, Depends(_require_desktop_user)]
