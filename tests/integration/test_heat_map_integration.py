"""
Test-Script für Heat-Map Integration in frm_plan.py

Testet die grundlegende Funktionalität der Heat-Map-Integration
ohne das gesamte System zu starten.

Erstellt: 1. September 2025
"""

import sys
import os
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_workload_calculator_import():
    """Test ob WorkloadCalculator importiert werden kann"""
    try:
        from gui.plan_visualization.workload_calculator import WorkloadCalculator
        calculator = WorkloadCalculator()
        print("✅ WorkloadCalculator erfolgreich importiert und initialisiert")
        return True
    except Exception as e:
        print(f"❌ Fehler beim WorkloadCalculator Import: {e}")
        return False

def test_frm_plan_imports():
    """Test ob frm_plan.py mit neuen Imports funktioniert"""
    try:
        # Nur Import testen, nicht initialisieren
        from gui.frm_plan import FrmTabPlan
        print("✅ frm_plan.py Import mit Heat-Map-Integration erfolgreich")
        return True
    except Exception as e:
        print(f"❌ Fehler beim frm_plan.py Import: {e}")
        return False

def test_heat_map_methods_exist():
    """Test ob Heat-Map-Methoden in FrmTabPlan existieren"""
    try:
        from gui.frm_plan import FrmTabPlan
        
        # Prüfen ob neue Methoden existieren
        required_methods = [
            '_setup_heat_map_system',
            '_toggle_heat_map',
            '_update_all_appointment_field_styles',
            '_update_appointment_field_workload_display',
            '_calculate_appointment_workload',
            '_apply_workload_styling',
            '_create_enhanced_tooltip'
        ]
        
        for method_name in required_methods:
            if not hasattr(FrmTabPlan, method_name):
                print(f"❌ Methode {method_name} fehlt in FrmTabPlan")
                return False
        
        print("✅ Alle Heat-Map-Methoden in FrmTabPlan gefunden")
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Prüfen der Heat-Map-Methoden: {e}")
        return False

def run_integration_tests():
    """Führt alle Integrations-Tests aus"""
    print("🔍 Starte Heat-Map Integration Tests...")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: WorkloadCalculator Import
    if test_workload_calculator_import():
        tests_passed += 1
    
    # Test 2: frm_plan.py Import
    if test_frm_plan_imports():
        tests_passed += 1
    
    # Test 3: Heat-Map-Methoden existieren
    if test_heat_map_methods_exist():
        tests_passed += 1
    
    print("=" * 50)
    print(f"📊 Test-Ergebnisse: {tests_passed}/{total_tests} bestanden")
    
    if tests_passed == total_tests:
        print("🎉 Alle Tests bestanden! Heat-Map-Integration ist bereit.")
        print("\n📋 Nächste Schritte:")
        print("1. frm_plan.py in der Anwendung öffnen")
        print("2. 'Heat-Map anzeigen' Button im Side-Menu testen")
        print("3. Tooltips der AppointmentFields überprüfen")
        return True
    else:
        print("❌ Einige Tests fehlgeschlagen. Bitte Fehler beheben.")
        return False

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
