"""Service-Funktionen für ExcelExportSettings (Excel-Exporteinstellungen).

Speichert und aktualisiert die projektspezifischen Einstellungen für den
Excel-Export (z. B. Spaltenbreiten, Formatierungen). Einfaches CRUD ohne
Soft-Delete, da die Einstellungen direkt an einen Plan oder ein Team gebunden sind.
"""
import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(excel_export_settings_id: UUID) -> schemas.ExcelExportSettingsShow:
    with get_session() as session:
        return schemas.ExcelExportSettingsShow.model_validate(session.get(models.ExcelExportSettings, excel_export_settings_id))


def create(excel_settings: schemas.ExcelExportSettingsCreate) -> schemas.ExcelExportSettingsShow:
    log_function_info()
    with get_session() as session:
        ees = models.ExcelExportSettings(**excel_settings.model_dump())
        session.add(ees)
        session.flush()
        return schemas.ExcelExportSettingsShow.model_validate(ees)


def update(excel_export_settings: schemas.ExcelExportSettings) -> schemas.ExcelExportSettings:
    log_function_info()
    with get_session() as session:
        ees = session.get(models.ExcelExportSettings, excel_export_settings.id)
        for k, v in excel_export_settings.model_dump(exclude={'id'}).items():
            setattr(ees, k, v)
        session.flush()
        return schemas.ExcelExportSettings.model_validate(ees)