"""Desktop-API: ExcelExportSettings-Endpunkte (/api/v1/excel-export-settings)."""

from fastapi import APIRouter, status

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/excel-export-settings", tags=["desktop-excel-export-settings"])


@router.post("", response_model=schemas.ExcelExportSettingsShow,
             status_code=status.HTTP_201_CREATED)
def create_excel_export_settings(body: schemas.ExcelExportSettingsCreate, _: DesktopUser):
    return db_services.ExcelExportSettings.create(body)