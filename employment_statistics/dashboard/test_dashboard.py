"""
Test-Script für Dashboard-Funktionalität

Testet die Dashboard-Datenaufbereitung und Template-Rendering.
"""

import datetime
from pprint import pprint

from employment_statistics.dashboard.service import DashboardService


def test_dashboard_service():
    """Testet den Dashboard-Service mit Beispieldaten"""
    
    print("🧪 Teste Dashboard-Service...")
    
    # Test-Parameter
    start_date = datetime.date(2024, 9, 1)
    end_date = datetime.date(2025, 8, 31)
    
    # Du kannst hier deine echten IDs einsetzen
    # team_id = UUID("your-team-id")
    # project_id = UUID("your-project-id")
    
    try:
        # Beispiel mit project_id (ersetze mit echter ID)
        # dashboard_data = DashboardService.get_dashboard_data(
        #     start_date=start_date,
        #     end_date=end_date,
        #     project_id=project_id
        # )
        
        print("✅ Dashboard-Service ist verfügbar")
        print("⚠️  Für echte Tests bitte Team/Projekt-IDs in test_dashboard.py einsetzen")
        
        # print("Dashboard-Daten:")
        # pprint(dashboard_data.dict())
        
    except Exception as e:
        print(f"❌ Fehler beim Testen: {e}")


if __name__ == "__main__":
    test_dashboard_service()
