"""
Tests für Plan Visualization Commands

Einfache Tests um sicherzustellen, dass die Command Pattern Integration
korrekt funktioniert.

Erstellt: 1. September 2025  
Teil von: Workload Heat-Maps Feature Implementation - Tag 3
"""

import pytest
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from commands.plan_visualization_commands_to_remove import (
    HeatMapConfig,
    ToggleHeatMapCommand,
    ConfigureHeatMapCommand, 
    RefreshHeatMapDataCommand,
    create_toggle_heat_map_command
)


class TestHeatMapConfig:
    """Tests für HeatMapConfig dataclass"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = HeatMapConfig()
        
        assert config.enabled is False
        assert config.show_percentage is True
        assert config.show_appointments is True
        assert config.use_gradients is True
        assert config.plan_period is None
    
    def test_config_copy(self):
        """Test configuration deep copy"""
        original = HeatMapConfig(
            enabled=True,
            show_percentage=False,
            use_gradients=False
        )
        
        copy = original.copy()
        
        # Values should be equal
        assert copy.enabled == original.enabled
        assert copy.show_percentage == original.show_percentage
        assert copy.use_gradients == original.use_gradients
        
        # But should be different objects
        assert copy is not original
    
    def test_config_with_kwargs(self):
        """Test configuration with keyword arguments"""
        config = HeatMapConfig(
            enabled=True,
            show_percentage=False,
            show_appointments=False,
            use_gradients=False
        )
        
        assert config.enabled is True
        assert config.show_percentage is False
        assert config.show_appointments is False
        assert config.use_gradients is False


class TestToggleHeatMapCommand:
    """Tests für ToggleHeatMapCommand"""
    
    def test_toggle_mode_execute_undo(self):
        """Test toggle mode with execute and undo"""
        # Mock controller
        controller = Mock()
        controller.is_heat_map_enabled = False
        controller.toggle_heat_map = Mock(return_value=True)
        
        # Create command in toggle mode
        command = ToggleHeatMapCommand(controller, enabled=None)
        
        # Execute should toggle from False to True
        command.execute()
        controller.toggle_heat_map.assert_called_with(True)
        
        # Undo should restore to False
        command.undo()
        controller.toggle_heat_map.assert_called_with(False)
    
    def test_explicit_mode_execute_undo(self):
        """Test explicit enabled mode"""
        # Mock controller
        controller = Mock()
        controller.is_heat_map_enabled = False
        controller.toggle_heat_map = Mock(return_value=True)
        
        # Create command with explicit enabled=True
        command = ToggleHeatMapCommand(controller, enabled=True)
        
        # Execute should set to True
        command.execute()
        controller.toggle_heat_map.assert_called_with(True)
        
        # Undo should restore to False
        command.undo()
        controller.toggle_heat_map.assert_called_with(False)
    
    def test_redo_calls_execute(self):
        """Test that redo calls execute again"""
        controller = Mock()
        controller.is_heat_map_enabled = False
        controller.toggle_heat_map = Mock(return_value=True)
        
        command = ToggleHeatMapCommand(controller, enabled=True)
        
        # Execute first time
        command.execute()
        assert controller.toggle_heat_map.call_count == 1
        
        # Redo should execute again
        command.redo()
        assert controller.toggle_heat_map.call_count == 2


class TestConfigureHeatMapCommand:
    """Tests für ConfigureHeatMapCommand"""
    
    def test_configure_execute_undo(self):
        """Test configuration command execute and undo"""
        # Mock controller with methods
        controller = Mock()
        controller.is_heat_map_enabled = False
        controller.current_plan_period = None
        controller.toggle_heat_map = Mock()
        controller.set_plan_period = Mock()
        controller.configure_heat_map_display = Mock()
        
        # New configuration
        new_config = HeatMapConfig(
            enabled=True,
            show_percentage=False,
            show_appointments=True,
            use_gradients=False
        )
        
        command = ConfigureHeatMapCommand(controller, new_config)
        
        # Execute should apply new configuration
        command.execute()
        
        # Verify controller methods were called
        controller.toggle_heat_map.assert_called_with(True)
        controller.configure_heat_map_display.assert_called_with(
            show_percentage=False,
            show_appointments=True,
            use_gradients=False
        )
        
        # Undo should restore previous state
        command.undo()
        controller.toggle_heat_map.assert_called_with(False)  # Back to original


class TestRefreshHeatMapDataCommand:
    """Tests für RefreshHeatMapDataCommand"""
    
    def test_refresh_execute(self):
        """Test refresh command execution"""
        controller = Mock()
        controller.invalidate_cache = Mock()
        controller.refresh_heat_map_data = Mock()
        
        command = RefreshHeatMapDataCommand(controller)
        
        # Execute should call both methods
        command.execute()
        
        controller.invalidate_cache.assert_called_once()
        controller.refresh_heat_map_data.assert_called_once()
    
    def test_refresh_undo_does_nothing(self):
        """Test that refresh undo does nothing (as expected)"""
        controller = Mock()
        
        command = RefreshHeatMapDataCommand(controller)
        
        # Undo should not raise exception and do nothing
        command.undo()  # Should not crash
    
    def test_refresh_redo_calls_execute(self):
        """Test that refresh redo calls execute again"""  
        controller = Mock()
        controller.invalidate_cache = Mock()
        controller.refresh_heat_map_data = Mock()
        
        command = RefreshHeatMapDataCommand(controller)
        
        # Execute first time
        command.execute()
        assert controller.refresh_heat_map_data.call_count == 1
        
        # Redo should execute again
        command.redo()
        assert controller.refresh_heat_map_data.call_count == 2


class TestFactoryFunctions:
    """Tests für Factory-Functions"""
    
    def test_create_toggle_heat_map_command(self):
        """Test factory function for toggle command"""
        controller = Mock()
        
        command = create_toggle_heat_map_command(controller, enabled=True)
        
        assert isinstance(command, ToggleHeatMapCommand)
        assert command.controller is controller
        assert command.target_enabled is True
    
    def test_create_toggle_heat_map_command_none(self):
        """Test factory function for toggle command with None"""
        controller = Mock()
        
        command = create_toggle_heat_map_command(controller, enabled=None)
        
        assert isinstance(command, ToggleHeatMapCommand)
        assert command.target_enabled is None


def run_basic_functionality_test():
    """
    Grundfunktionalitätstest ohne pytest
    
    Führt einfache Smoke-Tests aus um sicherzustellen,
    dass die Commands grundsätzlich funktionieren.
    """
    print("🔍 Starte grundlegende Heat-Map Commands Tests...")
    
    try:
        # Test 1: HeatMapConfig
        config = HeatMapConfig(enabled=True, show_percentage=False)
        config_copy = config.copy()
        assert config_copy.enabled == True
        assert config_copy is not config
        print("✅ HeatMapConfig: OK")
        
        # Test 2: ToggleHeatMapCommand
        controller_mock = Mock()
        controller_mock.is_heat_map_enabled = False
        controller_mock.toggle_heat_map = Mock(return_value=True)
        
        toggle_cmd = ToggleHeatMapCommand(controller_mock, enabled=True)
        toggle_cmd.execute()
        controller_mock.toggle_heat_map.assert_called_with(True)
        print("✅ ToggleHeatMapCommand: OK")
        
        # Test 3: Factory Functions
        factory_cmd = create_toggle_heat_map_command(controller_mock, enabled=False)
        assert isinstance(factory_cmd, ToggleHeatMapCommand)
        print("✅ Factory Functions: OK")
        
        # Test 4: RefreshHeatMapDataCommand
        refresh_controller = Mock()
        refresh_controller.invalidate_cache = Mock()
        refresh_controller.refresh_heat_map_data = Mock()
        
        refresh_cmd = RefreshHeatMapDataCommand(refresh_controller)
        refresh_cmd.execute()
        
        refresh_controller.invalidate_cache.assert_called_once()
        refresh_controller.refresh_heat_map_data.assert_called_once()
        print("✅ RefreshHeatMapDataCommand: OK")
        
        print("\n🎉 Alle grundlegenden Tests bestanden!")
        print("📋 Command Pattern Integration ist funktionsfähig!")
        
        return True
        
    except Exception as e:
        print(f"❌ Test fehlgeschlagen: {e}")
        return False


if __name__ == "__main__":
    # Führe grundlegende Tests aus
    run_basic_functionality_test()
