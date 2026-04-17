"""Desktop-API-Client: ExcelExportSettings-Operationen."""

from database import schemas
from gui.api_client.client import get_api_client


def create(settings: schemas.ExcelExportSettingsCreate) -> schemas.ExcelExportSettingsShow:
    data = get_api_client().post("/api/v1/excel-export-settings",
                                 json=settings.model_dump(mode="json"))
    return schemas.ExcelExportSettingsShow.model_validate(data)